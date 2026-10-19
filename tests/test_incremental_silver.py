"""
Tests for the incremental Silver load of fact_time_record.

Unit scope: the pure planning function plan_delta (pipelines/incremental.py).
Integration scope: running ``python pipelines/bronze_to_silver.py
--incremental`` twice must be idempotent (second run: 0 new rows, identical
row count) and expose the incremental metrics in silver_manifest.json.
"""
import json
import os
import subprocess
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipelines.incremental import plan_delta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# plan_delta — pure unit tests
# ---------------------------------------------------------------------------
def test_plan_delta_cold_start_loads_everything():
    new_dates = ["2024-01-01", "2024-01-03", "2024-01-02"]
    assert plan_delta(new_dates, None) == ["2024-01-01", "2024-01-02", "2024-01-03"]


def test_plan_delta_all_new_above_watermark():
    assert plan_delta(["2025-02-01", "2025-01-31"], "2025-01-30") == ["2025-01-31", "2025-02-01"]


def test_plan_delta_nothing_new():
    assert plan_delta(["2025-01-01", "2025-01-02"], "2025-01-02") == []


def test_plan_delta_off_by_one_watermark_day_is_excluded():
    # The watermark day itself is already loaded in a previous run:
    # strictly-greater comparison avoids re-ingesting it.
    watermark = "2025-06-10"
    assert plan_delta(["2025-06-10"], watermark) == []
    assert plan_delta(["2025-06-09"], watermark) == []
    assert plan_delta(["2025-06-11"], watermark) == ["2025-06-11"]


def test_plan_delta_partial_suffix_only():
    result = plan_delta(["2025-03-01", "2025-04-01", "2025-05-01"], "2025-04-01")
    assert result == ["2025-05-01"]


def test_plan_delta_deduplicates_and_sorts():
    result = plan_delta(["2025-02-02", "2025-02-01", "2025-02-02", "2025-02-03"], "2025-01-01")
    assert result == ["2025-02-01", "2025-02-02", "2025-02-03"]


def test_plan_delta_empty_candidates():
    assert plan_delta([], "2025-01-01") == []
    assert plan_delta([], None) == []
    assert plan_delta(None, "2025-01-01") == []


def test_plan_delta_accepts_date_objects():
    result = plan_delta([date(2025, 1, 2), date(2025, 1, 1)], "2025-01-01")
    assert result == ["2025-01-02"]


def test_plan_delta_returns_sorted_iso_strings():
    result = plan_delta(["2025-02-10", "2025-02-09", "2025-02-11"], "2025-02-09")
    assert result == ["2025-02-10", "2025-02-11"]


# ---------------------------------------------------------------------------
# Integration: two consecutive --incremental runs are idempotent
# ---------------------------------------------------------------------------
def _silver_path(name: str) -> str:
    return os.path.join(REPO_ROOT, "data", "silver", name)


def _run_incremental_pipeline() -> dict:
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "pipelines", "bronze_to_silver.py"), "--incremental"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"pipeline failed:\n{proc.stdout}\n{proc.stderr}"
    with open(os.path.join(REPO_ROOT, "data", "silver", "silver_manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _fact_time_record_rows() -> int:
    import pyarrow.parquet as pq
    return pq.ParquetFile(_silver_path("fact_time_record.parquet")).metadata.num_rows


@pytest.mark.skipif(
    not os.path.exists(os.path.join(REPO_ROOT, "data", "bronze", "time_clock", "time_records.csv")),
    reason="bronze time_records.csv not generated in this worktree",
)
def test_incremental_twice_idempotent():
    first = _run_incremental_pipeline()
    first_metrics = first["fact_time_record_incremental"]
    assert first_metrics["mode"] == "incremental"
    assert first_metrics["watermark"] is not None

    rows_after_first = _fact_time_record_rows()

    second = _run_incremental_pipeline()
    second_metrics = second["fact_time_record_incremental"]
    assert second_metrics["mode"] == "incremental"
    assert second_metrics["rows_new"] == 0
    assert second_metrics["watermark"] == first_metrics["watermark"]
    rows_after_second = _fact_time_record_rows()
    assert rows_after_second == rows_after_first
