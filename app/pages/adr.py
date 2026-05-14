from dash import html
import dash_bootstrap_components as dbc


def layout():
    items = [
        ("Stack local com DuckDB", "Portabilidade e custo baixo", "Sem execução distribuída nativa"),
        ("Regras SQL no validation_engine", "Alta explicabilidade", "Manutenção cresce com quantidade de regras"),
        ("Passivo derivado de inconsistências", "Causalidade auditável", "Depende de calibração de fatores"),
        ("CCT versionada por vigência", "Aderência histórica", "Join temporal mais complexo"),
        ("Observabilidade JSON + SLA", "Rápido para portfólio", "Sem integração externa de alertas"),
    ]
    rows = []
    for t, p, l in items:
        rows.append(
            dbc.Card(
                dbc.CardBody([
                    html.H5(t, style={"marginBottom": "8px"}),
                    html.P(f"Trade-off: {p}", style={"marginBottom": "4px"}),
                    html.P(f"Limite conhecido: {l}", style={"marginBottom": "0", "color": "#666"}),
                ]),
                className="mb-3"
            )
        )

    return html.Div([
        dbc.Container([
            html.H3("Architecture Decision Record"),
            html.P("Decisões arquiteturais, trade-offs e limites conhecidos do projeto."),
            *rows,
        ], fluid=True, style={"padding": "16px"})
    ])


def register_callbacks(app):
    return
