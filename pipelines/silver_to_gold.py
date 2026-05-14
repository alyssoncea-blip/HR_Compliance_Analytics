"""
Silver -> Gold Pipeline
Builds dimensional model (SCD2), consolidated monthly fact,
passivo trabalhista, and dashboard pre-aggregations.
Reads from data/silver/, writes ZSTD Parquet to data/gold/.
"""
import duckdb, os, json, time
from datetime import datetime, timezone

SILVER = "data/silver"
GOLD = "data/gold"
NOW_ISO = datetime.now(timezone.utc).isoformat()

os.makedirs(GOLD, exist_ok=True)
con = duckdb.connect()

def pq(path): return f"'{SILVER}/{path}.parquet'".replace(chr(92), "/")
def gq(path): return f"'{GOLD}/{path}.parquet'".replace(chr(92), "/")

def write_pq(name, sql):
    path = f"{GOLD}/{name}.parquet"
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  {path.split('/')[-1]:35s} {rows:>10,} rows  {size_mb:>8.1f} MB")

print("=" * 60)
print("SILVER -> GOLD PIPELINE")
print("=" * 60)

t0 = time.time()

# =========================================================================
# 0. dim_cct_rule_version — versioned CCT rules by validity window
# =========================================================================
print("\n[0/5] dim_cct_rule_version")
sql_cct_rules = f"""
WITH cct_rules_raw AS (
    SELECT * FROM (
        VALUES
        ('MG', 'Sindágua-MG', 'Copasa', DATE '2023-01-01', DATE '2023-12-31', 44, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0420),
        ('MG', 'Sindágua-MG', 'Copasa', DATE '2024-01-01', DATE '2024-12-31', 44, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0462),
        ('MG', 'Sindágua-MG', 'Copasa', DATE '2025-01-01', DATE '2027-12-31', 44, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0500),
        ('RJ', 'Sindágua-RJ', 'Águas do Rio', DATE '2023-01-01', DATE '2023-12-31', 44, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0480),
        ('RJ', 'Sindágua-RJ', 'Águas do Rio', DATE '2024-01-01', DATE '2024-12-31', 44, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0520),
        ('RJ', 'Sindágua-RJ', 'Águas do Rio', DATE '2025-01-01', DATE '2026-12-31', 44, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0560),
        ('RN', 'Sindágua-RN', 'CAERN', DATE '2020-01-01', DATE '2021-12-31', 30, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.0900),
        ('RN', 'Sindágua-RN', 'CAERN', DATE '2022-01-01', DATE '2023-12-31', 30, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.1100),
        ('RN', 'Sindágua-RN', 'CAERN', DATE '2024-01-01', DATE '2026-12-31', 30, 0.50, 1.00, 1.00, TRUE, 0.50, 0.70, 0.20, 22, 5, 0.30, 0.40, 40.0, 1.0, 0.1270)
    ) AS t(
        state, union_name, company, valid_from, valid_to, standard_weekly_hours,
        he_weekday_percent, he_sunday_percent, he_holiday_percent,
        he_progressive, he_first_hour_percent, he_additional_hours_percent,
        night_shift_percent, night_shift_start, night_shift_end,
        periculosidade_percent, insalubridade_percent,
        max_hour_bank_hours, min_rest_interval_hours, salary_adjustment_percent
    )
)
SELECT
    CONCAT(CAST(u.union_id AS VARCHAR), '-', STRFTIME(r.valid_from, '%Y%m%d')) AS cct_rule_id,
    u.union_id,
    r.state,
    r.union_name,
    r.company,
    r.valid_from,
    r.valid_to,
    r.standard_weekly_hours,
    r.he_weekday_percent,
    r.he_sunday_percent,
    r.he_holiday_percent,
    r.he_progressive,
    r.he_first_hour_percent,
    r.he_additional_hours_percent,
    r.night_shift_percent,
    r.night_shift_start,
    r.night_shift_end,
    r.periculosidade_percent,
    r.insalubridade_percent,
    r.max_hour_bank_hours,
    r.min_rest_interval_hours,
    r.salary_adjustment_percent,
    '{NOW_ISO}' AS generated_at
FROM cct_rules_raw r
JOIN read_parquet({pq('dim_union')}) u ON u.state = r.state
"""
write_pq("dim_cct_rule_version", sql_cct_rules)

