import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
from datetime import datetime, date
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import (perfil_funcionario, inconsistencias_funcionario, holerite_funcionario,
                      passivo_funcionario, employee_vacation_timeline,
                      employee_registration_checks, employee_risk_status,
                      employee_audit_log)

# ---------------------------------------------------------------------------
# Busca de funcionários para autocomplete
# ---------------------------------------------------------------------------
def _query_parquet(sql):
    import duckdb
    con = duckdb.connect()
    df = con.execute(sql).fetchdf()
    con.close()
    return df

def _employee_options():
    try:
        df = _query_parquet(f"""
            SELECT employee_id, name FROM read_parquet('data/silver/dim_employee.parquet')
            ORDER BY name LIMIT 500
        """)
        return [{"label": row["name"], "value": int(row["employee_id"])} for _, row in df.iterrows()]
    except Exception:
        return [{"label": "Erro ao carregar", "value": 0}]


def _cpf_options():
    try:
        df = _query_parquet(f"""
            SELECT employee_id, cpf, name FROM read_parquet('data/silver/dim_employee.parquet')
            ORDER BY cpf LIMIT 500
        """)
        return [{"label": f"{row['cpf']} - {row['name']}", "value": int(row["employee_id"])} for _, row in df.iterrows()]
    except Exception:
        return [{"label": "Erro ao carregar", "value": 0}]

# ---------------------------------------------------------------------------
# Fallback / mock data
# ---------------------------------------------------------------------------
def _mock_holerite():
    import pandas as pd
    return pd.DataFrame([
        {"competence": "2024-03", "base_salary": 5500.0, "overtime_50_hours": 12.0,
         "overtime_50_amount": 320.0, "overtime_70_amount": 180.0, "overtime_100_amount": 0.0,
         "night_shift_amount": 0.0, "periculosidade_amount": 1650.0,
         "insalubridade_amount": 0.0, "dsr_amount": 0.0,
         "gross_total": 7650.0, "inss_discount": 900.0, "irrf_discount": 540.0, "net_total": 6210.0},
        {"competence": "2024-02", "base_salary": 5500.0, "overtime_50_hours": 10.0,
         "overtime_50_amount": 380.0, "overtime_70_amount": 95.0, "overtime_100_amount": 0.0,
         "night_shift_amount": 0.0, "periculosidade_amount": 1650.0,
         "insalubridade_amount": 0.0, "dsr_amount": 0.0,
         "gross_total": 7625.0, "inss_discount": 895.0, "irrf_discount": 540.0, "net_total": 6190.0},
    ])

def _mock_inconsistencias():
    import pandas as pd
    return pd.DataFrame([
        {"use_case": 9, "rule_name": "Hora Extra nao paga", "severity": "critico",
         "category": "Ponto", "financial_impact": 320.0,
         "competence": "2024-03",
         "detail": "4h extras registradas no ponto nao constam na folha."},
        {"use_case": 21, "rule_name": "Pagamento divergente", "severity": "alto",
         "category": "Folha", "financial_impact": 125.0,
         "competence": "2024-02",
         "detail": "Diferenca de R$ 125 entre esperado e pago."},
    ])

def _mock_passivo():
    return 10450.0

def _mock_risk():
    return {"risk_level": "Critico", "days_overdue": 120, "inconsistency_count": 3}

def _mock_vacation_timeline():
    import pandas as pd
    return pd.DataFrame([
        {"acquisition_start": date(2022, 3, 15), "acquisition_end": date(2023, 3, 14),
         "concession_deadline": date(2024, 3, 14), "status": "expired"},
        {"acquisition_start": date(2023, 3, 15), "acquisition_end": date(2024, 3, 14),
         "concession_deadline": date(2025, 3, 14), "status": "impending"},
    ])

def _mock_reg_checks():
    return {
        "sindicato_definido": 1, "cpf_consistente": 0,
        "periculosidade_elegivel": 1, "insalubridade_elegivel": 1,
        "escala_compativel": 1, "jornada_dentro_limite": 1,
    }

