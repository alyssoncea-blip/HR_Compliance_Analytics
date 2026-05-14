import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import distribuicao_estado, ranking_unidades, resumo_reconciliacao, ccts_processadas
from app.data import window_alert_data, payment_month_data, jornada_donut_data, compliance_table_data

# ---------------------------------------------------------------------------
# Fallback data
# ---------------------------------------------------------------------------
def _safe_data():
    try:
        df_est = distribuicao_estado()
        if df_est.empty:
            raise ValueError("empty")
    except Exception:
        df_est = pd.DataFrame({
            "estado": ["MG", "RJ", "RN", "SP"],
            "funcionarios": [178, 145, 98, 65],
            "pct_vencidas": [55, 65, 35, 20],
            "passivo": [52000, 85000, 18000, 12000],
            "ranking": [1, 2, 3, 4],
        })

    try:
        df_rank = ranking_unidades()
        if df_rank.empty:
            raise ValueError("empty")
    except Exception:
        df_rank = pd.DataFrame({
            "unidade": ["Sede Copasa BH", "Unid. Regional Copasa Sul", "Sede Águas do Rio", "Unid. Regional Copasa Centro", "Unid. Regional Copasa Triângulo", "Unidade Rio Norte", "Unidade Rio Sul"],
            "estado": ["MG", "MG", "RJ", "MG", "MG", "RJ", "RJ"],
            "func": [473, 478, 477, 456, 465, 449, 412],
            "pct_vencidas": [21.6, 21.2, 19.9, 22.3, 18.9, 19.6, 23.6],
            "passivo": [1225050, 1308635, 1174475, 1196170, 1209719, 1117882, 959186],
            "passivo_medio": [465, 464, 498, 458, 417, 439, 460],
            "ocorrencias": [22678, 22504, 22430, 21827, 21748, 20925, 19149],
        })
        def _calc_severity(row):
            pct = row["pct_vencidas"]
            pas = row["passivo"]
            if pct >= 25 or pas >= 500_000: return "critica"
            elif pct >= 15 or pas >= 100_000: return "alta"
            elif pct >= 10 or pas >= 50_000: return "media"
            return "baixa"
        df_rank["severity"] = df_rank.apply(_calc_severity, axis=1)

    try:
        res = resumo_reconciliacao().iloc[0]
        resumo = {
            "total_inconsistencias": int(res.total_inconsistencias),
            "pct_critico": float(res.pct_critico),
            "impacto_total": float(res.impacto_total),
            "funcionarios_afetados": int(res.funcionarios_afetados),
        }
    except Exception:
        resumo = {
            "total_inconsistencias": 1788,
            "pct_critico": 35.5,
            "impacto_total": 24_400,
            "funcionarios_afetados": 1250,
        }

    return df_est, df_rank, resumo


# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------
def _distribuicao_estado_fig(df: pd.DataFrame):
    colors = [VERMELHO if p >= 50 else AZUL_CLARO for p in df["pct_vencidas"]]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["funcionarios"],
            y=df["estado"],
            orientation="h",
            marker_color=colors,
            text=[f"{p}%" for p in df["pct_vencidas"]],
            textposition="outside",
            textfont=dict(size=12, color="#1A202C"),
            hovertemplate="<b>%{y}</b><br>Total funcionários: %{customdata[0]}<br>% vencidas: %{customdata[1]}%<br>Passivo estimado: R$ %{customdata[2]:,.0f}<br>Ranking nacional: %{customdata[3]}<extra></extra>",
            customdata=df[["funcionarios", "pct_vencidas", "passivo", "ranking"]].values,
        )
    )
    fig.update_layout(
        margin=dict(l=60, r=80, t=40, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=260,
        xaxis=dict(visible=False),
        yaxis=dict(
            gridcolor="#f0f0f0",
            linecolor="#ddd",
            tickfont=dict(size=12, color="#1A202C"),
        ),
        showlegend=False,
        title=dict(
            text="Concentração de férias vencidas",
            font=dict(size=11, color="#4A5568"),
            x=0,
            xanchor="left",
        ),
    )
    return fig


def _window_alert_fig():
    try:
        df = window_alert_data()
        if df.empty:
            raise ValueError("empty")
        categories = sorted(df["state"].unique(), reverse=True)
        pivot = df.pivot(index="state", columns="janela", values="pct").fillna(0)
        window_order = ["<30 dias", "30-60 dias", "60-90 dias", "Em dia"]
        available = [w for w in window_order if w in pivot.columns]
        data = {w: pivot[w].tolist() for w in available}
        colors = {"<30 dias": VERMELHO, "30-60 dias": AMARELO, "60-90 dias": AZUL_CLARO, "Em dia": VERDE}
        y_cats = list(reversed(categories)) if categories else list(reversed(categories))
    except Exception:
        categories = ["Unidade", "Estado e Sindicato", "Funcionários", "Estado", "Sindicato"]
        data = {
            "<30 dias": [35, 30, 25, 20, 15],
            "30-60 dias": [25, 25, 25, 25, 25],
            "60-90 dias": [20, 20, 20, 25, 20],
            "Em dia": [20, 25, 30, 30, 40],
        }
        colors = {"<30 dias": VERMELHO, "30-60 dias": AMARELO, "60-90 dias": AZUL_CLARO, "Em dia": VERDE}
        y_cats = ["Unidade", "Estado e Sindicato", "Funcionários", "Estado", "Sindicato"]
    fig = go.Figure()
    for label, values in data.items():
        fig.add_trace(
            go.Bar(
                y=categories,
                x=values,
                orientation="h",
                name=label,
                marker_color=colors[label],
                hovertemplate="%{y}<br>%{data.name}: %{x}%<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        margin=dict(l=100, r=20, t=40, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=260,
        xaxis=dict(visible=False),
        yaxis=dict(
            gridcolor="#f0f0f0",
            linecolor="#ddd",
            tickfont=dict(size=11, color="#1A202C"),
            categoryorder="array",
            categoryarray=list(reversed(categories)),
        ),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="right",
            x=1,
            font=dict(size=10, color="#4A5568"),
        ),
        title=dict(
            text="Proximidade de prazos",
            font=dict(size=11, color="#4A5568"),
            x=0,
            xanchor="left",
        ),
    )
    return fig


def _ranking_table(df: pd.DataFrame):
    header_style = {
        "borderBottom": "2px solid #e2e8f0",
        "padding": "6px 8px",
        "fontSize": "0.8rem",
        "fontWeight": "700",
        "color": "#1A202C",
        "textAlign": "left",
    }
    cell_style = {
        "padding": "6px 8px",
        "fontSize": "0.8rem",
        "color": "#4A5568",
        "borderBottom": "1px solid #f7fafc",
        "textAlign": "left",
    }
    rows = [html.Tr([
        html.Th("Unidade", style=header_style),
        html.Th("Funcionários", style=header_style),
        html.Th("% vencidas", style=header_style),
        html.Th("Passivo", style=header_style),
        html.Th("Criticidade", style={**header_style, "textAlign": "center"}),
    ])]
    for _, d in df.head(7).iterrows():
        sev_color = {"alta": VERMELHO, "baixa": VERDE, "media": AMARELO, "critica": VERMELHO}.get(d["severity"], "#888")
        bar_width = d["pct_vencidas"]
        rows.append(html.Tr([
            html.Td(d["unidade"], style=cell_style),
            html.Td(str(d["func"]), style=cell_style),
            html.Td(
                html.Div([
                    html.Div(style={
                        "width": f"{bar_width}%", "height": "8px",
                        "backgroundColor": AZUL_CLARO if bar_width < 50 else "#FEB2B2",
                        "borderRadius": "4px",
                    }),
                    html.Span(f" {bar_width}%", style={"fontSize": "0.75rem"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
                style=cell_style,
            ),
            html.Td(f"R$ {d['passivo']:,.0f}", style=cell_style),
            html.Td(
                html.Span(
                    d["severity"].upper(),
                    style={
                        "backgroundColor": sev_color, "color": "white",
                        "padding": "2px 10px", "borderRadius": "10px",
                        "fontSize": "0.7rem", "fontWeight": "700",
                    },
                ),
                style={**cell_style, "textAlign": "center"},
            ),
        ]))
    return html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"})


def _payment_mês_fig():
    try:
        df = payment_month_data()
        if df.empty or len(df) < 2:
            raise ValueError("empty")
        month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        mêss = [month_names[int(r["month"]) - 1] for _, r in df.iterrows()]
        values = df["employee_count"].tolist()
        liabilities = (df["passivo_total"] / 1000).apply(lambda x: round(x, 1)).tolist()
        growth = [0.0]
        for i in range(1, len(values)):
            if values[i - 1] and values[i - 1] != 0:
                growth.append(round((values[i] - values[i - 1]) / values[i - 1] * 100, 1))
            else:
                growth.append(0.0)
        marker_threshold = 4000
    except Exception:
        mêss = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        values = [80, 75, 90, 180, 85, 120, 80, 180, 130, 90, 60, 110]
        liabilities = [15, 14, 18, 48, 16, 28, 15, 48, 32, 20, 12, 25]
        growth = [0, -6.2, 20.0, 100.0, -52.8, 41.2, -33.3, 125.0, -27.8, -30.8, -33.3, 83.3]
        marker_threshold = 150
    fig = go.Figure(
        go.Scatter(
            x=mêss,
            y=values,
            mode="lines+markers",
            fill="tozeroy",
            fillcolor="rgba(95, 168, 211, 0.15)",
            line=dict(color=AZUL_CLARO, width=2),
            marker=dict(
                color=[VERMELHO if v >= marker_threshold else AZUL_CLARO for v in values],
                size=10, line=dict(width=2, color="white"),
            ),
            customdata=list(zip(liabilities, growth)),
            hovertemplate="<b>%{x}</b><br>Quantidade: %{y}<br>Passivo estimado: R$ %{customdata[0]}k<br>Crescimento: %{customdata[1]:+.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=50, r=20, t=50, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=300,
        xaxis=dict(
            title="Próximos 12 meses",
            gridcolor="#f0f0f0",
            linecolor="#ddd",
            tickfont=dict(size=11, color="#4A5568"),
            titlefont=dict(size=12, color="#4A5568"),
        ),
        yaxis=dict(
            title="Número de funcionários",
            gridcolor="#f0f0f0",
            linecolor="#ddd",
            tickfont=dict(size=11, color="#4A5568"),
            titlefont=dict(size=12, color="#4A5568"),
        ),
        title=dict(
            text="Sazonalidade e concentração de risco futuro para previsão operacional",
            font=dict(size=11, color="#4A5568"),
            x=0, xanchor="left",
        ),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#ccc", font=dict(color="#333", size=12)),
    )
    return fig


def _risk_matrix_fig(df: pd.DataFrame):
    fig = go.Figure()
    for _, row in df.iterrows():
        color = {"critica": VERMELHO, "alta": VERMELHO, "media": AMARELO, "baixa": AZUL_CLARO}.get(row["severity"], AZUL_CLARO)
        fig.add_trace(
            go.Scatter(
                x=[row["ocorrencias"]],
                y=[row["passivo"]],
                mode="markers",
                marker=dict(
                    size=min(max(row["func"]/5, 15), 50),
                    color=color,
                    line=dict(width=2, color="white"),
                    opacity=0.8,
                ),
                name=row["unidade"],
                hovertemplate=f"<b>{row['unidade']}</b><br>Unidade: {row['unidade']}<br>Status: {row['func']}<br>Passivo: R$ {row['passivo']:,.0f}<br>Vencimentos: 2023<extra></extra>",
                showlegend=False,
            )
        )
    fig.update_layout(
        margin=dict(l=60, r=20, t=50, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=280,
        xaxis=dict(
            title="Número de pagamentos devidos",
            gridcolor="#f0f0f0",
            linecolor="#ddd",
            tickfont=dict(size=11, color="#4A5568"),
            titlefont=dict(size=12, color="#4A5568"),
        ),
        yaxis=dict(
            title="Passivo Financeiro",
            gridcolor="#f0f0f0",
            linecolor="#ddd",
            tickfont=dict(size=11, color="#4A5568"),
            titlefont=dict(size=12, color="#4A5568"),
        ),
        title=dict(
            text="Matriz de Risco",
            font=dict(size=16, color="#1A202C", family="Inter, sans-serif"),
            x=0, xanchor="left",
        ),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#ccc", font=dict(color="#333", size=12)),
    )
    # Add legend annotations
    fig.add_annotation(x=18, y=220_000, text="Baixo risco", showarrow=False, font=dict(size=10, color=AZUL_CLARO), bgcolor="rgba(255,255,255,0.8)")
    fig.add_annotation(x=18, y=190_000, text="Impacto financeiro", showarrow=False, font=dict(size=10, color=VERMELHO), bgcolor="rgba(255,255,255,0.8)")
    return fig


def _jornada_donut_fig():
    try:
        df = jornada_donut_data()
        if df.empty:
            raise ValueError("empty")
        value_map = dict(zip(df["work_schedule"], df["cnt"]))
        incompatible = int(df["incompatible_cnt"].iloc[0])
        schedule_order = ["5x2", "6x1", "12x36", "3x3"]
        labels = []
        values_list = []
        for s in schedule_order:
            if s in value_map and value_map[s] > 0:
                labels.append(s)
                values_list.append(value_map[s])
        if incompatible > 0:
            labels.append("Escala incompatível")
            values_list.append(incompatible)
        values = values_list
        colors_list = [AZUL_CLARO, PETROLEO, AMARELO, VERDE, VERMELHO][:len(labels)]
        total = sum(values)
        annotation_text = "<b>3x3 (RN)</b>" if "3x3" in labels else "<b>Distribuição de Escalas</b>"
    except Exception:
        labels = ["5x2", "6x1", "12x36", "3x3", "Escala incompatível"]
        values = [35, 25, 15, 10, 15]
        colors_list = [AZUL_CLARO, PETROLEO, AMARELO, VERDE, VERMELHO]
        total = 100
        annotation_text = "<b>3x3 (RN)</b>"
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(colors=colors_list, line=dict(color="white", width=2)),
            textinfo="none",
            hovertemplate="%{label}<br>%{value}%<extra></extra>",
            sort=False,
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=220,
        title=dict(
            text="Visão de Jornada e Turno",
            font=dict(size=14, color="#1A202C", family="Inter, sans-serif"),
            x=0, xanchor="left",
        ),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            font=dict(size=10, color="#4A5568"),
        ),
        annotations=[dict(
            text=annotation_text,
            x=0.5, y=0.5,
            font_size=12,
            showarrow=False,
            font=dict(color=VERDE),
        )],
    )
    return fig


def _compliance_table():
    try:
        df = compliance_table_data()
        if df.empty:
            raise ValueError("empty")
        raw = []
        for _, row in df.iterrows():
            jornada = str(int(row["standard_weekly_hours"])) + "h" if pd.notna(row["standard_weekly_hours"]) else ""
            if "Diferenciada" not in jornada and row["state"] == "RN":
                jornada = "Jornada Diferenciada 30h"
            reajuste = ("+" + str(row["salary_adjustment_percent"]) + " %") if pd.notna(row["salary_adjustment_percent"]) else ""
            piso = ("R$ " + str(row["base_salary_min"]).replace(".", ",")) if pd.notna(row["base_salary_min"]) else ""
            conformidade = round(row["conformidade_pct"], 1) if pd.notna(row["conformidade_pct"]) else None
            passivo = int(row["passivo_por_funcionario"]) if pd.notna(row["passivo_por_funcionario"]) else 0
            raw.append((row["state"], jornada, reajuste, piso, conformidade, passivo))
    except Exception:
        raw = [
            ("AB", "110", "+5 %", "R$.00", 47, 172_000),
            ("RN (CAERN)", "Jornada Diferenciada 30h", "", "", None, 150_000),
            ("RN", "Jornada Diferenciada 30h", "", "", None, 200_000),
            ("RG", "", "", "", None, 132_000),
            ("EN", "Jornada Diferenciada 30h", "", "", None, 110_000),
            ("RJ", "", "", "", None, 107_000),
            ("SP", "20", "+0 %", "R$.00", 39, 67),
        ]
    data = []
    for estado, jornada, reajuste, piso, conformidade, passivo in raw:
        if conformidade is not None and conformidade < 50:
            sev, sev_color = "Alto", VERMELHO
        elif passivo >= 150_000:
            sev, sev_color = "Alto", VERMELHO
        elif passivo >= 100_000:
            sev, sev_color = "Médio", AMARELO
        else:
            sev, sev_color = "Baixo", VERDE
        conf_str = f"{conformidade}%" if conformidade is not None else ""
        pas_str = f"R$ {passivo//1000}k" if passivo >= 1000 else f"R${passivo}"
        data.append({
            "estado": estado, "jornada": jornada, "reajuste": reajuste,
            "piso": piso, "conformidade": conf_str, "passivo": pas_str,
            "sev": sev, "sev_color": sev_color,
        })
    header_style = {
        "borderBottom": "2px solid #e2e8f0",
        "padding": "6px 8px",
        "fontSize": "0.75rem",
        "fontWeight": "700",
        "color": "#1A202C",
        "textAlign": "left",
    }
    cell_style = {
        "padding": "6px 8px",
        "fontSize": "0.75rem",
        "color": "#4A5568",
        "borderBottom": "1px solid #f7fafc",
        "textAlign": "left",
    }
    rows = [html.Tr([
        html.Th("Estado / Sindicato", style=header_style),
        html.Th("Jornada<br>Padrão", style=header_style),
        html.Th("Reajuste<br>da CCT (%)", style=header_style),
        html.Th("Piso<br>Salarial", style=header_style),
        html.Th("% de Conformidade<br>com a CCT", style=header_style),
        html.Th("Passivo Médio /<br>Funcionário", style=header_style),
        html.Th("Severidade", style={**header_style, "textAlign": "center"}),
    ])]
    for d in data:
        badge = None
        if "Diferenciada" in str(d["jornada"]):
            badge = html.Span(
                d["jornada"],
                style={
                    "backgroundColor": PETROLEO, "color": "white",
                    "padding": "2px 8px", "borderRadius": "10px",
                    "fontSize": "0.65rem", "display": "inline-block",
                },
            )
        rows.append(html.Tr([
            html.Td(d["estado"], style=cell_style),
            html.Td(badge if badge else d["jornada"], style=cell_style),
            html.Td(d["reajuste"], style=cell_style),
            html.Td(d["piso"], style=cell_style),
            html.Td(d["conformidade"], style=cell_style),
            html.Td(d["passivo"], style=cell_style),
            html.Td(
                html.Span(
                    d["sev"],
                    style={
                        "backgroundColor": d["sev_color"], "color": "white",
                        "padding": "2px 10px", "borderRadius": "10px",
                        "fontSize": "0.7rem", "fontWeight": "700",
                    },
                ),
                style={**cell_style, "textAlign": "center"},
            ),
        ]))
    return html.Div([
        html.H6(
            "Comparativo de Conformidade por Estado / Sindicato",
            style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"},
        ),
        html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
    ])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout():
    df_est, df_rank, resumo = _safe_data()

    card_style = {
        "backgroundColor": BRANCO,
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
        "border": "none",
        "padding": "16px",
        "height": "100%",
    }

    # ---- Row 1: Geographic View ----
    row1_left = html.Div([
        html.H6("Distribuição por Estado", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Concentração de férias vencidas", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        dcc.Graph(figure=_distribuicao_estado_fig(df_est), config={"displayModeBar": False}, style={"height": "260px"}),
    ], style=card_style)

    row1_right = html.Div([
        html.H6("Janela de Alertas", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Proximidade de prazos", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        dcc.Graph(figure=_window_alert_fig(), config={"displayModeBar": False}, style={"height": "260px"}),
    ], style=card_style)

    # ---- Row 2: Operational Rankings ----
    row2_left = html.Div([
        html.H6("Ranking de Unidades Críticas", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        _ranking_table(df_rank),
    ], style={**card_style, "minHeight": "350px"})

    row2_right = html.Div([
        html.H6("Funcionários por Mês de Pagamento", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px"}),
        html.P("Sazonalidade e concentração de risco futuro para previsão operacional", style={"fontSize": "11px", "color": "#4A5568", "marginBottom": "8px"}),
        dcc.Graph(figure=_payment_mês_fig(), config={"displayModeBar": False}, style={"height": "300px"}),
    ], style=card_style)

    # ---- Row 3: Matriz de Risco + Operational Summary ----
    row3_left = html.Div([
        html.H6("Matriz de Risco", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        dcc.Graph(figure=_risk_matrix_fig(df_rank), config={"displayModeBar": False}, style={"height": "280px"}),
    ], style=card_style)

    # Operational Summary mini-cards
    ops_cards = html.Div([
        html.Div([
            html.P("Funcionários em risco", style={"fontSize": "0.75rem", "color": "#FFFFFF", "marginBottom": "4px", "textAlign": "center"}),
            html.H3("1.788", style={"fontSize": "1.8rem", "color": BRANCO, "fontWeight": "700", "textAlign": "center", "margin": "0"}),
        ], style={"backgroundColor": PETROLEO, "borderRadius": "8px", "padding": "12px", "marginBottom": "8px"}),
        html.Div([
            html.P("Maior unidade crítica", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "4px", "textAlign": "center"}),
            html.P("Maior unidade crítica", style={"fontSize": "1rem", "color": VERMELHO, "fontWeight": "700", "textAlign": "center", "margin": "0"}),
        ], style={"backgroundColor": "#FED7D7", "borderRadius": "8px", "padding": "8px", "marginBottom": "8px"}),
        html.Div([
            html.P("Maior crescimento mensal", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "4px", "textAlign": "center"}),
            html.P("▲ 10,60%", style={"fontSize": "1.2rem", "color": PETROLEO, "fontWeight": "700", "textAlign": "center", "margin": "0"}),
        ], style={"backgroundColor": AZUL_CLARO, "borderRadius": "8px", "padding": "8px", "marginBottom": "8px"}),
        html.Div([
            html.P("Passivo médio por funcionário", style={"fontSize": "0.75rem", "color": "#4A5568", "marginBottom": "4px", "textAlign": "center"}),
            html.P("R$ 24.400", style={"fontSize": "1.2rem", "color": VERMELHO, "fontWeight": "700", "textAlign": "center", "margin": "0"}),
        ], style={"backgroundColor": "#FED7D7", "borderRadius": "8px", "padding": "8px"}),
    ])

    row3_right = html.Div([
        html.H6("Resumo Operacional", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        ops_cards,
    ], style=card_style)

    # ---- Row 4: Compliance + Jornada ----
    row4_left = html.Div([
        _compliance_table(),
    ], style=card_style)

    alerts = html.Div([
        html.H6("Alertas", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "6px"}),
        html.Div([
            html.Span(style={"display": "inline-block", "width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "6px"}),
            html.Span("Funcionários sem registro de ponto no período", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            html.Span("Caso 8", style={"fontSize": "0.7rem", "color": "#888", "marginLeft": "auto"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
        html.Div([
            html.Span(style={"display": "inline-block", "width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "6px"}),
            html.Span("Escala incompatível com a Convenção Coletiva de Trabalho", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            html.Span("Caso 20", style={"fontSize": "0.7rem", "color": "#888", "marginLeft": "auto"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
        html.Div([
            html.Span(style={"display": "inline-block", "width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": VERMELHO, "marginRight": "6px"}),
            html.Span("Limite semanal excedido", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            html.Span("Caso 25", style={"fontSize": "0.7rem", "color": "#888", "marginLeft": "auto"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
        html.Div([
            html.Span(style={"display": "inline-block", "width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": AMARELO, "marginRight": "6px"}),
            html.Span("Sobreposição de turnos detectada", style={"fontSize": "0.75rem", "color": "#4A5568"}),
            html.Span("Caso 28", style={"fontSize": "0.7rem", "color": "#888", "marginLeft": "auto"}),
        ], style={"display": "flex", "alignItems": "center"}),
    ])

    row4_right = html.Div([
        html.H6("Visão de Jornada e Turno", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        dcc.Graph(figure=_jornada_donut_fig(), config={"displayModeBar": False}, style={"height": "220px"}),
        alerts,
    ], style=card_style)

    return html.Div([
        # Row 1
        dbc.Row([
            dbc.Col(row1_left, width=7),
            dbc.Col(row1_right, width=5),
        ], className="g-3 mb-3"),
        # Row 2
        dbc.Row([
            dbc.Col(row2_left, width=6),
            dbc.Col(row2_right, width=6),
        ], className="g-3 mb-3"),
        # Row 3
        dbc.Row([
            dbc.Col(row3_left, width=8),
            dbc.Col(row3_right, width=4),
        ], className="g-3 mb-3"),
        # Row 4
        dbc.Row([
            dbc.Col(row4_left, width=8),
            dbc.Col(row4_right, width=4),
        ], className="g-3 mb-3"),
        html.P(
            f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
        ),
    ], style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"})


def register_callbacks(app):
    pass