# =========================================================================
# 0b. dim_liability_factor_version — versioned factors by severity
# =========================================================================
print("\n[0b/5] dim_liability_factor_version")
sql_liability_factors = f"""
SELECT * FROM (
    VALUES
    ('critico', 1.00, DATE '2020-01-01', DATE '2024-12-31', 'baseline_v1', '{NOW_ISO}'),
    ('alto',    0.65, DATE '2020-01-01', DATE '2024-12-31', 'baseline_v1', '{NOW_ISO}'),
    ('medio',   0.35, DATE '2020-01-01', DATE '2024-12-31', 'baseline_v1', '{NOW_ISO}'),
    ('critico', 1.00, DATE '2025-01-01', DATE '9999-12-31', 'baseline_v2', '{NOW_ISO}'),
    ('alto',    0.70, DATE '2025-01-01', DATE '9999-12-31', 'baseline_v2', '{NOW_ISO}'),
    ('medio',   0.40, DATE '2025-01-01', DATE '9999-12-31', 'baseline_v2', '{NOW_ISO}')
) AS t(severity, factor, valid_from, valid_to, parameter_set, generated_at)
"""
write_pq("dim_liability_factor_version", sql_liability_factors)

# =========================================================================
# 1. dim_employee_scd2 — SCD Type 2 from dim_employee + salary_history
# =========================================================================
print("\n[1/5] dim_employee_scd2")
sql_scd2 = f"""
WITH base AS (
    SELECT *, '{NOW_ISO}'::TIMESTAMP AS scd_valid_from,
           CAST('9999-12-31' AS DATE) AS scd_valid_to,
           1 AS scd_version,
           true AS is_current
    FROM read_parquet({pq('dim_employee')})
),
changes AS (
    SELECT sh.employee_id, sh.new_salary, sh.effective_date AS change_date,
           e.name, e.cpf, e.gender, e.birth_date, e.education,
           e.position_id, e.unit_id, e.union_id, e.hire_date,
           e.termination_date, e.termination_type, e.work_schedule,
           e.weekly_hours, e.shift_type, e.periculosidade_eligible,
           e.insalubridade_eligible, e.status,
           sh.effective_date AS scd_valid_from,
           COALESCE(LEAD(sh.effective_date) OVER (
               PARTITION BY sh.employee_id ORDER BY sh.effective_date
           ), CAST('9999-12-31' AS DATE)) AS scd_valid_to,
           ROW_NUMBER() OVER (
               PARTITION BY sh.employee_id ORDER BY sh.effective_date
           ) + 1 AS scd_version
    FROM read_parquet({pq('salary_history')}) sh
    JOIN read_parquet({pq('dim_employee')}) e ON sh.employee_id = e.employee_id
    WHERE sh.new_salary <> e.base_salary
),
all_versions AS (
    SELECT employee_id, name, cpf, gender, birth_date, education,
           position_id, unit_id, union_id, hire_date, termination_date,
           termination_type, work_schedule, weekly_hours, shift_type,
           base_salary, periculosidade_eligible, insalubridade_eligible, status,
           scd_valid_from, scd_valid_to, scd_version, is_current
    FROM base
    UNION ALL
    SELECT employee_id, name, cpf, gender, birth_date, education,
           position_id, unit_id, union_id, hire_date, termination_date,
           termination_type, work_schedule, weekly_hours, shift_type,
           new_salary AS base_salary, periculosidade_eligible, insalubridade_eligible, status,
           scd_valid_from, scd_valid_to, scd_version,
           scd_valid_to = CAST('9999-12-31' AS DATE) AS is_current
    FROM changes
)
SELECT *, '{NOW_ISO}' AS generated_at FROM all_versions
ORDER BY employee_id, scd_version
"""
write_pq("dim_employee_scd2", sql_scd2)

