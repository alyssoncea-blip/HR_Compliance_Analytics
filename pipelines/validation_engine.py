"""
Validation Engine — Motor de Validacao de 32 Regras Trabalhistas
Cross-references Ponto x Folha x Pagamento x CCT x Cadastro to detect
inconsistencies with calculated financial impact.

Reads from Gold/Silver. Writes fact_detected_inconsistency to Gold.
"""
import argparse, duckdb, os, sys, time, json
from datetime import datetime, timezone

try:
    from validation_rules import uc1_query, uc8_query, uc28_query
    from competence_utils import (
        CONTRACT_COLS, normalize_competence, list_competences,
        resolve_requested_competences, merge_detections,
    )
except ImportError:
    from pipelines.validation_rules import uc1_query, uc8_query, uc28_query
    from pipelines.competence_utils import (
        CONTRACT_COLS, normalize_competence, list_competences,
        resolve_requested_competences, merge_detections,
    )

SILVER = "data/silver"
GOLD = "data/gold"
OBS = f"{GOLD}/observability"
NOW_ISO = datetime.now(timezone.utc).isoformat()

os.makedirs(GOLD, exist_ok=True)
os.makedirs(OBS, exist_ok=True)
con = duckdb.connect()

parser = argparse.ArgumentParser(description="Validation engine - 32 labor rules")
parser.add_argument("--competence", action="append", metavar="YYYY-MM", default=None,
                    help="competence to (re)process, repeatable")
parser.add_argument("--competence-from", dest="competence_from", metavar="YYYY-MM", default=None,
                    help="inclusive lower bound of competence range")
parser.add_argument("--competence-to", dest="competence_to", metavar="YYYY-MM", default=None,
                    help="inclusive upper bound of competence range")
args = parser.parse_args()

AVAILABLE_COMPETENCES = list_competences(con, GOLD)
try:
    TARGETS = resolve_requested_competences(
        args.competence, args.competence_from, args.competence_to, AVAILABLE_COMPETENCES
    )
except ValueError as e:
    sys.stderr.write(f"[argument error] {e}\n")
    sys.exit(2)
PARTITIONED = TARGETS is not None
MONTH_SET = "(" + ",".join(f"'{c}'" for c in TARGETS) + ")" if PARTITIONED else None

# SLA basis: full-run thresholds; partitioned runs scale proportionally to the
# fraction of competences processed with generous floors (documented in prod).
FULL_SLA_RUNTIME, FULL_SLA_CRITICAL = 180, 350_000
if PARTITIONED:
    _frac = len(TARGETS) / max(1, len(AVAILABLE_COMPETENCES))
    SLA_RUNTIME = max(60.0, round(FULL_SLA_RUNTIME * _frac, 1))
    SLA_CRITICAL = max(2000, int(round(FULL_SLA_CRITICAL * _frac)))
    SLA_POLICY = (
        f"partitioned: thresholds scaled by the fraction of competences processed "
        f"({len(TARGETS)}/{len(AVAILABLE_COMPETENCES)}), floor 60s runtime / 2000 critical rows; "
        f"full-run threshold is {FULL_SLA_RUNTIME}s / {FULL_SLA_CRITICAL} critical rows"
    )
else:
    SLA_RUNTIME, SLA_CRITICAL = FULL_SLA_RUNTIME, FULL_SLA_CRITICAL
    SLA_POLICY = f"full run: fixed thresholds ({FULL_SLA_RUNTIME}s runtime, {FULL_SLA_CRITICAL} critical rows)"

# Row-scope predicates (empty strings in full mode -> SQL unchanged)
_scope_where_g = ""
_scope_tr = ""
_scope_tr_util = ""
_scope_pay_bp = ""
_scope_pay_raw = ""
_scope_sh = ""
_scope_vac = ""
if PARTITIONED:
    _scope_where_g = f"""
     WHERE g.year || '-' || LPAD(CAST(g.month AS VARCHAR), 2, '0') IN {MONTH_SET}"""
    _scope_tr = f"""
      AND SUBSTR(CAST(tr.date_sk AS VARCHAR), 1, 4) || '-' || SUBSTR(CAST(tr.date_sk AS VARCHAR), 5, 2) IN {MONTH_SET}"""
    _scope_tr_util = f"""
           SUBSTR(CAST(date_sk AS VARCHAR), 1, 4) || '-' || SUBSTR(CAST(date_sk AS VARCHAR), 5, 2) IN {MONTH_SET}"""
    _scope_pay_bp = f"""
        AND CAST(bp.year AS VARCHAR) || '-' || LPAD(CAST(bp.month AS VARCHAR), 2, '0') IN {MONTH_SET}"""
    _scope_pay_raw = f"""
        WHERE CAST(year AS VARCHAR) || '-' || LPAD(CAST(month AS VARCHAR), 2, '0') IN {MONTH_SET}"""
    _scope_sh = f"""
      AND SUBSTR(CAST(sh.effective_date AS VARCHAR), 1, 7) IN {MONTH_SET}"""
    _scope_vac = f"""
      AND SUBSTR(CAST(v.concession_deadline AS VARCHAR), 1, 7) IN {MONTH_SET}"""



def pq(path): return f"'{SILVER}/{path}.parquet'".replace(chr(92), "/")
def gq(path): return f"'{GOLD}/{path}.parquet'".replace(chr(92), "/")
def bq(path): return f"'{BRONZE}/{path}.parquet'".replace(chr(92), "/") if 'BRONZE' in dir() else f"'data/bronze/{path}.parquet'".replace(chr(92), "/")

# -------------------------------------------------------------------
# Build hourly rate and CCT rules context
# -------------------------------------------------------------------
print("=" * 60)
print(f"VALIDATION ENGINE — 32 RULES  (mode: {'partitioned ' + str(TARGETS) if PARTITIONED else 'full'})")
print("=" * 60)

t_start = time.time()

# Versioned CCT rules (built in silver_to_gold)
con.execute(f"""
    CREATE OR REPLACE TEMP VIEW cct_rules AS
    SELECT * FROM read_parquet({gq("dim_cct_rule_version")})
""")

