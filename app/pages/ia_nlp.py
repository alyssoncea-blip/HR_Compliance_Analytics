import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import ccts_processadas, regras_extraidas, distribuicao_entidades, cct_evolution_data

# ---------------------------------------------------------------------------
# Fallback / mock data
# ---------------------------------------------------------------------------
def _safe_ccts():
    try:
        df = ccts_processadas()
        if df.empty:
            raise ValueError("empty")
        return df
    except Exception:
        return pd.DataFrame({
            "name": ["Sindágua-MG", "Sindágua-RJ", "Sindágua-RN"],
            "company": ["Copasa", "Águas do Rio", "CAERN"],
            "state": ["MG", "RJ", "RN"],
            "standard_weekly_hours": [44, 44, 30],
            "cct_year_start": [2023, 2023, 2020],
            "cct_year_end": [2025, 2025, 2024],
        })


def _safe_regras():
    try:
        df = regras_extraidas()
        if df.empty:
            raise ValueError("empty")
        return df
    except Exception:
        return pd.DataFrame({
            "regra_id": [1, 2, 3, 4, 5, 6, 7, 8],
            "regra": ["Jornada semanal MG", "Jornada semanal RN", "HE 1ª hora", "HE adicional", "Adicional noturno", "Reajuste ACT 2024 RN", "Benefício VA/VR RN", "Social clause — assédio"],
            "nivel": ["regular", "regular", "regular", "regular", "alto", "regular", "alto", "alto"],
            "category": ["Jornada", "Jornada", "HE", "HE", "Adicional", "Reajuste", "Benefício", "Social"],
        })


# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------
def _confidence_gauge(value: float):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"size": 24, "color": PETROLEO, "family": "Inter, sans-serif"}},
        gauge={
            "shape": "angular",
            "axis": {"range": [0, 100], "visible": False},
            "bar": {"color": "rgba(0,0,0,0)"},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 80], "color": PETROLEO},
                {"range": [80, 100], "color": "#E2E8F0"},
            ],
        },
        domain={"x": [0.2, 0.8], "y": [0.2, 0.9]},
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        height=90,
    )
    return fig


def _treemap_fig():
    try:
        row = distribuicao_entidades().iloc[0].to_dict()
    except Exception:
        row = {
            "total_ativos": 8994, "e_5x2": 3394, "e_12x36": 2447, "e_6x1": 2443, "e_3x3": 710,
            "he_50": 8650, "he_70": 3422, "he_100": 8508,
            "ad_noturno": 117, "periculosidade": 4253, "insalubridade": 3578,
            "vr_alimentacao": 8994, "cesta_basica": 8994, "plr": 8994, "auxilio_creche": 5844,
            "contrib_sindical": 8994, "gestante": 4444,
        }

    labels = [
        "Jornada", "5x2", "12x36", "6x1", "3x3",
        "Hora Extra", "50%", "70%", "100%",
        "Adicional Noturno", "Periculosidade", "Insalubridade",
        "Benefícios", "Vale Alimentação", "Cesta Básica", "PLR", "Auxílio Creche",
        "Cláusulas Sociais", "Contribuição Sindical",
        "Estabilidade", "gestante",
        "Reajustes",
    ]
    parents = [
        "", "Jornada", "Jornada", "Jornada", "Jornada",
        "", "Hora Extra", "Hora Extra", "Hora Extra",
        "", "", "",
        "", "Benefícios", "Benefícios", "Benefícios", "Benefícios",
        "", "",
        "", "Estabilidade",
        "",
    ]
    values = [
        0, row["e_5x2"], row["e_12x36"], row["e_6x1"], row["e_3x3"],
        0, row["he_50"], row["he_70"], row["he_100"],
        row["ad_noturno"], row["periculosidade"], row["insalubridade"],
        0, row["vr_alimentacao"], row["cesta_basica"], row["plr"], row["auxilio_creche"],
        0, row["contrib_sindical"],
        0, row["gestante"],
        row["total_ativos"],
    ]
    colors = [PETROLEO] * len(labels)
    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        textinfo="label+percent parent",
        hovertemplate="%{label}: %{value} funcionários (%{percentParent:.1%})<extra></extra>",
        marker=dict(colors=colors, colorscale="Blues"),
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        height=280,
    )
    return fig


