"""La Cocina: back-office del operador.

Se entra agregando ?cocina=1 a la dirección de la app y escribiendo la clave (Secret COCINA_CLAVE).
Con la sesión abierta aparece, arriba de la página, el panel con cuatro secciones:
reportes (publicar, editar, vista previa del audio), noticias en Shorts, uso y sistema.
"""

import hmac
import hashlib
import json
from datetime import datetime
from importlib import metadata

import streamlit as st

import napo_basedatos as basedatos
from napo_componentes import kpi_grid
from napo_config import ACTIVOS, KLEIN_BLUE
from napo_datos import cargar_precios, tickers_sin_datos
from napo_actualidad_admin import guardar_borrador_y_vincular_reporte, seccion_actualidad_admin
from napo_actualidad_integracion import armar_fuentes_adicionales, armar_payload_desde_reporte, extraer_url_fuente, limpiar_nombre_fuente
from napo_ia_reportes import parsear_respuesta_manual, preparar_prompt_manual
from napo_eventos import leer_eventos, resumir
from napo_reportes import (
    IMPACTOS, LIMITE_AUDIO_BYTES, actualizar_reporte, eliminar_reporte, generar_audio, guion_audio,
    leer_reporte, listar_reportes, normalizar_ticker, parsear_reporte, publicar_reporte_con_id,
    reportes_configurados, validar_reporte,
)
from napo_secretos import secreto
from napo_shorts import (
    agregar_short, canal_confiable, datos_oembed, eliminar_short, extraer_video_id, listar_shorts,
)

CAMPOS_REPORTE = ("rep_pegado", "rep_ticker", "rep_titular", "rep_contexto", "rep_efecto", "rep_justif", "rep_fuente")
CAMPOS_SHORT = ("sh_url", "sh_titulo", "sh_canal", "sh_nota")
CAMPOS_ACTUALIDAD = (
    "rep_act_fuente_nombre", "rep_act_fuente_titulo", "rep_act_fuente_url",
    "rep_act_tipo_fuente", "rep_act_alcance", "rep_act_estado", "rep_act_importancia",
    "rep_act_paises", "rep_act_sectores", "rep_act_activos_extra", "rep_act_resumen",
    "rep_act_nota_fuente", "rep_act_nota_interna",
)
SECCIONES = ["📝 Reportes", "🎬 Noticias en Shorts", "🗞️ Actualidad", "📊 Uso", "⚙️ Sistema"]


def clave_correcta(ingresada: str) -> bool:
    """Compara la clave ingresada con la guardada en Secrets (COCINA_CLAVE)."""
    esperada = secreto("COCINA_CLAVE")
    if not esperada:
        return False
    return hmac.compare_digest(ingresada.encode("utf-8"), esperada.encode("utf-8"))


# ================================================================ callbacks
# (corren ANTES de redibujar la página, por eso pueden cambiar los campos sin problemas)

def _avisar(tipo: str, texto: str):
    st.session_state["rep_msg"] = (tipo, texto)


def _leer_formulario() -> dict:
    ss = st.session_state
    return {
        "ticker": normalizar_ticker(ss.get("rep_ticker", "")),
        "titular": str(ss.get("rep_titular", "")).strip(),
        "contexto": str(ss.get("rep_contexto", "")).strip(),
        "efecto": str(ss.get("rep_efecto", "")).strip(),
        "impacto": ss.get("rep_impacto", "neutral"),
        "justificacion": str(ss.get("rep_justif", "")).strip(),
        "fuente": str(ss.get("rep_fuente", "")).strip(),
    }


def _limpiar_formulario():
    for clave in CAMPOS_REPORTE:
        st.session_state[clave] = ""
    for clave in CAMPOS_ACTUALIDAD:
        st.session_state.pop(clave, None)
    st.session_state.pop("rep_actualidad_ultimo_fingerprint", None)
    st.session_state.pop("rep_actualidad_ultimo_id", None)
    st.session_state.pop("rep_crear_actualidad_al_publicar", None)
    st.session_state.pop("rep_reporte_id_pendiente", None)
    st.session_state.pop("rep_reporte_fingerprint_pendiente", None)
    st.session_state.pop("rep_reporte_audio_guardado", None)
    st.session_state.pop("rep_reporte_audio_aviso", None)
    st.session_state.pop("rep_evento_id_pendiente", None)
    st.session_state["rep_impacto"] = "neutral"
    st.session_state["rep_editando"] = None
    st.session_state.pop("rep_preview", None)
    st.session_state.pop("rep_ia_resultado", None)


