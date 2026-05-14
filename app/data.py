import duckdb
import pandas as pd
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
SILVER = ROOT / "data" / "silver"
GOLD = ROOT / "data" / "gold"
BRONZE = ROOT / "data" / "bronze"

_con = None
_GLOBAL_FILTERS = {"start_date": None, "end_date": None, "estado": None, "unidade": None, "sindicato": None}


def set_global_filters(filters: dict | None):
    global _GLOBAL_FILTERS
    if not filters:
        _GLOBAL_FILTERS = {"start_date": None, "end_date": None, "estado": None, "unidade": None, "sindicato": None}
        return
    _GLOBAL_FILTERS = {
        "start_date": filters.get("start_date"),
        "end_date": filters.get("end_date"),
        "estado": filters.get("estado"),
        "unidade": filters.get("unidade"),
        "sindicato": filters.get("sindicato"),
    }


def is_demo_mode() -> bool:
    return os.environ.get("HRA_DEMO_MODE", "false").lower() == "true"


def _filters_employee(alias="e", unit_alias="u", union_alias="un"):
    conds = []
    if _GLOBAL_FILTERS.get("estado"):
        conds.append(f"{unit_alias}.state = '{_GLOBAL_FILTERS['estado']}'")
    if _GLOBAL_FILTERS.get("unidade"):
        conds.append(f"{unit_alias}.name = '{_GLOBAL_FILTERS['unidade']}'")
    if _GLOBAL_FILTERS.get("sindicato"):
        conds.append(f"{union_alias}.name = '{_GLOBAL_FILTERS['sindicato']}'")
    return ("WHERE " + " AND ".join(conds)) if conds else ""


def _filters_competence(alias="m"):
    conds = []
    if _GLOBAL_FILTERS.get("start_date"):
        conds.append(f"MAKE_DATE({alias}.year, {alias}.month, 1) >= DATE '{_GLOBAL_FILTERS['start_date']}'")
    if _GLOBAL_FILTERS.get("end_date"):
        conds.append(f"MAKE_DATE({alias}.year, {alias}.month, 1) <= DATE '{_GLOBAL_FILTERS['end_date']}'")
    return (" AND " + " AND ".join(conds)) if conds else ""


def _filters_where_unit(alias="u"):
    conds = []
    if _GLOBAL_FILTERS.get("estado"):
        conds.append(f"{alias}.state = '{_GLOBAL_FILTERS['estado']}'")
    if _GLOBAL_FILTERS.get("unidade"):
        conds.append(f"{alias}.name = '{_GLOBAL_FILTERS['unidade']}'")
    return ("WHERE " + " AND ".join(conds)) if conds else ""

def get_con():
    global _con
    if _con is None:
        _con = duckdb.connect()
    return _con

def pq(path): return ("'" + str((SILVER / f"{path}.parquet").as_posix()) + "'").replace("//", "/")
def gq(path): return ("'" + str((GOLD / f"{path}.parquet").as_posix()) + "'").replace("//", "/")

def query(sql: str) -> pd.DataFrame:
    return get_con().execute(sql).fetchdf()

# ---------------------------------------------------------------------------
# Estratégico
# ---------------------------------------------------------------------------
def kpi_ferias_vencidas():
    return query(f"""
        SELECT count(*) AS total,
               SUM(CASE WHEN v.status IN ('expired','impending') THEN 1 ELSE 0 END) AS vencidas
        FROM read_parquet({pq('vacations')}) v
        JOIN read_parquet({pq('dim_employee')}) e USING(employee_id)
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e','u','un')}
    """)

def kpi_passivo_ferias():
    return query(f"""
        SELECT ROUND(SUM(CASE WHEN v.status='expired' THEN e.base_salary*2
                              WHEN v.status='impending' THEN e.base_salary*1.5 ELSE 0 END),0) AS passivo_total
        FROM read_parquet({pq('vacations')}) v
        JOIN read_parquet({pq('dim_employee')}) e ON v.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e','u','un')}
    """)

def kpi_proximos_vencimento():
    return query(f"""
        SELECT count(*) AS qtd,
               SUM(CASE WHEN v.concession_deadline - current_date <= 30 THEN 1 ELSE 0 END) AS critico,
               SUM(CASE WHEN v.concession_deadline - current_date BETWEEN 31 AND 60 THEN 1 ELSE 0 END) AS atencao
        FROM read_parquet({pq('vacations')}) v
        JOIN read_parquet({pq('dim_employee')}) e USING(employee_id)
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE v.status IN ('pending','impending') AND v.concession_deadline >= current_date
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
    """)

