"""Gráficos interactivos (Plotly) con la identidad visual de NAPO."""

import pandas as pd
import plotly.graph_objects as go

from .config import (
    BG_CARD_ALT, BG_DARK, BORDER_SUBTLE, KLEIN_BLUE_LIGHT, TEXT_PRIMARY, TEXT_SECONDARY,
    YOSHI_GREEN, YOSHI_ORANGE,
)


def grafico_precio(df: pd.DataFrame, tipo: str):
    """Gráfico interactivo (línea o velas) con los colores de la marca."""
    fig = go.Figure()
    if tipo == "Velas":
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                increasing_line_color=YOSHI_GREEN, decreasing_line_color=YOSHI_ORANGE,
                name="Precio",
            )
        )
        minimo, maximo = float(df["Low"].min()), float(df["High"].max())
    else:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["Close"], mode="lines", name="Cierre",
                line=dict(color=KLEIN_BLUE_LIGHT, width=2.2),
                fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.12)",
                hovertemplate="%{y:,.2f}<extra></extra>",
            )
        )
        minimo, maximo = float(df["Close"].min()), float(df["Close"].max())
    margen = (maximo - minimo) * 0.08 or maximo * 0.02
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=12),
        hovermode="x unified",
        showlegend=False,
        separators=",.",
        hoverlabel=dict(bgcolor=BG_CARD_ALT, bordercolor=BORDER_SUBTLE, font=dict(color=TEXT_PRIMARY)),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False), linecolor=BORDER_SUBTLE),
        yaxis=dict(
            gridcolor=BORDER_SUBTLE, zeroline=False, side="right", tickformat=",.2f",
            range=[minimo - margen, maximo + margen],
        ),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


def grafico_heatmap(df: pd.DataFrame):
    """Mapa de calor: verde sube, naranja baja. Todas las celdas del mismo tamaño."""
    tope = max(3.0, float(df["Variación (%)"].abs().max()))
    fig = go.Figure(
        go.Treemap(
            labels=df["Ticker"],
            parents=[""] * len(df),
            values=[1] * len(df),
            customdata=df["Variación (%)"],
            texttemplate="<b>%{label}</b><br>%{customdata:+.2f}%",
            hovertemplate="<b>%{label}</b><br>%{customdata:+.2f}%<extra></extra>",
            textfont=dict(size=18, color=TEXT_PRIMARY),
            tiling=dict(pad=2),
            marker=dict(
                colors=df["Variación (%)"],
                colorscale=[[0, YOSHI_ORANGE], [0.5, BG_CARD_ALT], [1, YOSHI_GREEN]],
                cmin=-tope, cmax=tope, cmid=0,
                line=dict(width=3, color=BG_DARK),
                showscale=False,
            ),
        )
    )
    fig.update_layout(
        height=340,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        separators=",.",
    )
    return fig
