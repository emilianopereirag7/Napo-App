"""
NAPO | Panel Táctico Financiero
--------------------------------
Panel táctico de mercado enfocado en Argentina y el mundo:
CEDEARs, Renta Variable ByMA, Bonos Soberanos, Dólares MEP/CCL, Riesgo País.

Ejecutar con:
    streamlit run app.py
"""

import hmac
import html
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# =============================================================================
# CONFIGURACIÓN GENERAL DE LA PÁGINA
# =============================================================================

try:
    _BASE_DIR = Path(__file__).resolve().parent
except NameError:
    _BASE_DIR = Path(".")
_FAVICON = _BASE_DIR / "favicon.png"

st.set_page_config(
    page_title="NAPO | Panel Táctico Financiero",
    page_icon=str(_FAVICON) if _FAVICON.exists() else "🧭",
    layout="wide",
    initial_sidebar_state="collapsed",  # La Cocina no debe recibir a los visitantes (sobre todo en celular)
)

# =============================================================================
# PALETA / IDENTIDAD VISUAL
# =============================================================================

KLEIN_BLUE = "#2563EB"
KLEIN_BLUE_DARK = "#1D4ED8"
KLEIN_BLUE_LIGHT = "#3B82F6"
BG_DARK = "#0B1120"
BG_CARD = "#111827"
BG_CARD_ALT = "#161F2E"
BORDER_SUBTLE = "#1F2A3C"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
YOSHI_GREEN = "#22C55E"
YOSHI_ORANGE = "#F97316"

# =============================================================================
# CSS GLOBAL — inyección forzada para pisar los estilos por defecto de Streamlit
# =============================================================================

CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    /* Fondo general forzado modo oscuro */
    .stApp {{
        background: linear-gradient(180deg, {BG_DARK} 0%, #0D1420 100%);
        color: {TEXT_PRIMARY};
    }}

    /* Ocultar elementos por defecto de Streamlit que ensucian el diseño */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    div[data-testid="stDecoration"] {{display: none;}}
    div[data-testid="stToolbar"] {{display: none;}}

    /* Contenedor principal */
    .block-container {{
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 1300px;
    }}

    /* ===================== MARQUESINA / TICKER SUPERIOR ===================== */
    .napo-ticker-wrap {{
        background: #070B14;
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 10px;
        padding: 10px 18px;
        margin-bottom: 18px;
        overflow: hidden;
        white-space: nowrap;
    }}
    .napo-ticker-inner {{
        display: inline-block;
        animation: napo-scroll 28s linear infinite;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        letter-spacing: 0.3px;
    }}
    .napo-ticker-wrap:hover .napo-ticker-inner {{
        animation-play-state: paused;
    }}
    @keyframes napo-scroll {{
        0%   {{ transform: translateX(0%); }}
        100% {{ transform: translateX(-50%); }}
    }}
    .napo-ticker-item {{
        display: inline-block;
        margin-right: 40px;
        color: {TEXT_SECONDARY};
    }}
    .napo-ticker-item b {{
        color: {TEXT_PRIMARY};
        margin-right: 6px;
    }}
    .napo-up {{ color: {YOSHI_GREEN}; font-weight: 600; }}
    .napo-down {{ color: {YOSHI_ORANGE}; font-weight: 600; }}

    /* ===================== HEADER / LOGO ===================== */
    .napo-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 2px 20px 2px;
    }}
    .napo-brand {{
        display: flex;
        align-items: baseline;
        gap: 10px;
    }}
    .napo-brand-mark {{
        font-size: 30px;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, {KLEIN_BLUE_LIGHT}, {KLEIN_BLUE});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .napo-brand-sub {{
        font-size: 12.5px;
        color: {TEXT_SECONDARY};
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 600;
    }}
    .napo-pill {{
        background: rgba(37, 99, 235, 0.12);
        border: 1px solid rgba(37, 99, 235, 0.4);
        color: {KLEIN_BLUE_LIGHT};
        font-size: 11.5px;
        font-weight: 600;
        padding: 5px 12px;
        border-radius: 999px;
        letter-spacing: 0.4px;
    }}

    /* ===================== TARJETAS KPI ===================== */
    .napo-card {{
        background: {BG_CARD};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 14px;
        padding: 16px 18px;
        height: 100%;
        transition: border-color 0.2s ease;
    }}
    .napo-card:hover {{
        border-color: {KLEIN_BLUE};
    }}
    .napo-card-label {{
        font-size: 11.5px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: {TEXT_SECONDARY};
        font-weight: 600;
        margin-bottom: 6px;
    }}
    .napo-card-value {{
        font-size: 24px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: -0.5px;
    }}
    .napo-card-delta {{
        font-size: 13px;
        font-weight: 600;
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
    }}

    .napo-card-sub {{
        font-size: 12px;
        color: {TEXT_SECONDARY};
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
    }}

    /* ===================== SECCIONES / TÍTULOS ===================== */
    .napo-section-title {{
        font-size: 15px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        margin: 22px 0 10px 0;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: 0.2px;
    }}
    .napo-section-title .bar {{
        width: 4px;
        height: 16px;
        background: {KLEIN_BLUE};
        border-radius: 2px;
        display: inline-block;
    }}

    /* ===================== FICHA TÉCNICA ===================== */
    .napo-ticket {{
        background: {BG_CARD};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 16px;
        padding: 22px 24px;
    }}
    .napo-ir-link {{
        font-size: 11.5px;
        color: {TEXT_SECONDARY} !important;
        text-decoration: none !important;
        border: 1px solid {BORDER_SUBTLE};
        padding: 3px 10px;
        border-radius: 999px;
        opacity: 0.8;
    }}
    .napo-ir-link:hover {{
        color: {KLEIN_BLUE_LIGHT} !important;
        border-color: {KLEIN_BLUE};
        opacity: 1;
    }}

    /* ===================== HEATMAP ===================== */
    .napo-heat-cell {{
        border-radius: 12px;
        padding: 14px 10px;
        text-align: center;
        font-family: 'JetBrains Mono', monospace;
        border: 1px solid rgba(255,255,255,0.06);
    }}
    .napo-heat-ticker {{
        font-size: 13px;
        font-weight: 700;
        opacity: 0.9;
    }}
    .napo-heat-value {{
        font-size: 18px;
        font-weight: 800;
        margin-top: 4px;
    }}

    /* ===================== REPRODUCTOR RETRO / CASSETTE ===================== */
    .napo-cassette {{
        background: linear-gradient(155deg, #2A2118 0%, #1A140D 100%);
        border: 1px solid #3A2E1F;
        border-radius: 16px;
        padding: 18px 20px;
        position: relative;
        box-shadow: inset 0 0 24px rgba(0,0,0,0.4);
    }}
    .napo-cassette-label {{
        background: #EFE6D0;
        color: #2A2118;
        border-radius: 6px;
        padding: 10px 14px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 12px;
        box-shadow: 0 2px 0 rgba(0,0,0,0.25);
    }}
    .napo-reels {{
        display: flex;
        justify-content: space-between;
        padding: 0 30px;
        margin-bottom: 10px;
    }}
    .napo-reel {{
        width: 46px;
        height: 46px;
        border-radius: 50%;
        background: radial-gradient(circle, #4A3B27 0%, #C9A96A 40%, #4A3B27 42%, #4A3B27 100%);
        border: 3px solid #6B5533;
        animation: napo-spin 4s linear infinite;
    }}
    @keyframes napo-spin {{
        from {{ transform: rotate(0deg); }}
        to   {{ transform: rotate(360deg); }}
    }}
    .napo-cassette-meta {{
        display: flex;
        justify-content: space-between;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #C9A96A;
        margin-top: 4px;
    }}

    /* ===================== BADGES ALCISTA / BAJISTA ===================== */
    .napo-badge-up {{
        background: rgba(34, 197, 94, 0.12);
        color: {YOSHI_GREEN};
        border: 1px solid rgba(34, 197, 94, 0.35);
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
    }}
    .napo-badge-down {{
        background: rgba(249, 115, 22, 0.12);
        color: {YOSHI_ORANGE};
        border: 1px solid rgba(249, 115, 22, 0.35);
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
    }}

    .napo-badge-neutral {{
        background: rgba(37, 99, 235, 0.12);
        color: {KLEIN_BLUE_LIGHT};
        border: 1px solid rgba(37, 99, 235, 0.35);
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
    }}

    /* ===================== TABS ===================== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: {BG_CARD};
        padding: 6px;
        border-radius: 12px;
        border: 1px solid {BORDER_SUBTLE};
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 42px;
        border-radius: 8px;
        color: {TEXT_SECONDARY};
        font-weight: 600;
        font-size: 13.5px;
    }}
    .stTabs [aria-selected="true"] {{
        background: {KLEIN_BLUE} !important;
        color: white !important;
    }}

    /* ===================== INPUTS / WIDGETS ===================== */
    div[data-baseweb="select"] > div {{
        background: {BG_CARD_ALT} !important;
        border-color: {BORDER_SUBTLE} !important;
        color: {TEXT_PRIMARY} !important;
    }}
    .stTextInput input {{
        background: {BG_CARD_ALT} !important;
        color: {TEXT_PRIMARY} !important;
        border-color: {BORDER_SUBTLE} !important;
    }}
    .stButton button {{
        background: {KLEIN_BLUE};
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 18px;
        transition: background 0.15s ease;
    }}
    .stButton button:hover {{
        background: {KLEIN_BLUE_DARK};
        color: white;
    }}

    /* ===================== SIDEBAR / COCINA ===================== */
    section[data-testid="stSidebar"] {{
        background: #070B14;
        border-right: 1px solid {BORDER_SUBTLE};
    }}
    section[data-testid="stSidebar"] .napo-kitchen-title {{
        font-size: 13px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: {KLEIN_BLUE_LIGHT};
        margin-bottom: 2px;
    }}
    section[data-testid="stSidebar"] textarea {{
        background: {BG_CARD_ALT} !important;
        color: {TEXT_PRIMARY} !important;
        border-color: {BORDER_SUBTLE} !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12.5px !important;
    }}

    /* Expanders (Academia NAPO) */
    .streamlit-expanderHeader {{
        background: {BG_CARD} !important;
        border: 1px solid {BORDER_SUBTLE} !important;
        border-radius: 10px !important;
        color: {TEXT_PRIMARY} !important;
        font-weight: 600 !important;
    }}

    /* ===================== CONTENEDORES CON BORDE (ficha técnica) ===================== */
    div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stForm"] {{
        background: {BG_CARD};
        border: 1px solid {BORDER_SUBTLE} !important;
        border-radius: 16px !important;
    }}

    /* ===================== BANNER DEMO ===================== */
    .napo-demo-banner {{
        background: rgba(249, 115, 22, 0.10);
        border: 1px solid rgba(249, 115, 22, 0.35);
        color: {YOSHI_ORANGE};
        border-radius: 10px;
        padding: 9px 14px;
        font-size: 12.5px;
        font-weight: 600;
        margin-bottom: 14px;
        text-align: center;
    }}

    /* Expanders en versiones nuevas de Streamlit */
    div[data-testid="stExpander"] {{
        background: {BG_CARD};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 10px;
    }}
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary p {{
        color: {TEXT_PRIMARY} !important;
        font-weight: 600;
    }}

    /* ===================== PULIDO VISUAL ===================== */
    .napo-brand {{ align-items: center; gap: 12px; }}
    .napo-logo {{ flex: none; filter: drop-shadow(0 4px 14px rgba(37, 99, 235, 0.35)); }}
    .napo-brand-text {{ display: flex; flex-direction: column; line-height: 1.1; }}
    .napo-brand-sub {{ margin-top: 4px; }}

    .napo-card-value {{
        font-size: clamp(19px, 2.1vw, 25px);
        font-variant-numeric: tabular-nums;
    }}
    .napo-ticker-inner {{ font-variant-numeric: tabular-nums; }}

    /* Grilla de tarjetas: 5 en una fila en escritorio, 2 por fila en celular */
    .napo-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
    }}

    .napo-kpi-grid .napo-card {{ height: auto; }}

    /* Estado "sin datos" prolijo */
    .napo-empty {{
        border: 1px dashed {BORDER_SUBTLE};
        border-radius: 14px;
        background: rgba(17, 24, 39, 0.6);
        padding: 26px 18px;
        text-align: center;
        margin: 8px 0;
    }}
    .napo-empty-icon {{ font-size: 26px; margin-bottom: 6px; }}
    .napo-empty-title {{ font-weight: 700; color: {TEXT_PRIMARY}; font-size: 15px; }}
    .napo-empty-text {{ color: {TEXT_SECONDARY}; font-size: 13px; margin-top: 4px; }}

    div[data-testid="stSpinner"] p {{ color: {TEXT_SECONDARY} !important; }}

    /* ===================== CELULAR ===================== */
    @media (max-width: 768px) {{
        .block-container {{ padding-left: 0.9rem; padding-right: 0.9rem; padding-top: 0.6rem; }}
        .napo-pill {{ display: none; }}
        .napo-brand-mark {{ font-size: 26px; }}
        .napo-brand-sub {{ font-size: 10.5px; letter-spacing: 1.2px; }}
        .napo-header {{ padding-bottom: 12px; }}
        .napo-card {{ padding: 12px 14px; }}
        .napo-section-title {{ margin-top: 16px; }}
        .napo-ticker-wrap {{ padding: 8px 12px; }}
        .napo-ticker-inner {{ font-size: 12px; animation-duration: 22s; }}
        .stTabs [data-baseweb="tab-list"] {{ overflow-x: auto; flex-wrap: nowrap; }}
        .stTabs [data-baseweb="tab"] {{ white-space: nowrap; padding: 0 12px; font-size: 12.5px; }}
        .napo-cassette {{ padding: 14px; }}
        .napo-reel {{ width: 36px; height: 36px; }}
        .napo-demo-banner {{ font-size: 11.5px; padding: 8px 10px; }}
    }}

    /* Accesibilidad: menos movimiento si el dispositivo lo pide */
    @media (prefers-reduced-motion: reduce) {{
        .napo-reel {{ animation: none; }}
        .napo-ticker-inner {{ animation-duration: 90s; }}
    }}

    /* Scrollbar prolija */
    ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
    ::-webkit-scrollbar-track {{ background: {BG_DARK}; }}
    ::-webkit-scrollbar-thumb {{ background: {BORDER_SUBTLE}; border-radius: 4px; }}

    .napo-footer {{
        text-align: center;
        color: {TEXT_SECONDARY};
        font-size: 11.5px;
        padding: 30px 0 10px 0;
        border-top: 1px solid {BORDER_SUBTLE};
        margin-top: 30px;
    }}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============================================================================