def evolucao_risco():
    return query(f"""
        SELECT m.year, m.month,
               m.year || '-' || LPAD(CAST(m.month AS VARCHAR),2,'0') AS competencia,
               count(DISTINCT f.employee_id) AS funcionarios_afetados,
               ROUND(SUM(f.financial_impact),0) AS impacto_total
        FROM read_parquet({gq('fact_detected_inconsistency')}) f
        JOIN read_parquet({gq('fact_monthly_employee')}) m
          ON f.employee_id = m.employee_id AND f.competence = m.competence
        JOIN read_parquet({pq('dim_employee')}) e ON m.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE TRY_CAST(SPLIT_PART(f.competence,'-',2) AS INT) IS NOT NULL
          AND m.year>=2024
          {_filters_competence('m')}
        GROUP BY m.year,m.month ORDER BY m.year,m.month
    """)

def passivo_por_unidade():
    return query(f"""
        SELECT u.name AS unidade, u.state AS estado,
               ROUND(SUM(f.estimated_impact),0) AS passivo
        FROM read_parquet({gq('fact_passivo_trabalhista')}) f
        JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id=e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id=un.union_id
        WHERE 1=1
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY u.name,u.state ORDER BY passivo DESC LIMIT 5
    """)

# ---------------------------------------------------------------------------
# Analítico
# ---------------------------------------------------------------------------
def distribuicao_estado():
    return query(f"""
        WITH estado_base AS (
            SELECT u.state AS estado, count(*) AS funcionarios
            FROM read_parquet({pq('dim_employee')}) e
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
            GROUP BY u.state
        ),
        estado_passivo AS (
            SELECT u.state AS estado,
                   ROUND(SUM(COALESCE(f.estimated_impact,0)),0) AS passivo
            FROM read_parquet({gq('fact_passivo_trabalhista')}) f
            JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id=e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
            GROUP BY u.state
        ),
        estado_vencidas AS (
            SELECT u.state AS estado,
                   ROUND(SUM(CASE WHEN v.status IN ('expired','impending') THEN 1 ELSE 0 END)*100.0/
                         NULLIF(count(*),0), 1) AS pct_vencidas
            FROM read_parquet({pq('vacations')}) v
            JOIN read_parquet({pq('dim_employee')}) e ON v.employee_id=e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
            GROUP BY u.state
        )
        SELECT eb.estado, eb.funcionarios,
               COALESCE(ev.pct_vencidas,0) AS pct_vencidas,
               COALESCE(ep.passivo,0) AS passivo,
               ROW_NUMBER() OVER (ORDER BY COALESCE(ep.passivo,0) DESC) AS ranking
        FROM estado_base eb
        LEFT JOIN estado_passivo ep ON eb.estado = ep.estado
        LEFT JOIN estado_vencidas ev ON eb.estado = ev.estado
        {"WHERE eb.estado = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
        ORDER BY ranking
    """)

def ranking_unidades():
    return query(f"""
        WITH unid_base AS (
            SELECT u.name AS unidade, u.state AS estado,
                   count(DISTINCT f.employee_id) AS func,
                   count(*) AS ocorrencias,
                   ROUND(AVG(f.financial_impact),0) AS passivo_medio
            FROM read_parquet({gq('fact_detected_inconsistency')}) f
            JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id=e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
            GROUP BY u.name, u.state
        ),
        unid_passivo AS (
            SELECT u.name AS unidade,
                   ROUND(SUM(COALESCE(fp.estimated_impact,0)),0) AS passivo
            FROM read_parquet({gq('fact_passivo_trabalhista')}) fp
            JOIN read_parquet({pq('dim_employee')}) e ON fp.employee_id=e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
            GROUP BY u.name
        ),
        unid_vencidas AS (
            SELECT u.name AS unidade,
                   ROUND(SUM(CASE WHEN v.status IN ('expired','impending') THEN 1 ELSE 0 END)*100.0/
                         NULLIF(count(*),0), 1) AS pct_vencidas
            FROM read_parquet({pq('vacations')}) v
            JOIN read_parquet({pq('dim_employee')}) e ON v.employee_id=e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
            GROUP BY u.name
        )
        SELECT ub.unidade, ub.estado, ub.func, ub.ocorrencias, ub.passivo_medio,
               COALESCE(uv.pct_vencidas,0) AS pct_vencidas,
               COALESCE(up.passivo,0) AS passivo,
               CASE WHEN COALESCE(up.passivo,0) > 500000 OR COALESCE(uv.pct_vencidas,0) > 25 THEN 'critica'
                    WHEN COALESCE(up.passivo,0) > 100000 OR COALESCE(uv.pct_vencidas,0) > 15 THEN 'alta'
                    WHEN COALESCE(up.passivo,0) > 50000 OR COALESCE(uv.pct_vencidas,0) > 10 THEN 'media'
                    ELSE 'baixa' END AS severity
        FROM unid_base ub
        LEFT JOIN unid_passivo up ON ub.unidade = up.unidade
        LEFT JOIN unid_vencidas uv ON ub.unidade = uv.unidade
        WHERE 1=1
          {"AND ub.estado = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND ub.unidade = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
        ORDER BY COALESCE(up.passivo,0) DESC, COALESCE(uv.pct_vencidas,0) DESC
        LIMIT 10
    """)

