"""Prototipo del flujo editorial de actualidad de NAPO.

Esta primera versión usa acontecimientos ficticios de demostración. No consulta APIs,
no persiste datos en Supabase y no debe presentarse como noticias reales.
El modelo de datos está pensado para reemplazar la demo por registros persistidos
sin cambiar la experiencia de lectura.
"""

from datetime import datetime, timedelta, timezone
import copy
import html
from typing import Any

import streamlit as st

TZ_ARG = timezone(timedelta(hours=-3))

ESTADOS = {
    "en_verificacion": ("En verificación", "warning"),
    "reportada": ("Reportada", "info"),
    "confirmada": ("Confirmada", "success"),
    "en_desarrollo": ("En desarrollo", "info"),
    "actualizada": ("Actualizada", "success"),
    "desmentida": ("Desmentida", "error"),
    "retirada": ("Retirada", "error"),
}

ALCANCES = {
    "global": "Global",
    "pais": "País / mercado",
    "sector": "Sector",
    "empresa": "Empresa",
    "instrumento": "Instrumento",
}

FILTROS = ["Todo el mercado", "Mis activos", "Global", "Argentina", "Tecnología"]


def _ahora() -> datetime:
    return datetime.now(TZ_ARG)


def _hace(minutos: int) -> str:
    return (_ahora() - timedelta(minutes=minutos)).isoformat(timespec="minutes")