# ACTIVOS Y DATOS DE MERCADO
# =============================================================================

# "yahoo" es el símbolo con el que Yahoo Finance publica cada papel en ByMA (.BA).
ACTIVOS = {
    "YPF": {"nombre": "YPF S.A.", "sector": "Energía", "yahoo": "YPFD.BA"},
    "PAMP": {"nombre": "Pampa Energía", "sector": "Energía", "yahoo": "PAMP.BA"},
    "GGAL": {"nombre": "Grupo Financiero Galicia", "sector": "Bancos", "yahoo": "GGAL.BA"},
    "TXAR": {"nombre": "Ternium Argentina", "sector": "Siderurgia", "yahoo": "TXAR.BA"},
    "ALUA": {"nombre": "Aluar Aluminio Argentino", "sector": "Industria", "yahoo": "ALUA.BA"},
    "BMA": {"nombre": "Banco Macro", "sector": "Bancos", "yahoo": "BMA.BA"},
    "CEPU": {"nombre": "Central Puerto", "sector": "Energía", "yahoo": "CEPU.BA"},
    "MELI": {"nombre": "MercadoLibre (CEDEAR)", "sector": "Tecnología", "yahoo": "MELI.BA"},
}

# Índices y commodities de la marquesina: (nombre, símbolo Yahoo, prefijo, decimales)
INDICES_MARQUESINA = [
    ("Merval", "^MERV", "", 0),
    ("S&P 500", "^GSPC", "", 0),
    ("WTI", "CL=F", "US$ ", 2),
    ("Oro", "GC=F", "US$ ", 0),
]

