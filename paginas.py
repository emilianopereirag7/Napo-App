"""Contenido de cada sección de la página: panel cambiario y las solapas."""

import pandas as pd
import streamlit as st

from .componentes import boton_link_html, cassette, estado_vacio, kpi_grid, reporte_html, section_title
from .config import ACTIVOS, DOLARES_PANEL, KLEIN_BLUE, RANGOS
from .contenido import DISCLAIMER_REPORTES, GLOSARIO, LINKS_OFICIALES
from .datos import recortar_rango, resumen_serie, serie_activo
from .formatos import fmt_fecha_corta, fmt_numero, fmt_pct, fmt_pesos, fmt_var, parse_iso
from .graficos import grafico_heatmap, grafico_precio
from .reportes import obtener_audio, reportes_configurados


def panel_cambiario(dolares, riesgo_pais):
    """Tarjetas de dólares y riesgo país."""
    section_title("Panel Cambiario", "💵")

    if dolares is None and riesgo_pais is None:
        estado_vacio("Cotizaciones no disponibles", "No pudimos traer las cotizaciones en este momento. Probá recargar la página en unos minutos.", "💵")

    items_cambio = []
    for etiqueta, casa in DOLARES_PANEL:
        cot = (dolares or {}).get(casa)
        if cot and cot.get("venta") is not None:
            sub = f"Compra {fmt_pesos(cot['compra'])}" if cot.get("compra") is not None else None
            items_cambio.append(dict(label=etiqueta, value=fmt_pesos(cot["venta"]), sub=sub))
        else:
            items_cambio.append(dict(label=etiqueta, value="—", sub="Sin datos por ahora"))
    if riesgo_pais:
        items_cambio.append(dict(label="Riesgo País", value=f"{int(round(riesgo_pais['valor']))} pb",
                                 sub=f"Dato del {fmt_fecha_corta(riesgo_pais['fecha'])}"))
    else:
        items_cambio.append(dict(label="Riesgo País", value="—", sub="Sin datos por ahora"))
    if not (dolares is None and riesgo_pais is None):
        kpi_grid(items_cambio)

    horas = [parse_iso(c.get("fechaActualizacion")) for c in (dolares or {}).values()]
    horas = [h for h in horas if h is not None]
    actualizado = max(horas).strftime("%d/%m %H:%M") if horas else "s/d"
    st.caption(
        f"Cotizaciones de venta · Fuentes: DolarApi y ArgentinaDatos · "
        f"Última actualización de dólares: {actualizado} (hora Argentina)"
    )


def _marcar_audio(clave: str):
    st.session_state[clave] = True


def _mostrar_mas(cantidad: int):
    st.session_state["reportes_visibles"] = cantidad + 5


def render_reportes(lista, prefijo: str):
    """Dibuja reportes con su botón de audio. El audio se baja recién cuando alguien lo pide."""
    for rep in lista:
        st.markdown(reporte_html(rep), unsafe_allow_html=True)
        if not rep.get("tiene_audio"):
            continue
        clave = f"audio_{prefijo}_{rep['id']}"
        if st.session_state.get(clave):
            audio = obtener_audio(rep["id"])
            if audio:
                cassette(f"▸ {rep['ticker']} · REPORTE EN AUDIO", "SIDE A", "VOZ AR", "NAPO FM")
                st.audio(audio, format="audio/mpeg")
            else:
                st.caption("No pudimos cargar el audio de este reporte. Probá de nuevo en unos minutos.")
        else:
            st.button("🎧 Escuchar este reporte", key=f"btn_{clave}", on_click=_marcar_audio, args=(clave,))


