"""Modo gratuito/manual del Prompt Maestro de NAPO.

No realiza llamadas a APIs ni búsquedas desde el servidor. Prepara un prompt
para usar en ChatGPT (o en otra herramienta externa) y valida la respuesta JSON
que el operador pega de vuelta en La Cocina.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")
MAX_RESPONSE_CHARS = 60_000
BLOCKED_DOMAINS = {
    "reddit.com", "x.com", "twitter.com", "facebook.com", "instagram.com",
    "tiktok.com", "quora.com", "wikipedia.org", "medium.com", "substack.com",
}
ALLOWED_SOURCE_TYPES = {"primaria", "periodistica", "mercado"}
ALLOWED_IMPACTS = {"alcista", "bajista", "neutral"}
ALLOWED_REACH = {"global", "pais", "sector", "empresa", "instrumento"}
ALLOWED_STATES = {"en_verificacion", "reportada", "confirmada", "en_desarrollo", "actualizada", "desmentida"}
ALLOWED_IMPORTANCE = {"alta", "media", "baja"}
ALLOWED_LINK_TYPES = {"directo", "transversal", "referencia", "benchmark"}


def normalizar_url(url: str) -> str:
    try:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return ""
        host = parsed.hostname.lower().removeprefix("www.")
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunparse((parsed.scheme.lower(), host, parsed.path.rstrip("/"), "", "", ""))
    except Exception:
        return ""


def _dominio(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def _dominio_bloqueado(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)


def preparar_prompt_manual(
    consulta: str,
    url: str = "",
    ventana_dias: int = 3,
    contexto_adicional: str = "",
) -> tuple[bool, str]:
    """Construye el prompt gratuito para copiar a ChatGPT; no ejecuta IA ni web."""
    consulta = str(consulta or "").strip()
    if len(consulta) < 2:
        return False, "Ingresá un ticker, empresa o tema para investigar."
    url = str(url or "").strip()
    if url and not normalizar_url(url):
        return False, "El enlace debe comenzar con https:// o http:// y tener un dominio válido."
    try:
        ventana_dias = max(1, min(int(ventana_dias), 7))
    except (TypeError, ValueError):
        ventana_dias = 3

    fecha_hora = datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M (Argentina)")
    contexto = str(contexto_adicional or "").strip() or "Ninguno"
    prompt = f'''Actuá como el Prompt Maestro de NAPO: analista financiero senior y periodista especializado en acciones argentinas, CEDEARs, acciones internacionales y contexto macroeconómico.
Tu prioridad absoluta es la veracidad, la trazabilidad de las fuentes y la atribución correcta.

CONSULTA DE ESTA INVESTIGACIÓN
- Fecha y hora de referencia: {fecha_hora}.
- Activo, ticker o tema: {consulta}.
- Ventana temporal prioritaria: últimos {ventana_dias} día(s).
- URL específica proporcionada por el operador: {url or 'No proporcionada'}.
- Contexto adicional: {contexto}.

REGLAS EDITORIALES NO NEGOCIABLES
1. Realizá búsqueda web en esta conversación. No respondas de memoria.
2. Usá fuentes primarias/institucionales (relaciones con inversores, comunicados, reportes, SEC, CNV, ByMA, bancos centrales y organismos oficiales) y medios financieros reconocidos (Reuters, Bloomberg, Associated Press, Ámbito, El Cronista, Infobae, iProfesional y equivalentes identificables).
3. No uses blogs personales, foros, redes sociales, agregadores de cotizaciones, contenido anónimo ni notas de opinión sin firma como evidencia.
4. No inventes ni estimes cifras, precios, porcentajes, fechas, declaraciones ni nombres. Si no encontrás el dato, escribí “sin dato verificado”.
5. Atribuí cada hecho a su fuente. Diferenciá lo confirmado de lo reportado. Que un medio publique algo confirma la publicación, no necesariamente el hecho.
6. Indicá fecha de publicación de cada fuente en dd/mm/aaaa. Si no se puede determinar, indicá “fecha no informada”.
7. Si hay contradicciones, describí qué informa cada fuente.
8. Separá hechos de interpretación. El impacto potencial es una lectura prudente, nunca recomendación de compra o venta.
9. Priorizá la ventana temporal indicada. Si una noticia es anterior, aclaralo.
10. Si no tenés búsqueda web disponible o no encontrás fuentes admisibles, devolvé found_verified_info=false y no completes con suposiciones.
11. No inventes URLs ni atribuyas a un medio información que no hayas abierto o podido comprobar.
12. Vinculá otros activos solo cuando exista una relación directa o macroeconómica justificada. No asocies automáticamente empresas por pertenecer al mismo sector.
13. Todo resultado es un BORRADOR y requiere revisión humana. No lo marques como confirmado si la única evidencia es un reporte periodístico sin corroboración.
14. No afirmes que una noticia es actualización de otra salvo que se te haya proporcionado el acontecimiento anterior y la relación sea clara. Nunca inventes IDs de Supabase.

SALIDA OBLIGATORIA
Devolvé exclusivamente un objeto JSON válido, sin Markdown, sin bloques de código y sin texto antes o después. Usá exactamente esta estructura y todas sus claves:

{{
  "found_verified_info": true,
  "ticker": "NVDA",
  "asset_name": "NVIDIA",
  "report": {{
    "titular": "Hecho central en una línea",
    "contexto": ["Hecho contextual atribuido a una fuente"],
    "efecto": ["Efecto operativo/financiero verificable; cotización solo con dato comprobado"],
    "impacto": "neutral",
    "justificacion": "Interpretación prudente sustentada en los hechos anteriores"
  }},
  "editorial": {{
    "alcance": "empresa",
    "paises": ["Estados Unidos"],
    "sectores": ["Tecnología"],
    "estado": "reportada",
    "importancia": "media",
    "resumen": "Resumen periodístico breve del acontecimiento",
    "related_assets": [
      {{"ticker": "SPY", "tipo_vinculo": "transversal", "relevancia": "media", "justificacion": "Explicación concreta del vínculo"}}
    ]
  }},
  "sources": [
    {{"tipo": "primaria", "nombre": "Nombre de empresa/medio", "titulo": "Título original", "url": "https://...", "fecha_publicacion": "dd/mm/aaaa", "respalda": "Qué afirmación respalda"}}
  ],
  "conflictos": [],
  "limitaciones": [],
  "requiere_revision_humana": true
}}

VALORES PERMITIDOS
- report.impacto: alcista, bajista o neutral.
- editorial.alcance: global, pais, sector, empresa o instrumento.
- editorial.estado: en_verificacion, reportada, confirmada, en_desarrollo, actualizada o desmentida.
- editorial.importancia: alta, media o baja.
- related_assets[].tipo_vinculo: directo, transversal, referencia o benchmark.
- related_assets[].relevancia: alta, media o baja.
- sources[].tipo: primaria, periodistica o mercado.

IMPORTANTE
- Si no hay información verificable, devolvé igualmente la estructura JSON con found_verified_info=false, ticker vacío, report con campos vacíos/listas vacías, editorial con related_assets vacío, sources vacío y una explicación en limitaciones.
- Máximo tres fuentes principales. No inventes fechas ni enlaces.
- El ticker principal debe ser un ticker identificable con seguridad. Si la consulta es macroeconómica y no corresponde un ticker principal, dejalo vacío; no inventes uno.
- No incluyas en el resumen frases que no estén respaldadas por las fuentes.
- Recordá: la aplicación no puede verificar automáticamente esta respuesta manual. Todas las fuentes deberán ser abiertas y revisadas por el operador antes de publicar.
'''
    return True, prompt.strip()


def _limpiar_json(texto: str) -> str:
    texto = str(texto or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.I | re.S).strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        raise ValueError("No encontré un objeto JSON. Pegá la respuesta completa, sin recortar el principio ni el final.")
    return texto[inicio:fin + 1]


def _texto(value: Any, field: str, max_len: int = 5000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"El campo '{field}' debe ser texto.")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"El campo '{field}' supera el máximo permitido.")
    return value


def parsear_respuesta_manual(texto: str) -> tuple[bool, dict[str, Any] | str]:
    """Valida estructura y consistencia básica; NO certifica la veracidad de las fuentes."""
    texto = str(texto or "").strip()
    if not texto:
        return False, "Pegá la respuesta JSON del asistente."
    if len(texto) > MAX_RESPONSE_CHARS:
        return False, f"La respuesta supera {MAX_RESPONSE_CHARS:,} caracteres. Pegá una respuesta más breve." 
    try:
        data = json.loads(_limpiar_json(texto))
    except (ValueError, json.JSONDecodeError) as exc:
        return False, f"No pude leer el JSON: {exc}"
    if not isinstance(data, dict):
        return False, "La respuesta JSON debe ser un objeto."
    if data.get("found_verified_info") is not True:
        limitaciones = data.get("limitaciones") or []
        detalle = " ".join(str(x) for x in limitaciones[:3]) if isinstance(limitaciones, list) else ""
        return False, "La investigación no encontró información suficientemente verificable. " + detalle

    ticker_raw = _texto(data.get("ticker", ""), "ticker", 24)
    ticker = re.sub(r"[^A-Za-z0-9.\-^]", "", ticker_raw).upper()
    asset_name = _texto(data.get("asset_name", ""), "asset_name", 160)
    report = data.get("report")
    editorial = data.get("editorial")
    if not isinstance(report, dict) or not isinstance(editorial, dict):
        return False, "Faltan los objetos 'report' o 'editorial'. Volvé a generar la salida con el formato solicitado."

    titular = _texto(report.get("titular", ""), "report.titular", 500)
    if not titular:
        return False, "El reporte no contiene un titular."
    if not ticker:
        return False, "No se identificó un ticker principal. Para noticias macro sin ticker todavía necesitaremos un flujo específico."
    impacto = str(report.get("impacto", "")).lower().strip()
    if impacto not in ALLOWED_IMPACTS:
        return False, "El impacto debe ser alcista, bajista o neutral."
    contexto = report.get("contexto", [])
    efecto = report.get("efecto", [])
    if not isinstance(contexto, list) or not isinstance(efecto, list):
        return False, "Los campos contexto y efecto deben ser listas de viñetas."
    contexto = [_texto(x, "report.contexto", 1200) for x in contexto if str(x).strip()]
    efecto = [_texto(x, "report.efecto", 1200) for x in efecto if str(x).strip()]
    justificacion = _texto(report.get("justificacion", ""), "report.justificacion", 1200)

    alcance = str(editorial.get("alcance", "")).lower().strip()
    estado = str(editorial.get("estado", "en_verificacion")).lower().strip()
    importancia = str(editorial.get("importancia", "media")).lower().strip()
    if alcance not in ALLOWED_REACH or estado not in ALLOWED_STATES or importancia not in ALLOWED_IMPORTANCE:
        return False, "La clasificación editorial contiene un valor no permitido. Revisá alcance, estado e importancia."
    paises = editorial.get("paises", [])
    sectores = editorial.get("sectores", [])
    related = editorial.get("related_assets", [])
    if not all(isinstance(x, list) for x in (paises, sectores, related)):
        return False, "Países, sectores y activos relacionados deben ser listas."
    relacionados = []
    for item in related[:20]:
        if not isinstance(item, dict):
            continue
        rticker = re.sub(r"[^A-Za-z0-9.\-^]", "", str(item.get("ticker", ""))).upper()
        tipo = str(item.get("tipo_vinculo", "directo")).lower()
        relevancia = str(item.get("relevancia", "media")).lower()
        just = str(item.get("justificacion", "")).strip()
        if rticker and just and tipo in ALLOWED_LINK_TYPES and relevancia in ALLOWED_IMPORTANCE:
            relacionados.append({"ticker": rticker, "tipo_vinculo": tipo, "relevancia": relevancia, "justificacion": just[:800]})

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return False, "El reporte no contiene fuentes. NAPO no permite preparar un borrador sin fuentes identificables."
    fuentes_limpias = []
    vistas = set()
    for source in sources[:3]:
        if not isinstance(source, dict):
            continue
        tipo = str(source.get("tipo", "")).lower().strip()
        nombre = _texto(source.get("nombre", ""), "sources.nombre", 200)
        titulo = _texto(source.get("titulo", ""), "sources.titulo", 500)
        url = normalizar_url(source.get("url", ""))
        fecha = _texto(source.get("fecha_publicacion", "fecha no informada"), "sources.fecha_publicacion", 40)
        respalda = _texto(source.get("respalda", ""), "sources.respalda", 800)
        if tipo not in ALLOWED_SOURCE_TYPES or not nombre or not titulo or not url or not respalda:
            continue
        domain = _dominio(url)
        if _dominio_bloqueado(domain) or url in vistas:
            continue
        vistas.add(url)
        fuentes_limpias.append({
            "tipo": tipo, "nombre": nombre, "titulo": titulo, "url": url,
            "fecha_publicacion": fecha or "fecha no informada", "respalda": respalda,
            "dominio": domain, "verificacion_manual_obligatoria": True,
        })
    if not fuentes_limpias:
        return False, "Ninguna fuente pasó la validación básica de formato. Revisá los enlaces y tipos de fuente."

    resumen = _texto(editorial.get("resumen", titular), "editorial.resumen", 3000)
    resultado = {
        "found_verified_info": True,
        "ticker": ticker,
        "asset_name": asset_name,
        "report": {
            "titular": titular,
            "contexto": contexto,
            "efecto": efecto,
            "impacto": impacto,
            "justificacion": justificacion,
        },
        "editorial": {
            "alcance": alcance,
            "paises": [str(x).strip()[:100] for x in paises[:10] if str(x).strip()],
            "sectores": [str(x).strip()[:100] for x in sectores[:10] if str(x).strip()],
            "estado": "en_verificacion",  # Nunca elevar a confirmado desde el parseo manual.
            "importancia": importancia,
            "resumen": resumen,
            "related_assets": relacionados,
        },
        "sources": fuentes_limpias,
        "conflictos": [str(x)[:1000] for x in (data.get("conflictos") or [])[:10]],
        "limitaciones": [str(x)[:1000] for x in (data.get("limitaciones") or [])[:10]],
        "requiere_revision_humana": True,
        "modo_manual": True,
        "model": "Modo manual gratuito (respuesta externa)",
        "generated_at": datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M (Argentina)"),
        "verificacion_fuentes": "pendiente de comprobación humana; la aplicación valida formato, no contenido ni autenticidad",
    }
    return True, resultado
