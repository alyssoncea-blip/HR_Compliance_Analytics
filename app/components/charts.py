import plotly.express as px
import plotly.graph_objects as go
from app.theme.colors import PETROLEO, AZUL_CLARO, CINZA, BRANCO, VERMELHO, AMARELO, VERDE

def apply_layout(fig, title=None, height=None):
    fig.update_layout(
        plot_bgcolor=CINZA, paper_bgcolor=BRANCO,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title, height=height,
        font=dict(color="#333"),
    )
    return fig

def bar(df, x, y, color=None, title=None, horizontal=False, **kw):
    fig = px.bar(df, x=x, y=y, color=color, orientation="h" if horizontal else None,
                 text_auto=".0s" if horizontal else None, **kw)
    return apply_layout(fig, title)

def line_area(df, x, y, title=None, color=AZUL_CLARO):
    fig = px.area(df, x=x, y=y, title=title, color_discrete_sequence=[color])
    return apply_layout(fig)

def pie(df, values, names, title=None, color_map=None):
    fig = px.pie(df, values=values, names=names, title=title,
                 color=color_map is not None, color_discrete_map=color_map)
    return apply_layout(fig)

def scatter(df, x, y, size, color, hover_name, title=None):
    fig = px.scatter(df, x=x, y=y, size=size, color=color, hover_name=hover_name, title=title)
    return apply_layout(fig)

def treemap(df, path, values, title=None, color=None):
    fig = px.treemap(df, path=path, values=values, title=title, color=color, color_continuous_scale="Blues")
    return apply_layout(fig)
