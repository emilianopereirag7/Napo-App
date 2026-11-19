"""Contenido de cada sección de la página: panel cambiario y las solapas."""

import pandas as pd
import streamlit as st
from streamlit import components

from napo_cartera import a_csv, cartera_vacia, composicion, desde_csv, limpiar_cartera, valuar
from napo_componentes import (
    acciones_rapidas_html, boton_link_html, carrusel_shorts_html, cassette, estado_vacio, kpi_grid, lista_activos_html,
    movers_html, reporte_html, saldo_html, saludo_html, section_title, shorts_html, titulo_app,
)
from napo_config import ACTIVOS, DOLARES_PANEL, KLEIN_BLUE, RANGOS
from napo_contenido import DISCLAIMER_CARTERA, DISCLAIMER_REPORTES, GLOSARIO, LINKS_OFICIALES
from napo_datos import cargar_historial, recortar_rango, resumen_serie, serie_activo
from napo_eventos import registrar, registrar_cambio, registrar_una_vez
from napo_formatos import fmt_fecha_corta, fmt_numero, fmt_pct, fmt_pesos, fmt_var, parse_iso
from napo_graficos import grafico_composicion, grafico_heatmap, grafico_precio
from napo_reportes import obtener_audio, reportes_configurados
from napo_shorts import url_video

FILTROS_TIPO = ["Todos", "Acciones", "CEDEARs"]


def _coincide_tipo(tipo: str, filtro: str) -> bool:
    return filtro == "Todos" or (filtro == "Acciones" and tipo == "Acción") or (filtro == "CEDEARs" and tipo == "CEDEAR")


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


def _marcar_audio(clave: str, reporte_id=None, ticker: str = ""):
    st.session_state[clave] = True
    registrar("audio", f"{ticker} #{reporte_id}")


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
            st.button("🎧 Escuchar este reporte", key=f"btn_{clave}", on_click=_marcar_audio, args=(clave, rep["id"], rep["ticker"]))


