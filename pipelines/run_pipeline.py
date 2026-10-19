#!/usr/bin/env python3
"""Run the HR Compliance Analytics pipeline sequentially.

Supports resumable execution and per-step retries:

    python pipelines/run_pipeline.py                      # full run (default)
    python pipelines/run_pipeline.py --dry-run            # print plan and exit
    python pipelines/run_pipeline.py --skip-ingest        # resume from bronze_to_silver
    python pipelines/run_pipeline.py --from-step validation
    python pipelines/run_pipeline.py --max-retries 2      # 2 extra attempts per step
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent

Step = Tuple[str, Path]

STEP_NAMES: Sequence[str] = (
    "ingest",
    "bronze_to_silver",
    "silver_to_gold",
    "validation",
    "refresh_aggs",
    "governance",
)


def build_full_plan(root: Path) -> List[Step]:
    """Ordered (short_name, script_path) steps for a complete run."""
    return [
        ("ingest", root / "ingest" / "main.py"),
        ("bronze_to_silver", root / "bronze_to_silver.py"),
        ("silver_to_gold", root / "silver_to_gold.py"),
        ("validation", root / "validation_engine.py"),
        ("refresh_aggs", root / "refresh_aggs.py"),
        ("governance", root / "governance.py"),
    ]


def parse_plan(args: Any) -> List[Step]:
    """Pure: build the ordered execution plan from parsed CLI args.

    ``args`` must expose ``from_step``, ``skip_ingest`` and ``dry_run``
    (plain argparse.Namespace works; tests may pass SimpleNamespace).
    Paths are deterministic for a given module location.
    """
    plan = build_full_plan(ROOT)
    start = "ingest" if not args.skip_ingest else "bronze_to_silver"
    if args.from_step:
        start = args.from_step
    names = [name for name, _ in plan]
    if start not in names:
        raise SystemExit(
            f"[FAIL] Unknown step '{start}'. Valid steps: {', '.join(names)}"
        )
    return plan[names.index(start):]


def run_step(step: str, script_path: Path, max_retries: int = 1) -> None:
    """Run one step, retrying up to ``max_retries`` extra attempts."""
    attempts = 1 + max(0, max_retries)
    for attempt in range(1, attempts + 1):
        print(f"\n[RUN] {step}: {script_path} (attempt {attempt}/{attempts})")
        result = subprocess.run([sys.executable, str(script_path)])
        if result.returncode == 0:
            print(f"[OK] {step}")
            return
        if attempt < attempts:
            backoff = 2 * attempt
            print(
                f"[RETRY] {step} failed with exit code {result.returncode}; "
                f"retrying in {backoff}s…"
            )
            time.sleep(backoff)
    raise SystemExit(f"[FAIL] {step} failed after {attempts} attempt(s)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sequential runner for the HR Compliance Analytics pipeline."
    )
    parser.add_argument(
        "--from-step",
        metavar="NAME",
        choices=STEP_NAMES,
        default=None,
        help=(
            "Resume from a named step (short name, e.g. 'validation'). "
            f"Valid names: {', '.join(STEP_NAMES)}"
        ),
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Shortcut for --from-step bronze_to_silver (reuses existing Bronze).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        metavar="N",
        help="Extra attempts per step on failure (default: 1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the execution plan and exit 0 without running anything.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    plan = parse_plan(args)

    print("HR Compliance Analytics - Pipeline Runner")
    if args.dry_run:
        print("[DRY-RUN] Execution plan:")
        for i, (step, script) in enumerate(plan, start=1):
            print(f"  {i}. {step}: {root_relative(script)}")
        print(f"[DRY-RUN] max_retries per step: {max(0, args.max_retries)}")
        print("[DRY-RUN] Nothing was executed.")
        return

    for step, script in plan:
        run_step(step, script, max_retries=args.max_retries)

    print("\n[SUCCESS] Pipeline completed.")


def root_relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
