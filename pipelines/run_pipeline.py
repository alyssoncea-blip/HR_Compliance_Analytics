#!/usr/bin/env python3
"""Run full HR Compliance Analytics data pipeline sequentially."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_step(step: str, script_path: Path) -> None:
    print(f"\n[RUN] {step}: {script_path}")
    result = subprocess.run([sys.executable, str(script_path)])
    if result.returncode != 0:
        raise SystemExit(f"[FAIL] {step} failed with exit code {result.returncode}")
    print(f"[OK] {step}")


def main() -> None:
    root = Path(__file__).resolve().parent
    steps = [
        ("Data generation (synthetic)", root / "ingest" / "main.py"),
        ("Bronze to Silver", root / "bronze_to_silver.py"),
        ("Silver to Gold", root / "silver_to_gold.py"),
        ("Labor validation engine", root / "validation_engine.py"),
        ("Data governance checks", root / "governance.py"),
    ]

    print("HR Compliance Analytics - Full Pipeline Runner")
    for step, script in steps:
        run_step(step, script)

    print("\n[SUCCESS] Full pipeline completed.")


if __name__ == "__main__":
    main()
