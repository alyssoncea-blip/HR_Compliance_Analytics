import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import (headcount, piramide_salarial, faixa_etaria,
                      turnover_anual, equidade_salarial,
                      movimentacao_mensal_12m, saude_organizacional)

# ---------------------------------------------------------------------------
# Fallback / mock data
# ---------------------------------------------------------------------------
def _safe_headcount():
    try:
        hc = headcount().iloc[0]
        return {
            "total": int(hc.total) if hasattr(hc, "total") else 4280,
            "masculino": int(hc.masculino) if hasattr(hc, "masculino") else 2500,
            "feminino": int(hc.feminino) if hasattr(hc, "feminino") else 1780,
            "idade_media": float(hc.idade_media) if hasattr(hc, "idade_media") else 35.2,
            "tempo_medio_anos": float(hc.tempo_medio_anos) if hasattr(hc, "tempo_medio_anos") else 7.2,
        }
    except Exception:
        return {"total": 4280, "masculino": 2500, "feminino": 1780, "idade_media": 35.2, "tempo_medio_anos": 7.2}


def _safe_faixa_etaria():
    try:
        df = faixa_etaria()
        if df.empty:
            raise ValueError("empty")
        return df
    except Exception:
        return pd.DataFrame({
            "faixa": ["18-25", "26-35", "36-45", "46-55", "56-65", "66+"],
            "qtd": [320, 1450, 1280, 890, 260, 80],
        })


def _safe_piramide():
    try:
        df = piramide_salarial()
        if df.empty:
            raise ValueError("empty")
        return df
    except Exception:
        return pd.DataFrame({
            "cargo": ["Gerente", "Coordenador", "Analista Sr", "Analista Pl", "Analista Jr", "Tecnico", "Assistente", "Operador", "Estagiario"],
            "gender": ["M", "F", "M", "F", "M", "F", "M", "F", "M"],
            "salario_medio": [18500, 17200, 12500, 11800, 9500, 9200, 6500, 5800, 3200],
            "qtd": [45, 32, 120, 145, 280, 310, 450, 520, 180],
        })


def _safe_turnover():
    try:
        df = turnover_anual()
        if df.empty:
            raise ValueError("empty")
        return float(df.iloc[0].taxa)
    except Exception:
        return 8.4


def _safe_equidade():
    try:
        df = equidade_salarial()
        if df.empty:
            raise ValueError("empty")
        return float(df.iloc[0].razao)
    except Exception:
        return 0.94


def _safe_movimentacao():
    try:
        df = movimentacao_mensal_12m()
        if df.empty:
            raise ValueError("empty")
        return df
    except Exception:
        return pd.DataFrame({
            "mes_num": list(range(1, 13)),
            "admissoes": [12, 15, 18, 14, 20, 22, 25, 18, 16, 14, 12, 10],
            "desligamentos": [8, 6, 10, 7, 9, 8, 12, 10, 7, 6, 8, 5],
            "promocoes": [3, 4, 5, 3, 6, 5, 4, 5, 3, 4, 3, 2],
            "ausencias": [2, 3, 4, 3, 5, 4, 3, 4, 2, 3, 2, 2],
        })


def _safe_saude():
    try:
        df = saude_organizacional()
        if df.empty:
            raise ValueError("empty")
        r = df.iloc[0]
        return {
            "taxa_absenteismo": float(r.taxa_absenteismo),
            "taxa_licenca": float(r.taxa_licenca),
            "media_he_mensal": float(r.media_he_mensal),
            "indice_saturacao": float(r.indice_saturacao),
        }
    except Exception:
        return {"taxa_absenteismo": 4.2, "taxa_licenca": 2.1, "media_he_mensal": 12, "indice_saturacao": 8}

# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------
def _turnover_gauge(value: float):
    needle_color = VERDE if value < 10 else (AMARELO if value <= 15 else VERMELHO)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": "%",
                "font": {"size": 24, "color": PETROLEO, "family": "Inter, sans-serif"},
                "valueformat": ".1f",
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 25],
                    "tickwidth": 1,
                    "tickcolor": "#ccc",
                    "visible": False,
                },
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "#e2e8f0",
                "steps": [
                    {"range": [0, 10], "color": "rgba(123,211,137,0.30)"},
                    {"range": [10, 15], "color": "rgba(244,211,94,0.30)"},
                    {"range": [15, 25], "color": "rgba(238,99,82,0.30)"},
                ],
                "threshold": {
                    "line": {"color": needle_color, "width": 3},
                    "thickness": 0.7,
                    "value": value,
                },
            },
            domain={"x": [0.1, 0.9], "y": [0.2, 0.9]},
        )
    )
    fig.update_layout(
        margin=dict(l=5, r=5, t=10, b=5),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=120,
    )
    return fig


