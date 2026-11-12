"""Reportes tácticos de NAPO.

- Se guardan en Supabase (tabla `reportes`) a través de su API REST.
- `parsear_reporte` convierte la respuesta del prompt maestro (el formato de 5 puntos) en campos.
- `generar_audio` crea la voz del reporte (edge-tts con voz argentina; gTTS de respaldo).
"""

import asyncio
import base64
import concurrent.futures
import io
import re

import requests
import streamlit as st

from .secretos import secreto

TABLA = "reportes"
VOZ_ARGENTINA = "es-AR-ElenaNeural"
LIMITE_AUDIO_BYTES = 1_800_000  # por seguridad: un reporte de ~2 minutos pesa bastante menos

# valor guardado -> (emoji, etiqueta)
IMPACTOS = {
    "alcista": ("🟢", "Alcista"),
    "bajista": ("🔴", "Bajista"),
    "neutral": ("⚪", "Neutral"),
}

COLUMNAS_LISTA = "id,creado,ticker,titular,contexto,efecto,impacto,justificacion,fuente,tiene_audio"


# =============================================================================
# BASE DE DATOS (Supabase, API REST)
# =============================================================================

def _conexion():
    """(url de la tabla, encabezados) o None si faltan los Secrets."""
    base = secreto("SUPABASE_URL").rstrip("/")
    clave = secreto("SUPABASE_KEY")
    if not base or not clave:
        return None
    # Las claves nuevas (sb_publishable_ / sb_secret_) van SOLO en `apikey`.
    # Las claves viejas (JWT, empiezan con "eyJ") van también como Bearer.
    encabezados = {"apikey": clave, "Content-Type": "application/json"}
    if clave.startswith("eyJ"):
        encabezados["Authorization"] = f"Bearer {clave}"
    return f"{base}/rest/v1/{TABLA}", encabezados


def reportes_configurados() -> bool:
    return _conexion() is not None


def _pedir(metodo, params=None, cuerpo=None, prefer=None, timeout=15):
    """Hace un pedido a la tabla. Devuelve (ok, datos_o_mensaje_de_error)."""
    conexion = _conexion()
    if conexion is None:
        return False, "Faltan SUPABASE_URL y SUPABASE_KEY en los Secrets."
    url, encabezados = conexion
    if prefer:
        encabezados = {**encabezados, "Prefer": prefer}
    try:
        resp = requests.request(metodo, url, headers=encabezados, params=params, json=cuerpo, timeout=timeout)
    except Exception as error:
        return False, f"No se pudo conectar con la base de datos ({type(error).__name__})."
    if resp.status_code >= 400:
        return False, f"La base de datos respondió {resp.status_code}: {resp.text[:200]}"
    try:
        return True, (resp.json() if resp.content else None)
    except ValueError:
        return True, None


@st.cache_data(ttl=60, show_spinner=False)
def listar_reportes(limite: int = 30):
    """Últimos reportes (sin el audio). None si no se pudo leer; [] si todavía no hay."""
    ok, datos = _pedir(
        "GET",
        params={"select": COLUMNAS_LISTA, "order": "creado.desc", "limit": str(int(limite))},
    )
    return datos if ok and isinstance(datos, list) else None


@st.cache_data(ttl=3600, show_spinner=False)
def obtener_audio(reporte_id: int):
    """Bytes del MP3 de un reporte, o None."""
    ok, datos = _pedir(
        "GET", params={"select": "audio_b64", "id": f"eq.{int(reporte_id)}", "limit": "1"}, timeout=20
    )
    if not ok or not datos:
        return None
    contenido = datos[0].get("audio_b64")
    if not contenido:
        return None
    try:
        return base64.b64decode(contenido)
    except Exception:
        return None


def normalizar_ticker(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9.\-]", "", str(texto or "")).upper()[:12]


def validar_reporte(rep: dict):
    """Devuelve un mensaje de error, o None si el reporte está completo."""
    if not normalizar_ticker(rep.get("ticker", "")):
        return "Falta el ticker."
    if not str(rep.get("titular", "")).strip():
        return "Falta el titular."
    if rep.get("impacto") not in IMPACTOS:
        return "Elegí el impacto (alcista, bajista o neutral)."
    return None


