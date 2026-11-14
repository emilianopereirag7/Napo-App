"""Funciones para dar formato argentino a números, monedas y fechas."""

from datetime import datetime

from .config import TZ_ARG


def fmt_numero(valor, decimales: int = 2) -> str:
    """1234567.891 -> '1.234.567,89' (formato argentino)."""
    texto = f"{float(valor):,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(valor) -> str:
    """-1.256 -> '1,26%' (sin signo; el signo lo marca la flecha)."""
    return f"{abs(float(valor)):.2f}".replace(".", ",") + "%"


def fmt_var(valor) -> str:
    """1.256 -> '+1,26%' (con signo, coma decimal)."""
    return f"{float(valor):+.2f}".replace(".", ",") + "%"


def fmt_pesos(valor) -> str:
    """1515.97 -> '$ 1.515,97' (formato argentino)."""
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {texto}"


def parse_iso(texto):
    """Convierte un texto ISO 8601 a datetime en hora argentina (o None)."""
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone(TZ_ARG)
    except Exception:
        return None


def fmt_fecha_corta(texto) -> str:
    """'2026-11-10' -> '10/11/2026'."""
    try:
        return datetime.strptime(str(texto)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(texto)
