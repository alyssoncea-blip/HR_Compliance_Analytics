import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
import pandas as pd
from datetime import datetime
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import (perfil_funcionario, inconsistencias_funcionario,
                      reconciliacao_mensal_funcionario, pagamentos_funcionario,
                      banco_horas_funcionario, resumo_reconciliacao_funcionario)

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
        df = _query_parquet("""
            SELECT employee_id, name FROM read_parquet('data/silver/dim_employee.parquet')
            ORDER BY name LIMIT 500
        """)
        return [{"label": row["name"], "value": int(row["employee_id"])} for _, row in df.iterrows()]
    except Exception:
        return [{"label": "Erro ao carregar", "value": 0}]

def _cpf_options():
    try:
        df = _query_parquet("""
            SELECT employee_id, cpf, name FROM read_parquet('data/silver/dim_employee.parquet')
            ORDER BY cpf LIMIT 500
        """)
        return [{"label": f"{row['cpf']} - {row['name']}", "value": int(row["employee_id"])} for _, row in df.iterrows()]
    except Exception:
        return [{"label": "Erro ao carregar", "value": 0}]

# ---------------------------------------------------------------------------
# Fallback / mock data
# ---------------------------------------------------------------------------
def _mock_perfil():
    return pd.DataFrame([{
        "name": "João Silva", "cpf": "123.456.789-00",
        "registration_number": "1001", "position_name": "Analista de RH",
        "state": "MG", "union_name": "Sindágua-MG",
        "base_salary": 5500.0, "unit_name": "Unidade MG Central",
        "hire_date": "2020-03-15", "work_schedule": "44h semanais",
    }])

def _mock_reconciliacao_mensal():
    return pd.DataFrame([
        {"competence": "2024-03", "total_hours_worked": 220.0,
         "total_overtime_50_hours": 12.0, "total_overtime_70_hours": 4.0, "total_overtime_100_hours": 0.0,
         "payroll_overtime_50_hours": 8.0, "overtime_50_amount": 320.0,
         "overtime_70_amount": 180.0, "overtime_100_amount": 0.0,
         "total_night_hours": 0.0, "payroll_night_hours": 0.0, "night_shift_amount": 0.0,
         "periculosidade_amount": 1650.0, "insalubridade_amount": 0.0,
         "base_salary": 5500.0, "gross_total": 7650.0, "net_total": 6210.0,
         "hour_bank_balance": 8.0, "hour_bank_negative": 0, "hour_bank_exceeded": 0,
         "payment_expected": 7650.0, "payment_paid": 7650.0, "payment_divergence": 0.0,
         "has_payment_divergence": 0, "payment_matched": 1,
         "he_inconsistencies": 1, "night_shift_inconsistencies": 0,
         "periculosidade_inconsistencies": 0, "payment_inconsistencies": 0,
         "total_inconsistencies": 1},
        {"competence": "2024-02", "total_hours_worked": 200.0,
         "total_overtime_50_hours": 10.0, "total_overtime_70_hours": 2.0, "total_overtime_100_hours": 0.0,
         "payroll_overtime_50_hours": 10.0, "overtime_50_amount": 380.0,
         "overtime_70_amount": 95.0, "overtime_100_amount": 0.0,
         "total_night_hours": 0.0, "payroll_night_hours": 0.0, "night_shift_amount": 0.0,
         "periculosidade_amount": 1650.0, "insalubridade_amount": 0.0,
         "base_salary": 5500.0, "gross_total": 7625.0, "net_total": 6190.0,
         "hour_bank_balance": 6.0, "hour_bank_negative": 0, "hour_bank_exceeded": 0,
         "payment_expected": 7625.0, "payment_paid": 7500.0, "payment_divergence": 125.0,
         "has_payment_divergence": 1, "payment_matched": 0,
         "he_inconsistencies": 0, "night_shift_inconsistencies": 0,
         "periculosidade_inconsistencies": 0, "payment_inconsistencies": 1,
         "total_inconsistencies": 1},
    ])