def resumo_reconciliacao():
    return query(f"""
        SELECT count(*) AS total_inconsistencias,
               ROUND(SUM(CASE WHEN severity='critico' THEN 1 ELSE 0 END)*100.0/count(*),1) AS pct_critico,
               ROUND(SUM(financial_impact),0) AS impacto_total,
               count(DISTINCT employee_id) AS funcionarios_afetados
        FROM read_parquet({gq('fact_detected_inconsistency')}) f
        LEFT JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
        LEFT JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        LEFT JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE 1=1
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
    """)

# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------
def perfil_funcionario(func_id):
    return query(f"""
        SELECT e.*, e.employee_id AS registration_number,
               u.name AS unit_name, u.state, u.city,
               uni.name AS union_name, p.name AS position_name, p.level
        FROM read_parquet({pq('dim_employee')}) e
        LEFT JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id=u.unit_id
        LEFT JOIN read_parquet({pq('dim_union')}) uni ON e.union_id=uni.union_id
        LEFT JOIN read_parquet({pq('dim_position')}) p ON e.position_id=p.position_id
        WHERE e.employee_id={func_id}
    """)

def inconsistencias_funcionario(func_id):
    return query(f"""
        SELECT competence,use_case,rule_name,severity,category,
               detected_value,expected_value,financial_impact,detail
        FROM read_parquet({gq('fact_detected_inconsistency')})
        WHERE employee_id={func_id}
        ORDER BY financial_impact DESC LIMIT 50
    """)

def holerite_funcionario(func_id):
    return query(f"""
        SELECT CAST(p.date_sk AS VARCHAR) AS competence, p.base_salary,
               p.overtime_50_hours, p.overtime_50_amount,
               p.overtime_70_amount, p.overtime_100_amount,
               p.night_shift_amount, p.periculosidade_amount,
               p.insalubridade_amount, p.dsr_amount,
               p.gross_total, p.inss_discount, p.irrf_discount, p.net_total
        FROM read_parquet({pq('fact_payroll')}) p
        WHERE p.employee_id={func_id}
        ORDER BY p.date_sk DESC LIMIT 24
    """)

# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------
def headcount():
    return query(f"""
        SELECT count(*) AS total,
               SUM(CASE WHEN gender='M' THEN 1 ELSE 0 END) AS masculino,
               SUM(CASE WHEN gender='F' THEN 1 ELSE 0 END) AS feminino,
               ROUND(AVG(EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM birth_date)),1) AS idade_media,
               ROUND(AVG(EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM hire_date)),1) AS tempo_medio_anos
        FROM read_parquet({pq('dim_employee')}) e
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e','u','un')}
    """)

def piramide_salarial():
    return query(f"""
        SELECT p.name AS cargo, e.gender,
               ROUND(AVG(e.base_salary),0) AS salario_medio, count(*) AS qtd
        FROM read_parquet({pq('dim_employee')}) e
        JOIN read_parquet({pq('dim_position')}) p ON e.position_id=p.position_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE e.status='active'
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY p.name, e.gender ORDER BY salario_medio DESC
    """)

def faixa_etaria():
    return query(f"""
        SELECT CASE
            WHEN EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM birth_date) < 25 THEN '18-25'
            WHEN EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM birth_date) BETWEEN 25 AND 35 THEN '26-35'
            WHEN EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM birth_date) BETWEEN 36 AND 45 THEN '36-45'
            WHEN EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM birth_date) BETWEEN 46 AND 55 THEN '46-55'
            WHEN EXTRACT(YEAR FROM current_date)-EXTRACT(YEAR FROM birth_date) BETWEEN 56 AND 65 THEN '56-65'
            ELSE '66+' END AS faixa,
            count(*) AS qtd
        FROM read_parquet({pq('dim_employee')}) e
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE 1=1
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY faixa ORDER BY faixa
    """)

# ---------------------------------------------------------------------------
# Governança
# ---------------------------------------------------------------------------
def quality_scores():
    import json
    with open(str(GOLD / "governance" / "data_quality_results.json"), encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data["results"])


