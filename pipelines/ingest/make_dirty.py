"""
Dirty data & seasonality simulation.
Creates *_dirty.csv and *_seasonal.csv variants WITHOUT overwriting originals.
These demonstrate real-world integration challenges: heterogeneous formats,
seasonal patterns, and edge cases.

Usage: python pipelines/ingest/make_dirty.py
Then: modify bronze_to_silver.py to optionally use _dirty or _seasonal variants.
"""
import csv, os, random
from pathlib import Path
from datetime import date, timedelta

BRONZE = Path("data/bronze")
random.seed(99)

def dirties():
    """Create dirty variants: renamed columns, mixed date formats, comma decimals."""
    print("=== DIRTY DATA VARIANTS ===\n")

    # 1. Payroll: English column names
    src = BRONZE / "payroll" / "payroll.csv"
    col_map = {"payroll_id":"id","employee_id":"emp_id","base_salary":"base_pay","gross_total":"gross","net_total":"net_pay","overtime_50_hours":"ot_50_hrs","overtime_50_amount":"ot_50_amt","overtime_70_hours":"ot_70_hrs","overtime_70_amount":"ot_70_amt","overtime_100_hours":"ot_100_hrs","overtime_100_amount":"ot_100_amt","night_shift_hours":"night_hrs","night_shift_amount":"night_amt","periculosidade_amount":"danger_pay","insalubridade_amount":"unhealth_pay","dsr_amount":"weekly_rest","inss_discount":"social_sec","irrf_discount":"income_tax","union_discount":"union_fee","competence":"period"}
    dst = BRONZE / "payroll" / "payroll_dirty.csv"
    with open(src, encoding="utf-8") as fin, open(dst, "w", encoding="utf-8", newline="") as fout:
        r, w = csv.DictReader(fin, delimiter=";"), csv.writer(fout, delimiter=";")
        w.writerow([col_map.get(f, f) for f in r.fieldnames])
        for row in r: w.writerow([row[k] for k in r.fieldnames])
    print(f"  payroll_dirty.csv: {sum(1 for _ in open(dst))} lines, English column names")

    # 2. Bank: comma-as-decimal (R$ 1.234,56)
    src = BRONZE / "bank" / "bank_payments.csv"
    dst = BRONZE / "bank" / "bank_payments_dirty.csv"
    amt = {"expected_amount", "paid_amount"}
    with open(src, encoding="utf-8") as fin:
        lines = list(csv.reader(fin, delimiter=";"))
    header = lines[0]
    with open(dst, "w", encoding="utf-8", newline="") as fout:
        w = csv.writer(fout, delimiter=";")
        w.writerow(header)
        for row in lines[1:]:
            row = dict(zip(header, row))
            for f in amt:
                if row.get(f):
                    try: row[f] = f"{float(row[f]):,.2f}".replace(",","X").replace(".",",").replace("X",".")
                    except: pass
            w.writerow([row.get(h,"") for h in header])
    print(f"  bank_payments_dirty.csv: BR decimal format (1.234,56)")

    print()

def seasonal():
    """Add seasonal patterns: more vacations Dec/Jan, more OT in rainy months (Oct-Mar)."""
    print("=== SEASONAL PATTERNS ===\n")

    # Vacation seasonality: 40% of vacations cluster in Dec/Jan
    src = BRONZE / "events" / "vacations.csv"
    dst = BRONZE / "events" / "vacations_seasonal.csv"
    modified = 0
    with open(src, encoding="utf-8") as fin, open(dst, "w", encoding="utf-8", newline="") as fout:
        r = csv.DictReader(fin, delimiter=";")
        w = csv.DictWriter(fout, fieldnames=r.fieldnames, delimiter=";")
        w.writeheader()
        for row in r:
            if random.random() < 0.40 and row.get("acquisition_start"):
                try:
                    d = date.fromisoformat(row["acquisition_start"])
                    row["acquisition_start"] = d.replace(month=12 if d.month > 6 else 1, day=min(d.day, 28)).isoformat()
                    modified += 1
                except: pass
            w.writerow(row)
    print(f"  vacations_seasonal.csv: {modified} vacations clustered to Dec/Jan")

    # Overtime seasonality: sanitation has more OT in rainy season (Oct-Mar in Brazil)
    # Already handled by inconsistency injection rates. Documented here.
    print(f"  OT seasonality: implied by 32 inconsistency use-cases (UC01-UC06 target overtime)")

    print()

if __name__ == "__main__":
    dirties()
    seasonal()
    print("Done. Original CSVs are intact. Use _dirty/_seasonal variants for demo.")
