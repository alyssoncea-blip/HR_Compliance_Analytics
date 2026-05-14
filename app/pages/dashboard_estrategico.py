import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import (kpi_ferias_vencidas, kpi_passivo_ferias, kpi_proximos_vencimento,
                      evolucao_risco, status_geral, ranking_unidades, is_demo_mode)

# ---------------------------------------------------------------------------
# Fallback data helpers
# ---------------------------------------------------------------------------
def _safe_data():
    """Fetch data. Fallbacks only when HRA_DEMO_MODE=true."""
    demo_mode = is_demo_mode()
    try:
        vac = kpi_ferias_vencidas().iloc[0]
        pct = round(vac.vencidas / vac.total * 100, 1) if vac.total > 0 else 0
    except Exception:
        if not demo_mode:
            raise
        pct = 12.4

    try:
        pas = kpi_passivo_ferias().iloc[0]
        passivo = pas.passivo_total
    except Exception:
        if not demo_mode:
            raise
        passivo = 1_245_000

    try:
        prox = kpi_proximos_vencimento().iloc[0]
        qtd_prox = int(prox.qtd)
        crit = int(prox.critico)
        aten = int(prox.atencao)
    except Exception:
        if not demo_mode:
            raise
        qtd_prox = 184
        crit = 55
        aten = 80

    try:
        df_ev = evolucao_risco()
        if df_ev.empty:
            raise ValueError("empty")
    except Exception:
        if not demo_mode:
            raise
        df_ev = pd.DataFrame(
            {
                "year": [2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2025],
                "month": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "competencia": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07", "2024-08", "2024-09", "2025-01"],
                "funcionarios_afetados": [80, 110, 145, 115, 165, 205, 260, 190, 230, 255],
                "impacto_total": [200_000, 350_000, 500_000, 400_000, 600_000, 800_000, 1_200_000, 900_000, 1_100_000, 1_250_000],
            }
        )

    try:
        df_rank = ranking_unidades()
        if df_rank.empty:
            raise ValueError("empty")
    except Exception:
        if not demo_mode:
            raise
        df_rank = pd.DataFrame()

    try:
        df_status = status_geral()
        if df_status.empty:
            raise ValueError("empty")
    except Exception:
        if not demo_mode:
            raise
        df_status = pd.DataFrame(
            {"status": ["Regular", "Atenção", "Crítico"], "qtd": [120, 45, 19]}
        )

    # Calculate month-over-month variation from risk evolution data
    try:
        if len(df_ev) >= 2:
            last = df_ev["funcionarios_afetados"].iloc[-1]
            prev = df_ev["funcionarios_afetados"].iloc[-2]
            var_pct = round((last - prev) / prev * 100, 1) if prev != 0 else 0.0
        else:
            var_pct = 0.0
    except Exception:
        if not demo_mode:
            raise
        var_pct = 2.3

    return pct, passivo, qtd_prox, crit, aten, df_ev, df_status, var_pct, df_rank


# ---------------------------------------------------------------------------
# Plotly figure builders
# ---------------------------------------------------------------------------
def _gauge_fig(value: float):
    needle_color = VERDE if value < 10 else (AMARELO if value <= 20 else VERMELHO)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": "%",
                "font": {"size": 42, "color": needle_color, "family": "Inter, sans-serif"},
                "valueformat": ".1f",
            },
            title={
                "text": "Funcionários com férias vencidas",
                "font": {"size": 12, "color": "#4A5568"},
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 30],
                    "showticklabels": False,
                },
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "#e2e8f0",
                "bar": {"color": needle_color},
                "steps": [
                    {"range": [0, 10], "color": "rgba(123,211,137,0.35)"},
                    {"range": [10, 20], "color": "rgba(244,211,94,0.35)"},
                    {"range": [20, 100], "color": "rgba(238,99,82,0.35)"},
                ],
                "threshold": {
                    "line": {"color": needle_color, "width": 4},
                    "thickness": 0.8,
                    "value": value,
                },
            },
            domain={"x": [0.05, 0.95], "y": [0.25, 0.95]},
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=220,
    )
    return fig


