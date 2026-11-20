"""Herramientas editoriales de Actualidad para La Cocina de NAPO.

Todas las operaciones usan SUPABASE_API_KEY exclusivamente desde el servidor.
Las escrituras se hacen mediante RPCs transaccionales creadas por la migración v10.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests
import streamlit as st

from napo_actualidad_datos import credencial_backend_configurada

BASE_RPC = "actualidad_"
ESTADOS = {
    "en_verificacion": "En verificación",
    "reportada": "Reportada",
    "confirmada": "Confirmada",
    "en_desarrollo": "En desarrollo",
    "actualizada": "Actualizada",
    "desmentida": "Desmentida",
    "retirada": "Retirada",
}
ALCANCES = {
    "global": "Global",
    "pais": "País / mercado",
    "sector": "Sector",
    "empresa": "Empresa",
    "instrumento": "Instrumento",
}
TIPOS_FUENTE = {
    "primaria": "Primaria",
    "periodistica": "Periodística",
    "mercado": "Mercado",
}
TIPOS_CAMBIO = {
    "contexto": "Contexto adicional",
    "corroboracion": "Corroboración",
    "confirmacion": "Confirmación",
    "respuesta_oficial": "Respuesta oficial",
    "desmentida": "Desmentida",
    "correccion": "Corrección",
    "cierre": "Cierre",
    "otro": "Otra actualización",
}
VIGENCIAS = {"activa": "Activa", "cerrada": "Cerrada", "archivada": "Archivada"}


def _secreto(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, "") or "").strip()
    except Exception:
        try:
            return str(st.secrets[nombre] or "").strip()
        except Exception:
            return ""


def _credenciales() -> tuple[str, str] | None:
    url = _secreto("SUPABASE_URL").rstrip("/")
    key = _secreto("SUPABASE_API_KEY")
    if not url or not credencial_backend_configurada(key):
        return None
    return url, key


def _headers(key: str) -> dict[str, str]:
    headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _rpc(nombre: str, payload: dict[str, Any]) -> tuple[bool, Any]:
    cred = _credenciales()
    if not cred:
        return False, "Falta SUPABASE_URL o SUPABASE_API_KEY, o la clave no es una credencial privada de backend."
    base, key = cred
    try:
        response = requests.post(
            f"{base}/rest/v1/rpc/{nombre}",
            headers=_headers(key),
            json=payload,
            timeout=25,
        )
    except requests.RequestException as exc:
        return False, f"No se pudo conectar con Supabase ({type(exc).__name__})."
    if response.status_code >= 400:
        # El cuerpo no contiene credenciales; limitamos su longitud para la UI.
        return False, f"Supabase respondió HTTP {response.status_code}: {response.text[:500]}"
    if not response.content:
        return True, None
    try:
        return True, response.json()
    except ValueError:
        return True, response.text


def _get(tabla: str, params: dict[str, str]) -> tuple[bool, Any]:
    cred = _credenciales()
    if not cred:
        return False, "Falta la credencial privada de Actualidad (SUPABASE_API_KEY)."
    base, key = cred
    try:
        response = requests.get(
            f"{base}/rest/v1/{tabla}", headers=_headers(key), params=params, timeout=20
        )
    except requests.RequestException as exc:
        return False, f"No se pudo conectar con Supabase ({type(exc).__name__})."
    if response.status_code >= 400:
        return False, f"Supabase respondió HTTP {response.status_code}: {response.text[:400]}"
    try:
        data = response.json() if response.content else []
    except ValueError:
        return False, "Supabase devolvió una respuesta no válida."
    return True, data if isinstance(data, list) else []


def parsear_tickers(texto: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parsea líneas TICKER | justificación o TICKER | tipo | relevancia | justificación."""
    activos: list[dict[str, str]] = []
    errores: list[str] = []
    vistos: set[str] = set()
    tipos_validos = {"directo", "transversal", "referencia", "benchmark"}
    relevancias_validas = {"alta", "media", "baja"}
    for numero, linea in enumerate(str(texto or "").splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        partes = [x.strip() for x in linea.split("|")]
        ticker = re.sub(r"[^A-Za-z0-9.\-^]", "", partes[0]).upper()[:24]
        if not ticker:
            errores.append(f"Línea {numero}: falta el ticker.")
            continue
        if ticker in vistos:
            errores.append(f"Línea {numero}: ticker repetido ({ticker}).")
            continue
        if len(partes) == 2:
            tipo, relevancia, justificacion = "directo", "alta", partes[1]
        elif len(partes) == 4:
            tipo, relevancia, justificacion = partes[1].lower(), partes[2].lower(), partes[3]
        else:
            errores.append(
                f"Línea {numero}: usá TICKER | justificación o TICKER | tipo | relevancia | justificación."
            )
            continue
        if tipo not in tipos_validos:
            errores.append(f"Línea {numero}: tipo de vínculo inválido ({tipo}).")
            continue
        if relevancia not in relevancias_validas:
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


def dominio_de_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed.netloc.lower().removeprefix("www.")


def validar_formulario(datos: dict[str, Any]) -> list[str]:
    errores = []
    for campo, etiqueta in (("titular", "titular"), ("resumen", "resumen"),
                            ("fuente_nombre", "nombre de la fuente"),
                            ("fuente_titulo", "título original de la fuente"),
                            ("fuente_url", "URL de la fuente"), ("detalle", "detalle inicial")):
        if not str(datos.get(campo, "")).strip():
            errores.append(f"Completá el {etiqueta}.")
    if datos.get("estado") not in ESTADOS:
        errores.append("Seleccioná un estado editorial válido.")
    if datos.get("alcance") not in ALCANCES:
        errores.append("Seleccioná un alcance válido.")
    if datos.get("tipo_fuente") not in TIPOS_FUENTE:
        errores.append("Seleccioná un tipo de fuente válido.")
    if not dominio_de_url(datos.get("fuente_url", "")):
        errores.append("La fuente necesita una URL válida que empiece con http:// o https://.")
    _, errores_tickers = parsear_tickers(datos.get("tickers_texto", ""))
    errores.extend(errores_tickers)
    return errores


def guardar_borrador(datos: dict[str, Any]) -> tuple[bool, Any]:
    """Crea evento, primera fuente, primera actualización y tickers en una transacción SQL."""
    errores = validar_formulario(datos)
    if errores:
        return False, " ".join(errores)

    tickers, _ = parsear_tickers(datos.get("tickers_texto", ""))
    url = str(datos["fuente_url"]).strip()
    evento = {
        "titular": str(datos["titular"]).strip(),
        "resumen_actual": str(datos["resumen"]).strip(),
        "alcance": datos["alcance"],
        "paises": [x.strip() for x in str(datos.get("paises", "")).split(",") if x.strip()],
        "sectores": [x.strip() for x in str(datos.get("sectores", "")).split(",") if x.strip()],
        "estado_editorial": datos["estado"],
        "vigencia": "activa",
        "importancia": datos.get("importancia", "media"),
        "idioma_redaccion": datos.get("idioma", "es-AR"),
        "origen_ingesta": "manual",
        "notas_editoriales_internas": str(datos.get("nota_interna", "")).strip(),
    }
    fuente = {
        "tipo_fuente": datos["tipo_fuente"],
        "nombre_fuente": str(datos["fuente_nombre"]).strip(),
        "titulo_original": str(datos["fuente_titulo"]).strip(),
        "url": url,
        "dominio": dominio_de_url(url),
        "idioma": datos.get("idioma", "es-AR"),
        "nota_verificacion": str(datos.get("nota_fuente", "")).strip(),
        "funcion": "fuente_inicial",
        "nota_editorial": str(datos.get("nota_fuente", "")).strip(),
    }
    actualizacion = {
        "tipo_cambio": "publicacion_inicial",
        "titulo": "Publicación inicial",
        "detalle": str(datos["detalle"]).strip(),
        "estado_resultante": datos["estado"],
        "vigencia_resultante": "activa",
        "requiere_revision": False,
    }
    resultado = _rpc("actualidad_guardar_evento_editorial", {
        "p_evento": evento,
        "p_fuente": fuente,
        "p_actualizacion": actualizacion,
        "p_activos": tickers,
    })
    if resultado[0]:
        listar_eventos_admin.clear()
    return resultado


@st.cache_data(ttl=15, show_spinner=False)
def listar_eventos_admin(limite: int = 50) -> tuple[bool, Any]:
    return _get("actualidad_eventos", {
        "select": "id,titular,resumen_actual,alcance,estado_editorial,vigencia,importancia,publicable,requiere_revision,creado_en,actualizado_en",
        "order": "actualizado_en.desc",
        "limit": str(max(1, min(int(limite), 100))),
    })


def publicar_evento(evento_id: str) -> tuple[bool, Any]:
    resultado = _rpc("actualidad_publicar_evento_editorial", {"p_evento_id": evento_id})
    if resultado[0]:
        listar_eventos_admin.clear()
    return resultado


def agregar_actualizacion(evento_id: str, datos: dict[str, Any]) -> tuple[bool, Any]:
    titulo = str(datos.get("titulo", "")).strip()
    detalle = str(datos.get("detalle", "")).strip()
    url = str(datos.get("fuente_url", "")).strip()
    if not titulo or not detalle:
        return False, "Completá el título y el detalle de la actualización."
    if not datos.get("tipo_cambio") in TIPOS_CAMBIO:
        return False, "Tipo de actualización inválido."
    if datos.get("estado") not in ESTADOS or datos.get("vigencia") not in VIGENCIAS:
        return False, "Estado o vigencia inválidos."
    if not str(datos.get("fuente_nombre", "")).strip() or not str(datos.get("fuente_titulo", "")).strip():
        return False, "Completá el nombre y el título original de la fuente."
    dominio = dominio_de_url(url)
    if not dominio:
        return False, "Ingresá una URL válida de la fuente."

    fuente = {
        "tipo_fuente": datos.get("tipo_fuente", "periodistica"),
        "nombre_fuente": str(datos["fuente_nombre"]).strip(),
        "titulo_original": str(datos["fuente_titulo"]).strip(),
        "url": url,
        "dominio": dominio,
        "idioma": datos.get("idioma", "es-AR"),
        "nota_verificacion": str(datos.get("nota_fuente", "")).strip(),
        "funcion": datos.get("funcion_fuente", "contexto"),
        "nota_editorial": str(datos.get("nota_fuente", "")).strip(),
    }
    actualizacion = {
        "tipo_cambio": datos["tipo_cambio"],
        "titulo": titulo,
        "detalle": detalle,
        "estado_resultante": datos["estado"],
        "vigencia_resultante": datos["vigencia"],
        "requiere_revision": False,
        "resumen_actual": str(datos.get("resumen_actual", "")).strip(),
    }
    resultado = _rpc("actualidad_agregar_actualizacion_editorial", {
        "p_evento_id": evento_id,
        "p_actualizacion": actualizacion,
        "p_fuente": fuente,
    })
    if resultado[0]:
        listar_eventos_admin.clear()
    return resultado


def _flash(tipo: str, mensaje: str):
    st.session_state["actualidad_admin_flash"] = (tipo, mensaje)


def _mostrar_error(resultado: Any):
    texto = str(resultado or "Error desconocido")
    if "PGRST202" in texto or "42883" in texto or "function" in texto.lower():
        st.error("No encuentro las funciones editoriales de la migración v10. Ejecutá primero el SQL v10 en Supabase.")
    elif "401" in texto or "403" in texto:
        st.error("Supabase rechazó la clave o los permisos. Revisá SUPABASE_API_KEY (clave Secret de backend).")
    else:
        st.error(texto[:700])


def _seccion_alta():
    st.markdown("#### Crear acontecimiento")
    st.caption("Se guarda como borrador privado. No aparece en Actualidad pública hasta que lo revises y publiques.")
    with st.form("actualidad_admin_crear_form", clear_on_submit=False):
        titular = st.text_input("Titular", placeholder="Ej.: NVIDIA presenta sus resultados trimestrales")
        resumen = st.text_area("Resumen actual", height=90, placeholder="Qué ocurrió, en términos claros y verificables.")
        col1, col2 = st.columns(2)
        with col1:
            alcance = st.selectbox("Alcance", list(ALCANCES), format_func=lambda x: ALCANCES[x])
            estados_iniciales = ["en_verificacion", "reportada", "confirmada", "en_desarrollo"]
            estado = st.selectbox("Estado editorial inicial", estados_iniciales, index=1, format_func=lambda x: ESTADOS[x])
            importancia = st.selectbox("Importancia", ["alta", "media", "baja"], index=1)
        with col2:
            paises = st.text_input("Países / mercados (separados por coma)", placeholder="Estados Unidos, Argentina")
            sectores = st.text_input("Sectores (separados por coma)", placeholder="Tecnología, Semiconductores")
            idioma = st.selectbox("Idioma editorial", ["es-AR", "es", "en", "pt-BR"], index=0)
        tickers_texto = st.text_area(
            "Activos vinculados (una línea por activo)",
            height=110, placeholder=(
                "NVDA | La noticia trata directamente sobre NVIDIA.\n"
                "QQQ | transversal | media | Puede tener un efecto relevante sobre el índice."
            ),
        )
        st.markdown("**Fuente inicial**")
        col3, col4 = st.columns(2)
        with col3:
            tipo_fuente = st.selectbox("Tipo de fuente", list(TIPOS_FUENTE), format_func=lambda x: TIPOS_FUENTE[x])
            fuente_nombre = st.text_input("Nombre del medio / entidad", placeholder="Reuters / NVIDIA Investor Relations")
        with col4:
            fuente_titulo = st.text_input("Título original de la publicación")
            fuente_url = st.text_input("URL original", placeholder="https://...")
        nota_fuente = st.text_input("Nota breve de verificación (opcional)")
        st.markdown("**Primera actualización**")
        detalle = st.text_area("Detalle inicial", height=100, placeholder="Qué se sabe hasta ahora y qué está respaldado por la fuente.")
        nota_interna = st.text_area("Nota editorial interna (no se publica)", height=70)
        guardar = st.form_submit_button("💾 Guardar como borrador", type="primary", use_container_width=True)

    if guardar:
        datos = {
            "titular": titular, "resumen": resumen, "alcance": alcance, "estado": estado,
            "importancia": importancia, "paises": paises, "sectores": sectores, "idioma": idioma,
            "tickers_texto": tickers_texto, "tipo_fuente": tipo_fuente, "fuente_nombre": fuente_nombre,
            "fuente_titulo": fuente_titulo, "fuente_url": fuente_url, "nota_fuente": nota_fuente,
            "detalle": detalle, "nota_interna": nota_interna,
        }
        errores = validar_formulario(datos)
        if errores:
            for error in errores:
                st.warning(error)
        else:
            with st.spinner("Guardando acontecimiento, fuente, actualización y activos en una transacción..."):
                ok, resultado = guardar_borrador(datos)
            if ok:
                _flash("success", f"Borrador guardado correctamente. ID: {resultado.get('evento_id') if isinstance(resultado, dict) else resultado}")
                st.rerun()
            else:
                _mostrar_error(resultado)


def _seccion_revision():
    st.markdown("#### Borradores y noticias publicadas")
    ok, eventos = listar_eventos_admin()
    if not ok:
        _mostrar_error(eventos)
        return
    if not eventos:
        st.info("Todavía no hay acontecimientos cargados en Supabase.")
        return

    borradores = [e for e in eventos if not e.get("publicable")]
    publicados = [e for e in eventos if e.get("publicable")]
    if borradores:
        st.markdown("**Pendientes de revisión / publicación**")
        for evento in borradores:
            with st.container(border=True):
                st.markdown(f"**{evento.get('titular', 'Sin titular')}**")
                st.caption(f"{ALCANCES.get(evento.get('alcance'), evento.get('alcance'))} · {ESTADOS.get(evento.get('estado_editorial'), evento.get('estado_editorial'))} · Importancia {evento.get('importancia', 'media')}")
                st.write(str(evento.get("resumen_actual") or ""))
                if evento.get("estado_editorial") == "en_verificacion":
                    st.warning("Todavía está en verificación. Agregá una corroboración o cambiá su estado mediante una actualización antes de publicar.")
                c1, c2 = st.columns([1, 5])
                with c1:
                    deshabilitado = evento.get("estado_editorial") == "en_verificacion" or evento.get("vigencia") == "archivada"
                    if st.button("Publicar", key=f"act_pub_{evento['id']}", disabled=deshabilitado):
                        with st.spinner("Publicando..."):
                            ok_pub, res_pub = publicar_evento(evento["id"])
                        if ok_pub:
                            _flash("success", "Acontecimiento publicado correctamente.")
                            st.rerun()
                        else:
                            _mostrar_error(res_pub)
                with c2:
                    st.caption(f"ID: {evento.get('id')} · Creado: {evento.get('creado_en', '')}")
    else:
        st.success("No hay borradores pendientes.")

    if publicados:
        st.markdown("**Últimos acontecimientos publicados**")
        for evento in publicados[:15]:
            with st.container(border=True):
                st.markdown(f"**{evento.get('titular', 'Sin titular')}**")
                st.caption(f"{ESTADOS.get(evento.get('estado_editorial'), evento.get('estado_editorial'))} · {VIGENCIAS.get(evento.get('vigencia'), evento.get('vigencia'))} · {evento.get('actualizado_en', '')}")


def _seccion_actualizaciones():
    st.markdown("#### Agregar actualización a un acontecimiento")
    ok, eventos = listar_eventos_admin()
    if not ok:
        _mostrar_error(eventos)
        return
    if not eventos:
        st.info("Primero creá un acontecimiento.")
        return
    opciones = {str(e["id"]): e for e in eventos if e.get("vigencia") != "archivada"}
    if not opciones:
        st.info("No hay acontecimientos activos para actualizar.")
        return
    with st.form("actualidad_admin_update_form", clear_on_submit=False):
        evento_id = st.selectbox(
            "Acontecimiento", list(opciones),
            format_func=lambda x: f"{'Publicado' if opciones[x].get('publicable') else 'Borrador'} · {opciones[x].get('titular', x)}",
        )
        tipo_cambio = st.selectbox("Tipo de actualización", list(TIPOS_CAMBIO), format_func=lambda x: TIPOS_CAMBIO[x])
        estado = st.selectbox("Estado resultante", list(ESTADOS), index=1, format_func=lambda x: ESTADOS[x])
        vigencia = st.selectbox("Vigencia", list(VIGENCIAS), index=0, format_func=lambda x: VIGENCIAS[x])
        titulo = st.text_input("Título de la actualización")
        detalle = st.text_area("Qué cambió y qué evidencia lo respalda", height=110)
        resumen_actual = st.text_area("Nuevo resumen actual (opcional)", height=80)
        st.markdown("**Fuente de esta actualización**")
        col1, col2 = st.columns(2)
        with col1:
            tipo_fuente = st.selectbox("Tipo de fuente de actualización", list(TIPOS_FUENTE), index=1, format_func=lambda x: TIPOS_FUENTE[x])
            fuente_nombre = st.text_input("Nombre de la fuente de actualización")
        with col2:
            fuente_titulo = st.text_input("Título original de la fuente de actualización")
            fuente_url = st.text_input("URL de la fuente de actualización")
        nota_fuente = st.text_input("Nota de verificación de esta fuente (opcional)")
        guardar = st.form_submit_button("Agregar actualización al historial", type="primary", use_container_width=True)
    if guardar:
        ok_upd, resultado = agregar_actualizacion(evento_id, {
            "tipo_cambio": tipo_cambio, "estado": estado, "vigencia": vigencia,
            "titulo": titulo, "detalle": detalle, "resumen_actual": resumen_actual,
            "tipo_fuente": tipo_fuente, "fuente_nombre": fuente_nombre,
            "fuente_titulo": fuente_titulo, "fuente_url": fuente_url,
            "nota_fuente": nota_fuente,
        })
        if ok_upd:
            _flash("success", "Actualización agregada. El historial anterior se conservó.")
            st.rerun()
        else:
            _mostrar_error(resultado)


def seccion_actualidad_admin():
    """Punto de entrada de la nueva sección de La Cocina."""
    st.markdown("### 🗞️ Gestión editorial de Actualidad")
    st.caption("Los borradores no aparecen en el sitio público. Publicar es una acción explícita.")
    mensaje = st.session_state.pop("actualidad_admin_flash", None)
    if mensaje:
        getattr(st, mensaje[0])(mensaje[1])
    if not _credenciales():
        st.error("No está disponible la clave privada de Actualidad. Revisá SUPABASE_URL y SUPABASE_API_KEY en Streamlit Secrets.")
        return
    pestañas = st.tabs(["✍️ Crear acontecimiento", "🛡️ Revisar y publicar", "🕒 Agregar actualización"])
    with pestañas[0]:
        _seccion_alta()
    with pestañas[1]:
        _seccion_revision()
    with pestañas[2]:
        _seccion_actualizaciones()