def _demo_eventos() -> list[dict[str, Any]]:
    """Datos sintéticos para probar el diseño. Nunca representan noticias reales."""
    return [
        {
            "id": "demo-global-001",
            "title": "DEMO · El mercado revisa sus expectativas sobre las tasas",
            "summary": (
                "Ejemplo ficticio de un acontecimiento macroeconómico con alcance global. "
                "La interpretación inicial cambia a medida que aparece nueva información."
            ),
            "scope": "global",
            "countries": ["Estados Unidos"],
            "sectors": ["Macro", "Tecnología", "Finanzas"],
            "related_tickers": ["SPY", "QQQ", "NVDA", "AAPL"],
            "status": "actualizada",
            "importance": "alta",
            "created_at": _hace(260),
            "updated_at": _hace(12),
            "sources": [
                {"id": "src-demo-001a", "type": "Primaria", "name": "Comunicado oficial de ejemplo", "url": None},
                {"id": "src-demo-001b", "type": "Periodística", "name": "Medio financiero de ejemplo", "url": None},
                {"id": "src-demo-001c", "type": "Mercado", "name": "Proveedor de datos de ejemplo", "url": None},
            ],
            "updates": [
                {
                    "id": "upd-demo-001c", "at": _hace(12), "status": "actualizada",
                    "title": "La lectura del escenario se actualiza",
                    "detail": "En este ejemplo, un dato posterior modifica la interpretación inicial. La actualización queda arriba del historial.",
                    "source_ids": ["src-demo-001a", "src-demo-001b"],
                },
                {
                    "id": "upd-demo-001b", "at": _hace(95), "status": "en_desarrollo",
                    "title": "Aparece información complementaria",
                    "detail": "Se agrega contexto de mercado, pero todavía no alcanza para cerrar la interpretación.",
                    "source_ids": ["src-demo-001b", "src-demo-001c"],
                },
                {
                    "id": "upd-demo-001a", "at": _hace(260), "status": "reportada",
                    "title": "Se publica la información inicial",
                    "detail": "Primera versión del acontecimiento. Se conserva para que el lector pueda reconstruir cómo evolucionó.",
                    "source_ids": ["src-demo-001b"],
                },
            ],
        },
        {
            "id": "demo-company-002",
            "title": "DEMO · Una tecnológica presenta sus resultados trimestrales",
            "summary": (
                "Ejemplo ficticio de una noticia específica de empresa. El acontecimiento se vincula "
                "únicamente con el activo indicado; compartir sector no implica recibir esta noticia."
            ),
            "scope": "empresa",
            "countries": ["Estados Unidos"],
            "sectors": ["Tecnología", "Semiconductores"],
            "related_tickers": ["NVDA"],
            "status": "confirmada",
            "importance": "alta",
            "created_at": _hace(155),
            "updated_at": _hace(34),
            "sources": [
                {"id": "src-demo-002a", "type": "Primaria", "name": "Presentación de resultados de ejemplo", "url": None},
                {"id": "src-demo-002b", "type": "Periodística", "name": "Cobertura especializada de ejemplo", "url": None},
            ],
            "updates": [
                {
                    "id": "upd-demo-002b", "at": _hace(34), "status": "confirmada",
                    "title": "Se publica la presentación oficial",
                    "detail": "La fuente primaria permite comprobar las cifras citadas en la noticia. Este contenido es ficticio y solo demuestra el flujo.",
                    "source_ids": ["src-demo-002a"],
                },
                {
                    "id": "upd-demo-002a", "at": _hace(155), "status": "reportada",
                    "title": "Se anticipa la publicación de resultados",
                    "detail": "Primera cobertura periodística del acontecimiento.",
                    "source_ids": ["src-demo-002b"],
                },
            ],
        },
        {
            "id": "demo-argentina-003",
            "title": "DEMO · Una empresa energética informa una novedad operativa",
            "summary": (
                "Ejemplo ficticio de noticia de alcance corporativo y local. La ficha identifica "
                "el activo relacionado y evita extenderla automáticamente a otras compañías del sector."
            ),
            "scope": "empresa",
            "countries": ["Argentina"],
            "sectors": ["Energía"],
            "related_tickers": ["YPF"],
            "status": "en_verificacion",
            "importance": "media",
            "created_at": _hace(70),
            "updated_at": _hace(70),
            "sources": [
                {"id": "src-demo-003a", "type": "Primaria", "name": "Comunicación corporativa de ejemplo", "url": None},
                {"id": "src-demo-003b", "type": "Periodística", "name": "Medio argentino de ejemplo", "url": None},
            ],
            "updates": [
                {
                    "id": "upd-demo-003a", "at": _hace(70), "status": "en_verificacion",
                    "title": "Se detecta una publicación inicial",
                    "detail": "El equipo editorial todavía debe contrastar el dato con documentación primaria antes de elevar su estado.",
                    "source_ids": ["src-demo-003b"],
                }
            ],
        },
        {
            "id": "demo-rumor-004",
            "title": "DEMO · Una versión sobre una operación corporativa es desmentida",
            "summary": (
                "Ejemplo ficticio de cómo se conserva una información inicial y se agrega una respuesta "
                "posterior. No describe un acontecimiento real ni se refiere a una empresa real."
            ),
            "scope": "empresa",
            "countries": ["Mercado internacional"],
            "sectors": ["Finanzas"],
            "related_tickers": [],
            "status": "desmentida",
            "importance": "media",
            "created_at": _hace(390),
            "updated_at": _hace(45),
            "sources": [
                {"id": "src-demo-004a", "type": "Periodística", "name": "Publicación inicial de ejemplo", "url": None},
                {"id": "src-demo-004b", "type": "Primaria", "name": "Respuesta oficial de ejemplo", "url": None},
            ],
            "updates": [
                {
                    "id": "upd-demo-004c", "at": _hace(45), "status": "desmentida",
                    "title": "La compañía desmiente la versión",
                    "detail": "La respuesta oficial contradice la información inicial. El acontecimiento queda marcado como desmentido, sin borrar su historial.",
                    "source_ids": ["src-demo-004b"],
                },
                {
                    "id": "upd-demo-004b", "at": _hace(180), "status": "en_desarrollo",
                    "title": "La información sigue sin confirmación",
                    "detail": "Se agregan publicaciones, pero no aparece una confirmación primaria.",
                    "source_ids": ["src-demo-004a"],
                },
                {
                    "id": "upd-demo-004a", "at": _hace(390), "status": "reportada",
                    "title": "Se publica una versión inicial",
                    "detail": "El dato se presenta como una versión atribuida a una fuente, no como un hecho confirmado.",
                    "source_ids": ["src-demo-004a"],
                },
            ],
        },
    ]