SIMBOLOS_TODOS = [a["yahoo"] for a in ACTIVOS.values()] + [i[1] for i in INDICES_MARQUESINA]

IR_LINKS = {
    "YPF": "https://inversores.ypf.com",
    "PAMP": "https://ri.pampa.com",
    "GGAL": "https://www.gfgsa.com/relaciones-con-inversores",
    "TXAR": "https://www.ternium.com.ar/inversores",
    "ALUA": "https://www.aluar.com.ar/inversores",
    "BMA": "https://www.macro.com.ar/ir",
    "CEPU": "https://www.centralpuerto.com/inversores",
    "MELI": "https://investor.mercadolibre.com",
}

NOTICIAS_TACTICAS = {
    "YPF": "El mercado sigue de cerca el cronograma de la FID de Argentina LNG, con financiamiento en curso vía ECAs y bancos comerciales.",
    "PAMP": "Mindlin proyecta un EBITDA anual de la planta de urea comparable al de generación y oil & gas combinados.",
    "GGAL": "El sector bancario acompaña la mejora de expectativas de crédito privado en un contexto de tasas reales positivas.",
    "TXAR": "La demanda de acero se mantiene ligada al ciclo de obra pública y construcción privada en recuperación.",
    "ALUA": "Exportaciones de aluminio sostenidas por precios internacionales firmes y demanda de la industria automotriz.",
    "BMA": "Banco Macro amplía su cartera de créditos en un escenario de desinflación gradual.",
    "CEPU": "Central Puerto evalúa nuevas inversiones en generación térmica y renovable de cara a 2027.",
    "MELI": "MercadoLibre sostiene el ritmo de crecimiento en comercio electrónico y fintech en toda la región.",
}