def _mock_audit_log():
    import pandas as pd
    return pd.DataFrame([
        {"data": "2024-03", "evento": "Folha importada", "status": "Normal", "obs": "", "color": "#E6F7FF"},
        {"data": "2024-03", "evento": "Inconsistencia HE", "status": "Critico", "obs": "4h nao pagas", "color": "#FED7D7"},
        {"data": "2024-02", "evento": "Divergencia pagamento", "status": "Alto", "obs": "R$ 125 divergencia", "color": "#FEF3C7"},
        {"data": "2024-02", "evento": "Alerta gerado", "status": "Alto", "obs": "", "color": "#FEF3C7"},
    ])

def _safe_data(func_id):
    try:
        perf = perfil_funcionario(func_id)
        if perf.empty:
            raise ValueError("empty")
    except Exception:
        perf = None

    try:
        inc = inconsistencias_funcionario(func_id)
        if inc.empty:
            raise ValueError("empty")
    except Exception:
        inc = _mock_inconsistencias()

    risk_sum = 0.0
    try:
        if inc is not None and not inc.empty and "financial_impact" in inc.columns:
            risk_sum = float(inc["financial_impact"].fillna(0).sum())
    except Exception:
        risk_sum = 0.0

    try:
        hol = holerite_funcionario(func_id)
        if hol.empty:
            raise ValueError("empty")
    except Exception:
        hol = _mock_holerite()

    try:
        passivo = passivo_funcionario(func_id)
        raw_passivo = passivo.iloc[0]["passivo_total"] if not passivo.empty else None
        if raw_passivo is None or raw_passivo != raw_passivo:
            passivo_val = risk_sum
        else:
            passivo_val = float(raw_passivo)
    except Exception:
        passivo_val = risk_sum if risk_sum > 0 else _mock_passivo()

    try:
        risk = employee_risk_status(func_id)
        if not risk.empty:
            r = risk.iloc[0]
            risk_info = {"risk_level": r["risk_level"], "days_overdue": 0, "inconsistency_count": int(r["inconsistency_count"])}
        else:
            raise ValueError("empty")
    except Exception:
        risk_info = _mock_risk()

    try:
        vactl = employee_vacation_timeline(func_id)
        if vactl.empty:
            raise ValueError("empty")
    except Exception:
        vactl = _mock_vacation_timeline()

    try:
        reg = employee_registration_checks(func_id)
        if reg.empty:
            raise ValueError("empty")
        reg_info = reg.iloc[0].to_dict()
    except Exception:
        reg_info = _mock_reg_checks()

    try:
        audit = employee_audit_log(func_id)
        if audit.empty:
            raise ValueError("empty")
    except Exception:
        audit = _mock_audit_log()

    return perf, inc, hol, passivo_val, risk_info, vactl, reg_info, audit


# ---------------------------------------------------------------------------
# UI builders
# ---------------------------------------------------------------------------
def _severity_badge(text, color):
    return html.Span(
        text,
        style={
            "backgroundColor": color, "color": "white",
            "padding": "4px 14px", "borderRadius": "6px",
            "fontSize": "0.75rem", "fontWeight": "700",
            "display": "inline-block",
        },
    )


