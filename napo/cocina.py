"""La Cocina: back-office del operador.

- La barra lateral pide una clave (Secret COCINA_CLAVE).
- Con la clave, en la página principal aparece el panel para publicar reportes:
  pegás la respuesta del prompt maestro, se completan los campos, revisás y publicás.
"""

import hmac
from datetime import datetime

import streamlit as st

from .reportes import (
    IMPACTOS, LIMITE_AUDIO_BYTES, eliminar_reporte, generar_audio, guion_audio, listar_reportes,
    normalizar_ticker, parsear_reporte, publicar_reporte, reportes_configurados, validar_reporte,
)
from .secretos import secreto

CAMPOS_TEXTO = ("rep_pegado", "rep_ticker", "rep_titular", "rep_contexto", "rep_efecto", "rep_justif", "rep_fuente")


def clave_correcta(ingresada: str) -> bool:
    """Compara la clave ingresada con la guardada en Secrets (COCINA_CLAVE)."""
    esperada = secreto("COCINA_CLAVE")
    if not esperada:
        return False
    return hmac.compare_digest(ingresada.encode("utf-8"), esperada.encode("utf-8"))


# ---------------------------------------------------------------- callbacks del formulario
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
    for clave in CAMPOS_TEXTO:
        st.session_state[clave] = ""
    st.session_state["rep_impacto"] = "neutral"


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
    if datos["impacto"]:
        ss["rep_impacto"] = datos["impacto"]
    faltan = [nombre for nombre, valor in (("ticker", ss["rep_ticker"]), ("impacto", datos["impacto"])) if not valor]
    _avisar("success", "Campos completados. Revisalos antes de publicar."
                       + (f" Falta completar: {', '.join(faltan)}." if faltan else ""))


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

    quiere_audio = bool(ss.get("rep_audio", True))
    audio, aviso_audio = None, None
    if quiere_audio:
        audio, aviso_audio = generar_audio(guion_audio(rep))
        if audio and len(audio) > LIMITE_AUDIO_BYTES:
            audio, aviso_audio = None, "El audio quedó demasiado largo, así que se publicó sin voz. Acortá el reporte."

    ok, mensaje = publicar_reporte(rep, audio)
    if not ok:
        _avisar("error", mensaje)
        return
    if audio or not quiere_audio:
        _avisar("success", "Reporte publicado" + (" con audio." if audio else " (sin audio)."))
    else:
        _avisar("warning", f"Reporte publicado SIN audio. {aviso_audio}")
    _limpiar_formulario()


def _cb_eliminar(reporte_id: int):
    ok, mensaje = eliminar_reporte(reporte_id)
    _avisar("success" if ok else "error", mensaje)


# ---------------------------------------------------------------- pantallas

def render_cocina():
    """Barra lateral: acceso con clave y estado del sistema."""
    with st.sidebar:
        st.markdown('<div class="napo-kitchen-title">🔧 La Cocina</div>', unsafe_allow_html=True)
        st.caption("Back-office interno · uso exclusivo del operador")
        st.divider()

        if not st.session_state.get("cocina_ok", False):
            st.markdown("**Acceso restringido**")
            clave = st.text_input("Clave de acceso", type="password", key="cocina_clave")
            if st.button("Entrar", key="cocina_entrar"):
                if clave_correcta(clave):
                    st.session_state["cocina_ok"] = True
                    st.rerun()
                else:
                    st.error("Clave incorrecta o no configurada.")
        else:
            st.markdown("**Sesión de operador activa**")
            st.caption("El formulario para publicar reportes está en la página principal, arriba.")
            st.divider()
            st.markdown("**Estado del sistema**")
            st.caption("Base de datos: " + ("conectada ✅" if reportes_configurados() else "sin configurar ⚠️"))
            st.caption(f"Última sincronización: {datetime.now().strftime('%d/%m/%Y %H:%M')} hs")
            st.caption("Fuentes: DolarApi, ArgentinaDatos y Yahoo Finance")

            if st.button("Cerrar sesión de La Cocina"):
                st.session_state["cocina_ok"] = False
                st.rerun()


def panel_operador():
    """Panel para publicar y administrar reportes. Solo se dibuja con la sesión de operador abierta."""
    if not st.session_state.get("cocina_ok", False):
        return
    st.session_state.setdefault("rep_impacto", "neutral")
    st.session_state.setdefault("rep_audio", True)

    with st.expander("🔧 La Cocina · Publicar reporte", expanded=True):
        mensaje = st.session_state.pop("rep_msg", None)
        if mensaje:
            getattr(st, mensaje[0])(mensaje[1])
        if not reportes_configurados():
            st.warning("La base de datos todavía no está conectada: cargá SUPABASE_URL y SUPABASE_KEY en los Secrets.")

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
        st.checkbox("Generar audio con voz argentina", key="rep_audio")
        st.button("📤 Publicar reporte", key="rep_btn_publicar", on_click=_cb_publicar)

        st.divider()
        st.markdown("**Últimos reportes publicados**")
        recientes = listar_reportes(10) if reportes_configurados() else None
        if recientes:
            for rep in recientes:
                col_texto, col_borrar = st.columns([6, 1])
                with col_texto:
                    st.caption(f"{rep['ticker']} · {str(rep['titular'])[:90]}")
                with col_borrar:
                    st.button("🗑", key=f"del_{rep['id']}", on_click=_cb_eliminar, args=(rep["id"],),
                              help="Eliminar este reporte")
        else:
            st.caption("Todavía no hay reportes publicados.")
