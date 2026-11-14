"""Lógica de «Mi cartera» (sin Streamlit): limpieza, CSV de ida y vuelta y valuación.

La cartera NO se guarda en ningún servidor: vive en la sesión de quien la usa
y se conserva descargando el CSV.
"""

import io
import unicodedata

import pandas as pd

COLUMNAS = ["ticker", "cantidad", "precio_compra"]
MAX_FILAS = 200
_NAN = float("nan")

_ALIAS = {
    "ticker": ("ticker", "simbolo", "activo", "papel", "especie"),
    "cantidad": ("cantidad", "cant", "nominales", "qty", "unidades"),
    "precio_compra": ("precio_compra", "precio", "ppc", "costo", "precio_promedio"),
}


def cartera_vacia() -> pd.DataFrame:
    return pd.DataFrame({"ticker": pd.Series(dtype="object"), "cantidad": pd.Series(dtype="float"),
                         "precio_compra": pd.Series(dtype="float")})


def _a_numero(valor, punto_es_miles: bool = False) -> float:
    """'1.234,5' / '1234.5' / 1234.5 -> float. NaN si no se puede leer."""
    if valor is None:
        return _NAN
    if isinstance(valor, (int, float)):
        return float(valor)
    t = str(valor).strip().replace("$", "").replace(" ", "")
    if not t:
        return _NAN
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    elif punto_es_miles and t.count(".") == 1:
        entero, decimales = t.split(".")
        if len(decimales) == 3 and entero.isdigit() and 1 <= len(entero) <= 3 and entero != "0":
            t = entero + decimales  # '1.250' -> 1250
    try:
        return float(t)
    except ValueError:
        return _NAN


def limpiar_cartera(df, validos):
    """Valida una tabla de cartera. Devuelve (tabla_limpia, avisos)."""
    avisos = []
    if df is None or len(df) == 0:
        return cartera_vacia(), avisos
    d = df.copy()
    for c in COLUMNAS:
        if c not in d.columns:
            d[c] = _NAN
    d = d[COLUMNAS]
    if len(d) > MAX_FILAS:
        avisos.append(f"Solo se toman las primeras {MAX_FILAS} filas.")
        d = d.head(MAX_FILAS)
    d["ticker"] = d["ticker"].astype(str).str.strip().str.upper().str.replace("$", "", regex=False)
    d["cantidad"] = pd.to_numeric(d["cantidad"], errors="coerce")
    d["precio_compra"] = pd.to_numeric(d["precio_compra"], errors="coerce")

    d = d[~(d["ticker"].isin(["", "NAN", "NONE"]) & d["cantidad"].isna())]
    desconocidos = sorted(set(d.loc[~d["ticker"].isin(validos), "ticker"]))
    if desconocidos:
        avisos.append("Ticker no reconocido (se ignoró): " + ", ".join(desconocidos)[:200])
    d = d[d["ticker"].isin(validos)]
    sin_cantidad = int((~(d["cantidad"] > 0)).sum())
    if sin_cantidad:
        avisos.append(f"Se ignoraron {sin_cantidad} fila(s) sin una cantidad mayor a 0.")
    d = d[d["cantidad"] > 0].copy()
    d.loc[d["precio_compra"] < 0, "precio_compra"] = _NAN

    filas = []
    for ticker, grupo in d.groupby("ticker", sort=False):
        con_precio = grupo[grupo["precio_compra"].notna()]
        precio = ((con_precio["cantidad"] * con_precio["precio_compra"]).sum() / con_precio["cantidad"].sum()
                  if len(con_precio) else _NAN)
        filas.append({"ticker": ticker, "cantidad": float(grupo["cantidad"].sum()), "precio_compra": precio})
    if not filas:
        return cartera_vacia(), avisos
    return pd.DataFrame(filas, columns=COLUMNAS), avisos


