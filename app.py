"""
NAPO | Panel Táctico Financiero
-------------------------------
Punto de entrada. Ejecutar con:  streamlit run app.py

La lógica está repartida en los archivos napo_*.py (todos en la misma carpeta, sin subcarpetas):
  napo_config.py      colores, activos, URLs y constantes
  napo_contenido.py   textos y contenido editorial
  napo_secretos.py    lectura segura de los Secrets
  napo_formatos.py    formato argentino de números y fechas
  napo_datos.py       DolarApi, ArgentinaDatos y Yahoo Finance
  napo_basedatos.py   acceso a Supabase
  napo_reportes.py    reportes, lectura del prompt maestro y voz
  napo_shorts.py      noticias en Shorts de YouTube
  napo_seguimiento.py lista informativa de activos seguidos
  napo_eventos.py     medición de uso anónima
  napo_graficos.py    gráficos Plotly
  napo_componentes.py piezas de interfaz (tarjetas, marquesina, encabezado)
  napo_paginas.py     panel cambiario y solapas
  napo_cocina.py      back-office con clave (se abre con ?cocina=1)
  napo_estilos.css    estilos globales
"""

from pathlib import Path

import streamlit as st

from napo_cocina import acceso_cocina, panel_operador
from napo_componentes import banner_demo, encabezado, marquesina, pie_de_pagina
from napo_datos import cargar_precios, obtener_dolares, obtener_riesgo_pais
from napo_estilos import cargar_estilos
from napo_eventos import registrar_visita
from napo_paginas import (
    tab_academia, tab_explorador, tab_feedback, tab_inicio, tab_noticias, tab_ranking, tab_reportes, tab_seguimiento,
)
from napo_reportes import listar_reportes
from napo_secretos import secreto
from napo_shorts import listar_shorts

try:
    _BASE_DIR = Path(__file__).resolve().parent
except NameError:
    _BASE_DIR = Path(".")
_FAVICON = _BASE_DIR / "favicon.png"

st.set_page_config(
    page_title="NAPO | Panel Táctico Financiero",
    page_icon=str(_FAVICON) if _FAVICON.exists() else "🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

cargar_estilos(nav_inferior=secreto("NAV_INFERIOR", "1") != "0")
registrar_visita()
aviso = st.session_state.pop("_toast", None)  # mensajes breves de los botones (por ejemplo, "Agregamos YPF")
if aviso:
    st.toast(aviso)

# Datos (cada fuente se guarda unos minutos para no saturar las APIs)
dolares = obtener_dolares()
riesgo_pais = obtener_riesgo_pais()
precios = cargar_precios()
reportes = listar_reportes()
shorts = listar_shorts()

# Página
marquesina(dolares, riesgo_pais, precios)
encabezado()
banner_demo()
acceso_cocina()
panel_operador()

url_feedback = secreto("FEEDBACK_URL")
nombres_solapas = [
    "🏠 Inicio", "📡 Explorador", "🔥 Ranking & Heatmap", "📌 Mis activos", "📰 Reportes & Audio",
    "🎬 Noticias en Shorts", "🎓 Academia NAPO",
]
if url_feedback:
    nombres_solapas.append("💬 Tu opinión")
solapas = st.tabs(nombres_solapas)

# «Mis activos» se dibuja primero para que Inicio pueda mostrar el seguimiento actualizado.
with solapas[3]:
    tab_seguimiento(precios, reportes, dolares)
with solapas[0]:
    tab_inicio(precios, reportes, shorts, dolares, riesgo_pais)
with solapas[1]:
    tab_explorador(precios, reportes)
with solapas[2]:
    tab_ranking(precios)
with solapas[4]:
    tab_reportes(reportes)
with solapas[5]:
    tab_noticias(shorts)
with solapas[6]:
    tab_academia()
if url_feedback:
    with solapas[7]:
        tab_feedback(url_feedback)

pie_de_pagina()
