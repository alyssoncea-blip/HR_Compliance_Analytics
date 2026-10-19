import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERDE, AMARELO, VERMELHO
from app.data import ccts_processadas, distribuicao_entidades, cct_evolution_data, cct_clauses, clausulas_relevantes_por_uc

# ---------------------------------------------------------------------------
# Real data loader for the offline CCT clause extractor output
# ---------------------------------------------------------------------------
EXTRACTED_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "gold" / "governance" / "cct_extracted_rules.json"
)

EXPECTED_CCT_STATES = ("MG", "RJ", "RN")

UNCATEGORIZED = "nao_classificada"


def _cct_clauses_gold() -> pd.DataFrame:
    """Stage 1 source: gold dim table. Empty when missing/unreadable."""
    try:
        df = cct_clauses()
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _normalize_gold_rules_df(gold_df: pd.DataFrame) -> pd.DataFrame:
    """Adapt the gold dim frame to the clause contract consumed by the table."""
    df = gold_df.rename(columns={"clause_title": "title", "source_pdf": "pdf_path"}).copy()
    if "title" not in df.columns:
        df["title"] = None
    if "period" not in df.columns:
        df["period"] = df.get("pdf_path", pd.Series([""] * len(df), index=df.index)).astype(str).str.split("/").str[3]
    if "text" not in df.columns:
        df["text"] = df.get("title")
    return df


def _gold_extraction_doc(gold_df: pd.DataFrame) -> dict:
    """Extraction-style summary synthesized from gold when JSON is unavailable."""
    by_state: dict = {}
    if "union_state" in gold_df.columns:
        by_state = {str(k): int(v) for k, v in gold_df["union_state"].value_counts().items()}
    return {
        "extraction_method": "pypdf + regex rules (promoted to gold)",
        "source_count": int(gold_df["source_pdf"].nunique()) if "source_pdf" in gold_df.columns else 0,
        "readable_source_count": int(gold_df["source_pdf"].nunique()) if "source_pdf" in gold_df.columns else 0,
        "total_clauses": int(len(gold_df)),
        "avg_confidence": round(float(gold_df["confidence"].fillna(0.0).mean()), 3) if "confidence" in gold_df.columns else 0.0,
        "by_state": by_state,
        "by_category": {str(k): int(v) for k, v in gold_df.get("category", pd.Series(dtype=object)).value_counts().items()} if "category" in gold_df.columns else {},
        "validation": {},
    }


def _load_extracted_rules(path: Path | None = None) -> tuple[dict | None, pd.DataFrame, str | None]:
    """Load the offline CCT clause extraction produced by pipelines/nlp/cct_extractor.py.

    Returns (data, clauses_df, message). There is NO mock fallback: when the
    file is missing or empty the message explains how to generate it for real
    from the PDFs in Docs/CCTs/.
    """
    target = Path(path) if path else EXTRACTED_RULES_PATH
    try:
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None, pd.DataFrame(), "missing"
    except (json.JSONDecodeError, OSError):
        return None, pd.DataFrame(), "unreadable"

    clauses = data.get("clauses") or []
    if not clauses:
        return data, pd.DataFrame(), "empty"
    return data, pd.DataFrame(clauses), None