def _parse_fecha(valor: str | None) -> datetime:
    if not valor:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=TZ_ARG)
        return fecha
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def ordenar_eventos(eventos: list[dict]) -> list[dict]:
    """Ordena acontecimientos por su última actualización, del más nuevo al más viejo."""
    return sorted(eventos or [], key=lambda e: _parse_fecha(e.get("updated_at")), reverse=True)


def filtrar_eventos(
    eventos: list[dict], filtro: str = "Todo el mercado", tickers_seguidos: list[str] | None = None,
    busqueda: str = "",
) -> list[dict]:
    """Aplica filtros editoriales; Mis activos exige vínculo explícito con un ticker."""
    seguidos = {str(t).upper() for t in (tickers_seguidos or [])}
    consulta = str(busqueda or "").strip().casefold()
    salida = []
    for evento in ordenar_eventos(eventos):
        tickers = {str(t).upper() for t in evento.get("related_tickers", [])}
        if filtro == "Mis activos" and not (tickers & seguidos):
            continue
        if filtro == "Global" and evento.get("scope") != "global":
            continue
        if filtro == "Argentina" and "Argentina" not in evento.get("countries", []):
            continue
        if filtro == "Tecnología" and "Tecnología" not in evento.get("sectors", []):
            continue
        if consulta:
            texto = " ".join([
                str(evento.get("title", "")), str(evento.get("summary", "")),
                " ".join(evento.get("related_tickers", [])),
                " ".join(evento.get("countries", [])), " ".join(evento.get("sectors", [])),
            ]).casefold()
            if consulta not in texto:
                continue
        salida.append(evento)
    return salida


def validar_evento(evento: dict) -> list[str]:
    """Validación básica del contrato editorial que luego usará la persistencia real."""
    errores = []
    for campo in ("id", "title", "summary", "scope", "status", "created_at", "updated_at"):
        if not str(evento.get(campo, "")).strip():
            errores.append(f"Falta {campo}.")
    if evento.get("scope") not in ALCANCES:
        errores.append("Alcance inválido.")
    if evento.get("status") not in ESTADOS:
        errores.append("Estado editorial inválido.")
    if not isinstance(evento.get("updates"), list) or not evento.get("updates"):
        errores.append("El acontecimiento necesita al menos una actualización.")
    if not isinstance(evento.get("sources"), list) or not evento.get("sources"):
        errores.append("El acontecimiento necesita al menos una fuente registrada.")
    ids_fuente = {s.get("id") for s in evento.get("sources", [])}
    for actualizacion in evento.get("updates", []):
        if actualizacion.get("status") not in ESTADOS:
            errores.append("Una actualización tiene un estado editorial inválido.")
        if not actualizacion.get("id") or not actualizacion.get("at"):
            errores.append("Cada actualización necesita ID y fecha.")
        if not set(actualizacion.get("source_ids", [])) <= ids_fuente:
            errores.append("Una actualización referencia una fuente inexistente.")
    return errores


def aplicar_actualizacion_demo(evento: dict, estado: str, titulo: str, detalle: str, ahora: str | None = None) -> dict:
    """Agrega una actualización ficticia y devuelve una copia del acontecimiento."""
    if estado not in ESTADOS:
        raise ValueError("Estado editorial inválido.")
    titulo = str(titulo or "").strip()
    detalle = str(detalle or "").strip()
    if not titulo or not detalle:
        raise ValueError("La actualización necesita título y detalle.")

    actualizado = copy.deepcopy(evento)
    fecha = ahora or _ahora().isoformat(timespec="minutes")
    update_id = f"demo-update-{actualizado.get('id', 'evento')}-{len(actualizado.get('updates', [])) + 1}"
    actualizado.setdefault("updates", []).append({
        "id": update_id,
        "at": fecha,
        "status": estado,
        "title": titulo,
        "detail": detalle,
        "source_ids": [],
        "demo_note": "Simulación de interfaz; no es una fuente real.",
    })
    actualizado["status"] = estado
    actualizado["updated_at"] = fecha
    return actualizado


