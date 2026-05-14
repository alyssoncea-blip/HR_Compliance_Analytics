"""Shared UI components for Dash dashboards."""
import dash_bootstrap_components as dbc
from dash import html, dcc
from app.theme.colors import PETROLEO, VERMELHO, AMARELO, AZUL_CLARO, VERDE

def kpi_card(title, value, subtitle=None, color=PETROLEO):
    return dbc.Card([
        dbc.CardBody([
            html.H6(title, className="text-muted", style={"fontSize": "0.85rem"}),
            html.H2(value, style={"color": color, "fontWeight": "700", "margin": "0"}),
            html.Small(subtitle, style={"color": "#888"}) if subtitle else None,
        ], style={"padding": "0.8rem 1rem"})
    ], style={"boxShadow": "0 1px 3px rgba(0,0,0,0.1)", "borderRadius": "8px", "border": "none", "height": "100%"})

def kpi_row(cols):
    """cols: list of (title, value, subtitle, color) tuples."""
    return dbc.Row([
        dbc.Col(kpi_card(title, value, subtitle, color or PETROLEO), width=12//len(cols))
        for title, value, subtitle, color in cols
    ], className="mb-3", style={"gap": "0"})

def severity_badge(severity):
    color = {"critico": VERMELHO, "alto": AMARELO, "medio": AMARELO, "regular": VERDE}.get(severity, "#888")
    return html.Span(severity.upper(), style={
        "background": color, "color": "white", "padding": "2px 10px",
        "borderRadius": "10px", "fontSize": "0.75rem", "fontWeight": "600"
    })

def alert_card(use_case, rule, detail, severity, impact):
    color = {"critico": VERMELHO, "alto": AMARELO, "medio": AMARELO}.get(severity, "#888")
    return dbc.Card([
        dbc.CardBody([
            html.Strong(f"UC{use_case:02d} {rule}", style={"color": color}),
            html.Br(),
            html.Small(detail[:120], style={"color": "#666"}),
            html.Br(),
            html.Small(f"Impacto: R$ {impact:,.2f}", style={"color": color, "fontWeight": "600"}),
        ], style={"padding": "0.5rem 1rem"})
    ], style={
        "borderLeft": f"4px solid {color}", "borderRadius": "4px",
        "boxShadow": "0 1px 2px rgba(0,0,0,0.05)", "marginBottom": "0.3rem"
    })

def section_header(title):
    return html.H4(title, style={"color": PETROLEO, "marginTop": "1.5rem", "marginBottom": "1rem", "fontWeight": "600"})

def figure_card(fig, title=None):
    """Wrap a Plotly figure in a DBC card."""
    children = []
    if title:
        children.append(html.H6(title, style={"color": PETROLEO, "padding": "0.8rem 1rem 0", "fontWeight": "600"}))
    children.append(dbc.CardBody([dcc.Graph(figure=fig)], style={"padding": "0.5rem"}))
    return dbc.Card(children, style={"boxShadow": "0 1px 3px rgba(0,0,0,0.1)", "borderRadius": "8px", "border": "none", "height": "100%"})
