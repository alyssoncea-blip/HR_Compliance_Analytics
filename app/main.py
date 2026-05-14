"""
HR Compliance Analytics — Dash Application
Multi-page dashboard with Dash Bootstrap Components.
"""
import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from app.theme.colors import PETROLEO, CINZA, BRANCO
from app.pages import (dashboard_estrategico, dashboard_analitico,
                        dashboard_auditoria, reconciliacao, funcionario,
                        ia_nlp, governanca, adr)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="HR Compliance Analytics",
    update_title=None,
)
server = app.server

NAV_ITEMS = [
    ("estrategico", "Estratégico"),
    ("analitico", "Analítico"),
    ("auditoria", "Auditoria"),
    ("reconciliacao", "Reconciliação"),
    ("funcionario", "People Analytics"),
    ("ia_nlp", "IA / NLP"),
    ("governanca", "Governança"),
    ("adr", "ADR"),
]

SELECT_STYLE = {
    "fontSize": "0.8rem",
    "borderRadius": "6px",
    "border": "none",
    "color": "#1A202C",
    "height": "32px",
    "paddingLeft": "8px",
    "textOverflow": "ellipsis",
    "overflow": "hidden",
    "whiteSpace": "nowrap",
}

TODAY = datetime.now().date()
GLOBAL_DEFAULT_START_DATE = datetime(2013, 1, 2).date()

def _days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


def _resolve_default_date_range():
    fallback = (GLOBAL_DEFAULT_START_DATE.isoformat(), TODAY.isoformat())
    try:
        return fallback
    except Exception:
        return fallback


DEFAULT_START_DATE, DEFAULT_END_DATE = _resolve_default_date_range()

STATES = [{"label": "— Todos —", "value": None}] + [{"label": s, "value": s} for s in ["MG","RJ","RN"]]

BTN_STYLE = {
    "fontSize": "0.7rem",
    "padding": "2px 8px",
    "height": "24px",
    "borderRadius": "4px",
    "backgroundColor": "rgba(255,255,255,0.12)",
    "border": "1px solid rgba(255,255,255,0.25)",
    "color": "white",
    "cursor": "pointer",
    "fontWeight": "500",
}

DATE_INPUT_STYLE = {
    "fontSize": "0.8rem",
    "height": "32px",
    "borderRadius": "6px",
    "border": "none",
    "padding": "0 8px",
    "width": "100%",
    "boxSizing": "border-box",
}

def _nav_link(key, label, active):
    base_style = {
        "color": "rgba(255,255,255,0.85)",
        "fontWeight": "500",
        "fontSize": "0.85rem",
        "padding": "8px 10px",
        "borderRadius": "6px",
        "textDecoration": "none",
        "display": "inline-block",
    }
    if active:
        return dbc.NavLink(
            label,
            href=f"/{key}",
            id=f"nav-{key}",
            active=True,
            style={
                **base_style,
                "backgroundColor": "rgba(255,255,255,0.15)",
                "color": "white",
                "fontWeight": "700",
                "borderBottom": "3px solid white",
            },
        )
    return dbc.NavLink(label, href=f"/{key}", id=f"nav-{key}", active=False, style=base_style)


