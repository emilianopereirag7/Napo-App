"""Adaptadores puros entre la salida del Prompt Maestro y el modelo de Actualidad.

Este módulo no accede a Streamlit ni a Supabase. Su responsabilidad es reutilizar
el contenido ya interpretado por napo_reportes.parsear_reporte y completarlo con
metadatos de trazabilidad que no forman parte del reporte táctico tradicional.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any

ESTADOS = {
    "en_verificacion", "reportada", "confirmada", "en_desarrollo",
    "actualizada", "desmentida", "retirada",
}
ALCANCES = {"global", "pais", "sector", "empresa", "instrumento"}
IMPORTANCIAS = {"alta", "media", "baja"}
TIPOS_FUENTE = {"primaria", "periodistica", "mercado"}
TIPOS_VINCULO = {"directo", "transversal", "referencia", "benchmark"}
RELEVANCIAS = {"alta", "media", "baja"}

_URL_RE = re.compile(r"https?://[^\s<>\]\[()]+", re.IGNORECASE)


def extraer_url_fuente(texto: str) -> str:
    """Devuelve la primera URL explícita de la línea Fuente, si existe."""
    match = _URL_RE.search(str(texto or ""))
    if not match:
        return ""
    return match.group(0).rstrip(".,;:)")


def limpiar_nombre_fuente(texto: str) -> str:
    """Quita etiquetas y URLs de la línea Fuente para sugerir el nombre del medio."""
    valor = str(texto or "").strip()
    valor = re.sub(r"^\s*fuente(?:\s+oficial)?\s*:\s*", "", valor, flags=re.IGNORECASE)
    valor = _URL_RE.sub("", valor)
    valor = valor.strip(" \t-–—|,;:.")
    return valor[:180]


def dominio_de_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed.netloc.lower().removeprefix("www.")


def _lista_comas(valor: Any) -> list[str]:
    salida = []
    vistos = set()
    for item in str(valor or "").split(","):
        limpio = item.strip()
        clave = limpio.casefold()
        if limpio and clave not in vistos:
            vistos.add(clave)
            salida.append(limpio)
    return salida


def parsear_activos_extra(texto: str, ticker_principal: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parsea activos extra en líneas TICKER | justificación [| tipo | relevancia].

    Formatos aceptados:
      TICKER | justificación
      TICKER | tipo_vinculo | relevancia | justificación
    El ticker principal del Prompt Maestro se agrega automáticamente.
    """
    principal = re.sub(r"[^A-Za-z0-9.\-^]", "", str(ticker_principal or "")).upper()[:24]
    if not principal:
        return [], ["El reporte no contiene un ticker principal válido."]

    activos = [{
        "ticker": principal,
        "nombre_activo": "",
        "mercado": "",
        "tipo_vinculo": "directo",
        "relevancia": "alta",
        "justificacion": "Activo principal indicado en el reporte táctico.",
    }]
    vistos = {principal}
    errores: list[str] = []

    for numero, linea in enumerate(str(texto or "").splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        partes = [parte.strip() for parte in linea.split("|")]
        ticker = re.sub(r"[^A-Za-z0-9.\-^]", "", partes[0]).upper()[:24]
        if not ticker:
            errores.append(f"Línea {numero}: ticker inválido.")
            continue
        if ticker in vistos:
            errores.append(f"Línea {numero}: ticker repetido ({ticker}).")
            continue
        if len(partes) == 2:
            tipo, relevancia, justificacion = "directo", "media", partes[1]
        elif len(partes) == 4:
            tipo, relevancia, justificacion = partes[1].lower(), partes[2].lower(), partes[3]
        else:
            errores.append(f"Línea {numero}: usá TICKER | justificación o TICKER | tipo | relevancia | justificación.")
            continue
        if tipo not in TIPOS_VINCULO:
            errores.append(f"Línea {numero}: tipo de vínculo inválido ({tipo}).")
            continue
        if relevancia not in RELEVANCIAS:
            errores.append(f"Línea {numero}: relevancia inválida ({relevancia}).")
            continue
        if not justificacion:
            errores.append(f"Línea {numero}: falta la justificación editorial.")
            continue
        vistos.add(ticker)
        activos.append({
            "ticker": ticker,
            "nombre_activo": "",
            "mercado": "",
            "tipo_vinculo": tipo,
            "relevancia": relevancia,
            "justificacion": justificacion,
        })
    return activos, errores



def armar_fuentes_adicionales(fuentes: Any) -> tuple[list[dict[str, str]], list[str]]:
    """Normaliza hasta dos fuentes de contraste para guardar en el modelo editorial.

    Recibe fuentes ya parseadas por napo_ia_reportes; la primera fuente se envía
    como p_fuente y esta función procesa las restantes.
    """
    salida: list[dict[str, str]] = []
    errores: list[str] = []
    if fuentes is None:
        return salida, errores
    if not isinstance(fuentes, list):
        return [], ["Las fuentes adicionales deben ser una lista."]

    for indice, fuente in enumerate(fuentes[:2], start=2):
        if not isinstance(fuente, dict):
            errores.append(f"La fuente adicional {indice} tiene un formato inválido.")
            continue
        tipo = str(fuente.get("tipo") or "").strip().lower()
        nombre = str(fuente.get("nombre") or "").strip()
        titulo = str(fuente.get("titulo") or "").strip()
        url = str(fuente.get("url") or "").strip()
        fecha = str(fuente.get("fecha_publicacion") or "fecha no informada").strip()
        respalda = str(fuente.get("respalda") or "").strip()
        dominio = dominio_de_url(url)
        if tipo not in TIPOS_FUENTE or not nombre or not titulo or not dominio or not respalda:
            errores.append(
                f"La fuente adicional {indice} está incompleta (tipo, nombre, título, URL o afirmación respaldada)."
            )
            continue
        nota = f"Fecha de publicación: {fecha}. Respalda: {respalda}"[:1800]
        salida.append({
            "tipo_fuente": tipo,
            "nombre_fuente": nombre[:200],
            "titulo_original": titulo[:500],
            "url": url,
            "dominio": dominio,
            "idioma": "",
            "nota_verificacion": nota,
            "funcion": "corroboracion",
            "nota_editorial": respalda[:1200],
        })
    if len(fuentes) > 3:
        errores.append("NAPO admite hasta tres fuentes principales por reporte.")
    return salida, errores

def armar_payload_desde_reporte(reporte: dict[str, Any], metadata: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Construye el payload exacto de la RPC v10 desde el reporte ya parseado."""
    errores: list[str] = []
    ticker = re.sub(r"[^A-Za-z0-9.\-^]", "", str(reporte.get("ticker") or "")).upper()[:24]
    titular = str(reporte.get("titular") or "").strip()
    contexto = str(reporte.get("contexto") or "").strip()
    efecto = str(reporte.get("efecto") or "").strip()
    impacto = str(reporte.get("impacto") or "").strip().lower()
    justificacion = str(reporte.get("justificacion") or "").strip()

    if not ticker:
        errores.append("El reporte necesita un ticker para vincular el acontecimiento.")
    if not titular:
        errores.append("El reporte necesita un titular.")
    if not (contexto or efecto):
        errores.append("El reporte necesita contexto o efecto para crear el acontecimiento.")

    tipo_fuente = str(metadata.get("tipo_fuente") or "periodistica").strip().lower()
    alcance = str(metadata.get("alcance") or "empresa").strip().lower()
    estado = str(metadata.get("estado") or "en_verificacion").strip().lower()
    importancia = str(metadata.get("importancia") or "media").strip().lower()
    fuente_nombre = str(metadata.get("fuente_nombre") or limpiar_nombre_fuente(reporte.get("fuente", ""))).strip()
    fuente_titulo = str(metadata.get("fuente_titulo") or "").strip()
    fuente_url = str(metadata.get("fuente_url") or extraer_url_fuente(reporte.get("fuente", ""))).strip()
    dominio = dominio_de_url(fuente_url)

    if tipo_fuente not in TIPOS_FUENTE:
        errores.append("Seleccioná un tipo de fuente válido.")
    if alcance not in ALCANCES:
        errores.append("Seleccioná un alcance válido.")
    if estado not in ESTADOS:
        errores.append("Seleccioná un estado editorial válido.")
    if importancia not in IMPORTANCIAS:
        errores.append("Seleccioná una importancia válida.")
    if not fuente_nombre:
        errores.append("Completá el nombre del medio o entidad que publicó la fuente.")
    if not fuente_titulo:
        errores.append("Completá el título original de la publicación fuente. No lo inventamos a partir del titular NAPO.")
    if not dominio:
        errores.append("Completá una URL original válida (http:// o https://).")

    activos, errores_activos = parsear_activos_extra(metadata.get("activos_extra", ""), ticker)
    errores.extend(errores_activos)
    if errores:
        return None, errores

    resumen_editorial = str(metadata.get("resumen_actual") or "").strip()
    resumen_partes = [x for x in (contexto, efecto) if x]
    resumen = resumen_editorial or "\n\n".join(resumen_partes)
    detalle_partes = []
    if contexto:
        detalle_partes.append("Contexto: " + contexto)
    if efecto:
        detalle_partes.append("Efecto en la acción: " + efecto)
    if impacto:
        detalle_partes.append("Impacto potencial: " + impacto.capitalize() + (". " + justificacion if justificacion else "."))
    detalle = "\n\n".join(detalle_partes)

    nota_fuente = str(metadata.get("nota_fuente") or "").strip()
    nota_interna = str(metadata.get("nota_interna") or "").strip()
    idioma = str(metadata.get("idioma") or "es-AR").strip()

    payload = {
        "p_evento": {
            "titular": titular,
            "resumen_actual": resumen,
            "alcance": alcance,
            "paises": _lista_comas(metadata.get("paises", "")),
            "sectores": _lista_comas(metadata.get("sectores", "")),
            "estado_editorial": estado,
            "vigencia": "activa",
            "importancia": importancia,
            "idioma_redaccion": idioma,
            "origen_ingesta": "manual",
            "notas_editoriales_internas": nota_interna,
        },
        "p_fuente": {
            "tipo_fuente": tipo_fuente,
            "nombre_fuente": fuente_nombre,
            "titulo_original": fuente_titulo,
            "url": fuente_url,
            "dominio": dominio,
            "idioma": idioma,
            "nota_verificacion": nota_fuente,
            "funcion": "fuente_inicial",
            "nota_editorial": nota_fuente,
        },
        "p_actualizacion": {
            "tipo_cambio": "publicacion_inicial",
            "titulo": "Publicación inicial",
            "detalle": detalle,
            "estado_resultante": estado,
            "vigencia_resultante": "activa",
            "nota_editorial_interna": nota_interna,
        },
        "p_activos": activos,
    }
    return payload, []
