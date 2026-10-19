"""Tests for run_pipeline CLI plan parsing (pure function only)."""

import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipelines.run_pipeline import STEP_NAMES, parse_plan  # noqa: E402


def make_args(from_step=None, skip_ingest=False, max_retries=1, dry_run=False):
    return SimpleNamespace(
        from_step=from_step,
        skip_ingest=skip_ingest,
        max_retries=max_retries,
        dry_run=dry_run,
    )


def test_full_plan_by_default():
    plan = parse_plan(make_args())
    assert [name for name, _ in plan] == list(STEP_NAMES)
    assert len(plan) == 6


def test_dry_run_with_skip_ingest_still_resolves_plan():
    plan = parse_plan(make_args(skip_ingest=True, dry_run=True))
    assert [name for name, _ in plan] == [
        "bronze_to_silver",
        "silver_to_gold",
        "validation",
        "refresh_aggs",
        "governance",
    ]


def test_skip_ingest_starts_at_bronze_to_silver():
    plan = parse_plan(make_args(skip_ingest=True))
    assert plan[0][0] == "bronze_to_silver"
    assert len(plan) == 5


def test_from_step_validation_resumes_midway():
    plan = parse_plan(make_args(from_step="validation"))
    assert [name for name, _ in plan] == ["validation", "refresh_aggs", "governance"]


def test_from_step_ingest_equals_full_plan():
    assert parse_plan(make_args(from_step="ingest")) == parse_plan(make_args())


def test_dry_run_with_from_step_keeps_tail_only():
    plan = parse_plan(make_args(from_step="silver_to_gold", dry_run=True))
    assert [name for name, _ in plan] == ["silver_to_gold", "validation", "refresh_aggs", "governance"]


def test_unknown_step_raises_systemexit_with_hint():
    with pytest.raises(SystemExit) as exc_info:
        parse_plan(make_args(from_step="does-not-exist"))
    assert "does-not-exist" in str(exc_info.value)
    assert "validation" in str(exc_info.value)


def test_plan_paths_exist_in_repo():
    for _name, path in parse_plan(make_args()):
        assert isinstance(path, Path)
        assert path.suffix == ".py"