def _cb_actualizacion_demo(event_id: str, estado: str, titulo: str, detalle: str):
    """Callback de Streamlit: modifica únicamente los datos de demostración de la sesión."""
    eventos = st.session_state.get("actualidad_demo_eventos", [])
    nuevos = []
    for evento in eventos:
        if evento.get("id") == event_id:
            try:
                evento = aplicar_actualizacion_demo(evento, estado, titulo, detalle)
                st.session_state["actualidad_demo_mensaje"] = "Actualización simulada agregada. El acontecimiento subió al inicio del flujo."
                st.session_state["actualidad_demo_error"] = False
            except ValueError as error:
                st.session_state["actualidad_demo_mensaje"] = str(error)
                st.session_state["actualidad_demo_error"] = True
        nuevos.append(evento)
    st.session_state["actualidad_demo_eventos"] = nuevos


def _simulador_actualizacion(eventos: list[dict]):
    """Herramienta temporal para probar cómo cambia una noticia durante el día."""
    with st.expander("🧪 Probar una actualización en tiempo real (solo demo)", expanded=False):
        st.caption(
            "Podés simular una confirmación, actualización o desmentida. "
            "El cambio vive solamente en tu sesión y no se guarda en Supabase."
        )
        por_id = {e["id"]: e for e in eventos}
        opciones = list(por_id)
        if not opciones:
            return
        elegido = st.selectbox(
            "Acontecimiento", opciones,
            format_func=lambda clave: por_id[clave].get("title", clave),
            key="actualidad_demo_evento_sel",
        )
        estado = st.selectbox(
            "Nuevo estado editorial", list(ESTADOS),
            format_func=lambda clave: ESTADOS[clave][0],
            key="actualidad_demo_estado_sel",
        )
        titulo = st.text_input("Título de la actualización", key="actualidad_demo_titulo")
        detalle = st.text_area("Qué cambió", key="actualidad_demo_detalle")
        st.button(
            "Agregar actualización simulada",
            key="actualidad_demo_agregar",
            on_click=_cb_actualizacion_demo,
            args=(elegido, estado, titulo, detalle),
        )
        mensaje = st.session_state.pop("actualidad_demo_mensaje", None)
        es_error = st.session_state.pop("actualidad_demo_error", False)
        if mensaje:
            st.error(mensaje) if es_error else st.success(mensaje)



def _fecha_hora(valor: str) -> str:
    fecha = _parse_fecha(valor)
    if fecha.year == datetime.min.year:
        return "Fecha sin informar"
    return fecha.strftime("%d/%m · %H:%M")


def _estado_texto(estado: str) -> str:
    etiqueta, color = ESTADOS.get(estado, ("Estado no definido", "secondary"))
    colores_markdown = {"warning": "orange", "info": "blue", "success": "green", "error": "red", "secondary": "gray"}
    return f":{colores_markdown.get(color, 'gray')}[{etiqueta}]"