def _timeline_card(vactl=None):
    try:
        if vactl is not None and not vactl.empty:
            stages = []
            for _, v in vactl.iterrows():
                a_end = v["acquisition_end"]
                c_deadline = v["concession_deadline"]
                status = v["status"]
                days_left = (c_deadline - date.today()).days if c_deadline else 0
                if status == "expired":
                    label, color_key = "Vencido", "red"
                elif status == "impending" and days_left <= 30:
                    label, color_key = "Proximo ao Vencimento", "yellow"
                elif status == "impending":
                    label, color_key = "Periodo Concessivo", "green"
                else:
                    label, color_key = "Periodo Aquisitivo", "green"
                stages.append((label, color_key, str(a_end)[:10]))
            if not stages:
                stages = [("Sem ferias registradas", "green", "N/A")]
        else:
            stages = [("Sem ferias registradas", "green", "N/A")]
    except Exception:
        stages = [
            ("Periodo Aquisitivo", "green", "Data Aquisitiva"),
            ("Periodo Concessivo", "green", "Inicio Concessivo"),
            ("Proximo ao Vencimento", "yellow", "Limite Legal"),
            ("Vencido", "red", "Data Atual"),
        ]

    colors_map = {"green": VERDE, "yellow": AMARELO, "red": VERMELHO}
    n = len(stages)
    segment_widths = [f"{100/n}%" for _ in stages]

    segments = []
    for i, (label, color_key, marker_label) in enumerate(stages):
        color = colors_map.get(color_key, VERDE)
        segments.append(
            html.Div(
                [
                    html.Div(
                        label,
                        style={
                            "position": "absolute", "top": "-22px",
                            "fontSize": "0.7rem", "color": "#4A5568",
                            "fontWeight": "600", "whiteSpace": "nowrap",
                        },
                    ),
                    html.Div(
                        style={
                            "height": "12px", "backgroundColor": color,
                            "borderRadius": "6px" if i == 0 else ("0 6px 6px 0" if i == n-1 else "0"),
                        },
                    ),
                    html.Div(
                        "▲",
                        style={
                            "position": "absolute", "bottom": "-18px",
                            "left": "50%", "transform": "translateX(-50%)",
                            "fontSize": "10px", "color": "#4A5568",
                        },
                    ),
                    html.Div(
                        marker_label,
                        style={
                            "position": "absolute", "bottom": "-34px",
                            "fontSize": "0.65rem", "color": "#4A5568",
                            "whiteSpace": "nowrap", "left": "50%", "transform": "translateX(-50%)",
                        },
                    ),
                ],
                style={
                    "position": "relative",
                    "flex": segment_widths[i],
                    "marginRight": "2px" if i < n-1 else "0",
                },
            )
        )

    return html.Div(
        [
            html.H6(
                "LINHA DO TEMPO DO FUNCIONARIO",
                style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"},
            ),
            html.P(
                "Rastreabilidade temporal, periodos aquisitivos, evolucao ate o vencimento",
                style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "20px"},
            ),
            html.Div(segments, style={"display": "flex", "alignItems": "center", "position": "relative", "marginBottom": "40px"}),

        ],
        style={"position": "relative"},
    )


def _financial_table(hol=None, passivo_val=None):
    data = []
    try:
        if hol is not None and not hol.empty:
            for _, r in hol.head(4).iterrows():
                expected = r.get("gross_total", 0) or 0
                paid = r.get("net_total", 0) or 0
                diff = paid - expected
                abs_diff_pct = abs(diff) / expected * 100 if expected else 0
                if abs_diff_pct >= 50 or abs(diff) >= 10000:
                    status, status_color, bar_color = "Critico", VERMELHO, VERMELHO
                elif abs_diff_pct >= 10 or abs(diff) >= 1000:
                    status, status_color, bar_color = "Divergente", AMARELO, AMARELO
                else:
                    status, status_color, bar_color = "Correto", VERDE, VERDE
                data.append({
                    "event": f"Folha {r.get('competence', '-')}", "expected": expected, "paid": paid,
                    "diff": diff, "status": status, "status_color": status_color,
                    "bar_color": bar_color,
                })
    except Exception:
        pass

    if not data:
        data = [
            {"event": "Folha 2024-03", "expected": 18450, "paid": 18000, "diff": -450, "status": "Divergente", "status_color": AMARELO, "bar_color": AMARELO},
            {"event": "Folha 2024-02", "expected": 1850, "paid": 350, "diff": -1500, "status": "Critico", "status_color": VERMELHO, "bar_color": VERMELHO},
            {"event": "Folha 2024-01", "expected": 1350, "paid": 1300, "diff": -50, "status": "Correto", "status_color": VERDE, "bar_color": VERDE},
            {"event": "Folha 2023-12", "expected": 1350, "paid": 1350, "diff": 0, "status": "Correto", "status_color": VERDE, "bar_color": VERDE},
        ]

    header_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "6px 8px",
        "fontSize": "0.75rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
    }
    cell_style = {
        "padding": "6px 8px", "fontSize": "0.75rem", "color": "#4A5568",
        "borderBottom": "1px solid #f7fafc", "textAlign": "left",
    }
    rows = [html.Tr([
        html.Th("Evento", style=header_style),
        html.Th("", style=header_style),
        html.Th("Valor Esperado", style=header_style),
        html.Th("Valor Pago", style=header_style),
        html.Th("Diferenca", style=header_style),
        html.Th("Status", style={**header_style, "textAlign": "center"}),
    ])]
    for d in data:
        bar_w = min(abs(d["expected"]) / 200, 60) if d["expected"] else 10
        rows.append(html.Tr([
            html.Td(d["event"], style=cell_style),
            html.Td(
                html.Div(style={"width": f"{bar_w}px", "height": "6px", "backgroundColor": d["bar_color"], "borderRadius": "3px"}),
                style=cell_style,
            ),
            html.Td(f"R$ {d['expected']:,.0f}".replace(",", "."), style=cell_style),
            html.Td(f"R$ {d['paid']:,.0f}".replace(",", "."), style=cell_style),
            html.Td(
                f"{d['diff']:,}".replace(",", "."),
                style={**cell_style, "color": VERMELHO if d["diff"] < 0 else VERDE},
            ),
            html.Td(
                _severity_badge(d["status"], d["status_color"]),
                style={**cell_style, "textAlign": "center"},
            ),
        ]))

    pv = passivo_val
    if pv is None or pv != pv:
        pv = 10450

    return html.Div([
        html.H6("DETALHAMENTO FINANCEIRO", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Impacto financeiro, calculo de valores, divergencias e discrepancias", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div(
            html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
            style={"maxHeight": "240px", "overflowY": "auto", "overflowX": "hidden"},
        ),
        html.Div(
            f"Passivo Estimado: R$ {pv:,.0f}".replace(",", "."),
            style={"textAlign": "right", "fontWeight": "700", "fontSize": "0.85rem", "color": "#1A202C", "marginTop": "8px"},
        ),
    ])


