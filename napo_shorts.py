"""Noticias en Shorts de YouTube: las carga el operador y se muestran las 5 más recientes."""

import re

import requests
import streamlit as st

import napo_basedatos as basedatos
from napo_config import CANALES_CONFIABLES, HTTP_TIMEOUT

TABLA = "noticias_shorts"
COLUMNAS = "id,creado,video_id,titulo,canal,nota"

_ID_SUELTO = re.compile(r"^[A-Za-z0-9_-]{11}$")
_ID_EN_URL = re.compile(r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:shorts/|embed/|live/|v/)|[?&]v=)([A-Za-z0-9_-]{11})")


def extraer_video_id(texto: str):
    """Saca el ID de 11 caracteres de cualquier link de YouTube (shorts, watch, youtu.be, embed)."""
    t = (texto or "").strip()
    if _ID_SUELTO.match(t):
        return t
    m = _ID_EN_URL.search(t)
    return m.group(1) if m else None


def url_video(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def url_short(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


def url_miniatura(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def datos_oembed(video_id: str):
    """(título, canal, error). Lee los datos públicos del video (no hace falta clave de YouTube)."""
    try:
        resp = requests.get("https://www.youtube.com/oembed",
                            params={"url": url_video(video_id), "format": "json"}, timeout=HTTP_TIMEOUT)
        if resp.status_code in (400, 401, 403, 404):
            return "", "", "El video no existe, es privado o no permite verse desde otros sitios."
        resp.raise_for_status()
        datos = resp.json()
        return str(datos.get("title", "")), str(datos.get("author_name", "")), None
    except Exception:
        return "", "", "No pude leer los datos del video: completá título y canal a mano."


def canal_confiable(canal: str) -> bool:
    """True si el canal figura (por nombre) en la lista de fuentes de confianza."""
    return any(re.search(rf"\b{re.escape(c)}\b", canal or "", re.I) for c in CANALES_CONFIABLES)


@st.cache_data(ttl=120, show_spinner=False)
def listar_shorts(limite: int = 5):
    """Los últimos shorts cargados. None si no se pudo leer; [] si todavía no hay."""
    ok, datos = basedatos.pedir(TABLA, "GET", params={"select": COLUMNAS, "order": "creado.desc",
                                                      "limit": str(int(limite))})
    return datos if ok and isinstance(datos, list) else None


def agregar_short(video_id, titulo: str, canal: str, nota: str = ""):
    if not video_id:
        return False, "Falta un link de YouTube válido."
    if not (titulo or "").strip():
        return False, "Falta el título."
    cuerpo = {"video_id": video_id, "titulo": titulo.strip()[:200], "canal": (canal or "").strip()[:100],
              "nota": (nota or "").strip()[:300]}
    ok, resultado = basedatos.pedir(TABLA, "POST", cuerpo=cuerpo, prefer="return=minimal")
    if ok:
        listar_shorts.clear()
        return True, "Short agregado a Noticias."
    if basedatos.es_duplicado(resultado):
        return False, "Ese video ya está cargado."
    return False, str(resultado)


def eliminar_short(short_id: int):
    ok, resultado = basedatos.pedir(TABLA, "DELETE", params={"id": f"eq.{int(short_id)}"}, prefer="return=minimal")
    if ok:
        listar_shorts.clear()
        return True, "Short eliminado."
    return False, str(resultado)
