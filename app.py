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
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# =============================================================================
# CONFIGURACIÓN GENERAL DE LA PÁGINA
# =============================================================================

st.set_page_config(
    page_title="NAPO | Panel Táctico Financiero",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
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
# DATOS SIMULADOS (reemplazar por fuente real / API cuando esté disponible)
# =============================================================================

ACTIVOS = {
    "YPF": {"nombre": "YPF S.A.", "sector": "Energía", "mkt_cap": "US$ 20.400 M", "prox_balance": "05-Nov-2026"},
    "PAMP": {"nombre": "Pampa Energía", "sector": "Energía", "mkt_cap": "US$ 8.900 M", "prox_balance": "12-Nov-2026"},
    "GGAL": {"nombre": "Grupo Financiero Galicia", "sector": "Bancos", "mkt_cap": "US$ 7.100 M", "prox_balance": "20-Oct-2026"},
    "TXAR": {"nombre": "Ternium Argentina", "sector": "Siderurgia", "mkt_cap": "US$ 2.300 M", "prox_balance": "28-Oct-2026"},
    "ALUA": {"nombre": "Aluar Aluminio Argentino", "sector": "Industria", "mkt_cap": "US$ 2.900 M", "prox_balance": "15-Nov-2026"},
    "BMA": {"nombre": "Banco Macro", "sector": "Bancos", "mkt_cap": "US$ 4.600 M", "prox_balance": "22-Oct-2026"},
    "CEPU": {"nombre": "Central Puerto", "sector": "Energía", "mkt_cap": "US$ 3.100 M", "prox_balance": "10-Nov-2026"},
    "MELI": {"nombre": "MercadoLibre", "sector": "Tecnología", "mkt_cap": "US$ 90.500 M", "prox_balance": "05-Nov-2026"},
}

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


@st.cache_data(ttl=300)
def generar_serie_precios(ticker: str, dias: int = 90) -> pd.DataFrame:
    """Genera una serie de precios simulada (random walk) para graficar."""
    seed = sum(ord(c) for c in ticker)
    rng = np.random.default_rng(seed)
    fechas = [datetime.today() - timedelta(days=i) for i in range(dias)][::-1]
    precio_inicial = 100 + (seed % 50)
    retornos = rng.normal(loc=0.0015, scale=0.022, size=dias)
    precios = precio_inicial * np.cumprod(1 + retornos)
    return pd.DataFrame({"Fecha": fechas, "Precio": precios}).set_index("Fecha")


@st.cache_data(ttl=300)
def generar_rendimientos_diarios() -> pd.DataFrame:
    """Genera rendimientos diarios simulados para el heatmap y ranking."""
    seed = datetime.today().day
    rng = np.random.default_rng(seed)
    data = []
    for tk in ACTIVOS:
        var = round(rng.normal(loc=0.3, scale=3.2), 2)
        data.append({"Ticker": tk, "Variación (%)": var})
    return pd.DataFrame(data).sort_values("Variación (%)", ascending=False)


def kpi_card(label: str, value: str, delta: str = None, positive: bool = True):
    delta_html = ""
    if delta:
        color = YOSHI_GREEN if positive else YOSHI_ORANGE
        arrow = "▲" if positive else "▼"
        delta_html = f'<div class="napo-card-delta" style="color:{color};">{arrow} {delta}</div>'
    st.markdown(
        f"""
        <div class="napo-card">
            <div class="napo-card-label">{label}</div>
            <div class="napo-card-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(text: str, icon: str = ""):
    st.markdown(
        f'<div class="napo-section-title"><span class="bar"></span>{icon} {text}</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# MARQUESINA GLOBAL DE MERCADO
# =============================================================================

marquee_items = [
    ("WTI", "US$ 68,42", "+0,8%", True),
    ("Oro", "US$ 2.615", "+0,3%", True),
    ("S&P 500", "5.812", "-0,4%", False),
    ("Merval", "2.969.546", "-0,94%", False),
    ("Riesgo País", "642 pb", "-1,2%", True),
    ("Dólar CCL", "$ 1.604,58", "+0,2%", False),
    ("Dólar MEP", "$ 1.588,10", "+0,1%", False),
]
ticker_html = "".join(
    f'<span class="napo-ticker-item"><b>{name}</b>{val} '
    f'<span class="{"napo-up" if up else "napo-down"}">{chg}</span></span>'
    for name, val, chg, up in (marquee_items * 2)
)
st.markdown(
    f'<div class="napo-ticker-wrap"><div class="napo-ticker-inner">{ticker_html}</div></div>',
    unsafe_allow_html=True,
)

# =============================================================================
# HEADER
# =============================================================================

st.markdown(
    f"""
    <div class="napo-header">
        <div class="napo-brand">
            <span class="napo-brand-mark">NAPO</span>
            <span class="napo-brand-sub">Panel Táctico Financiero</span>
        </div>
        <div class="napo-pill">🧭 Menos ruido, más decisión</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="napo-demo-banner">🧪 VERSIÓN DEMO · Precios, cotizaciones y novedades simulados. '
    'No constituye asesoramiento financiero.</div>',
    unsafe_allow_html=True,
)

# =============================================================================
# KPIs CAMBIARIOS
# =============================================================================

section_title("Panel Cambiario", "💵")
col1, col2, col3, col4 = st.columns(4)
with col1:
    kpi_card("Dólar Oficial", "$ 1.515,97", "0,12%", True)
with col2:
    kpi_card("Dólar MEP", "$ 1.588,10", "0,45%", False)
with col3:
    kpi_card("Dólar CCL", "$ 1.604,58", "0,22%", False)
with col4:
    kpi_card("Riesgo País", "642 pb", "1,20%", True)

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
        st.caption("Fuente de datos: simulada (demo) — reemplazar por API real")

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

    with st.container(border=True):

        top_a, top_b = st.columns([3, 1])
        with top_a:
            st.markdown(f"### {ticker_sel} · {info['nombre']}")
            st.caption(f"Sector: {info['sector']}")
        with top_b:
            st.markdown(
                f'<div style="text-align:right; padding-top:6px;">'
                f'<a class="napo-ir-link" href="{ir_link}" target="_blank" rel="noopener noreferrer">Relaciones con Inversores ↗</a>'
                f"</div>",
                unsafe_allow_html=True,
            )

        m1, m2, m3 = st.columns(3)
        with m1:
            kpi_card("Cap. de Mercado", info["mkt_cap"])
        with m2:
            serie = generar_serie_precios(ticker_sel)
            vol_simulado = f"{int(abs(np.random.default_rng(len(ticker_sel)).normal(1_200_000, 300_000))):,}".replace(",", ".")
            kpi_card("Volumen (aprox.)", vol_simulado)
        with m3:
            kpi_card("Próximo Balance", info["prox_balance"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Evolución de precio (90 días)**")
        st.line_chart(serie, color=KLEIN_BLUE, height=320)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**🎯 Resumen táctico**")
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
        st.caption("Audio demo — reemplazar por el resumen de voz real del activo seleccionado.")


# -----------------------------------------------------------------------------
# TAB 2 — RANKING & HEATMAP
# -----------------------------------------------------------------------------
with tab2:
    section_title("Heatmap de Rendimiento Diario", "🔥")

    df_rend = generar_rendimientos_diarios()

    cols = st.columns(len(df_rend))
    for c, (_, row) in zip(cols, df_rend.iterrows()):
        var = row["Variación (%)"]
        intensidad = min(abs(var) / 4, 1)
        if var >= 0:
            bg = f"rgba(34, 197, 94, {0.12 + 0.35 * intensidad})"
            txt_color = YOSHI_GREEN
        else:
            bg = f"rgba(249, 115, 22, {0.12 + 0.35 * intensidad})"
            txt_color = YOSHI_ORANGE
        with c:
            st.markdown(
                f"""
                <div class="napo-heat-cell" style="background:{bg};">
                    <div class="napo-heat-ticker" style="color:{TEXT_PRIMARY};">{row['Ticker']}</div>
                    <div class="napo-heat-value" style="color:{txt_color};">{var:+.2f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    rank_col1, rank_col2, rank_col3 = st.columns(3)

    with rank_col1:
        section_title("Top Ganadores", "🟢")
        for _, row in df_rend.head(3).iterrows():
            st.markdown(
                f'<div class="napo-card" style="margin-bottom:8px;">'
                f'<b>{row["Ticker"]}</b> '
                f'<span class="napo-badge-up">+{row["Variación (%)"]:.2f}%</span></div>',
                unsafe_allow_html=True,
            )

    with rank_col2:
        section_title("Top Perdedores", "🔴")
        for _, row in df_rend.tail(3).iterrows():
            st.markdown(
                f'<div class="napo-card" style="margin-bottom:8px;">'
                f'<b>{row["Ticker"]}</b> '
                f'<span class="napo-badge-down">{row["Variación (%)"]:.2f}%</span></div>',
                unsafe_allow_html=True,
            )

    with rank_col3:
        section_title("Oportunidades Swing", "⚡")
        swing = df_rend.iloc[(df_rend["Variación (%)"].abs() - 1.5).abs().argsort()[:3]]
        for _, row in swing.iterrows():
            badge = "napo-badge-up" if row["Variación (%)"] >= 0 else "napo-badge-down"
            st.markdown(
                f'<div class="napo-card" style="margin-bottom:8px;">'
                f'<b>{row["Ticker"]}</b> '
                f'<span class="{badge}">{row["Variación (%)"]:+.2f}%</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Tabla completa**")
    st.dataframe(df_rend.set_index("Ticker"))

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
        Los datos mostrados son simulados a fines demostrativos. No constituye asesoramiento financiero.
    </div>
    """,
    unsafe_allow_html=True,
)
