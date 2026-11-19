# NAPO — Cambio 02: Mis activos

## Qué cambia

La antigua sección **Mi cartera** pasa a ser **Mis activos**: una lista de seguimiento informativo. Ya no solicita ni muestra cantidad, precio de compra, valor total, peso de cartera ni composición.

Muestra por activo:
- Último precio diario disponible en ARS.
- Equivalente estimado en USD CCL (precio ARS dividido por el dólar CCL vendedor de DolarApi).
- Variación diaria, semanal (5 ruedas) y mensual (desde el primer cierre disponible del último mes), calculadas sobre el precio local en ARS.
- Fecha del último dato disponible.
- Reportes existentes asociados al ticker.

También permite agregar/quitar tickers, exportar una lista CSV e importar CSV anteriores. Si se importa el CSV antiguo con cantidad y precio de compra, se toman solamente los tickers.

## Archivos que hay que subir a la raíz del repositorio

**Reemplazar:**
1. `app.py`
2. `napo_paginas.py`
3. `napo_componentes.py`
4. `napo_cocina.py`

**Crear como archivo nuevo:**
5. `napo_seguimiento.py`

**Agregar carpeta de pruebas (opcional, recomendada para el repositorio):**
6. `tests/test_napo_seguimiento.py`

No borrar `napo_cartera.py` en este cambio. Queda sin uso por ahora para facilitar la vuelta atrás y evitar borrar código prematuramente.

## Supabase

No requiere ejecutar SQL ni modificar tablas de Supabase.

## Pasos sugeridos en GitHub

1. Crear un commit o punto de restauración antes de reemplazar archivos.
2. Subir los cuatro archivos para reemplazar y crear `napo_seguimiento.py` en la raíz.
3. Opcionalmente agregar `tests/test_napo_seguimiento.py` dentro de una carpeta `tests`.
4. Guardar los cambios en un único commit: `Cambio 02 - Mis activos`.
5. Esperar el redeploy automático de Streamlit Cloud y revisar los logs si aparece un error.
6. Probar agregar YPF, NVIDIA y GOOGL; quitar uno; descargar el CSV; importar el CSV antiguo de Mi cartera.

Si falla la aplicación, revertir el commit completo.

## Pruebas realizadas

- Todos los módulos Python del ZIP original más los modificados compilan con `py_compile`.
- Las cinco pruebas unitarias de `napo_seguimiento.py` pasaron en el entorno de preparación.
- No se ejecutó la interfaz dentro de Streamlit Cloud desde este entorno; la prueba final de interfaz debe hacerse después del deploy.

## Notas de datos

- Los precios son los últimos datos diarios que devuelve Yahoo Finance para los símbolos locales `.BA`; pueden tener demora y no son una promesa de tiempo real.
- El valor USD CCL es una equivalencia estimada con el CCL vendedor actual. No es una cotización independiente del activo en dólares.
- Las variaciones 1D/1S/1M de esta versión son sobre el precio local en ARS. Para mostrar variaciones históricas en USD CCL hace falta una serie histórica del dólar CCL, que no está implementada todavía.
- La lista sigue viviendo en la sesión de Streamlit y puede descargarse/importarse por CSV. Este cambio no agrega cuentas ni persistencia de usuario en Supabase.