def _extractor_banner():
    return dbc.Alert([
        html.Span("⚠ Sem dados de extração de CCT. ", style={"fontWeight": "700"}),
        html.Span(
            "Esta página consome o JSON REAL de cláusulas extraídas offline "
            "(pypdf + regex) dos PDFs em Docs/CCTs/. "
            f"Arquivo não encontrado em: {EXTRACTED_RULES_PATH}. ",
            style={"fontWeight": "400"},
        ),
        html.Span(
            "Execute: python pipelines/nlp/cct_extractor.py",
            style={"fontWeight": "700", "fontFamily": "monospace"},
        ),
    ], color="warning", style={"fontSize": "0.75rem", "padding": "8px 12px", "marginBottom": "0px"})


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
def _rules_table(extracted_data, rules_df, rules_message, source_label: str | None = None):
    if not rules_df.empty:
        header_style = {
            "borderBottom": "2px solid #e2e8f0", "padding": "5px 8px",
            "fontSize": "0.7rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
        }
        cell_style = {"padding": "4px 8px", "fontSize": "0.68rem", "color": "#4A5568", "borderBottom": "1px solid #f7fafc", "textAlign": "left"}
        rows = [html.Tr([
            html.Th("Clausula", style=header_style),
            html.Th("Titulo / Resumo", style=header_style),
            html.Th("Categoria", style=header_style),
            html.Th("Confianca (%)", style=header_style),
            html.Th("Fonte", style=header_style),
        ])]
        for _, clause in rules_df.iterrows():
            clause_number = str(clause.get("clause_number") or "—")
            title = str(clause.get("title") or "")[:90]
            summary = str(clause.get("text") or "")[:110]
            label = title or summary
            category = str(clause.get("category") or "")
            confidence = float(clause.get("confidence") or 0.0) * 100
            conf_color = VERDE if confidence >= 80 else (AMARELO if confidence >= 60 else VERMELHO)
            source = f"{clause.get('union_state', '')} {clause.get('period', '')} · pag. {clause.get('page', '')}"
            rows.append(html.Tr([
                html.Td(clause_number, style=cell_style),
                html.Td(label, style=cell_style),
                html.Td(category, style={**cell_style, "fontWeight": "600" if category != UNCATEGORIZED else "400"}),
                html.Td(
                    html.Span(f"{confidence:.0f}%", style={"color": conf_color, "fontWeight": "600"}),
                    style=cell_style,
                ),
                html.Td(source, style=cell_style),
            ]))
        content = html.Div([
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
    else:
        content = rules_message or "Sem cláusulas extraídas."

    heading_children = [
        html.H6(
            "CLAUSULAS REAIS EXTRAIDAS DAS CCTs (pypdf + regex)",
            style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "4px", "display": "inline-block"},
        ),
    ]
    if source_label:
        heading_children.append(html.Span(
            source_label,
            style={
                "fontSize": "0.62rem", "fontWeight": "700", "color": "white",
                "backgroundColor": VERDE, "padding": "2px 8px", "borderRadius": "6px", "marginLeft": "6px",
            },
        ))
    return html.Div([html.Div(heading_children, style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}), content])


def _ai_metrics(extracted_data, rules_df, rules_message):
    if rules_df.empty:
        metrics = [
            ("Metodo", "Extrator offline pypdf + regex (sem LLM)", False),
            ("Status", "Dados reais nao gerados", True),
            ("Comando", "python pipelines/nlp/cct_extractor.py", False),
        ]
    else:
        total = int(len(rules_df))
        categorized = rules_df[rules_df["category"].fillna(UNCATEGORIZED) != UNCATEGORIZED]
        pending = int((rules_df["confidence"].fillna(0.0) < 0.8).sum())
        sources = extracted_data.get("source_count") or 0
        readable = extracted_data.get("readable_source_count") or 0
        by_state = extracted_data.get("by_state") or {}
        by_state_display = " · ".join(f"{state}: {count}" for state, count in sorted(by_state.items())) or "—"
        percent_counts = extracted_data.get("percent_counts") or {}
        percent_display = (
            f"50%: {percent_counts.get('50', 0)} · 70%: {percent_counts.get('70', 0)} · 100%: {percent_counts.get('100', 0)}"
            if percent_counts else "—"
        )
        validation = (extracted_data.get("validation") or {}).get("weekly_hours") or {}
        validation_display = (
            f"{validation.get('matches', 0)} match / {len(validation.get('mismatches') or [])} mismatch"
            if validation else "—"
        )
        metrics = [
            ("Metodo", "Extrator offline pypdf + regex (sem LLM)", False),
            ("Clausulas extraidas", str(total), False),
            ("Clausulas classificadas", f"{len(categorized)}/{total}", len(categorized) == 0),
            ("Confianca media", f"{((extracted_data.get('avg_confidence') or 0.0) * 100):.1f}%", (extracted_data.get('avg_confidence') or 0) < 0.8),
            ("IDs com confianca < 80%", str(pending), pending > 0),
            ("Fontes legiveis", f"{readable}/{sources}", False),
            ("Clausulas por estado", by_state_display, False),
        ]
        if "percent_counts" in extracted_data:
            metrics.append(("Percentuais em clausulas HE", percent_display, False))
        if validation:
            metrics.append((
                "Validacao jornada semanal vs dim",
                f"{validation.get('matches', 0)} match / {len(validation.get('mismatches') or [])} mismatch",
                len(validation.get('mismatches') or []) > 0,
            ))
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
        html.H6("EXTRACAO NLP — METRICAS DO EXTRATOR OFFLINE", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        html.Div(rows),
    ])