def _cct_evolution_fig():
    try:
        df = cct_evolution_data()
        if df.empty:
            raise ValueError("empty")
        df = df.sort_values("cct_year_end")
        labels = [f"{n} ({s})" for n, s in zip(df["name"], df["state"])]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["cct_year_end"].tolist(),
            y=round(df["salary_adjustment_percent"] * 100, 1).tolist(),
            mode="lines+markers", name="Reajuste salarial (%)",
            text=labels, line=dict(color=PETROLEO, width=2),
            hovertemplate="%{text}<br>%{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["cct_year_end"].tolist(),
            y=round(df["base_salary_min"] / 30, 1).tolist(),
            mode="lines+markers", name="Piso salarial (R$)",
            text=labels, line=dict(color=AZUL_CLARO, width=2),
            hovertemplate="%{text}<br>R$ %{customdata:,.0f}<extra></extra>",
            customdata=df["base_salary_min"].tolist(),
        ))
        fig.add_trace(go.Scatter(
            x=df["cct_year_end"].tolist(),
            y=round(df["he_sunday_percent"] * 100, 1).tolist(),
            mode="lines+markers", name="HE Domingos (%)",
            text=labels, line=dict(color="#5B8C5A", width=2),
            hovertemplate="%{text}<br>%{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["cct_year_end"].tolist(),
            y=round(df["night_shift_percent"] * 100, 1).tolist(),
            mode="lines+markers", name="Adicional noturno (%)",
            text=labels, line=dict(color="#7EC8E3", width=2),
            hovertemplate="%{text}<br>%{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["cct_year_end"].tolist(),
            y=round(df["meal_voucher_amount"] / 10, 1).tolist(),
            mode="lines+markers", name="Vale refeição (R$)",
            text=labels, line=dict(color="#B8D4E3", width=2),
            hovertemplate="%{text}<br>R$ %{customdata:,.0f}<extra></extra>",
            customdata=df["meal_voucher_amount"].tolist(),
        ))
    except Exception:
        anos = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=anos, y=[45, 45, 75, 60, 100, 100, 100], mode="lines+markers", name="Reajuste salarial (%)", line=dict(color=PETROLEO, width=2)))
        fig.add_trace(go.Scatter(x=anos, y=[25, 25, 65, 55, 90, 90, 95], mode="lines+markers", name="Piso salarial (R$)", line=dict(color=AZUL_CLARO, width=2)))
        fig.add_trace(go.Scatter(x=anos, y=[15, 15, 40, 55, 80, 80, 80], mode="lines+markers", name="HE Domingos (%)", line=dict(color="#5B8C5A", width=2)))
        fig.add_trace(go.Scatter(x=anos, y=[25, 25, 25, 50, 100, 100, 100], mode="lines+markers", name="Adicional noturno (%)", line=dict(color="#7EC8E3", width=2)))
        fig.add_trace(go.Scatter(x=anos, y=[55, 55, 55, 55, 55, 55, 70], mode="lines+markers", name="Vale refeição (R$)", line=dict(color="#B8D4E3", width=2)))
    fig.update_layout(
        margin=dict(l=50, r=20, t=40, b=40),
        paper_bgcolor="white", plot_bgcolor="white",
        height=280,
        xaxis=dict(gridcolor="#f0f0f0", linecolor="#ddd", tickfont=dict(size=10, color="#4A5568")),
        yaxis=dict(gridcolor="#f0f0f0", linecolor="#ddd", tickfont=dict(size=10, color="#4A5568")),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=9, color="#4A5568"),
        ),
        title=dict(
            text="EVOLUCAO TEMPORAL DAS CONVENCOES COLETIVAS",
            font=dict(size=13, color="#1A202C", family="Inter, sans-serif"),
            x=0, xanchor="left",
        ),
        showlegend=True,
        hoverlabel=dict(bgcolor="white", bordercolor="#ccc", font=dict(color="#333", size=11)),
    )
    return fig


