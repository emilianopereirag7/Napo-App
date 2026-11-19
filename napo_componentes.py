"""Piezas de interfaz reutilizables: tarjetas, cartel sin datos, marquesina, encabezado y pie."""

import html

import streamlit as st

from napo_config import (
    BG_CARD, BORDER_SUBTLE, DOLARES_PANEL, INDICES_MARQUESINA, KLEIN_BLUE_LIGHT, TEXT_PRIMARY, TEXT_SECONDARY,
    YOSHI_GREEN, YOSHI_ORANGE,
)
from napo_contenido import TEXTO_BANNER, TEXTO_PIE
from napo_datos import resumen_serie, serie_activo
from napo_formatos import fmt_numero, fmt_pct, fmt_pesos, fmt_var, parse_iso
from napo_reportes import IMPACTOS
from napo_shorts import extraer_video_id, url_miniatura, url_short


def _kpi_html(label: str, value: str, delta: str = None, positive: bool = True, sub: str = None) -> str:
    extra = ""
    if delta:
        color = YOSHI_GREEN if positive else YOSHI_ORANGE
        arrow = "▲" if positive else "▼"
        extra += f'<div class="napo-card-delta" style="color:{color};">{arrow} {html.escape(delta)}</div>'
    if sub:
        extra += f'<div class="napo-card-sub">{html.escape(sub)}</div>'
    return (
        f'<div class="napo-card"><div class="napo-card-label">{html.escape(label)}</div>'
        f'<div class="napo-card-value">{html.escape(value)}</div>{extra}</div>'
    )


def kpi_card(label: str, value: str, delta: str = None, positive: bool = True, sub: str = None):
    st.markdown(_kpi_html(label, value, delta, positive, sub), unsafe_allow_html=True)


def kpi_grid(items: list):
    """Fila de tarjetas que se acomoda sola: varias por fila en escritorio, 2 por fila en celular.
    items: lista de dicts con las claves label, value y opcionalmente delta, positive, sub."""
    celdas = "".join(_kpi_html(**item) for item in items)
    st.markdown(f'<div class="napo-kpi-grid">{celdas}</div>', unsafe_allow_html=True)


def estado_vacio(titulo: str, detalle: str, icono: str = "📡"):
    """Cartel prolijo para cuando una fuente de datos no responde."""
    st.markdown(
        f'<div class="napo-empty"><div class="napo-empty-icon">{icono}</div>'
        f'<div class="napo-empty-title">{html.escape(titulo)}</div>'
        f'<div class="napo-empty-text">{html.escape(detalle)}</div></div>',
        unsafe_allow_html=True,
    )


def section_title(text: str, icon: str = ""):
    st.markdown(
        f'<div class="napo-section-title"><span class="bar"></span>{icon} {text}</div>',
        unsafe_allow_html=True,
    )


def _lista_html(texto: str) -> str:
    items = [linea.strip() for linea in (texto or "").splitlines() if linea.strip()]
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def reporte_html(rep: dict) -> str:
    """Tarjeta de un reporte táctico (todo el texto va escapado)."""
    emoji, etiqueta = IMPACTOS.get(rep.get("impacto"), ("⚪", "Neutral"))
    clase = {"alcista": "napo-badge-up", "bajista": "napo-badge-down"}.get(rep.get("impacto"), "napo-badge-neutral")
    fecha = parse_iso(rep.get("creado"))
    partes = [
        '<div class="napo-rep">',
        f'<div class="napo-rep-head"><span class="napo-tag">{html.escape(str(rep.get("ticker", "")))}</span>'
        f'<span class="napo-rep-fecha">{fecha.strftime("%d/%m/%Y %H:%M") if fecha else ""}</span></div>',
        f'<div class="napo-rep-titular">{html.escape(str(rep.get("titular", "")))}</div>',
    ]
    if rep.get("contexto"):
        partes.append(f'<div class="napo-rep-label">Contexto</div>{_lista_html(rep["contexto"])}')
    if rep.get("efecto"):
        partes.append(f'<div class="napo-rep-label">Efecto en la acción</div>{_lista_html(rep["efecto"])}')
    partes.append(
        f'<div class="napo-rep-impacto"><span class="{clase}">{emoji} {etiqueta}</span>'
        f'<span class="napo-rep-just">{html.escape(str(rep.get("justificacion", "")))}</span></div>'
    )
    if rep.get("fuente"):
        partes.append(f'<div class="napo-rep-fuente">Fuente: {html.escape(str(rep["fuente"]))}</div>')
    partes.append("</div>")
    return "".join(partes)


def _tarjeta_short(s: dict) -> str:
    video_id = extraer_video_id(str(s.get("video_id", "")))
    if not video_id:
        return ""
    fecha = parse_iso(s.get("creado"))
    detalle = html.escape(str(s.get("canal", "")))
    if fecha:
        detalle += f" · {fecha.strftime('%d/%m')}"
    nota = f'<div class="napo-short-nota">{html.escape(str(s["nota"]))}</div>' if s.get("nota") else ""
    return (
        f'<a class="napo-short" href="{url_short(video_id)}" target="_blank" rel="noopener noreferrer">'
        f'<div class="napo-short-thumb"><img src="{url_miniatura(video_id)}" alt="" loading="lazy">'
        f'<span class="napo-short-play">▶</span></div>'
        f'<div class="napo-short-titulo">{html.escape(str(s.get("titulo", "")))}</div>'
        f'<div class="napo-short-canal">{detalle}</div>{nota}</a>'
    )


