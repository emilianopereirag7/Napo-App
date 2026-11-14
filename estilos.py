"""Carga de los estilos globales (napo/estilos.css) con los colores de config.py."""

from pathlib import Path

import streamlit as st

from .config import PALETA_CSS

_CSS_PATH = Path(__file__).with_name("estilos.css")


def cargar_estilos():
    """Inyecta el CSS de NAPO. Las variables de color salen de PALETA_CSS."""
    css = _CSS_PATH.read_text(encoding="utf-8")
    variables = ":root {" + " ".join(f"{k}: {v};" for k, v in PALETA_CSS.items()) + "}"
    st.markdown(f"<style>\n{css.replace('/*VARIABLES*/', variables)}\n</style>", unsafe_allow_html=True)
