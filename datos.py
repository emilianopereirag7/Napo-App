"""Obtención de datos de mercado: DolarApi, ArgentinaDatos y Yahoo Finance."""

import time

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from .config import DOLARAPI_URL, HTTP_TIMEOUT, RANGOS, RIESGO_PAIS_URL, SIMBOLOS_TODOS


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


def recortar_rango(df: pd.DataFrame, rango: str) -> pd.DataFrame:
    corte = df.index.max() - pd.Timedelta(days=RANGOS[rango])
    return df[df.index >= corte]
