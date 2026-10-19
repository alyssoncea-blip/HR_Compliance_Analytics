"""Gold promotion tests: extracted CCT clauses -> dim_cct_clause.parquet,
semantic app.data.cct_clauses() consumer and CCT<->UC mapping linkage."""
import sys, os, json
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipelines.nlp.cct_extractor import (
    DIM_CCT_CLAUSE, GOLD_MANIFEST_PATH, run, clause_sk, normalize_clause_number,
)

DIM_CCT_CLAUSE_COLUMNS = [
    "clause_sk", "union_state", "source_pdf",
    "clause_number", "clause_number_int",
    "clause_title", "category", "keywords_matched",
    "confidence", "page", "weekly_hours_extracted", "extracted_at",
]


def _docs_available() -> bool:
    from pipelines.nlp.cct_extractor import CCT_ROOT
    return any(CCT_ROOT.rglob("*.pdf")) if CCT_ROOT.exists() else False


@pytest.fixture(scope="module")
def extraction_doc():
    if not _docs_available():
        pytest.skip("Docs/CCTs PDFs not available in this worktree")
    return run()


# ---------------------------------------------------------------------------
# Extraction -> gold promotion
# ---------------------------------------------------------------------------
def test_extraction_promotes_clauses_to_gold_parquet(extraction_doc):
    assert extraction_doc["total_clauses"] >= 30
    assert extraction_doc["readable_source_count"] >= 1
    assert DIM_CCT_CLAUSE.exists()
    gold = pd.read_parquet(DIM_CCT_CLAUSE)
    for column in DIM_CCT_CLAUSE_COLUMNS:
        assert column in gold.columns, f"gold dim missing contract column: {column}"
    assert len(gold) == extraction_doc["total_clauses"]
    assert gold["clause_sk"].is_unique
    assert set(gold["union_state"].unique()) <= {"MG", "RJ", "RN"}
    assert gold["clause_number_int"].notna().any()
    assert gold["clause_number_int"].dtype.kind in ("i", "u", "I", "U", "f")
    assert (gold["confidence"].between(0.0, 1.0)).all()


def test_gold_parquet_rerun_is_deterministic(extraction_doc):
    first = pd.read_parquet(DIM_CCT_CLAUSE)
    run()
    second = pd.read_parquet(DIM_CCT_CLAUSE)
    pd.testing.assert_frame_equal(
        first.drop(columns=["extracted_at"]),
        second.drop(columns=["extracted_at"]),
    )


def test_clause_sk_and_number_normalization():
    assert clause_sk("MG", "Docs/CCTs/MG/x.pdf", "cláusula 12ª", 3) == clause_sk(
        "MG", "Docs/CCTs/MG/x.pdf", "cláusula 12ª", 3
    )
    assert clause_sk("MG", "Docs/CCTs/MG/x.pdf", "cláusula 12ª", 3) != clause_sk(
        "RJ", "Docs/CCTs/MG/x.pdf", "cláusula 12ª", 3
    )
    assert normalize_clause_number({"clause_order": 12, "clause_number": "cláusula 12ª"}) == 12
    assert normalize_clause_number({"clause_order": None, "clause_number": "cláusula 7ª"}) == 7
    assert normalize_clause_number({"clause_order": None, "clause_number": "cláusula Única"}) is None


def test_gold_manifest_documents_on_demand_target(extraction_doc):
    assert GOLD_MANIFEST_PATH.exists()
    with open(GOLD_MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert "dim_cct_clause" in manifest.get("targets", [])
    on_demand = (manifest.get("on_demand") or {}).get("dim_cct_clause") or {}
    assert on_demand.get("in_run_pipeline") is False
    assert on_demand.get("produced_by") == "pipelines/nlp/cct_extractor.py"


# ---------------------------------------------------------------------------
# app.data consumer layer
# ---------------------------------------------------------------------------
def test_cct_clauses_returns_gold_data():
    from app.data import cct_clauses
    if not DIM_CCT_CLAUSE.exists():
        pytest.skip("dim_cct_clause.parquet not generated in this worktree")
    df = cct_clauses()
    assert not df.empty
    for column in DIM_CCT_CLAUSE_COLUMNS:
        assert column in df.columns
    assert df["clause_sk"].is_unique


def test_uc_mapping_links_categories_to_engine_ucs():
    from app.data import clausulas_relevantes_por_uc
    clauses = pd.DataFrame([
        {"union_state": "MG", "category": "jornada"} for _ in range(2)
    ] + [
        {"union_state": "RJ", "category": "periculosidade"},
        {"union_state": "MG", "category": "nao_classificada"},
    ])
    mapping = clausulas_relevantes_por_uc(clauses)
    assert not mapping.empty
    rows = {(row["union_state"], row["category"]): row for _, row in mapping.iterrows()}
    assert ("MG", "jornada") in rows
    assert rows[("MG", "jornada")]["clause_count"] == 2
    assert "UC25" in rows[("MG", "jornada")]["ucs"]
    assert rows[("RJ", "periculosidade")]["ucs"] == "UC13"
    assert rows[("RJ", "periculosidade")]["uc_count"] == 1
    assert ("MG", "nao_classificada") not in rows
    assert ("MG", "banco_de_horas") not in rows  # categories absent from input


def test_uc_mapping_empty_and_known_contract():
    from app.data import clausulas_relevantes_por_uc
    empty = clausulas_relevantes_por_uc(pd.DataFrame(columns=["union_state", "category"]))
    assert empty.empty
    assert list(empty.columns) == ["union_state", "category", "clause_count", "ucs", "uc_count"]
    fallback = clausulas_relevantes_por_uc(None)
    assert isinstance(fallback, pd.DataFrame)


def _component_text(node):
    if isinstance(node, str):
        return node
    if isinstance(node, (list, tuple)):
        return " ".join(_component_text(item) for item in node)
    children = getattr(node, "children", None)
    return _component_text(children) if children is not None else ""


def test_uc_mapping_handles_rn_absence(extraction_doc):
    from app.data import clausulas_relevantes_por_uc
    from app.pages.ia_nlp import _cct_uc_block, EXPECTED_CCT_STATES
    if DIM_CCT_CLAUSE.exists():
        clauses = pd.read_parquet(DIM_CCT_CLAUSE)
    else:
        clauses = pd.DataFrame(extraction_doc.get("clauses") or [])
    if clauses.empty:
        pytest.skip("no real clauses to test RN absence handling")

    mapping = clausulas_relevantes_por_uc(clauses)
    present = set(clauses["union_state"].astype(str).unique())

    rn_absent = "RN" not in present
    block = _cct_uc_block(clauses, mapping)
    rendered = _component_text(block)
    for state in EXPECTED_CCT_STATES:
        if state in present:
            continue
        assert state in rendered, f"missing absence note for {state}"
    if rn_absent:
        assert "RN" not in set(mapping["union_state"].astype(str).unique())
        assert "sem cláusulas extraídas" in rendered