def shorts_html(shorts, clase: str = "napo-shorts-grid") -> str:
    """Tarjetas con miniatura vertical (grilla o carrusel). Cada tarjeta abre el Short en YouTube."""
    return f'<div class="{clase}">' + "".join(_tarjeta_short(s) for s in shorts) + "</div>"


def carrusel_shorts_html(shorts) -> str:
    """Los Shorts en una fila que se desliza con el dedo."""
    return shorts_html(shorts, "napo-shorts-row")


def boton_link_html(texto: str, url: str) -> str:
    """Botón con link (solo http/https)."""
    if not str(url).lower().startswith(("http://", "https://")):
        return ""
    return (
        f'<a class="napo-btn" href="{html.escape(url, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer">{html.escape(texto)}</a>'
    )


def cassette(titulo: str, lado: str, tiempo: str, sello: str):
    """Reproductor retro: etiqueta, dos rollos animados y una línea de datos."""
    st.markdown(
        f"""
        <div class="napo-cassette">
            <div class="napo-cassette-label">{titulo}</div>
            <div class="napo-reels">
                <div class="napo-reel"></div>
                <div class="napo-reel"></div>
            </div>
            <div class="napo-cassette-meta">
                <span>{lado}</span><span>{tiempo}</span><span>{sello}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _item_marquesina(nombre, valor, chg, sube):
    cambio = ""
    if chg is not None:
        clase = "napo-up" if sube else "napo-down"
        flecha = "▲" if sube else "▼"
        cambio = f' <span class="{clase}">{flecha} {chg}</span>'
    return f'<span class="napo-ticker-item"><b>{nombre}</b>{valor}{cambio}</span>'


def marquesina(dolares, riesgo_pais, precios):
    """Cinta superior con dólares, riesgo país, índices y commodities (solo datos reales)."""
    marquee_items = []  # (nombre, valor, variación en texto o None, sube True/False/None)
    for etiqueta, casa in DOLARES_PANEL:
        cot = (dolares or {}).get(casa)
        if cot and cot.get("venta") is not None:
            marquee_items.append((etiqueta, fmt_pesos(cot["venta"]), None, None))
    if riesgo_pais:
        marquee_items.append(("Riesgo País", f"{int(round(riesgo_pais['valor']))} pb", None, None))
    for nombre, simbolo, prefijo, decimales in INDICES_MARQUESINA:
        r = resumen_serie(serie_activo(precios, simbolo))
        if r:
            marquee_items.append(
                (nombre, f"{prefijo}{fmt_numero(r['ultimo'], decimales)}", fmt_pct(r["var"]), r["var"] >= 0)
            )
    if not marquee_items:
        marquee_items = [("NAPO", "Panel Táctico Financiero", None, None)]

    ticker_html = "".join(_item_marquesina(*item) for item in (marquee_items * 4))
    st.markdown(
        f'<div class="napo-ticker-wrap"><div class="napo-ticker-inner">{ticker_html}</div></div>',
        unsafe_allow_html=True,
    )


LOGO_SVG = (
    '<svg class="napo-logo" width="42" height="42" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="NAPO"><rect width="48" height="48" rx="12" fill="#2563EB"/><path d="M24 8 L32 24 L16 24 Z" fill="#FFFFFF"/><path d="M24 40 L32 24 L16 24 Z" fill="#FFFFFF" fill-opacity="0.38"/><circle cx="24" cy="24" r="2.6" fill="#2563EB"/></svg>'
)


def encabezado():
    """Logo + nombre + lema."""
    st.markdown(
        f'<div class="napo-header"><div class="napo-brand">{LOGO_SVG}'
        '<div class="napo-brand-text"><span class="napo-brand-mark">NAPO</span>'
        '<span class="napo-brand-sub">Panel Táctico Financiero</span></div></div>'
        '<div class="napo-pill">Menos ruido, más decisión</div></div>',
        unsafe_allow_html=True,
    )


def banner_demo():
    st.markdown(f'<div class="napo-demo-banner">{TEXTO_BANNER}</div>', unsafe_allow_html=True)


def pie_de_pagina():
    st.markdown(
        f"""
        <div class="napo-footer">
            NAPO | Panel Táctico Financiero — Menos ruido, datos duros y decisiones tácticas.<br>
            {TEXTO_PIE}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ================================================================ piezas del estilo "app financiera"

_PALETA_AVATAR = ["#2563EB", "#7C3AED", "#0891B2", "#DB2777", "#059669", "#D97706", "#4F46E5", "#DC2626"]


def avatar_html(ticker: str, tam: int = 40) -> str:
    """Círculo de color con las iniciales del activo."""
    color = _PALETA_AVATAR[sum(map(ord, ticker)) % len(_PALETA_AVATAR)]
    return (f'<div class="napo-av" style="background:{color};width:{tam}px;height:{tam}px;font-size:{round(tam * 0.3)}px">'
            f'{html.escape(ticker[:3])}</div>')


def pill_html(var) -> str:
    """Variación en pastilla: verde ▲ si sube, naranja ▼ si baja."""
    clase = "napo-badge-up" if var >= 0 else "napo-badge-down"
    return f'<span class="{clase}">{"▲" if var >= 0 else "▼"} {fmt_pct(var)}</span>'


def _hay(valor) -> bool:
    return valor is not None and valor == valor  # descarta None y NaN


def fila_activo_html(ticker: str, nombre: str, detalle: str, derecha: str, var=None) -> str:
    pastilla = pill_html(var) if _hay(var) else ""
    return (
        f'<div class="napo-fila" data-t="{html.escape(ticker)}">{avatar_html(ticker)}'
        f'<div class="napo-fila-t"><b>{html.escape(nombre)}</b><span>{html.escape(detalle)}</span></div>'
        f'<div class="napo-fila-d"><b>{html.escape(derecha)}</b>{pastilla}</div></div>'
    )


def lista_activos_html(filas: list) -> str:
    """Lista de activos en una tarjeta. filas: dicts con ticker, nombre, detalle, derecha y var (opcional)."""
    return '<div class="napo-lista">' + "".join(fila_activo_html(**f) for f in filas) + "</div>"


def movers_html(items: list) -> str:
    """Fila que se desliza con los activos que más se mueven. items: (ticker, nombre, variación)."""
    tarjetas = "".join(
        f'<div class="napo-mv" data-t="{html.escape(t)}">{avatar_html(t, 34)}<b>{html.escape(t)}</b>'
        f'<span>{html.escape(n)}</span>{pill_html(v)}</div>'
        for t, n, v in items
    )
    return f'<div class="napo-movers">{tarjetas}</div>'


def titulo_app(texto: str) -> str:
    return f'<div class="napo-sec">{html.escape(texto)}</div>'


def saludo_html() -> str:
    return '<div class="napo-saludo"><small>Hola 👋</small><h3>Tu resumen de hoy</h3></div>'


def saldo_html(tot=None) -> str:
    """Tarjeta grande de saldo. Sin cartera cargada, invita a armarla."""
    if not tot or not tot.get("n_activos"):
        return ('<div class="napo-saldo"><small>Tu cartera hoy</small>'
                '<div class="napo-saldo-vacio">Armá tu cartera</div>'
                '<div class="napo-saldo-sub">Cargá tus activos y mirá cuánto valen hoy. '
                'No se guarda en nuestros servidores.</div></div>')
    cuerpo, _, centavos = fmt_pesos(tot["valor_total"]).rpartition(",")
    sub = ""
    if _hay(tot.get("var_dia_pct")):
        signo = "+" if tot["var_dia"] >= 0 else "-"
        flecha = "▲" if tot["var_dia"] >= 0 else "▼"
        sub = f'<div class="napo-saldo-sub">{flecha} {signo}{fmt_pesos(abs(tot["var_dia"]))} ({fmt_var(tot["var_dia_pct"])}) hoy</div>'
    return (f'<div class="napo-saldo"><small>Tu cartera hoy</small>'
            f'<div class="napo-saldo-n">{html.escape(cuerpo)}<span>,{html.escape(centavos)}</span></div>{sub}</div>')


def acciones_rapidas_html() -> str:
    """Documento para un iframe: cuatro botones redondos que cambian de solapa de la página.

    Es un atajo opcional: si el navegador no permite tocar las solapas desde el iframe, no pasa nada.
    """
    accesos = [("📊", "Mercado", "Ranking"), ("💼", "Mi cartera", "Mi cartera"), ("📰", "Reportes", "Reportes"),
               ("🎬", "Noticias", "Noticias")]
    botones = "".join(
        f'<button onclick="ir(\'{buscar}\')" aria-label="Ir a {etiqueta}"><i>{icono}</i>{etiqueta}</button>'
        for icono, etiqueta, buscar in accesos
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif;background:transparent}}
.f{{display:flex;justify-content:space-around;padding:6px 4px}}
button{{background:none;border:0;cursor:pointer;width:78px;text-align:center;color:{TEXT_SECONDARY};font-size:12px;font-weight:700;font-family:inherit}}
i{{display:flex;width:56px;height:56px;border-radius:50%;background:{BG_CARD};border:1px solid {BORDER_SUBTLE};align-items:center;justify-content:center;font-style:normal;font-size:22px;margin:0 auto 8px}}
button:hover i{{border-color:{KLEIN_BLUE_LIGHT}}}button:hover{{color:{TEXT_PRIMARY}}}
</style></head><body><div class="f">{botones}</div><script>
function ir(texto){{try{{var t=window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
for(var i=0;i<t.length;i++){{if(t[i].textContent.indexOf(texto)!==-1){{t[i].click();break;}}}}}}catch(e){{}}}}
</script></body></html>"""