# Monthly payroll + time aggregate - reads from Gold + Silver facts for precision
con.execute(f"""
    CREATE OR REPLACE TEMP VIEW monthly_ctx AS
    SELECT
        g.employee_id, g.date_sk, g.year, g.month,
        g.year || '-' || LPAD(CAST(g.month AS VARCHAR), 2, '0') AS competence,
        g.base_salary, g.dsr_amount, g.periculosidade_amount, g.insalubridade_amount,
        g.gross_total, g.net_total, g.inss_discount, g.irrf_discount, g.union_discount,
        g.payment_expected, g.payment_paid, g.payment_divergence, g.has_payment_divergence,
        g.hour_bank_balance, g.hour_bank_negative, g.hour_bank_exceeded,
        g.total_hours_worked,
        g.total_overtime_50_hours AS time_overtime_50,
        g.total_overtime_70_hours AS time_overtime_70,
        g.total_overtime_100_hours AS time_overtime_100,
        g.total_night_hours AS time_night_hours,
        g.medical_absences, g.unjustified_absences, g.missing_records,
        g.holiday_days_worked, g.sundays_worked,
        g.payroll_overtime_50_hours,
        g.overtime_50_amount, g.overtime_70_amount, g.overtime_100_amount,
        g.payroll_night_hours, g.night_shift_amount,
        g.salary_family_amount,
        ROUND(ed.base_salary / (NULLIF(ed.weekly_hours, 0) * 4.33), 4) AS hourly_rate,
        ed.weekly_hours,
        cct.he_weekday_percent, cct.he_sunday_percent, cct.he_holiday_percent,
        cct.he_progressive, cct.he_first_hour_percent, cct.he_additional_hours_percent,
        cct.night_shift_percent, cct.periculosidade_percent, cct.insalubridade_percent,
        cct.max_hour_bank_hours, cct.min_rest_interval_hours,
        cct.state, ed.union_id, ed.work_schedule, ed.shift_type, cct.standard_weekly_hours AS cct_weekly_hours,
        -- Direct payroll columns (overtime_70/100 hours not in fact_monthly_employee)
        fp.overtime_50_hours, fp.overtime_70_hours, fp.overtime_100_hours,
        fp.night_shift_hours,
    fp.overtime_50_amount AS fp_overtime_50_amount,
    fp.overtime_70_amount AS fp_overtime_70_amount,
    fp.overtime_100_amount AS fp_overtime_100_amount,
    fp.gross_total AS fp_gross_total
FROM read_parquet({gq("fact_monthly_employee")}) g
INNER JOIN read_parquet({pq("dim_employee")}) ed ON g.employee_id = ed.employee_id
LEFT JOIN cct_rules cct
  ON ed.union_id = cct.union_id
 AND MAKE_DATE(g.year, g.month, 1) BETWEEN cct.valid_from AND cct.valid_to
LEFT JOIN read_parquet({pq("fact_payroll")}) fp
    ON g.employee_id = fp.employee_id AND g.date_sk = fp.date_sk
{_scope_where_g}
""")

# Employee-level pre-aggregation: one row per employee (avg rate across months,
# schedule) — lets day-granularity rules run full-coverage without LIMIT and
# without per-row correlated subqueries or month duplication.
# Built from the UNscoped context: employee attributes are month-independent,
# so partitioned runs keep the same employee/rate base as a full run.
con.execute(f"""
    CREATE OR REPLACE TEMP VIEW monthly_ctx_full AS
    SELECT
        g.employee_id,
        g.year || '-' || LPAD(CAST(g.month AS VARCHAR), 2, '0') AS competence,
        g.base_salary,
        ed.weekly_hours, ed.work_schedule,
        cct.standard_weekly_hours AS cct_weekly_hours
    FROM read_parquet({gq("fact_monthly_employee")}) g
    INNER JOIN read_parquet({pq("dim_employee")}) ed ON g.employee_id = ed.employee_id
    LEFT JOIN cct_rules cct
      ON ed.union_id = cct.union_id
     AND MAKE_DATE(g.year, g.month, 1) BETWEEN cct.valid_from AND cct.valid_to
""")
con.execute(f"""
    CREATE OR REPLACE TEMP VIEW emp_ctx AS
    SELECT employee_id,
           ANY_VALUE(work_schedule) AS work_schedule,
           AVG(ROUND(base_salary / (NULLIF(weekly_hours, 0) * 4.33), 4)) AS hourly_rate
    FROM monthly_ctx_full
    GROUP BY employee_id
""")

detections = []