def observability_status():
    import json
    obs_dir = GOLD / "observability"
    out = []
    for name in ["validation_history.json", "governance_history.json"]:
        p = obs_dir / name
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            arr = json.load(f)
        if arr:
            out.append(arr[-1])
    return pd.DataFrame(out)

def orfaos():
    return query(f"""
        SELECT f.employee_id, count(*) AS registros_sem_ponto
        FROM read_parquet({pq('fact_payroll')}) f
        JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        LEFT JOIN read_parquet({pq('fact_time_record')}) t
            ON f.employee_id=t.employee_id AND f.date_sk=t.date_sk
        WHERE t.record_id IS NULL
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY f.employee_id ORDER BY registros_sem_ponto DESC LIMIT 20
    """)

# ---------------------------------------------------------------------------
# Reconciliação
# ---------------------------------------------------------------------------
def reconciliacao_mensal_funcionario(func_id):
    return query(f"""
        SELECT m.competence, m.year, m.month,
               m.total_hours_worked,
               m.total_overtime_50_hours, m.total_overtime_70_hours, m.total_overtime_100_hours,
               m.payroll_overtime_50_hours, m.overtime_50_amount,
               m.overtime_70_amount, m.overtime_100_amount,
               m.total_night_hours, m.payroll_night_hours, m.night_shift_amount,
               m.periculosidade_amount, m.insalubridade_amount,
               m.base_salary, m.gross_total, m.net_total,
               m.hour_bank_balance, m.hour_bank_negative, m.hour_bank_exceeded,
               m.payment_expected, m.payment_paid, m.payment_divergence,
               m.has_payment_divergence, m.payment_matched,
               m.he_inconsistencies, m.night_shift_inconsistencies,
               m.periculosidade_inconsistencies, m.payment_inconsistencies,
               m.total_inconsistencies
        FROM read_parquet({gq('fact_monthly_employee')}) m
        WHERE m.employee_id = {func_id}
        ORDER BY m.year DESC, m.month DESC
        LIMIT 12
    """)

def pagamentos_funcionario(func_id):
    return query(f"""
        SELECT CAST(p.date_sk AS VARCHAR) AS competence,
               p.expected_amount, p.paid_amount,
               (p.expected_amount - p.paid_amount) AS divergencia,
               p.payment_date, p.payment_status, p.receipt_code
        FROM read_parquet({pq('fact_payment')}) p
        WHERE p.employee_id = {func_id}
        ORDER BY p.date_sk DESC
        LIMIT 12
    """)

def banco_horas_funcionario(func_id):
    return query(f"""
        SELECT CAST(h.date_sk AS VARCHAR) AS competence,
               h.previous_balance, h.credits, h.debits,
               h.current_balance, h.negative_balance
        FROM read_parquet({pq('fact_hour_bank')}) h
        WHERE h.employee_id = {func_id}
        ORDER BY h.date_sk DESC
        LIMIT 12
    """)

def resumo_reconciliacao_funcionario(func_id):
    return query(f"""
        SELECT
            SUM(m.total_inconsistencies) AS total_inconsistencias,
            SUM(m.he_inconsistencies) AS he_inconsistencias,
            SUM(m.payment_inconsistencies) AS payment_inconsistencias,
            COALESCE(SUM(m.payment_divergence), 0) AS divergencia_financeira,
            COUNT(CASE WHEN m.has_payment_divergence = 1 THEN 1 END) AS meses_com_divergencia,
            COUNT(*) AS total_meses,
            ROUND(AVG(m.hour_bank_balance), 1) AS saldo_medio_banco_horas,
            SUM(CASE WHEN m.hour_bank_negative = 1 THEN 1 ELSE 0 END) AS meses_banco_negativo,
            SUM(CASE WHEN m.hour_bank_exceeded = 1 THEN 1 ELSE 0 END) AS meses_banco_excedido
        FROM read_parquet({gq('fact_monthly_employee')}) m
        WHERE m.employee_id = {func_id}
    """)

# ---------------------------------------------------------------------------
# Operational / Dashboard-level aggregations
# ---------------------------------------------------------------------------
def turnover_anual():
    return query(f"""
        WITH latest_year AS (
            SELECT COALESCE(MAX(EXTRACT(YEAR FROM termination_date)), EXTRACT(YEAR FROM current_date))
            FROM read_parquet({pq('terminations')})
        )
        SELECT ROUND(
            COUNT(t.employee_id) * 100.0 /
            (SELECT COUNT(*) FROM read_parquet({pq('dim_employee')}) WHERE status='active'),
        1) AS taxa
        FROM read_parquet({pq('terminations')}) t
        JOIN read_parquet({pq('dim_employee')}) e ON t.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE EXTRACT(YEAR FROM t.termination_date) = (SELECT * FROM latest_year)
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
    """)