# =========================================================================
# 2. fact_monthly_employee — Consolidated monthly fact
# =========================================================================
print("\n[2/5] fact_monthly_employee")
sql_monthly = f"""
SELECT
    e.employee_id,
    CAST(p.year * 100 + p.month AS INTEGER) AS date_sk,
    p.year, p.month,
    CASE WHEN p.month IN (1,2,3) THEN 1 WHEN p.month IN (4,5,6) THEN 2
         WHEN p.month IN (7,8,9) THEN 3 ELSE 4 END AS quarter,
    p.year || '-' || LPAD(CAST(p.month AS VARCHAR), 2, '0') AS competence,

    COALESCE(t_agg.total_hours, 0) AS total_hours_worked,
    COALESCE(t_agg.total_overtime_50, 0) AS total_overtime_50_hours,
    COALESCE(t_agg.total_overtime_70, 0) AS total_overtime_70_hours,
    COALESCE(t_agg.total_overtime_100, 0) AS total_overtime_100_hours,
    COALESCE(t_agg.total_night, 0) AS total_night_hours,
    COALESCE(t_agg.medical_absences, 0) AS medical_absences,
    COALESCE(t_agg.unjustified_absences, 0) AS unjustified_absences,
    COALESCE(t_agg.missing_records, 0) AS missing_records,
    COALESCE(t_agg.holidays_worked, 0) AS holiday_days_worked,
    COALESCE(t_agg.sundays_worked, 0) AS sundays_worked,

    p.base_salary,
    p.overtime_50_hours AS payroll_overtime_50_hours,
    p.overtime_50_amount, p.overtime_70_amount, p.overtime_100_amount,
    p.night_shift_hours AS payroll_night_hours, p.night_shift_amount,
    p.periculosidade_amount, p.insalubridade_amount,
    p.dsr_amount, p.salary_family_amount,
    p.gross_total, p.inss_discount, p.irrf_discount,
    p.union_discount, p.net_total,

    COALESCE(pay.expected_amount, 0) AS payment_expected,
    COALESCE(pay.paid_amount, 0) AS payment_paid,
    COALESCE(pay.paid_amount - pay.expected_amount, 0) AS payment_divergence,
    CASE WHEN pay.payment_status = 'paid' THEN 1 ELSE 0 END AS payment_matched,
    CASE WHEN ABS(COALESCE(pay.paid_amount, 0) - COALESCE(pay.expected_amount, 0)) > 5 THEN 1 ELSE 0 END AS has_payment_divergence,

    COALESCE(hb.current_balance, 0) AS hour_bank_balance,
    CASE WHEN COALESCE(hb.current_balance, 0) < -5 THEN 1 ELSE 0 END AS hour_bank_negative,
    CASE WHEN COALESCE(hb.current_balance, 0) > 40 THEN 1 ELSE 0 END AS hour_bank_exceeded,

    0 AS he_inconsistencies,
    0 AS night_shift_inconsistencies,
    0 AS periculosidade_inconsistencies,
    0 AS payment_inconsistencies,
    0 AS total_inconsistencies,

    '{NOW_ISO}' AS generated_at
FROM read_parquet({pq('fact_payroll')}) p
JOIN read_parquet({pq('dim_employee')}) e ON p.employee_id = e.employee_id
LEFT JOIN (
    SELECT employee_id,
           CAST(STRFTIME(CAST(date AS DATE), '%Y') AS INTEGER) AS year,
           CAST(STRFTIME(CAST(date AS DATE), '%m') AS INTEGER) AS month,
           SUM(total_hours) AS total_hours,
            SUM(overtime_50) AS total_overtime_50,
            SUM(overtime_70) AS total_overtime_70,
            SUM(overtime_100) AS total_overtime_100,
           SUM(night_hours) AS total_night,
           SUM(CASE WHEN absence_type = 'medical' THEN 1 ELSE 0 END) AS medical_absences,
           SUM(CASE WHEN absence_type = 'unjustified' THEN 1 ELSE 0 END) AS unjustified_absences,
           SUM(CASE WHEN absence_type = 'missing' THEN 1 ELSE 0 END) AS missing_records,
           SUM(CASE WHEN is_holiday = true THEN 1 ELSE 0 END) AS holidays_worked,
           SUM(CASE WHEN is_sunday = true THEN 1 ELSE 0 END) AS sundays_worked
    FROM read_parquet({pq('fact_time_record')})
    GROUP BY employee_id, year, month
) t_agg ON p.employee_id = t_agg.employee_id AND p.year = t_agg.year AND p.month = t_agg.month
LEFT JOIN read_parquet({pq('fact_payment')}) pay ON p.employee_id = pay.employee_id AND p.year = pay.year AND p.month = pay.month
LEFT JOIN read_parquet({pq('fact_hour_bank')}) hb ON p.employee_id = hb.employee_id AND p.year = hb.year AND p.month = hb.month
"""
write_pq("fact_monthly_employee", sql_monthly)

# =========================================================================
# 3. fact_passivo_trabalhista — placeholder (materialized in validation_engine)
# =========================================================================
print("\n[3/5] fact_passivo_trabalhista (placeholder)")
write_pq("fact_passivo_trabalhista", """
SELECT
    CAST(NULL AS VARCHAR) AS passivo_id,
    CAST(NULL AS BIGINT) AS employee_id,
    CAST(NULL AS BIGINT) AS unit_id,
    CAST(NULL AS VARCHAR) AS unit_name,
    CAST(NULL AS BIGINT) AS union_id,
    CAST(NULL AS VARCHAR) AS union_name,
    CAST(NULL AS INTEGER) AS use_case,
    CAST(NULL AS VARCHAR) AS rule_name,
    CAST(NULL AS VARCHAR) AS liability_type,
    CAST(NULL AS VARCHAR) AS category,
    CAST(NULL AS VARCHAR) AS severity,
    CAST(NULL AS DOUBLE) AS estimated_impact,
    CAST(NULL AS TIMESTAMP) AS calculated_at
WHERE 1 = 0
""")

# =========================================================================
# 4. Dashboard pre-aggregations
# =========================================================================
print("\n[4/5] Dashboard aggregations")