navbar = html.Div(
    dbc.Container(
        dbc.Row(
            [
                dbc.Col(
                    html.A(
                        "HR Compliance Analytics",
                        href="/",
                        style={
                            "color": "white",
                            "fontWeight": "700",
                            "fontSize": "1.3rem",
                            "textDecoration": "none",
                            "whiteSpace": "nowrap",
                        },
                    ),
                    width="auto",
                    align="center",
                ),
                dbc.Col(
                    html.Div(
                        [_nav_link(key, label, key == "estrategico") for key, label in NAV_ITEMS],
                        style={"display": "flex", "gap": "2px", "justifyContent": "center", "flexWrap": "wrap"},
                    ),
                    width="auto",
                    align="center",
                    className="mx-auto",
                ),
                dbc.Col(
                    html.Div(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Div(
                                            [
                                                dcc.Input(
                                                    id="filter-start-date",
                                                    type="date",
                                                    value=DEFAULT_START_DATE,
                                                    style=DATE_INPUT_STYLE,
                                                ),
                                                html.Span("→", style={"color": "white", "margin": "0 6px", "fontWeight": "bold", "fontSize": "0.85rem"}),
                                                dcc.Input(
                                                    id="filter-end-date",
                                                    type="date",
                                                    value=DEFAULT_END_DATE,
                                                    style=DATE_INPUT_STYLE,
                                                ),
                                            ],
                                            style={"display": "flex", "alignItems": "center", "gap": "4px"},
                                        ),
                                        width=9,
                                    ),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="filter-estado",
                                            placeholder="Estado",
                                            options=STATES,
                                            clearable=True,
                                            style=SELECT_STYLE,
                                        ),
                                        width=3,
                                    ),
                                ],
                                className="g-2 mb-1",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Div(
                                            [
                                                html.Button("30d", id="btn-30d", n_clicks=0, style=BTN_STYLE),
                                                html.Button("60d", id="btn-60d", n_clicks=0, style=BTN_STYLE),
                                                html.Button("90d", id="btn-90d", n_clicks=0, style=BTN_STYLE),
                                            ],
                                            style={"display": "flex", "gap": "3px"},
                                        ),
                                        width=4,
                                    ),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="filter-unidade",
                                            placeholder="Unidade",
                                            options=[{"label": "— Todos —", "value": None}],
                                            clearable=True,
                                            style=SELECT_STYLE,
                                        ),
                                        width=4,
                                    ),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="filter-sindicato",
                                            placeholder="Sindicato",
                                            options=[{"label": "— Todos —", "value": None}],
                                            clearable=True,
                                            style=SELECT_STYLE,
                                        ),
                                        width=4,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ],
                        style={"minWidth": "380px", "maxWidth": "480px"},
                    ),
                    width="auto",
                    align="center",
                ),
            ],
            align="center",
            className="w-100 flex-nowrap",
        ),
        fluid=True,
        style={"maxWidth": "1400px"},
    ),
    style={
        "backgroundColor": PETROLEO,
        "height": "80px",
        "display": "flex",
        "alignItems": "center",
        "position": "sticky",
        "top": "0",
        "zIndex": "1000",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.15)",
    },
)

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        dcc.Store(id="filter-store", data={
            "start_date": DEFAULT_START_DATE,
            "end_date": DEFAULT_END_DATE,
        }),
        dcc.Store(id="filter-estado-store", data=None),
        dcc.Store(id="filter-unidade-store", data=None),
        dcc.Store(id="filter-sindicato-store", data=None),
        dbc.Container(
            id="page-content",
            fluid=True,
            style={"minHeight": "80vh", "backgroundColor": CINZA, "paddingTop": "20px"},
        ),
        html.Footer(
            dbc.Container(
                [
                    html.Hr(),
                    html.P(
                        "HR Compliance Analytics · Projeto de Portfólio · Engenharia de Dados · Governança · IA",
                        className="text-center text-muted",
                        style={"fontSize": "0.8rem"},
                    ),
                ],
            ),
        ),
    ],
    style={"backgroundColor": CINZA},
)


@app.callback(
    [Output(f"nav-{key}", "style") for key, _ in NAV_ITEMS]
    + [Output(f"nav-{key}", "active") for key, _ in NAV_ITEMS],
    Input("url", "pathname"),
)
def update_nav(pathname):
    path = pathname.strip("/") if pathname else "estrategico"
    styles = []
    actives = []
    for key, label in NAV_ITEMS:
        base_style = {
            "color": "rgba(255,255,255,0.85)",
            "fontWeight": "500",
            "fontSize": "0.85rem",
            "padding": "8px 10px",
            "borderRadius": "6px",
            "textDecoration": "none",
            "display": "inline-block",
        }
        if key == path:
            styles.append(
                {
                    **base_style,
                    "backgroundColor": "rgba(255,255,255,0.15)",
                    "color": "white",
                    "fontWeight": "700",
                    "borderBottom": "3px solid white",
                }
            )
            actives.append(True)
        else:
            styles.append(base_style)
            actives.append(False)
    return styles + actives


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("filter-store", "data"),
    Input("filter-estado-store", "data"),
    Input("filter-unidade-store", "data"),
    Input("filter-sindicato-store", "data"),
)
def render_page(pathname, date_filter, estado, unidade, sindicato):
    filters = {
        "start_date": date_filter.get("start_date") if date_filter else DEFAULT_START_DATE,
        "end_date": date_filter.get("end_date") if date_filter else DEFAULT_END_DATE,
        "estado": estado,
        "unidade": unidade,
        "sindicato": sindicato,
    }
    try:
        from app.data import set_global_filters
        set_global_filters(filters)
    except Exception:
        pass
    path = pathname.strip("/") if pathname else "estrategico"
    pages = {
        "estrategico": dashboard_estrategico.layout,
        "analitico": dashboard_analitico.layout,
        "auditoria": dashboard_auditoria.layout,
        "reconciliacao": reconciliacao.layout,
        "funcionario": funcionario.layout,
        "ia_nlp": ia_nlp.layout,
        "governanca": governanca.layout,
        "adr": adr.layout,
    }
    try:
        return pages.get(path, dashboard_estrategico.layout)(filters=filters)
    except TypeError:
        return pages.get(path, dashboard_estrategico.layout)()