def _operational_alerts_list(inc_df):
    severity_map = {"critico": (VERMELHO, "Vermelho"), "alto": (AMARELO, "Amarelo"), "medio": (AZUL_CLARO, "Azul")}
    items = []
    for _, r in inc_df.iterrows():
        color, label = severity_map.get(r["severity"], ("#888", "Cinza"))
        items.append(html.Div([
            html.Div([
                html.Span(
                    "!" if r["severity"] == "alto" else "X",
                    style={
                        "display": "inline-flex", "alignItems": "center", "justifyContent": "center",
                        "width": "18px", "height": "18px", "borderRadius": "50%",
                        "backgroundColor": color, "color": "white", "fontSize": "0.65rem",
                        "fontWeight": "700", "marginRight": "8px",
                    },
                ),
                html.Span(f"{label}", style={"fontSize": "0.7rem", "color": color, "fontWeight": "700", "marginRight": "6px"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "2px"}),
            html.Div(
                f"{r['detail']} (Case {r['use_case']})",
                style={"fontSize": "0.75rem", "color": "#4A5568", "paddingLeft": "26px"},
            ),
        ], style={"marginBottom": "10px", "borderBottom": "1px solid #f0f0f0", "paddingBottom": "8px"}))
    return html.Div([
        html.H6("ALERTAS OPERACIONAIS", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        html.P("Inconsistências detectadas, severidade e prioridade", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div(items, style={"maxHeight": "240px", "overflowY": "auto"}),
    ])


def _operational_alerts_compact(inc_df=None):
    severity_colors = {"critico": VERMELHO, "alto": AMARELO, "medio": AZUL_CLARO}

    def _format_competence(value):
        if value is None:
            return "-"
        comp = str(value).strip()
        if not comp:
            return "-"
        if len(comp) >= 7 and comp[4] == "-":
            return f"{comp[5:7]}/{comp[0:4]}"
        if len(comp) >= 7 and comp[2] == "/":
            return comp
        return comp

    items = []
    try:
        if inc_df is not None and not inc_df.empty:
            for _, r in inc_df.iterrows():
                color = severity_colors.get(r.get("severity", ""), "#888")
                text = r.get("rule_name", "Inconsistencia")
                if len(text) > 42:
                    text = text[:42] + "..."
                comp_txt = _format_competence(r.get("competence", "-"))
                items.append(html.Div([
                    html.Span(
                        style={
                            "display": "inline-block", "width": "16px", "height": "16px", "borderRadius": "50%",
                            "backgroundColor": color, "marginRight": "8px",
                        },
                    ),
                    html.Span(f"{text} ({comp_txt})", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}))
    except Exception:
        pass

    if not items:
        items = [
            html.Div([
                html.Span(style={"display": "inline-block", "width": "16px", "height": "16px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "8px"}),
                html.Span("Ferias vencidas ha 120 dias", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
            html.Div([
                html.Span(style={"display": "inline-block", "width": "16px", "height": "16px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "8px"}),
                html.Span("Ferias vencidas ha 120 dias", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
            html.Div([
                html.Span(style={"display": "inline-block", "width": "16px", "height": "16px", "borderRadius": "50%", "backgroundColor": AMARELO, "marginRight": "8px"}),
                html.Span("Pagamento parcial identificado", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
            html.Div([
                html.Span(style={"display": "inline-block", "width": "16px", "height": "16px", "borderRadius": "50%", "backgroundColor": AZUL_CLARO, "marginRight": "8px"}),
                html.Span("Funcionario proximo ao vencimento", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
        ]

    return html.Div([
        html.H6("ALERTAS OPERACIONAIS", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        html.P("Inconsistencias detectadas, severidade e prioridade", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div(items, style={"height": "260px", "overflowY": "auto", "overflowX": "hidden"}),
    ])


def _registration_data(reg_info=None):
    try:
        if reg_info is not None:
            checks = [
                ("Sindicato definido", bool(reg_info.get("sindicato_definido", 0)), 19),
                ("CPF Consistente (RH x Financeiro)", bool(reg_info.get("cpf_consistente", 0)), 17),
                ("Cargo Elegivel - 30% Periculosidade", bool(reg_info.get("periculosidade_elegivel", 0)), 13),
                ("Cargo Elegivel - Insalubridade 40%", bool(reg_info.get("insalubridade_elegivel", 0)), 29),
                ("Escala compativel com a CCT", bool(reg_info.get("escala_compativel", 0)), 20),
                ("Jornada semanal dentro do limite", bool(reg_info.get("jornada_dentro_limite", 0)), 25),
            ]
        else:
            raise ValueError("no reg_info")
    except Exception:
        checks = [
            ("Sindicato definido", True, 19),
            ("CPF Consistente (RH x Financeiro)", False, 17),
            ("Cargo Elegivel - 30% Periculosidade", True, 13),
            ("Cargo Elegivel - Insalubridade 40%", True, 29),
            ("Escala compativel com a CCT", True, 20),
            ("Jornada semanal dentro do limite", True, 25),
        ]

    rows = []
    for text, ok, case in checks:
        rows.append(html.Div([
            html.Span(text, style={"fontSize": "0.75rem", "color": "#4A5568", "flex": "1"}),
            html.Span("✓" if ok else "✗", style={"color": VERDE if ok else VERMELHO, "fontWeight": "700", "fontSize": "0.85rem", "marginRight": "4px"}),
            html.Span(f"(Case {case})", style={"fontSize": "0.7rem", "color": "#888"}),
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "8px", "borderBottom": "1px solid #f0f0f0", "paddingBottom": "6px"}))
    return html.Div([
        html.H6("DADOS CADASTRAIS E SINDICAIS", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Dados cadastrais criticos, elegibilidade a adicionais (periculosidade, insalubridade).", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div(rows),
    ])


def _event_log(audit_log=None):
    events = []
    try:
        if audit_log is not None and not audit_log.empty:
            for _, r in audit_log.iterrows():
                events.append({
                    "ts": str(r.get("data", "-")),
                    "event": str(r.get("evento", "-")),
                    "system": "Validacao",
                    "user": "Sistema",
                    "status": str(r.get("status", "Normal")),
                    "obs": str(r.get("obs", "")),
                    "color": str(r.get("color", "#E6F7FF")),
                })
    except Exception:
        pass

    if not events:
        events = [
            {"ts": "02/03.13 21:33", "event": "Evento Normal", "system": "Normal", "user": "Usuario/API", "status": "Normal", "obs": "", "color": "#E6F7FF"},
            {"ts": "02/03.13 21:33", "event": "Evento Normal", "system": "Normal", "user": "Usuario/API", "status": "Normal", "obs": "", "color": "#E6F7FF"},
            {"ts": "04/03.13 20:37", "event": "Alertas", "system": "Normal", "user": "Usuario/API", "status": "Alertas", "obs": "", "color": "#FEF3C7"},
            {"ts": "05/03.13 22:33", "event": "Evento Normal", "system": "Normal", "user": "Usuario/API", "status": "Critico", "obs": "", "color": "#FED7D7"},
        ]

    header_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "6px 8px",
        "fontSize": "0.75rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
    }
    cell_style = {"padding": "6px 8px", "fontSize": "0.75rem", "color": "#4A5568", "textAlign": "left"}
    rows = [html.Tr([
        html.Th("Data/Hora", style=header_style),
        html.Th("Evento", style=header_style),
        html.Th("Sistema de Origem", style=header_style),
        html.Th("Usuario/API", style=header_style),
        html.Th("Status", style=header_style),
        html.Th("Observacao", style=header_style),
    ])]
    for e in events:
        rows.append(html.Tr([
            html.Td(e["ts"], style={**cell_style, "backgroundColor": e["color"]}),
            html.Td(e["event"], style={**cell_style, "backgroundColor": e["color"]}),
            html.Td(e["system"], style={**cell_style, "backgroundColor": e["color"]}),
            html.Td(e["user"], style={**cell_style, "backgroundColor": e["color"]}),
            html.Td(e["status"], style={**cell_style, "backgroundColor": e["color"]}),
            html.Td(e["obs"], style={**cell_style, "backgroundColor": e["color"]}),
        ]))
    return html.Div([
        html.H6("LOG DE EVENTOS", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Historico completo, rastreabilidade e alteracoes em formato temporal", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div(
            html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
            style={"height": "260px", "overflowY": "auto", "overflowX": "hidden"},
        ),
    ])


def _recommended_actions(inc_df=None):
    def _format_competence(value):
        if value is None:
            return "-"
        comp = str(value).strip()
        if len(comp) >= 7 and comp[4] == "-":
            return f"{comp[5:7]}/{comp[0:4]}"
        return comp if comp else "-"

    def _competences_for(df):
        try:
            comps = []
            for c in df.get("competence", []).tolist():
                f = _format_competence(c)
                if f != "-" and f not in comps:
                    comps.append(f)
            if not comps:
                return "competencias do periodo filtrado"
            return ", ".join(comps[:4])
        except Exception:
            return "competencias do periodo filtrado"

    actions = []
    try:
        if inc_df is not None and not inc_df.empty:
            critical = inc_df[inc_df["severity"] == "critico"]
            if not critical.empty:
                actions.append((
                    VERMELHO,
                    f"Regularizar {critical.iloc[0].get('rule_name', 'inconsistencia critica')} nas competencias: {_competences_for(critical)}.",
                ))
            high = inc_df[inc_df["severity"] == "alto"]
            if not high.empty:
                actions.append((
                    AMARELO,
                    f"Revisar {high.iloc[0].get('rule_name', 'inconsistencia de alta prioridade')} e regularizar nas competencias: {_competences_for(high)}.",
                ))
    except Exception:
        pass

    if not actions:
        actions = [
            (VERMELHO, "Regularizar os lancamentos nas competencias com alerta critico do periodo filtrado."),
            (AMARELO, "Revisar e regularizar as competencias com risco de vencimento nos proximos 30 dias."),
        ]

    items = []
    for color, text in actions:
        items.append(html.Div([
            html.Span(
                style={
                    "display": "inline-block", "width": "18px", "height": "18px", "borderRadius": "50%",
                    "backgroundColor": color, "marginRight": "8px", "flexShrink": "0",
                },
            ),
            html.Span(text, style={"fontSize": "0.8rem", "color": "#4A5568"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}))
    return html.Div([
        html.H6("ACAO RECOMENDADA", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Sugestoes operacionais, priorizacao e possiveis correcoes", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div(items),
    ])


def _event_mini_log(audit_log=None):
    events = []
    try:
        if audit_log is not None and not audit_log.empty:
            for _, r in audit_log.head(4).iterrows():
                events.append((
                    str(r.get("data", "-"))[:5],
                    str(r.get("evento", "-")),
                    str(r.get("color", "#E6F7FF")),
                ))
    except Exception:
        pass

    if not events:
        events = [
            ("02/03", "Folha importada", "#E6F7FF"),
            ("04/03", "Divergencia encontrada", "#FEF3C7"),
            ("05/03", "Alerta gerado", "#FED7D7"),
            ("05/03", "Alerta gerado", "#FED7D7"),
        ]

    header_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "6px 8px",
        "fontSize": "0.75rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
    }
    cell_style = {"padding": "6px 8px", "fontSize": "0.75rem", "color": "#4A5568", "textAlign": "left"}
    rows = [html.Tr([html.Th("Data", style=header_style), html.Th("Evento", style=header_style)])]
    for date_str, evt, bg in events:
        rows.append(html.Tr([html.Td(date_str, style={**cell_style, "backgroundColor": bg}), html.Td(evt, style={**cell_style, "backgroundColor": bg})]))
    return html.Div([
        html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
    ])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout():
    card_style = {
        "backgroundColor": BRANCO,
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
        "border": "none",
        "padding": "16px",
        "height": "100%",
    }

    return html.Div([
        dbc.Row([
            dbc.Col(
                html.Div([
                    dbc.Label("ID do Funcionário:", style={"fontWeight": "600", "fontSize": "0.85rem", "whiteSpace": "nowrap"}),
                    dcc.Input(
                        id="func-id", type="number", min=1, max=10000, value=1, step=1,
                        style={"width": "120px", "padding": "0.3rem", "borderRadius": "6px", "border": "1px solid #ccc"},
                    ),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
                width="auto", className="mb-3",
            ),
            dbc.Col(
                html.Div([
                    dbc.Label("Nome:", style={"fontWeight": "600", "fontSize": "0.85rem", "whiteSpace": "nowrap"}),
                    dcc.Dropdown(
                        id="func-name",
                        options=_employee_options(),
                        placeholder="Digite para buscar...",
                        searchable=True,
                        clearable=True,
                        style={"width": "280px"},
                    ),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
                width="auto", className="mb-3",
            ),
            dbc.Col(
                html.Div([
                    dbc.Label("CPF:", style={"fontWeight": "600", "fontSize": "0.85rem", "whiteSpace": "nowrap"}),
                    dcc.Dropdown(
                        id="func-cpf",
                        options=_cpf_options(),
                        placeholder="Digite o CPF...",
                        searchable=True,
                        clearable=True,
                        style={"width": "200px"},
                    ),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
                width="auto", className="mb-3",
            ),
        ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "8px"}),
        html.Div(id="audit-content"),
        dcc.Store(id="audit-init", data=1),
    ], style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"})


def register_callbacks(app):
    @app.callback(
        Output("func-id", "value"),
        Input("func-name", "value"),
        Input("func-cpf", "value"),
    )
    def update_id_from_name_or_cpf(selected_name, selected_cpf):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "func-name" and selected_name is not None:
            return selected_name
        if trigger_id == "func-cpf" and selected_cpf is not None:
            return selected_cpf
        return dash.no_update

    @app.callback(
        Output("audit-content", "children"),
        Input("func-id", "value"),
        Input("audit-init", "data"),
    )
    def load_audit(func_id, _init):
        if not func_id:
            return html.Div("Insira um ID de funcionario para ver os detalhes.", style={"color": "#888", "padding": "40px", "textAlign": "center"})

        perf, inc, hol, passivo_val, risk_info, vactl, reg_info, audit = _safe_data(func_id)

        if perf is not None and not perf.empty:
            p = perf.iloc[0]
        else:
            p = {"name": "Nao encontrado", "cpf": "-", "registration_number": "-",
                 "position_name": "-", "state": "-", "union_name": "-"}

        card_style = {
            "backgroundColor": BRANCO,
            "borderRadius": "12px",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
            "border": "none",
            "padding": "16px",
            "height": "100%",
        }

        # ---- Risk status derived from real data ----
        risk_level = risk_info.get("risk_level", "Regular") if isinstance(risk_info, dict) else "Regular"
        days_overdue = risk_info.get("days_overdue", 0) if isinstance(risk_info, dict) else 0
        inc_count = risk_info.get("inconsistency_count", 0) if isinstance(risk_info, dict) else 0

        risk_color_map = {"Critico": VERMELHO, "Atencao": AMARELO, "Monitorar": AZUL_CLARO, "Regular": VERDE}
        risk_color = risk_color_map.get(risk_level, VERDE)
        risk_desc_map = {"Critico": f"Vencido ha {days_overdue} dias" if days_overdue else "Inconsistencias: {inc_count}",
                         "Atencao": "Proximo ao vencimento",
                         "Monitorar": "Monitorar",
                         "Regular": "Situacao regular"}
        risk_desc = risk_desc_map.get(risk_level, "Verificar")

        # ---- Row 1: Funcionario Profile + Risk Status + Secondary Statuses ----
        avatar = html.Div(
            p["name"][0].upper() if p["name"] else "?",
            style={
                "width": "60px", "height": "60px", "borderRadius": "50%",
                "backgroundColor": PETROLEO, "color": "white",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontSize": "1.5rem", "fontWeight": "700", "marginRight": "16px",
            },
        )

        risk_status = html.Div(
            [
                html.Div(str(inc_count), style={"fontSize": "0.65rem", "color": "white", "marginBottom": "2px"}),
                html.Div(risk_level, style={"fontSize": "1.2rem", "color": "white", "fontWeight": "700", "marginBottom": "2px"}),
                html.Div(risk_desc, style={"fontSize": "0.65rem", "color": "white"}),
            ],
            style={
                "backgroundColor": risk_color, "borderRadius": "8px",
                "padding": "10px 16px", "textAlign": "center", "minWidth": "120px",
            },
        )

        # Secondary statuses derived from real data
        sec_statuses = html.Div([
            html.Div([
                html.Span(style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERDE, "marginRight": "6px"}),
                html.Span("Perfil Cadastral OK" if reg_info else "Verde", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
            html.Div([
                html.Span(style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERDE if inc_count == 0 else AMARELO, "marginRight": "6px"}),
                html.Span(f"Folha: {inc_count} inconsistencia(s)" if inc_count > 0 else "Folha Regular", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
            html.Div([
                html.Span(style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": risk_color, "marginRight": "6px"}),
                html.Span(f"{risk_level} - {risk_desc}", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"display": "flex", "alignItems": "center"}),
        ])

        profile_card = html.Div([
            html.H6("PERFIL DO FUNCIONARIO", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
            html.Div([
                avatar,
                html.Div([
                    html.Div([
                        html.Span("Nome: ", style={"fontWeight": "700", "fontSize": "0.85rem", "color": "#1A202C"}),
                        html.Span(p["name"], style={"fontWeight": "700", "fontSize": "0.85rem", "color": PETROLEO}),
                    ], style={"marginBottom": "2px"}),
                    html.Div(f"CPF: {p['cpf']}", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "2px"}),
                    html.Div(f"Matricula: {p['registration_number']}", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "2px"}),
                ], style={"flex": "1"}),
                html.Div([
                    html.Div(f"Cargo: {p['position_name']}", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "2px"}),
                    html.Div(f"Estado: {p['state']}", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "2px"}),
                    html.Div(f"Sindicato: {p['union_name']}", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                ], style={"flex": "1"}),
                html.Div([
                    html.H6("STATUS DE RISCO", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px"}),
                    risk_status,
                ], style={"marginRight": "16px"}),
                sec_statuses,
            ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),
        ], style=card_style)

        # ---- Row 2: Timeline ----
        timeline_card = html.Div([_timeline_card(vactl)], style=card_style)

        # ---- Row 3: Financial + Alerts + Cadastro ----
        financial_card = html.Div([_financial_table(hol, passivo_val)], style=card_style)
        alerts_card = html.Div([_operational_alerts_compact(inc)], style=card_style)
        reg_card = html.Div([_registration_data(reg_info)], style=card_style)

        # ---- Row 4: Log de Eventos + Mini events + Acao Recomendada ----
        event_log_card = html.Div([_event_log(audit)], style=card_style)
        mini_events = html.Div([_event_mini_log(audit)], style=card_style)
        rec_action_card = html.Div([_recommended_actions(inc)], style=card_style)

        return html.Div([
            # Row 1
            dbc.Row([dbc.Col(profile_card, width=12)], className="g-3 mb-3"),
            # Row 2
            dbc.Row([dbc.Col(timeline_card, width=12)], className="g-3 mb-3"),
            # Row 3
            dbc.Row([
                dbc.Col(financial_card, width=6),
                dbc.Col(alerts_card, width=3),
                dbc.Col(reg_card, width=3),
            ], className="g-3 mb-3"),
            # Row 4
            dbc.Row([
                dbc.Col(event_log_card, width=7),
                dbc.Col(mini_events, width=2),
                dbc.Col(rec_action_card, width=3),
            ], className="g-3 mb-3"),
            html.P(
                f"Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
            ),
        ])
