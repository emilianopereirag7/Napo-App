-- Verificación de las tres funciones RPC de La Cocina de Actualidad.
-- Solo lectura. No crea ni modifica registros.

select
    p.proname as funcion,
    has_function_privilege('service_role', p.oid, 'EXECUTE') as service_role_puede_ejecutar,
    has_function_privilege('anon', p.oid, 'EXECUTE') as anon_puede_ejecutar,
    has_function_privilege('authenticated', p.oid, 'EXECUTE') as authenticated_puede_ejecutar
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname in (
      'actualidad_guardar_evento_editorial',
      'actualidad_publicar_evento_editorial',
      'actualidad_agregar_actualizacion_editorial'
  )
order by p.proname;
