"""
Tests for the offline CCT clause extractor's pure classification logic and
for the IA/NLP dashboard loader (app/pages/ia_nlp.py) — no network, no LLM.
"""
import sys, os, json, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipelines.nlp.cct_extractor import classify_clause, extract_weekly_hours, parse_ordinal, UNCATEGORIZED


# ---------------------------------------------------------------------------
# Pure classification function — synthetic PT-BR texts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("Jornada de trabalho semanal de 44 horas e escala 5x2.", "jornada"),
    ("Carga horária mensal de 220 horas.", "jornada"),
    ("Prorrogação da jornada mediante atividade suplementar as horas extras.", "hora_extra"),
    ("Pagamento da hora extra da primeira hora adicional a 70%.", "hora_extra"),
    ("Durante o intervalo das 22 horas o trabalho noturno recebe adicional.", "adicional_noturno"),
    ("Elegíveis ao adicional de periculosidade 30% os empregados que expostos a eletricidade.", "periculosidade"),
    ("Ambiente com grau de insalubridade elevado receberá adicionais de insalubridade 40%.", "insalubridade"),
    ("O empregado compensa horas ate esgotamento do banco de horas.", "banco_de_horas"),
    ("Durante as ferias o empregado pode vender abono pecuniário de um terço, após a concessão.", "ferias"),
    ("Estatui-se reajuste salarial na data-base de acordo com revisão salarial de 5,5%.", "reajuste"),
    ("Concessão de vale transporte, cesta básica e tíquete alimentação aos empregados.", "beneficios"),
    ("A empresa propiciará ambiente onde não haja assédio, violência, racismo e respeita igualdade e discriminação zero.", "clausulas_sociais"),
])
def test_classify_clause_categories(text, expected):
    result = classify_clause(text)
    assert result["category"] == expected
    assert 0.0 < result["confidence"] <= 0.95
    assert result["keywords_matched"]


def test_classify_clause_uncategorized():
    result = classify_clause("Texto irrelevante sem marcadores trabalhistas conhecidos.")
    assert result["category"] == UNCATEGORIZED
    assert result["keywords_matched"] == []
    assert result["confidence"] == 0.0


def test_classify_clause_is_deterministic():
    text = "Jornada semanal de 44 horas com banco de horas e adicional noturno às 22 horas."
    assert classify_clause(text) == classify_clause(text)
    assert classify_clause(text) == classify_clause(text)


def test_extract_weekly_hours():
    assert extract_weekly_hours(
        "redução da jornada de trabalho de 44 (quarenta e quatro) para 40 horas semanais") == [40]
    assert sorted(extract_weekly_hours(
        "jornada semanal de 44 horas, com 40 horas aos sábados")) == [40, 44]
    assert extract_weekly_hours("jornada semanal máxima de 44 (quarenta e quatro) horas") == [44]
    assert extract_weekly_hours("intervalo de 30 minutos entre as pausas") == []
    assert extract_weekly_hours("desconto de 40% no tempo de serviço") == []


def test_parse_ordinal():
    assert parse_ordinal("décima quarta") == 14
    assert parse_ordinal("vigésima terceira") == 23
    assert parse_ordinal("trigésima segunda") == 32
    assert parse_ordinal("quinta") == 5
    assert parse_ordinal("décima") == 10
    assert parse_ordinal("única") is None
    assert parse_ordinal("texto qualquer") is None


# ---------------------------------------------------------------------------
# Dashboard loader (_load_extracted_rules)
# ---------------------------------------------------------------------------
def test_load_extracted_rules_demo_file(tmp_path):
    import pandas as pd
    from app.pages.ia_nlp import _load_extracted_rules

    demo = {
        "total_clauses": 2,
        "avg_confidence": 0.8,
        "by_state": {"MG": 1, "RJ": 1},
        "by_category": {"jornada": 1, "nao_classificada": 1},
        "percent_counts": {"50": 1, "70": 0, "100": 1},
        "clauses": [
            {"union_state": "MG", "pdf_path": "Docs/CCTs/MG/x.pdf", "period": "2024-2025",
             "clause_number": "cláusula segunda", "title": "DA JORNADA", "text": "resumo",
             "category": "jornada", "keywords_matched": ["jornada"], "confidence": 0.8, "page": 3},
            {"union_state": "RJ", "pdf_path": "Docs/CCTs/RJ/y.pdf", "period": "2025-2026",
             "clause_number": "cláusula 7ª", "title": None, "text": "resumo",
             "category": UNCATEGORIZED, "keywords_matched": [], "confidence": 0.0, "page": 5},
        ],
    }
    demo_path = tmp_path / "cct_extracted_rules.json"
    demo_path.write_text(json.dumps(demo, ensure_ascii=False), encoding="utf-8")

    data, df, message = _load_extracted_rules(demo_path)
    assert message is None
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df["union_state"]) == ["MG", "RJ"]
    assert "category" in df.columns and "confidence" in df.columns
    assert data["by_state"] == {"MG": 1, "RJ": 1}


def test_load_extracted_rules_missing_file(tmp_path):
    from app.pages.ia_nlp import _load_extracted_rules

    data, df, message = _load_extracted_rules(tmp_path / "nao_existe.json")
    assert data is None
    assert df.empty
    assert message == "missing"


# ---------------------------------------------------------------------------
# Real extraction JSON (if it exists in this worktree)
# ---------------------------------------------------------------------------
REQUIRED_JSON_KEYS = [
    "extraction_method", "source_count", "readable_source_count", "total_clauses",
    "avg_confidence", "by_state", "by_category", "percent_counts", "validation",
    "sources", "clauses",
]
REQUIRED_CLAUSE_KEYS = [
    "union_state", "pdf_path", "clause_number", "category",
    "keywords_matched", "confidence", "page",
]


def _real_extraction_json():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gold', 'governance', 'cct_extracted_rules.json')
    if not os.path.exists(path):
        pytest.skip("cct_extracted_rules.json not generated in this worktree")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_real_extraction_json_structure():
    data = _real_extraction_json()
    for key in REQUIRED_JSON_KEYS:
        assert key in data, f"missing key: {key}"
    assert data["extraction_method"] == "pypdf + regex rules"
    assert data["total_clauses"] >= 30
    assert 0.0 <= data["avg_confidence"] <= 1.0
    assert data["readable_source_count"] >= 1
    assert len(data["sources"]) == data["source_count"]


def test_real_extraction_json_clauses():
    data = _real_extraction_json()
    assert len(data["clauses"]) == data["total_clauses"]
    for clause in data["clauses"]:
        for key in REQUIRED_CLAUSE_KEYS:
            assert key in clause, f"clause missing key: {key}"
        assert isinstance(clause["confidence"], float)
        assert 0.0 <= clause["confidence"] <= 1.0
        assert clause["union_state"] in ("MG", "RJ", "RN")
        assert clause["category"]