def equidade_salarial():
    return query(f"""
        SELECT ROUND(
            AVG(CASE WHEN gender='F' THEN base_salary END) /
            NULLIF(AVG(CASE WHEN gender='M' THEN base_salary END), 0),
        2) AS razao
        FROM read_parquet({pq('dim_employee')}) e
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE e.status='active'
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
    """)

def movimentacao_mensal_12m():
    return query(f"""
        WITH emp_filtered AS (
            SELECT e.employee_id
            FROM read_parquet({pq('dim_employee')}) e
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
            WHERE 1=1
              {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
              {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
              {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        ),
        meses AS (
            SELECT unnest(generate_series(1,12)) AS mes_num
        ),
        admissoes AS (
            SELECT EXTRACT(MONTH FROM hire_date) AS m, COUNT(*) AS cnt
            FROM read_parquet({pq('dim_employee')}) e
            JOIN emp_filtered ef ON e.employee_id = ef.employee_id
            WHERE EXTRACT(YEAR FROM hire_date) = EXTRACT(YEAR FROM current_date)
            GROUP BY m
        ),
        desligamentos AS (
            SELECT EXTRACT(MONTH FROM termination_date) AS m, COUNT(*) AS cnt
            FROM read_parquet({pq('terminations')}) t
            JOIN emp_filtered ef ON t.employee_id = ef.employee_id
            WHERE EXTRACT(YEAR FROM termination_date) = EXTRACT(YEAR FROM current_date)
            GROUP BY m
        ),
        promocoes AS (
            SELECT EXTRACT(MONTH FROM effective_date) AS m, COUNT(*) AS cnt
            FROM read_parquet({pq('salary_history')}) s
            JOIN emp_filtered ef ON s.employee_id = ef.employee_id
            WHERE EXTRACT(YEAR FROM effective_date) = EXTRACT(YEAR FROM current_date)
              AND change_reason = 'promotion'
            GROUP BY m
        ),
        ausencias AS (
            SELECT EXTRACT(MONTH FROM start_date) AS m, SUM(days_count) AS cnt
            FROM read_parquet({pq('leaves')}) l
            JOIN emp_filtered ef ON l.employee_id = ef.employee_id
            WHERE EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM current_date)
            GROUP BY m
        )
        SELECT m.mes_num,
               COALESCE(a.cnt, 0) AS admissoes,
               COALESCE(d.cnt, 0) AS desligamentos,
               COALESCE(p.cnt, 0) AS promocoes,
               COALESCE(au.cnt, 0) AS ausencias
        FROM meses m
        LEFT JOIN admissoes a ON m.mes_num = a.m
        LEFT JOIN desligamentos d ON m.mes_num = d.m
        LEFT JOIN promocoes p ON m.mes_num = p.m
        LEFT JOIN ausencias au ON m.mes_num = au.m
        ORDER BY m.mes_num
    """)

def saude_organizacional():
    return query(f"""
        WITH emp_filtered AS (
            SELECT e.employee_id
            FROM read_parquet({pq('dim_employee')}) e
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
            WHERE 1=1
              {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
              {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
              {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        ),
        base AS (
            SELECT
                (SELECT COUNT(*) FROM read_parquet({pq('dim_employee')}) e JOIN emp_filtered ef ON e.employee_id=ef.employee_id WHERE e.status='active') AS head,
                (SELECT COUNT(*) FROM read_parquet({pq('dim_employee')}) e JOIN emp_filtered ef ON e.employee_id=ef.employee_id WHERE e.status='active') AS head_dup
        ),
        overtime_stats AS (
            SELECT ROUND(AVG(COALESCE(overtime_50_hours,0) + COALESCE(overtime_70_hours,0) + COALESCE(overtime_100_hours,0)), 1) AS avg_he
            FROM read_parquet({pq('fact_payroll')}) p
            JOIN emp_filtered ef ON p.employee_id = ef.employee_id
        ),
        leave_stats AS (
            SELECT
                SUM(CASE WHEN type = 'Afastamento' THEN days_count ELSE 0 END) AS total_absenteismo,
                SUM(CASE WHEN type = 'Licenca Medica' THEN days_count ELSE 0 END) AS total_licenca
            FROM read_parquet({pq('leaves')}) l
            JOIN emp_filtered ef ON l.employee_id = ef.employee_id
            WHERE EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM current_date)
        ),
        bank_stats AS (
            SELECT COUNT(*) AS saturados
            FROM read_parquet({pq('fact_hour_bank')}) h
            JOIN emp_filtered ef ON h.employee_id = ef.employee_id
            WHERE current_balance > 0 AND negative_balance = false
        )
        SELECT
            ROUND(COALESCE(ls.total_absenteismo, 0) * 100.0 / (b.head * 22), 2) AS taxa_absenteismo,
            ROUND(COALESCE(ls.total_licenca, 0) * 100.0 / (b.head * 22), 2) AS taxa_licenca,
            COALESCE(os.avg_he, 0) AS media_he_mensal,
            ROUND(COALESCE(bs.saturados, 0) * 100.0 / NULLIF(b.head, 0), 1) AS indice_saturacao
        FROM base b
        LEFT JOIN overtime_stats os ON true
        LEFT JOIN leave_stats ls ON true
        LEFT JOIN bank_stats bs ON true
    """)