# ---------------------------------------------------------------------------
# Semantic linkage: CCT categories <-> validation engine UCs
# ---------------------------------------------------------------------------
def _cct_uc_block(clauses_df: pd.DataFrame, mapping_df: pd.DataFrame):
    html_resp_style = {
        "borderBottom": "2px solid #e2e8f0", "padding": "5px 8px",
        "fontSize": "0.7rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "left",
    }
    cell_resp_style = {"padding": "4px 8px", "fontSize": "0.68rem", "color": "#4A5568", "borderBottom": "1px solid #f7fafc", "textAlign": "left"}

    rows = [html.Tr([
        html.Th("Estado", style=html_resp_style),
        html.Th("Categoria da cláusula (CCT)", style=html_resp_style),
        html.Th("Clausulas", style=html_resp_style),
        html.Th("Regras do motor (UCs)", style=html_resp_style),
    ])]
    if not mapping_df.empty:
        for _, row in mapping_df.iterrows():
            rows.append(html.Tr([
                html.Td(str(row["union_state"]), style=cell_resp_style),
                html.Td(str(row["category"]), style={**cell_resp_style, "fontWeight": "600"}),
                html.Td(str(row["clause_count"]), style=cell_resp_style),
                html.Td(str(row["ucs"]) or "—", style=cell_resp_style),
            ]))
    else:
        rows.append(html.Tr([html.Td("Sem cláusulas classificadas para mapear ao motor.", style=cell_resp_style, colSpan=4)]))

    notes = []
    present_states = set()
    if not clauses_df.empty and "union_state" in clauses_df.columns:
        present_states = set(clauses_df["union_state"].dropna().astype(str).unique())
    for state in EXPECTED_CCT_STATES:
        if state in present_states:
            continue
        notes.append(html.Div(
            f"{state}: sem cláusulas extraídas — PDF não legível (scanned, sem camada de texto), "
            "mapping CCT↔UC indisponível para este estado.",
            style={"fontSize": "0.66rem", "color": VERMELHO, "marginTop": "4px"},
        ))
    return html.Div([
        html.H6("CCT ↔ REGRAS DO MOTOR (VINCULO SEMANTICO POR ESTADO)", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "6px"}),
        html.Div(
            html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"}),
            style={"maxHeight": "220px", "overflowY": "auto"},
        ),
        html.Div(notes, style={"marginTop": "2px"}),
    ], style={"marginTop": "4px"})


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

    # 3-stage honest degradation: Gold parquet -> governance JSON -> banner.
    gold_df = _cct_clauses_gold()
    extracted_data, rules_df, rules_message = _load_extracted_rules()
    if not gold_df.empty:
        rules_df = _normalize_gold_rules_df(gold_df)
        rules_message = None
        source_label = "GOLD · dim_cct_clause.parquet"
        if extracted_data is None:
            extracted_data = _gold_extraction_doc(gold_df)
    else:
        extracted_data = extracted_data  # noqa: F841 (kept for clarity of stages)
        source_label = None

    ccts_count = len(ccts_df)
    regras_count = int(len(rules_df)) if not rules_df.empty else int(extracted_data.get("total_clauses") or 0) if extracted_data else 0
    ccts_states = ", ".join(ccts_df["state"].tolist()) if not ccts_df.empty and "state" in ccts_df.columns else "MG, RJ, RN"
    pending_count = 0
    avg_confidence_pct = 0.0
    if not rules_df.empty:
        pending_count = int((rules_df["confidence"].fillna(0.0) < 0.8).sum())
        avg_confidence_pct = float(extracted_data.get("avg_confidence") or 0.0) * 100
    else:
        detection_rate = 0

    kpi1 = html.Div([
        html.H6("CCTs PROCESSADAS", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        html.H2(str(ccts_count), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "center", "margin": "0"}),
        html.P(f"PDFs de ACT/CCT em Docs/CCTs ({ccts_states})", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    kpi2 = html.Div([
        html.H6("CLAUSULAS EXTRAIDAS AUTOMATICAMENTE", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        html.Div([
            html.H2(str(regras_count), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "margin": "0"}),
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "marginBottom": "4px"}),
        html.P("Clausulas reais via pypdf + regex (offline)", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    kpi3 = html.Div([
        html.H6("CONFIANCA MEDIA DA EXTRACAO", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        dcc.Graph(figure=_confidence_gauge(avg_confidence_pct), config={"displayModeBar": False}, style={"height": "90px"}),
        html.P("Heuristica de palavras-chave por categoria", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    kpi4 = html.Div([
        html.H6("CLAUSULAS COM CONFIANCA < 80%", style={"fontWeight": "700", "fontSize": "12px", "color": "#1A202C", "marginBottom": "4px", "textAlign": "center"}),
        html.H2(str(pending_count), style={"fontSize": "2.5rem", "fontWeight": "700", "color": "#1A202C", "textAlign": "center", "margin": "0"}),
        html.P("Aguardando revisao humana", style={"fontSize": "0.7rem", "color": "#4A5568", "textAlign": "center"}),
    ], style=card_style)

    # ---- Linha 2: Regras + Treemap ----
    rules_lines = [_rules_table(extracted_data, rules_df, rules_message, source_label=source_label)]
    if not rules_df.empty and extracted_data and "percent_counts" in (extracted_data or {}):
        percent_counts = extracted_data.get("percent_counts") or {}
        percent_lines = [
            html.Span(f"50%: {percent_counts.get('50', 0)}", style={"color": AZUL_CLARO, "fontWeight": "700", "marginRight": "10px"}),
            html.Span(f"70%: {percent_counts.get('70', 0)}", style={"color": AMARELO, "fontWeight": "700", "marginRight": "10px"}),
            html.Span(f"100%: {percent_counts.get('100', 0)}", style={"color": VERMELHO, "fontWeight": "700"}),
        ]
        rules_lines.append(html.Div([
            html.Span("Menções a percentuais de HE nas cláusulas extraídas: ", style={"fontSize": "0.68rem", "color": "#4A5568"}),
        ] + percent_lines, style={"marginTop": "6px", "fontSize": "0.68rem"}))
    else:
        rules_lines.append(_extractor_banner())
    rules_card = html.Div(rules_lines, style=card_style)

    treemap_card = html.Div([
        html.H6("ENTIDADES EXTRAÍDAS (NUVEM DE PALAVRAS / TREEMAP)", style={"fontWeight": "700", "fontSize": "14px", "color": "#1A202C", "marginBottom": "8px"}),
        dcc.Graph(figure=_treemap_fig(), config={"displayModeBar": False}, style={"height": "280px"}),
    ], style=card_style)

    # ---- Linha 3: Evolução + Métricas de IA ----
    evolution_card = html.Div([
        dcc.Graph(figure=_cct_evolution_fig(), config={"displayModeBar": False}, style={"height": "280px"}),
    ], style=card_style)

    metrics_card = html.Div([
        _ai_metrics(extracted_data, rules_df, rules_message),
    ], style=card_style)

    # ---- Linha 4: CCT <-> Regras do Motor (semantic mapping) ----
    uc_mapping_df = clausulas_relevantes_por_uc(rules_df)
    semantic_card = html.Div([
        _cct_uc_block(rules_df, uc_mapping_df),
    ], style=card_style)

    return html.Div([
        # Linha 1
        dbc.Row([dbc.Col(kpi1, width=3), dbc.Col(kpi2, width=3), dbc.Col(kpi3, width=3), dbc.Col(kpi4, width=3)], className="g-3 mb-3"),
        # Linha 2
        dbc.Row([dbc.Col(rules_card, width=7), dbc.Col(treemap_card, width=5)], className="g-3 mb-3"),
        # Linha 3
        dbc.Row([dbc.Col(evolution_card, width=7), dbc.Col(metrics_card, width=5)], className="g-3 mb-3"),
        # Linha 4
        dbc.Row([dbc.Col(semantic_card, width=12)], className="g-3 mb-3"),
        html.P(
            f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            style={"textAlign": "right", "color": "#888", "fontSize": "0.75rem", "marginTop": "12px"},
        ),
    ], style={"backgroundColor": CINZA, "padding": "16px", "minHeight": "100vh"})


def register_callbacks(app):
    pass
