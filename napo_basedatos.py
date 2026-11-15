"""Acceso genérico a las tablas de Supabase (API REST). Lo usan reportes, shorts y eventos."""

import requests

from napo_secretos import secreto


def conexion(tabla: str):
    """(url de la tabla, encabezados) o None si faltan los Secrets."""
    base = secreto("SUPABASE_URL").rstrip("/")
    clave = secreto("SUPABASE_KEY")
    if not base or not clave:
        return None
    # Las claves nuevas (sb_publishable_ / sb_secret_) van SOLO en `apikey`.
    # Las claves viejas (JWT, empiezan con "eyJ") van también como Bearer.
    encabezados = {"apikey": clave, "Content-Type": "application/json"}
    if clave.startswith("eyJ"):
        encabezados["Authorization"] = f"Bearer {clave}"
    return f"{base}/rest/v1/{tabla}", encabezados


def configurado() -> bool:
    return conexion("x") is not None


def pedir(tabla: str, metodo: str, params=None, cuerpo=None, prefer=None, timeout=15):
    """Hace un pedido a una tabla. Devuelve (ok, datos_o_mensaje_de_error)."""
    con = conexion(tabla)
    if con is None:
        return False, "Faltan SUPABASE_URL y SUPABASE_KEY en los Secrets."
    url, encabezados = con
    if prefer:
        encabezados = {**encabezados, "Prefer": prefer}
    try:
        resp = requests.request(metodo, url, headers=encabezados, params=params, json=cuerpo, timeout=timeout)
    except Exception as error:
        return False, f"No se pudo conectar con la base de datos ({type(error).__name__})."
    if resp.status_code >= 400:
        return False, f"La base de datos respondió {resp.status_code}: {resp.text[:200]}"
    try:
        return True, (resp.json() if resp.content else None)
    except ValueError:
        return True, None


def es_duplicado(mensaje: str) -> bool:
    """True si el error de la base fue por un dato repetido (HTTP 409)."""
    return "respondió 409" in str(mensaje)