@st.cache_data(ttl=600, show_spinner="Trayendo precios del mercado…")
def _descargar_precios():
    """Una sola descarga (1 año, diario) con todos los símbolos. Lanza error si falla."""
    datos = yf.download(
        SIMBOLOS_TODOS,
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if datos is None or datos.empty:
        raise ValueError("Yahoo Finance no devolvió datos")
    return datos


def cargar_precios():
    """Devuelve la tabla de precios o None. Si falla, no reintenta durante 60 segundos."""
    ahora = time.time()
    if ahora - st.session_state.get("precios_fallo_ts", 0) < 60:
        return None
    try:
        return _descargar_precios()
    except Exception:
        st.session_state["precios_fallo_ts"] = ahora
        return None


def serie_activo(datos, simbolo) -> pd.DataFrame:
    """Extrae Open/High/Low/Close/Volume de un símbolo (vacío si no hay datos)."""
    if datos is None:
        return pd.DataFrame()
    try:
        df = datos[simbolo][["Open", "High", "Low", "Close", "Volume"]].copy()
    except Exception:
        return pd.DataFrame()
    df = df.dropna(subset=["Close"])
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def resumen_serie(df):
    """Último precio, variación diaria, volumen, amplitud del día y rango del año."""
    if df is None or len(df) < 2:
        return None
    ultimo = float(df["Close"].iloc[-1])
    previo = float(df["Close"].iloc[-2])
    fila = df.iloc[-1]
    var = (ultimo / previo - 1) * 100 if previo else 0.0
    amplitud = 0.0
    if ultimo and pd.notna(fila["High"]) and pd.notna(fila["Low"]):
        amplitud = (float(fila["High"]) - float(fila["Low"])) / ultimo * 100
    return {
        "ultimo": ultimo,
        "var": var,
        "volumen": float(fila["Volume"]) if pd.notna(fila["Volume"]) else 0.0,
        "amplitud": amplitud,
        "fecha": df.index[-1],
        "min_1a": float(df["Close"].min()),
        "max_1a": float(df["Close"].max()),
    }


def fmt_numero(valor, decimales: int = 2) -> str:
    """1234567.891 -> '1.234.567,89' (formato argentino)."""
    texto = f"{float(valor):,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(valor) -> str:
    """-1.256 -> '1,26%' (sin signo; el signo lo marca la flecha)."""
    return f"{abs(float(valor)):.2f}".replace(".", ",") + "%"


def fmt_var(valor) -> str:
    """1.256 -> '+1,26%' (con signo, coma decimal)."""
    return f"{float(valor):+.2f}".replace(".", ",") + "%"


RANGOS = {"1M": 31, "3M": 92, "6M": 183, "1A": 366}


def recortar_rango(df: pd.DataFrame, rango: str) -> pd.DataFrame:
    corte = df.index.max() - pd.Timedelta(days=RANGOS[rango])
    return df[df.index >= corte]


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


def _kpi_html(label: str, value: str, delta: str = None, positive: bool = True, sub: str = None) -> str:
    extra = ""
    if delta:
        color = YOSHI_GREEN if positive else YOSHI_ORANGE
        arrow = "▲" if positive else "▼"
        extra += f'<div class="napo-card-delta" style="color:{color};">{arrow} {html.escape(delta)}</div>'
    if sub:
        extra += f'<div class="napo-card-sub">{html.escape(sub)}</div>'
    return (
        f'<div class="napo-card"><div class="napo-card-label">{html.escape(label)}</div>'
        f'<div class="napo-card-value">{html.escape(value)}</div>{extra}</div>'
    )


def kpi_card(label: str, value: str, delta: str = None, positive: bool = True, sub: str = None):
    st.markdown(_kpi_html(label, value, delta, positive, sub), unsafe_allow_html=True)


def kpi_grid(items: list):
    """Fila de tarjetas que se acomoda sola: varias por fila en escritorio, 2 por fila en celular.
    items: lista de dicts con las claves label, value y opcionalmente delta, positive, sub."""
    celdas = "".join(_kpi_html(**item) for item in items)
    st.markdown(f'<div class="napo-kpi-grid">{celdas}</div>', unsafe_allow_html=True)


def estado_vacio(titulo: str, detalle: str, icono: str = "📡"):
    """Cartel prolijo para cuando una fuente de datos no responde."""
    st.markdown(
        f'<div class="napo-empty"><div class="napo-empty-icon">{icono}</div>'
        f'<div class="napo-empty-title">{html.escape(titulo)}</div>'
        f'<div class="napo-empty-text">{html.escape(detalle)}</div></div>',
        unsafe_allow_html=True,
    )


def section_title(text: str, icon: str = ""):
    st.markdown(
        f'<div class="napo-section-title"><span class="bar"></span>{icon} {text}</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# DATOS REALES: DÓLARES (DolarApi) Y RIESGO PAÍS (ArgentinaDatos)
# =============================================================================

DOLARAPI_URL = "https://dolarapi.com/v1/dolares"
RIESGO_PAIS_URL = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo"
HTTP_TIMEOUT = 6  # segundos máximos de espera por cada fuente
TZ_ARG = timezone(timedelta(hours=-3))  # Argentina no usa horario de verano


@st.cache_data(ttl=120, show_spinner=False)
def obtener_dolares():
    """Devuelve {casa: cotización} desde DolarApi, o None si la fuente falla."""
    try:
        resp = requests.get(DOLARAPI_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return {item["casa"]: item for item in resp.json()}
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def obtener_riesgo_pais():
    """Devuelve {valor, fecha} del último riesgo país, o None si la fuente falla."""
    try:
        resp = requests.get(RIESGO_PAIS_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        dato = resp.json()
        return {"valor": float(dato["valor"]), "fecha": str(dato["fecha"])}
    except Exception:
        return None


def fmt_pesos(valor) -> str:
    """1515.97 -> '$ 1.515,97' (formato argentino)."""
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {texto}"


def parse_iso(texto):
    """Convierte un texto ISO 8601 a datetime en hora argentina (o None)."""
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone(TZ_ARG)
    except Exception:
        return None


def fmt_fecha_corta(texto) -> str:
    """'2026-11-10' -> '10/11/2026'."""
    try:
        return datetime.strptime(str(texto)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(texto)


DOLARES_PANEL = [
    ("Dólar Oficial", "oficial"),
    ("Dólar MEP", "bolsa"),
    ("Dólar CCL", "contadoconliqui"),
    ("Dólar Blue", "blue"),
]

dolares = obtener_dolares()
riesgo_pais = obtener_riesgo_pais()
precios = cargar_precios()

# =============================================================================
# MARQUESINA GLOBAL DE MERCADO (solo con datos reales)
# =============================================================================

marquee_items = []  # (nombre, valor, variación en texto o None, sube True/False/None)
for etiqueta, casa in DOLARES_PANEL:
    cot = (dolares or {}).get(casa)
    if cot and cot.get("venta") is not None:
        marquee_items.append((etiqueta, fmt_pesos(cot["venta"]), None, None))
if riesgo_pais:
    marquee_items.append(("Riesgo País", f"{int(round(riesgo_pais['valor']))} pb", None, None))
for nombre, simbolo, prefijo, decimales in INDICES_MARQUESINA:
    r = resumen_serie(serie_activo(precios, simbolo))
    if r:
        marquee_items.append(
            (nombre, f"{prefijo}{fmt_numero(r['ultimo'], decimales)}", fmt_pct(r["var"]), r["var"] >= 0)
        )
if not marquee_items:
    marquee_items = [("NAPO", "Panel Táctico Financiero", None, None)]


def _item_marquesina(nombre, valor, chg, sube):
    cambio = ""
    if chg is not None:
        clase = "napo-up" if sube else "napo-down"
        flecha = "▲" if sube else "▼"
        cambio = f' <span class="{clase}">{flecha} {chg}</span>'
    return f'<span class="napo-ticker-item"><b>{nombre}</b>{valor}{cambio}</span>'


ticker_html = "".join(_item_marquesina(*item) for item in (marquee_items * 4))
st.markdown(
    f'<div class="napo-ticker-wrap"><div class="napo-ticker-inner">{ticker_html}</div></div>',
    unsafe_allow_html=True,
)

# =============================================================================
# HEADER
# =============================================================================

LOGO_SVG = (
    '<svg class="napo-logo" width="42" height="42" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="NAPO"><rect width="48" height="48" rx="12" fill="#2563EB"/><path d="M24 8 L32 24 L16 24 Z" fill="#FFFFFF"/><path d="M24 40 L32 24 L16 24 Z" fill="#FFFFFF" fill-opacity="0.38"/><circle cx="24" cy="24" r="2.6" fill="#2563EB"/></svg>'
)

st.markdown(
    f'<div class="napo-header"><div class="napo-brand">{LOGO_SVG}'
    '<div class="napo-brand-text"><span class="napo-brand-mark">NAPO</span>'
    '<span class="napo-brand-sub">Panel Táctico Financiero</span></div></div>'
    '<div class="napo-pill">Menos ruido, más decisión</div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="napo-demo-banner">🧪 VERSIÓN DEMO · Dólares, riesgo país y precios con datos reales (pueden tener demora); '
    'novedades, audios y comunidad son de ejemplo. '
    'No constituye asesoramiento financiero.</div>',
    unsafe_allow_html=True,
)

# =============================================================================
# KPIs CAMBIARIOS
# =============================================================================

section_title("Panel Cambiario", "💵")

if dolares is None and riesgo_pais is None:
    estado_vacio("Cotizaciones no disponibles", "No pudimos traer las cotizaciones en este momento. Probá recargar la página en unos minutos.", "💵")

items_cambio = []
for etiqueta, casa in DOLARES_PANEL:
    cot = (dolares or {}).get(casa)
    if cot and cot.get("venta") is not None:
        sub = f"Compra {fmt_pesos(cot['compra'])}" if cot.get("compra") is not None else None
        items_cambio.append(dict(label=etiqueta, value=fmt_pesos(cot["venta"]), sub=sub))
    else:
        items_cambio.append(dict(label=etiqueta, value="—", sub="Sin datos por ahora"))
if riesgo_pais:
    items_cambio.append(dict(label="Riesgo País", value=f"{int(round(riesgo_pais['valor']))} pb",
                             sub=f"Dato del {fmt_fecha_corta(riesgo_pais['fecha'])}"))
else:
    items_cambio.append(dict(label="Riesgo País", value="—", sub="Sin datos por ahora"))
if not (dolares is None and riesgo_pais is None):
    kpi_grid(items_cambio)

horas = [parse_iso(c.get("fechaActualizacion")) for c in (dolares or {}).values()]
horas = [h for h in horas if h is not None]
actualizado = max(horas).strftime("%d/%m %H:%M") if horas else "s/d"
st.caption(
    f"Cotizaciones de venta · Fuentes: DolarApi y ArgentinaDatos · "
    f"Última actualización de dólares: {actualizado} (hora Argentina)"
)

# =============================================================================
# SIDEBAR — "LA COCINA" (Back-office del operador)
# =============================================================================

def clave_correcta(ingresada: str) -> bool:
    """Compara la clave ingresada con la guardada en Secrets (COCINA_CLAVE)."""
    try:
        esperada = str(st.secrets["COCINA_CLAVE"])
    except Exception:
        return False
    if not esperada:
        return False
    return hmac.compare_digest(ingresada.encode("utf-8"), esperada.encode("utf-8"))


with st.sidebar:
    st.markdown('<div class="napo-kitchen-title">🔧 La Cocina</div>', unsafe_allow_html=True)
    st.caption("Back-office interno · uso exclusivo del operador")
    st.divider()

    if not st.session_state.get("cocina_ok", False):
        st.markdown("**Acceso restringido**")
        clave = st.text_input("Clave de acceso", type="password", key="cocina_clave")
        if st.button("Entrar", key="cocina_entrar"):
            if clave_correcta(clave):
                st.session_state["cocina_ok"] = True
                st.rerun()
            else:
                st.error("Clave incorrecta o no configurada.")
    else:
        st.markdown("**Prompt Maestro — Procesar Noticia**")
        ticker_cocina = st.text_input("Ticker", placeholder="Ej: $PAMP")
        fuente_cocina = st.text_input("Fuente / link", placeholder="URL o nombre del medio")
        nota_bruta = st.text_area(
            "Pegar noticia / nota en bruto",
            height=180,
            placeholder="Pegar aquí el texto de la noticia a procesar...",
        )

        if st.button("⚡ Generar reporte exprés"):
            if nota_bruta.strip():
                st.success("Nota cargada. Lista para procesar con el prompt maestro NAPO.")
            else:
                st.warning("Pegá el texto de la noticia antes de generar el reporte.")

        st.divider()
        st.markdown("**Estado del sistema**")
        st.caption(f"Última sincronización: {datetime.now().strftime('%d/%m/%Y %H:%M')} hs")
        st.caption("Fuentes: DolarApi, ArgentinaDatos y Yahoo Finance · novedades/audio de ejemplo")

        if st.button("Cerrar sesión de La Cocina"):
            st.session_state["cocina_ok"] = False
            st.rerun()

# =============================================================================
# TABS PRINCIPALES
# =============================================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📡 Explorador de Activos", "🔥 Ranking & Heatmap", "📻 Audio-Resúmenes", "🎓 Academia NAPO", "💬 Comunidad"]
)

# -----------------------------------------------------------------------------
# TAB 1 — EXPLORADOR DE ACTIVOS
# -----------------------------------------------------------------------------
with tab1:
    section_title("Radar de Activos", "📡")

    col_search, _ = st.columns([1, 2])
    with col_search:
        ticker_sel = st.selectbox("Buscar ticker", list(ACTIVOS.keys()), index=0)

    info = ACTIVOS[ticker_sel]
    ir_link = IR_LINKS[ticker_sel]
    df_activo = serie_activo(precios, info["yahoo"])
    resumen = resumen_serie(df_activo)

    with st.container(border=True):
        top_a, top_b = st.columns([3, 1])
        with top_a:
            st.markdown(f"### {ticker_sel} · {info['nombre']}")
            st.caption(f"Sector: {info['sector']}")
        with top_b:
            st.markdown(
                f'<div style="text-align:right; padding-top:6px;">'
                f'<a class="napo-ir-link" href="{ir_link}" target="_blank" rel="noopener noreferrer">'
                f"Relaciones con Inversores ↗</a></div>",
                unsafe_allow_html=True,
            )

        if resumen is None:
            estado_vacio("Sin precios por ahora", "No pudimos traer los precios de este activo. Probá recargar en unos minutos.", "📉")
        else:
            kpi_grid([
                dict(label="Último precio (ARS)", value=fmt_pesos(resumen["ultimo"])),
                dict(label="Variación diaria", value=fmt_pct(resumen["var"]),
                     delta="vs. cierre anterior", positive=resumen["var"] >= 0),
                dict(label="Volumen", value=fmt_numero(resumen["volumen"], 0), sub="último día operado"),
                dict(label="Rango 1 año",
                     value=f"{fmt_numero(resumen['min_1a'], 0)}–{fmt_numero(resumen['max_1a'], 0)}",
                     sub="mín–máx de cierres"),
            ])

            st.markdown("<br>", unsafe_allow_html=True)
            ctrl1, ctrl2 = st.columns([1, 1])
            with ctrl1:
                rango = st.radio("Rango", list(RANGOS.keys()), index=1, horizontal=True, key="rango_grafico")
            with ctrl2:
                tipo = st.radio("Tipo de gráfico", ["Línea", "Velas"], horizontal=True, key="tipo_grafico")

            df_rec = recortar_rango(df_activo, rango)
            try:
                st.plotly_chart(grafico_precio(df_rec, tipo), config={"displayModeBar": False})
            except Exception:
                st.line_chart(df_rec["Close"], color=KLEIN_BLUE, height=320)
            st.caption(
                f"Fuente: Yahoo Finance (puede tener demora) · Último dato: "
                f"{resumen['fecha'].strftime('%d/%m/%Y')}"
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**🎯 Resumen táctico (ejemplo)**")
        st.info(NOTICIAS_TACTICAS.get(ticker_sel, "Sin novedades tácticas registradas."))

        # Reproductor de audio vintage integrado
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="napo-cassette">
                <div class="napo-cassette-label">▸ PÍLDORA TÁCTICA · {ticker_sel}.WAV</div>
                <div class="napo-reels">
                    <div class="napo-reel"></div>
                    <div class="napo-reel"></div>
                </div>
                <div class="napo-cassette-meta">
                    <span>SIDE A</span><span>02:14 / 03:40</span><span>NAPO REC.</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.audio(
            "https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg",
            format="audio/ogg",
        )
        st.caption("Audio de ejemplo — reemplazar por el resumen de voz real del activo seleccionado.")


# -----------------------------------------------------------------------------
# TAB 2 — RANKING & HEATMAP
# -----------------------------------------------------------------------------
with tab2:
    section_title("Heatmap de Rendimiento Diario", "🔥")

    filas = []
    for tk, datos_tk in ACTIVOS.items():
        r = resumen_serie(serie_activo(precios, datos_tk["yahoo"]))
        if r:
            filas.append({
                "Ticker": tk,
                "Último": round(r["ultimo"], 2),
                "Variación (%)": round(r["var"], 2),
                "Volumen": int(r["volumen"]),
                "Amplitud (%)": round(r["amplitud"], 2),
            })
    df_rend = pd.DataFrame(filas)

    if df_rend.empty:
        estado_vacio("Mercado sin datos por ahora", "No pudimos traer los precios del mercado. Probá recargar en unos minutos.", "📉")
    else:
        df_rend = df_rend.sort_values("Variación (%)", ascending=False).reset_index(drop=True)

        try:
            st.plotly_chart(grafico_heatmap(df_rend), config={"displayModeBar": False})
        except Exception:
            st.dataframe(df_rend.set_index("Ticker"))
        st.caption("Variación diaria vs. cierre anterior · Celdas del mismo tamaño (no representan capitalización) · "
                   "Fuente: Yahoo Finance, con posible demora.")

        rank_col1, rank_col2, rank_col3 = st.columns(3)

        with rank_col1:
            section_title("Top Ganadores", "🟢")
            for _, row in df_rend.head(3).iterrows():
                clase = "napo-badge-up" if row["Variación (%)"] >= 0 else "napo-badge-down"
                st.markdown(
                    f'<div class="napo-card" style="margin-bottom:8px;">'
                    f'<b>{row["Ticker"]}</b> '
                    f'<span class="{clase}">{fmt_var(row["Variación (%)"])}</span></div>',
                    unsafe_allow_html=True,
                )

        with rank_col2:
            section_title("Top Perdedores", "🔴")
            for _, row in df_rend.sort_values("Variación (%)").head(3).iterrows():
                clase = "napo-badge-up" if row["Variación (%)"] >= 0 else "napo-badge-down"
                st.markdown(
                    f'<div class="napo-card" style="margin-bottom:8px;">'
                    f'<b>{row["Ticker"]}</b> '
                    f'<span class="{clase}">{fmt_var(row["Variación (%)"])}</span></div>',
                    unsafe_allow_html=True,
                )

        with rank_col3:
            section_title("Mayor Amplitud del Día", "⚡")
            for _, row in df_rend.sort_values("Amplitud (%)", ascending=False).head(3).iterrows():
                st.markdown(
                    f'<div class="napo-card" style="margin-bottom:8px;">'
                    f'<b>{row["Ticker"]}</b> '
                    f'<span class="napo-badge-neutral">rango {fmt_pct(row["Amplitud (%)"])}</span></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Tabla completa**")
        st.dataframe(df_rend[["Ticker", "Último", "Variación (%)", "Volumen"]].set_index("Ticker"))


# -----------------------------------------------------------------------------
# TAB 3 — AUDIO-RESÚMENES (MODO CASSETTE)
# -----------------------------------------------------------------------------
with tab3:
    section_title("Modo Cassette · Píldoras Diarias", "📻")
    st.caption("Un resumen corto por día, en formato audio, sin vueltas.")

    audio_col1, audio_col2 = st.columns(2)
    episodios = [
        ("APERTURA DE RUEDA", "04:12", "Panorama de apertura Merval + CEDEARs"),
        ("CIERRE TÁCTICO", "05:03", "Resumen de cierre y qué mirar mañana"),
    ]
    for col, (titulo, dur, desc) in zip([audio_col1, audio_col2], episodios):
        with col:
            st.markdown(
                f"""
                <div class="napo-cassette">
                    <div class="napo-cassette-label">▸ {titulo}</div>
                    <div class="napo-reels">
                        <div class="napo-reel"></div>
                        <div class="napo-reel"></div>
                    </div>
                    <div class="napo-cassette-meta">
                        <span>NAPO FM</span><span>{dur}</span><span>HOY</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(desc)
            st.audio(
                "https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg",
                format="audio/ogg",
            )
            st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# TAB 4 — ACADEMIA NAPO
# -----------------------------------------------------------------------------
with tab4:
    section_title("Academia NAPO · Glosario Táctico", "🎓")

    glosario = {
        "CEDEAR": "Certificado de Depósito Argentino que representa acciones de empresas extranjeras, "
                  "operable en pesos dentro de ByMA.",
        "Dólar MEP": "Tipo de cambio que surge de comprar un bono en pesos y venderlo en dólares dentro "
                     "del mercado local, de forma legal y sin cepo operativo.",
        "Dólar CCL (Contado con Liqui)": "Similar al MEP, pero permite sacar los dólares fuera del país "
                                          "al liquidarse la operación en una cuenta en el exterior.",
        "Riesgo País": "Indicador (en puntos básicos) que mide el sobrecosto que paga un país para "
                       "financiarse en el mercado internacional respecto a EE.UU.",
        "EBITDA": "Ganancias antes de intereses, impuestos, depreciaciones y amortizaciones. Mide la "
                  "rentabilidad operativa pura de una empresa.",
        "RIGI": "Régimen de Incentivo para Grandes Inversiones: otorga estabilidad fiscal, cambiaria y "
                "aduanera a 30 años para proyectos superiores a US$200 millones en Argentina.",
        "Arbitraje CCL": "Estrategia de comprar un activo en pesos y venderlo en dólares (o viceversa) "
                          "aprovechando diferencias de precio entre mercados.",
        "Renta Variable": "Instrumentos financieros (como acciones) cuyo rendimiento no está garantizado "
                           "y depende de la evolución del mercado.",
    }

    for termino, definicion in glosario.items():
        with st.expander(f"📘 {termino}"):
            st.write(definicion)

# -----------------------------------------------------------------------------
# TAB 5 — COMUNIDAD
# -----------------------------------------------------------------------------
with tab5:
    section_title("Comunidad NAPO", "💬")
    st.caption("Demo: los comentarios se guardan solo en tu sesión y se pierden al recargar. Los dos primeros son de ejemplo.")

    if "napo_comentarios" not in st.session_state:
        st.session_state.napo_comentarios = [
            {"user": "Ejemplo", "msg": "¿Alguien más viendo el arbitraje CCL en GGAL hoy?", "ts": "10:32"},
            {"user": "Ejemplo", "msg": "PAMP con buen volumen tras la noticia de la planta de urea.", "ts": "11:05"},
        ]

    with st.form("napo_comment_form", clear_on_submit=True):
        nuevo_comentario = st.text_area("Compartir un comentario táctico", height=80)
        enviado = st.form_submit_button("Publicar")
        if enviado and nuevo_comentario.strip():
            st.session_state.napo_comentarios.append(
                {"user": "Vos", "msg": nuevo_comentario.strip()[:280], "ts": datetime.now().strftime("%H:%M")}
            )

    st.markdown("<br>", unsafe_allow_html=True)
    for c in reversed(st.session_state.napo_comentarios):
        st.markdown(
            f"""
            <div class="napo-card" style="margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between;">
                    <b style="color:{KLEIN_BLUE_LIGHT};">{html.escape(c['user'])}</b>
                    <span style="color:{TEXT_SECONDARY}; font-size:11.5px;">{c['ts']}</span>
                </div>
                <div style="margin-top:6px; color:{TEXT_PRIMARY};">{html.escape(c['msg'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# =============================================================================
# FOOTER
# =============================================================================

st.markdown(
    """
    <div class="napo-footer">
        NAPO | Panel Táctico Financiero — Menos ruido, datos duros y decisiones tácticas.<br>
        Dólares y riesgo país: DolarApi y ArgentinaDatos. Precios: Yahoo Finance (pueden tener demora). Novedades, audios y comunidad: contenido de ejemplo. No constituye asesoramiento financiero.
    </div>
    """,
    unsafe_allow_html=True,
)
