"""Unit tests for quality gates resolution (pure logic, no DuckDB)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipelines.quality.gates import resolve_gates, DEFAULT_CONFIG


def result(dimension="completude", table="fact", layer="silver", pass_pct=100.0,
           status="PASS", fail_count=0, total_count=100):
    return {
        "layer": layer, "table_name": table, "dimension": dimension,
        "status": status, "pass_pct": pass_pct, "severity": "high",
        "fail_count": fail_count, "total_count": total_count,
    }


def test_blocking_gate_passes_at_threshold():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "unico", "mode": "blocking", "dimension": "unicidade", "threshold_pct": 100.0}]}
    out = resolve_gates([result(dimension="unicidade", pass_pct=100.0)], cfg)
    assert out["gates"][0]["status"] == "PASS"
    assert out["gates"][0]["pass_pct"] == 100.0
    assert out["overall_status"] == "PASS"
    assert out["blocking_gate_failures"] == []


def test_blocking_gate_fails_below_threshold():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "integ", "mode": "blocking", "dimension": "integ_ref", "threshold_pct": 99.5}]}
    out = resolve_gates([result(dimension="integ_ref", pass_pct=97.3, status="FAIL")], cfg)
    assert out["gates"][0]["status"] == "FAIL"
    assert out["overall_status"] == "FAIL"
    assert out["blocking_gate_failures"] == ["integ"]
    assert out["gates"][0]["violations"][0]["check"] == "silver.fact"


def test_informational_gate_does_not_block():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "rn", "mode": "informational", "dimension": "regra_negocio"}]}
    failing = result(dimension="regra_negocio", pass_pct=12.26, status="FAIL",
                     fail_count=210585, total_count=240000)
    out = resolve_gates([failing], cfg)
    assert out["gates"][0]["status"] == "INFORMATIONAL"
    assert out["overall_status"] == "PASS"
    assert out["blocking_gate_failures"] == []
    assert out["informational_gate_findings"] == ["rn"]
    assert len(out["gates"][0]["violations"]) == 1


def test_warn_margin_near_threshold():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "g", "mode": "blocking", "dimension": "completude", "threshold_pct": 99.0}]}
    out = resolve_gates([result(dimension="completude", pass_pct=98.7)], cfg)
    assert out["gates"][0]["status"] == "WARN"
    assert out["overall_status"] == "WARN"
    assert out["warned_gates"] == ["g"]
    assert out["blocking_gate_failures"] == []


def test_warn_margin_boundary_exactly_at_fail():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "g", "mode": "blocking", "dimension": "completude", "threshold_pct": 99.0}]}
    out = resolve_gates([result(dimension="completude", pass_pct=98.4)], cfg)
    assert out["gates"][0]["status"] == "FAIL"


def test_default_config_informational_regra_negocio():
    results = [
        result(dimension="completude", table="dim_employee", pass_pct=99.9),
        result(dimension="unicidade", table="dim_employee", pass_pct=100.0),
        result(dimension="integ_ref", table="fact_payroll", pass_pct=100.0),
        result(dimension="consistencia", table="fact_time_record", pass_pct=100.0),
        result(dimension="validade", table="dim_employee", pass_pct=100.0),
        result(dimension="regra_negocio", table="fact_payroll", pass_pct=12.26,
               status="FAIL", fail_count=210585, total_count=240000),
    ]
    out = resolve_gates(results, DEFAULT_CONFIG)
    assert out["overall_status"] == "PASS"
    assert out["blocking_gate_failures"] == []
    assert "regra_negocio_informational" in out["informational_gate_findings"]
    by_id = {g["id"]: g for g in out["gates"]}
    assert by_id["regra_negocio_informational"]["status"] == "INFORMATIONAL"


def test_default_config_all_pass_overall_pass():
    results = [
        result(dimension="completude", table="dim_employee"),
        result(dimension="unicidade", table="dim_employee"),
        result(dimension="integ_ref", table="fact_payroll"),
        result(dimension="consistencia", table="fact_time_record"),
        result(dimension="validade", table="dim_employee"),
        result(dimension="regra_negocio", table="fact_payroll"),
    ]
    out = resolve_gates(results, DEFAULT_CONFIG)
    assert out["overall_status"] == "PASS"
    by_id = {g["id"]: g for g in out["gates"]}
    assert by_id["regra_negocio_informational"]["status"] == "PASS"


def test_table_scoped_gate_only_matches_that_table():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "fk", "mode": "blocking", "table": "silver.fact_payroll",
         "dimension": "integ_ref", "threshold_pct": 99.9}]}
    results = [
        result(dimension="integ_ref", table="fact_payment", pass_pct=50.0),
        result(dimension="integ_ref", table="fact_payroll", pass_pct=100.0),
    ]
    out = resolve_gates(results, cfg)
    g = out["gates"][0]
    assert g["matched_checks"] == 1
    assert g["pass_pct"] == 100.0
    assert g["status"] == "PASS"
    assert out["overall_status"] == "PASS"


def test_gate_matches_full_layer_table_or_bare_name():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "bare", "mode": "blocking", "table": "fact_payroll",
         "dimension": "integ_ref", "threshold_pct": 100.0}]}
    out = resolve_gates([result(dimension="integ_ref", table="fact_payroll", pass_pct=100.0)], cfg)
    assert out["gates"][0]["matched_checks"] == 1


def test_zero_matched_checks_is_error_and_blocks():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "ghost", "mode": "blocking", "dimension": "dim_missingo", "threshold_pct": 100.0}]}
    out = resolve_gates([result(dimension="completude")], cfg)
    assert out["gates"][0]["status"] == "ERROR"
    assert out["gates"][0]["pass_pct"] is None
    assert out["overall_status"] == "FAIL"
    assert out["blocking_gate_failures"] == ["ghost"]


def test_blocking_gate_without_threshold_is_config_error():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "bad", "mode": "blocking", "dimension": "completude"}]}
    out = resolve_gates([result(dimension="completude", pass_pct=100.0)], cfg)
    assert out["gates"][0]["status"] == "ERROR"
    assert out["overall_status"] == "FAIL"


def test_errored_check_forces_gate_error():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "g", "mode": "blocking", "dimension": "completude", "threshold_pct": 99.0}]}
    errored = result(dimension="completude", pass_pct=100.0)
    errored["status"] = "ERROR"
    out = resolve_gates([errored], cfg)
    assert out["gates"][0]["status"] == "ERROR"
    assert out["overall_status"] == "FAIL"


def test_worst_check_drives_gate_pct():
    cfg = {"warn_margin_pct": 0.5, "gates": [
        {"id": "g", "mode": "blocking", "dimension": "integ_ref", "threshold_pct": 99.5}]}
    results = [
        result(dimension="integ_ref", table="fact_payroll", pass_pct=100.0),
        result(dimension="integ_ref", table="fact_payment", pass_pct=99.2),
        result(dimension="integ_ref", table="fact_time_record", pass_pct=99.9),
    ]
    out = resolve_gates(results, cfg)
    assert out["gates"][0]["pass_pct"] == 99.2
    assert out["gates"][0]["status"] == "WARN"
