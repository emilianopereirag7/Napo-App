"""Piezas de interfaz reutilizables: tarjetas, cartel sin datos, marquesina, encabezado y pie."""

import html

import streamlit as st

from .config import DOLARES_PANEL, INDICES_MARQUESINA, YOSHI_GREEN, YOSHI_ORANGE
from .contenido import TEXTO_BANNER, TEXTO_PIE
from .datos import resumen_serie, serie_activo
from .formatos import fmt_numero, fmt_pct, fmt_pesos, parse_iso
from .reportes import IMPACTOS


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
