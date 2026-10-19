"""Tests for competence-partitioned validation runs.

Covers the three hard requirements of partitioned detection:
 - a --competence run preserves detection rows of every untouched competence
   (integrated against the real worktree data via subprocess),
 - the competence list helper derives from fact_monthly_employee,
 - detection_id resequencing after the merge is deterministic.

The stored detection parquet is rebuilt in full mode when missing so the
partitioned merge always has a previous state to preserve against.
"""
import os
import subprocess
import sys

import duckdb
import pandas as pd
import pytest

BASE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(ROOT, "pipelines"))

from competence_utils import (
    CONTRACT_COLS, list_competences, merge_detections, normalize_competence,
    resequence_detection_ids, resolve_requested_competences,
)

DET_PATH = os.path.join(ROOT, "data", "gold", "fact_detected_inconsistency.parquet")
MONTHLY_PATH = os.path.join(ROOT, "data", "gold", "fact_monthly_employee.parquet")
DATA_MISSING_REASON = "worktree data/ not generated yet"
TARGET = "2024-06"


def _run_engine(*extra_args, timeout=1800):
    engine = os.path.join("pipelines", "validation_engine.py")
    result = subprocess.run(
        [sys.executable, engine, *extra_args],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def det_full_state():
    """Ensure a stored detection set exists for the partitioned merge."""
    if not os.path.exists(MONTHLY_PATH):
        pytest.skip(DATA_MISSING_REASON)
    if not os.path.exists(DET_PATH):
        _run_engine()


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


def _read_det(con):
    return con.execute(f"SELECT * FROM read_parquet('{DET_PATH}')").fetchdf()


def _norm_counts(df):
    counts = df["competence"].map(normalize_competence).value_counts().sort_index()
    return {k: int(v) for k, v in counts.items()}


def test_partitioned_run_preserves_other_competences(con, det_full_state):
    before = _read_det(con)

    result = _run_engine("--competence", TARGET)
    assert f"partitioned ['{TARGET}']" in result.stdout

    after = _read_det(con)
    before_counts = _norm_counts(before)
    after_counts = _norm_counts(after)

    preserved_before = {k: v for k, v in before_counts.items() if k != TARGET}
    preserved_after = {k: v for k, v in after_counts.items() if k != TARGET}
    assert preserved_before == preserved_after, "untouched competences must be preserved"
    assert after_counts[TARGET] > 0, "target competence must be recomputed"

    # monthly fact untouched outside the target competence (same rows, same values)
    monthly_before = con.execute(f"SELECT * FROM read_parquet('{MONTHLY_PATH}')").fetchdf()
    monthly_before["competence"] = (monthly_before["year"].astype(str) + "-"
                                    + monthly_before["month"].astype(str).str.zfill(2))
    monthly_after = con.execute(f"SELECT * FROM read_parquet('{MONTHLY_PATH}')").fetchdf()
    monthly_after["competence"] = (monthly_after["year"].astype(str) + "-"
                                   + monthly_after["month"].astype(str).str.zfill(2))
    pd.testing.assert_frame_equal(
        monthly_before[monthly_before["competence"] != TARGET].reset_index(drop=True),
        monthly_after[monthly_after["competence"] != TARGET].reset_index(drop=True),
    )


def test_list_competences_derives_from_fact_monthly_employee(con, det_full_state):
    listed = list_competences(con, os.path.join(ROOT, "data", "gold"))
    rows = con.execute(f"SELECT DISTINCT year, month FROM read_parquet('{MONTHLY_PATH}')").fetchall()
    expected = sorted(f"{y}-{int(m):02d}" for y, m in rows)
    assert listed == expected
    assert listed == sorted(listed)
    assert all(len(c) == 7 and c[4] == "-" for c in listed)


def test_resolve_requested_competences_range_and_validation():
    available = ["2024-01", "2024-02", "2024-03", "2024-04"]
    got = resolve_requested_competences(["2024-02"], "2024-02", "2024-04", available)
    assert got == ["2024-02", "2024-03", "2024-04"]
    assert resolve_requested_competences(None, None, None, available) is None
    with pytest.raises(ValueError):
        resolve_requested_competences(["2025-01"], None, None, available)
    with pytest.raises(ValueError):
        resolve_requested_competences(None, "2024-01", None, available)


def _mk_df(seed):
    rows = []
    for i in range(9):
        rows.append(_mk_row(i))
    df = pd.DataFrame(rows)
    return pd.concat([df, df.sample(frac=1.0, random_state=seed)], ignore_index=True)


def _mk_row(i, comp=None, detail=None):
    return {
        "employee_id": 1 + (i % 2),
        "competence": comp or ["2024-06", "2024-07", "N/A"][i % 3],
        "use_case": [1, 5, 28][i % 3],
        "rule_name": ["r-a", "r-b", "r-a"][i % 3],
        "category": "jornada",
        "severity": "medio",
        "detected_value": f"v{i % 2}",
        "expected_value": f"e{i % 2}",
        "financial_impact": float(i % 4),
        "detail": detail or f"d{i}",
        "rule_origin": "rule_engine",
        "evidence_source": "computed_from_cross_source",
        "detected_at": "2026-01-01T00:00:00+00:00",
    }


def test_detection_id_resequencing_deterministic():
    df1 = _mk_df(seed=1).sample(frac=1.0, random_state=7).reset_index(drop=True)
    df2 = _mk_df(seed=2).sample(frac=1.0, random_state=11).reset_index(drop=True)

    out1 = resequence_detection_ids(df1)
    out2 = resequence_detection_ids(df2)

    assert list(out1["detection_id"]) == list(range(1, len(out1) + 1))

    key_cols = [c for c in CONTRACT_COLS if c != "detection_id"]
    sorted1 = out1.sort_values(["detection_id"]).reset_index(drop=True)[key_cols]
    sorted2 = out2.sort_values(["detection_id"]).reset_index(drop=True)[key_cols]
    pd.testing.assert_frame_equal(sorted1, sorted2)


def test_merge_detections_replaces_target_and_preserves_rest():
    old = pd.DataFrame([_mk_row(i) for i in range(6)])
    fresh = _mk_row(0, comp=TARGET, detail="fresh")
    merged = merge_detections(old, pd.DataFrame([fresh]), [TARGET])

    kept = merged[merged["competence"] != TARGET]
    assert len(kept) == len(old[old["competence"] != TARGET])
    n_old = {d for d in old[old["competence"] != TARGET]["detail"]}
    assert {d for d in merged["detail"]} == n_old | {"fresh"}
    assert list(merged["detection_id"]) == list(range(1, len(merged) + 1))
