"""
Offline CCT/ACT clause extractor (pypdf + regex classification).

Extracts clause structure from the real Collective Bargaining Agreement PDFs
stored under ``Docs/CCTs/`` (MG / RJ / RN sanitation unions) and classifies
clauses into labor-compliance categories using keyword / term-expansion rules
in Portuguese. No LLM and no external APIs are used: 100% offline, fully
deterministic and reproducible (no randomness involved anywhere).

Usage:
    python pipelines/nlp/cct_extractor.py

Output:
    data/gold/governance/cct_extracted_rules.json
"""
from __future__ import annotations

import io
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CCT_ROOT = REPO_ROOT / "Docs" / "CCTs"
OUTPUT_PATH = REPO_ROOT / "data" / "gold" / "governance" / "cct_extracted_rules.json"
DIM_CCT_RULE_VERSION = REPO_ROOT / "data" / "gold" / "dim_cct_rule_version.parquet"

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - dependency guard
    PdfReader = None

# OCR is an *optional* fallback for scanned PDFs (no text layer). Both
# pytesseract (+ Pillow) and the tesseract binary are deliberately imported
# lazily inside detection/extraction helpers: if anything is missing the
# extractor degrades gracefully with ``ocr_available: false`` instead of
# failing the whole run.
TESSERACT_FALLBACK_BINARIES = (
    "C:/Program Files/Tesseract-OCR/tesseract.exe",  # UB-Mannheim Windows installer
    "/usr/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
)

# Readability heuristic: a PDF counts as readable when at least 50% of its
# pages yield more than 50 characters of text and the document has >= 500
# characters in total. Below that the source is treated as scanned-only
# (no text layer) and marked ``source_readable: false`` instead of failing.
MIN_PAGE_CHARS = 50
MIN_TOTAL_CHARS = 500
READABLE_PAGE_SHARE = 0.5

SUMMARY_TEXT_CHARS = 220

# ---------------------------------------------------------------------------
# Category keyword rules (Portuguese regex patterns on normalized text)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "periculosidade": ["periculosidade", "perigoso"],
    "insalubridade": ["insalubridade", "insalubre"],
    "adicional_noturno": ["noturno", "22h", "22 horas", "22 (vinte e duas) horas"],
    "hora_extra": [
        r"horas?\s+extras?",
        "atividade suplementar",
        r"horas?\s+suplementa(?:r|res)",
    ],
    "banco_de_horas": ["banco de horas", r"compensa\w+ de horas"],
    "jornada": ["jornada", "horário", "semanal", "carga horária", "descanso semanal"],
    "ferias": [r"f[ée]rias", "abono pecuniário"],
    "reajuste": [
        "reajuste",
        "revisão salarial",
        "correção salarial",
        r"data-?\s?base",
        "dissídio",
    ],
    "beneficios": [
        "cesta", "alimentação", "refeição", "plr",
        "participação nos lucros", "creche", "tíquete", "ticket",
        "auxílio", "vale",
    ],
    "clausulas_sociais": [
        "assédio", "igualdade", "maternidade", "discriminação",
        "raça", "ética", "integridade", "convivência",
    ],
}

# Tie-break priority: specific additives win before generic jornada terms.
CATEGORY_PRIORITY = [
    "adicional_noturno",
    "hora_extra",
    "periculosidade",
    "insalubridade",
    "banco_de_horas",
    "ferias",
    "clausulas_sociais",
    "reajuste",
    "beneficios",
    "jornada",
]

UNCATEGORIZED = "nao_classificada"