def _mock_inconsistencias():
    return pd.DataFrame([
        {"use_case": 9, "rule_name": "Hora Extra não paga", "severity": "critico",
         "category": "Ponto", "financial_impact": 320.0,
         "competence": "2024-03",
         "detail": "4h extras registradas no ponto não constam na folha."},
        {"use_case": 21, "rule_name": "Pagamento duplicado", "severity": "critico",
         "category": "Folha", "financial_impact": 125.0,
         "competence": "2024-02",
         "detail": "Diferença de R$ 125 entre esperado e pago."},
    ])

def _mock_pagamentos():
    return pd.DataFrame([
        {"competence": "2024-03", "expected_amount": 7650.0, "paid_amount": 7650.0,
         "divergencia": 0.0, "payment_date": "2024-03-28", "payment_status": "paid"},
        {"competence": "2024-02", "expected_amount": 7625.0, "paid_amount": 7500.0,
         "divergencia": 125.0, "payment_date": "2024-02-28", "payment_status": "paid"},
    ])

def _mock_banco_horas():
    return pd.DataFrame([
        {"competence": "2024-03", "previous_balance": 6.0, "credits": 4.0, "debits": 2.0,
         "current_balance": 8.0, "negative_balance": False},
        {"competence": "2024-02", "previous_balance": 4.0, "credits": 5.0, "debits": 3.0,
         "current_balance": 6.0, "negative_balance": False},
    ])

def _mock_resumo():
    return {
        "total_inconsistencias": 2, "he_inconsistencias": 1, "payment_inconsistencias": 1,
        "divergencia_financeira": 125.0, "meses_com_divergencia": 1, "total_meses": 2,
        "saldo_medio_banco_horas": 7.0, "meses_banco_negativo": 0, "meses_banco_excedido": 0,
    }

def _safe_data(func_id):
    try:
        perf = perfil_funcionario(func_id)
        if perf.empty:
            raise ValueError("empty")
    except Exception:
        perf = _mock_perfil()

    try:
        rec = reconciliacao_mensal_funcionario(func_id)
        if rec.empty:
            raise ValueError("empty")
    except Exception:
        rec = _mock_reconciliacao_mensal()

    try:
        inc = inconsistencias_funcionario(func_id)
        if inc.empty:
            raise ValueError("empty")
    except Exception:
        inc = _mock_inconsistencias()

    try:
        pag = pagamentos_funcionario(func_id)
        if pag.empty:
            raise ValueError("empty")
    except Exception:
        pag = _mock_pagamentos()

    try:
        bh = banco_horas_funcionario(func_id)
        if bh.empty:
            raise ValueError("empty")
    except Exception:
        bh = _mock_banco_horas()

    try:
        res = resumo_reconciliacao_funcionario(func_id)
        resumo = res.iloc[0].to_dict() if not res.empty else _mock_resumo()
    except Exception:
        resumo = _mock_resumo()

    return perf, rec, inc, pag, bh, resumo


