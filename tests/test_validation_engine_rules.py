"""Unit tests for validation rule logic on controlled fixtures.

Rules are exercised against small in-memory DuckDB tables (no data/ access),
matching the detection contract of the validation engine.
"""
import duckdb
import pytest

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipelines"))
import validation_rules as rules


@pytest.fixture
def con():
    return duckdb.connect(":memory:")


def _make_monthly_ctx(con, rows):
    con.execute("""
        CREATE OR REPLACE TEMP VIEW fixture_monthly_ctx AS
        SELECT * FROM (VALUES
            {cols}
            {rows}
        ) AS fixture (employee_id, competence, overtime_70_hours, overtime_70_amount,
                   hourly_rate, he_first_hour_percent, he_additional_hours_percent,
                   he_progressive, missing_records)
    """.format(
        cols="",  # values list includes columns inline
        rows=",\n".join(
            f"({r['employee_id']}, '{r['competence']}', {r['overtime_70_hours']}, {r['overtime_70_amount']}, "
            f"{r['hourly_rate']}, {r['he_first_hour_percent']}, {r['he_additional_hours_percent']}, "
            f"{r['he_progressive']}, {r['missing_records']})"
            for r in rows
        ),
    ))


def _time(v):
    return "NULL" if v is None else f"CAST('{v}' AS TIME)"


def _make_time_records(con, rows):
    con.execute("""
        CREATE OR REPLACE TEMP VIEW fixture_time_record AS
        SELECT * FROM (VALUES
            {}
        ) AS fixture (record_id, employee_id, date_sk, total_hours,
                   entry_1, exit_1, entry_2, exit_2)
    """.format(
        ",\n".join(
            f"({r['record_id']}, {r['employee_id']}, {r['date_sk']}, {r['total_hours']}, "
            f"{_time(r['entry_1'])}, {_time(r['exit_1'])}, "
            f"{_time(r['entry_2'])}, {_time(r['exit_2'])})"
            for r in rows
        )
    ))


# ---------------------------------------------------------------------------
# UC1 — HE progressiva
# ---------------------------------------------------------------------------
UC1_ROWS = [
    # Detected: 10h at the additional tier paid at first-hour rate (50%)
    dict(employee_id=1, competence="2024-06", overtime_70_hours=10.0, overtime_70_amount=750.0,
         hourly_rate=50.0, he_first_hour_percent=0.5, he_additional_hours_percent=0.7,
         he_progressive=True, missing_records=0),
    # Correct payment: no detection expected
    dict(employee_id=2, competence="2024-06", overtime_70_hours=10.0, overtime_70_amount=850.0,
         hourly_rate=50.0, he_first_hour_percent=0.5, he_additional_hours_percent=0.7,
         he_progressive=True, missing_records=0),
    # Overtime exists but CCT is not progressive: no detection expected
    dict(employee_id=3, competence="2024-06", overtime_70_hours=10.0, overtime_70_amount=750.0,
         hourly_rate=50.0, he_first_hour_percent=0.5, he_additional_hours_percent=0.7,
         he_progressive=False, missing_records=0),
]


def test_uc1_detects_wrong_progressive_overtime(con):
    _make_monthly_ctx(con, UC1_ROWS)
    res = con.execute(rules.uc1_query("SELECT * FROM fixture_monthly_ctx")).fetchdf()
    assert len(res) == 1
    row = res.iloc[0]
    assert row["employee_id"] == 1
    assert row["severity"] == "alto"
    assert row["category"] == "remuneracao"
    # Impact = hours * rate * (additional% - first%)
    expected_impact = 10.0 * 50.0 * (0.7 - 0.5)
    assert abs(row["financial_impact"] - expected_impact) < 0.01
    assert "em vez de 70" in row["detail"]


def test_uc1_not_detected_when_paid_correctly_or_non_progressive(con):
    _make_monthly_ctx(con, UC1_ROWS)
    res = con.execute(rules.uc1_query("SELECT * FROM fixture_monthly_ctx")).fetchdf()
    detected_ids = set(res["employee_id"])
    assert 2 not in detected_ids, "correct payment must not be flagged"
    assert 3 not in detected_ids, "non-progressive CCT must not be flagged"


# ---------------------------------------------------------------------------
# UC8 — Funcionario sem registro de ponto
# ---------------------------------------------------------------------------
UC8_ROWS = [
    dict(employee_id=1, competence="2024-06", overtime_70_hours=0.0, overtime_70_amount=0.0,
         hourly_rate=50.0, he_first_hour_percent=0.5, he_additional_hours_percent=0.7,
         he_progressive=True, missing_records=5),
    dict(employee_id=2, competence="2024-06", overtime_70_hours=0.0, overtime_70_amount=0.0,
         hourly_rate=50.0, he_first_hour_percent=0.5, he_additional_hours_percent=0.7,
         he_progressive=True, missing_records=0),
]


