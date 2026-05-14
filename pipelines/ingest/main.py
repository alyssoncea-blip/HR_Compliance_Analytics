#!/usr/bin/env python3
"""
HR Compliance Analytics — Synthetic Data Generator
Generates realistic Brazilian labor/sanitation sector data covering 32 use cases.
Outputs to Bronze layer: CSV + Parquet + JSON schema.
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BRONZE_PATH, PERIOD_START, PERIOD_END
from gen_base import (
    generate_positions, generate_unions, generate_units, generate_holidays,
    generate_employees, build_lookups,
)
from gen_time import generate_time_records
from gen_payroll import generate_payroll
from gen_payments import generate_bank_payments
from gen_events import (
    generate_vacations, generate_leaves, generate_salary_history,
    generate_terminations, generate_hour_bank,
)
from gen_dependents import generate_dependents
from gen_inconsistencies import inject_all
from gen_exporter import export_all


def main():
    start = datetime.now()
    print(f"HR Compliance Analytics — Data Generator")
    print(f"Period: {PERIOD_START} to {PERIOD_END}")
    print(f"{'='*60}")

    # -----------------------------------------------------------------------
    # Phase 1: Master data
    # -----------------------------------------------------------------------
    print("\n[1/6] Generating master data...")
    positions = generate_positions()
    unions_ = generate_unions()
    units_ = generate_units()
    holidays = generate_holidays()
    employees = generate_employees()
    print(f"  employees: {len(employees)}")
    print(f"  positions: {len(positions)}")
    print(f"  unions: {len(unions_)}")
    print(f"  units: {len(units_)}")
    print(f"  holidays: {len(holidays)}")

    # -----------------------------------------------------------------------
    # Phase 2: Time records
    # -----------------------------------------------------------------------
    print("\n[2/6] Generating time records...")
    time_records = generate_time_records(employees, holidays)
    print(f"  time_records: {len(time_records)}")

    # -----------------------------------------------------------------------
    # Phase 3: Payroll
    # -----------------------------------------------------------------------
    print("\n[3/6] Generating payroll...")
    payroll = generate_payroll(employees, time_records)
    print(f"  payroll records: {len(payroll)}")

    # -----------------------------------------------------------------------
    # Phase 4: Bank payments
    # -----------------------------------------------------------------------
    print("\n[4/6] Generating bank payments...")
    payments = generate_bank_payments(employees, payroll)
    print(f"  bank payments: {len(payments)}")

    # -----------------------------------------------------------------------
    # Phase 5: Events (vacations, leaves, salary history, terminations, hour bank)
    # -----------------------------------------------------------------------
    print("\n[5/6] Generating events...")
    vacations = generate_vacations(employees)
    leaves = generate_leaves(employees)
    salary_history = generate_salary_history(employees, positions)
    terminations = generate_terminations(employees)
    hour_bank = generate_hour_bank(employees, time_records)
    print(f"  vacations: {len(vacations)}")
    print(f"  leaves: {len(leaves)}")
    print(f"  salary_history: {len(salary_history)}")
    print(f"  terminations: {len(terminations)}")
    print(f"  hour_bank: {len(hour_bank)}")

    # -----------------------------------------------------------------------
    # Phase 6: Dependents
    # -----------------------------------------------------------------------
    print("\n[6/7] Generating dependents...")
    dependents = generate_dependents(employees)
    print(f"  dependents: {len(dependents)}")

    # -----------------------------------------------------------------------
    # Phase 7: Inject inconsistencies (32 use cases)
    # -----------------------------------------------------------------------
    print("\n[7/7] Injecting inconsistencies (32 use cases)...")
    inconsistency_log = inject_all(
        payroll=payroll,
        time_records=time_records,
        payments=payments,
        hour_bank=hour_bank,
        vacations=vacations,
        employees=employees,
        holidays=holidays,
        positions=positions,
        salary_history=salary_history,
    )
    # Group log counts by use case
    uc_counts = {}
    for entry in inconsistency_log:
        uc = entry["use_case"]
        uc_counts[uc] = uc_counts.get(uc, 0) + 1
    print(f"  Total inconsistencies injected: {len(inconsistency_log)}")
    for uc in sorted(uc_counts):
        print(f"    UC{uc:02d}: {uc_counts[uc]} occurrences")

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    export_all(
        employees=employees,
        positions=positions,
        unions_=unions_,
        units_=units_,
        holidays=holidays,
        time_records=time_records,
        payroll=payroll,
        payments=payments,
        hour_bank=hour_bank,
        vacations=vacations,
        leaves=leaves,
        salary_history=salary_history,
        terminations=terminations,
        inconsistency_log=inconsistency_log,
        dependents=dependents,
    )

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nDone in {elapsed:.1f}s.")
    print(f"Output: {os.path.abspath(BRONZE_PATH)}")


if __name__ == "__main__":
    main()