def _cb_rellenar():
    if st.session_state.get("rep_reporte_id_pendiente"):
        _avisar("warning", "Primero terminá de vincular el reporte ya publicado con Actualidad; no cargues otro reporte todavía.")
        return
    datos = parsear_reporte(st.session_state.get("rep_pegado", ""))
    if not any(datos[k] for k in ("titular", "contexto", "efecto")):
        _avisar("warning", "No reconocí el formato. Pegá la respuesta completa del prompt maestro "
                           "(con Titular, Contexto, Efecto, Impacto y Fuente).")
        return
    ss = st.session_state
    ss["rep_ticker"] = datos["ticker"] or ss.get("rep_ticker", "")
    ss["rep_titular"] = datos["titular"]
    ss["rep_contexto"] = datos["contexto"]
    ss["rep_efecto"] = datos["efecto"]
    ss["rep_justif"] = datos["justificacion"]
    ss["rep_fuente"] = datos["fuente"]
    # Sugerimos nombre y URL si la línea Fuente del Prompt Maestro los incluye.
    # El título original de la publicación se confirma manualmente; no se inventa.
    ss["rep_act_fuente_nombre"] = limpiar_nombre_fuente(datos["fuente"])
    ss["rep_act_fuente_url"] = extraer_url_fuente(datos["fuente"])
    ss["rep_act_fuente_titulo"] = ""
    ss["rep_act_resumen"] = ""
    ss["rep_act_paises"] = ""
    ss["rep_act_sectores"] = ""
    ss["rep_act_activos_extra"] = ""
    ss["rep_act_nota_fuente"] = ""
    ss["rep_act_nota_interna"] = ""
    ss["rep_crear_actualidad_al_publicar"] = False
    ss.pop("rep_actualidad_ultimo_fingerprint", None)
    ss.pop("rep_actualidad_ultimo_id", None)
    if datos["impacto"]:
        ss["rep_impacto"] = datos["impacto"]
    faltan = [nombre for nombre, valor in (("ticker", ss["rep_ticker"]), ("impacto", datos["impacto"])) if not valor]
    _avisar("success", "Campos completados. Revisalos antes de publicar."
                       + (f" Falta completar: {', '.join(faltan)}." if faltan else ""))


def _audio_para(rep: dict):
    """(audio, aviso). Reusa la vista previa si el texto no cambió desde que se escuchó."""
    guion = guion_audio(rep)
    previa = st.session_state.get("rep_preview")
    if previa and previa.get("guion") == guion and previa.get("audio"):
        return previa["audio"], None
    audio, aviso = generar_audio(guion)
    if audio and len(audio) > LIMITE_AUDIO_BYTES:
        return None, "El audio quedó demasiado largo, así que se publicó sin voz. Acortá el reporte."
    return audio, aviso


def _cb_preview():
    rep = _leer_formulario()
    error = validar_reporte(rep)
    if error:
        _avisar("warning", error)
        return
    guion = guion_audio(rep)
    audio, aviso = generar_audio(guion)
    if not audio:
        _avisar("error", aviso or "No se pudo generar el audio.")
        return
    st.session_state["rep_preview"] = {"guion": guion, "audio": audio}
    _avisar("success", "Vista previa lista: escuchala abajo. Si no la tocás, se usa tal cual al publicar.")


def _metadata_actualidad_desde_sesion() -> dict:
    """Obtiene los metadatos ya precargados por el JSON del Prompt Maestro."""
    ss = st.session_state
    return {
        "tipo_fuente": ss.get("rep_act_tipo_fuente", "periodistica"),
        "alcance": ss.get("rep_act_alcance", "empresa"),
        "estado": ss.get("rep_act_estado", "en_verificacion"),
        "importancia": ss.get("rep_act_importancia", "media"),
        "paises": ss.get("rep_act_paises", ""),
        "sectores": ss.get("rep_act_sectores", ""),
        "fuente_nombre": ss.get("rep_act_fuente_nombre", ""),
        "fuente_titulo": ss.get("rep_act_fuente_titulo", ""),
        "fuente_url": ss.get("rep_act_fuente_url", ""),
        "resumen_actual": ss.get("rep_act_resumen", ""),
        "nota_fuente": ss.get("rep_act_nota_fuente", ""),
        "nota_interna": ss.get("rep_act_nota_interna", ""),
        "activos_extra": ss.get("rep_act_activos_extra", ""),
        "fuentes_adicionales": (
            (ss.get("rep_ia_resultado") or {}).get("sources", []) or []
        )[1:3],
        "idioma": "es-AR",
    }