def publicar_reporte(rep: dict, audio: bytes = None):
    """Guarda el reporte (con su audio si hay). Devuelve (ok, mensaje)."""
    cuerpo = {
        "ticker": normalizar_ticker(rep["ticker"]),
        "titular": rep["titular"].strip(),
        "contexto": rep.get("contexto", "").strip(),
        "efecto": rep.get("efecto", "").strip(),
        "impacto": rep["impacto"],
        "justificacion": rep.get("justificacion", "").strip(),
        "fuente": rep.get("fuente", "").strip(),
        "tiene_audio": bool(audio),
        "audio_b64": base64.b64encode(audio).decode("ascii") if audio else None,
    }
    ok, resultado = _pedir("POST", cuerpo=cuerpo, prefer="return=minimal", timeout=40)
    if ok:
        listar_reportes.clear()
        return True, "Reporte publicado."
    return False, str(resultado)


def eliminar_reporte(reporte_id: int):
    ok, resultado = _pedir("DELETE", params={"id": f"eq.{int(reporte_id)}"}, prefer="return=minimal")
    if ok:
        listar_reportes.clear()
        obtener_audio.clear()
        return True, "Reporte eliminado."
    return False, str(resultado)


# =============================================================================
# LECTURA DEL FORMATO DEL PROMPT MAESTRO
# =============================================================================

_ENCABEZADOS = (
    ("titular", r"Titular(?:\s+al\s+hueso)?"),
    ("contexto", r"(?:El\s+porqu[eé]\s*\(Contexto\)|Contexto(?:\s+clave)?)"),
    ("efecto", r"Efecto\s+directo(?:\s+en\s+la\s+acci[oó]n)?"),
    ("impacto", r"Impacto\s+potencial"),
    ("fuente", r"Fuente(?:\s+oficial)?"),
)
_PREFIJO_LINEA = r"^[ \t]*(?:[*\-•][ \t]*)?(?:\d+[.)][ \t]*)?"


def _lineas(bloque: str):
    """Quita viñetas y símbolos sobrantes; devuelve las líneas con contenido."""
    salida = []
    for linea in bloque.splitlines():
        linea = re.sub(r"^[ \t]*[*\-•–][ \t]+", "", linea).strip().strip("*_ ")
        if linea:
            salida.append(linea)
    return salida


def parsear_reporte(texto: str) -> dict:
    """Convierte la respuesta del prompt maestro en campos. Lo que no encuentra queda vacío."""
    vacio = {"ticker": "", "titular": "", "contexto": "", "efecto": "", "impacto": "",
             "justificacion": "", "fuente": ""}
    if not texto or not texto.strip():
        return vacio
    t = texto.replace("\r", "").replace("**", "").replace("__", "")

    hallados = []
    for clave, patron in _ENCABEZADOS:
        m = re.search(rf"(?im){_PREFIJO_LINEA}(?:{patron})[ \t]*:", t)
        if m:
            hallados.append((m.start(), m.end(), clave))
    hallados.sort()
    bloques = {}
    for i, (_, fin, clave) in enumerate(hallados):
        siguiente = hallados[i + 1][0] if i + 1 < len(hallados) else len(t)
        bloques[clave] = t[fin:siguiente]

    datos = dict(vacio)
    m = re.search(r"(?i)Ticker\s*:\s*\$?([A-Za-z0-9.\-]{1,12})", t) or re.search(r"\$([A-Za-z]{1,6})\b", t)
    if m:
        datos["ticker"] = normalizar_ticker(m.group(1))

    datos["titular"] = " ".join(_lineas(bloques.get("titular", "")))
    datos["contexto"] = "\n".join(_lineas(bloques.get("contexto", "")))
    datos["efecto"] = "\n".join(_lineas(bloques.get("efecto", "")))

    bloque_impacto = bloques.get("impacto", "")
    if bloque_impacto:
        marcas = {"alcista": ("🟢", "alcista"), "bajista": ("🔴", "bajista"), "neutral": ("⚪", "neutral")}
        minimo = None
        minuscula = bloque_impacto.lower()
        for clave, opciones in marcas.items():
            for marca in opciones:
                pos = bloque_impacto.find(marca) if marca in ("🟢", "🔴", "⚪") else minuscula.find(marca)
                if pos != -1 and (minimo is None or pos < minimo[0]):
                    minimo = (pos, clave)
        if minimo:
            datos["impacto"] = minimo[1]
        justificacion = " ".join(_lineas(bloque_impacto))
        datos["justificacion"] = re.sub(r"^\W*(?:alcista|bajista|neutral)?\W*", "", justificacion, flags=re.I).strip()

    fuente = " ".join(_lineas(bloques.get("fuente", "")))
    fuente = re.split(r"\s*[—–-]?\s*\*?\s*aclaraci[oó]n", fuente, flags=re.I)[0]
    datos["fuente"] = fuente.strip(" —–-*")[:400]
    return datos


