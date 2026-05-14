"""Data contracts and regression guards for pipeline outputs."""
import duckdb


def test_gold_contract_tables_exist_and_non_empty():
    con = duckdb.connect()
    required = [
        "data/gold/dim_cct_rule_version.parquet",
        "data/gold/fact_monthly_employee.parquet",
        "data/gold/fact_detected_inconsistency.parquet",
        "data/gold/fact_passivo_trabalhista.parquet",
    ]
    for path in required:
        cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
        assert cnt > 0, f"{path} should not be empty"


def test_cct_rules_have_temporal_coverage():
    con = duckdb.connect()
    df = con.execute(
        """
        SELECT state, MIN(valid_from) AS min_v, MAX(valid_to) AS max_v, COUNT(*) AS versions
        FROM read_parquet('data/gold/dim_cct_rule_version.parquet')
        GROUP BY state
        """
    ).fetchdf()
    assert set(df["state"]) == {"MG", "RJ", "RN"}
    assert (df["versions"] >= 3).all()


def test_cct_rules_do_not_overlap_within_state():
    con = duckdb.connect()
    overlap = con.execute(
        """
        WITH r AS (
            SELECT state, valid_from, valid_to,
                   LEAD(valid_from) OVER (PARTITION BY state ORDER BY valid_from) AS next_valid_from
            FROM read_parquet('data/gold/dim_cct_rule_version.parquet')
        )
        SELECT COUNT(*)
        FROM r
        WHERE next_valid_from IS NOT NULL
          AND valid_to >= next_valid_from
        """
    ).fetchone()[0]
    assert overlap == 0, f"Found {overlap} overlapping CCT validity windows"


def test_passivo_is_derived_from_detected_inconsistencies():
    con = duckdb.connect()
    counts = con.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM read_parquet('data/gold/fact_detected_inconsistency.parquet')) AS det,
          (SELECT COUNT(*) FROM read_parquet('data/gold/fact_passivo_trabalhista.parquet')) AS pas
        """
    ).fetchone()
    assert counts[1] <= counts[0]


def test_monthly_contract_columns_are_populated():
    con = duckdb.connect()
    row = con.execute(
        """
        SELECT
          SUM(total_inconsistencies) AS total_inc,
          SUM(payment_inconsistencies) AS pay_inc,
          SUM(he_inconsistencies) AS he_inc
        FROM read_parquet('data/gold/fact_monthly_employee.parquet')
        """
    ).fetchone()
    assert row[0] is not None
    assert row[1] is not None
    assert row[2] is not None


def test_silver_tables_have_source_hash_lineage_column():
    con = duckdb.connect()
    cols = con.execute(
        "DESCRIBE SELECT * FROM read_parquet('data/silver/dim_employee.parquet')"
    ).fetchdf()["column_name"].tolist()
    assert "source_hash" in cols
