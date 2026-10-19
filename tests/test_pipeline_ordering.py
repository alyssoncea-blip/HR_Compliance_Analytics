"""Ordering guard: passivo pre-aggregation must be populated after the
full pipeline (ingest -> silver -> gold -> validation_engine -> refresh_aggs)."""
import duckdb

AGG = "data/gold/agg_passivo_by_unit.parquet"
FACT = "data/gold/fact_passivo_trabalhista.parquet"


def test_agg_passivo_by_unit_is_populated_after_full_pipeline():
    con = duckdb.connect()
    cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{AGG}')").fetchone()[0]
    fact_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{FACT}')").fetchone()[0]
    assert cnt > 0, (
        f"agg_passivo_by_unit is empty ({fact_cnt} passivo rows exist). "
        "Was refresh_aggs.py run after validation_engine?"
    )


def test_agg_passivo_by_unit_totals_match_passivo_fact():
    con = duckdb.connect()
    agg_total, fact_total, agg_rows = con.execute(
        f"""
        SELECT
          (SELECT SUM(total_estimated_impact) FROM read_parquet('{AGG}')),
          (SELECT SUM(estimated_impact) FROM read_parquet('{FACT}')),
          (SELECT COUNT(*) FROM read_parquet('{AGG}'))
        """
    ).fetchone()
    assert fact_total is not None
    tolerance = max(1.0, agg_rows * 1.0)
    assert abs(agg_total - fact_total) <= tolerance, (
        f"agg total ({agg_total}) diverges from fact total ({fact_total})"
    )
