"""Carga de los estilos globales (napo_estilos.css) con los colores de config.py."""

from pathlib import Path

import streamlit as st

from napo_config import PALETA_CSS

_CSS_PATH = Path(__file__).with_name("napo_estilos.css")


# En celular, las solapas pasan a una barra fija abajo, como en una app. Es un ajuste visual experimental:
# si no se ve bien, se apaga cargando NAV_INFERIOR = "0" en los Secrets (no hace falta tocar el código).
CSS_NAV_INFERIOR = """
@media (max-width: 640px) {
    .stTabs [data-baseweb="tab-list"] {
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 9999;
        border-radius: 0; border-left: 0; border-right: 0; border-bottom: 0;
        padding: 6px 4px calc(8px + env(safe-area-inset-bottom, 0px));
        overflow-x: auto; flex-wrap: nowrap;
        background: var(--card); box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.35);
    }
    .stTabs [data-baseweb="tab"] { flex: 0 0 auto; height: 46px; padding: 0 12px; font-size: 11.5px; }
    .block-container { padding-bottom: 96px; }
}
"""


def cargar_estilos(nav_inferior: bool = True):
    """Inyecta el CSS de NAPO. Las variables de color salen de PALETA_CSS."""
    css = _CSS_PATH.read_text(encoding="utf-8")
    if nav_inferior:
        css += CSS_NAV_INFERIOR
    variables = ":root {" + " ".join(f"{k}: {v};" for k, v in PALETA_CSS.items()) + "}"
    st.markdown(f"<style>\n{css.replace('/*VARIABLES*/', variables)}\n</style>", unsafe_allow_html=True)