def passivo_funcionario(func_id):
    return query(f"""
        SELECT ROUND(SUM(estimated_impact), 0) AS passivo_total
        FROM read_parquet({gq('fact_passivo_trabalhista')})
        WHERE employee_id = {func_id}
    """)

def employee_vacation_timeline(func_id):
    return query(f"""
        SELECT acquisition_start, acquisition_end, concession_deadline,
               days_taken, days_sold, status
        FROM read_parquet({pq('vacations')})
        WHERE employee_id = {func_id}
        ORDER BY acquisition_start DESC
        LIMIT 5
    """)

def employee_registration_checks(func_id):
    return query(f"""
        SELECT
            CASE WHEN e.union_id IS NOT NULL THEN 1 ELSE 0 END AS sindicato_definido,
            CASE WHEN (SELECT COUNT(*) FROM read_parquet({pq('fact_payroll')}) p
                        WHERE p.employee_id = e.employee_id) > 0 THEN 1 ELSE 0 END AS cpf_consistente,
            CASE WHEN e.periculosidade_eligible THEN 1 ELSE 0 END AS periculosidade_elegivel,
            CASE WHEN e.insalubridade_eligible THEN 1 ELSE 0 END AS insalubridade_elegivel,
            CASE WHEN e.weekly_hours <= u.standard_weekly_hours THEN 1 ELSE 0 END AS escala_compativel,
            CASE WHEN e.weekly_hours <= 44 THEN 1 ELSE 0 END AS jornada_dentro_limite
        FROM read_parquet({pq('dim_employee')}) e
        LEFT JOIN read_parquet({pq('dim_union')}) u ON e.union_id = u.union_id
        WHERE e.employee_id = {func_id}
    """)

def employee_risk_status(func_id):
    return query(f"""
        SELECT
            COALESCE(
                (SELECT MAX(CASE
                    WHEN v.status = 'expired' THEN 'Critico'
                    WHEN v.status = 'impending' AND v.concession_deadline <= current_date + 30 THEN 'Atencao'
                    WHEN v.status = 'impending' THEN 'Monitorar'
                    ELSE 'Regular'
                END)
                FROM read_parquet({pq('vacations')}) v
                WHERE v.employee_id = {func_id}),
            'Regular'
            ) AS risk_level,
            COALESCE(
                (SELECT MAX(v.concession_deadline)
                FROM read_parquet({pq('vacations')}) v
                WHERE v.employee_id = {func_id} AND v.status = 'expired'),
            NULL) AS latest_expired,
            COALESCE(
                (SELECT COUNT(*)
                FROM read_parquet({gq('fact_detected_inconsistency')})
                WHERE employee_id = {func_id}),
            0) AS inconsistency_count
    """)

def employee_audit_log(func_id):
    return query(f"""
        SELECT competence AS data, rule_name AS evento,
               severity AS status,
               detail AS obs,
               CASE WHEN severity = 'critico' THEN '#FED7D7'
                    WHEN severity = 'alto' THEN '#FEF3C7'
                    ELSE '#E6F7FF' END AS color
        FROM read_parquet({gq('fact_detected_inconsistency')})
        WHERE employee_id = {func_id}
        ORDER BY competence DESC
        LIMIT 20
    """)

# ---------------------------------------------------------------------------
# IA / CCT
# ---------------------------------------------------------------------------
def cct_evolution_data():
    return query(f"""
        SELECT name, state, cct_year_start, cct_year_end,
               salary_adjustment_percent, base_salary_min,
               he_sunday_percent, night_shift_percent,
               meal_voucher_amount
        FROM read_parquet({pq('dim_union')})
        WHERE 1=1
          {"AND state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
    """)
