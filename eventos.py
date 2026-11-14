"""Medición de uso anónima: visitas, audios escuchados, activos vistos, etc.

No se guarda ningún dato personal: cada visita recibe un código al azar que dura lo que dura la sesión.
Las sesiones del operador (La Cocina) no se cuentan.
"""

import threading
import uuid
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

from . import basedatos
from .config import TZ_ARG

TABLA = "eventos"


def _es_operador() -> bool:
    if st.session_state.get("cocina_ok"):
        return True
    try:
        return bool(st.query_params.get("cocina"))
    except Exception:
        return False


def _enviar(url, encabezados, cuerpo):
    try:
        requests.request("POST", url, headers={**encabezados, "Prefer": "return=minimal"}, json=cuerpo, timeout=5)
    except Exception:
        pass  # medir nunca puede romper ni frenar la página


def registrar(tipo: str, detalle: str = ""):
    """Registra un evento anónimo en un hilo aparte (no frena la página y falla en silencio)."""
    if _es_operador():
        return
    con = basedatos.conexion(TABLA)
    if con is None:
        return
    ss = st.session_state
    if "_sesion_id" not in ss:
        ss["_sesion_id"] = uuid.uuid4().hex[:12]
    cuerpo = {"tipo": str(tipo)[:40], "detalle": str(detalle)[:120], "sesion": ss["_sesion_id"]}
    threading.Thread(target=_enviar, args=(con[0], con[1], cuerpo), daemon=True).start()


def registrar_visita():
    """Una visita por sesión."""
    if st.session_state.get("_visita_ok"):
        return
    st.session_state["_visita_ok"] = True
    registrar("visita")


def registrar_cambio(tipo: str, valor: str, clave: str):
    """Registra solo cuando el valor cambia (el valor inicial por defecto no cuenta)."""
    ss = st.session_state
    anterior = ss.get(clave)
    ss[clave] = valor
    if anterior is not None and anterior != valor:
        registrar(tipo, valor)


def registrar_una_vez(tipo: str, detalle: str, clave: str):
    """Registra el evento una sola vez por sesión."""
    if st.session_state.get(clave):
        return
    st.session_state[clave] = True
    registrar(tipo, detalle)


# ---------------------------------------------------------------- lectura para el panel del operador

@st.cache_data(ttl=120, show_spinner=False)
def leer_eventos(dias: int = 30):
    """Eventos de los últimos días (hasta 5.000). None si no se pudo leer."""
    desde = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=dias)).isoformat()
    filas = []
    for pagina in range(5):
        ok, datos = basedatos.pedir(
            TABLA, "GET",
            params={"select": "creado,tipo,detalle,sesion", "creado": f"gte.{desde}",
                    "order": "creado.desc", "limit": "1000", "offset": str(pagina * 1000)},
        )
        if not ok or not isinstance(datos, list):
            return None if pagina == 0 else filas
        filas += datos
        if len(datos) < 1000:
            break
    return filas


def _top(serie: pd.Series, n: int = 5):
    return [(str(k), int(v)) for k, v in serie.value_counts().head(n).items()]


def resumir(filas) -> dict:
    """Convierte los eventos en los números del panel de uso."""
    hoy = datetime.now(TZ_ARG).date()
    dias = [hoy - timedelta(days=i) for i in range(13, -1, -1)]
    vacio = {"eventos": 0, "visitas_hoy": 0, "visitas_7d": 0, "visitas_30d": 0, "audios": 0, "audios_top": [],
             "tickers_top": [], "shorts": 0, "usaron_cartera": 0,
             "por_dia": pd.Series([0] * 14, index=[d.strftime("%d/%m") for d in dias])}
    if not filas:
        return vacio
    df = pd.DataFrame(filas)
    df["creado"] = pd.to_datetime(df["creado"], utc=True, errors="coerce")
    df = df.dropna(subset=["creado"])
    if df.empty:
        return vacio
    df["dia"] = df["creado"].dt.tz_convert(TZ_ARG).dt.date
    visitas = df[df["tipo"] == "visita"]
    por_dia = visitas.groupby("dia")["sesion"].nunique().reindex(dias, fill_value=0)
    por_dia.index = [d.strftime("%d/%m") for d in dias]
    return {
        "eventos": len(df),
        "visitas_hoy": int(visitas[visitas["dia"] == hoy]["sesion"].nunique()),
        "visitas_7d": int(visitas[visitas["dia"] >= hoy - timedelta(days=6)]["sesion"].nunique()),
        "visitas_30d": int(visitas["sesion"].nunique()),
        "audios": int((df["tipo"] == "audio").sum()),
        "audios_top": _top(df[df["tipo"] == "audio"]["detalle"]),
        "tickers_top": _top(df[df["tipo"] == "ticker"]["detalle"]),
        "shorts": int((df["tipo"] == "short").sum()),
        "usaron_cartera": int(df[df["tipo"] == "cartera"]["sesion"].nunique()),
        "por_dia": por_dia,
    }