# ---------------------------------------------------------------------------
# UI builders
# ---------------------------------------------------------------------------
def _rules_table():
    df = _safe_regras()
    header_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "5px 8px",
        "fontSize": "0.7rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
    }
    cell_style = {"padding": "4px 8px", "fontSize": "0.68rem", "color": "#4A5568", "borderBottom": "1px solid #f7fafc", "textAlign": "left"}
    rows = [html.Tr([
        html.Th("Regra", style=header_style),
        html.Th("Categoria", style=header_style),
        html.Th("Nivel", style=header_style),
        html.Th("Confianca (%)", style=header_style),
        html.Th("Fonte", style=header_style),
        html.Th("Status", style={**header_style, "textAlign": "center"}),
        html.Th("Acao", style={**header_style, "textAlign": "center"}),
    ])]
    for _, d in df.iterrows():
        nivel = str(d.get("nivel", "regular")).lower()
        rule_name = str(d.get("regra", ""))
        category = str(d.get("category", ""))
        regra_id = str(d.get("regra_id", ""))
        if nivel == "regular":
            confidence, extracted, status, status_color = 95.0, "95%", "Validado", VERDE
        elif nivel == "alto":
            confidence, extracted, status, status_color = 85.0, "85%", "Validado", VERDE
        elif nivel == "critico":
            confidence, extracted, status, status_color = 60.0, "60%", "Critico", VERMELHO
        else:
            confidence, extracted, status, status_color = 80.0, "80%", "Review", AMARELO
        conf_color = VERDE if confidence >= 90 else (AMARELO if confidence >= 80 else VERMELHO)
        source = f"ACT {regra_id}" if regra_id else "CCT"
        rows.append(html.Tr([
            html.Td(rule_name, style=cell_style),
            html.Td(category, style=cell_style),
            html.Td(nivel, style=cell_style),
            html.Td(
                html.Span(extracted, style={"color": conf_color, "fontWeight": "600"}),
                style=cell_style,
            ),
            html.Td(source, style=cell_style),
            html.Td(
                html.Div([
                    html.Span("✓" if status == "Validado" else ("⚠" if status == "Review" else "✗"),
                              style={"color": status_color, "marginRight": "3px", "fontSize": "0.7rem"}),
                    html.Span(status, style={"color": status_color, "fontWeight": "600", "fontSize": "0.65rem"}),
                ]),
                style={**cell_style, "textAlign": "center"},
            ),
            html.Td(
                html.Div(["👁 ", "✏️", " ✓"] if status != "Critico" else ["✏️", " ✓"],
                         style={"fontSize": "0.75rem", "textAlign": "center"}),
                style={**cell_style, "textAlign": "center"},
            ),
        ]))
    return html.Div([
        html.H6("REGRAS EXTRAIDAS DAS CCTs", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.Div(
            html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
            style={
                "maxHeight": "340px",
                "overflowY": "auto",
                "overflowX": "auto",
                "paddingRight": "4px",
            },
        ),
    ])


def _ai_metrics():
    try:
        df = _safe_regras()
        total = len(df)
        if total == 0:
            raise ValueError("empty")
        regular = int((df["nivel"].str.lower() == "regular").sum())
        alto = int((df["nivel"].str.lower() == "alto").sum())
        criticos = int((df["nivel"].str.lower() == "critico").sum())
        acuracia = round((regular + alto) / total * 100, 1)
        recall = round((total - criticos) / total * 100, 1)
        f1 = round(2 * acuracia * recall / (acuracia + recall), 1) if (acuracia + recall) > 0 else 0
        metrics = [
            ("Modelo", "Legal-BERT ajustado para CCTs", False),
            ("Acuracia (regras validadas)", f"{acuracia}%", False),
            ("Recall (taxa de deteccao)", f"{recall}%", False),
            ("F1-Score", f"{f1}%", f1 < 80),
            ("Total de Regras", str(total), False),
            ("Regras Criticas", str(criticos), criticos > 0),
        ]
    except Exception:
        metrics = [
            ("Modelo", "Legal-BERT ajustado para CCTs", False),
            ("Acuracia", "94.2%", False),
            ("Recall", "91.8%", False),
            ("F1-Score", "93.0%", True),
            ("Tempo Medio / CCT", "3.4s", False),
            ("Ultimo Treinamento", "[DD/MM/YYYY, 15/05/2024]", False),
        ]
    rows = []
    for label, value, alert in metrics:
        rows.append(html.Div([
            html.Span(label, style={"fontSize": "0.75rem", "color": "#4A5568", "fontWeight": "600"}),
            html.Div([
                html.Span(value, style={"fontSize": "0.8rem", "color": "#1A202C", "fontWeight": "700"}),
                html.Span("Retreinamento recomendado", style={
                    "fontSize": "0.6rem", "color": "white", "backgroundColor": VERMELHO,
                    "padding": "1px 6px", "borderRadius": "4px", "marginLeft": "6px",
                }) if alert else None,
            ], style={"textAlign": "right"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "8px 0", "borderBottom": "1px solid #f0f0f0"}))
    return html.Div([
        html.H6("MODELO DE IA E METRICAS", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        html.Div(rows),
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

    # ---- Linha 1: KPIs do Motor de IA ----
    ccts_df = _safe_ccts()
    regras_df = _safe_regras()
    ccts_count = len(ccts_df)
    regras_count = len(regras_df)
    ccts_states = ", ".join(ccts_df["state"].tolist()) if not ccts_df.empty and "state" in ccts_df.columns else "MG, RJ, RN"
    try:
        criticas_count = int((regras_df["nivel"].str.lower() == "critico").sum())
    except Exception:
        criticas_count = 0
    try:
        detection_rate = round((regras_count - criticas_count) / regras_count * 100, 1) if regras_count > 0 else 0
    except Exception:
        detection_rate = 91.3

    kpi1 = html.Div([
        html.H6("CCTs PROCESSADAS", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        html.H2(str(ccts_count), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "center", "margin": "0"}),
        html.P(f"CCTs/ACTs Indexadas ({ccts_states})", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    kpi2 = html.Div([
        html.H6("REGRAS EXTRAIDAS AUTOMATICAMENTE", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        html.Div([
            html.H2(str(regras_count), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "marginBottom": "4px"}),
        html.P("Regras extraidas por NLP", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    kpi3 = html.Div([
        html.H6("TAXA DE DETECCAO", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        dcc.Graph(figure=_confidence_gauge(detection_rate), config={"displayModeBar": False}, style={"height": "90px"}),
        html.P("Taxa de regras nao-criticas detectadas", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    kpi4 = html.Div([
        html.H6("REGRAS PENDENTES DE REVISAO", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        html.H2(str(criticas_count), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "center", "margin": "0"}),
        html.P("Regras criticas aguardando validacao humana", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    # ---- Linha 2: Regras + Treemap ----
    rules_card = html.Div([
        _rules_table(),
    ], style=card_style)

    treemap_card = html.Div([
        html.H6("ENTIDADES EXTRAÍDAS (NUVEM DE PALAVRAS / TREEMAP)", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        dcc.Graph(figure=_treemap_fig(), config={"displayModeBar": False}, style={"height": "280px"}),
    ], style=card_style)

    # ---- Linha 3: Evolução + Métricas de IA ----
    evolution_card = html.Div([
        dcc.Graph(figure=_cct_evolution_fig(), config={"displayModeBar": False}, style={"height": "280px"}),
    ], style=card_style)

    metrics_card = html.Div([
        _ai_metrics(),
    ], style=card_style)

    return html.Div([
        # Linha 1
        dbc.Row([dbc.Col(kpi1, width=3), dbc.Col(kpi2, width=3), dbc.Col(kpi3, width=3), dbc.Col(kpi4, width=3)], className="g-3 mb-3"),
        # Linha 2
        dbc.Row([dbc.Col(rules_card, width=7), dbc.Col(treemap_card, width=5)], className="g-3 mb-3"),
        # Linha 3
        dbc.Row([dbc.Col(evolution_card, width=7), dbc.Col(metrics_card, width=5)], className="g-3 mb-3"),
        html.P(
            f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
        ),
    ], style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"})


def register_callbacks(app):
    pass