def ccts_processadas():
    return query(f"""
        SELECT name, state, company, standard_weekly_hours,
               cct_year_start, cct_year_end
        FROM read_parquet({pq('dim_union')})
        WHERE 1=1
          {"AND state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
    """)

def regras_extraidas():
    return query(f"""
        SELECT use_case AS regra_id, rule_name AS regra,
               severity AS nivel, category
        FROM read_parquet({gq('fact_detected_inconsistency')}) f
        LEFT JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
        LEFT JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        LEFT JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE 1=1
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY use_case, rule_name, severity, category
        ORDER BY use_case
    """)

def status_geral():
    return query(f"""
        SELECT CASE WHEN severity='critico' THEN 'Critico'
                    WHEN severity='alto' THEN 'Atencao'
                    ELSE 'Regular' END AS status,
                   COUNT(*) AS qtd
        FROM read_parquet({gq('fact_detected_inconsistency')}) f
        LEFT JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
        LEFT JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        LEFT JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        WHERE 1=1
          {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY severity ORDER BY severity
    """)

# ---------------------------------------------------------------------------
# Analitico - new data functions for dashboard_analitico
# ---------------------------------------------------------------------------
def window_alert_data():
    return query(f"""
        WITH vacations_by_state AS (
            SELECT u.state,
                   CASE
                       WHEN v.concession_deadline - CURRENT_DATE <= 30 THEN '<30 dias'
                       WHEN v.concession_deadline - CURRENT_DATE <= 60 THEN '30-60 dias'
                       WHEN v.concession_deadline - CURRENT_DATE <= 90 THEN '60-90 dias'
                       ELSE 'Em dia'
                   END AS janela,
                   COUNT(*) AS cnt
            FROM read_parquet({pq('vacations')}) v
            JOIN read_parquet({pq('dim_employee')}) e ON v.employee_id = e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            WHERE v.status IN ('pending', 'impending')
              AND v.concession_deadline > CURRENT_DATE
              {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
            GROUP BY u.state, janela
        ),
        totals AS (
            SELECT state, SUM(cnt) AS total
            FROM vacations_by_state
            GROUP BY state
        )
        SELECT vb.state, vb.janela,
               ROUND(vb.cnt * 100.0 / t.total, 1) AS pct
        FROM vacations_by_state vb
        JOIN totals t ON vb.state = t.state
        ORDER BY vb.state, vb.janela
    """)

def payment_month_data():
    return query(f"""
        WITH monthly_employees AS (
            SELECT year, month,
                   CONCAT(CAST(year AS VARCHAR), '-', LPAD(CAST(month AS VARCHAR), 2, '0')) AS competence,
                   COUNT(DISTINCT employee_id) AS employee_count
            FROM read_parquet({gq('fact_monthly_employee')}) m
            JOIN read_parquet({pq('dim_employee')}) e ON m.employee_id = e.employee_id
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
            WHERE 1=1
              {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
              {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
              {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
              {_filters_competence('m')}
            GROUP BY year, month
        ),
        monthly_passivo AS (
            SELECT competence,
                   COUNT(DISTINCT employee_id) AS affected_employees,
                   ROUND(SUM(estimated_impact), 0) AS passivo_total
            FROM read_parquet({gq('fact_passivo_trabalhista')})
            GROUP BY competence
        )
        SELECT me.competence, me.year, me.month,
               me.employee_count,
               COALESCE(mp.affected_employees, 0) AS affected_employees,
               COALESCE(mp.passivo_total, 0) AS passivo_total
        FROM monthly_employees me
        LEFT JOIN monthly_passivo mp ON me.competence = mp.competence
        ORDER BY me.year, me.month
        LIMIT 12
    """)

def jornada_donut_data():
    return query(f"""
        WITH incompatible_ids AS (
            SELECT DISTINCT employee_id
            FROM read_parquet({gq('fact_detected_inconsistency')})
            WHERE use_case = 20
        ),
        schedule_counts AS (
            SELECT e.work_schedule, COUNT(*) AS cnt
            FROM read_parquet({pq('dim_employee')}) e
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
            LEFT JOIN incompatible_ids i ON e.employee_id = i.employee_id
            WHERE e.status = 'active' AND i.employee_id IS NULL
              {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
              {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
              {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
            GROUP BY e.work_schedule
        ),
        incompatible_count AS (
            SELECT COUNT(DISTINCT i.employee_id) AS cnt
            FROM incompatible_ids i
            JOIN read_parquet({pq('dim_employee')}) e ON i.employee_id = e.employee_id
            WHERE e.status = 'active'
        )
        SELECT sc.work_schedule, sc.cnt,
               COALESCE((SELECT cnt FROM incompatible_count), 0) AS incompatible_cnt
        FROM schedule_counts sc
        ORDER BY sc.cnt DESC
    """)