def tab_explorador(precios, reportes):
    """Solapa 1: radar de activos con ficha técnica y gráfico."""
    section_title("Radar de Activos", "📡")

    col_tipo, col_search, _ = st.columns([2, 3, 1])
    with col_tipo:
        tipo_sel = st.radio("Mostrar", FILTROS_TIPO, horizontal=True, key="exp_tipo")
    opciones = [t for t, a in ACTIVOS.items() if _coincide_tipo(a["tipo"], tipo_sel)]
    with col_search:
        ticker_sel = st.selectbox(
            "Buscar activo", opciones, key=f"exp_ticker_{tipo_sel}",  # un selector por filtro: no saltan entre sí
            index=opciones.index("YPF") if "YPF" in opciones else 0,
            format_func=lambda t: f"{t} · {ACTIVOS[t]['nombre']}",
        )
    if st.session_state.get("_ult_tipo") != tipo_sel:  # cambió el filtro: el activo mostrado cambia solo, no cuenta
        st.session_state["_ult_tipo"] = tipo_sel
        st.session_state["_ult_ticker"] = ticker_sel
    else:
        registrar_cambio("ticker", ticker_sel, "_ult_ticker")

    info = ACTIVOS[ticker_sel]
    link_oficial = LINKS_OFICIALES.get(ticker_sel)
    df_activo = serie_activo(cargar_historial(info["yahoo"]), info["yahoo"])
    if df_activo.empty:  # si falla el historial anual, el mes de cotizaciones alcanza para los números
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
                dict(label="Rango 1 año" if len(df_activo) > 150 else "Rango del último mes",
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


def _filas_mercado(precios, tipo_sel: str = "Todos") -> pd.DataFrame:
    """Una fila por activo con precio, variación, volumen, amplitud y monto operado del último día."""
    filas = []
    for tk, datos_tk in ACTIVOS.items():
        if not _coincide_tipo(datos_tk["tipo"], tipo_sel):
            continue
        r = resumen_serie(serie_activo(precios, datos_tk["yahoo"]))
        if r:
            filas.append({
                "Ticker": tk,
                "Activo": datos_tk["nombre"],
                "Tipo": datos_tk["tipo"],
                "Último": round(r["ultimo"], 2),
                "Variación (%)": round(r["var"], 2),
                "Volumen": int(r["volumen"]),
                "Amplitud (%)": round(r["amplitud"], 2),
                "Monto (M $)": round(r["volumen"] * r["ultimo"] / 1e6),
            })
    return pd.DataFrame(filas)


def _lista_ranking(df: pd.DataFrame, columna: str, ascendente: bool, derecha, con_variacion: bool = True) -> str:
    top = df.sort_values(columna, ascending=ascendente).head(5)
    return lista_activos_html([
        dict(ticker=r["Ticker"], nombre=r["Activo"], detalle=f"{r['Ticker']} · {r['Tipo']}", derecha=derecha(r),
             var=r["Variación (%)"] if con_variacion else None)
        for _, r in top.iterrows()
    ])


def tab_ranking(precios):
    """Solapa 2: heatmap y rankings del día."""
    section_title("Heatmap de Rendimiento Diario", "🔥")
    tipo_sel = st.radio("Mostrar", FILTROS_TIPO, horizontal=True, key="rank_tipo")

    df_rend = _filas_mercado(precios, tipo_sel)
    if df_rend.empty:
        estado_vacio("Mercado sin datos por ahora", "No pudimos traer los precios del mercado. Probá recargar en unos minutos.", "📉")
        return
    df_rend = df_rend.sort_values("Variación (%)", ascending=False).reset_index(drop=True)

    try:
        st.plotly_chart(grafico_heatmap(df_rend), config={"displayModeBar": False})
    except Exception:
        st.dataframe(df_rend.set_index("Ticker"))
    st.caption("Variación diaria vs. cierre anterior · Celdas del mismo tamaño (no representan capitalización) · "
               "Fuente: Yahoo Finance, con posible demora.")

    precio = lambda r: fmt_pesos(r["Último"])
    col1, col2 = st.columns(2)
    with col1:
        section_title("Top Ganadores", "🟢")
        st.markdown(_lista_ranking(df_rend, "Variación (%)", False, precio), unsafe_allow_html=True)
    with col2:
        section_title("Top Perdedores", "🔴")
        st.markdown(_lista_ranking(df_rend, "Variación (%)", True, precio), unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        section_title("Más Operados del Día", "💰")
        st.markdown(_lista_ranking(df_rend, "Monto (M $)", False, lambda r: f"$ {fmt_numero(r['Monto (M $)'], 0)} M"),
                    unsafe_allow_html=True)
    with col4:
        section_title("Mayor Amplitud del Día", "⚡")
        st.markdown(_lista_ranking(df_rend, "Amplitud (%)", False, lambda r: f"rango {fmt_pct(r['Amplitud (%)'])}",
                                   con_variacion=False), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Tabla completa**")
    st.dataframe(df_rend[["Ticker", "Activo", "Último", "Variación (%)", "Volumen", "Monto (M $)"]].set_index("Ticker"))


def _con_signo(valor: float) -> str:
    return ("+" if valor >= 0 else "-") + fmt_pesos(abs(valor))


def _vaciar_cartera():
    ss = st.session_state
    ss["cartera_base"] = cartera_vacia()
    ss["cartera_v"] = ss.get("cartera_v", 0) + 1


def valuar_con_precios(df: pd.DataFrame, precios):
    """Valúa una cartera con el último precio del mercado. Devuelve (tabla_valuada, totales)."""
    mercado = {}
    for t in df["ticker"]:
        r = resumen_serie(serie_activo(precios, ACTIVOS[t]["yahoo"]))
        if r:
            mercado[t] = {"ultimo": r["ultimo"], "previo": r["previo"]}
    return valuar(df, mercado, ACTIVOS)


def _cb_agregar_activo(prefijo: str):
    """Suma un activo a la cartera. Corre como callback: la cartera queda actualizada antes de dibujar la página."""
    ss = st.session_state
    ss.setdefault("cartera_base", cartera_vacia())
    ss.setdefault("cartera_v", 0)
    ticker = ss.get(f"{prefijo}_nuevo_ticker")
    cantidad = float(ss.get(f"{prefijo}_nueva_cantidad") or 0)
    precio = float(ss.get(f"{prefijo}_nuevo_precio") or 0)
    if ticker not in ACTIVOS or cantidad <= 0:
        ss["_toast"] = "⚠️ Ingresá una cantidad mayor a 0."
        return
    fila = pd.DataFrame([{"ticker": ticker, "cantidad": cantidad, "precio_compra": precio if precio > 0 else float("nan")}])
    combinada, avisos = limpiar_cartera(pd.concat([ss["cartera_base"], fila], ignore_index=True), list(ACTIVOS))
    ss["cartera_base"] = combinada
    ss["cartera_avisos"] = avisos
    ss["cartera_v"] += 1
    ss["_toast"] = f"✅ Agregamos {ticker} a tu cartera."


def _form_agregar(prefijo: str):
    """Formulario para sumar un activo (se usa en el Inicio y en Mi cartera)."""
    validos = list(ACTIVOS.keys())
    with st.form(f"{prefijo}_form", clear_on_submit=True):
        col_a, col_b, col_c = st.columns([3, 1, 2])
        with col_a:
            st.selectbox("Activo", validos, key=f"{prefijo}_nuevo_ticker",
                         format_func=lambda t: f"{t} · {ACTIVOS[t]['nombre']}")
        with col_b:
            st.number_input("Cantidad", min_value=0.0, value=0.0, step=1.0, key=f"{prefijo}_nueva_cantidad")
        with col_c:
            st.number_input("Precio de compra (opcional)", min_value=0.0, value=0.0, step=1.0,
                            key=f"{prefijo}_nuevo_precio")
        st.form_submit_button("➕ Agregar a mi cartera", on_click=_cb_agregar_activo, args=(prefijo,))


def tab_cartera(precios, reportes):
    """Solapa 3: «Mi cartera». No se guarda en ningún servidor (se descarga y se vuelve a cargar)."""
    section_title("Mi cartera", "💼")
    st.caption("Tu cartera NO se guarda en nuestros servidores: dura mientras tengas esta página abierta. "
               "Descargala en CSV para volver a cargarla cuando quieras.")
    ss = st.session_state
    ss.setdefault("cartera_base", cartera_vacia())
    ss.setdefault("cartera_v", 0)
    validos = list(ACTIVOS.keys())

    archivo = st.file_uploader("Cargar una cartera guardada (CSV)", type=["csv"], key="cartera_archivo")
    if archivo is not None:
        firma = (archivo.name, archivo.size)
        if ss.get("cartera_firma") != firma:
            ss["cartera_firma"] = firma
            tabla, avisos = desde_csv(archivo.getvalue(), validos)
            ss["cartera_base"] = tabla
            ss["cartera_v"] += 1
            ss["cartera_avisos"] = avisos
    else:
        ss["cartera_firma"] = None
    for aviso in ss.pop("cartera_avisos", []):
        st.warning(aviso)

    _form_agregar("cartera")

    base = ss["cartera_base"]
    if len(base):
        st.markdown("**Mis activos** · podés corregir los números o borrar filas")
        editada = st.data_editor(
            base, num_rows="dynamic", hide_index=True, key=f"cartera_editor_{ss['cartera_v']}",
            column_config={
                "ticker": st.column_config.SelectboxColumn("Activo", options=validos, required=True),
                "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, format="%.2f"),
                "precio_compra": st.column_config.NumberColumn("Precio de compra", min_value=0.0, format="%.2f"),
            },
        )
    else:
        editada = base
    vigente, avisos_limpieza = limpiar_cartera(editada, validos)
    for aviso in avisos_limpieza:
        st.warning(aviso)
    ss["cartera"] = vigente  # lo que se valúa y se descarga (sin pisar la base del editor)

    if vigente.empty:
        estado_vacio("Tu cartera está vacía", "Agregá tu primer activo con el formulario de arriba o cargá un CSV.", "💼")
        st.caption(DISCLAIMER_CARTERA)
        return

    valuada, tot = valuar_con_precios(vigente, precios)
    registrar_una_vez("cartera", "", "_cartera_evento")

    items = [dict(label="Valor de la cartera", value=fmt_pesos(tot["valor_total"]), sub=f"{tot['n_activos']} activo(s)")]
    if pd.notna(tot["var_dia_pct"]):
        items.append(dict(label="Variación del día", value=_con_signo(tot["var_dia"]),
                          delta=fmt_pct(tot["var_dia_pct"]), positive=tot["var_dia"] >= 0))
    if tot["costo_total"]:
        resultado_incompleto = (
            valuada["precio_compra"].isna().any() or valuada["precio"].isna().any()
        )
        items.append(dict(
            label="Resultado parcial" if resultado_incompleto else "Resultado total",
            value=_con_signo(tot["resultado_total"]),
            delta=fmt_pct(tot["resultado_pct"]),
            positive=tot["resultado_total"] >= 0,
            sub=("Excluye posiciones sin costo de compra o sin cotización"
                 if resultado_incompleto else "Según los costos y cotizaciones disponibles"),
        ))
    kpi_grid(items)
    if tot["n_sin_precio"]:
        st.caption(f"{tot['n_sin_precio']} activo(s) sin precio disponible por ahora: no suman al total.")

    tabla = pd.DataFrame({
        "Activo": valuada["ticker"],
        "Cantidad": [fmt_numero(x, 0 if float(x).is_integer() else 2) for x in valuada["cantidad"]],
        "Precio": [fmt_pesos(x) if pd.notna(x) else "—" for x in valuada["precio"]],
        "Valor": [fmt_pesos(x) if pd.notna(x) else "—" for x in valuada["valor"]],
        "Peso": [fmt_pct(x) if pd.notna(x) else "—" for x in valuada["peso"]],
        "Var. día": [fmt_var(x) if pd.notna(x) else "—" for x in valuada["var_dia_pct"]],
        "Resultado": [fmt_var(x) if pd.notna(x) else "—" for x in valuada["resultado_pct"]],
    })
    st.dataframe(tabla, hide_index=True)

    comp = composicion(valuada)
    if not comp.empty:
        st.markdown("**Composición**")
        try:
            st.plotly_chart(grafico_composicion(comp), config={"displayModeBar": False})
        except Exception:
            st.dataframe(comp, hide_index=True)

    col_desc, col_vaciar, _ = st.columns([2, 1, 2])
    with col_desc:
        st.download_button("⬇️ Descargar mi cartera (CSV)", data=a_csv(vigente).encode("utf-8-sig"),
                           file_name="mi_cartera_napo.csv", mime="text/csv", key="cartera_descargar")
    with col_vaciar:
        st.button("Vaciar cartera", key="cartera_vaciar", on_click=_vaciar_cartera)

    propios = [r for r in (reportes or []) if r.get("ticker") in set(vigente["ticker"])]
    if propios:
        section_title("Reportes de tus activos", "📰")
        render_reportes(propios[:3], "cart")
    st.caption(DISCLAIMER_CARTERA)


def tab_noticias(shorts):
    """Solapa 5: las 5 noticias del momento, en Shorts de YouTube de fuentes confiables."""
    section_title("Las 5 noticias del momento, en Shorts", "🎬")
    if shorts is None:
        if reportes_configurados():
            estado_vacio("Noticias no disponibles", "No pudimos cargar las noticias ahora. Probá recargar en unos minutos.", "🎬")
        else:
            estado_vacio("Próximamente", "Estamos eligiendo las primeras noticias.", "🎬")
        return
    if not shorts:
        estado_vacio("Todavía no hay noticias", "Cargamos los primeros Shorts muy pronto.", "🎬")
        return

    st.markdown(shorts_html(shorts[:5]), unsafe_allow_html=True)
    st.caption("Videos de YouTube de medios de confianza, elegidos por el equipo de NAPO. "
               "Tocá una tarjeta para verla en YouTube.")
    visibles = {f"{s['titulo']} — {s['canal']}": s for s in shorts[:5]}
    elegido = st.selectbox("Reproducir acá mismo", ["— Elegí un video —"] + list(visibles), key="short_sel")
    if elegido in visibles:
        corto = visibles[elegido]
        registrar_una_vez("short", corto["video_id"], f"_short_ev_{corto['video_id']}")
        st.video(url_video(corto["video_id"]))
        st.caption("Si el reproductor no carga, abrilo en YouTube desde la tarjeta de arriba.")
    st.caption(DISCLAIMER_REPORTES)


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


def tab_inicio(precios, reportes, shorts, dolares, riesgo_pais):
    """Solapa 1: pantalla de inicio estilo app. En computadora va en una columna centrada; en celular, a todo el ancho."""
    _, centro, _ = st.columns([1, 2.4, 1])
    with centro:
        _contenido_inicio(precios, reportes, shorts, dolares, riesgo_pais)


def _contenido_inicio(precios, reportes, shorts, dolares, riesgo_pais):
    """Saldo, atajos, dólar, movimientos, reporte del día, tus activos y noticias."""
    ss = st.session_state
    vigente = ss.get("cartera")
    valuada, tot = None, None
    if vigente is not None and len(vigente):
        valuada, tot = valuar_con_precios(vigente, precios)

    st.markdown(saludo_html(), unsafe_allow_html=True)
    st.markdown(saldo_html(tot), unsafe_allow_html=True)
    with st.popover("➕ Agregar activo a mi cartera"):
        _form_agregar("inicio")
    components.v1.html(acciones_rapidas_html(), height=112)
    panel_cambiario(dolares, riesgo_pais)

    mercado = _filas_mercado(precios)
    if not mercado.empty:
        liquidos = mercado.sort_values("Monto (M $)", ascending=False).head(25)  # lo más operado...
        movers = liquidos.reindex(liquidos["Variación (%)"].abs().sort_values(ascending=False, kind="mergesort").index).head(5)  # ...que más se mueve
        st.markdown(titulo_app("Lo que más se mueve hoy"), unsafe_allow_html=True)
        st.markdown(movers_html([(r["Ticker"], r["Activo"], r["Variación (%)"]) for _, r in movers.iterrows()]),
                    unsafe_allow_html=True)

    if reportes:
        st.markdown(titulo_app("Reporte del día"), unsafe_allow_html=True)
        render_reportes(reportes[:1], "inicio")

    if valuada is not None:
        st.markdown(titulo_app("Tus activos"), unsafe_allow_html=True)
        filas = []
        for _, r in valuada.head(5).iterrows():
            entero = float(r["cantidad"]).is_integer()
            filas.append(dict(
                ticker=r["ticker"], nombre=r["nombre"] or r["ticker"],
                detalle=f"{fmt_numero(r['cantidad'], 0 if entero else 2)} × " + (fmt_pesos(r["precio"]) if pd.notna(r["precio"]) else "—"),
                derecha=fmt_pesos(r["valor"]) if pd.notna(r["valor"]) else "—", var=r["var_dia_pct"],
            ))
        st.markdown(lista_activos_html(filas), unsafe_allow_html=True)
    elif not mercado.empty:
        st.markdown(titulo_app("Lo más operado del día"), unsafe_allow_html=True)
        st.markdown(_lista_ranking(mercado, "Monto (M $)", False, lambda r: fmt_pesos(r["Último"])), unsafe_allow_html=True)
    else:
        estado_vacio("Mercado sin datos por ahora", "No pudimos traer los precios del mercado. Probá recargar en unos minutos.", "📉")

    if shorts:
        st.markdown(titulo_app("Noticias en 1 minuto"), unsafe_allow_html=True)
        st.markdown(carrusel_shorts_html(shorts[:5]), unsafe_allow_html=True)
    st.caption(DISCLAIMER_CARTERA)
