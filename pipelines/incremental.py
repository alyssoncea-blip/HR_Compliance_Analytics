"""
Incremental planning helpers for the Bronze -> Silver pipeline.

Pure, dependency-free functions only: they must be trivially unit-testable
without touching DuckDB, Parquet or the filesystem. Dates are represented as
ISO "YYYY-MM-DD" strings so planning is deterministic regardless of how the
caller obtained them.
"""
from __future__ import annotations


def plan_delta(new_dates: list[str], watermark: str | None) -> list[str]:
    """Decide which bronze dates still need to be loaded into Silver.

    The high-watermark is the maximum ``full_date`` already present in the
    Silver table. A cold start is expressed as ``watermark=None`` and loads
    every candidate date.

    Comparison is strict: a date equal to the watermark is already loaded
    (its whole day arrived in a previous run), so only dates strictly greater
    than the watermark are returned. This rules out the classic off-by-one
    re-ingestion of the watermark day.

    Args:
        new_dates: candidate date strings observed in the Bronze CSV.
        watermark: current high-watermark, or ``None`` for a cold start.

    Returns:
        Sorted, de-duplicated list of dates to load.
    """
    if new_dates is None:
        return []
    distinct = sorted({str(date) for date in new_dates})
    if watermark is None:
        return distinct
    return [date for date in distinct if date > str(watermark)]