def compliance_table_data():
    return query(f"""
        WITH employee_consistency AS (
            SELECT e.employee_id, e.union_id,
                   CASE WHEN fp.employee_id IS NOT NULL THEN 1 ELSE 0 END AS has_passivo
            FROM read_parquet({pq('dim_employee')}) e
            LEFT JOIN (SELECT DISTINCT employee_id FROM read_parquet({gq('fact_passivo_trabalhista')})) fp
                ON e.employee_id = fp.employee_id
            WHERE e.status = 'active'
        )
        SELECT 
            un.state,
            un.name AS union_name,
            un.standard_weekly_hours,
            ROUND(un.salary_adjustment_percent * 100, 1) AS salary_adjustment_percent,
            un.base_salary_min,
            COUNT(DISTINCT ec.employee_id) AS employee_count,
            ROUND(SUM(CASE WHEN ec.has_passivo = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS conformidade_pct,
            COALESCE(ROUND(SUM(fp.estimated_impact) / NULLIF(COUNT(DISTINCT ec.employee_id), 0), 0), 0) AS passivo_por_funcionario,
            COALESCE(ROUND(SUM(fp.estimated_impact), 0), 0) AS passivo_total
        FROM read_parquet({pq('dim_union')}) un
        LEFT JOIN employee_consistency ec ON un.union_id = ec.union_id
        LEFT JOIN read_parquet({gq('fact_passivo_trabalhista')}) fp ON ec.employee_id = fp.employee_id
        WHERE 1=1
          {"AND un.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
          {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        GROUP BY un.state, un.name, un.standard_weekly_hours, un.salary_adjustment_percent, un.base_salary_min
        ORDER BY passivo_total DESC
    """)

def distribuicao_entidades():
    base = pq('dim_employee')
    pay = pq('fact_payroll')
    return query(f"""
        WITH ebase AS (
            SELECT e.*
            FROM read_parquet({base}) e
            JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
            JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
            WHERE 1=1
              {"AND u.state = '" + _GLOBAL_FILTERS['estado'] + "'" if _GLOBAL_FILTERS.get('estado') else ""}
              {"AND u.name = '" + _GLOBAL_FILTERS['unidade'] + "'" if _GLOBAL_FILTERS.get('unidade') else ""}
              {"AND un.name = '" + _GLOBAL_FILTERS['sindicato'] + "'" if _GLOBAL_FILTERS.get('sindicato') else ""}
        )
        SELECT
            (SELECT count(*) FROM ebase WHERE status='active') AS total_ativos,

            (SELECT count(*) FROM ebase WHERE status='active' AND work_schedule='5x2') AS e_5x2,
            (SELECT count(*) FROM ebase WHERE status='active' AND work_schedule='12x36') AS e_12x36,
            (SELECT count(*) FROM ebase WHERE status='active' AND work_schedule='6x1') AS e_6x1,
            (SELECT count(*) FROM ebase WHERE status='active' AND work_schedule='3x3') AS e_3x3,

            (SELECT count(DISTINCT employee_id) FROM read_parquet({pay}) WHERE overtime_50_hours > 0) AS he_50,
            (SELECT count(DISTINCT employee_id) FROM read_parquet({pay}) WHERE overtime_70_hours > 0) AS he_70,
            (SELECT count(DISTINCT employee_id) FROM read_parquet({pay}) WHERE overtime_100_hours > 0) AS he_100,

            (SELECT count(DISTINCT employee_id) FROM read_parquet({pay}) WHERE night_shift_amount > 0) AS ad_noturno,

            (SELECT count(*) FROM ebase WHERE status='active' AND periculosidade_eligible=true) AS periculosidade,
            (SELECT count(*) FROM ebase WHERE status='active' AND insalubridade_eligible=true) AS insalubridade,

            (SELECT count(*) FROM ebase WHERE status='active') AS vr_alimentacao,
            (SELECT count(*) FROM ebase WHERE status='active') AS cesta_basica,
            (SELECT count(*) FROM ebase WHERE status='active') AS plr,
            (SELECT count(*) FROM ebase WHERE status='active' AND dependents > 0) AS auxilio_creche,

            (SELECT count(DISTINCT employee_id) FROM read_parquet({pay}) WHERE union_discount > 0) AS contrib_sindical,

            (SELECT count(*) FROM ebase WHERE status='active' AND gender='F') AS gestante
    """)