# =============================================================================
# AUDIO (voz)
# =============================================================================

def limpiar_para_voz(texto: str) -> str:
    """Prepara el texto para que la voz lo lea bien (sin links ni símbolos, con siglas y números legibles)."""
    t = re.sub(r"https?://\S+", "", texto)
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", t)
    t = re.sub(r"\$(?=[A-Za-z])", "", t)  # $PAMP -> PAMP
    trimestres = {"1": "primer", "2": "segundo", "3": "tercer", "4": "cuarto"}
    t = re.sub(r"\b([1-4])T(\d{2})\b", lambda m: f"{trimestres[m.group(1)]} trimestre de 20{m.group(2)}", t)
    for origen, destino in (
        ("S&P", "S and P"), ("US$", "dólares "), ("u$s", "dólares "),
        ("MMm³/d", " millones de metros cúbicos por día"), ("bbl/d", " barriles por día"),
        ("P/E", "P E"), ("i.a.", "interanual"), ("~", "aproximadamente "),
        ("%", " por ciento"), ("&", " y "),
    ):
        t = t.replace(origen, destino)
    t = re.sub(r"(?<=\d)x\b", " veces", t)       # 16,4x -> 16,4 veces
    t = re.sub(r"(?<=\d)M\b", " millones", t)    # 2.700M -> 2.700 millones
    t = re.sub(r"\bpb\b", "puntos básicos", t)
    return re.sub(r"\s+", " ", t).strip()


def _oraciones(texto: str) -> str:
    """Une líneas asegurando punto final en cada una (así la voz hace pausas)."""
    partes = []
    for linea in [l.strip() for l in texto.splitlines() if l.strip()]:
        partes.append(linea if linea[-1] in ".!?:" else linea + ".")
    return " ".join(partes)


def guion_audio(rep: dict) -> str:
    """Texto que va a leer la voz."""
    etiqueta = IMPACTOS.get(rep.get("impacto"), ("", ""))[1]
    partes = [f"Reporte táctico de {normalizar_ticker(rep.get('ticker', ''))}.", _oraciones(rep.get("titular", ""))]
    if rep.get("contexto"):
        partes.append("Contexto. " + _oraciones(rep["contexto"]))
    if rep.get("efecto"):
        partes.append("Efecto en la acción. " + _oraciones(rep["efecto"]))
    impacto = f"Impacto potencial: {etiqueta}."
    if rep.get("justificacion"):
        justificacion = _oraciones(rep["justificacion"])
        impacto += " " + justificacion[:1].upper() + justificacion[1:]
    partes.append(impacto)
    partes.append("Información con fines informativos. No es una recomendación de inversión.")
    return limpiar_para_voz(" ".join(p for p in partes if p))


async def _sintetizar_edge(texto: str) -> bytes:
    import edge_tts

    comunicar = edge_tts.Communicate(texto, VOZ_ARGENTINA)
    audio = bytearray()
    async for pedazo in comunicar.stream():
        if pedazo["type"] == "audio":
            audio.extend(pedazo["data"])
    return bytes(audio)


def _edge_en_hilo(texto: str) -> bytes:
    """Corre edge-tts en un hilo aparte (así no choca con el bucle de eventos de Streamlit)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ejecutor:
        return ejecutor.submit(lambda: asyncio.run(_sintetizar_edge(texto))).result(timeout=90)


def generar_audio(texto: str):
    """Devuelve (mp3_en_bytes o None, mensaje de error o None). Prueba edge-tts y luego gTTS."""
    errores = []
    try:
        datos = _edge_en_hilo(texto)
        if datos:
            return datos, None
        errores.append("edge-tts devolvió audio vacío")
    except Exception as error:
        errores.append(f"edge-tts ({type(error).__name__})")
    try:
        from gtts import gTTS

        buffer = io.BytesIO()
        gTTS(texto, lang="es", tld="com.mx").write_to_fp(buffer)
        datos = buffer.getvalue()
        if datos:
            return datos, None
        errores.append("gTTS devolvió audio vacío")
    except Exception as error:
        errores.append(f"gTTS ({type(error).__name__})")
    return None, "No se pudo generar la voz: " + " · ".join(errores)
