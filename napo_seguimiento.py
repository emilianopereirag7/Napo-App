"""Lista personal de activos para seguimiento informativo de NAPO.

No representa una cartera de inversión ni registra cantidades, costos o patrimonio.
La lista vive en la sesión del usuario y puede exportarse/importarse como CSV.
"""

import io
import math
import unicodedata

import pandas as pd

COLUMNA = "ticker"
MAX_ACTIVOS = 200
_ALIAS_TICKER = ("ticker", "simbolo", "activo", "papel", "especie", "symbol")


def lista_vacia() -> pd.DataFrame:
    return pd.DataFrame({COLUMNA: pd.Series(dtype="object")})


def limpiar_lista(df, validos):
    """Valida y deduplica una lista de tickers. Devuelve (DataFrame, avisos).

    Acepta también DataFrames antiguos de Mi cartera: cantidad y precio_compra
    se ignoran deliberadamente porque NAPO pasa a ser una herramienta de seguimiento.
    """
    avisos = []
    if df is None or len(df) == 0:
        return lista_vacia(), avisos

    if isinstance(df, pd.Series):
        d = df.to_frame(name=COLUMNA)
    elif isinstance(df, (list, tuple, set)):
        d = pd.DataFrame({COLUMNA: list(df)})
    else:
        d = df.copy()

    if COLUMNA not in d.columns:
        encontrada = None
        for col in d.columns:
            normalizada = (
                unicodedata.normalize("NFKD", str(col))
                .encode("ascii", "ignore").decode().lower().strip().replace(" ", "_")
            )
            if normalizada in _ALIAS_TICKER:
                encontrada = col
                break
        if encontrada is None:
            return lista_vacia(), ["No encontré una columna de ticker o símbolo."]
        d = d.rename(columns={encontrada: COLUMNA})

    tickers = (
        d[COLUMNA].fillna("").astype(str).str.strip().str.upper()
        .str.replace("$", "", regex=False)
    )
    tickers = tickers[~tickers.isin(["", "NAN", "NONE", "NULL"])]

    validos_set = set(validos)
    desconocidos = sorted(set(tickers) - validos_set)
    if desconocidos:
        avisos.append("Activos no reconocidos (se ignoraron): " + ", ".join(desconocidos)[:200])

    resultado = []
    vistos = set()
    for ticker in tickers:
        if ticker not in validos_set or ticker in vistos:
            continue
        vistos.add(ticker)
        resultado.append(ticker)
        if len(resultado) >= MAX_ACTIVOS:
            if len(vistos) < len(set(tickers)):
                avisos.append(f"La lista está limitada a {MAX_ACTIVOS} activos.")
            break

    return pd.DataFrame({COLUMNA: resultado}), avisos


def desde_csv(contenido, validos):
    """Importa una lista nueva o un CSV legado de Mi cartera.

    Si el CSV anterior contiene ticker, cantidad y precio_compra, solo se importa
    el ticker: las cantidades y los precios de compra ya no forman parte del modelo.
    """
    if isinstance(contenido, (bytes, bytearray)) and len(contenido) > 500_000:
        return lista_vacia(), ["El archivo es demasiado grande para una lista de activos."]

    texto = (
        contenido.decode("utf-8-sig", errors="replace")
        if isinstance(contenido, (bytes, bytearray)) else str(contenido)
    )
    lineas = [linea for linea in texto.splitlines() if linea.strip()]
    if not lineas:
        return lista_vacia(), ["El archivo está vacío."]

    primera = lineas[0]
    separador = ";" if primera.count(";") >= primera.count(",") and ";" in primera else ","
    try:
        crudo = pd.read_csv(io.StringIO("\n".join(lineas)), sep=separador, dtype=str, keep_default_na=False)
    except Exception:
        return lista_vacia(), ["No pude leer el archivo. Usá un CSV con una columna ticker o símbolo."]

    renombrar = {}
    for col in crudo.columns:
        normalizada = (
            unicodedata.normalize("NFKD", str(col))
            .encode("ascii", "ignore").decode().lower().strip().replace(" ", "_")
        )
        if normalizada in _ALIAS_TICKER:
            renombrar[col] = COLUMNA
            break
    crudo = crudo.rename(columns=renombrar)
    if COLUMNA not in crudo.columns:
        return lista_vacia(), ["Al archivo le falta una columna llamada ticker, símbolo o activo."]

    tabla, avisos = limpiar_lista(crudo[[COLUMNA]], validos)
    if any(col in crudo.columns for col in ("cantidad", "precio_compra", "precio", "costo")):
        avisos.insert(0, "Se importaron los tickers del CSV anterior. Cantidades y costos no se utilizan en Mis activos.")
    return tabla, avisos


