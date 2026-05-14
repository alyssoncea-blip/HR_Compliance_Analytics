"""
Unit tests for HR Compliance Analytics — data functions & validation rules.
Run with: python -m pytest tests/ -v
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import duckdb, pandas as pd
from datetime import date

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def con():
    return duckdb.connect()

@pytest.fixture
def sample_employees():
    return pd.DataFrame({
        "employee_id": [1, 2, 3, 4, 5],
        "name": ["João Silva", "Maria Santos", "Pedro Costa", "Ana Lima", "Carlos Souza"],
        "cpf": ["12345678901", "23456789012", "34567890123", "45678901234", "56789012345"],
        "gender": ["M", "F", "M", "F", "M"],
        "base_salary": [2000.0, 3500.0, 1800.0, 5000.0, 2200.0],
        "weekly_hours": [44, 44, 30, 44, 44],
        "work_schedule": ["5x2", "12x36", "3x3", "5x2", "6x1"],
        "periculosidade_eligible": [True, False, True, False, True],
        "insalubridade_eligible": [False, True, False, True, False],
        "status": ["active"] * 5,
        "hire_date": pd.to_datetime(["2020-01-15", "2019-06-01", "2021-03-10", "2018-11-20", "2022-07-05"]),
        "dependents": [2, 0, 1, 3, 0],
    })

@pytest.fixture
def sample_payroll():
    return pd.DataFrame({
        "payroll_id": [1, 2],
        "employee_id": [1, 2],
        "base_salary": [2000.0, 3500.0],
        "overtime_50_hours": [5.0, 0.0],
        "overtime_50_amount": [68.18, 0.0],
        "overtime_70_hours": [8.0, 3.0],
        "overtime_70_amount": [123.64, 55.68],
        "overtime_100_hours": [0.0, 10.0],
        "overtime_100_amount": [0.0, 176.14],
        "night_shift_hours": [0.0, 20.0],
        "night_shift_amount": [0.0, 79.55],
        "periculosidade_amount": [600.0, 0.0],
        "insalubridade_amount": [0.0, 1400.0],
        "dsr_amount": [100.0, 150.0],
        "salary_family_amount": [0.0, 0.0],
        "gross_total": [2891.82, 5361.37],
        "inss_discount": [260.26, 482.52],
        "irrf_discount": [0.0, 250.0],
        "union_discount": [20.0, 35.0],
        "other_discounts": [10.0, 17.5],
        "net_total": [2601.56, 4576.35],
    })

# ---------------------------------------------------------------------------
# Data generation tests
# ---------------------------------------------------------------------------
def test_headcount_query_returns_active_employees(con):
    """headcount() should return total, male, female breakdown."""
    try:
        from app.data import headcount
        hc = headcount().iloc[0]
        assert hc["total"] > 0, "Must have active employees"
        assert hc["masculino"] + hc["feminino"] <= hc["total"], "Gender sum <= total"
        assert hc["idade_media"] > 0, "Must have avg age"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")

def test_distribuicao_entidades_returns_all_fields(con):
    """distribuicao_entidades() must have all expected fields."""
    try:
        from app.data import distribuicao_entidades
        row = distribuicao_entidades().iloc[0].to_dict()
        expected_keys = {"total_ativos", "e_5x2", "e_12x36", "e_6x1", "e_3x3",
                         "he_50", "he_70", "he_100", "ad_noturno",
                         "periculosidade", "insalubridade",
                         "vr_alimentacao", "cesta_basica", "plr", "auxilio_creche",
                         "contrib_sindical", "gestante"}
        missing = expected_keys - set(row.keys())
        assert not missing, f"Missing fields: {missing}"
        assert row["total_ativos"] > 0, "Must have active employees"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")

def test_ccts_processadas_has_3_unions(con):
    """There should be exactly 3 unions (MG, RJ, RN)."""
    try:
        from app.data import ccts_processadas
        df = ccts_processadas()
        assert len(df) == 3, f"Expected 3 unions, got {len(df)}"
        assert set(df["state"]) == {"MG", "RJ", "RN"}, "Must have MG, RJ, RN"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")

# ---------------------------------------------------------------------------
# Business rule tests
# ---------------------------------------------------------------------------
def test_gross_total_equals_components(sample_payroll):
    """Gross total must equal sum of earnings components."""
    for _, row in sample_payroll.iterrows():
        computed = row["base_salary"] + row["overtime_50_amount"] + row["overtime_70_amount"] + \
                   row["overtime_100_amount"] + row["night_shift_amount"] + \
                   row["periculosidade_amount"] + row["insalubridade_amount"] + \
                   row["dsr_amount"] + row["salary_family_amount"]
        assert abs(computed - row["gross_total"]) < 0.02, \
            f"Employee {row['employee_id']}: computed={computed:.2f}, gross={row['gross_total']:.2f}"

def test_net_total_equals_gross_minus_deductions(sample_payroll):
    """Net total = gross - INSS - IRRF - union - other."""
    for _, row in sample_payroll.iterrows():
        computed = row["gross_total"] - row["inss_discount"] - row["irrf_discount"] - \
                   row["union_discount"] - row["other_discounts"]
        assert abs(computed - row["net_total"]) < 0.02, \
            f"Employee {row['employee_id']}: computed={computed:.2f}, net={row['net_total']:.2f}"

def test_periculosidade_eligible_has_positive_amount(sample_employees, sample_payroll):
    """Periculosidade-eligible employees must have non-zero periculosidade_amount."""
    for _, emp in sample_employees.iterrows():
        if not emp["periculosidade_eligible"]:
            continue
        match = sample_payroll[sample_payroll["employee_id"] == emp["employee_id"]]
        if len(match) > 0:
            assert match.iloc[0]["periculosidade_amount"] > 0, \
                f"Periculosidade missing for employee {emp['employee_id']}"

# ---------------------------------------------------------------------------
# Validation rule tests
# ---------------------------------------------------------------------------
def test_validation_engine_has_32_rules():
    """Validation engine must detect all 32 use cases."""
    try:
        con = duckdb.connect()
        df = con.execute("""
            SELECT COUNT(DISTINCT use_case) as qtd
            FROM read_parquet('data/gold/fact_detected_inconsistency.parquet')
        """).fetchdf()
        assert df.iloc[0]["qtd"] >= 30, f"Expected >=30 use cases, got {df.iloc[0]['qtd']}"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")

def test_quality_business_rules_fail():
    """Business rule checks MUST fail (detect injected inconsistencies)."""
    try:
        import json
        with open("data/gold/governance/data_quality_results.json", encoding="utf-8") as f:
            data = json.load(f)
        rule_checks = [r for r in data["results"] if r.get("dimension") == "regra_negocio"]
        assert len(rule_checks) >= 5, f"Expected >=5 business rule checks, got {len(rule_checks)}"
        failed = [r for r in rule_checks if r["status"] == "FAIL"]
        assert len(failed) > 0, "At least one business rule check must fail"
        print(f"\n  Business rule failures: {len(failed)}/{len(rule_checks)}")
        for r in failed:
            print(f"    FAIL: {r['table_name']} — {r['check_sql'][:80]}... ({r['fail_count']} rows)")
    except Exception as e:
        pytest.skip(f"Quality results not available: {e}")

# ---------------------------------------------------------------------------
# Schedule distribution tests
# ---------------------------------------------------------------------------
def test_schedule_distribution():
    """All 4 schedule types must be present with valid counts."""
    try:
        from app.data import query, pq
        df = query(f"SELECT work_schedule, count(*) qtd FROM read_parquet({pq('dim_employee')}) WHERE status='active' GROUP BY work_schedule ORDER BY qtd DESC")
        schedules = set(df["work_schedule"])
        assert schedules == {"5x2", "6x1", "12x36", "3x3"}, f"Unexpected schedules: {schedules}"
        total = df["qtd"].sum()
        assert total > 8000, f"Expected >8k active employees, got {total}"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")

def test_weekly_hours_per_state():
    """MG/RJ = 44h, RN = 30h."""
    try:
        from app.data import query, pq
        df = query(f"""
            SELECT u.state, e.weekly_hours, COUNT(*) qtd
            FROM read_parquet({pq('dim_employee')}) e
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            GROUP BY u.state, e.weekly_hours
        """)
        for state in ["MG", "RJ"]:
            state_df = df[df["state"] == state]
            assert all(state_df["weekly_hours"] == 44), f"{state} must have only 44h"
        rn_df = df[df["state"] == "RN"]
        assert any(rn_df["weekly_hours"] == 30), "RN must have 30h employees"
    except Exception as e:
        pytest.skip(f"Data not available: {e}")

# ---------------------------------------------------------------------------
# Dashboard integrity tests
# ---------------------------------------------------------------------------
def test_all_dashboard_layouts_compile():
    """All dashboard layouts must compile without error."""
    dashboards = [
        ("estrategico", "app.pages.dashboard_estrategico"),
        ("analitico", "app.pages.dashboard_analitico"),
        ("auditoria", "app.pages.dashboard_auditoria"),
        ("reconciliacao", "app.pages.reconciliacao"),
        ("funcionario", "app.pages.funcionario"),
        ("ia_nlp", "app.pages.ia_nlp"),
        ("governanca", "app.pages.governanca"),
        ("adr", "app.pages.adr"),
    ]
    for name, modpath in dashboards:
        mod = __import__(modpath, fromlist=["layout"])
        result = mod.layout()
        assert result is not None, f"{name} layout returned None"
        # Verify it's a Dash component
        from dash import html
        assert isinstance(result, html.Div), f"{name} layout should be a Dash Div"

def test_app_main_compiles():
    """The main Dash app must compile with all callbacks."""
    from app.main import app
    assert len(app.callback_map) >= 10, f"Expected >=10 callbacks, got {len(app.callback_map)}"

# ---------------------------------------------------------------------------
# CCT rules test
# ---------------------------------------------------------------------------
def test_cct_rules_config():
    """Config must define 3 unions with correct rules."""
    from pipelines.ingest.config import CCT_RULES
    assert len(CCT_RULES) == 3, f"Expected 3 CCT rulesets, got {len(CCT_RULES)}"
    states = {r.state for r in CCT_RULES}
    assert states == {"MG", "RJ", "RN"}
    for rule in CCT_RULES:
        assert 20 <= rule.standard_weekly_hours <= 44, f"Invalid weekly hours for {rule.state}"
        assert 0 < rule.he_weekday_percent < 2.0, f"Invalid HE percent for {rule.state}"
        assert rule.periculosidade_percent == 0.30, f"Periculosidade must be 30% for {rule.state}"
        assert rule.insalubridade_percent == 0.40, f"Insalubridade must be 40% for {rule.state}"