# agg_unit_monthly
sql_agg_unit = f"""
SELECT u.name AS unit_name, u.state, f.year, f.month, f.competence,
       COUNT(DISTINCT f.employee_id) AS employee_count,
       ROUND(AVG(f.total_hours_worked), 1) AS avg_hours,
       ROUND(SUM(f.total_overtime_50_hours), 1) AS total_ot_50,
       ROUND(SUM(f.total_overtime_100_hours), 1) AS total_ot_100,
       ROUND(SUM(f.total_night_hours), 1) AS total_night,
       ROUND(AVG(f.gross_total), 0) AS avg_gross
FROM read_parquet({gq('fact_monthly_employee')}) f
JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
GROUP BY u.name, u.state, f.year, f.month, f.competence
"""
write_pq("agg_unit_monthly", sql_agg_unit)

# agg_union_monthly
sql_agg_union = f"""
SELECT un.name AS union_name, un.state, un.standard_weekly_hours,
       f.year, f.month, f.competence,
       COUNT(DISTINCT f.employee_id) AS employee_count,
       ROUND(AVG(f.total_hours_worked), 1) AS avg_hours,
       ROUND(AVG(f.gross_total), 0) AS avg_gross
FROM read_parquet({gq('fact_monthly_employee')}) f
JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
GROUP BY un.name, un.state, un.standard_weekly_hours, f.year, f.month, f.competence
"""
write_pq("agg_union_monthly", sql_agg_union)

# agg_passivo_by_unit
sql_agg_passivo = f"""
SELECT u.name AS unit_name, u.state,
       fp.liability_type, fp.severity,
       COUNT(*) AS occurrence_count,
       ROUND(SUM(fp.estimated_impact), 0) AS total_estimated_impact,
       ROUND(AVG(fp.estimated_impact), 0) AS avg_impact
FROM read_parquet({gq('fact_passivo_trabalhista')}) fp
JOIN read_parquet({pq('dim_unit')}) u ON fp.unit_id = u.unit_id
GROUP BY u.name, u.state, fp.liability_type, fp.severity
"""
write_pq("agg_passivo_by_unit", sql_agg_passivo)

# agg_vacation_risk
sql_agg_vac = f"""
SELECT u.name AS unit_name, u.state,
       v.status,
       COUNT(*) AS vacation_count,
       ROUND(AVG(DATEDIFF('day', v.acquisition_start, CURRENT_DATE)), 0) AS avg_days_since_start,
       SUM(e.base_salary * CASE WHEN v.status = 'expired' THEN 2.0 WHEN v.status = 'impending' THEN 1.5 ELSE 1.0 END) AS estimated_passivo
FROM read_parquet({pq('vacations')}) v
JOIN read_parquet({pq('dim_employee')}) e ON v.employee_id = e.employee_id
JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
WHERE e.status = 'active'
GROUP BY u.name, u.state, v.status
"""
write_pq("agg_vacation_risk", sql_agg_vac)

# agg_employee_annual
sql_agg_emp = f"""
SELECT e.employee_id, e.work_schedule, e.weekly_hours, u.state,
       f.year,
       COUNT(DISTINCT f.month) AS months_active,
       ROUND(AVG(f.total_hours_worked), 1) AS avg_monthly_hours,
       ROUND(SUM(f.total_overtime_50_hours + f.total_overtime_70_hours + f.total_overtime_100_hours), 1) AS total_overtime,
       ROUND(AVG(f.gross_total), 0) AS avg_gross,
       ROUND(SUM(f.gross_total), 0) AS total_gross
FROM read_parquet({gq('fact_monthly_employee')}) f
JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
GROUP BY e.employee_id, e.work_schedule, e.weekly_hours, u.state, f.year
"""
write_pq("agg_employee_annual", sql_agg_emp)

# =========================================================================
# Summary
# =========================================================================
elapsed = time.time() - t0
print(f"\nDone in {elapsed:.1f}s")
print(f"Output: {os.path.abspath(GOLD)}")

total_tables = len([f for f in os.listdir(GOLD) if f.endswith('.parquet')])
manifest = {
    "pipeline": "silver_to_gold",
    "run_at": NOW_ISO,
    "elapsed_s": round(elapsed, 1),
    "output_tables": total_tables,
    "targets": [
        "dim_cct_rule_version", "dim_liability_factor_version", "dim_employee_scd2", "fact_monthly_employee", "fact_passivo_trabalhista",
        "agg_unit_monthly", "agg_union_monthly", "agg_passivo_by_unit",
        "agg_vacation_risk", "agg_employee_annual",
    ],
}
with open(f"{GOLD}/gold_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  Manifest: {GOLD}/gold_manifest.json")

con.close()
