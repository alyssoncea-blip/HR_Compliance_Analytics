"""Tests for the benchmark harness (pipelines/benchmark_engine.py).

Unit tests cover the stdout parser against synthetic lines reproducing the
engine's current print format exactly. The integration test runs the harness
end-to-end via subprocess (skipped when worktree data/ is missing).
"""
import json
import os
import subprocess
import sys

import pytest

BASE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(ROOT, "pipelines"))

from benchmark_engine import parse_engine_output

DATA_MISSING_REASON = "worktree data/ not copied yet"
TARGET = "2024-06"

# Synthetic lines copied from the engine's current print format
FULL_STDOUT_SAMPLE = "\n".join([
    "=" * 60,
    "VALIDATION ENGINE — 32 RULES  (mode: partitioned ['2024-06'])",
    "=" * 60,
    "[UC1] HE Progressiva...",
    "  -> 332 detected (0.5s)",
    "[UC2] HE Domingo...",
    "  -> 0 detected (0.1s)",
    "[UC3] Adicional Noturno...",
    "  -> skipped (partitioned mode: N/A-competence rows preserved from prior runs)",
    "[UC4] Banco de Horas...",
    "  -> 184686 detected (2.3s)",
    "",
    "=" * 60,
    "Consolidating detections...",
    "  Total detections: 629300",
    "  Total financial impact: R$ 119,216,499.73",
    "  Total time: 10.9s",
    "",
    "=" * 60,
    "SUMMARY BY USE CASE",
    "=" * 60,
    "  UC01 HE progressiva incorreta            alto       7808 ocorr.  R$600,295.91",
    "  UC02 HE domingo incorreta                alto       9212 ocorr.  R$2,060,893.88",
    "  UC04 Banco de horas excedido             medio    184686 ocorr.  R$      0.00",
    "  UC25 Limite semanal excedido             critico  298771 ocorr.  R$36,140,140.12",
    "",
    "  " + "TOTAL" + (" " * 50) + "629300 ocorr.  R$119,216,499.73",
])


def test_parser_extracts_summary_rows():
    summary_total, rows, per_uc_runtime, by_uc = parse_engine_output(FULL_STDOUT_SAMPLE)
    assert summary_total == 629300
    assert [r["uc"] for r in rows] == [1, 2, 4, 25]
    assert rows[0]["rule_name"] == "HE progressiva incorreta"
    assert rows[0]["detections"] == 7808
    assert rows[3]["detections"] == 298771
    assert by_uc["UC25"] == 298771


def test_parser_extracts_per_uc_runtime_when_available():
    summary_total, rows, per_uc_runtime, by_uc = parse_engine_output(FULL_STDOUT_SAMPLE)
    assert per_uc_runtime == {"UC01": 0.5, "UC02": 0.1, "UC04": 2.3}
    runtime_by_uc = {r["uc"]: r["runtime_s"] for r in rows}
    assert runtime_by_uc[1] == 0.5
    assert runtime_by_uc[4] == 2.3
    # UC3 skipped -> no runtime, absent from parsed rows entirely (no summary row)


def test_parser_handles_skipped_blocks_and_totals():
    summary_total, rows, per_uc_runtime, by_uc = parse_engine_output(FULL_STDOUT_SAMPLE)
    # skipped block did not fabricate a runtime
    assert "UC03" not in per_uc_runtime
    # totals parsed from stdout
    m_rows = {r["rule_name"]: r for r in rows}
    assert m_rows["HE progressiva incorreta"]["detections"] == 7808


def _benchmark_out():
    return os.path.join(
        ROOT, "data", "gold", "observability", "engine_benchmark.json"
    )


@pytest.fixture(scope="module")
def data_available():
    if not os.path.exists(os.path.join(ROOT, "data", "gold", "fact_monthly_employee.parquet")):
        pytest.skip(DATA_MISSING_REASON)


def _run_harness(out_path, *extra):
    cmd = [sys.executable, os.path.join("pipelines", "benchmark_engine.py"),
           "--scenario", "partitioned", "--out", out_path, *extra]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=1800)
    assert result.returncode == 0, result.stdout + result.stderr
    with open(out_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_harness_partitioned_run_valid_history(data_available):
    out_path = os.environ["TEMP"] + os.sep + "engine_benchmark_it1.json"
    if os.path.exists(out_path):
        os.remove(out_path)
    history = _run_harness(out_path, "--competence", TARGET)
    assert len(history) == 1
    rec = history[-1]
    # required keys
    for key in ("run_id", "scenario", "competences", "runtime_s", "detections",
                "per_uc", "per_uc_runtime_s", "manifest_fields", "host_info",
                "engine_commit"):
        assert key in rec, key
    # scenario + competence fidelity
    assert rec["scenario"] == "partitioned"
    assert rec["competences"] == [TARGET]
    assert rec["manifest_fields"]["mode"] == "partitioned"
    # runtime numeric and positive
    assert isinstance(rec["runtime_s"], float) and rec["runtime_s"] > 0
    assert isinstance(rec["detections"]["total_stdout"], int)
    # per-UC entries exist with parsed runtime
    assert len(rec["per_uc"]) > 0
    assert isinstance(rec["per_uc_runtime_s"], dict) and len(rec["per_uc_runtime_s"]) > 0
    assert all("UC" in k for k in rec["per_uc_runtime_s"])
    committed = rec["engine_commit"]
    assert isinstance(committed, str) and len(committed) >= 40


def test_harness_history_appends(data_available):
    out_path = os.environ["TEMP"] + os.sep + "engine_benchmark_it2.json"
    if os.path.exists(out_path):
        os.remove(out_path)
    first = _run_harness(out_path, "--competence", TARGET)
    second = _run_harness(out_path, "--competence", TARGET)
    assert len(first) == 1
    assert len(second) == len(first) + 1
    assert second[-1]["run_id"] != first[-1]["run_id"]
    assert second[-1]["scenario"] == first[-1]["scenario"] == "partitioned"
