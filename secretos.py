"""Lectura segura de los Secrets de Streamlit (claves que no van en el código)."""

import streamlit as st


def secreto(nombre: str, default: str = "") -> str:
    """Devuelve el secreto como texto, o `default` si no existe o está vacío."""
    try:
        valor = st.secrets[nombre]
    except Exception:
        return default
    if valor is None:
        return default
    texto = str(valor).strip()
    return texto or default