# ---------------------------------------------------------------------------
# UI Builders
# ---------------------------------------------------------------------------
def _profile_header(p):
    avatar = html.Div(
        p["name"][0].upper(),
        style={
            "width": "56px", "height": "56px", "borderRadius": "50%",
            "backgroundColor": PETROLEO, "color": "white",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "fontSize": "1.3rem", "fontWeight": "700", "marginRight": "14px",
            "flexShrink": "0",
        },
    )
    return html.Div([
        html.H6("FUNCIONÁRIO", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "6px"}),
        html.Div([
            avatar,
            html.Div([
                html.Div(p["name"], style={"fontWeight": "700", "fontSize": "1rem", "color": PETROLEO}),
                html.Div([
                    html.Span(f"CPF: {p['cpf']}", style={"marginRight": "16px"}),
                    html.Span(f"Matrícula: {p['registration_number']}"),
                ], style={"fontSize": "0.75rem", "color": "#4A5568", "marginTop": "2px"}),
            ]),
            html.Div([
                html.Div(f"Cargo: {p['position_name']}", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                html.Div(f"Unidade: {p.get('unit_name', '-')} / {p.get('state', '-')}", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                html.Div(f"Sindicato: {p['union_name']}", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            ], style={"marginLeft": "auto", "textAlign": "right"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
    ])

def _kpi_card(title, value, color=VERDE, subtitle=""):
    return html.Div([
        html.P(title, style={"fontSize": "0.65rem", "color": "#4A5568", "marginBottom": "2px", "fontWeight": "600"}),
        html.H3(value, style={"fontSize": "1.4rem", "fontWeight": "700", "color": color, "margin": "0"}),
        html.P(subtitle, style={"fontSize": "0.6rem", "color": "#888", "marginTop": "2px"}) if subtitle else None,
    ], style={"backgroundColor": "#F7FAFC", "borderRadius": "8px", "padding": "10px", "textAlign": "center", "height": "100%"})

def _monthly_comparison_table(rec: pd.DataFrame):
    header_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "5px 6px",
        "fontSize": "0.65rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "center",
    }
    cell_style = {"padding": "4px 6px", "fontSize": "0.65rem", "color": "#4A5568", "borderBottom": "1px solid #f7fafc", "textAlign": "center"}

    rows = [html.Tr([
        html.Th("Competência", style=header_style),
        html.Th("HE 50%", style=header_style),
        html.Th("HE 70%", style=header_style),
        html.Th("HE 100%", style=header_style),
        html.Th("HE Pagas 50%", style=header_style),
        html.Th("Valor HE", style=header_style),
        html.Th("Banco de\nHoras", style=header_style),
        html.Th("Divergência\nPagamento", style=header_style),
        html.Th("Inconsis.", style=header_style),
    ])]

    for _, r in rec.iterrows():
        div_color = VERMELHO if r["payment_divergence"] > 0 else VERDE
        rows.append(html.Tr([
            html.Td(r["competence"], style={**cell_style, "fontWeight": "600"}),
            html.Td(f'{r["total_overtime_50_hours"]:.0f}h', style=cell_style),
            html.Td(f'{r["total_overtime_70_hours"]:.0f}h', style=cell_style),
            html.Td(f'{r["total_overtime_100_hours"]:.0f}h', style=cell_style),
            html.Td(f'{r["payroll_overtime_50_hours"]:.0f}h', style=cell_style),
            html.Td(f'R$ {r["overtime_50_amount"] + r["overtime_70_amount"] + r["overtime_100_amount"]:.0f}', style=cell_style),
            html.Td(f'{r["hour_bank_balance"]:.0f}h', style={
                **cell_style, "color": VERMELHO if r["hour_bank_negative"] else VERDE,
                "fontWeight": "600",
            }),
            html.Td(f'R$ {r["payment_divergence"]:.0f}', style={**cell_style, "color": div_color, "fontWeight": "600"}),
            html.Td(str(int(r["total_inconsistencies"])), style={**cell_style, "color": VERMELHO if r["total_inconsistencies"] > 0 else VERDE}),
        ]))

    return html.Div([
        html.H6("Comparativo Mensal: Ponto vs Folha", style={"fontWeight": "700", "fontSize": "13px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Horas registradas no cartão de ponto vs horas pagas na folha por competência.", style={"fontSize": "10px", "color": "#4A5568", "marginBottom": "6px"}),
        html.Div(
            html.Table(rows, style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.65rem"}),
            style={"overflowX": "auto"},
        ),
    ])

def _inconsistencies_table(inc: pd.DataFrame):
    header_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "5px 6px",
        "fontSize": "0.65rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
    }
    cell_style = {"padding": "4px 6px", "fontSize": "0.65rem", "color": "#4A5568", "borderBottom": "1px solid #f7fafc", "textAlign": "left"}

    rows = [html.Tr([
        html.Th("Competência", style=header_style),
        html.Th("Regra", style=header_style),
        html.Th("Categoria", style=header_style),
        html.Th("Severidade", style={**header_style, "textAlign": "center"}),
        html.Th("Impacto", style={**header_style, "textAlign": "right"}),
        html.Th("Detalhe", style=header_style),
    ])]

    for _, r in inc.iterrows():
        sev_color = VERMELHO if r["severity"] in ("critico", "critical") else AMARELO
        rows.append(html.Tr([
            html.Td(r.get("competence", "-"), style=cell_style),
            html.Td(r["rule_name"], style={**cell_style, "fontWeight": "600"}),
            html.Td(r["category"], style=cell_style),
            html.Td(html.Span(r["severity"], style={"backgroundColor": sev_color, "color": "white", "padding": "1px 8px", "borderRadius": "8px", "fontSize": "0.6rem", "fontWeight": "700"}), style={**cell_style, "textAlign": "center"}),
            html.Td(f'R$ {r["financial_impact"]:.0f}', style={**cell_style, "textAlign": "right", "fontWeight": "600", "color": VERMELHO if r["financial_impact"] > 0 else "#888"}),
            html.Td(r.get("detail", ""), style=cell_style),
        ]))

    return html.Div([
        html.H6("Inconsistências Detectadas", style={"fontWeight": "700", "fontSize": "13px", "color": "#1A202C", "marginBottom": "4px"}),
        html.Div(
            html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
            style={"maxHeight": "220px", "overflowY": "auto"},
        ),
    ])

def _payment_card(pag: pd.DataFrame):
    items = []
    for _, r in pag.iterrows():
        div_color = VERMELHO if r["divergencia"] > 0 else VERDE
        div_text = f'R$ {r["divergencia"]:.0f}' if r["divergencia"] != 0 else "OK"
        items.append(html.Div([
            html.Span(r["competence"], style={"fontWeight": "600", "fontSize": "0.7rem", "minWidth": "60px"}),
            html.Span(f'Esperado: R$ {r["expected_amount"]:.0f}', style={"fontSize": "0.7rem", "color": "#4A5568"}),
            html.Span(f'Pago: R$ {r["paid_amount"]:.0f}', style={"fontSize": "0.7rem", "color": "#4A5568"}),
            html.Span(div_text, style={"fontWeight": "700", "fontSize": "0.75rem", "color": div_color, "marginLeft": "auto"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px", "padding": "3px 0", "borderBottom": "1px solid #f7fafc"}))

    return html.Div([
        html.H6("Pagamentos vs Expectativa", style={"fontWeight": "700", "fontSize": "13px", "color": "#1A202C", "marginBottom": "6px"}),
        html.Div(items, style={"maxHeight": "180px", "overflowY": "auto"}),
    ])

def _hour_bank_card(bh: pd.DataFrame):
    items = []
    for _, r in bh.iterrows():
        bal_color = VERMELHO if r["negative_balance"] else VERDE
        items.append(html.Div([
            html.Span(r["competence"], style={"fontWeight": "600", "fontSize": "0.7rem", "minWidth": "60px"}),
            html.Span(f'Crédito: {r["credits"]:.0f}h', style={"fontSize": "0.7rem", "color": "#4A5568"}),
            html.Span(f'Débito: {r["debits"]:.0f}h', style={"fontSize": "0.7rem", "color": "#4A5568"}),
            html.Span(f'Saldo: {r["current_balance"]:.0f}h', style={"fontWeight": "700", "fontSize": "0.75rem", "color": bal_color, "marginLeft": "auto"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px", "padding": "3px 0", "borderBottom": "1px solid #f7fafc"}))

    return html.Div([
        html.H6("Banco de Horas", style={"fontWeight": "700", "fontSize": "13px", "color": "#1A202C", "marginBottom": "6px"}),
        html.Div(items, style={"maxHeight": "180px", "overflowY": "auto"}),
    ])


def _render_reconciliation(func_id):
    if not func_id:
        return html.Div("Insira um ID de funcionario para ver a reconciliacao.", style={"color": "#888", "padding": "40px", "textAlign": "center"})

    perf, rec, inc, pag, bh, resumo = _safe_data(func_id)
    p = perf.iloc[0]

    card_style = {
        "backgroundColor": BRANCO,
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
        "border": "none",
        "padding": "16px",
        "height": "100%",
    }

    profile = html.Div([_profile_header(p)], style=card_style)

    def _num(key, default=0.0):
        value = resumo.get(key, default)
        return default if pd.isna(value) else value

    total_inc = int(_num("total_inconsistencias", 0))
    div_fin = float(_num("divergencia_financeira", 0.0))
    saldo_bh = float(_num("saldo_medio_banco_horas", 0.0))
    meses_div = int(_num("meses_com_divergencia", 0))
    total_meses = int(_num("total_meses", 1))
    pct_conforme = round((1 - meses_div / total_meses) * 100) if total_meses > 0 else 100

    conforme_color = VERDE if pct_conforme >= 80 else (AMARELO if pct_conforme >= 50 else VERMELHO)
    inc_color = VERDE if total_inc == 0 else (AMARELO if total_inc <= 3 else VERMELHO)
    div_color = VERDE if div_fin == 0 else (AMARELO if div_fin <= 500 else VERMELHO)
    bh_color = VERDE if saldo_bh >= 0 else VERMELHO

    kpi_row = dbc.Row([
        dbc.Col(_kpi_card("Conformidade", f"{pct_conforme}%", conforme_color, f"{meses_div}/{total_meses} meses com divergencia"), width=3),
        dbc.Col(_kpi_card("Inconsistencias", str(total_inc), inc_color, "total detectadas"), width=3),
        dbc.Col(_kpi_card("Divergencia Financeira", f"R$ {div_fin:.0f}", div_color, "esperado vs pago"), width=3),
        dbc.Col(_kpi_card("Banco de Horas", f"{saldo_bh:.0f}h", bh_color, "saldo medio"), width=3),
    ], className="g-2 mb-3")

    comp_table = html.Div([_monthly_comparison_table(rec)], style=card_style)
    inc_table = html.Div([_inconsistencies_table(inc)], style=card_style)
    pay_card = html.Div([_payment_card(pag)], style=card_style)
    bh_card = html.Div([_hour_bank_card(bh)], style=card_style)

    return html.Div([
        dbc.Row([dbc.Col(profile, width=12)], className="g-3 mb-3"),
        kpi_row,
        dbc.Row([dbc.Col(comp_table, width=12)], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(inc_table, width=7),
            dbc.Col(pay_card, width=3),
            dbc.Col(bh_card, width=2),
        ], className="g-3 mb-3"),
        html.P(
            f"Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
        ),
    ], style={"backgroundColor": CINZA})


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout():
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.Div([
                    dbc.Label("ID do Funcionário:", style={"fontWeight": "600", "fontSize": "0.85rem", "whiteSpace": "nowrap"}),
                    dcc.Input(id="reconc-func-id", type="number", min=1, max=10000, value=1, step=1,
                              style={"width": "120px", "padding": "0.3rem", "borderRadius": "6px", "border": "1px solid #ccc"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
                width="auto", className="mb-3",
            ),
            dbc.Col(
                html.Div([
                    dbc.Label("Nome:", style={"fontWeight": "600", "fontSize": "0.85rem", "whiteSpace": "nowrap"}),
                    dcc.Dropdown(id="reconc-func-name", options=_employee_options(),
                                 placeholder="Digite para buscar...", searchable=True, clearable=True,
                                 style={"width": "280px"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
                width="auto", className="mb-3",
            ),
            dbc.Col(
                html.Div([
                    dbc.Label("CPF:", style={"fontWeight": "600", "fontSize": "0.85rem", "whiteSpace": "nowrap"}),
                    dcc.Dropdown(id="reconc-func-cpf", options=_cpf_options(),
                                 placeholder="Digite o CPF...", searchable=True, clearable=True,
                                 style={"width": "200px"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
                width="auto", className="mb-3",
            ),
        ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "8px"}),
        html.Div(id="reconc-content", children=_render_reconciliation(1)),
    ], style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"})


def register_callbacks(app):
    @app.callback(
        Output("reconc-func-id", "value"),
        Input("reconc-func-name", "value"),
        Input("reconc-func-cpf", "value"),
    )
    def update_id_from_name_or_cpf(selected_name, selected_cpf):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "reconc-func-name" and selected_name is not None:
            return selected_name
        if trigger_id == "reconc-func-cpf" and selected_cpf is not None:
            return selected_cpf
        return dash.no_update

    @app.callback(
        Output("reconc-content", "children"),
        Input("reconc-func-id", "value"),
    )
    def load_reconciliation(func_id):
        return _render_reconciliation(func_id)