def _gender_donut(hc=None):
    if hc and hc.get("masculino") and hc.get("feminino"):
        total = hc["masculino"] + hc["feminino"]
        pct_m = round(hc["masculino"] / total * 100) if total else 58
        pct_f = round(hc["feminino"] / total * 100) if total else 42
    else:
        pct_m, pct_f = 58, 42

    labels = ["Masculino", "Feminino"]
    values = [pct_m, pct_f]
    colors_list = [AZUL_CLARO, "#E88DAB"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.65,
        marker=dict(colors=colors_list, line=dict(color="white", width=2)),
        textinfo="none", hovertemplate="%{label}<br>%{value}%<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        height=160, showlegend=False,
    )
    return fig


def _age_bar_fig(df: pd.DataFrame):
    fig = go.Figure(go.Bar(
        x=df["qtd"], y=df["faixa"], orientation="h",
        marker_color=PETROLEO,
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    fig.update_layout(
        margin=dict(l=60, r=10, t=10, b=10),
        paper_bgcolor="white", plot_bgcolor="white",
        height=160,
        xaxis=dict(visible=False),
        yaxis=dict(
            gridcolor="#f0f0f0", linecolor="#ddd",
            tickfont=dict(size=11, color="#1A202C"),
            categoryorder="array", categoryarray=list(reversed(df["faixa"].tolist())),
        ),
        showlegend=False,
    )
    return fig


def _salary_pyramid_fig(df_piramide=None):
    try:
        if df_piramide is not None and not df_piramide.empty:
            male_df = df_piramide[df_piramide["gender"] == "M"].copy()
            female_df = df_piramide[df_piramide["gender"] == "F"].copy()
            all_cargos = sorted(set(df_piramide["cargo"].unique()), key=lambda x: df_piramide[df_piramide["cargo"] == x]["salario_medio"].max(), reverse=True)
            cargos = all_cargos[:8] if len(all_cargos) > 8 else all_cargos
            male_vals = [int(male_df[male_df["cargo"] == c]["salario_medio"].values[0]) // 1000 if c in male_df["cargo"].values else 0 for c in cargos]
            female_vals = [int(female_df[female_df["cargo"] == c]["salario_medio"].values[0]) // 1000 if c in female_df["cargo"].values else 0 for c in cargos]
        else:
            raise ValueError("no data")
    except Exception:
        cargos = ["Gerente", "Coordenador", "Analista Sr", "Analista Pl", "Analista Jr"]
        male_vals = [85, 78, 72, 65, 58]
        female_vals = [75, 82, 68, 70, 55]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=cargos, x=male_vals, orientation="h", name="Masculino",
        marker_color=AZUL_CLARO, hovertemplate="%{y}<br>Masculino: %{x}k<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=cargos, x=female_vals, orientation="h", name="Feminino",
        marker_color="#E88DAB", hovertemplate="%{y}<br>Feminino: %{x}k<extra></extra>",
    ))
    fig.update_layout(
        barmode="group",
        margin=dict(l=100, r=40, t=10, b=10),
        paper_bgcolor="white", plot_bgcolor="white",
        height=180,
        xaxis=dict(visible=False),
        yaxis=dict(
            gridcolor="#f0f0f0", linecolor="#ddd",
            tickfont=dict(size=11, color="#1A202C"),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=10, color="#4A5568"),
        ),
        showlegend=True,
    )
    if cargos and male_vals and female_vals:
        pass
    return fig


def _movement_fig(df_mov=None):
    try:
        if df_mov is not None and not df_mov.empty:
            meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            admissions = [int(df_mov[df_mov["mes_num"] == i]["admissoes"].values[0]) if i in df_mov["mes_num"].values else 0 for i in range(1, 13)]
            desligamentos = [int(df_mov[df_mov["mes_num"] == i]["desligamentos"].values[0]) if i in df_mov["mes_num"].values else 0 for i in range(1, 13)]
            promotions = [int(df_mov[df_mov["mes_num"] == i]["promocoes"].values[0]) if i in df_mov["mes_num"].values else 0 for i in range(1, 13)]
            absences = [int(df_mov[df_mov["mes_num"] == i]["ausencias"].values[0]) if i in df_mov["mes_num"].values else 0 for i in range(1, 13)]
        else:
            raise ValueError("no data")
    except Exception:
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        admissions = [12, 15, 18, 14, 20, 22, 25, 18, 16, 14, 12, 10]
        desligamentos = [8, 6, 10, 7, 9, 8, 12, 10, 7, 6, 8, 5]
        promotions = [3, 4, 5, 3, 6, 5, 4, 5, 3, 4, 3, 2]
        absences = [2, 3, 4, 3, 5, 4, 3, 4, 2, 3, 2, 2]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=meses, y=admissions, mode="lines", name="Admissoes", line=dict(color=AZUL_CLARO, width=2), fill="tozeroy", fillcolor="rgba(95,168,211,0.1)"))
    fig.add_trace(go.Scatter(x=meses, y=desligamentos, mode="lines", name="Desligamentos", line=dict(color=VERMELHO, width=2)))
    fig.add_trace(go.Scatter(x=meses, y=promotions, mode="lines", name="Promocoes", line=dict(color=VERDE, width=2)))
    fig.add_trace(go.Scatter(x=meses, y=absences, mode="lines", name="Ausencias/Licencas", line=dict(color="#888", width=2, dash="dash")))
    fig.update_layout(
        margin=dict(l=40, r=20, t=10, b=30),
        paper_bgcolor="white", plot_bgcolor="white",
        height=220,
        xaxis=dict(gridcolor="#f0f0f0", linecolor="#ddd", tickfont=dict(size=10, color="#4A5568")),
        yaxis=dict(gridcolor="#f0f0f0", linecolor="#ddd", tickfont=dict(size=10, color="#4A5568")),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=10, color="#4A5568"),
        ),
        showlegend=True,
    )
    return fig


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout():
    hc = _safe_headcount()
    df_fx = _safe_faixa_etaria()
    df_piramide = _safe_piramide()
    df_mov = _safe_movimentacao()
    saude = _safe_saude()
    turnover_val = _safe_turnover()
    equidade_val = _safe_equidade()

    card_style = {
        "backgroundColor": BRANCO,
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
        "border": "none",
        "padding": "16px",
        "height": "100%",
    }

    equidade_bg = AMARELO if equidade_val < 0.95 else VERDE

    # ---- Row 1: Workforce KPIs ----
    kpi1 = html.Div([
        html.H6("TOTAL DE FUNCIONARIOS", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px"}),
        html.Div([
            html.H2(f"{hc['total']:,}".replace(",", "."), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
            html.Div([
                html.Span("▲ +1.2%", style={"color": VERDE, "fontWeight": "700", "fontSize": "0.8rem"}),
                html.Br(),
                html.Span("vs. mes anterior", style={"color": "#4A5568", "fontSize": "0.7rem"}),
            ], style={"backgroundColor": "#F0FFF4", "padding": "4px 8px", "borderRadius": "6px", "marginLeft": "12px"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
        html.P("Funcionarios ativos", style={"fontSize": "0.75rem", "color": "#4A5568"}),
    ], style=card_style)

    kpi2 = html.Div([
        html.H6("ROTATIVIDADE", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        html.Div([
            html.Div([
                html.H2(f"{turnover_val:.1f}%", style={"fontSize": "2.2rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
                html.P("Rotatividade anual", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "8px"}),
                html.Div([
                    html.Span(style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERDE, "marginRight": "4px"}),
                    html.Span("<10%", style={"fontSize": "0.75rem", "color": "#4A5568", "marginRight": "12px"}),
                    html.Span(style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": AMARELO, "marginRight": "4px"}),
                    html.Span("10-15%", style={"fontSize": "0.75rem", "color": "#4A5568", "marginRight": "12px"}),
                    html.Span(style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "4px"}),
                    html.Span(">15%", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                ]),
            ]),
            html.Div([
                dcc.Graph(figure=_turnover_gauge(turnover_val), config={"displayModeBar": False}, style={"height": "120px"}),
            ], style={"position": "absolute", "top": "-15px", "right": "0", "width": "50%"}),
        ], style={"position": "relative", "display": "flex", "alignItems": "flex-start"}),
    ], style={**card_style, "minHeight": "180px", "position": "relative"})

    kpi3 = html.Div([
        html.H6("TEMPO MEDIO NA EMPRESA", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px"}),
        html.H2(f"{hc['tempo_medio_anos']:.1f} anos", style={"fontSize": "2.2rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
        html.P("Tempo medio de permanencia na empresa", style={"fontSize": "0.75rem", "color": "#4A5568"}),
    ], style=card_style)

    kpi4 = html.Div([
        html.H6("INDICE DE EQUIDADE SALARIAL", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px"}),
        html.Div([
            html.H2(f"{equidade_val:.2f}", style={"fontSize": "2.2rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
            html.Div([
                html.Div("amarelo se < 0,95", style={"fontSize": "0.65rem", "color": "#1A202C"}),
                html.Div("verde se >= 0,95", style={"fontSize": "0.65rem", "color": "#1A202C"}),
            ], style={"backgroundColor": equidade_bg, "padding": "4px 8px", "borderRadius": "6px", "marginLeft": "12px"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
        html.P("Razao salarial Feminino/Masculino (1,0 = equidade)", style={"fontSize": "0.75rem", "color": "#4A5568"}),
    ], style=card_style)

    # ---- Row 2: Distribution and Profile ----
    demo_card = html.Div([
        html.H6("DISTRIBUICAO DEMOGRAFICA", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Distribuicao por genero, faixa etaria, tempo de servico e nivel de escolaridade", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        html.Div([
            dbc.Col(dcc.Graph(figure=_gender_donut(hc), config={"displayModeBar": False}, style={"height": "160px"}), width=5),
            dbc.Col(dcc.Graph(figure=_age_bar_fig(df_fx), config={"displayModeBar": False}, style={"height": "160px"}), width=7),
        ], style={"display": "flex"}),
    ], style=card_style)

    salary_card = html.Div([
        html.H6("PIRAMIDE SALARIAL POR CARGO E GENERO", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Salario medio por cargo, diferenca entre generos e identificacao de disparidades", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        dcc.Graph(figure=_salary_pyramid_fig(df_piramide), config={"displayModeBar": False}, style={"height": "200px"}),
    ], style=card_style)

    # ---- Row 3: Movement and Saude Organizacional ----
    movement_card = html.Div([
        html.H6("MOVIMENTACAO DE PESSOAS", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Admissoes, desligamentos, promocoes, transferencias e licencas nos ultimos 12 meses", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        dcc.Graph(figure=_movement_fig(df_mov), config={"displayModeBar": False}, style={"height": "220px"}),
    ], style=card_style)

    health_cards = html.Div([
        html.H6("SAUDE ORGANIZACIONAL (INDICADORES)", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        dbc.Row([
            dbc.Col(html.Div([
                html.P("Taxa de absenteismo", style={"fontSize": "0.7rem", "color": "#1A202C", "marginBottom": "4px"}),
                html.H4(f"{saude['taxa_absenteismo']:.1f}%", style={"fontSize": "1.6rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
            ], style={"backgroundColor": "#C6F6D5", "borderRadius": "8px", "padding": "12px", "height": "100%"}), width=6),
            dbc.Col(html.Div([
                html.P("Taxa de licenca medica", style={"fontSize": "0.7rem", "color": "#1A202C", "marginBottom": "4px"}),
                html.H4(f"{saude['taxa_licenca']:.1f}%", style={"fontSize": "1.6rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
            ], style={"backgroundColor": "#C6F6D5", "borderRadius": "8px", "padding": "12px", "height": "100%"}), width=6),
        ], className="g-2 mb-2"),
        dbc.Row([
            dbc.Col(html.Div([
                html.P("Media de horas extras/funcionario", style={"fontSize": "0.7rem", "color": "#1A202C", "marginBottom": "4px"}),
                html.H4(f"{saude['media_he_mensal']:.0f}h/mes", style={"fontSize": "1.6rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
            ], style={"backgroundColor": "#FEF3C7", "borderRadius": "8px", "padding": "12px", "height": "100%"}), width=6),
            dbc.Col(html.Div([
                html.P("Indice de saturacao (banco de horas elevado)", style={"fontSize": "0.7rem", "color": "#1A202C", "marginBottom": "4px"}),
                html.H4(f"{saude['indice_saturacao']:.0f}%", style={"fontSize": "1.6rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
            ], style={"backgroundColor": "#FEF3C7", "borderRadius": "8px", "padding": "12px", "height": "100%"}), width=6),
        ], className="g-2"),
    ], style=card_style)

    return html.Div([
        dbc.Row([dbc.Col(kpi1, width=3), dbc.Col(kpi2, width=3), dbc.Col(kpi3, width=3), dbc.Col(kpi4, width=3)], className="g-3 mb-3"),
        dbc.Row([dbc.Col(demo_card, width=6), dbc.Col(salary_card, width=6)], className="g-3 mb-3"),
        dbc.Row([dbc.Col(movement_card, width=6), dbc.Col(health_cards, width=6)], className="g-3 mb-3"),
        html.P(
            f"Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
        ),
    ], style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"})


def register_callbacks(app):
    pass
