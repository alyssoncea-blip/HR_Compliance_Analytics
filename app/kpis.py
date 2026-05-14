"""
Semantic KPI Layer — metricas de negocio versionadas e reusaveis.

Centraliza definicoes de KPIs para evitar duplicacao de logica SQL
nos dashboards e garantir uma unica fonte de verdade para cada indicador.
"""
import pandas as pd
from app.data import query, pq, gq, _filters_employee, _filters_competence

_METRICS = {}


def register(name, category, unit, description):
    """Decorator que registra uma metrica no catalogo semantico."""
    def decorator(fn):
        _METRICS[name] = {
            "name": name,
            "category": category,
            "unit": unit,
            "description": description,
            "fn": fn,
        }
        return fn
    return decorator


@register("passivo_total", "Financeiro", "BRL",
          "Somatorio do passivo trabalhista estimado a partir das inconsistencias detectadas")
def metric_passivo_total():
    sql = f"""
        SELECT ROUND(SUM(estimated_impact), 0) AS value
        FROM read_parquet({gq('fact_passivo_trabalhista')}) fp
        JOIN read_parquet({pq('dim_employee')}) e ON fp.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e', 'u', 'un')}
    """
    df = query(sql)
    return float(df.iloc[0]["value"]) if not df.empty and df.iloc[0]["value"] is not None else 0.0


@register("conformidade_pct", "Qualidade", "%",
          "Percentual de competencias sem inconsistencias criticas")
def metric_conformidade_pct():
    sql = f"""
        SELECT
            COUNT(DISTINCT CASE WHEN total_inconsistencies = 0 THEN competence END) * 100.0 /
            NULLIF(COUNT(DISTINCT competence), 0) AS value
        FROM read_parquet({gq('fact_monthly_employee')}) m
        JOIN read_parquet({pq('dim_employee')}) e ON m.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e', 'u', 'un')}
    """
    df = query(sql)
    val = df.iloc[0]["value"]
    return round(float(val), 1) if not df.empty and val is not None else 100.0


@register("headcount", "Pessoas", "funcionarios", "Total de funcionarios ativos filtrados")
def metric_headcount():
    from app.data import headcount
    df = headcount()
    return int(df.iloc[0]["total"]) if not df.empty else 0


@register("turnover_pct", "Pessoas", "%", "Taxa de turnover anual calculada")
def metric_turnover_pct():
    from app.data import turnover_anual
    df = turnover_anual()
    return float(df.iloc[0]["taxa"]) if not df.empty else 0.0


@register("equidade_salarial", "Pessoas", "razao",
          "Razao salarial feminino / masculino (1.0 = equidade)")
def metric_equidade_salarial():
    from app.data import equidade_salarial
    df = equidade_salarial()
    val = df.iloc[0]["razao"]
    return float(val) if not df.empty and val is not None else 1.0


@register("passivo_por_funcionario", "Financeiro", "BRL",
          "Passivo medio estimado por funcionario afetado")
def metric_passivo_por_funcionario():
    sql = f"""
        SELECT
            COUNT(DISTINCT f.employee_id) AS affected,
            ROUND(SUM(f.estimated_impact), 0) AS total
        FROM read_parquet({gq('fact_passivo_trabalhista')}) f
        JOIN read_parquet({pq('dim_employee')}) e ON f.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e', 'u', 'un')}
    """
    df = query(sql)
    total = df.iloc[0]["total"] if not df.empty and df.iloc[0]["total"] is not None else 0
    affected = df.iloc[0]["affected"] if not df.empty and df.iloc[0]["affected"] is not None else 1
    return round(total / max(affected, 1), 0)


@register("he_media_mensal", "Operacao", "horas",
          "Media mensal de horas extras por funcionario")
def metric_he_media_mensal():
    sql = f"""
        SELECT ROUND(AVG(
            COALESCE(total_overtime_50_hours, 0) +
            COALESCE(total_overtime_70_hours, 0) +
            COALESCE(total_overtime_100_hours, 0)
        ), 1) AS value
        FROM read_parquet({gq('fact_monthly_employee')}) m
        JOIN read_parquet({pq('dim_employee')}) e ON m.employee_id = e.employee_id
        JOIN read_parquet({pq('dim_unit')}) u ON e.unit_id = u.unit_id
        JOIN read_parquet({pq('dim_union')}) un ON e.union_id = un.union_id
        {_filters_employee('e', 'u', 'un')}
          {_filters_competence('m')}
    """
    df = query(sql)
    val = df.iloc[0]["value"]
    return float(val) if not df.empty and val is not None else 0.0


@register("pct_ferias_vencidas", "Pessoas", "%", "Percentual de funcionarios com ferias vencidas ou proximas")
def metric_pct_ferias_vencidas():
    from app.data import kpi_ferias_vencidas
    df = kpi_ferias_vencidas()
    if df.empty:
        return 0.0
    total = int(df.iloc[0]["total"]) if df.iloc[0]["total"] else 0
    vencidas = int(df.iloc[0]["vencidas"]) if df.iloc[0]["vencidas"] else 0
    return round(vencidas / max(total, 1) * 100, 1)


@register("proximos_vencimento_count", "Pessoas", "funcionarios",
          "Quantidade de funcionarios com ferias proximas ao vencimento")
def metric_proximos_vencimento():
    from app.data import kpi_proximos_vencimento
    df = kpi_proximos_vencimento()
    return int(df.iloc[0]["qtd"]) if not df.empty and df.iloc[0]["qtd"] is not None else 0


@register("inconsistencias_total", "Qualidade", "ocorrencias",
          "Total de inconsistencias detectadas pelo motor de validacao")
def metric_inconsistencias_total():
    from app.data import resumo_reconciliacao
    df = resumo_reconciliacao()
    return int(df.iloc[0]["total_inconsistencias"]) if not df.empty and df.iloc[0]["total_inconsistencias"] is not None else 0


@register("impacto_total", "Financeiro", "BRL",
          "Impacto financeiro total das inconsistencias detectadas")
def metric_impacto_total():
    from app.data import resumo_reconciliacao
    df = resumo_reconciliacao()
    return float(df.iloc[0]["impacto_total"]) if not df.empty and df.iloc[0]["impacto_total"] is not None else 0.0


@register("funcionarios_afetados", "Pessoas", "funcionarios",
          "Quantidade de funcionarios com pelo menos uma inconsistencia")
def metric_funcionarios_afetados():
    from app.data import resumo_reconciliacao
    df = resumo_reconciliacao()
    return int(df.iloc[0]["funcionarios_afetados"]) if not df.empty and df.iloc[0]["funcionarios_afetados"] is not None else 0


def list_metrics():
    """Retorna DataFrame com o catalogo de KPIs disponiveis."""
    return pd.DataFrame([
        {"name": k, "category": v["category"], "unit": v["unit"], "description": v["description"]}
        for k, v in _METRICS.items()
    ])


def get_metric(name: str):
    """Executa uma metrica pelo nome e retorna o valor escalar."""
    entry = _METRICS.get(name)
    if not entry:
        raise KeyError(f"Metric '{name}' not found. Available: {list(_METRICS.keys())}")
    return entry["fn"]()


def get_metrics(names: list[str]) -> dict:
    """Executa multiplas metricas e retorna dict {name: value}."""
    return {n: get_metric(n) for n in names}