def desde_csv(contenido, validos):
    """Lee un CSV (el que se descarga de la app, o uno armado a mano). Devuelve (tabla, avisos)."""
    if isinstance(contenido, (bytes, bytearray)) and len(contenido) > 500_000:
        return cartera_vacia(), ["El archivo es demasiado grande para ser una cartera."]
    texto = contenido.decode("utf-8-sig", errors="replace") if isinstance(contenido, (bytes, bytearray)) else str(contenido)
    lineas = [l for l in texto.splitlines() if l.strip()]
    if not lineas:
        return cartera_vacia(), ["El archivo está vacío."]
    sep = ";" if lineas[0].count(";") >= lineas[0].count(",") and ";" in lineas[0] else ","
    try:
        crudo = pd.read_csv(io.StringIO("\n".join(lineas)), sep=sep, dtype=str, keep_default_na=False)
    except Exception:
        return cartera_vacia(), ["No pude leer el archivo. Usá el CSV que se descarga desde esta misma sección."]
    renombrar = {}
    for col in crudo.columns:
        norm = unicodedata.normalize("NFKD", str(col)).encode("ascii", "ignore").decode().lower().strip().replace(" ", "_")
        for destino, nombres in _ALIAS.items():
            if norm in nombres:
                renombrar[col] = destino
    crudo = crudo.rename(columns=renombrar)
    if "ticker" not in crudo.columns or "cantidad" not in crudo.columns:
        return cartera_vacia(), ["Al archivo le faltan las columnas «ticker» y «cantidad»."]
    miles = sep == ";"
    tabla = pd.DataFrame({
        "ticker": crudo["ticker"],
        "cantidad": crudo["cantidad"].map(lambda v: _a_numero(v, miles)),
        "precio_compra": crudo["precio_compra"].map(lambda v: _a_numero(v, miles)) if "precio_compra" in crudo.columns else _NAN,
    })
    return limpiar_cartera(tabla, validos)


def a_csv(df: pd.DataFrame) -> str:
    """CSV para Excel en español: separador «;» y coma decimal."""
    salida = df[COLUMNAS].copy() if len(df) else cartera_vacia()
    return salida.to_csv(index=False, sep=";", decimal=",", na_rep="")


def valuar(df: pd.DataFrame, mercado: dict, info: dict):
    """Valúa la cartera con los precios actuales.

    mercado: {ticker: {"ultimo": precio, "previo": cierre anterior}}
    info:    {ticker: {"nombre", "sector", "tipo"}}
    Devuelve (tabla_valuada, totales).
    """
    filas = []
    for _, f in df.iterrows():
        t = f["ticker"]
        m = mercado.get(t)
        i = info.get(t, {})
        cant = float(f["cantidad"])
        pc = f["precio_compra"]
        precio = m["ultimo"] if m else _NAN
        previo = m["previo"] if m else _NAN
        valor = cant * precio
        costo = cant * pc if pd.notna(pc) else _NAN
        filas.append({
            "ticker": t, "nombre": i.get("nombre", ""), "sector": i.get("sector", ""), "tipo": i.get("tipo", ""),
            "cantidad": cant, "precio": precio, "valor": valor, "valor_previo": cant * previo,
            "var_dia_pct": (precio / previo - 1) * 100 if m and previo else _NAN,
            "precio_compra": pc, "costo": costo, "resultado": valor - costo,
            "resultado_pct": (precio / pc - 1) * 100 if m and pd.notna(pc) and pc else _NAN,
        })
    v = pd.DataFrame(filas)
    if v.empty:
        return v, {"valor_total": 0.0, "var_dia": 0.0, "var_dia_pct": _NAN, "costo_total": 0.0,
                   "resultado_total": 0.0, "resultado_pct": _NAN, "n_activos": 0, "n_sin_precio": 0}
    valor_total = float(v["valor"].sum(skipna=True))
    v["peso"] = v["valor"] / valor_total * 100 if valor_total else _NAN
    con_precio = v[v["precio"].notna()]
    valor_previo = float(con_precio["valor_previo"].sum())
    var_dia = float(con_precio["valor"].sum()) - valor_previo
    con_costo = con_precio[con_precio["costo"].notna()]
    costo_total = float(con_costo["costo"].sum())
    resultado_total = float(con_costo["valor"].sum()) - costo_total
    totales = {
        "valor_total": valor_total,
        "var_dia": var_dia,
        "var_dia_pct": var_dia / valor_previo * 100 if valor_previo else _NAN,
        "costo_total": costo_total,
        "resultado_total": resultado_total,
        "resultado_pct": resultado_total / costo_total * 100 if costo_total else _NAN,
        "n_activos": len(v),
        "n_sin_precio": int(v["precio"].isna().sum()),
    }
    return v, totales


def composicion(valuada: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Peso de cada activo; los más chicos se agrupan en «Otros»."""
    base = valuada[valuada["valor"].notna() & (valuada["valor"] > 0)][["ticker", "valor"]].sort_values("valor", ascending=False)
    if len(base) <= top:
        return base.reset_index(drop=True)
    resto = float(base.iloc[top:]["valor"].sum())
    grande = base.iloc[:top].copy()
    return pd.concat([grande, pd.DataFrame([{"ticker": "Otros", "valor": resto}])], ignore_index=True)
