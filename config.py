"""Configuración central de NAPO: paleta, activos, fuentes de datos y constantes."""

from datetime import timedelta, timezone

# ---------------------------------------------------------------- Paleta
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

# Nombre de variable CSS -> color (se inyecta como :root en napo/estilos.py)
PALETA_CSS = {
    "--klein": KLEIN_BLUE,
    "--klein-dark": KLEIN_BLUE_DARK,
    "--klein-light": KLEIN_BLUE_LIGHT,
    "--bg": BG_DARK,
    "--card": BG_CARD,
    "--card-alt": BG_CARD_ALT,
    "--border": BORDER_SUBTLE,
    "--text": TEXT_PRIMARY,
    "--text-2": TEXT_SECONDARY,
    "--green": YOSHI_GREEN,
    "--orange": YOSHI_ORANGE,
}

# ---------------------------------------------------------------- Fuentes de datos
DOLARAPI_URL = "https://dolarapi.com/v1/dolares"
RIESGO_PAIS_URL = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo"
HTTP_TIMEOUT = 6  # segundos máximos de espera por cada fuente
TZ_ARG = timezone(timedelta(hours=-3))  # Argentina no usa horario de verano

# ---------------------------------------------------------------- Activos
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

# Dólares del panel cambiario: (etiqueta, "casa" en DolarApi)
DOLARES_PANEL = [
    ("Dólar Oficial", "oficial"),
    ("Dólar MEP", "bolsa"),
    ("Dólar CCL", "contadoconliqui"),
    ("Dólar Blue", "blue"),
]

# Rangos del gráfico de precios (días hacia atrás)
RANGOS = {"1M": 31, "3M": 92, "6M": 183, "1A": 366}