def _huella_reporte(reporte: dict) -> str:
    contenido = json.dumps(reporte, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

def _cb_publicar():
    ss = st.session_state
    rep = _leer_formulario()
    error = validar_reporte(rep)
    if error:
        _avisar("warning", error)
        return
    if not reportes_configurados():
        _avisar("error", "Falta conectar la base de datos (SUPABASE_URL y SUPABASE_KEY en Secrets).")
        return

    editando = ss.get("rep_editando")
    quiere_audio = bool(ss.get("rep_audio", True))
    crear_actualidad = bool(ss.get("rep_crear_actualidad_al_publicar", False)) and not editando

    if editando:
        audio, aviso_audio = (None, None)
        if quiere_audio:
            audio, aviso_audio = _audio_para(rep)
        ok, mensaje = actualizar_reporte(editando, rep, audio, cambiar_audio=audio is not None)
        if not ok:
            _avisar("error", mensaje)
            return
        if quiere_audio and audio is None:
            _avisar("warning", f"Cambios guardados, pero el audio NO se regeneró (queda el anterior). {aviso_audio}")
        else:
            _avisar("success", "Cambios guardados" + (" y audio regenerado." if audio else "."))
        _limpiar_formulario()
        return

    # Si el reporte ya se guardó pero falló el paso editorial, reintentar utiliza
    # el mismo ID: no vuelve a insertar el reporte ni genera un segundo audio.
    reporte_id = str(ss.get("rep_reporte_id_pendiente", "")).strip()
    if reporte_id:
        huella_guardada = str(ss.get("rep_reporte_fingerprint_pendiente", ""))
        if huella_guardada and huella_guardada != _huella_reporte(rep):
            _avisar(
                "warning",
                f"El reporte #{reporte_id} ya fue publicado. No cambies su contenido mientras se completa el vínculo con Actualidad. "
                "Restaurá los campos originales y volvé a intentar.",
            )
            return

    metadata = _metadata_actualidad_desde_sesion() if crear_actualidad else {}
    if crear_actualidad:
        _, errores_editoriales = armar_payload_desde_reporte(rep, metadata)
        _, errores_fuentes = armar_fuentes_adicionales(metadata.get("fuentes_adicionales", []))
        errores_editoriales.extend(errores_fuentes)
        if errores_editoriales:
            _avisar(
                "warning",
                "No publiqué el reporte porque faltan datos para crear el borrador de Actualidad: "
                + " ".join(errores_editoriales),
            )
            return

    if not reporte_id:
        audio, aviso_audio = (None, None)
        if quiere_audio:
            audio, aviso_audio = _audio_para(rep)
        ok, mensaje, id_nuevo = publicar_reporte_con_id(rep, audio)
        if not ok:
            _avisar("error", mensaje)
            return
        if not id_nuevo:
            _avisar("warning", mensaje or "El reporte se guardó, pero no recibimos su ID.")
            return
        reporte_id = str(id_nuevo)
        ss["rep_reporte_id_pendiente"] = reporte_id
        ss["rep_reporte_fingerprint_pendiente"] = _huella_reporte(rep)
        ss["rep_reporte_audio_guardado"] = bool(audio)
        ss["rep_reporte_audio_aviso"] = aviso_audio

    if crear_actualidad:
        # RPC atómica e idempotente: crea acontecimiento + fuente + historial +
        # tickers y lo vincula al reporte existente en una sola transacción.
        with st.spinner("Creando el acontecimiento y vinculándolo al reporte..."):
            ok_evento, resultado_evento = guardar_borrador_y_vincular_reporte(
                rep, metadata, reporte_id
            )
        if not ok_evento:
            _avisar(
                "warning",
                f"El reporte #{reporte_id} ya está publicado, pero no se pudo completar el borrador de Actualidad. "
                f"No vuelvas a publicar el reporte: corregí el dato indicado y volvé a pulsar el botón. Detalle: {resultado_evento}",
            )
            return
        evento_id = ""
        if isinstance(resultado_evento, dict):
            evento_id = str(resultado_evento.get("evento_id", ""))
        elif isinstance(resultado_evento, list) and resultado_evento and isinstance(resultado_evento[0], dict):
            evento_id = str(resultado_evento[0].get("evento_id", ""))
        mensaje_final = (
            f"Reporte #{reporte_id} publicado con audio si estaba habilitado. "
            f"Borrador de Actualidad creado y vinculado{f' (evento {evento_id})' if evento_id else ''}. "
            "Queda pendiente de revisión editorial antes de publicarse en el sitio."
        )
        audio_aviso = ss.get("rep_reporte_audio_aviso")
        if quiere_audio and not ss.get("rep_reporte_audio_guardado") and audio_aviso:
            mensaje_final += f" El reporte quedó sin audio: {audio_aviso}"
        _avisar("success", mensaje_final)
        _limpiar_formulario()
        return

    audio_guardado = bool(ss.get("rep_reporte_audio_guardado", quiere_audio))
    audio_aviso = ss.get("rep_reporte_audio_aviso")
    if quiere_audio and not audio_guardado and audio_aviso:
        _avisar("warning", f"Reporte #{reporte_id} publicado SIN audio. {audio_aviso}")
    else:
        _avisar("success", f"Reporte #{reporte_id} publicado" + (" con audio." if audio_guardado else " (sin audio)."))
    _limpiar_formulario()


def _cb_editar(reporte_id: int):
    rep = leer_reporte(reporte_id)
    if not rep:
        _avisar("error", "No pude leer ese reporte.")
        return
    ss = st.session_state
    ss["rep_editando"] = reporte_id
    ss["rep_pegado"] = ""
    ss["rep_ticker"] = rep.get("ticker", "")
    ss["rep_titular"] = rep.get("titular", "")
    ss["rep_contexto"] = rep.get("contexto", "")
    ss["rep_efecto"] = rep.get("efecto", "")
    ss["rep_justif"] = rep.get("justificacion", "")
    ss["rep_fuente"] = rep.get("fuente", "")
    ss["rep_impacto"] = rep.get("impacto", "neutral")
    ss["rep_audio"] = True
    ss.pop("rep_preview", None)
    _avisar("success", f"Reporte #{reporte_id} cargado en el formulario. Cambiá lo que quieras y guardá.")


def _cb_cancelar_edicion():
    _limpiar_formulario()
    _avisar("success", "Edición cancelada.")


def _cb_eliminar(reporte_id: int):
    ok, mensaje = eliminar_reporte(reporte_id)
    _avisar("success" if ok else "error", mensaje)


def _cb_traer_short():
    ss = st.session_state
    video_id = extraer_video_id(ss.get("sh_url", ""))
    if not video_id:
        _avisar("warning", "No reconocí ese link de YouTube.")
        return
    titulo, canal, error = datos_oembed(video_id)
    if titulo:
        ss["sh_titulo"] = titulo
    if canal:
        ss["sh_canal"] = canal
    _avisar("warning" if error else "success", error or "Datos traídos de YouTube. Revisalos y agregá.")


def _cb_agregar_short():
    ss = st.session_state
    video_id = extraer_video_id(ss.get("sh_url", ""))
    ok, mensaje = agregar_short(video_id, str(ss.get("sh_titulo", "")), str(ss.get("sh_canal", "")),
                                str(ss.get("sh_nota", "")))
    _avisar("success" if ok else "warning", mensaje)
    if ok:
        for clave in CAMPOS_SHORT:
            ss[clave] = ""


def _cb_eliminar_short(short_id: int):
    ok, mensaje = eliminar_short(short_id)
    _avisar("success" if ok else "error", mensaje)


# ================================================================ pantallas

def _pidio_cocina() -> bool:
    """True si la dirección de la app termina en ?cocina=1."""
    try:
        return bool(st.query_params.get("cocina"))
    except Exception:
        return False


def acceso_cocina():
    """Formulario de clave del operador.

    Solo aparece si la dirección termina en ?cocina=1 y todavía no hay sesión abierta,
    así los visitantes no ven nada de esto.
    """
    if st.session_state.get("cocina_ok", False) or not _pidio_cocina():
        return
    with st.expander("🔧 Acceso de operador", expanded=True):
        with st.form("cocina_form"):
            clave = st.text_input("Clave de acceso", type="password", key="cocina_clave")
            entrar = st.form_submit_button("Entrar")
        if entrar:
            if clave_correcta(clave):
                st.session_state["cocina_ok"] = True
                st.rerun()
            else:
                st.error("Clave incorrecta, o falta cargar COCINA_CLAVE en los Secrets.")



def _seccion_actualidad_desde_reporte():
    """Permite ajustar metadatos; el borrador se crea al publicar el reporte."""
    ss = st.session_state
    if ss.get("rep_editando"):
        st.info("La vinculación automática está disponible al publicar un reporte nuevo, no al editar uno existente.")
        return

    ss.setdefault("rep_act_fuente_nombre", limpiar_nombre_fuente(ss.get("rep_fuente", "")))
    ss.setdefault("rep_act_fuente_titulo", "")
    ss.setdefault("rep_act_fuente_url", extraer_url_fuente(ss.get("rep_fuente", "")))
    ss.setdefault("rep_act_tipo_fuente", "periodistica")
    ss.setdefault("rep_act_alcance", "empresa")
    ss.setdefault("rep_act_estado", "en_verificacion")
    ss.setdefault("rep_act_importancia", "media")
    ss.setdefault("rep_act_paises", "")
    ss.setdefault("rep_act_sectores", "")
    ss.setdefault("rep_act_activos_extra", "")
    ss.setdefault("rep_act_nota_fuente", "")
    ss.setdefault("rep_act_nota_interna", "")
    ss.setdefault("rep_act_resumen", "")
    if "rep_crear_actualidad_al_publicar" not in ss:
        ss["rep_crear_actualidad_al_publicar"] = bool(ss.get("rep_ia_resultado"))

    pendiente = bool(ss.get("rep_reporte_id_pendiente"))
    if pendiente:
        ss["rep_crear_actualidad_al_publicar"] = True

    with st.expander("🗞️ Vincular este reporte con Actualidad", expanded=bool(ss.get("rep_ia_resultado")) or pendiente):
        st.caption(
            "Al publicar el reporte, NAPO creará automáticamente un borrador editorial con el mismo ticker, "
            "titular, contexto, efecto, fuentes y activos relacionados. No se publicará en Actualidad hasta tu revisión."
        )
        st.checkbox(
            "Crear borrador en Actualidad y vincularlo al reporte",
            key="rep_crear_actualidad_al_publicar",
            disabled=pendiente,
        )
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox(
                "Alcance editorial", ["empresa", "instrumento", "sector", "pais", "global"],
                format_func=lambda x: {
                    "empresa": "Empresa", "instrumento": "Instrumento", "sector": "Sector",
                    "pais": "País / mercado", "global": "Global",
                }[x], key="rep_act_alcance",
            )
            st.selectbox(
                "Estado inicial", ["en_verificacion", "reportada", "confirmada", "en_desarrollo"],
                format_func=lambda x: {
                    "en_verificacion": "En verificación", "reportada": "Reportada",
                    "confirmada": "Confirmada", "en_desarrollo": "En desarrollo",
                }[x], key="rep_act_estado",
            )
            st.selectbox(
                "Importancia", ["alta", "media", "baja"],
                format_func=lambda x: {"alta": "Alta", "media": "Media", "baja": "Baja"}[x],
                key="rep_act_importancia",
            )
            st.text_input("Países / mercados (separados por coma)", key="rep_act_paises")
            st.text_input("Sectores (separados por coma)", key="rep_act_sectores")
        with col2:
            st.selectbox(
                "Tipo de fuente", ["primaria", "periodistica", "mercado"],
                format_func=lambda x: {"primaria": "Primaria", "periodistica": "Periodística", "mercado": "Mercado"}[x],
                key="rep_act_tipo_fuente",
            )
            st.text_input("Medio / entidad de la fuente", key="rep_act_fuente_nombre")
            st.text_input("Título original de la publicación", key="rep_act_fuente_titulo")
            st.text_input("URL original de la fuente", key="rep_act_fuente_url", placeholder="https://...")
        st.text_area("Resumen periodístico para Actualidad", key="rep_act_resumen", height=105)
        st.text_area("Fuentes de contraste / nota de verificación", key="rep_act_nota_fuente", height=75)
        st.text_area(
            "Otros activos relacionados (opcional; uno por línea)",
            key="rep_act_activos_extra", height=70,
            placeholder="SPY | benchmark | media | Índice de referencia, no impacto directo.",
        )
        st.text_area("Nota editorial interna (no se publica)", key="rep_act_nota_interna", height=60)
        if pendiente:
            st.warning(
                f"El reporte #{ss.get('rep_reporte_id_pendiente')} ya se guardó. "
                "Al pulsar el botón principal se reintentará únicamente crear/vincular el borrador; no se duplicará el reporte."
            )


def _texto_prompt_desde_ia(resultado: dict) -> str:
    """Convierte el JSON de IA al formato histórico que ya interpreta NAPO."""
    rep = resultado.get("report", {})
    fuentes = resultado.get("sources", []) or []
    partes = [f"**Ticker: ${resultado.get('ticker', '')}**", ""]
    partes.append(f"1. **Titular al hueso:** {rep.get('titular', '')}")
    partes.append("2. **Contexto clave:**")
    partes.extend(f"   * {x}" for x in rep.get("contexto", []) or [])
    partes.append("3. **Efecto directo en la acción:**")
    partes.extend(f"   * {x}" for x in rep.get("efecto", []) or [])
    partes.append(f"4. **Impacto potencial:** {rep.get('impacto', 'neutral')} — {rep.get('justificacion', '')}")
    partes.append("5. **Fuente oficial:**")
    for fuente in fuentes:
        partes.append(
            f"   * {fuente.get('nombre', '')} — {fuente.get('titulo', '')} — "
            f"{fuente.get('fecha_publicacion', 'fecha no informada')} — {fuente.get('url', '')}"
        )
    return "\n".join(partes).strip()


def _aplicar_reporte_ia(resultado: dict):
    """Carga el resultado validado en los mismos campos que usa el flujo manual."""
    ss = st.session_state
    rep = resultado.get("report", {})
    editorial = resultado.get("editorial", {})
    fuentes = resultado.get("sources", []) or []
    principal = fuentes[0] if fuentes else {}

    ss["rep_pegado"] = _texto_prompt_desde_ia(resultado)
    ss["rep_ticker"] = str(resultado.get("ticker", "")).strip()
    ss["rep_titular"] = str(rep.get("titular", "")).strip()
    ss["rep_contexto"] = "\n".join(str(x).strip() for x in rep.get("contexto", []) if str(x).strip())
    ss["rep_efecto"] = "\n".join(str(x).strip() for x in rep.get("efecto", []) if str(x).strip())
    ss["rep_impacto"] = rep.get("impacto", "neutral") if rep.get("impacto") in IMPACTOS else "neutral"
    ss["rep_justif"] = str(rep.get("justificacion", "")).strip()
    if principal:
        ss["rep_fuente"] = (
            f"{principal.get('nombre', '')} — {principal.get('titulo', '')} — "
            f"{principal.get('fecha_publicacion', 'fecha no informada')} — {principal.get('url', '')}"
        )[:1200]
        ss["rep_act_fuente_nombre"] = principal.get("nombre", "")
        ss["rep_act_fuente_titulo"] = principal.get("titulo", "")
        ss["rep_act_fuente_url"] = principal.get("url", "")
        ss["rep_act_tipo_fuente"] = principal.get("tipo", "periodistica")
    ss["rep_act_alcance"] = editorial.get("alcance", "empresa")
    # Todo resultado de IA entra como borrador en verificación. El operador decide si elevarlo.
    ss["rep_act_estado"] = "en_verificacion"
    ss["rep_act_importancia"] = editorial.get("importancia", "media")
    ss["rep_act_paises"] = ", ".join(editorial.get("paises", []) or [])
    ss["rep_act_sectores"] = ", ".join(editorial.get("sectores", []) or [])
    ss["rep_act_resumen"] = str(editorial.get("resumen", "") or "").strip()

    relacionados = []
    for activo in editorial.get("related_assets", []) or []:
        ticker = str(activo.get("ticker", "")).strip().upper()
        tipo = activo.get("tipo_vinculo", "directo")
        relevancia = activo.get("relevancia", "media")
        justificacion = str(activo.get("justificacion", "")).strip()
        if ticker and justificacion:
            relacionados.append(f"{ticker} | {tipo} | {relevancia} | {justificacion}")
    ss["rep_act_activos_extra"] = "\n".join(relacionados)

    notas = []
    for fuente in fuentes[1:]:
        notas.append(
            f"Fuente de contraste consultada: {fuente.get('nombre', '')} — "
            f"{fuente.get('titulo', '')} — {fuente.get('fecha_publicacion', 'fecha no informada')} — "
            f"{fuente.get('url', '')}"
        )
    if resultado.get("conflictos"):
        notas.extend("Discrepancia entre fuentes: " + x for x in resultado["conflictos"])
    ss["rep_act_nota_fuente"] = "\n".join(notas)[:1800]
    prefijo_revision = (
        "BORRADOR GENERADO EN MODO MANUAL CON ASISTENTE EXTERNO. "
        if resultado.get("modo_manual")
        else "BORRADOR GENERADO CON IA. "
    )
    ss["rep_act_nota_interna"] = (
        prefijo_revision + "REQUIERE REVISIÓN HUMANA. "
        + " ".join(resultado.get("limitaciones", []) or [])
    )[:1800]
    ss["rep_ia_resultado"] = resultado
    ss["rep_crear_actualidad_al_publicar"] = True
    ss.pop("rep_actualidad_ultimo_fingerprint", None)
    ss.pop("rep_actualidad_ultimo_id", None)
    ss.pop("rep_preview", None)


def _seccion_generador_ia():
    """Puente gratuito/manual: prepara un prompt y procesa la respuesta pegada por el operador."""
    ss = st.session_state
    with st.expander("🧠 Prompt Maestro NAPO (modo gratuito, sin API)", expanded=True):
        st.caption(
            "NAPO prepara una consigna completa para usar en ChatGPT. Después pegás aquí la respuesta JSON. "
            "No consume API ni requiere OPENAI_API_KEY; la investigación se realiza en el chat externo."
        )
        with st.form("rep_ia_investigar_form", clear_on_submit=False):
            consulta = st.text_input(
                "Ticker, empresa o tema para investigar",
                key="rep_ia_consulta",
                placeholder="NVDA, NVIDIA, YPF, Mercado Libre, tasas de la Fed...",
            )
            url = st.text_input(
                "URL de una noticia o comunicado (opcional)",
                key="rep_ia_url",
                placeholder="https://...",
            )
            ventana = st.selectbox(
                "Ventana de actualidad",
                options=[1, 3, 7],
                index=1,
                format_func=lambda x: {1: "Últimas 24 horas", 3: "Últimos 3 días", 7: "Últimos 7 días"}[x],
                key="rep_ia_ventana",
            )
            extra = st.text_area(
                "Contexto o pregunta adicional (opcional)",
                key="rep_ia_contexto_extra",
                height=70,
                placeholder="Ej.: priorizá resultados trimestrales y comunicados oficiales.",
            )
            preparar = st.form_submit_button(
                "📋 Preparar investigación gratuita",
                type="primary",
                use_container_width=True,
            )

        if preparar:
            if ss.get("rep_reporte_id_pendiente"):
                st.warning("Primero completá el vínculo pendiente del reporte ya publicado antes de iniciar otra investigación.")
                return
            ok_prompt, prompt_o_error = preparar_prompt_manual(
                consulta=consulta,
                url=url,
                ventana_dias=ventana,
                contexto_adicional=extra,
            )
            if not ok_prompt:
                st.error(str(prompt_o_error))
            else:
                ss["rep_ia_prompt_manual"] = prompt_o_error
                ss["rep_ia_respuesta_manual"] = ""
                ss.pop("rep_ia_resultado", None)
                st.success("Investigación preparada. Copiá el prompt y pegalo en ChatGPT.")

        prompt_manual = ss.get("rep_ia_prompt_manual", "")
        if prompt_manual:
            st.markdown("**Paso 1. Copiá esta consigna**")
            st.caption("Usá este chat de ChatGPT u otro chat con búsqueda web habilitada. No necesitás crear una API key.")
            st.code(prompt_manual, language="text")
            st.markdown("**Paso 2. Pegá la respuesta JSON completa**")
            st.caption(
                "La respuesta debe contener el JSON solicitado, idealmente sin texto adicional. "
                "La app validará estructura y enlaces, pero no puede certificar automáticamente que el contenido de cada fuente sea verdadero."
            )
            with st.form("rep_ia_respuesta_manual_form", clear_on_submit=False):
                st.text_area(
                    "Respuesta del asistente",
                    key="rep_ia_respuesta_manual",
                    height=260,
                    placeholder='Pegá acá el JSON completo devuelto por ChatGPT...',
                )
                procesar = st.form_submit_button(
                    "✅ Validar respuesta y completar reporte",
                    type="primary",
                    use_container_width=True,
                )
            if procesar:
                if ss.get("rep_reporte_id_pendiente"):
                    st.warning("Primero completá el vínculo pendiente del reporte ya publicado antes de procesar otra investigación.")
                    return
                ok_manual, resultado_manual = parsear_respuesta_manual(ss.get("rep_ia_respuesta_manual", ""))
                if not ok_manual:
                    st.error(str(resultado_manual))
                else:
                    _aplicar_reporte_ia(resultado_manual)
                    ss["rep_msg"] = (
                        "success",
                        "Respuesta procesada. Revisá manualmente todas las fuentes y el contenido antes de guardar o publicar."
                    )
                    st.rerun()

        resultado_visible = ss.get("rep_ia_resultado")
        if resultado_visible:
            st.success(
                f"Borrador preparado para {resultado_visible.get('ticker', '')} · "
                f"{len(resultado_visible.get('sources', []) or [])} fuente(s) declarada(s) · "
                f"{resultado_visible.get('model', 'Modo manual')} ."
            )
            st.warning(
                "Modo gratuito/manual: NAPO validó el formato del JSON y los enlaces, pero no comprobó automáticamente "
                "la autenticidad de las fuentes ni que respalden cada afirmación. Abrí las fuentes originales antes de publicar."
            )
            with st.expander("Ver fuentes declaradas en la respuesta", expanded=True):
                for indice, fuente in enumerate(resultado_visible.get("sources", []) or [], start=1):
                    st.markdown(
                        f"**{indice}. {fuente.get('nombre', 'Fuente')}** — "
                        f"{fuente.get('fecha_publicacion', 'fecha no informada')}"
                    )
                    st.caption(fuente.get("titulo", ""))
                    if fuente.get("url", "").startswith(("https://", "http://")):
                        st.link_button("Abrir fuente original", fuente["url"], key=f"rep_ia_fuente_{indice}")
                    st.caption("Respalda: " + str(fuente.get("respalda", "")))
            if resultado_visible.get("conflictos"):
                st.warning("Discrepancias declaradas: " + " | ".join(resultado_visible["conflictos"]))
            if resultado_visible.get("limitaciones"):
                st.info("Limitaciones declaradas: " + " | ".join(resultado_visible["limitaciones"]))
            st.caption(
                "El reporte queda precargado en el formulario tradicional. Revisá los datos, generá el audio y, "
                "si corresponde, creá el borrador de Actualidad desde el apartado siguiente."
            )


def _seccion_reportes():
    ss = st.session_state
    editando = ss.get("rep_editando")
    if not editando:
        _seccion_generador_ia()
    if editando:
        st.info(f"Estás editando el reporte #{editando}.")
        st.button("Cancelar edición", key="rep_btn_cancelar", on_click=_cb_cancelar_edicion)
    else:
        st.caption("También podés seguir usando el método manual pegando una respuesta del Prompt Maestro.")
        st.text_area(
            "Respuesta manual del Prompt Maestro (opcional)",
            key="rep_pegado", height=170,
            placeholder="**Ticker: $PAMP**\n1. **Titular al hueso:** ...\n2. **Contexto clave:** ...",
        )
        st.button("🪄 Rellenar los campos", key="rep_btn_rellenar", on_click=_cb_rellenar)

    col_ticker, col_titular = st.columns([1, 3])
    with col_ticker:
        st.text_input("Ticker", key="rep_ticker", placeholder="PAMP")
    with col_titular:
        st.text_input("Titular", key="rep_titular")
    st.text_area("Contexto (una viñeta por línea)", key="rep_contexto", height=110)
    st.text_area("Efecto en la acción (una viñeta por línea)", key="rep_efecto", height=110)
    col_impacto, col_just = st.columns([1, 3])
    with col_impacto:
        st.selectbox(
            "Impacto", list(IMPACTOS.keys()), key="rep_impacto",
            format_func=lambda v: f"{IMPACTOS[v][0]} {IMPACTOS[v][1]}",
        )
    with col_just:
        st.text_input("Justificación (una línea)", key="rep_justif")
    st.text_input("Fuente", key="rep_fuente")
    _seccion_actualidad_desde_reporte()
    st.checkbox("Regenerar el audio (si no, queda el audio anterior)" if editando
                else "Generar audio con voz argentina", key="rep_audio")

    st.button("🔊 Escuchar vista previa del audio", key="rep_btn_preview", on_click=_cb_preview)
    previa = ss.get("rep_preview")
    if previa and previa.get("audio"):
        st.audio(previa["audio"], format="audio/mpeg")
        vigente = guion_audio(_leer_formulario()) == previa.get("guion")
        st.caption("✅ Esta vista previa corresponde al texto actual: es la que se va a publicar." if vigente
                   else "⚠️ El texto cambió desde esta vista previa. Generá una nueva para escuchar lo que se va a publicar.")

    if editando:
        etiqueta_publicar = "💾 Guardar cambios"
    elif ss.get("rep_reporte_id_pendiente"):
        etiqueta_publicar = "🔁 Reintentar creación/vínculo en Actualidad"
    elif ss.get("rep_crear_actualidad_al_publicar"):
        etiqueta_publicar = "📤 Publicar reporte + crear borrador en Actualidad"
    else:
        etiqueta_publicar = "📤 Publicar reporte"
    st.button(etiqueta_publicar, key="rep_btn_publicar", on_click=_cb_publicar)

    st.divider()
    st.markdown("**Últimos reportes publicados**")
    recientes = listar_reportes(10) if reportes_configurados() else None
    if recientes:
        for rep in recientes:
            col_texto, col_editar, col_borrar = st.columns([6, 1, 1])
            with col_texto:
                st.caption(f"#{rep['id']} · {rep['ticker']} · {str(rep['titular'])[:80]}")
            with col_editar:
                st.button("✏️", key=f"edit_{rep['id']}", on_click=_cb_editar, args=(rep["id"],), help="Editar")
            with col_borrar:
                st.button("🗑", key=f"del_{rep['id']}", on_click=_cb_eliminar, args=(rep["id"],), help="Eliminar")
    else:
        st.caption("Todavía no hay reportes publicados.")


def _seccion_shorts():
    ss = st.session_state
    st.markdown("Pegá el link de un Short de una fuente confiable. La página muestra **los 5 más recientes**.")
    st.text_input("Link del Short (YouTube)", key="sh_url", placeholder="https://www.youtube.com/shorts/...")
    st.button("🔎 Traer título y canal", key="sh_btn_traer", on_click=_cb_traer_short)
    col_titulo, col_canal = st.columns([3, 2])
    with col_titulo:
        st.text_input("Título", key="sh_titulo")
    with col_canal:
        st.text_input("Canal", key="sh_canal")
    st.text_input("Nota (opcional, una línea)", key="sh_nota")
    canal = str(ss.get("sh_canal", "")).strip()
    if canal and not canal_confiable(canal):
        st.warning(f"«{canal}» no está en la lista de fuentes de confianza (se edita en napo_config.py). "
                   "Verificá la fuente antes de publicar.")
    st.button("➕ Agregar a Noticias", key="sh_btn_agregar", on_click=_cb_agregar_short)

    st.divider()
    st.markdown("**Noticias cargadas**")
    lista = listar_shorts(10) if reportes_configurados() else None
    if lista:
        for posicion, corto in enumerate(lista):
            col_texto, col_borrar = st.columns([8, 1])
            with col_texto:
                estado = "visible" if posicion < 5 else "oculta (más antigua)"
                st.caption(f"{posicion + 1}. {corto['titulo']} — {corto['canal']} · {estado}")
            with col_borrar:
                st.button("🗑", key=f"delsh_{corto['id']}", on_click=_cb_eliminar_short, args=(corto["id"],))
    else:
        st.caption("Todavía no hay Shorts cargados (o falta crear la tabla: supabase/migracion_v8.sql).")


def _seccion_uso():
    filas = leer_eventos(30) if reportes_configurados() else None
    if filas is None:
        st.warning("No pude leer las mediciones. ¿Ya corriste supabase/migracion_v8.sql en Supabase?")
        return
    r = resumir(filas)
    kpi_grid([
        dict(label="Visitas hoy", value=str(r["visitas_hoy"]), sub="sesiones únicas"),
        dict(label="Últimos 7 días", value=str(r["visitas_7d"]), sub="sesiones únicas"),
        dict(label="Últimos 30 días", value=str(r["visitas_30d"]), sub="sesiones únicas"),
        dict(label="Audios escuchados", value=str(r["audios"]), sub="últimos 30 días"),
        dict(label="Usaron Mi cartera", value=str(r["usaron_cartera"]), sub="sesiones"),
        dict(label="Shorts reproducidos", value=str(r["shorts"]), sub="en la página"),
    ])
    st.markdown("**Visitas por día (últimos 14 días)**")
    st.bar_chart(r["por_dia"], color=KLEIN_BLUE)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Reportes más escuchados**")
        for nombre, cantidad in r["audios_top"] or [("Todavía sin datos", 0)]:
            st.caption(f"{nombre}" + (f" · {cantidad}" if cantidad else ""))
    with col_b:
        st.markdown("**Activos más consultados**")
        for nombre, cantidad in r["tickers_top"] or [("Todavía sin datos", 0)]:
            st.caption(f"{nombre}" + (f" · {cantidad}" if cantidad else ""))
    st.caption("Medición anónima: no se guarda ningún dato personal. Tu propia sesión de operador no cuenta. "
               "El activo por defecto de cada visita no se cuenta; solo los cambios que hace la gente.")


def _seccion_sistema():
    st.markdown("**Versiones instaladas**")
    lineas = []
    for paquete in ("streamlit", "pandas", "numpy", "requests", "plotly", "yfinance", "edge-tts", "gTTS"):
        try:
            lineas.append(f"{paquete}=={metadata.version(paquete)}")
        except Exception:
            lineas.append(f"# {paquete}: no encontrada")
    st.code("\n".join(lineas), language="text")
    st.caption("Para fijarlas: copiá este bloque y pegalo como contenido de requirements.txt en GitHub "
               "(reemplazando lo que hay). Así una versión nueva de una librería no rompe la app de un día para otro.")

    st.divider()
    st.markdown("**Tickers sin datos**")
    precios = cargar_precios()
    if precios is None:
        st.caption("No hay datos de mercado en este momento: no se puede revisar.")
    else:
        sin_datos = tickers_sin_datos(precios, ACTIVOS)
        if sin_datos:
            st.warning(f"{len(sin_datos)} de {len(ACTIVOS)} no trajeron datos: {', '.join(sin_datos)}. "
                       "Si es siempre el mismo, corregí su símbolo o sacalo de napo_config.py.")
        else:
            st.success(f"Los {len(ACTIVOS)} tickers traen datos.")

    st.divider()
    st.markdown("**Base de datos**")
    if not reportes_configurados():
        st.warning("Sin configurar: faltan SUPABASE_URL y SUPABASE_KEY en los Secrets.")
    elif st.button("Probar conexión con las tablas", key="sis_probar"):
        for tabla in ("reportes", "eventos", "noticias_shorts"):
            ok, resultado = basedatos.pedir(tabla, "GET", params={"select": "id", "limit": "1"})
            if ok:
                st.success(f"{tabla}: funciona")
            else:
                st.error(f"{tabla}: {resultado}")


def panel_operador():
    """Panel del operador. Solo se dibuja con la sesión abierta."""
    if not st.session_state.get("cocina_ok", False):
        return
    ss = st.session_state
    ss.setdefault("rep_impacto", "neutral")
    ss.setdefault("rep_audio", True)
    # Streamlit descarta el valor de los campos que no se dibujan en una corrida (por ejemplo al cambiar de
    # sección). Reasignarlos al principio los conserva, así no se pierde lo que se estaba escribiendo.
    for clave in CAMPOS_REPORTE + CAMPOS_SHORT + CAMPOS_ACTUALIDAD + ("rep_impacto", "rep_audio"):
        if clave in ss:
            ss[clave] = ss[clave]

    with st.expander("🔧 La Cocina", expanded=True):
        mensaje = ss.pop("rep_msg", None)
        if mensaje:
            getattr(st, mensaje[0])(mensaje[1])
        if not reportes_configurados():
            st.warning("La base de datos todavía no está conectada: cargá SUPABASE_URL y SUPABASE_KEY en los Secrets.")
        seccion = st.radio("Sección", SECCIONES, horizontal=True, key="cocina_seccion")
        if seccion == SECCIONES[0]:
            _seccion_reportes()
        elif seccion == SECCIONES[1]:
            _seccion_shorts()
        elif seccion == SECCIONES[2]:
            seccion_actualidad_admin()
        elif seccion == SECCIONES[3]:
            _seccion_uso()
        else:
            _seccion_sistema()

        st.divider()
        st.caption("Base de datos: " + ("conectada ✅" if reportes_configurados() else "sin configurar ⚠️")
                   + f" · Hora del servidor: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        if st.button("Cerrar sesión de La Cocina", key="cocina_salir"):
            ss["cocina_ok"] = False
            st.rerun()