def a_csv(df: pd.DataFrame) -> str:
    """Exporta únicamente los tickers seguidos."""
    salida, _ = limpiar_lista(df, set(df[COLUMNA]) if df is not None and COLUMNA in df else set())
    return salida.to_csv(index=False, sep=";", encoding="utf-8")


def _numero(valor):
    try:
        numero = float(valor)
        return numero if math.isfinite(numero) else None
    except (TypeError, ValueError):
        return None


def _variacion_sesiones(close: pd.Series, sesiones_atras: int):
    """Variación contra el cierre de hace N ruedas, respetando feriados y fines de semana."""
    if close is None or len(close) <= sesiones_atras:
        return None
    precio_base = _numero(close.iloc[-(sesiones_atras + 1)])
    ultimo = _numero(close.iloc[-1])
    if not precio_base or ultimo is None:
        return None
    return (ultimo / precio_base - 1) * 100


def _dolar_ccl_venta(dolares):
    cotizacion = (dolares or {}).get("contadoconliqui") or {}
    valor = _numero(cotizacion.get("venta"))
    return valor if valor and valor > 0 else None


def _serie_cierre(precios, simbolo):
    """Extrae una serie de cierres sin depender de Streamlit ni de otros módulos."""
    if precios is None or not simbolo:
        return pd.Series(dtype=float)
    try:
        if isinstance(precios.columns, pd.MultiIndex):
            cierre = precios[simbolo]["Close"].copy()
        else:
            cierre = precios["Close"].copy()
        cierre = cierre.dropna()
        if getattr(cierre.index, "tz", None) is not None:
            cierre.index = cierre.index.tz_localize(None)
        return cierre
    except (KeyError, TypeError, AttributeError):
        return pd.Series(dtype=float)


def resumir_activos(tickers, precios, activos: dict, dolares=None):
    """Devuelve cotización local, equivalente USD CCL y variaciones 1D/1S/1M.

    Los símbolos de ACTIVOS corresponden a papeles locales (.BA), por lo que
    el precio de Yahoo se interpreta como ARS. USD CCL es una conversión
    indicativa: precio ARS / dólar CCL vendedor de DolarApi.
    """
    ccl = _dolar_ccl_venta(dolares)
    filas = []
    for ticker in tickers or []:
        info = activos.get(ticker, {})
        simbolo = info.get("yahoo")
        close = _serie_cierre(precios, simbolo)

        if close.empty:
            filas.append({
                "ticker": ticker, "nombre": info.get("nombre", ticker), "tipo": info.get("tipo", ""),
                "precio_ars": None, "precio_usd_ccl": None, "var_dia": None,
                "var_semana": None, "var_mes": None, "fecha": None,
            })
            continue

        ultimo = _numero(close.iloc[-1])
        previo = _numero(close.iloc[-2]) if len(close) >= 2 else None
        var_dia = (ultimo / previo - 1) * 100 if ultimo is not None and previo else None
        filas.append({
            "ticker": ticker,
            "nombre": info.get("nombre", ticker),
            "tipo": info.get("tipo", ""),
            "precio_ars": ultimo,
            "precio_usd_ccl": ultimo / ccl if ultimo is not None and ccl else None,
            "var_dia": var_dia,
            "var_semana": _variacion_sesiones(close, 5),
            # La descarga general contiene aproximadamente un mes de ruedas.
            # Exigimos al menos 15 observaciones para no presentar pocos días como un mes.
            "var_mes": (ultimo / _numero(close.iloc[0]) - 1) * 100
                if len(close) >= 15 and _numero(close.iloc[0]) else None,
            "fecha": close.index[-1],
        })
    return filas