def _render_fuentes(evento: dict):
    fuentes = evento.get("sources", [])
    if not fuentes:
        st.caption("No hay fuentes registradas.")
        return
    for fuente in fuentes:
        st.markdown(f"**{html.escape(str(fuente.get('type', 'Fuente')))}:** {html.escape(str(fuente.get('name', 'Sin nombre')))}")
        url = fuente.get("url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            st.markdown(f"[Consultar publicación original]({url})")


def _render_evento(evento: dict):
    with st.container(border=True):
        col_titulo, col_estado = st.columns([4, 1.5])
        with col_titulo:
            st.markdown(f"#### {html.escape(str(evento.get('title', 'Sin título')))}")
        with col_estado:
            st.markdown(_estado_texto(evento.get("status", "")))
        actualizaciones = sorted(evento.get("updates", []), key=lambda u: _parse_fecha(u.get("at")), reverse=True)
        st.caption(
            f"Última actualización: {_fecha_hora(evento.get('updated_at'))} · "
            f"Publicado inicialmente: {_fecha_hora(evento.get('created_at'))} · "
            f"{len(actualizaciones)} actualización(es)"
        )
        st.write(evento.get("summary", ""))

        alcance = ALCANCES.get(evento.get("scope"), "Sin clasificar")
        paises = ", ".join(evento.get("countries", [])) or "Sin país asignado"
        sectores = ", ".join(evento.get("sectors", [])) or "Sin sector asignado"
        tickers = ", ".join(evento.get("related_tickers", [])) or "Sin activos específicos vinculados"
        st.caption(f"Alcance: {alcance} · Mercado: {paises} · Sector: {sectores}")
        st.caption(f"Activos vinculados: {tickers}")

        with st.expander(f"Ver evolución del acontecimiento ({len(actualizaciones)} actualizaciones)", expanded=False):
            for actualizacion in actualizaciones:
                st.markdown(
                    f"**{_fecha_hora(actualizacion.get('at'))} · "
                    f"{html.escape(str(actualizacion.get('title', 'Actualización')))}**"
                )
                st.markdown(_estado_texto(actualizacion.get("status", "")))
                st.write(actualizacion.get("detail", ""))
                if actualizacion.get("demo_note"):
                    st.caption(actualizacion["demo_note"])
                if actualizacion is not actualizaciones[-1]:
                    st.divider()
        with st.expander("Fuentes registradas", expanded=False):
            _render_fuentes(evento)


def tab_actualidad(tickers_seguidos: list[str] | None = None):
    """Prototipo visual del flujo de noticias y evolución editorial de NAPO."""
    st.markdown("## 🗞️ Actualidad financiera")
    st.caption("Un flujo de acontecimientos: lo último arriba y el historial debajo de cada noticia.")
    st.warning(
        "MODO DEMOSTRACIÓN · Las noticias, fuentes, fechas y actualizaciones que ves son ficticias. "
        "Esta pantalla todavía no consulta proveedores ni publica información real."
    )

    if "actualidad_demo_eventos" not in st.session_state:
        st.session_state["actualidad_demo_eventos"] = copy.deepcopy(_demo_eventos())
    eventos = st.session_state["actualidad_demo_eventos"]
    tickers = [str(t).upper() for t in (tickers_seguidos or [])]

    _simulador_actualizacion(eventos)

    c_filtro, c_busqueda = st.columns([1.2, 1])
    with c_filtro:
        filtro = st.selectbox("Filtrar", FILTROS, key="actualidad_filtro")
    with c_busqueda:
        busqueda = st.text_input("Buscar en actualidad", placeholder="Empresa, ticker, tema...", key="actualidad_busqueda")

    filtrados = filtrar_eventos(eventos, filtro, tickers, busqueda)
    total_actualizaciones = sum(len(e.get("updates", [])) for e in filtrados)
    k1, k2, k3 = st.columns(3)
    k1.metric("Acontecimientos", len(filtrados))
    k2.metric("Actualizaciones", total_actualizaciones)
    k3.metric("Activos que seguís", len(tickers))

    st.markdown("### Últimas actualizaciones")
    if filtro == "Mis activos" and not tickers:
        st.info("Todavía no seguís activos. Agregalos en la sección «Mis activos» para personalizar este flujo.")
        return
    if not filtrados:
        st.info("No hay acontecimientos de demostración que coincidan con este filtro.")
        return

    for evento in filtrados:
        _render_evento(evento)

    st.caption(
        "Criterio del prototipo: los acontecimientos se ordenan por su última actualización. "
        "Dentro de cada acontecimiento, la actualización más reciente aparece primero. "
        "Las relaciones con activos son explícitas; compartir sector no alcanza para vincular una noticia."
    )
