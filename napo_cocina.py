"""La Cocina: back-office del operador.

Se entra agregando ?cocina=1 a la dirección de la app y escribiendo la clave (Secret COCINA_CLAVE).
Con la sesión abierta aparece, arriba de la página, el panel con cuatro secciones:
reportes (publicar, editar, vista previa del audio), noticias en Shorts, uso y sistema.
"""

import hashlib
import hmac
from datetime import datetime
from importlib import metadata

import streamlit as st

import napo_basedatos as basedatos
from napo_componentes import kpi_grid
from napo_config import ACTIVOS, KLEIN_BLUE
from napo_datos import cargar_precios, tickers_sin_datos
from napo_actualidad_admin import guardar_borrador_desde_reporte, seccion_actualidad_admin
from napo_actualidad_integracion import extraer_url_fuente, limpiar_nombre_fuente
from napo_eventos import leer_eventos, resumir
from napo_reportes import (
    IMPACTOS, LIMITE_AUDIO_BYTES, actualizar_reporte, eliminar_reporte, generar_audio, guion_audio,
    leer_reporte, listar_reportes, normalizar_ticker, parsear_reporte, publicar_reporte,
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
    "rep_act_paises", "rep_act_sectores", "rep_act_activos_extra",
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
    st.session_state["rep_impacto"] = "neutral"
    st.session_state["rep_editando"] = None
    st.session_state.pop("rep_preview", None)


def _cb_rellenar():
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
    audio, aviso_audio = (None, None)
    if quiere_audio:
        audio, aviso_audio = _audio_para(rep)

    if editando:
        ok, mensaje = actualizar_reporte(editando, rep, audio, cambiar_audio=audio is not None)
        if not ok:
            _avisar("error", mensaje)
            return
        if quiere_audio and audio is None:
            _avisar("warning", f"Cambios guardados, pero el audio NO se regeneró (queda el anterior). {aviso_audio}")
        else:
            _avisar("success", "Cambios guardados" + (" y audio regenerado." if audio else "."))
    else:
        ok, mensaje = publicar_reporte(rep, audio)
        if not ok:
            _avisar("error", mensaje)
            return
        if audio or not quiere_audio:
            _avisar("success", "Reporte publicado" + (" con audio." if audio else " (sin audio)."))
        else:
            _avisar("warning", f"Reporte publicado SIN audio. {aviso_audio}")
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
    """Crea un borrador editorial reutilizando los campos del Prompt Maestro.

    No vuelve a pedir titular, contexto, efecto ni ticker: solo pide la metadata
    de fuente/clasificación necesaria para trazabilidad del acontecimiento.
    """
    ss = st.session_state
    if ss.get("rep_editando"):
        st.info("La integración con Actualidad está disponible al crear un reporte nuevo, no al editar uno ya publicado.")
        return

    # Valores por defecto preparados antes de instanciar los widgets.
    ss.setdefault("rep_act_fuente_nombre", limpiar_nombre_fuente(ss.get("rep_fuente", "")))
    ss.setdefault("rep_act_fuente_titulo", "")
    ss.setdefault("rep_act_fuente_url", extraer_url_fuente(ss.get("rep_fuente", "")))
    ss.setdefault("rep_act_tipo_fuente", "periodistica")
    ss.setdefault("rep_act_alcance", "empresa")
    ss.setdefault("rep_act_estado", "reportada")
    ss.setdefault("rep_act_importancia", "media")
    ss.setdefault("rep_act_paises", "")
    ss.setdefault("rep_act_sectores", "")
    ss.setdefault("rep_act_activos_extra", "")
    ss.setdefault("rep_act_nota_fuente", "")
    ss.setdefault("rep_act_nota_interna", "")

    with st.expander("🗞️ Crear también un borrador en Actualidad con este reporte", expanded=False):
        st.caption(
            "Reutiliza ticker, titular, contexto, efecto e impacto del Prompt Maestro. "
            "Solo completás la fuente original y la clasificación editorial. El borrador no se publica automáticamente."
        )
        with st.form("rep_actualidad_desde_prompt_form", clear_on_submit=False):
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
                st.text_input("Nota de verificación de la fuente (opcional)", key="rep_act_nota_fuente")
            st.text_area(
                "Otros activos relacionados (opcional; uno por línea)",
                key="rep_act_activos_extra", height=75,
                placeholder="QQQ | transversal | media | Índice con exposición al activo principal.",
            )
            st.text_area("Nota editorial interna (no se publica)", key="rep_act_nota_interna", height=65)
            guardar_actualidad = st.form_submit_button(
                "📥 Crear borrador en Actualidad", type="primary", use_container_width=True,
            )

        if guardar_actualidad:
            reporte = _leer_formulario()
            metadata = {
                "tipo_fuente": ss.get("rep_act_tipo_fuente"),
                "alcance": ss.get("rep_act_alcance"),
                "estado": ss.get("rep_act_estado"),
                "importancia": ss.get("rep_act_importancia"),
                "paises": ss.get("rep_act_paises", ""),
                "sectores": ss.get("rep_act_sectores", ""),
                "fuente_nombre": ss.get("rep_act_fuente_nombre", ""),
                "fuente_titulo": ss.get("rep_act_fuente_titulo", ""),
                "fuente_url": ss.get("rep_act_fuente_url", ""),
                "nota_fuente": ss.get("rep_act_nota_fuente", ""),
                "nota_interna": ss.get("rep_act_nota_interna", ""),
                "activos_extra": ss.get("rep_act_activos_extra", ""),
                "idioma": "es-AR",
            }
            errores_reporte = validar_reporte(reporte)
            if errores_reporte:
                st.warning(errores_reporte)
            else:
                huella_base = "|".join((reporte["ticker"], reporte["titular"], metadata["fuente_url"].strip()))
                fingerprint = hashlib.sha256(huella_base.encode("utf-8")).hexdigest()
                if ss.get("rep_actualidad_ultimo_fingerprint") == fingerprint:
                    st.info(f"Este reporte ya generó un borrador en esta sesión (ID: {ss.get('rep_actualidad_ultimo_id', 'guardado')}). No lo duplicamos.")
                else:
                    with st.spinner("Creando acontecimiento, fuente e historial inicial en Supabase..."):
                        ok, resultado = guardar_borrador_desde_reporte(reporte, metadata)
                    if ok:
                        evento_id = resultado.get("evento_id") if isinstance(resultado, dict) else ""
                        ss["rep_actualidad_ultimo_fingerprint"] = fingerprint
                        ss["rep_actualidad_ultimo_id"] = evento_id or "guardado"
                        st.success(
                            f"Borrador de Actualidad creado correctamente{f' · ID {evento_id}' if evento_id else ''}. "
                            "Ahora podés publicar el reporte/audio desde el botón habitual."
                        )
                    else:
                        st.error(str(resultado)[:700])


def _seccion_reportes():
    ss = st.session_state
    editando = ss.get("rep_editando")
    if editando:
        st.info(f"Estás editando el reporte #{editando}.")
        st.button("Cancelar edición", key="rep_btn_cancelar", on_click=_cb_cancelar_edicion)
    else:
        st.text_area(
            "Pegá acá la respuesta del prompt maestro",
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

    st.button("💾 Guardar cambios" if editando else "📤 Publicar reporte", key="rep_btn_publicar", on_click=_cb_publicar)

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