def tab_explorador(precios, reportes):
    """Solapa 1: radar de activos con ficha técnica y gráfico."""
    section_title("Radar de Activos", "📡")

    col_search, _ = st.columns([1, 2])
    with col_search:
        ticker_sel = st.selectbox("Buscar ticker", list(ACTIVOS.keys()), index=0)

    info = ACTIVOS[ticker_sel]
    link_oficial = LINKS_OFICIALES.get(ticker_sel)
    df_activo = serie_activo(precios, info["yahoo"])
    resumen = resumen_serie(df_activo)

    with st.container(border=True):
        top_a, top_b = st.columns([3, 1])
        with top_a:
            st.markdown(f"### {ticker_sel} · {info['nombre']}")
            st.caption(f"Sector: {info['sector']}")
        with top_b:
            if link_oficial:
                url_oficial, etiqueta_oficial = link_oficial
                st.markdown(
                    f'<div style="text-align:right; padding-top:6px;">'
                    f'<a class="napo-ir-link" href="{url_oficial}" target="_blank" rel="noopener noreferrer">'
                    f"{etiqueta_oficial} ↗</a></div>",
                    unsafe_allow_html=True,
                )

        if resumen is None:
            estado_vacio("Sin precios por ahora", "No pudimos traer los precios de este activo. Probá recargar en unos minutos.", "📉")
        else:
            kpi_grid([
                dict(label="Último precio (ARS)", value=fmt_pesos(resumen["ultimo"])),
                dict(label="Variación diaria", value=fmt_pct(resumen["var"]),
                     delta="vs. cierre anterior", positive=resumen["var"] >= 0),
                dict(label="Volumen", value=fmt_numero(resumen["volumen"], 0), sub="último día operado"),
                dict(label="Rango 1 año",
                     value=f"{fmt_numero(resumen['min_1a'], 0)}–{fmt_numero(resumen['max_1a'], 0)}",
                     sub="mín–máx de cierres"),
            ])

            st.markdown("<br>", unsafe_allow_html=True)
            ctrl1, ctrl2 = st.columns([1, 1])
            with ctrl1:
                rango = st.radio("Rango", list(RANGOS.keys()), index=1, horizontal=True, key="rango_grafico")
            with ctrl2:
                tipo = st.radio("Tipo de gráfico", ["Línea", "Velas"], horizontal=True, key="tipo_grafico")

            df_rec = recortar_rango(df_activo, rango)
            try:
                st.plotly_chart(grafico_precio(df_rec, tipo), config={"displayModeBar": False})
            except Exception:
                st.line_chart(df_rec["Close"], color=KLEIN_BLUE, height=320)
            st.caption(
                f"Fuente: Yahoo Finance (puede tener demora) · Último dato: "
                f"{resumen['fecha'].strftime('%d/%m/%Y')}"
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**🎯 Último reporte táctico**")
        propios = [r for r in (reportes or []) if r.get("ticker") == ticker_sel]
        if propios:
            render_reportes(propios[:1], "exp")
        else:
            st.caption("Todavía no hay reportes de este activo.")


def tab_ranking(precios):
    """Solapa 2: heatmap y rankings del día."""
    section_title("Heatmap de Rendimiento Diario", "🔥")

    filas = []
    for tk, datos_tk in ACTIVOS.items():
        r = resumen_serie(serie_activo(precios, datos_tk["yahoo"]))
        if r:
            filas.append({
                "Ticker": tk,
                "Último": round(r["ultimo"], 2),
                "Variación (%)": round(r["var"], 2),
                "Volumen": int(r["volumen"]),
                "Amplitud (%)": round(r["amplitud"], 2),
            })
    df_rend = pd.DataFrame(filas)

    if df_rend.empty:
        estado_vacio("Mercado sin datos por ahora", "No pudimos traer los precios del mercado. Probá recargar en unos minutos.", "📉")
    else:
        df_rend = df_rend.sort_values("Variación (%)", ascending=False).reset_index(drop=True)

        try:
            st.plotly_chart(grafico_heatmap(df_rend), config={"displayModeBar": False})
        except Exception:
            st.dataframe(df_rend.set_index("Ticker"))
        st.caption("Variación diaria vs. cierre anterior · Celdas del mismo tamaño (no representan capitalización) · "
                   "Fuente: Yahoo Finance, con posible demora.")

        rank_col1, rank_col2, rank_col3 = st.columns(3)

        with rank_col1:
            section_title("Top Ganadores", "🟢")
            for _, row in df_rend.head(3).iterrows():
                clase = "napo-badge-up" if row["Variación (%)"] >= 0 else "napo-badge-down"
                st.markdown(
                    f'<div class="napo-card" style="margin-bottom:8px;">'
                    f'<b>{row["Ticker"]}</b> '
                    f'<span class="{clase}">{fmt_var(row["Variación (%)"])}</span></div>',
                    unsafe_allow_html=True,
                )

        with rank_col2:
            section_title("Top Perdedores", "🔴")
            for _, row in df_rend.sort_values("Variación (%)").head(3).iterrows():
                clase = "napo-badge-up" if row["Variación (%)"] >= 0 else "napo-badge-down"
                st.markdown(
                    f'<div class="napo-card" style="margin-bottom:8px;">'
                    f'<b>{row["Ticker"]}</b> '
                    f'<span class="{clase}">{fmt_var(row["Variación (%)"])}</span></div>',
                    unsafe_allow_html=True,
                )

        with rank_col3:
            section_title("Mayor Amplitud del Día", "⚡")
            for _, row in df_rend.sort_values("Amplitud (%)", ascending=False).head(3).iterrows():
                st.markdown(
                    f'<div class="napo-card" style="margin-bottom:8px;">'
                    f'<b>{row["Ticker"]}</b> '
                    f'<span class="napo-badge-neutral">rango {fmt_pct(row["Amplitud (%)"])}</span></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Tabla completa**")
        st.dataframe(df_rend[["Ticker", "Último", "Variación (%)", "Volumen"]].set_index("Ticker"))


def tab_reportes(reportes):
    """Solapa 3: reportes tácticos con audio."""
    section_title("Reportes tácticos", "📰")
    if reportes is None:
        if reportes_configurados():
            estado_vacio("Reportes no disponibles", "No pudimos cargar los reportes ahora. Probá recargar en unos minutos.", "📰")
        else:
            estado_vacio("Próximamente", "Estamos preparando los primeros reportes.", "📰")
        return
    if not reportes:
        estado_vacio("Todavía no hay reportes", "Publicamos los primeros muy pronto.", "📰")
        return

    tickers = ["Todos"] + sorted({r["ticker"] for r in reportes})
    col_filtro, _ = st.columns([1, 2])
    with col_filtro:
        filtro = st.selectbox("Filtrar por activo", tickers, key="filtro_reportes")
    visibles = [r for r in reportes if filtro == "Todos" or r["ticker"] == filtro]
    cantidad = st.session_state.get("reportes_visibles", 5)

    render_reportes(visibles[:cantidad], "tab")
    if len(visibles) > cantidad:
        st.button("Mostrar más reportes", key="mas_reportes", on_click=_mostrar_mas, args=(cantidad,))
    st.caption(DISCLAIMER_REPORTES)


def tab_academia():
    """Solapa 4: glosario."""
    section_title("Academia NAPO · Glosario Táctico", "🎓")

    glosario = GLOSARIO

    for termino, definicion in glosario.items():
        with st.expander(f"📘 {termino}"):
            st.write(definicion)


def tab_feedback(url: str):
    """Solapa 5: link al formulario de opinión (solo si hay FEEDBACK_URL configurado)."""
    section_title("Ayudanos a mejorar NAPO", "💬")
    boton = boton_link_html("Dejar mi opinión ↗", url)
    st.markdown(
        '<div class="napo-card"><div class="napo-card-label">Versión de prueba</div>'
        '<div style="color:var(--text); font-size:15px; line-height:1.5;">Contanos qué te sirvió, qué te sobra y '
        f'qué te falta. Lleva dos minutos y nos ayuda a decidir qué construir.</div>{boton}</div>',
        unsafe_allow_html=True,
    )
