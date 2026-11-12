"""Textos y contenido editorial de NAPO (lo que se edita sin tocar la lógica)."""

# Links oficiales por activo: ticker -> (url, etiqueta del botón).
# Solo van los que están verificados; sumá más a medida que los confirmes.
LINKS_OFICIALES = {
    "YPF": ("https://www.ypf.com", "Sitio oficial"),
    "PAMP": ("https://ri.pampa.com", "Relaciones con Inversores"),
}

# Academia NAPO: glosario
GLOSARIO = {
    "CEDEAR": "Certificado de Depósito Argentino que representa acciones de empresas extranjeras, "
              "operable en pesos dentro de ByMA.",
    "Dólar MEP": "Tipo de cambio que surge de comprar un bono en pesos y venderlo en dólares dentro "
                 "del mercado local, de forma legal y sin cepo operativo.",
    "Dólar CCL (Contado con Liqui)": "Similar al MEP, pero permite sacar los dólares fuera del país "
                                      "al liquidarse la operación en una cuenta en el exterior.",
    "Riesgo País": "Indicador (en puntos básicos) que mide el sobrecosto que paga un país para "
                   "financiarse en el mercado internacional respecto a EE.UU.",
    "EBITDA": "Ganancias antes de intereses, impuestos, depreciaciones y amortizaciones. Mide la "
              "rentabilidad operativa pura de una empresa.",
    "RIGI": "Régimen de Incentivo para Grandes Inversiones: otorga estabilidad fiscal, cambiaria y "
            "aduanera a 30 años para proyectos superiores a US$200 millones en Argentina.",
    "Arbitraje CCL": "Estrategia de comprar un activo en pesos y venderlo en dólares (o viceversa) "
                      "aprovechando diferencias de precio entre mercados.",
    "Renta Variable": "Instrumentos financieros (como acciones) cuyo rendimiento no está garantizado "
                       "y depende de la evolución del mercado.",
}

# Textos fijos de la interfaz
TEXTO_BANNER = (
    "🧪 VERSIÓN DE PRUEBA · Dólares, riesgo país y precios con datos reales (pueden tener demora). "
    "Los reportes son análisis informativos y no constituyen asesoramiento financiero."
)
TEXTO_PIE = (
    "Dólares y riesgo país: DolarApi y ArgentinaDatos. Precios: Yahoo Finance (pueden tener demora). "
    "Los reportes son análisis informativos y no constituyen asesoramiento financiero."
)
DISCLAIMER_REPORTES = (
    "Contenido informativo. No constituye asesoramiento financiero ni una recomendación de compra o venta. "
    "Las fuentes de cada reporte están indicadas al pie."
)