def test_uc8_detects_missing_time_records(con):
    _make_monthly_ctx(con, UC8_ROWS)
    res = con.execute(rules.uc8_query("SELECT * FROM fixture_monthly_ctx")).fetchdf()
    assert len(res) == 1
    row = res.iloc[0]
    assert row["employee_id"] == 1
    assert row["severity"] == "critico"
    assert row["financial_impact"] == 0.0
    assert row["rule_name"] == "Funcionario sem registro de ponto"


def test_uc8_not_detected_with_complete_records(con):
    _make_monthly_ctx(con, UC8_ROWS)
    res = con.execute(rules.uc8_query("SELECT * FROM fixture_monthly_ctx")).fetchdf()
    assert 2 not in set(res["employee_id"]), "employee with full records must not be flagged"


# ---------------------------------------------------------------------------
# UC28 — Jornada sobreposta (real interval overlap)
# ---------------------------------------------------------------------------
TIME_ROWS = [
    # Overlapping pair: 07-13 x 11-17 -> 2h overlap
    dict(record_id=1, employee_id=1, date_sk=20240610, total_hours=6.0,
         entry_1="07:00:00", exit_1="13:00:00", entry_2=None, exit_2=None),
    dict(record_id=2, employee_id=1, date_sk=20240610, total_hours=6.0,
         entry_1="11:00:00", exit_1="17:00:00", entry_2=None, exit_2=None),
    # Same employee, touching boundary (13:00): NOT overlap
    dict(record_id=3, employee_id=3, date_sk=20240610, total_hours=6.0,
         entry_1="07:00:00", exit_1="13:00:00", entry_2=None, exit_2=None),
    dict(record_id=4, employee_id=3, date_sk=20240610, total_hours=6.0,
         entry_1="13:00:00", exit_1="19:00:00", entry_2=None, exit_2=None),
    # Disjoint pair: not overlap
    dict(record_id=5, employee_id=4, date_sk=20240610, total_hours=6.0,
         entry_1="07:00:00", exit_1="13:00:00", entry_2=None, exit_2=None),
    dict(record_id=6, employee_id=4, date_sk=20240610, total_hours=6.0,
         entry_1="14:00:00", exit_1="20:00:00", entry_2=None, exit_2=None),
    # Single record: no pair, no detection
    dict(record_id=7, employee_id=5, date_sk=20240610, total_hours=8.0,
         entry_1="08:00:00", exit_1="16:00:00", entry_2=None, exit_2=None),
    # Overlap only via second split (entry_2/exit_2)
    dict(record_id=8, employee_id=6, date_sk=20240610, total_hours=8.0,
         entry_1="07:00:00", exit_1="12:00:00", entry_2="13:00:00", exit_2="19:00:00"),
    dict(record_id=9, employee_id=6, date_sk=20240610, total_hours=4.0,
         entry_1="18:00:00", exit_1="22:00:00", entry_2=None, exit_2=None),
    # Zero-hour record must be ignored entirely
    dict(record_id=10, employee_id=7, date_sk=20240610, total_hours=0.0,
         entry_1="07:00:00", exit_1="13:00:00", entry_2=None, exit_2=None),
    dict(record_id=11, employee_id=7, date_sk=20240610, total_hours=0.0,
         entry_1="08:00:00", exit_1="12:00:00", entry_2=None, exit_2=None),
]


def test_uc28_detects_real_interval_overlap(con):
    _make_time_records(con, TIME_ROWS)
    res = con.execute(rules.uc28_query("SELECT * FROM fixture_time_record")).fetchdf()
    detected = res[res["employee_id"] == 1]
    assert len(detected) == 1
    row = detected.iloc[0]
    assert row["use_case"] == 28
    assert row["rule_name"] == "Jornada sobreposta"
    assert row["severity"] == "medio"
    assert "120 min" in row["detected_value"]


def test_uc28_boundary_touch_and_disjoint_not_flagged(con):
    _make_time_records(con, TIME_ROWS)
    res = con.execute(rules.uc28_query("SELECT * FROM fixture_time_record")).fetchdf()
    flagged = set(res["employee_id"])
    # Strict overlap: records touching at 13:00 are NOT flagged (emp 3)
    assert 3 not in flagged
    # Fully disjoint shifts are NOT flagged (emp 4)
    assert 4 not in flagged


def test_uc28_split_shifts_and_zero_hours(con):
    _make_time_records(con, TIME_ROWS)
    res = con.execute(rules.uc28_query("SELECT * FROM fixture_time_record")).fetchdf()
    flagged = set(res["employee_id"])
    # Emp 6: overlap via split marks (entry_2/exit_2) x second record (emp 6)
    assert 6 in flagged
    # Zero-hour records carry no valid span and cannot count as a pair (emp 7)
    assert 7 not in flagged
