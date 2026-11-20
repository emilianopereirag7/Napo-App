"""Lectura del modelo editorial v9 de Actualidad desde Supabase.

Solo expone acontecimientos publicables y aprobados. No escribe ni modifica datos.
La carga está cacheada brevemente para evitar consultar Supabase en cada rerun.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import requests

import streamlit as st

from napo_secretos import secreto

TABLAS = {
    "eventos": "actualidad_eventos",
    "actualizaciones": "actualidad_actualizaciones",
    "fuentes": "actualidad_fuentes",
    "evento_fuentes": "actualidad_evento_fuentes",
    "actualizacion_fuentes": "actualidad_actualizacion_fuentes",
    "activos": "actualidad_evento_activos",
}

TIPOS_FUENTE = {
    "primaria": "Primaria",
    "periodistica": "Periodística",
    "mercado": "Mercado",
}


def _rol_jwt(clave: str) -> str | None:
    """Lee el claim role de un JWT legacy sin mostrar ni registrar el token.

    Esto solo identifica el tipo de credencial configurada; Supabase valida
    realmente la firma y los permisos en cada petición.
    """
    partes = str(clave or "").split(".")
    if len(partes) != 3:
        return None
    try:
        payload = partes[1] + "=" * (-len(partes[1]) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return str(datos.get("role", "")) or None
    except Exception:
        return None


def credencial_backend_configurada(clave: str | None = None) -> bool:
    """True si la clave exclusiva de Actualidad es una credencial backend.

    Se usa SUPABASE_ACTUALIDAD_KEY para no elevar accidentalmente los permisos
    de los demás módulos que continúan usando SUPABASE_KEY.
    """
    clave = secreto("SUPABASE_ACTUALIDAD_KEY") if clave is None else str(clave or "").strip()
    if clave.startswith("sb_secret_"):
        return True
    if clave.startswith("eyJ"):
        return _rol_jwt(clave) == "service_role"
    return False


def _in_filter(ids: list[str]) -> str:
    """Construye el filtro PostgREST in.(...) para UUIDs ya obtenidos de la DB."""
    seguros = [str(x) for x in ids if re.fullmatch(r"[0-9a-fA-F-]{36}", str(x))]
    return f"in.({','.join(seguros)})" if seguros else "in.()"


def _pedir_lista(tabla: str, params: dict[str, str], timeout: int = 15) -> tuple[bool, list[dict[str, Any]] | str]:
    """Lee una tabla v9 usando la credencial privilegiada exclusiva de Actualidad."""
    base = secreto("SUPABASE_URL").rstrip("/")
    clave = secreto("SUPABASE_ACTUALIDAD_KEY")
    if not base or not clave:
        return False, "Faltan SUPABASE_URL o SUPABASE_ACTUALIDAD_KEY en Streamlit Secrets."

    headers = {"apikey": clave, "Accept": "application/json"}
    # Las claves JWT legacy requieren también Authorization: Bearer.
    # Las nuevas sb_secret_ se envían solamente mediante apikey.
    if clave.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {clave}"

    try:
        respuesta = requests.get(
            f"{base}/rest/v1/{tabla}",
            headers=headers,
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as error:
        return False, f"No se pudo conectar con Supabase ({type(error).__name__})."

    if respuesta.status_code >= 400:
        return False, f"Supabase respondió {respuesta.status_code}: {respuesta.text[:200]}"
    if not respuesta.content:
        return True, []
    try:
        resultado = respuesta.json()
    except ValueError:
        return False, "Supabase devolvió una respuesta que no es JSON válido."
    if resultado is None:
        return True, []
    if not isinstance(resultado, list):
        return False, "La respuesta de Supabase no tuvo el formato esperado."
    return True, resultado


def _mensaje_error(resultado: str) -> str:
    """Traduce errores técnicos a mensajes seguros para la interfaz."""
    texto = str(resultado or "")
    match = re.search(r"respondió (\d{3})", texto)
    codigo = match.group(1) if match else None
    if codigo in {"401", "403"}:
        return (
            "Supabase rechazó la credencial o los permisos. Revisá que "
            "SUPABASE_ACTUALIDAD_KEY sea la clave secreta de backend "
            "(sb_secret_) o la antigua service_role, y que la migración v9 esté aplicada."
        )
    if codigo == "404" or "PGRST205" in texto or "PGRST204" in texto:
        return (
            "Supabase no encontró una tabla o columna del modelo v9. "
            "Revisá que la migración de Actualidad esté aplicada y que el esquema public esté actualizado."
        )
    if codigo:
        return f"No se pudo consultar Actualidad en Supabase (HTTP {codigo})."
    return "No se pudo consultar Actualidad en Supabase. Revisá la conexión y los Secrets del servidor."


def _tipo_fuente(tipo: str) -> str:
    return TIPOS_FUENTE.get(str(tipo or "").lower(), "Fuente")


def normalizar_registros(
    filas_eventos: list[dict],
    filas_actualizaciones: list[dict],
    filas_fuentes: list[dict],
    filas_evento_fuentes: list[dict],
    filas_actualizacion_fuentes: list[dict],
    filas_activos: list[dict],
) -> list[dict]:
    """Convierte las seis tablas relacionadas al contrato que renderiza la UI."""
    fuentes = {}
    for fila in filas_fuentes or []:
        fuente_id = str(fila.get("id", ""))
        if not fuente_id:
            continue
        fuentes[fuente_id] = {
            "id": fuente_id,
            "type": _tipo_fuente(fila.get("tipo_fuente")),
            "name": str(fila.get("nombre_fuente") or "Fuente sin nombre"),
            "title": str(fila.get("titulo_original") or ""),
            "url": fila.get("url"),
            "domain": str(fila.get("dominio") or ""),
            "published_at": fila.get("publicado_en"),
            "source_status": str(fila.get("estado_fuente") or "activa"),
        }

    fuentes_evento: dict[str, list[dict]] = {}
    for relacion in filas_evento_fuentes or []:
        if not relacion.get("vigente", True):
            continue
        evento_id = str(relacion.get("evento_id", ""))
        fuente = fuentes.get(str(relacion.get("fuente_id", "")))
        if evento_id and fuente:
            item = dict(fuente)
            item["function"] = str(relacion.get("funcion") or "contexto")
            item["note"] = str(relacion.get("nota_editorial") or "")
            fuentes_evento.setdefault(evento_id, []).append(item)

    fuentes_update: dict[str, list[dict]] = {}
    for relacion in filas_actualizacion_fuentes or []:
        actualizacion_id = str(relacion.get("actualizacion_id", ""))
        fuente = fuentes.get(str(relacion.get("fuente_id", "")))
        if actualizacion_id and fuente:
            item = dict(fuente)
            item["function"] = str(relacion.get("funcion") or "contexto")
            item["note"] = str(relacion.get("nota_editorial") or "")
            fuentes_update.setdefault(actualizacion_id, []).append(item)

    actualizaciones_por_evento: dict[str, list[dict]] = {}
    for fila in filas_actualizaciones or []:
        evento_id = str(fila.get("evento_id", ""))
        actualizacion_id = str(fila.get("id", ""))
        if not evento_id or not actualizacion_id:
            continue
        actualizaciones_por_evento.setdefault(evento_id, []).append({
            "id": actualizacion_id,
            "at": fila.get("creado_en") or fila.get("fecha_informacion"),
            "status": str(fila.get("estado_resultante") or "en_verificacion"),
            "title": str(fila.get("titulo") or "Actualización"),
            "detail": str(fila.get("detalle") or ""),
            "source_ids": [x["id"] for x in fuentes_update.get(actualizacion_id, [])],
            "sources": fuentes_update.get(actualizacion_id, []),
            "change_type": str(fila.get("tipo_cambio") or "otro"),
            "validity": str(fila.get("vigencia_resultante") or "activa"),
        })

    tickers_por_evento: dict[str, list[str]] = {}
    for fila in filas_activos or []:
        if not fila.get("vigente", True):
            continue
        evento_id = str(fila.get("evento_id", ""))
        ticker = str(fila.get("ticker", "")).strip().upper()
        if evento_id and ticker:
            tickers_por_evento.setdefault(evento_id, []).append(ticker)

    salida = []
    for fila in filas_eventos or []:
        evento_id = str(fila.get("id", ""))
        if not evento_id:
            continue
        # La consulta de Supabase ya entrega las actualizaciones en orden
        # cronológico descendente; preservamos ese orden sin comparar strings
        # de timestamps que podrían tener offsets distintos.
        updates = actualizaciones_por_evento.get(evento_id, [])
        tickers = sorted(set(tickers_por_evento.get(evento_id, [])))
        salida.append({
            "id": evento_id,
            "title": str(fila.get("titular") or "Sin título"),
            "summary": str(fila.get("resumen_actual") or ""),
            "scope": str(fila.get("alcance") or "empresa"),
            "countries": list(fila.get("paises") or []),
            "sectors": list(fila.get("sectores") or []),
            "related_tickers": tickers,
            "status": str(fila.get("estado_editorial") or "en_verificacion"),
            "validity": str(fila.get("vigencia") or "activa"),
            "importance": str(fila.get("importancia") or "media"),
            "created_at": fila.get("publicado_en") or fila.get("creado_en"),
            "updated_at": fila.get("actualizado_en") or fila.get("creado_en"),
            "sources": fuentes_evento.get(evento_id, []),
            "updates": updates,
            "is_demo": False,
        })

    # La consulta de acontecimientos ya viene ordenada por actualizado_en DESC.
    return salida


@st.cache_data(ttl=45, show_spinner=False)
def cargar_actualidad_publicada(limite: int = 100) -> dict[str, Any]:
    """Lee únicamente acontecimientos publicados y aprobados del modelo v9.

    Resultado:
      {"status": "ok", "events": [...], "message": ""}
      {"status": "error", "events": [], "message": "..."}
    """
    if not secreto("SUPABASE_URL") or not secreto("SUPABASE_ACTUALIDAD_KEY"):
        return {
            "status": "error", "events": [],
            "message": (
                "Faltan SUPABASE_URL o SUPABASE_ACTUALIDAD_KEY en los Secrets de Streamlit."
            ),
        }
    if not credencial_backend_configurada():
        return {
            "status": "error", "events": [],
            "message": (
                "SUPABASE_ACTUALIDAD_KEY no parece ser una credencial de backend. "
                "Configurá una clave sb_secret_ o la antigua service_role. "
                "No uses la clave pública sb_publishable_/anon."
            ),
        }

    ok, eventos = _pedir_lista(
        TABLAS["eventos"],
        {
            "select": (
                "id,titular,resumen_actual,alcance,paises,sectores,estado_editorial,vigencia,"
                "importancia,fecha_acontecimiento,publicado_en,creado_en,actualizado_en"
            ),
            "publicable": "eq.true",
            "requiere_revision": "eq.false",
            "order": "actualizado_en.desc",
            "limit": str(max(1, min(int(limite), 200))),
        },
    )
    if not ok:
        return {"status": "error", "events": [], "message": _mensaje_error(eventos)}
    if not eventos:
        return {"status": "ok", "events": [], "message": ""}

    ids_eventos = [str(x.get("id", "")) for x in eventos if x.get("id")]
    filtro_eventos = _in_filter(ids_eventos)
    if filtro_eventos == "in.()":
        return {"status": "ok", "events": [], "message": ""}

    consultas = [
        ("actualizaciones", {
            "select": "id,evento_id,tipo_cambio,titulo,detalle,estado_resultante,vigencia_resultante,fecha_informacion,creado_en,orden",
            "evento_id": filtro_eventos,
            "requiere_revision": "eq.false",
            "order": "creado_en.desc,orden.desc",
            "limit": "500",
        }),
        ("evento_fuentes", {
            "select": "evento_id,fuente_id,funcion,nota_editorial,vigente",
            "evento_id": filtro_eventos,
            "vigente": "eq.true",
            "limit": "500",
        }),
        ("activos", {
            "select": "evento_id,ticker,vigente",
            "evento_id": filtro_eventos,
            "vigente": "eq.true",
            "limit": "500",
        }),
    ]
    resultados: dict[str, list[dict]] = {}
    for clave, params in consultas:
        ok, filas = _pedir_lista(TABLAS[clave], params)
        if not ok:
            return {"status": "error", "events": [], "message": _mensaje_error(filas)}
        resultados[clave] = filas

    ids_actualizaciones = [str(x.get("id", "")) for x in resultados["actualizaciones"] if x.get("id")]
    filas_actualizacion_fuentes: list[dict] = []
    if ids_actualizaciones:
        ok, filas = _pedir_lista(
            TABLAS["actualizacion_fuentes"],
            {
                "select": "actualizacion_id,fuente_id,funcion,nota_editorial",
                "actualizacion_id": _in_filter(ids_actualizaciones),
                "limit": "1000",
            },
        )
        if not ok:
            return {"status": "error", "events": [], "message": _mensaje_error(filas)}
        filas_actualizacion_fuentes = filas

    ids_fuentes = sorted({
        str(x.get("fuente_id", ""))
        for x in resultados["evento_fuentes"] + filas_actualizacion_fuentes
        if x.get("fuente_id")
    })
    filas_fuentes: list[dict] = []
    if ids_fuentes:
        ok, filas = _pedir_lista(
            TABLAS["fuentes"],
            {
                "select": "id,tipo_fuente,nombre_fuente,titulo_original,url,dominio,publicado_en,estado_fuente",
                "id": _in_filter(ids_fuentes),
                "limit": "1000",
            },
        )
        if not ok:
            return {"status": "error", "events": [], "message": _mensaje_error(filas)}
        filas_fuentes = filas

    normalizados = normalizar_registros(
        eventos,
        resultados["actualizaciones"],
        filas_fuentes,
        resultados["evento_fuentes"],
        filas_actualizacion_fuentes,
        resultados["activos"],
    )
    return {"status": "ok", "events": normalizados, "message": ""}