# Register callbacks from each page
dashboard_estrategico.register_callbacks(app)
dashboard_analitico.register_callbacks(app)
dashboard_auditoria.register_callbacks(app)
reconciliacao.register_callbacks(app)
funcionario.register_callbacks(app)
ia_nlp.register_callbacks(app)
governanca.register_callbacks(app)
adr.register_callbacks(app)


# ---------------------------------------------------------------------------
# Populate filter dropdowns with real data
# ---------------------------------------------------------------------------
@app.callback(
    [Output("filter-unidade", "options"),
     Output("filter-sindicato", "options")],
    Input("url", "pathname"),
)
def populate_filter_dropdowns(_pathname):
    try:
        from app.data import query, pq
        unidades = query(f"SELECT DISTINCT name FROM read_parquet({pq('dim_unit')}) ORDER BY name")
        unid_opts = [{"label": "— Todas —", "value": None}] + [
            {"label": row["name"], "value": row["name"]} for _, row in unidades.iterrows()
        ]
        sindicatos = query(f"SELECT DISTINCT name FROM read_parquet({pq('dim_union')}) ORDER BY name")
        sind_opts = [{"label": "— Todos —", "value": None}] + [
            {"label": row["name"], "value": row["name"]} for _, row in sindicatos.iterrows()
        ]
        return unid_opts, sind_opts
    except Exception:
        return [{"label": "— Todas —", "value": None}], [{"label": "— Todos —", "value": None}]


# ---------------------------------------------------------------------------
# Global filter callbacks
# ---------------------------------------------------------------------------
@app.callback(
    Output("filter-start-date", "value"),
    Output("filter-end-date", "value"),
    Input("btn-30d", "n_clicks"),
    Input("btn-60d", "n_clicks"),
    Input("btn-90d", "n_clicks"),
    prevent_initial_call=True,
)
def quick_date_range(n30, n60, n90):
    ctx = dash.callback_context
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    days = {"btn-30d": 30, "btn-60d": 60, "btn-90d": 90}
    n = days.get(btn, 90)
    return _days_ago(n), TODAY.isoformat()


@app.callback(
    Output("filter-store", "data"),
    Input("filter-start-date", "value"),
    Input("filter-end-date", "value"),
)
def sync_date_store(start, end):
    return {"start_date": start, "end_date": end}


@app.callback(
    Output("filter-estado-store", "data"),
    Input("filter-estado", "value"),
)
def sync_estado(estado):
    return estado


@app.callback(
    Output("filter-unidade-store", "data"),
    Input("filter-unidade", "value"),
)
def sync_unidade(unidade):
    return unidade


@app.callback(
    Output("filter-sindicato-store", "data"),
    Input("filter-sindicato", "value"),
)
def sync_sindicato(sindicato):
    return sindicato


if __name__ == "__main__":
    import os
    host = os.environ.get("DASH_HOST", "127.0.0.1")
    port = int(os.environ.get("DASH_PORT", "8050"))
    debug = os.environ.get("DASH_DEBUG_MODE", "false").lower() == "true"
    app.run(debug=debug, host=host, port=port)