def _sparkline_fig(df: pd.DataFrame = None):
    if df is not None and not df.empty and "competencia" in df.columns and "impacto_total" in df.columns:
        _MESES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
                  7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
        def _label(c):
            try:
                parts = c.split("-")
                ano = str(int(parts[0]))[-2:]
                mes = _MESES[int(parts[1])]
                return f"{mes}/{ano}"
            except Exception:
                return c
        meses = [_label(c) for c in df["competencia"].tolist()]
        values = df["impacto_total"].tolist()
    else:
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        values = [850, 920, 880, 950, 1_020, 1_100, 1_080, 1_150, 1_220, 1_180, 1_250, 1_245]
    fig = go.Figure(
        go.Scatter(
            x=meses,
            y=values,
            mode="lines+markers",
            fill="tozeroy",
            line=dict(color=AZUL_CLARO, width=2),
            marker=dict(color=VERMELHO, size=7, line=dict(width=2, color="white")),
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=20),
        xaxis=dict(
            tickfont=dict(size=9, color="#888"),
            tickangle=0,
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(visible=False),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=100,
        showlegend=False,
    )
    return fig


def _risk_evolution_fig(df: pd.DataFrame):
    df = df.copy()
    df["growth"] = df["funcionarios_afetados"].pct_change() * 100
    df["growth_str"] = df["growth"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
    df["liability_str"] = df["impacto_total"].apply(lambda x: f"R$ {x:,.0f}".replace(",", "."))

    _MESES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
              7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

    def _label(row):
        try:
            parts = row["competencia"].split("-")
            ano = str(int(parts[0]))[-2:]
            mes = _MESES[int(parts[1])]
            return f"{mes}/{ano}"
        except Exception:
            return row["competencia"]

    df["label"] = df.apply(_label, axis=1)

    fig = go.Figure(
        go.Scatter(
            x=df["label"],
            y=df["funcionarios_afetados"],
            mode="lines+markers",
            fill="tozeroy",
            fillcolor="rgba(95, 168, 211, 0.15)",
            line=dict(color=AZUL_CLARO, width=2),
            marker=dict(color=VERMELHO, size=10, line=dict(width=2, color="white")),
            customdata=df[["growth_str", "liability_str"]],
            hovertemplate="<b>Quantity:</b> %{y}<br><b>Growth:</b> %{customdata[0]}<br><b>Passivo:</b> %{customdata[1]}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=50, r=20, t=50, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=300,
        xaxis=dict(
                title="Tempo",
                            gridcolor="#f0f0f0",
                            linecolor="#ddd",
                            tickfont=dict(size=11, color="#4A5568"),
                            titlefont=dict(size=12, color="#4A5568"),
                        ),
                        yaxis=dict(
                            title="Nº de funcionários vencidos",
                            gridcolor="#f0f0f0",
                            linecolor="#ddd",
                            tickfont=dict(size=11, color="#4A5568"),
                            titlefont=dict(size=12, color="#4A5568"),
                        ),
        title=dict(
            text="EVOLUÇÃO DO RISCO",
            font=dict(size=16, color="#1A202C", family="Inter, sans-serif"),
            x=0,
            xanchor="left",
        ),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#ccc", font=dict(color="#333", size=12)),
    )
    return fig


def _donut_fig(df: pd.DataFrame):
    color_map = {"Regular": VERDE, "Atenção": AMARELO, "Crítico": VERMELHO, "Critico": VERMELHO, "Atencao": AMARELO}
    colors = [color_map.get(s, "#ccc") for s in df["status"]]
    fig = go.Figure(
        go.Pie(
            labels=df["status"],
            values=df["qtd"],
            hole=0.6,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            textinfo="none",
            hovertemplate="%{label}<br>%{value}<extra></extra>",
            sort=False,
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=280,
        title=dict(
            text="STATUS GERAL",
            font=dict(size=16, color="#1A202C", family="Inter, sans-serif"),
            x=0,
            xanchor="left",
        ),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            font=dict(size=11, color="#4A5568"),
        ),
        annotations=[
            dict(
                text="<b>Total</b><br>{}".format(df["qtd"].sum()),
                x=0.5,
                y=0.5,
                font_size=14,
                showarrow=False,
                font=dict(color="#1A202C"),
            )
        ],
    )
    return fig


# ---------------------------------------------------------------------------
# UI builders
# ---------------------------------------------------------------------------
def _top_units_table(df_rank: pd.DataFrame):
    sev_map = {"critica": ("CRÍTICO", VERMELHO), "alta": ("ATENÇÃO", AMARELO), "media": ("MÉDIO", AZUL_CLARO), "baixa": ("OK", VERDE)}
    header_style = {
        "borderBottom": "2px solid #e2e8f0",
        "padding": "8px",
        "fontSize": "0.85rem",
        "fontWeight": "700",
        "color": "#1A202C",
        "textAlign": "left",
    }
    cell_style = {
        "padding": "8px",
        "fontSize": "0.85rem",
        "color": "#4A5568",
        "borderBottom": "1px solid #f7fafc",
        "textAlign": "left",
    }
    rows = [
        html.Tr([
            html.Th("Unidade", style=header_style),
            html.Th("% férias vencidas", style=header_style),
            html.Th("Passivo", style=header_style),
            html.Th("Status", style={**header_style, "textAlign": "center"}),
        ])
    ]
    for _, d in df_rank.head(8).iterrows():
        sev, sev_color = sev_map.get(d["severity"], ("OK", VERDE))
        pct_val = float(d["pct_vencidas"])
        liab_val = float(d["passivo"])
        rows.append(html.Tr([
            html.Td(html.Span(d["unidade"], style={"fontWeight": "600"}), style=cell_style),
            html.Td(f"{pct_val:.1f}%".replace(".", ","), style={**cell_style, "color": VERMELHO if pct_val >= 20 else "#4A5568"}),
            html.Td(f"R$ {liab_val:,.0f}".replace(",", "."), style={**cell_style, "fontWeight": "600"}),
            html.Td(
                html.Span(sev, style={
                    "backgroundColor": sev_color, "color": "white",
                    "padding": "2px 12px", "borderRadius": "10px",
                    "fontSize": "0.7rem", "fontWeight": "700",
                    "display": "inline-block", "minWidth": "28px", "textAlign": "center",
                }),
                style={**cell_style, "textAlign": "center"},
            ),
        ]))
    return html.Div([
        html.H6("TOP UNIDADES CRÍTICAS", style={"fontWeight": "700", "fontSize": "16px", "color": "#1A202C", "marginBottom": "12px"}),
        html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
    ])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout(filters=None):
    pct, passivo, qtd_prox, crit, aten, df_ev, df_status, var_pct, df_rank = _safe_data()

    # Apply filters to ranking data
    if filters and df_rank is not None and not df_rank.empty:
        if filters.get("estado"):
            df_rank = df_rank[df_rank["estado"] == filters["estado"]]
        if filters.get("unidade"):
            df_rank = df_rank[df_rank["unidade"] == filters["unidade"]]
        if filters.get("sindicato"):
            df_rank = df_rank[df_rank["estado"].isin(
                {"Sindágua-MG": "MG", "Sindágua-RJ": "RJ", "Sindágua-RN": "RN"}.get(filters["sindicato"], [])
            )]

    card_style = {
        "backgroundColor": BRANCO,
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
        "border": "none",
        "padding": "20px",
        "height": "100%",
    }

    # ---- KPI 1: Gauge de Férias Vencidas ----
    kpi1 = html.Div(
        [
            html.Div(
                [
                    html.H6(
                        "% FÉRIAS VENCIDAS",
                        style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "0"},
                    ),
                    html.Div(
                        f"{'▲' if var_pct >= 0 else '▼'} {var_pct:+.1f}%",
                        style={
                            "position": "absolute",
                            "top": "4px",
                            "right": "4px",
                            "backgroundColor": "#fff0f0" if var_pct >= 0 else "#e6f7e6",
                            "color": VERMELHO if var_pct >= 0 else VERDE,
                            "padding": "2px 8px",
                            "borderRadius": "6px",
                            "fontSize": "0.75rem",
                            "fontWeight": "700",
                            "whiteSpace": "nowrap",
                            "zIndex": "10",
                            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                        },
                    ),
                ],
                style={"position": "relative", "minHeight": "28px", "overflow": "visible"},
            ),
            dcc.Graph(
                figure=_gauge_fig(pct),
                config={"displayModeBar": False},
                style={"height": "220px", "overflow": "visible"},
            ),
            html.Div(
                [
                    html.Span(
                        style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERDE, "marginRight": "4px"}
                    ),
                    html.Span("0% - 10%", style={"fontSize": "0.75rem", "color": "#4A5568", "marginRight": "12px"}),
                    html.Span(
                        style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": AMARELO, "marginRight": "4px"}
                    ),
                    html.Span("10% - 20%", style={"fontSize": "0.75rem", "color": "#4A5568", "marginRight": "12px"}),
                    html.Span(
                        style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "4px"}
                    ),
                    html.Span(">20%", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                ],
                style={"textAlign": "center", "marginTop": "0px", "position": "relative", "zIndex": "10"},
            ),
        ],
        style={**card_style, "minHeight": "280px"},
    )

    # ---- KPI 2: Passivo Estimado ----
    passivo_str = f"R$ {passivo:,.0f}".replace(",", ".")
    kpi2 = html.Div(
        [
            html.H6(
                "PASSIVO ESTIMADO FÉRIAS EM DOBRO",
                style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"},
            ),
            html.H2(
                passivo_str,
                style={
                    "color": PETROLEO,
                    "fontWeight": "700",
                    "fontSize": "2.5rem",
                    "margin": "0",
                    "letterSpacing": "-1px",
                },
            ),
            html.P(
                "Passivo financeiro estimado",
                style={"color": "#4A5568", "fontSize": "0.85rem", "marginBottom": "12px"},
            ),
            dcc.Graph(
                figure=_sparkline_fig(df_ev),
                config={"displayModeBar": False},
                style={"height": "110px"},
            ),
            html.P(
                "Evolução do passivo nos últimos 12 meses",
                style={"color": "#4A5568", "fontSize": "0.75rem", "textAlign": "center", "marginTop": "4px"},
            ),
        ],
        style={**card_style, "border": f"2px solid {VERMELHO}", "minHeight": "280px"},
    )

    # ---- KPI 3: Próximos ao Vencimento ----
    rest = max(0, qtd_prox - crit - aten)
    total_bar = qtd_prox if qtd_prox > 0 else 1
    p_crit = crit / total_bar * 100
    p_aten = aten / total_bar * 100
    p_reg = rest / total_bar * 100

    kpi3 = html.Div(
        [
            html.H6(
                "FUNCIONÁRIOS PRÓXIMOS AO VENCIMENTO",
                style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"},
            ),
            html.H2(
                f"{qtd_prox}",
                style={"color": PETROLEO, "fontWeight": "700", "fontSize": "3rem", "margin": "0", "textAlign": "center"},
            ),
            html.P(
                "Funcionários próximos ao vencimento",
                style={"color": "#4A5568", "fontSize": "0.85rem", "textAlign": "center", "marginBottom": "16px"},
            ),
            html.Div(
                [
                    html.Div(style={"flex": f"{p_crit}", "backgroundColor": VERMELHO, "height": "16px"}),
                    html.Div(style={"flex": f"{p_aten}", "backgroundColor": AMARELO, "height": "16px"}),
                    html.Div(style={"flex": f"{p_reg}", "backgroundColor": AZUL_CLARO, "height": "16px"}),
                ],
                style={"display": "flex", "borderRadius": "4px", "overflow": "hidden", "marginBottom": "12px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "4px"}
                            ),
                            html.Span("<30 dias", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    html.Div(
                        [
                            html.Span(
                                style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": AMARELO, "marginRight": "4px"}
                            ),
                            html.Span("30-60 dias", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    html.Div(
                        [
                            html.Span(
                                style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "50%", "backgroundColor": AZUL_CLARO, "marginRight": "4px"}
                            ),
                            html.Span("60-90 dias", style={"fontSize": "0.75rem", "color": "#4A5568"}),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-around"},
            ),
        ],
        style={**card_style, "minHeight": "280px"},
    )

    # ---- Row 2: Evolução do Risco ----
    row2 = html.Div(
        [
            dcc.Graph(
                figure=_risk_evolution_fig(df_ev),
                config={"displayModeBar": False},
                style={"height": "300px"},
            )
        ],
        style=card_style,
    )

    # ---- Row 3: Table + Donut ----
    row3_left = html.Div([_top_units_table(df_rank)], style=card_style)
    row3_right = html.Div(
        [
            dcc.Graph(
                figure=_donut_fig(df_status),
                config={"displayModeBar": False},
                style={"height": "280px"},
            )
        ],
        style=card_style,
    )

    return html.Div(
        [
            dbc.Row(
                [dbc.Col(kpi1, width=4), dbc.Col(kpi2, width=5), dbc.Col(kpi3, width=3)],
                className="g-3 mb-3",
            ),
            dbc.Row([dbc.Col(row2, width=12)], className="g-3 mb-3"),
            dbc.Row(
                [dbc.Col(row3_left, width=8), dbc.Col(row3_right, width=4)],
                className="g-3 mb-3",
            ),
            html.P(
                f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
            ),
        ],
        style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"},
    )


def register_callbacks(app):
    pass
