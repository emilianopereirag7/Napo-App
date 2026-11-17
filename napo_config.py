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

# Nombre de variable CSS -> color (se inyecta como :root en napo_estilos.py)
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
# (ticker, nombre, sector, tipo, símbolo en Yahoo Finance). Los .BA son los papeles que cotizan en ByMA.
# Los símbolos de Yahoo están cargados de memoria: si alguno no trae datos, aparece en
# La Cocina > Sistema > "Tickers sin datos" para corregirlo o sacarlo.
_LISTA_ACTIVOS = [
    # ---- Acciones argentinas
    ("ALUA", "Aluar", "Industria", "Acción", "ALUA.BA"),
    ("AUSO", "Autopistas del Sol", "Infraestructura", "Acción", "AUSO.BA"),
    ("BBAR", "BBVA Argentina", "Bancos", "Acción", "BBAR.BA"),
    ("BHIP", "Banco Hipotecario", "Bancos", "Acción", "BHIP.BA"),
    ("BMA", "Banco Macro", "Bancos", "Acción", "BMA.BA"),
    ("BYMA", "Bolsas y Mercados Argentinos", "Finanzas", "Acción", "BYMA.BA"),
    ("CAPX", "Capex", "Energía", "Acción", "CAPX.BA"),
    ("CEPU", "Central Puerto", "Energía", "Acción", "CEPU.BA"),
    ("CGPA2", "Camuzzi Gas Pampeana", "Energía", "Acción", "CGPA2.BA"),
    ("COME", "Sociedad Comercial del Plata", "Holding", "Acción", "COME.BA"),
    ("CRES", "Cresud", "Agro", "Acción", "CRES.BA"),
    ("CVH", "Cablevisión Holding", "Telecomunicaciones", "Acción", "CVH.BA"),
    ("DGCU2", "Distribuidora de Gas Cuyana", "Energía", "Acción", "DGCU2.BA"),
    ("EDN", "Edenor", "Energía", "Acción", "EDN.BA"),
    ("GBAN", "Naturgy Ban", "Energía", "Acción", "GBAN.BA"),
    ("GCLA", "Grupo Clarín", "Medios", "Acción", "GCLA.BA"),
    ("GGAL", "Grupo Financiero Galicia", "Bancos", "Acción", "GGAL.BA"),
    ("HARG", "Holcim Argentina", "Materiales", "Acción", "HARG.BA"),
    ("IRSA", "IRSA", "Inmobiliario", "Acción", "IRSA.BA"),
    ("LEDE", "Ledesma", "Agro", "Acción", "LEDE.BA"),
    ("LOMA", "Loma Negra", "Materiales", "Acción", "LOMA.BA"),
    ("METR", "Metrogas", "Energía", "Acción", "METR.BA"),
    ("MIRG", "Mirgor", "Industria", "Acción", "MIRG.BA"),
    ("MOLI", "Molinos Río de la Plata", "Consumo", "Acción", "MOLI.BA"),
    ("MORI", "Morixe Hermanos", "Consumo", "Acción", "MORI.BA"),
    ("OEST", "Grupo Concesionario del Oeste", "Infraestructura", "Acción", "OEST.BA"),
    ("PAMP", "Pampa Energía", "Energía", "Acción", "PAMP.BA"),
    ("SAMI", "San Miguel", "Agro", "Acción", "SAMI.BA"),
    ("SUPV", "Grupo Supervielle", "Bancos", "Acción", "SUPV.BA"),
    ("TECO2", "Telecom Argentina", "Telecomunicaciones", "Acción", "TECO2.BA"),
    ("TGNO4", "Transportadora de Gas del Norte", "Energía", "Acción", "TGNO4.BA"),
    ("TGSU2", "Transportadora de Gas del Sur", "Energía", "Acción", "TGSU2.BA"),
    ("TRAN", "Transener", "Energía", "Acción", "TRAN.BA"),
    ("TXAR", "Ternium Argentina", "Siderurgia", "Acción", "TXAR.BA"),
    ("VALO", "Grupo Financiero Valores", "Finanzas", "Acción", "VALO.BA"),
    ("YPF", "YPF", "Energía", "Acción", "YPFD.BA"),
    # ---- CEDEARs
    ("AAPL", "Apple", "Tecnología", "CEDEAR", "AAPL.BA"),
    ("AMD", "AMD", "Tecnología", "CEDEAR", "AMD.BA"),
    ("AMZN", "Amazon", "Consumo", "CEDEAR", "AMZN.BA"),
    ("BABA", "Alibaba", "Tecnología", "CEDEAR", "BABA.BA"),
    ("CVX", "Chevron", "Energía", "CEDEAR", "CVX.BA"),
    ("DIS", "Disney", "Medios", "CEDEAR", "DIS.BA"),
    ("GLOB", "Globant", "Tecnología", "CEDEAR", "GLOB.BA"),
    ("GOOGL", "Alphabet (Google)", "Tecnología", "CEDEAR", "GOOGL.BA"),
    ("JNJ", "Johnson & Johnson", "Salud", "CEDEAR", "JNJ.BA"),
    ("JPM", "JPMorgan Chase", "Bancos", "CEDEAR", "JPM.BA"),
    ("KO", "Coca-Cola", "Consumo", "CEDEAR", "KO.BA"),
    ("MA", "Mastercard", "Finanzas", "CEDEAR", "MA.BA"),
    ("MELI", "MercadoLibre", "Tecnología", "CEDEAR", "MELI.BA"),
    ("META", "Meta Platforms", "Tecnología", "CEDEAR", "META.BA"),
    ("MSFT", "Microsoft", "Tecnología", "CEDEAR", "MSFT.BA"),
    ("NFLX", "Netflix", "Medios", "CEDEAR", "NFLX.BA"),
    ("NVDA", "Nvidia", "Tecnología", "CEDEAR", "NVDA.BA"),
    ("ORCL", "Oracle", "Tecnología", "CEDEAR", "ORCL.BA"),
    ("PBR", "Petrobras", "Energía", "CEDEAR", "PBR.BA"),
    ("PEP", "PepsiCo", "Consumo", "CEDEAR", "PEP.BA"),
    ("PFE", "Pfizer", "Salud", "CEDEAR", "PFE.BA"),
    ("QQQ", "ETF Nasdaq 100 (QQQ)", "ETF", "CEDEAR", "QQQ.BA"),
    ("SNDK", "SanDisk", "Tecnología", "CEDEAR", "SNDK.BA"),
    ("SPY", "ETF S&P 500 (SPY)", "ETF", "CEDEAR", "SPY.BA"),
    ("TSLA", "Tesla", "Autos", "CEDEAR", "TSLA.BA"),
    ("V", "Visa", "Finanzas", "CEDEAR", "V.BA"),
    ("VALE", "Vale", "Minería", "CEDEAR", "VALE.BA"),
    ("VIST", "Vista Energy", "Energía", "CEDEAR", "VIST.BA"),
    ("WMT", "Walmart", "Consumo", "CEDEAR", "WMT.BA"),
    ("XOM", "ExxonMobil", "Energía", "CEDEAR", "XOM.BA"),
    # ---- CEDEARs: sumados en la v9 (los más operados según BYMA y los más conocidos)
    ("NU", "Nu Holdings (Nubank)", "Finanzas", "CEDEAR", "NU.BA"),
    ("INTC", "Intel", "Tecnología", "CEDEAR", "INTC.BA"),
    ("QCOM", "Qualcomm", "Tecnología", "CEDEAR", "QCOM.BA"),
    ("AVGO", "Broadcom", "Tecnología", "CEDEAR", "AVGO.BA"),
    ("TSM", "TSMC", "Tecnología", "CEDEAR", "TSM.BA"),
    ("MU", "Micron", "Tecnología", "CEDEAR", "MU.BA"),
    ("PLTR", "Palantir", "Tecnología", "CEDEAR", "PLTR.BA"),
    ("UBER", "Uber", "Tecnología", "CEDEAR", "UBER.BA"),
    ("SHOP", "Shopify", "Tecnología", "CEDEAR", "SHOP.BA"),
    ("CRM", "Salesforce", "Tecnología", "CEDEAR", "CRM.BA"),
    ("ADBE", "Adobe", "Tecnología", "CEDEAR", "ADBE.BA"),
    ("IBM", "IBM", "Tecnología", "CEDEAR", "IBM.BA"),
    ("PYPL", "PayPal", "Finanzas", "CEDEAR", "PYPL.BA"),
    ("COIN", "Coinbase", "Finanzas", "CEDEAR", "COIN.BA"),
    ("MCD", "McDonald's", "Consumo", "CEDEAR", "MCD.BA"),
    ("NKE", "Nike", "Consumo", "CEDEAR", "NKE.BA"),
    ("SBUX", "Starbucks", "Consumo", "CEDEAR", "SBUX.BA"),
    ("COST", "Costco", "Consumo", "CEDEAR", "COST.BA"),
    ("PG", "Procter & Gamble", "Consumo", "CEDEAR", "PG.BA"),
    ("HD", "Home Depot", "Consumo", "CEDEAR", "HD.BA"),
    ("BAC", "Bank of America", "Bancos", "CEDEAR", "BAC.BA"),
    ("GS", "Goldman Sachs", "Bancos", "CEDEAR", "GS.BA"),
    ("MRK", "Merck", "Salud", "CEDEAR", "MRK.BA"),
    ("LLY", "Eli Lilly", "Salud", "CEDEAR", "LLY.BA"),
    ("ABBV", "AbbVie", "Salud", "CEDEAR", "ABBV.BA"),
    ("BA", "Boeing", "Industria", "CEDEAR", "BA.BA"),
    ("GE", "General Electric", "Industria", "CEDEAR", "GE.BA"),
    ("CAT", "Caterpillar", "Industria", "CEDEAR", "CAT.BA"),
    ("FCX", "Freeport-McMoRan", "Minería", "CEDEAR", "FCX.BA"),
    ("NEM", "Newmont", "Minería", "CEDEAR", "NEM.BA"),
    ("GLD", "ETF Oro (GLD)", "ETF", "CEDEAR", "GLD.BA"),
    ("EWZ", "ETF Brasil (EWZ)", "ETF", "CEDEAR", "EWZ.BA"),
    ("EEM", "ETF Mercados Emergentes (EEM)", "ETF", "CEDEAR", "EEM.BA"),
]
ACTIVOS = {t: {"nombre": n, "sector": s, "tipo": tp, "yahoo": y} for t, n, s, tp, y in _LISTA_ACTIVOS}

# Canales de YouTube que consideramos fuentes confiables para las noticias en Shorts.
# Si cargás un Short de un canal que no está acá, La Cocina te avisa (no lo bloquea).
CANALES_CONFIABLES = (
    "Bloomberg Línea", "Bloomberg", "Reuters", "Ámbito", "El Cronista", "Infobae", "iProfesional",
    "Clarín", "La Nación", "CNBC", "Financial Times", "BBC News Mundo", "TN",
)

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
