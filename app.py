"""
NAPO | Panel Táctico Financiero
-------------------------------
Punto de entrada. Ejecutar con:  streamlit run app.py

La lógica está repartida en la carpeta napo/:
  config.py      colores, activos, URLs y constantes
  contenido.py   textos y contenido editorial
  secretos.py    lectura segura de los Secrets
  formatos.py    formato argentino de números y fechas
  datos.py       DolarApi, ArgentinaDatos y Yahoo Finance
  reportes.py    reportes (Supabase), lectura del prompt maestro y voz
  graficos.py    gráficos Plotly
  componentes.py piezas de interfaz (tarjetas, marquesina, encabezado)
  paginas.py     panel cambiario y solapas
  cocina.py      back-office con clave (publicar reportes)
  estilos.css    estilos globales
"""

from pathlib import Path

import streamlit as st

from napo.cocina import panel_operador, render_cocina
from napo.componentes import banner_demo, encabezado, marquesina, pie_de_pagina
from napo.datos import cargar_precios, obtener_dolares, obtener_riesgo_pais
from napo.estilos import cargar_estilos
from napo.paginas import (
    panel_cambiario, tab_academia, tab_explorador, tab_feedback, tab_ranking, tab_reportes,
)
from napo.reportes import listar_reportes
from napo.secretos import secreto

try:
    _BASE_DIR = Path(__file__).resolve().parent
except NameError:
    _BASE_DIR = Path(".")
_FAVICON = _BASE_DIR / "favicon.png"

st.set_page_config(
    page_title="NAPO | Panel Táctico Financiero",
    page_icon=str(_FAVICON) if _FAVICON.exists() else "🧭",
    layout="wide",
    initial_sidebar_state="collapsed",  # La Cocina no debe recibir a los visitantes (sobre todo en celular)
)

cargar_estilos()

# Datos (cada fuente se guarda unos minutos para no saturar las APIs)
dolares = obtener_dolares()
riesgo_pais = obtener_riesgo_pais()
precios = cargar_precios()
reportes = listar_reportes()

# Página
marquesina(dolares, riesgo_pais, precios)
encabezado()
banner_demo()
panel_cambiario(dolares, riesgo_pais)
render_cocina()
panel_operador()

url_feedback = secreto("FEEDBACK_URL")
nombres_solapas = ["📡 Explorador de Activos", "🔥 Ranking & Heatmap", "📰 Reportes & Audio", "🎓 Academia NAPO"]
if url_feedback:
    nombres_solapas.append("💬 Tu opinión")
solapas = st.tabs(nombres_solapas)

with solapas[0]:
    tab_explorador(precios, reportes)
with solapas[1]:
    tab_ranking(precios)
with solapas[2]:
    tab_reportes(reportes)
with solapas[3]:
    tab_academia()
if url_feedback:
    with solapas[4]:
        tab_feedback(url_feedback)

pie_de_pagina()
