"""
Bronze -> Silver Pipeline
Reads raw CSV from data/bronze/, standardizes schemas, casts types,
adds lineage columns (source_file, ingested_at),
writes ZSTD-compressed Parquet to data/silver/.
"""
import duckdb, os, json, time
from datetime import datetime, timezone

SILVER = "data/silver"
BRONZE = "data/bronze"
NOW_ISO = datetime.now(timezone.utc).isoformat()

os.makedirs(SILVER, exist_ok=True)
con = duckdb.connect()

def csv_q(path):
    return f"read_csv_auto('{BRONZE}/{path}')".replace(chr(92), "/")

def write_pq(name, sql):
    path = f"{SILVER}/{name}.parquet"
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  {name:30s} {rows:>10,} rows  {size_mb:>8.1f} MB")

def lineage_columns(source):
    return f"'{source}' AS source_file, TIMESTAMP '{NOW_ISO}' AS ingested_at"

print("=" * 60)
print("BRONZE -> SILVER PIPELINE")
print("=" * 60)

t0 = time.time()

# ---------------------------------------------------------------------------
# 1. dim_date
# ---------------------------------------------------------------------------
print("\n[1/9] dim_date")
raw = con.execute(f"SELECT MIN(date) as min_d, MAX(date) as max_d FROM {csv_q('time_clock/time_records.csv')}").fetchone()
min_d = raw[0] or "2024-01-01"; max_d = raw[1] or "2025-12-31"
write_pq("dim_date", f"""
WITH RECURSIVE dates(d) AS (
    SELECT CAST('{min_d}' AS DATE)
    UNION ALL SELECT d+1 FROM dates WHERE d<CAST('{max_d}' AS DATE)
)
SELECT CAST(STRFTIME(d, '%Y%m%d') AS INT) AS date_sk, d AS full_date,
  CAST(STRFTIME(d, '%Y') AS INT) AS yr, CAST(STRFTIME(d, '%m') AS INT) AS mo,
  CAST(STRFTIME(d, '%d') AS INT) AS day, CAST(STRFTIME(d, '%j') AS INT) AS day_of_year,
  CAST(STRFTIME(d, '%u') AS INT) AS day_of_week,
  CASE CAST(STRFTIME(d, '%u') AS INT)
    WHEN 1 THEN 'segunda' WHEN 2 THEN 'terca' WHEN 3 THEN 'quarta'
    WHEN 4 THEN 'quinta' WHEN 5 THEN 'sexta' WHEN 6 THEN 'sabado' WHEN 7 THEN 'domingo'
  END AS day_name,
  STRFTIME(d, '%Y-%m') AS competence, (EXTRACT(YEAR FROM d) * 100 + EXTRACT(MONTH FROM d)) AS year_month,
  CASE WHEN EXTRACT(MONTH FROM d) IN (1,2,3) THEN 1
       WHEN EXTRACT(MONTH FROM d) IN (4,5,6) THEN 2
       WHEN EXTRACT(MONTH FROM d) IN (7,8,9) THEN 3 ELSE 4 END AS quarter,
  CAST(STRFTIME(d, '%u') AS INT) IN (6,7) AS is_weekend,
  {lineage_columns('auto_generated')}
FROM dates
""")

# ---------------------------------------------------------------------------
# 2-4. Passthrough dimensions
# ---------------------------------------------------------------------------
for name, src in [
    ("dim_position", "hr_system/positions.csv"),
    ("dim_union", "hr_system/unions.csv"),
    ("dim_unit", "hr_system/units.csv"),
]:
    print(f"\n[{name}]")
    write_pq(name, f"SELECT c.*, {lineage_columns(src)} FROM {csv_q(src)} c")

# ---------------------------------------------------------------------------
# 5. dim_employee
# ---------------------------------------------------------------------------
print("\n[5/9] dim_employee")
write_pq("dim_employee", f"""
SELECT c.employee_id, c.name, c.cpf, c.rg, c.gender, c.birth_date, c.education,
  c.position_id, c.unit_id, c.union_id, c.hire_date, c.termination_date,
  c.termination_type, c.work_schedule, c.weekly_hours, c.shift_type,
  c.shift_entry_1, c.shift_exit_1, c.shift_entry_2, c.shift_exit_2,
  c.base_salary, c.bank_code, c.bank_agency, c.bank_account,
  c.dependents, c.periculosidade_eligible, c.insalubridade_eligible, c.status,
  {lineage_columns('hr_system/employees.csv')}
FROM {csv_q('hr_system/employees.csv')} c
""")

# ---------------------------------------------------------------------------
# 6. fact_time_record
# ---------------------------------------------------------------------------
print("\n[6/9] fact_time_record")
write_pq("fact_time_record", f"""
SELECT c.*, CAST(STRFTIME(CAST(c.date AS DATE),'%Y%m%d')AS INT) date_sk,
  CAST(c.date AS DATE) full_date, {lineage_columns('time_clock/time_records.csv')}
FROM {csv_q('time_clock/time_records.csv')} c
""")

# ---------------------------------------------------------------------------
# 7. fact_payroll
# ---------------------------------------------------------------------------
print("\n[7/9] fact_payroll")
write_pq("fact_payroll", f"""
SELECT c.*, CAST(c.year*100+c.month AS INT) date_sk,
  {lineage_columns('payroll/payroll.csv')}
FROM {csv_q('payroll/payroll.csv')} c
""")

# ---------------------------------------------------------------------------
# 8. fact_payment
# ---------------------------------------------------------------------------
print("\n[8/9] fact_payment")
write_pq("fact_payment", f"""
SELECT c.*, {lineage_columns('bank/bank_payments.csv')}
FROM {csv_q('bank/bank_payments.csv')} c
""")

# ---------------------------------------------------------------------------
# 9. fact_hour_bank
# ---------------------------------------------------------------------------
print("\n[9/9] fact_hour_bank")
write_pq("fact_hour_bank", f"""
SELECT c.*, {lineage_columns('time_clock/hour_bank.csv')}
FROM {csv_q('time_clock/hour_bank.csv')} c
""")

# ---------------------------------------------------------------------------
# Event tables
# ---------------------------------------------------------------------------
for name, src in [
    ("vacations", "events/vacations.csv"),
    ("leaves", "events/leaves.csv"),
    ("salary_history", "events/salary_history.csv"),
    ("terminations", "events/terminations.csv"),
    ("dependents", "hr_system/dependents.csv"),
]:
    print(f"\n[{name}]")
    try:
        write_pq(name, f"SELECT c.*, {lineage_columns(src)} FROM {csv_q(src)} c")
    except Exception as e:
        print(f"  SKIP {name}: {e}")

# ---------------------------------------------------------------------------
elapsed = time.time() - t0
total_tables = len([f for f in os.listdir(SILVER) if f.endswith('.parquet')])
print(f"\nDone in {elapsed:.1f}s — {total_tables} tables in {SILVER}")

manifest = {"pipeline":"bronze_to_silver","run_at":NOW_ISO,"elapsed_s":round(elapsed,1),"output_tables":total_tables}
with open(f"{SILVER}/silver_manifest.json","w") as f: json.dump(manifest,f,indent=2)
con.close()
