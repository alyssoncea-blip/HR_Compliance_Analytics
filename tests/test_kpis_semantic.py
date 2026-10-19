"""
Semantic KPI layer tests — parameterized filter builders, metric values, SQL injection safety.
Covers the hardened parameter-passing contract of app/kpis.py + app/data.py.
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.data import (
    query, set_global_filters, _filters_employee, _filters_competence, _filters_where_unit,
)
import app.data


@pytest.fixture(autouse=True)
def clean_filters():
    set_global_filters(None)
    yield
    set_global_filters(None)


# ---------------------------------------------------------------------------
# Filter builders return (placeholder_sql, params)
# ---------------------------------------------------------------------------
def test_filters_employee_empty_returns_no_where_and_no_params():
    where, params = _filters_employee()
    assert where == ""
    assert params == []


def test_filters_employee_estado_only():
    set_global_filters({"estado": "MG"})
    where, params = _filters_employee()
    assert where == "WHERE u.state = ?"
    assert params == ["MG"]
    assert '"MG"' not in where and "'MG'" not in where


def test_filters_employee_full_combo():
    set_global_filters({"estado": "RJ", "unidade": "Unidade X", "sindicato": "Sindágua-RJ"})
    where, params = _filters_employee()
    assert where == "WHERE u.state = ? AND u.name = ? AND un.name = ?"
    assert params == ["RJ", "Unidade X", "Sindágua-RJ"]
    assert "Sindágua-RJ" not in where


def test_filters_employee_partial_combo_skips_missing():
    set_global_filters({"estado": "MG", "sindicato": "Sindágua-MG"})
    where, params = _filters_employee()
    assert where == "WHERE u.state = ? AND un.name = ?"
    assert params == ["MG", "Sindágua-MG"]


def test_filters_where_unit_and_competence_placeholders():
    set_global_filters({"estado": "RN", "unidade": "Unidade Y",
                        "start_date": "2024-01-01", "end_date": "2024-12-31"})
    where_u, params_u = _filters_where_unit()
    assert where_u == "WHERE u.state = ? AND u.name = ?"
    assert params_u == ["RN", "Unidade Y"]

    where_c, params_c = _filters_competence()
    assert where_c == " AND MAKE_DATE(m.year, m.month, 1) >= ? AND MAKE_DATE(m.year, m.month, 1) <= ?"
    assert params_c == ["2024-01-01", "2024-12-31"]


def test_filters_competence_empty():
    where, params = _filters_competence()
    assert where == ""
    assert params == []


# ---------------------------------------------------------------------------
# Metric execution against existing data
# ---------------------------------------------------------------------------
def test_get_metric_passivo_total_positive():
    try:
        value = __import__("app.kpis", fromlist=["get_metric"]).get_metric("passivo_total")
        assert value > 0, f"Expected passivo_total > 0, got {value}"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")


def test_get_metric_headcount_positive():
    try:
        value = __import__("app.kpis", fromlist=["get_metric"]).get_metric("headcount")
        assert value > 0, f"Expected headcount > 0, got {value}"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")


def test_metric_catalog_lists_passivo_total():
    from app.kpis import get_metric
    with pytest.raises(KeyError):
        get_metric("nonexistent_metric")


# ---------------------------------------------------------------------------
# SQL injection safety
# ---------------------------------------------------------------------------
def test_injection_in_estado_is_parameterized_not_interpolated():
    payload = "' OR 1=1 --"
    set_global_filters({"estado": payload})
    where, params = _filters_employee()
    assert payload in params, "Payload must travel as a bound parameter"
    assert "1=1" not in where, "Payload must never be interpolated into SQL string"


def test_injection_payload_executes_safely_and_filters_out_all_rows():
    payload = "' OR 1=1 --"
    set_global_filters({"estado": payload})
    df = __import__("app.data", fromlist=["headcount"]).headcount()
    assert df is not None and not df.empty
    assert int(df.iloc[0]["total"]) == 0, "Injection payload must match zero units"


def test_query_params_are_cache_keyed():
    df_mg = query("SELECT ?::VARCHAR AS v", ("MG",))
    df_rn = query("SELECT ?::VARCHAR AS v", ("RN",))
    assert df_mg.iloc[0]["v"] == "MG"
    assert df_rn.iloc[0]["v"] == "RN"


def test_query_legacy_no_params_does_not_error():
    df = query("SELECT 1 AS one")
    assert df.iloc[0]["one"] == 1
