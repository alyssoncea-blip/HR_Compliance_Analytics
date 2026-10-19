"""Unit tests for trend regression and freshness gates (pure logic, no DuckDB)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipelines.quality.gates import resolve_gates, DEFAULT_CONFIG
from pipelines.quality.trend import (
    evaluate_trend, evaluate_freshness, merge_overall_status, check_key,
    TREND_CONFIG_DEFAULTS, FRESHNESS_CONFIG_DEFAULTS,
)


def result(layer="silver", table="fact_payroll", dimension="unicidade",
           sql=None,
           fail_count=0, pass_pct=100.0, status="PASS", severity="high"):
    if sql is None:
        sql = f"SELECT employee_id FROM {table} GROUP BY employee_id HAVING count(*) > 1"
    return {
        "layer": layer, "table_name": table, "dimension": dimension,
        "check_sql": sql, "fail_count": fail_count, "total_count": 100,
        "pass_pct": pass_pct, "severity": severity, "status": status,
    }


def baseline_of(results):
    return {
        "pipeline": "governance", "run_at": "2026-01-01T00:00:00+00:00",
        "checks": {
            check_key(r["layer"], r["check_sql"]): {
                "fail_count": r["fail_count"], "pass_pct": r["pass_pct"],
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
            for r in results
        },
    }


# ---------------------------------------------------------------- trend core

def test_first_run_without_baseline_is_stable():
    out = evaluate_trend([result()], None, {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["first_run"] is True
    assert out["status"] == "PASS"
    assert out["regression_count"] == 0
    assert out["regressions"] == []


def test_regression_detected_when_fail_count_increases():
    prev = [result(fail_count=3, pass_pct=97.0, status="FAIL")]
    curr = [result(fail_count=7, pass_pct=93.0, status="FAIL")]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["regression_count"] == 1
    r = out["regressions"][0]
    assert r["change"] == "REGRESSION"
    assert r["baseline_fail_count"] == 3
    assert r["fail_count"] == 7
    assert r["delta"] == 4
    assert out["stable_count"] == 0


def test_improvement_when_fail_count_decreases():
    prev = [result(fail_count=9, pass_pct=91.0, status="FAIL")]
    curr = [result(fail_count=2, pass_pct=98.0, status="FAIL")]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["improvement_count"] == 1
    assert out["improvements"][0]["change"] == "IMPROVED"
    assert out["improvements"][0]["delta"] == -7
    assert out["regression_count"] == 0


def test_stable_when_fail_count_unchanged():
    prev = [result(fail_count=5, pass_pct=95.0, status="FAIL")]
    curr = [result(fail_count=5, pass_pct=95.0, status="FAIL")]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["stable_count"] == 1
    assert out["regression_count"] == 0
    assert out["improvement_count"] == 0
    assert out["status"] == "PASS"


def test_key_normalization_matches_despite_whitespace_and_case():
    prev = [result(sql="SELECT  a,  b\nFROM t WHERE x = 1")]
    curr = [result(sql="select a, b from t where x = 1")]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["stable_count"] == 1
    assert out["new_checks"] == []


def test_critical_regression_fails_trend_gate():
    prev = [result(dimension="integ_ref", severity="critical", fail_count=0)]
    curr = [result(dimension="integ_ref", severity="critical", fail_count=4, status="FAIL")]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["status"] == "FAIL"
    assert len(out["critical_regressions"]) == 1


def test_noncritical_regressions_below_warn_threshold_pass():
    cfg = {"trend": dict(TREND_CONFIG_DEFAULTS, warn_on_regressions=3)}
    prev = [result(table="t1", fail_count=1, status="FAIL"),
            result(table="t2", fail_count=1, status="FAIL")]
    curr = [result(table="t1", fail_count=2, status="FAIL"),
            result(table="t2", fail_count=3, status="FAIL")]
    out = evaluate_trend(curr, baseline_of(prev), cfg)
    assert out["regression_count"] == 2
    assert out["critical_regressions"] == []
    assert out["status"] == "PASS"


def test_regressions_at_warn_threshold_warn():
    cfg = {"trend": dict(TREND_CONFIG_DEFAULTS, warn_on_regressions=2)}
    prev = [result(table="t1", fail_count=1, status="FAIL"),
            result(table="t2", fail_count=1, status="FAIL")]
    curr = [result(table="t1", fail_count=2, status="FAIL"),
            result(table="t2", fail_count=3, status="FAIL")]
    out = evaluate_trend(curr, baseline_of(prev), cfg)
    assert out["status"] == "WARN"


def test_errored_check_is_always_a_regression():
    prev = [result(fail_count=0)]
    curr = [result(fail_count=-1, pass_pct=0.0, status="ERROR")]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["regression_count"] == 1
    assert out["regressions"][0]["delta"] is None


def test_new_and_retired_checks_are_reported_without_blocking():
    prev = [result(sql="SELECT old_check")]
    curr = [result(sql="SELECT brand_new_check", fail_count=0)]
    out = evaluate_trend(curr, baseline_of(prev), {"trend": dict(TREND_CONFIG_DEFAULTS)})
    assert out["new_checks"] == [check_key("silver", "SELECT brand_new_check")]
    assert out["retired_checks"] == [check_key("silver", "SELECT old_check")]
    assert out["status"] == "PASS"


# ---------------------------------------------------------------- freshness

def test_freshness_pass_when_data_is_fresh():
    out = evaluate_freshness({"bronze/employees": 1.5, "silver/dim_employee": 2.0},
                             {"freshness": dict(FRESHNESS_CONFIG_DEFAULTS)})
    assert out["status"] == "PASS"
    assert out["warn_tables"] == [] and out["fail_tables"] == []


def test_freshness_warn_and_fail_by_layer_thresholds():
    out = evaluate_freshness(
        {"bronze/employees": 60.0, "bronze/time_records": 200.0, "silver/fact_payroll": 80.0},
        {"freshness": dict(FRESHNESS_CONFIG_DEFAULTS)})
    assert out["status"] == "FAIL"
    assert out["warn_tables"] == ["bronze/employees", "silver/fact_payroll"]
    assert out["fail_tables"] == ["bronze/time_records"]


def test_freshness_unknown_layer_is_flagged_without_blocking():
    out = evaluate_freshness({"staging/raw": 500.0}, {"freshness": dict(FRESHNESS_CONFIG_DEFAULTS)})
    assert out["status"] == "PASS"
    assert out["unknown_tables"] == ["staging/raw"]


def test_freshness_boundary_is_strictly_greater_than():
    out = evaluate_freshness({"bronze/employees": 48.0, "bronze/payroll": 168.0},
                             {"freshness": dict(FRESHNESS_CONFIG_DEFAULTS)})
    by_path = {r["path"]: r["status"] for r in out["tables"]}
    assert by_path["bronze/employees"] == "PASS"
    assert by_path["bronze/payroll"] == "WARN"


# ------------------------------------------------------- overall integration

def test_merge_overall_status_trend_blocking_fail_blocks():
    trend = {"mode": "blocking", "status": "FAIL"}
    fresh = {"mode": "warn_only", "status": "FAIL"}
    assert merge_overall_status("PASS", trend, fresh) == "FAIL"


def test_merge_overall_status_freshness_warn_only_never_blocks():
    fresh = {"mode": "warn_only", "status": "FAIL"}
    assert merge_overall_status("PASS", None, fresh) == "WARN"
    assert merge_overall_status("PASS", {"mode": "informational", "status": "FAIL"}, fresh) == "WARN"


def test_merge_overall_status_never_downgrades():
    assert merge_overall_status("FAIL", {"mode": "blocking", "status": "PASS"}) == "FAIL"
    assert merge_overall_status("WARN", {"mode": "blocking", "status": "PASS"}) == "WARN"


def test_integration_resolve_gates_and_trend_with_default_config():
    checks = [
        result(table="dim_employee", dimension="completude", sql="SELECT 1 FROM dim_employee WHERE name IS NULL"),
        result(table="dim_employee", dimension="unicidade", sql="SELECT employee_id FROM dim_employee GROUP BY 1 HAVING count(*) > 1"),
        result(table="fact_payroll", dimension="integ_ref", severity="critical",
               sql="SELECT f.employee_id FROM fact_payroll f LEFT JOIN dim_employee e ON f.employee_id = e.employee_id WHERE e.employee_id IS NULL"),
        result(table="fact_time_record", dimension="consistencia", severity="critical",
               sql="SELECT 1 FROM fact_time_record WHERE total_hours < 0 OR total_hours > 24"),
        result(table="dim_employee", dimension="validade", sql="SELECT 1 FROM dim_employee WHERE LENGTH(cpf) != 11 AND cpf IS NOT NULL"),
        result(table="fact_payroll", dimension="regra_negocio", sql="SELECT 1 FROM fact_payroll WHERE night_shift_hours > 0 AND night_shift_amount = 0"),
    ]
    cfg = {"trend": dict(TREND_CONFIG_DEFAULTS), "freshness": dict(FRESHNESS_CONFIG_DEFAULTS)}

    # Previous run: consistency check clean. Current run: failures appeared.
    prev = [dict(c, fail_count=0, status="PASS") for c in checks]
    curr = list(checks)
    curr[3] = dict(checks[3], fail_count=120, pass_pct=99.0, status="FAIL")
    gates = resolve_gates(curr, DEFAULT_CONFIG)
    trend = evaluate_trend(curr, baseline_of(prev), cfg)
    overall = merge_overall_status(gates["overall_status"], trend, None)
    assert gates["overall_status"] == "PASS"
    assert trend["status"] == "FAIL"
    assert overall == "FAIL"

    # Stable data: trend stays PASS and overall keeps the gates verdict.
    trend_ok = evaluate_trend(curr, baseline_of(curr), cfg)
    assert trend_ok["status"] == "PASS"
    assert merge_overall_status(gates["overall_status"], trend_ok, None) == "PASS"