PERCENT_PATTERN = re.compile(r"\b(50|70|100)\s*%")
WEEKLY_HOURS_PATTERN = re.compile(
    r"(?<!\d)(30|40|44)(?!\d)\s*(?:\([^)]{0,40}\))?\s*horas?\b",
    re.IGNORECASE,
)
WEEKLY_HOURS_CONTEXT_PATTERN = re.compile(
    r"jornada|carga horária|horas?\s+semanais|semanal",
    re.IGNORECASE,
)
MINUTES_GUARD_PATTERN = re.compile(r"(?<!\d)(30|40|44)(?!\d)\s*(?:\([^)]*\))?\s*minutos?", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Clause header patterns.
#   Numeric form  : "CLÁUSULA 12ª - TÍTULO" (Aguas do Rio / RJ)
#   Ordinal form  : "CLÁUSULA DÉCIMA QUINTA – TÍTULO" (Copasa / MG)
# Body references inside paragraphs (lowercase, no separator/title) are
# filtered out by the uppercase-title requirement of the ordinal pattern.
# ---------------------------------------------------------------------------
NUMERIC_HEADER_PATTERN = re.compile(
    r"cl[áa]usula\s+(?P<num>\d{1,3})\s*[ªº°a]?\s*[-–—:.]\s*(?P<title>[^\n]{0,110})",
    re.IGNORECASE,
)
ORDINAL_HEADER_PATTERN = re.compile(
    r"cl[áa]usula\s+(?P<ord>(?:(?:vig[ée]sima|tr[ée]sima|d[ée]cima)\s+)?"
    r"(?:primeira|segunda|terceira|quarta|quinta|sexta|s[ée]tima|oitava|nona|[uú]nica))"
    r"\s*[.,]?[ \t]*[-–—:.[ \t]?]*(?P<title>[^\n]{0,110})",
    re.IGNORECASE,
)

ORDINAL_UNITS = {
    "primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4,
    "quinta": 5, "sexta": 6, "sétima": 7, "setima": 7,
    "oitava": 8, "nona": 9, "única": 0, "unica": 0,
}
ORDINAL_MAGNITUDE = {"décima": 10, "decima": 10, "vigésima": 20, "vigesima": 20, "trigésima": 30, "trigesima": 30}


def norm_text(text: str) -> str:
    """NFC-normalize and lowercase text for deterministic matching."""
    return unicodedata.normalize("NFC", text).lower()


def parse_ordinal(ordinal_phrase: str) -> int | None:
    """Map a Portuguese ordinal clause phrase (e.g. 'décima quarta') to a number."""
    cleaned = re.sub(r"\s+", " ", norm_text(ordinal_phrase).strip())
    words = cleaned.split(" ")
    if "unica" in words or "única" in words:
        return None
    magnitude = 0
    for word in words:
        if word in ORDINAL_MAGNITUDE:
            magnitude += ORDINAL_MAGNITUDE[word]
        elif word in ORDINAL_UNITS:
            return magnitude + ORDINAL_UNITS[word]
        else:
            return None
    return magnitude if magnitude else None


def find_cct_pdfs(root: Path = CCT_ROOT) -> list[Path]:
    """List all ACT/CCT PDFs under Docs/CCTs (any state/company/vigência)."""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.pdf"))


def extract_pdf_texts(pdf_path: Path) -> list[str]:
    """Return per-page text for a PDF (may contain empty strings)."""
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def pdf_readability(page_texts: list[str]) -> tuple[bool, int, float]:
    """Return (readable, total_chars, share_of_pages_with_text)."""
    total_chars = sum(len(t) for t in page_texts)
    text_pages = sum(1 for t in page_texts if len(t.strip()) > MIN_PAGE_CHARS)
    share = (text_pages / len(page_texts)) if page_texts else 0.0
    readable = share >= READABLE_PAGE_SHARE and total_chars >= MIN_TOTAL_CHARS
    return readable, total_chars, share


# ---------------------------------------------------------------------------
# Optional OCR fallback (scanned PDFs without a text layer)
# ---------------------------------------------------------------------------
def detect_ocr_environment() -> tuple[bool, str, str]:
    """Lazy OCR availability probe. Returns (available, note, tesseract_binary).

    Only ``pytesseract`` is imported here; the tesseract engine itself is a
    system binary located via PATH (plus well-known install locations).
    Degrades gracefully instead of raising.
    """
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False, ("pytesseract not installed (optional dependency; "
                       "pip install -r requirements-ocr.txt)"), ""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False, ("Pillow not installed (optional dependency; "
                       "pip install -r requirements-ocr.txt)"), ""
    binary = shutil.which("tesseract")
    if binary is None:
        for candidate in TESSERACT_FALLBACK_BINARIES:
            if Path(candidate).exists():
                binary = candidate
                break
    if binary is None:
        return False, ("pytesseract installed but the tesseract binary was not "
                       "found on PATH"), ""
    return True, "", binary


def resolve_ocr_language(binary: str) -> str:
    """Prefer the 'por' traineddata when available, otherwise 'eng'.

    Deterministic: resolves against ``binary`` explicitly and the
    ``TESSDATA_PREFIX`` environment variable the engine itself honours.
    """
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = binary
    try:
        languages = pytesseract.get_languages(config="")
    except Exception:
        return "eng"
    return "por" if "por" in languages else "eng"


def ocr_pdf_page_texts(pdf_path: Path, binary: str, language: str) -> tuple[list[str], dict]:
    """OCR the embedded page images of a scanned PDF via tesseract.

    Requires pytesseract + Pillow. Returns per-page OCR text (pages whose
    images fail get an empty string) and the images actually OCR'd.

    Honesty rules:
      * a page without an embedded raster image yields '' (pypdf cannot render
        vector PDFs to pixels);
      * if a PDF exposes no images at all, text coercion is impossible and the
        caller must report the OCR as ineffective rather than fabricate a pass.
    """
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = binary
    reader = PdfReader(str(pdf_path))
    page_texts: list[str] = []
    images_ocrd = 0
    for page in reader.pages:
        page_text = ""
        images = list(page.images)
        for image_obj in images:
            try:
                image = Image.open(io.BytesIO(image_obj.data))
                text = pytesseract.image_to_string(image, lang=language)
            except Exception:
                text = ""
            page_text += text + "\n"
            if text.strip():
                images_ocrd += 1
        page_texts.append(page_text)
    meta = {"images_ocrd": images_ocrd}
    return page_texts, meta


def parse_pdf_path(pdf_path: Path) -> dict:
    """Derive union state, company, and vigência period from the CCT folder layout."""
    relative = pdf_path.relative_to(REPO_ROOT)
    parts = relative.parts  # Docs / CCTs / STATE / COMPANY / PERIOD / file.pdf
    union_state = parts[2] if len(parts) > 2 else ""
    company = parts[3] if len(parts) > 3 else ""
    period = parts[4] if len(parts) > 4 else ""
    years = re.findall(r"\d{4}", period)
    year_start = int(years[0]) if years else None
    year_end = int(years[-1]) if years else None
    return {
        "pdf_path": relative.as_posix(),
        "union_state": union_state,
        "company": company,
        "period": period,
        "year_start": year_start,
        "year_end": year_end,
    }


# ---------------------------------------------------------------------------
# Pure classification function (unit-tested directly)
# ---------------------------------------------------------------------------
def classify_clause(text: str) -> dict:
    """Classify a clause body/title into a labor-rule category.

    Returns a dict with:
        category          : best-matching category or ``nao_classificada``
        keywords_matched  : matched keyword patterns for that category
        confidence        : heuristic confidence in [0.0, 0.95]
    Deterministic: identical input always yields identical output.
    """
    normalized = norm_text(text)
    scores: dict[str, list[str]] = {}
    for category, patterns in CATEGORY_KEYWORDS.items():
        hits: list[str] = []
        for pattern in patterns:
            if re.search(pattern, normalized):
                hits.append(pattern)
        if hits:
            scores[category] = hits

    category = UNCATEGORIZED
    matched: list[str] = []
    max_hits = 0
    for cat in CATEGORY_PRIORITY:
        hits = scores.get(cat, [])
        if hits and len(hits) > max_hits:
            category = cat
            matched = hits
            max_hits = len(hits)

    if category == UNCATEGORIZED:
        return {"category": UNCATEGORIZED, "keywords_matched": [], "confidence": 0.0}

    if max_hits >= 5:
        confidence = 0.95
    else:
        confidence = 0.45 + 0.2 * (max_hits - 1) + 0.15
    return {"category": category, "keywords_matched": matched, "confidence": round(min(0.95, confidence), 2)}


def extract_numbers(pattern: re.Pattern, text: str, exclude: re.Pattern | None = None) -> list[str]:
    """Extract distinct tokens captured by ``pattern`` (group 1), excluding overlaps."""
    if exclude:
        text = exclude.sub(lambda match: " " * (match.end() - match.start()), text)
    found = list(dict.fromkeys(match.group(1) for match in pattern.finditer(text)))
    return found


def extract_weekly_hours(text: str) -> list[int]:
    """Find weekly-hour values (30/40/44) inside a jornada clauses text."""
    normalized = norm_text(text)
    if not WEEKLY_HOURS_CONTEXT_PATTERN.search(normalized):
        return []
    if MINUTES_GUARD_PATTERN.search(normalized):
        return []
    values = extract_numbers(WEEKLY_HOURS_PATTERN, normalized)
    return sorted({int(v) for v in values})


def count_percent_occurrences(text: str) -> dict[str, int]:
    """Count 50% / 70% / 100% mentions inside a clause."""
    counts = {"50": 0, "70": 0, "100": 0}
    for match in PERCENT_PATTERN.finditer(norm_text(text)):
        counts[match.group(1)] += 1
    return counts


# ---------------------------------------------------------------------------
# Clause structure extraction
# ---------------------------------------------------------------------------
def build_page_offsets(page_texts: list[str]) -> tuple[str, list[int]]:
    """Concatenate page texts keeping the start offset of each page."""
    full_text = ""
    offsets = []
    for page_text in page_texts:
        offsets.append(len(full_text))
        full_text += page_text + "\n"
    return full_text, offsets


def page_for_offset(offsets: list[int], offset: int) -> int:
    """1-based page number containing a given absolute text offset."""
    page = 0
    for index, start in enumerate(offsets):
        if offset >= start:
            page = index + 1
    return page


def clause_page_offset(full_text: str, start: int, next_start: int) -> str:
    """Clause body text: from the header start up to the next header."""
    return full_text[start:max(next_start, start)]


def locate_clause_headers(full_text: str) -> list[dict]:
    """Find clause header markers (numeric and ordinal forms) in original text.

    Matching is case-insensitive on the original text (accent-relevant), and
    ordinal headers are real headers only when the remainder of the line
    starts with an uppercase letter (ACT titles are written in ALL CAPS);
    lowercase follow-ups are body references and are filtered out.
    """
    candidates: list[dict] = []

    for match in NUMERIC_HEADER_PATTERN.finditer(full_text):
        number = int(match.group("num"))
        candidates.append({
            "start": match.start(),
            "number": number,
            "display": f"cláusula {match.group('num')}ª",
            "title": (match.group("title") or "").strip(),
        })

    for match in ORDINAL_HEADER_PATTERN.finditer(full_text):
        title = (match.group("title") or "").strip()
        if title and not title[0].isupper():
            continue
        number = parse_ordinal(match.group("ord"))
        candidates.append({
            "start": match.start(),
            "number": number,
            "display": f"cláusula {norm_text(match.group('ord')).title()}",
            "title": title,
        })

    candidates.sort(key=lambda entry: entry["start"])
    seen_numbers: set[int] = set()
    unique: list[dict] = []
    for entry in candidates:
        if entry["number"] is not None:
            if entry["number"] in seen_numbers:
                continue
            seen_numbers.add(entry["number"])
        unique.append(entry)
    return unique


def split_clauses(full_text: str, headers: list[dict]) -> list[dict]:
    """Slice the document text into clause segments (header + body)."""
    segments: list[dict] = []
    for index, header in enumerate(headers):
        next_start = headers[index + 1]["start"] if index + 1 < len(headers) else len(full_text)
        body = clause_page_offset(full_text, header["start"], next_start)
        title = header["title"]
        if not title:
            first_line = body.splitlines()[1] if len(body.splitlines()) > 1 else ""
            title = first_line.strip()[:110]
        segments.append({**header, "title": title, "body": body})
    return segments


def classify_document_segments(full_text: str, meta: dict, offsets: list[int]) -> tuple[list[dict], dict, set[int]]:
    """Split clause segments out of ``full_text`` and classify each segment.

    Returns (clauses, percent_totals, weekly_hours_set).
    """
    headers = locate_clause_headers(full_text)
    segments = split_clauses(full_text, headers)

    percent_totals = {"50": 0, "70": 0, "100": 0}
    doc_weekly_hours: set[int] = set()
    clauses: list[dict] = []
    for segment in segments:
        body = " ".join(segment["body"].split())
        summary = body[:SUMMARY_TEXT_CHARS]
        for percent, hits in count_percent_occurrences(segment["body"]).items():
            percent_totals[percent] += hits
        title_classification = classify_clause(segment["title"] or "")
        classification = classify_clause(segment["title"] + "\n" + segment["body"])
        if title_classification["category"] != UNCATEGORIZED:
            # Clause titles name the rule directly; they outrank body noise.
            classification["category"] = title_classification["category"]
            classification["keywords_matched"] = sorted(
                set(classification["keywords_matched"]) | set(title_classification["keywords_matched"])
            )
            classification["confidence"] = round(max(title_classification["confidence"], classification["confidence"]), 2)
        clause = {
            "union_state": meta["union_state"],
            "pdf_path": meta["pdf_path"],
            "period": meta["period"],
            "company": meta["company"],
            "clause_number": segment["display"],
            "clause_order": segment["number"],
            "title": segment["title"] or None,
            "text": summary,
            "category": classification["category"],
            "keywords_matched": classification["keywords_matched"],
            "confidence": classification["confidence"],
            "page": page_for_offset(offsets, segment["start"]),
        }
        if clause["category"] == "jornada":
            weekly_hours = extract_weekly_hours(segment["title"] + "\n" + segment["body"])
            clause["weekly_hours"] = weekly_hours
            doc_weekly_hours.update(weekly_hours)
        clauses.append(clause)
    return clauses, percent_totals, doc_weekly_hours


def extract_clauses_from_pdf(pdf_path: Path) -> dict:
    """Full local pipeline for one PDF: readability, OCR fallback, splitting, classification."""
    meta = parse_pdf_path(pdf_path)
    empty = {"meta": meta, "clauses": [], "percent_counts": {}, "weekly_hours": []}
    if PdfReader is None:
        source_info = {
            **meta, "pages": 0, "total_text_chars": 0, "readable_page_share": 0.0,
            "source_readable": False, "clause_count": 0,
            "extraction_method": "none",
            "ocr_available": False, "ocr_note": "pypdf not installed",
        }
        return {**empty, "source_info": source_info}

    try:
        page_texts = extract_pdf_texts(pdf_path)
    except Exception:  # unreadable/corrupted file: keep honest, do not crash
        source_info = {
            **meta, "pages": 0, "total_text_chars": 0, "readable_page_share": 0.0,
            "source_readable": False, "clause_count": 0,
            "extraction_method": "none",
            "ocr_available": False, "ocr_note": "pypdf could not open the PDF",
        }
        return {**empty, "source_info": source_info}

    readable, total_chars, share = pdf_readability(page_texts)
    source_info = {
        **meta,
        "pages": len(page_texts),
        "total_text_chars": total_chars,
        "readable_page_share": round(share, 3),
        "source_readable": readable,
        "clause_count": 0,
    }
    if readable:
        source_info["extraction_method"] = "pypdf+regex"
        full_text, offsets = build_page_offsets(page_texts)
        clauses, percent_totals, doc_weekly_hours = classify_document_segments(full_text, meta, offsets)
        source_info["clause_count"] = len(clauses)
        return {
            **empty,
            "source_info": source_info,
            "clauses": clauses,
            "percent_counts": percent_totals,
            "weekly_hours": sorted(doc_weekly_hours),
        }

    # Scanned PDF (no text layer): optional tesseract OCR fallback.
    source_info["ocr_available"] = False
    ocr_available, ocr_note, binary = detect_ocr_environment()
    source_info.update({"ocr_available": ocr_available, "ocr_note": ocr_note})
    if not ocr_available:
        source_info["extraction_method"] = "none"
        return {**empty, "source_info": source_info}

    language = resolve_ocr_language(binary)
    try:
        ocr_texts, ocr_meta = ocr_pdf_page_texts(pdf_path, binary, language)
    except Exception as exc:  # OCR is best-effort: report, never fail the run
        source_info.update({
            "ocr_used": False,
            "ocr_note": f"OCR attempt failed: {exc}",
            "extraction_method": "none",
            "ocr_language": language,
        })
        return {**empty, "source_info": source_info}

    ocr_total = sum(len(text) for text in ocr_texts)
    ocr_used = ocr_total >= MIN_TOTAL_CHARS and ocr_meta["images_ocrd"] > 0
    source_info.update({
        "ocr_used": ocr_used,
        "ocr_language": language,
        "ocr_total_text_chars": ocr_total,
        "ocr_images_ocrd": ocr_meta["images_ocrd"],
        "ocr_pages_ocrd": sum(1 for t in ocr_texts if t.strip()),
        "ocr_note": ("scanned-only PDF rescued via tesseract OCR" if ocr_used
                     else "OCR produced no usable text (no embedded page images or unreadable output)"),
    })
    if not ocr_used:
        source_info["extraction_method"] = "none"
        return {**empty, "source_info": source_info}

    source_info["extraction_method"] = "pypdf+regex+ocr"
    full_text, offsets = build_page_offsets(ocr_texts)
    clauses, percent_totals, doc_weekly_hours = classify_document_segments(full_text, meta, offsets)
    source_info["clause_count"] = len(clauses)
    return {
        **empty,
        "source_info": source_info,
        "clauses": clauses,
        "percent_counts": percent_totals,
        "weekly_hours": sorted(doc_weekly_hours),
    }


# ---------------------------------------------------------------------------
# Semantic validation against dim_cct_rule_version (non-blocking)
# ---------------------------------------------------------------------------
def dim_weekly_hours_for_period(state: str, year_start: int | None, year_end: int | None) -> list[int]:
    """Collect standard_weekly_hours from dim rows overlapping the ACT period."""
    try:
        import pandas as pd
        frame = pd.read_parquet(DIM_CCT_RULE_VERSION)
    except Exception:
        return []
    if frame.empty or "state" not in frame.columns:
        return []
    valid_from = pd.to_datetime(frame["valid_from"])
    valid_to = pd.to_datetime(frame["valid_to"])
    mask = frame["state"].astype(str) == state
    if year_start is not None:
        mask &= (valid_from.dt.year <= year_end) & (valid_to.dt.year >= year_start)
    return sorted({int(value) for value in frame.loc[mask, "standard_weekly_hours"].dropna().unique()})


def validate_weekly_hours(extracted: list[int], dim_values: list[int]) -> str:
    """Return 'match' / 'mismatch' / 'no_data' for one doc vs dimensions."""
    if not extracted or not dim_values:
        return "no_data"
    return "match" if set(extracted).issubset(set(dim_values)) else "mismatch"


def run() -> dict:
    """Extract clauses from every real CCT PDF and persist the gold JSON."""
    pdfs = find_cct_pdfs()
    sources: list[dict] = []
    clauses: list[dict] = []
    validation: list[dict] = []
    percent_totals = {"50": 0, "70": 0, "100": 0}
    readable_count = 0
    ocr_rescued_count = 0

    for pdf_path in pdfs:
        result = extract_clauses_from_pdf(pdf_path)
        source_info = result["source_info"]
        sources.append(source_info)
        contributes = source_info.get("source_readable") or source_info.get("ocr_used", False)
        if not contributes:
            continue
        if source_info.get("source_readable"):
            readable_count += 1
        if source_info.get("ocr_used"):
            ocr_rescued_count += 1
        clauses.extend(result["clauses"])
        for percent, hits in result["percent_counts"].items():
            percent_totals[percent] += hits
        meta = result["meta"]
        extracted_hours = result["weekly_hours"]
        dim_hours = dim_weekly_hours_for_period(meta["union_state"], meta["year_start"], meta["year_end"])
        validation.append({
            "pdf_path": meta["pdf_path"],
            "union_state": meta["union_state"],
            "period": meta["period"],
            "extraction_method": source_info.get("extraction_method"),
            "extracted_weekly_hours": extracted_hours,
            "dim_weekly_hours": dim_hours,
            "status": validate_weekly_hours(extracted_hours, dim_hours),
        })

    by_state: dict[str, int] = {}
    by_category: dict[str, int] = {}
    weekly_hours_by_state: dict[str, list[int]] = {}
    for clause in clauses:
        state = clause["union_state"]
        category = clause["category"]
        by_state[state] = by_state.get(state, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        for value in clause.get("weekly_hours", []):
            weekly_hours_by_state.setdefault(state, [])
            if value not in weekly_hours_by_state[state]:
                weekly_hours_by_state[state].append(value)
    weekly_hours_by_state = {state: sorted(values) for state, values in weekly_hours_by_state.items()}
    by_state = dict(sorted(by_state.items()))
    by_category = dict(sorted(by_category.items()))

    conformances = [entry for entry in validation if entry["status"] == "match"]
    mismatches = [entry for entry in validation if entry["status"] == "mismatch"]
    checked = [entry for entry in validation if entry["status"] in ("match", "mismatch")]

    ocr_languages = sorted({s["ocr_language"] for s in sources if s.get("ocr_used")})

    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "pypdf + regex rules",
        "offline": True,
        "llm_used": False,
        "ocr_fallback": {
            "enabled": True,
            "used_for_sources": ocr_rescued_count,
            "languages": ocr_languages,
            "per_source_id": "sources[*].extraction_method = 'pypdf+regex+ocr' "
                             "plus sources[*].ocr_used / ocr_note for details",
        },
        "source_count": len(pdfs),
        "readable_source_count": readable_count,
        "ocr_rescued_source_count": ocr_rescued_count,
        "unreadable_source_count": len(pdfs) - readable_count - ocr_rescued_count,
        "total_clauses": len(clauses),
        "avg_confidence": round(sum(c["confidence"] for c in clauses) / len(clauses), 3) if clauses else 0.0,
        "by_state": by_state,
        "by_category": by_category,
        "percent_counts": percent_totals,
        "weekly_hours_by_state": weekly_hours_by_state,
        "validation": {
            "weekly_hours": {
                "checked": len(checked),
                "matches": len(conformances),
                "mismatches": mismatches,
            },
        },
        "sources": sources,
        "extraction_note": (
            "Scanned PDFs (no text layer) attempt an optional tesseract OCR "
            "fallback; without OCR tooling they stay marked source_readable: "
            "false and are excluded from the extract."
            if readable_count < len(pdfs) else
            "All sources readable."
        ),
        "clauses": clauses,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return document


def main() -> None:
    document = run()
    print(f"cct_extracted_rules.json -> {OUTPUT_PATH}")
    print(f"sources={document['source_count']} readable={document['readable_source_count']} "
          f"ocr_rescued={document['ocr_rescued_source_count']} "
          f"clauses={document['total_clauses']} avg_confidence={document['avg_confidence']}")
    print(f"by_state={document['by_state']}")
    print(f"by_category={document['by_category']}")


if __name__ == "__main__":
    main()