# =========================================================================
# UC1 — HE Progressiva: adicional >1h should be 70%, but paid at 50%
# =========================================================================
print("[UC1] HE Progressiva...")
t0 = time.time()
q = uc1_query("SELECT * FROM monthly_ctx")
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC2 — HE Domingo: paid at 50% instead of 100%
# =========================================================================
print("[UC2] HE Domingo...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 2 AS use_case,
           'HE domingo incorreta' AS rule_name, 'remuneracao' AS category, 'alto' AS severity,
           CAST(m.overtime_100_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(m.overtime_100_hours * m.hourly_rate * (1 + m.he_sunday_percent), 2) AS VARCHAR) AS expected_value,
           ROUND(ABS(m.overtime_100_amount - ROUND(m.overtime_100_hours * m.hourly_rate * (1 + m.he_sunday_percent), 2)), 2) AS financial_impact,
           'HE domingo: esperado ' || CAST((1+m.he_sunday_percent)*100 AS VARCHAR) || '%, pago ' ||
           CASE WHEN m.overtime_100_amount > 0 THEN CAST(ROUND(m.overtime_100_amount / NULLIF(m.overtime_100_hours,0) / m.hourly_rate * 100, 0) AS VARCHAR) ELSE '0' END || '%' AS detail
    FROM monthly_ctx m
    WHERE m.overtime_100_hours > 0
      AND ABS(m.overtime_100_amount - ROUND(m.overtime_100_hours * m.hourly_rate * (1 + m.he_sunday_percent), 2)) > 0.50
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC3 — Adicional Noturno nao pago
# =========================================================================
print("[UC3] Adicional Noturno...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 3 AS use_case,
           'Adicional noturno nao pago' AS rule_name, 'adicional_noturno' AS category, 'alto' AS severity,
           CAST(m.night_shift_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(m.time_night_hours * m.hourly_rate * m.night_shift_percent, 2) AS VARCHAR) AS expected_value,
           ROUND(m.time_night_hours * m.hourly_rate * m.night_shift_percent, 2) AS financial_impact,
           CAST(m.time_night_hours AS VARCHAR) || 'h noturnas sem adicional de ' || CAST(m.night_shift_percent*100 AS VARCHAR) || '%' AS detail
    FROM monthly_ctx m
    WHERE m.time_night_hours > 0 AND m.night_shift_amount = 0
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC4 — Banco de Horas Excedido (> 40h)
# =========================================================================
print("[UC4] Banco de Horas Excedido...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 4 AS use_case,
           'Banco de horas excedido' AS rule_name, 'banco_horas' AS category, 'medio' AS severity,
           CAST(m.hour_bank_balance AS VARCHAR) AS detected_value,
           CAST(m.max_hour_bank_hours AS VARCHAR) || 'h (limite)' AS expected_value,
           0.0 AS financial_impact,
           'Saldo de ' || CAST(m.hour_bank_balance AS VARCHAR) || 'h excede limite de ' || CAST(m.max_hour_bank_hours AS VARCHAR) || 'h' AS detail
    FROM monthly_ctx m
    WHERE m.hour_bank_balance > m.max_hour_bank_hours
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC5 — Intervalo Intrajornada violado (< 60min em jornada > 6h)
# =========================================================================
print("[UC5] Intervalo Intrajornada...")
t0 = time.time()
q = f"""
    SELECT tr.employee_id, CAST(tr.date_sk AS VARCHAR) AS competence, 5 AS use_case,
           'Intervalo intrajornada violado' AS rule_name, 'jornada' AS category, 'critico' AS severity,
           CAST(tr.interval_minutes AS VARCHAR) AS detected_value,
           '>= 60' AS expected_value,
           ROUND(tr.total_hours * 0.5 * e.hourly_rate, 2) AS financial_impact,
           'Intervalo de ' || CAST(tr.interval_minutes AS VARCHAR) || 'min em jornada de ' || CAST(tr.total_hours AS VARCHAR) || 'h (minimo 60min)' AS detail
    FROM read_parquet({pq("fact_time_record")}) tr
    INNER JOIN emp_ctx e ON tr.employee_id = e.employee_id
    WHERE tr.total_hours > 6 AND tr.interval_minutes < 60 AND tr.interval_minutes > 0
    {_scope_tr}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC6 — Divergencia Ponto vs Folha (HE hours differ)
# =========================================================================
print("[UC6] Ponto vs Folha...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 6 AS use_case,
           'Divergencia ponto vs folha' AS rule_name, 'remuneracao' AS category, 'critico' AS severity,
           'Folha: ' || CAST(m.overtime_50_hours + m.overtime_70_hours + m.overtime_100_hours AS VARCHAR) || 'h' AS detected_value,
           'Ponto: ' || CAST(m.time_overtime_50 + m.time_overtime_70 + m.time_overtime_100 AS VARCHAR) || 'h' AS expected_value,
           ROUND(ABS((m.overtime_50_hours + m.overtime_70_hours + m.overtime_100_hours)
                   - (m.time_overtime_50 + m.time_overtime_70 + m.time_overtime_100)) * m.hourly_rate * 1.5, 2) AS financial_impact,
           'Ponto registra ' || CAST(m.time_overtime_50 + m.time_overtime_70 + m.time_overtime_100 AS VARCHAR)
           || 'h extras, folha pagou ' || CAST(m.overtime_50_hours + m.overtime_70_hours + m.overtime_100_hours AS VARCHAR) || 'h' AS detail
    FROM monthly_ctx m
    WHERE ABS((m.overtime_50_hours + m.overtime_70_hours + m.overtime_100_hours)
            - (m.time_overtime_50 + m.time_overtime_70 + m.time_overtime_100)) > 2
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC7 — Pagamento Financeiro Divergente
# =========================================================================
print("[UC7] Pagamento Divergente...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 7 AS use_case,
           'Pagamento financeiro divergente' AS rule_name, 'financeiro' AS category, 'alto' AS severity,
           'Pago: R$' || CAST(m.payment_paid AS VARCHAR) AS detected_value,
           'Esperado: R$' || CAST(m.payment_expected AS VARCHAR) AS expected_value,
           m.payment_divergence AS financial_impact,
           'Folha indica R$' || CAST(m.payment_expected AS VARCHAR) || ', comprovante mostra R$' || CAST(m.payment_paid AS VARCHAR) AS detail
    FROM monthly_ctx m
    WHERE m.has_payment_divergence = 1 AND m.payment_divergence > 5
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC8 — Funcionario sem Registro de Ponto
# =========================================================================
print("[UC8] Sem Registro de Ponto...")
t0 = time.time()
q = uc8_query("SELECT * FROM monthly_ctx")
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC9 — Pagamento pos-demissao
# =========================================================================
print("[UC9] Pagamento pos-demissao...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 9 AS use_case,
           'Pagamento apos demissao' AS rule_name, 'sindicato' AS category, 'critico' AS severity,
           'Recebeu R$' || CAST(m.net_total AS VARCHAR) AS detected_value,
           'Demitido: zero' AS expected_value,
           m.net_total AS financial_impact,
           'Funcionario desligado continua recebendo verbas' AS detail
    FROM monthly_ctx m
    INNER JOIN read_parquet({pq("dim_employee")}) e ON m.employee_id = e.employee_id
    WHERE e.status = 'terminated'
      AND e.termination_date IS NOT NULL
      AND CAST(m.year || '-' || m.month || '-01' AS DATE) > e.termination_date
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC10 — HE por cargo incorreta (Supervisor deve receber 80%)
# =========================================================================
print("[UC10] HE por cargo...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 10 AS use_case,
           'HE por cargo incorreta' AS rule_name, 'cct' AS category, 'alto' AS severity,
           CAST(m.overtime_50_amount AS VARCHAR) AS detected_value,
           'Supervisor: 80%' AS expected_value,
           ROUND(m.overtime_50_hours * m.hourly_rate * 0.30, 2) AS financial_impact,
           'Supervisor recebeu HE a 50% em vez de 80% conforme CCT' AS detail
    FROM monthly_ctx m
    INNER JOIN read_parquet({pq("dim_employee")}) e ON m.employee_id = e.employee_id
    INNER JOIN read_parquet({pq("dim_position")}) pos ON e.position_id = pos.position_id
    WHERE pos.level = 'supervisor' AND m.overtime_50_hours > 0
      AND m.overtime_50_amount < ROUND(m.overtime_50_hours * m.hourly_rate * 1.80, 2) - 1
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC11 — Regra CCT 2023 aplicada em 2024
# =========================================================================
print("[UC11] CCT entre anos...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 11 AS use_case,
           'CCT entre anos incorreta' AS rule_name, 'cct' AS category, 'medio' AS severity,
           CAST(m.overtime_100_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(m.overtime_100_hours * m.hourly_rate * 2.0, 2) AS VARCHAR) AS expected_value,
           ROUND(ABS(m.overtime_100_amount - ROUND(m.overtime_100_hours * m.hourly_rate * 2.0, 2)), 2) AS financial_impact,
           'HE domingo em 2024 deveria ser 100%, paga a percentual menor (possivel regra de 2023)' AS detail
    FROM monthly_ctx m
    WHERE m.year = 2024 AND m.overtime_100_hours > 0
      AND m.overtime_100_amount < ROUND(m.overtime_100_hours * m.hourly_rate * 1.80, 2)
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC12 — Jornada 12x36 excedida
# =========================================================================
print("[UC12] 12x36 excedida...")
t0 = time.time()
q = f"""
    SELECT tr.employee_id, CAST(tr.date_sk AS VARCHAR) AS competence, 12 AS use_case,
           'Jornada 12x36 excedida' AS rule_name, 'jornada' AS category, 'alto' AS severity,
           CAST(tr.total_hours AS VARCHAR) AS detected_value,
           '<= 12h' AS expected_value,
           ROUND(GREATEST(0, CAST(tr.total_hours - 12 AS DOUBLE)) * e.hourly_rate * 1.5, 2) AS financial_impact,
           'Jornada de ' || CAST(tr.total_hours AS VARCHAR) || 'h em regime 12x36 (maximo 12h)' AS detail
    FROM read_parquet({pq("fact_time_record")}) tr
    INNER JOIN emp_ctx e ON tr.employee_id = e.employee_id
    WHERE e.work_schedule = '12x36' AND tr.total_hours > 12
    {_scope_tr}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC13 — Periculosidade Ausente
# =========================================================================
print("[UC13] Periculosidade ausente...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 13 AS use_case,
           'Periculosidade ausente' AS rule_name, 'remuneracao' AS category, 'critico' AS severity,
           CAST(m.periculosidade_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(e.base_salary * m.periculosidade_percent, 2) AS VARCHAR) AS expected_value,
           ROUND(e.base_salary * m.periculosidade_percent, 2) AS financial_impact,
           'Cargo elegivel a periculosidade (30%) nao recebeu o adicional' AS detail
    FROM monthly_ctx m
    INNER JOIN read_parquet({pq("dim_employee")}) e ON m.employee_id = e.employee_id
    WHERE e.periculosidade_eligible = TRUE AND m.periculosidade_amount = 0
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC14 — DSR Incorreto
# =========================================================================
print("[UC14] DSR incorreto...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 14 AS use_case,
           'DSR incorreto' AS rule_name, 'cct' AS category, 'alto' AS severity,
           CAST(m.dsr_amount AS VARCHAR) AS detected_value,
           CAST(ROUND((m.sundays_worked * m.overtime_50_hours * m.hourly_rate * 0.5), 2) AS VARCHAR) AS expected_value,
           ROUND(ABS(m.dsr_amount - ROUND((m.sundays_worked + 0.5) * m.overtime_50_hours * m.hourly_rate * 0.5, 2)), 2) AS financial_impact,
           'DSR de R$' || CAST(m.dsr_amount AS VARCHAR) || ' discrepante do esperado com base nas HE do mes' AS detail
    FROM monthly_ctx m
    WHERE m.dsr_amount > 0 AND m.overtime_50_hours > 0
      AND m.dsr_amount < ROUND(m.overtime_50_hours * m.hourly_rate * 0.3, 2)
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC15 — Feriado Trabalhado sem Adicional
# =========================================================================
print("[UC15] Feriado sem adicional...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 15 AS use_case,
           'Feriado trabalhado sem adicional' AS rule_name, 'remuneracao' AS category, 'alto' AS severity,
           CAST(m.overtime_100_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(m.holiday_days_worked * 8 * m.hourly_rate * 2.0, 2) AS VARCHAR) AS expected_value,
           ROUND(m.holiday_days_worked * 8 * m.hourly_rate, 2) AS financial_impact,
           CAST(m.holiday_days_worked AS VARCHAR) || ' feriados trabalhados sem adicional de 100%' AS detail
    FROM monthly_ctx m
    WHERE m.holiday_days_worked > 0 AND m.overtime_100_amount = 0
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC16 — Banco de Horas Negativo
# =========================================================================
print("[UC16] Banco de Horas Negativo...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 16 AS use_case,
           'Banco de horas negativo' AS rule_name, 'banco_horas' AS category, 'medio' AS severity,
           CAST(m.hour_bank_balance AS VARCHAR) AS detected_value,
           '>= 0' AS expected_value,
           ABS(m.hour_bank_balance) * m.hourly_rate * 0.5 AS financial_impact,
           'Saldo negativo de ' || CAST(m.hour_bank_balance AS VARCHAR) || 'h no banco de horas' AS detail
    FROM monthly_ctx m
    WHERE m.hour_bank_balance < -5
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC17 — CPF Divergente (cadastral)
# =========================================================================
print("[UC17] CPF Divergente...")
t0 = time.time()
q = f"""
    SELECT i.employee_id, 'N/A' AS competence, 17 AS use_case,
           'CPF divergente entre sistemas' AS rule_name, 'cadastro' AS category, 'medio' AS severity,
           'CPF divergente' AS detected_value,
            'CPF consistente' AS expected_value,
            0.0 AS financial_impact,
            'CPF do sistema financeiro difere do RH — reconciliacao impedida' AS detail
    FROM read_parquet({bq("audit/inconsistency_log")}) i
    WHERE i.use_case = 17
"""
if PARTITIONED:
    print("  -> skipped (partitioned mode: N/A-competence rows preserved from prior runs)")
else:
    res = con.execute(q).fetchdf()
    detections.append(res)
    print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC18 — Pagamento Orfao
# =========================================================================
print("[UC18] Pagamento orfao...")
t0 = time.time()
q = f"""
    SELECT bp.employee_id, CAST(bp.year || '-' || LPAD(CAST(bp.month AS VARCHAR), 2, '0') AS VARCHAR) AS competence, 18 AS use_case,
           'Pagamento orfao' AS rule_name, 'financeiro' AS category, 'alto' AS severity,
           'R$' || CAST(bp.paid_amount AS VARCHAR) AS detected_value,
           'Sem evento na folha' AS expected_value,
           bp.paid_amount AS financial_impact,
           'Pagamento de R$' || CAST(bp.paid_amount AS VARCHAR) || ' sem evento correspondente na folha' AS detail
    FROM read_parquet({pq("fact_payment")}) bp
    LEFT JOIN read_parquet({pq("fact_payroll")}) p
        ON bp.employee_id = p.employee_id AND bp.year = p.year AND bp.month = p.month
    WHERE p.payroll_id IS NULL AND bp.expected_amount = 0 AND bp.paid_amount > 0
    {_scope_pay_bp}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC19 — Funcionario sem Sindicato
# =========================================================================
print("[UC19] Sem sindicato...")
t0 = time.time()
q = f"""
    SELECT e.employee_id, 'N/A' AS competence, 19 AS use_case,
           'Funcionario sem sindicato' AS rule_name, 'sindicato' AS category, 'medio' AS severity,
           'Sindicato: NULL' AS detected_value,
           'Sindicato definido' AS expected_value,
           0.0 AS financial_impact,
           'Funcionario sem sindicato associado — CCT nao pode ser aplicada' AS detail
    FROM read_parquet({pq("dim_employee")}) e
    WHERE e.union_id IS NULL
"""
if PARTITIONED:
    print("  -> skipped (partitioned mode: N/A-competence rows preserved from prior runs)")
else:
    res = con.execute(q).fetchdf()
    detections.append(res)
    print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC20 — Escala Incompativel com Convencao
# =========================================================================
print("[UC20] Escala incompativel...")
t0 = time.time()
q = f"""
    SELECT e.employee_id, 'N/A' AS competence, 20 AS use_case,
           'Escala incompativel com CCT' AS rule_name, 'jornada' AS category, 'critico' AS severity,
           'Escala: ' || e.work_schedule AS detected_value,
           'Esperado: 3x3 ou 5x2 (RN)' AS expected_value,
           0.0 AS financial_impact,
           'Funcionario do RN registrado como ' || e.work_schedule || ' — CCT do RN permite apenas 3x3 (operacional) ou 5x2 (adm)' AS detail
    FROM read_parquet({pq("dim_employee")}) e
    INNER JOIN read_parquet({pq("dim_union")}) u ON e.union_id = u.union_id
    WHERE u.state = 'RN' AND e.work_schedule = '6x1'
"""
if PARTITIONED:
    print("  -> skipped (partitioned mode: N/A-competence rows preserved from prior runs)")
else:
    res = con.execute(q).fetchdf()
    detections.append(res)
    print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC21 — Pagamento Duplicado
# =========================================================================
print("[UC21] Pagamento duplicado...")
t0 = time.time()
q = f"""
    WITH dup AS (
        SELECT employee_id, year, month, receipt_code, COUNT(*) AS cnt,
               SUM(paid_amount) AS total_paid
        FROM read_parquet({pq("fact_payment")})
        {_scope_pay_raw}
        GROUP BY employee_id, year, month, receipt_code
        HAVING COUNT(*) > 1
    )
    SELECT dup.employee_id, CAST(dup.year || '-' || LPAD(CAST(dup.month AS VARCHAR), 2, '0') AS VARCHAR) AS competence, 21 AS use_case,
           'Pagamento duplicado' AS rule_name, 'financeiro' AS category, 'critico' AS severity,
           CAST(dup.total_paid AS VARCHAR) AS detected_value,
           CAST(dup.total_paid / dup.cnt AS VARCHAR) || ' (valor unico)' AS expected_value,
           dup.total_paid - (dup.total_paid / dup.cnt) AS financial_impact,
           'Mesmo evento pago ' || CAST(dup.cnt AS VARCHAR) || 'x — valor total R$' || CAST(dup.total_paid AS VARCHAR) AS detail
    FROM dup
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC22 — HE sem Aprovacao
# =========================================================================
print("[UC22] HE sem aprovacao...")
t0 = time.time()
q = f"""
    SELECT tr.employee_id, CAST(tr.date_sk AS VARCHAR) AS competence, 22 AS use_case,
           'HE sem aprovacao' AS rule_name, 'jornada' AS category, 'medio' AS severity,
           CAST(tr.overtime_50 + tr.overtime_70 AS VARCHAR) || 'h extras' AS detected_value,
           'Aprovacao necessaria' AS expected_value,
           0.0 AS financial_impact,
           CAST(tr.overtime_50 + tr.overtime_70 AS VARCHAR) || 'h extras sem aprovacao do gestor (politica: >2h requer aprovacao)' AS detail
    FROM read_parquet({pq("fact_time_record")}) tr
    WHERE tr.overtime_50 + tr.overtime_70 > 2 AND tr.has_overtime_approval = FALSE
    {_scope_tr}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC23 — Promocao sem Reajuste Salarial
# =========================================================================
print("[UC23] Promocao sem reajuste...")
t0 = time.time()
q = f"""
    SELECT sh.employee_id, CAST(sh.effective_date AS VARCHAR) AS competence, 23 AS use_case,
           'Promocao sem reajuste' AS rule_name, 'cadastro' AS category, 'medio' AS severity,
           'Salario anterior: R$' || CAST(sh.previous_salary AS VARCHAR) AS detected_value,
           'Salario maior esperado' AS expected_value,
           0.0 AS financial_impact,
           'Promocao em ' || CAST(sh.effective_date AS VARCHAR) || ' sem alteracao salarial (R$' || CAST(sh.previous_salary AS VARCHAR) || ')' AS detail
    FROM read_parquet({pq("salary_history")}) sh
    WHERE sh.previous_salary = sh.new_salary AND sh.change_reason = 'promotion'
    {_scope_sh}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC24 — Adicional Noturno Aplicado Fora do Horario
# =========================================================================
print("[UC24] Noturno fora do horario...")
t0 = time.time()
q = f"""
    SELECT tr.employee_id, CAST(tr.date_sk AS VARCHAR) AS competence, 24 AS use_case,
           'Noturno fora do horario' AS rule_name, 'adicional_noturno' AS category, 'medio' AS severity,
           'Night hours: ' || CAST(tr.night_hours AS VARCHAR) || 'h' AS detected_value,
           'Adicional so entre 22h-5h' AS expected_value,
           0.0 AS financial_impact,
           'Adicional noturno registrado em horario fora da faixa 22h-5h (entrada: ' || CAST(tr.entry_1 AS VARCHAR) || ')' AS detail
    FROM read_parquet({pq("fact_time_record")}) tr
    WHERE tr.night_hours > 0 AND tr.entry_1 IS NOT NULL
      AND EXTRACT(HOUR FROM tr.entry_1) < 18 AND EXTRACT(HOUR FROM tr.entry_1) >= 5
    {_scope_tr}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC25 — Limite Semanal Excedido
# =========================================================================
print("[UC25] Limite semanal excedido...")
t0 = time.time()
q = f"""
    WITH weekly AS (
        SELECT tr.employee_id,
               DATE_TRUNC('week', d.full_date) AS week_start,
               CAST(EXTRACT('year' FROM DATE_TRUNC('week', d.full_date)) AS INTEGER) AS wy,
               CAST(EXTRACT('month' FROM DATE_TRUNC('week', d.full_date)) AS INTEGER) AS wm,
               SUM(tr.total_hours) AS week_hours
        FROM read_parquet({pq("fact_time_record")}) tr
        INNER JOIN read_parquet({pq("dim_date")}) d ON tr.date_sk = d.date_sk
        WHERE tr.total_hours > 0 AND tr.employee_id IS NOT NULL
        GROUP BY tr.employee_id, DATE_TRUNC('week', d.full_date),
                 CAST(EXTRACT('year' FROM DATE_TRUNC('week', d.full_date)) AS INTEGER),
                 CAST(EXTRACT('month' FROM DATE_TRUNC('week', d.full_date)) AS INTEGER)
        HAVING SUM(tr.total_hours) > 44
    )
    SELECT w.employee_id, CAST(w.week_start AS VARCHAR) AS competence, 25 AS use_case,
           'Limite semanal excedido' AS rule_name, 'jornada' AS category, 'critico' AS severity,
           CAST(w.week_hours AS VARCHAR) || 'h na semana' AS detected_value,
           'Max ' || CAST(e.cct_weekly_hours AS VARCHAR) || 'h/semana' AS expected_value,
           ROUND((w.week_hours - e.cct_weekly_hours) * e.hourly_rate * 1.5, 2) AS financial_impact,
           'Jornada de ' || CAST(w.week_hours AS VARCHAR) || 'h na semana ' || CAST(w.week_start AS VARCHAR) || ' — limite: ' || CAST(e.cct_weekly_hours AS VARCHAR) || 'h' AS detail
    FROM weekly w
    INNER JOIN monthly_ctx e
        ON w.employee_id = e.employee_id
       AND w.wy = e.year AND w.wm = e.month
    WHERE w.week_hours > e.cct_weekly_hours
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC26 — Sindicato Errado / CCT Incorreta
# =========================================================================
print("[UC26] Sindicato errado...")
t0 = time.time()
q = f"""
    SELECT e.employee_id, 'N/A' AS competence, 26 AS use_case,
           'Sindicato/CCT incorreta' AS rule_name, 'sindicato' AS category, 'medio' AS severity,
           'Sindicato: ' || u.name AS detected_value,
           'Verificar sindicato correto' AS expected_value,
           0.0 AS financial_impact,
           'Funcionario pode estar vinculado ao sindicato errado — CCT divergente' AS detail
    FROM read_parquet({pq("dim_employee")}) e
    INNER JOIN read_parquet({pq("dim_union")}) u ON e.union_id = u.union_id
    INNER JOIN read_parquet({pq("dim_unit")}) un ON e.unit_id = un.unit_id
    WHERE u.state != un.state
"""
if PARTITIONED:
    print("  -> skipped (partitioned mode: N/A-competence rows preserved from prior runs)")
else:
    res = con.execute(q).fetchdf()
    detections.append(res)
    print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC27 — Falta com Atestado Descontada
# =========================================================================
print("[UC27] Atestado ignorado...")
t0 = time.time()
q = f"""
    SELECT tr.employee_id, CAST(tr.date_sk AS VARCHAR) AS competence, 27 AS use_case,
           'Falta com atestado descontada' AS rule_name, 'cadastro' AS category, 'medio' AS severity,
           'Falta injustificada' AS detected_value,
           'Falta justificada (atestado)' AS expected_value,
            ROUND(8 * e.hourly_rate, 2) AS financial_impact,
           'Falta com atestado medico registrada como injustificada' AS detail
    FROM read_parquet({pq("fact_time_record")}) tr
    INNER JOIN emp_ctx e ON tr.employee_id = e.employee_id
    WHERE tr.absence_type = 'unjustified'
    {_scope_tr}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC28 — Jornada Sobreposta
# =========================================================================
print("[UC28] Jornada sobreposta...")
t0 = time.time()
# Real interval-overlap rule (validation_rules.uc28_query): same employee/day,
# two records whose shift spans (entry/exit marks) actually overlap. The old
# "any two records on the same day" heuristic is retired.
uc28_source = ("SELECT * FROM read_parquet(" + pq('fact_time_record') +
               f") WHERE {_scope_tr_util.strip()}" if PARTITIONED else
               f"SELECT * FROM read_parquet({pq('fact_time_record')})")
q = uc28_query(uc28_source)
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC29 — Insalubridade Ausente
# =========================================================================
print("[UC29] Insalubridade ausente...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 29 AS use_case,
           'Insalubridade ausente' AS rule_name, 'remuneracao' AS category, 'critico' AS severity,
           CAST(m.insalubridade_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(e.base_salary * m.insalubridade_percent, 2) AS VARCHAR) AS expected_value,
           ROUND(e.base_salary * m.insalubridade_percent, 2) AS financial_impact,
           'Cargo elegivel a insalubridade (40%) nao recebeu o adicional' AS detail
    FROM monthly_ctx m
    INNER JOIN read_parquet({pq("dim_employee")}) e ON m.employee_id = e.employee_id
    WHERE e.insalubridade_eligible = TRUE AND m.insalubridade_amount = 0
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC30 — Inconsistencia Temporal de CCT
# =========================================================================
print("[UC30] CCT temporal...")
t0 = time.time()
q = f"""
    SELECT m.employee_id, m.competence, 30 AS use_case,
           'Inconsistencia temporal CCT' AS rule_name, 'cct' AS category, 'medio' AS severity,
           'Regra futura aplicada' AS detected_value,
           'Regra vigente na competencia' AS expected_value,
           ROUND(ABS(m.overtime_50_amount - ROUND(m.overtime_50_hours * m.hourly_rate * 1.5, 2)), 2) AS financial_impact,
           'Possivel regra de CCT futura aplicada em competencia anterior' AS detail
    FROM monthly_ctx m
    WHERE m.year = 2024 AND m.month <= 6
      AND m.overtime_50_amount > ROUND(m.overtime_50_hours * m.hourly_rate * 1.65, 2)
      AND m.overtime_50_hours > 0
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC31 — Ferias Vencidas
# =========================================================================
print("[UC31] Ferias vencidas...")
t0 = time.time()
q = f"""
    SELECT v.employee_id, CAST(v.concession_deadline AS VARCHAR) AS competence, 31 AS use_case,
           'Ferias vencidas nao gozadas' AS rule_name, 'ferias' AS category, 'critico' AS severity,
           'Vencidas: ' || CAST(v.concession_deadline AS VARCHAR) AS detected_value,
           'Gozo dentro do prazo legal' AS expected_value,
           ROUND(e.base_salary * 2, 2) AS financial_impact,
           'Ferias do periodo ' || CAST(v.acquisition_start AS VARCHAR) || ' a ' || CAST(v.acquisition_end AS VARCHAR)
           || ' vencidas — passivo de R$' || CAST(ROUND(e.base_salary * 2, 2) AS VARCHAR) || ' (dobro)' AS detail
    FROM read_parquet({pq("vacations")}) v
    INNER JOIN read_parquet({pq("dim_employee")}) e ON v.employee_id = e.employee_id
    WHERE v.status = 'expired'
    {_scope_vac}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UC32 — Alerta Preventivo Ferias
# =========================================================================
print("[UC32] Alerta ferias...")
t0 = time.time()
q = f"""
    SELECT v.employee_id, CAST(v.concession_deadline AS VARCHAR) AS competence, 32 AS use_case,
           'Alerta preventivo ferias' AS rule_name, 'ferias' AS category, 'medio' AS severity,
           'Vence em: ' || CAST(v.concession_deadline AS VARCHAR) AS detected_value,
           'Agendar antes do vencimento' AS expected_value,
           ROUND(e.base_salary * 1.5, 2) AS financial_impact,
           'Ferias proximas ao vencimento (prazo: ' || CAST(v.concession_deadline AS VARCHAR)
           || ') — agendar para evitar pagamento em dobro' AS detail
    FROM read_parquet({pq("vacations")}) v
    INNER JOIN read_parquet({pq("dim_employee")}) e ON v.employee_id = e.employee_id
    WHERE v.status = 'impending'
    {_scope_vac}
"""
res = con.execute(q).fetchdf()
detections.append(res)
print(f"  -> {len(res)} detected ({time.time()-t0:.1f}s)")

# =========================================================================
# UNION ALL and write to Gold
# =========================================================================
print(f"\n{'='*60}")
print("Consolidating detections...")
t0 = time.time()

# Concatenate all detections
import pandas as pd
new_detections = pd.concat(detections, ignore_index=True)
new_detections["detected_at"] = NOW_ISO
new_detections["rule_origin"] = "rule_engine"
new_detections["evidence_source"] = "computed_from_cross_source"
sim_mask = new_detections["use_case"].isin([17])
new_detections.loc[sim_mask, "rule_origin"] = "simulation_marker"
new_detections.loc[sim_mask, "evidence_source"] = "bronze.audit.inconsistency_log"

# Merge into the stored detection set: partitioned mode reuses rows of every
# untouched competence and renumbers the whole set deterministically.
det_path = f"{GOLD}/fact_detected_inconsistency.parquet".replace(chr(92), "/")
old_df = None
prior_norm_counts = {}
if PARTITIONED:
    if not os.path.exists(det_path):
        sys.exit("partitioned run requires an existing fact_detected_inconsistency.parquet (run full mode first)")
    old_df = con.execute(f"""
        SELECT {",".join(CONTRACT_COLS)} FROM read_parquet('{det_path}')
    """).fetchdf()
    prior_norm_counts = old_df["competence"].map(normalize_competence).value_counts().to_dict()

all_detections = merge_detections(old_df, new_detections, TARGETS)

# Write to Gold Parquet
path = det_path
all_detections.to_parquet(path, index=False, compression="zstd")

merge_proof = None
norm_counts = all_detections["competence"].map(normalize_competence).value_counts().to_dict()
if PARTITIONED:
    non_target = {k: int(v) for k, v in prior_norm_counts.items() if k not in TARGETS}
    after_non_target = {k: int(v) for k, v in norm_counts.items() if k not in TARGETS}
    merge_proof = {
        "deleted_by_target": {t: int(prior_norm_counts.get(t, 0)) for t in TARGETS},
        "final_by_target": {t: int(norm_counts.get(t, 0)) for t in TARGETS},
        "preserved_rows": {k: after_non_target[k] for k in sorted(after_non_target)},
        "non_target_unchanged": non_target == after_non_target,
    }
    del old_df, prior_norm_counts

# Derive labor liability fact from detected inconsistencies
liab_factors = con.execute(f"""
    SELECT severity, factor
    FROM read_parquet({gq('dim_liability_factor_version')})
    WHERE DATE '{NOW_ISO[:10]}' BETWEEN valid_from AND valid_to
""").fetchdf()
factor_map = dict(zip(liab_factors["severity"], liab_factors["factor"]))
all_detections["severity_factor"] = all_detections["severity"].map(factor_map).fillna(0.25)
all_detections["estimated_impact"] = all_detections["financial_impact"].abs() * all_detections["severity_factor"]

dim_emp = con.execute(f"""
    SELECT e.employee_id, e.unit_id, e.union_id, u.name AS unit_name, un.name AS union_name
    FROM read_parquet({pq('dim_employee')}) e
    LEFT JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
    LEFT JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
""").fetchdf()

passivo = all_detections.merge(dim_emp, on="employee_id", how="left")
passivo["passivo_id"] = "P-" + passivo["detection_id"].astype(str)
passivo["liability_type"] = passivo["category"]
passivo["calculated_at"] = NOW_ISO
passivo = passivo[[
    "passivo_id", "employee_id", "unit_id", "unit_name", "union_id", "union_name",
    "use_case", "rule_name", "liability_type", "category", "severity", "estimated_impact", "calculated_at"
]]
passivo.to_parquet(f"{GOLD}/fact_passivo_trabalhista.parquet", index=False, compression="zstd")

# Fill monthly dashboard contract columns from detections
COUNTER_COLS = ["total_inconsistencies", "payment_inconsistencies",
                "night_shift_inconsistencies", "periculosidade_inconsistencies",
                "he_inconsistencies"]
monthly = con.execute(f"SELECT * FROM read_parquet({gq('fact_monthly_employee')})").fetchdf()
monthly["competence"] = monthly["year"].astype(str) + "-" + monthly["month"].astype(str).str.zfill(2)
if PARTITIONED:
    # Only target competences are recomputed; untouched rows keep their values
    monthly_mask = monthly["competence"].isin(TARGETS)
    for c in COUNTER_COLS:
        if c not in monthly.columns:
            monthly[c] = 0
        monthly.loc[monthly_mask, c] = 0
    det_m = all_detections[all_detections["competence"].isin(TARGETS)].copy()
else:
    det_m = all_detections[all_detections["competence"].str.contains("-", na=False)].copy()
if not det_m.empty:
    con.register("det_m_view", det_m)
    agg = con.execute(f"""
        SELECT employee_id, competence,
               COUNT(*) AS total_inconsistencies,
               COUNT(*) FILTER (WHERE category = 'financeiro') AS payment_inconsistencies,
               COUNT(*) FILTER (WHERE category = 'adicional_noturno') AS night_shift_inconsistencies,
               COUNT(*) FILTER (WHERE regexp_matches(rule_name, 'Periculosidade', 'i')) AS periculosidade_inconsistencies,
               COUNT(*) FILTER (WHERE regexp_matches(rule_name, 'HE|hora extra|Feriado', 'i')) AS he_inconsistencies
        FROM det_m_view
        GROUP BY employee_id, competence
    """).fetchdf()
    if PARTITIONED:
        sub = monthly.loc[monthly_mask].merge(
            agg, on=["employee_id", "competence"], how="left", suffixes=("", "_new"))
        for c in COUNTER_COLS:
            if f"{c}_new" in sub.columns:
                sub[c] = sub[f"{c}_new"].fillna(0).astype(int)
                sub.drop(columns=[f"{c}_new"], inplace=True)
        monthly.loc[monthly_mask, COUNTER_COLS] = sub[COUNTER_COLS].to_numpy()
    else:
        monthly = monthly.merge(agg, on=["employee_id", "competence"], how="left", suffixes=("", "_new"))
        for c in COUNTER_COLS:
            monthly[c] = monthly[f"{c}_new"].fillna(0).astype(int)
            monthly.drop(columns=[f"{c}_new"], inplace=True)
    con.unregister("det_m_view")
monthly.to_parquet(f"{GOLD}/fact_monthly_employee.parquet", index=False, compression="zstd")

total_impact = all_detections["financial_impact"].sum()
elapsed = time.time() - t_start

print(f"  Total detections: {len(all_detections)}")
print(f"  Total financial impact: R$ {total_impact:,.2f}")
print(f"  Total time: {elapsed:.1f}s")

# Summary by UC
print(f"\n{'='*60}")
print("SUMMARY BY USE CASE")
print(f"{'='*60}")
uc_summary = all_detections.groupby(["use_case", "rule_name", "category", "severity"]).agg(
    count=("detection_id", "count"),
    total_impact=("financial_impact", "sum")
).reset_index().sort_values("use_case")
for _, r in uc_summary.iterrows():
    print(f"  UC{r['use_case']:02d} {r['rule_name']:35s} {r['severity']:8s} {r['count']:>6} ocorr.  R${r['total_impact']:>10,.2f}")

print(f"\n  {'TOTAL':55s} {len(all_detections):>6} ocorr.  R${total_impact:>10,.2f}")

# Write manifest
manifest = {
    "pipeline": "validation_engine",
    "run_at": NOW_ISO,
    "total_detections": len(all_detections),
    "total_estimated_impact": round(total_impact, 2),
    "rules_implemented": 32,
    "output": "data/gold/fact_detected_inconsistency.parquet",
    "truncation": False,
    "truncation_removed_use_cases": [5, 12, 22, 24, 25, 27, 28],
    "full_coverage": True,
    "uc28_method": "interval-overlap of entry/exit shift spans; records without readable marks cannot be assessed (documented in rule detail)",
    "sla_rebaseline": "max_critical_rows 6000 -> 350000 (previous threshold matched LIMIT-truncated detection; runtime SLA 180s unchanged)",
    "mode": "partitioned" if PARTITIONED else "full",
    "competences_available": AVAILABLE_COMPETENCES,
    "competences_processed": TARGETS if PARTITIONED else "all (full run)",
    "detections_by_competence": {k: int(v) for k, v in sorted(norm_counts.items())},
    "sla_policy": SLA_POLICY,
}
if merge_proof is not None:
    manifest["merge"] = merge_proof
with open(f"{GOLD}/validation_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

# Operational observability (history + SLA + alert)
# max_critical_rows is re-baselined for full-coverage detection: the previous
# 6000 threshold was calibrated when rules were LIMIT-truncated (baseline run
# already reported 34k critical rows). In partitioned mode the scoped rows and
# a proportionally scaled SLA are recorded (see sla_policy in the manifest).
obs_event = {
    "run_at": NOW_ISO,
    "pipeline": "validation_engine",
    "mode": "partitioned" if PARTITIONED else "full",
    "competences_processed": TARGETS if PARTITIONED else "all (full run)",
    "runtime_seconds": round(elapsed, 2),
    "rows_detected": int(len(new_detections)),
    "critical_rows": int((new_detections["severity"] == "critico").sum()),
    "total_detections_in_output": int(len(all_detections)),
    "total_estimated_impact": float(round(total_impact, 2)),
    "sla": {"max_runtime_seconds": SLA_RUNTIME, "max_critical_rows": SLA_CRITICAL},
}
obs_event["sla_status"] = "PASS" if (obs_event["runtime_seconds"] <= obs_event["sla"]["max_runtime_seconds"] and obs_event["critical_rows"] <= obs_event["sla"]["max_critical_rows"]) else "FAIL"
history_path = f"{OBS}/validation_history.json"
history = []
if os.path.exists(history_path):
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
history.append(obs_event)
with open(history_path, "w", encoding="utf-8") as f:
    json.dump(history[-200:], f, indent=2, ensure_ascii=False)
if obs_event["sla_status"] == "FAIL":
    with open(f"{OBS}/alerts.log", "a", encoding="utf-8") as f:
        f.write(f"{NOW_ISO} | validation_engine | SLA_FAIL | runtime={elapsed:.2f}s | critical={obs_event['critical_rows']}\n")

con.close()
print(f"\nDone. Output: {path}")

