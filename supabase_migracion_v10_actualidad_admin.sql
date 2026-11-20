-- ============================================================================
-- NAPO | Migración v10: operaciones editoriales transaccionales de Actualidad
--
-- Requisito: migración v9 de Actualidad ya aplicada.
-- Esta migración NO crea ni modifica tablas. Agrega funciones RPC para que
-- La Cocina pueda crear acontecimientos, publicar y anexar actualizaciones
-- sin dejar registros parciales si una operación falla.
--
-- Seguridad:
--   - SECURITY INVOKER: opera con los permisos del rol que llama.
--   - Solo service_role puede ejecutar las funciones.
--   - No se habilita acceso para anon ni authenticated.
--   - La clave sb_secret_/service_role debe quedar en Streamlit Secrets.
-- ============================================================================

begin;

-- 1. Crear un acontecimiento completo en una sola transacción.
-- p_evento: titular, resumen_actual, alcance, paises[], sectores[],
--           estado_editorial, importancia, idioma_redaccion,
--           notas_editoriales_internas.
-- p_fuente: metadatos de la fuente inicial + funcion + nota_editorial.
-- p_actualizacion: tipo_cambio, titulo, detalle, estado_resultante,
--                  vigencia_resultante.
-- p_activos: array de {ticker, nombre_activo, mercado, tipo_vinculo,
--                      relevancia, justificacion}.

create or replace function public.actualidad_guardar_evento_editorial(
    p_evento jsonb,
    p_fuente jsonb,
    p_actualizacion jsonb,
    p_activos jsonb default '[]'::jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $function$
declare
    v_evento_id uuid;
    v_fuente_id uuid;
    v_actualizacion_id uuid;
    v_activo jsonb;
    v_paises text[];
    v_sectores text[];
    v_url text;
begin
    if jsonb_typeof(p_evento) <> 'object'
       or jsonb_typeof(p_fuente) <> 'object'
       or jsonb_typeof(p_actualizacion) <> 'object' then
        raise exception 'Los datos del acontecimiento, fuente y actualización deben ser objetos JSON.';
    end if;

    if jsonb_typeof(coalesce(p_activos, '[]'::jsonb)) <> 'array' then
        raise exception 'Los activos vinculados deben enviarse como un array JSON.';
    end if;

    if nullif(btrim(p_evento->>'titular'), '') is null then
        raise exception 'El titular es obligatorio.';
    end if;
    if nullif(btrim(p_fuente->>'nombre_fuente'), '') is null
       or nullif(btrim(p_fuente->>'titulo_original'), '') is null then
        raise exception 'La fuente necesita nombre y título original.';
    end if;
    v_url := btrim(coalesce(p_fuente->>'url', ''));
    if v_url !~* '^https?://' then
        raise exception 'La fuente necesita una URL http o https válida.';
    end if;

    select coalesce(array_agg(x), array[]::text[])
      into v_paises
      from jsonb_array_elements_text(coalesce(p_evento->'paises', '[]'::jsonb)) as t(x);

    select coalesce(array_agg(x), array[]::text[])
      into v_sectores
      from jsonb_array_elements_text(coalesce(p_evento->'sectores', '[]'::jsonb)) as t(x);

    insert into public.actualidad_eventos (
        titular, resumen_actual, alcance, paises, sectores,
        estado_editorial, vigencia, importancia, idioma_redaccion,
        origen_ingesta, requiere_revision, publicable,
        notas_editoriales_internas
    ) values (
        btrim(p_evento->>'titular'),
        coalesce(p_evento->>'resumen_actual', ''),
        coalesce(nullif(p_evento->>'alcance', ''), 'empresa'),
        v_paises,
        v_sectores,
        coalesce(nullif(p_evento->>'estado_editorial', ''), 'reportada'),
        coalesce(nullif(p_evento->>'vigencia', ''), 'activa'),
        coalesce(nullif(p_evento->>'importancia', ''), 'media'),
        coalesce(nullif(p_evento->>'idioma_redaccion', ''), 'es-AR'),
        'manual',
        true,
        false,
        coalesce(p_evento->>'notas_editoriales_internas', '')
    ) returning id into v_evento_id;

    -- La fuente es un documento concreto. Si la URL ya existe, se reutiliza
    -- el registro sin sobrescribir sus metadatos originales.
    insert into public.actualidad_fuentes (
        tipo_fuente, nombre_fuente, titulo_original, url, dominio,
        idioma, nota_verificacion
    ) values (
        coalesce(nullif(p_fuente->>'tipo_fuente', ''), 'periodistica'),
        btrim(p_fuente->>'nombre_fuente'),
        btrim(p_fuente->>'titulo_original'),
        v_url,
        coalesce(p_fuente->>'dominio', ''),
        coalesce(p_fuente->>'idioma', ''),
        coalesce(p_fuente->>'nota_verificacion', '')
    ) on conflict (url) do nothing
    returning id into v_fuente_id;

    if v_fuente_id is null then
        select id into v_fuente_id
          from public.actualidad_fuentes
         where url = v_url;
    end if;

    insert into public.actualidad_evento_fuentes (
        evento_id, fuente_id, funcion, nota_editorial, vigente
    ) values (
        v_evento_id, v_fuente_id,
        coalesce(nullif(p_fuente->>'funcion', ''), 'fuente_inicial'),
        coalesce(p_fuente->>'nota_editorial', ''), true
    ) on conflict do nothing;

    insert into public.actualidad_actualizaciones (
        evento_id, tipo_cambio, titulo, detalle,
        estado_resultante, vigencia_resultante,
        fecha_informacion, requiere_revision, nota_editorial_interna
    ) values (
        v_evento_id,
        coalesce(nullif(p_actualizacion->>'tipo_cambio', ''), 'publicacion_inicial'),
        coalesce(nullif(p_actualizacion->>'titulo', ''), 'Publicación inicial'),
        btrim(coalesce(p_actualizacion->>'detalle', '')),
        coalesce(nullif(p_actualizacion->>'estado_resultante', ''), 'reportada'),
        coalesce(nullif(p_actualizacion->>'vigencia_resultante', ''), 'activa'),
        nullif(p_actualizacion->>'fecha_informacion', '')::timestamptz,
        false,
        coalesce(p_actualizacion->>'nota_editorial_interna', '')
    ) returning id into v_actualizacion_id;

    insert into public.actualidad_actualizacion_fuentes (
        actualizacion_id, fuente_id, funcion, nota_editorial
    ) values (
        v_actualizacion_id, v_fuente_id,
        coalesce(nullif(p_fuente->>'funcion', ''), 'fuente_inicial'),
        coalesce(p_fuente->>'nota_editorial', '')
    ) on conflict do nothing;

    for v_activo in
        select value from jsonb_array_elements(coalesce(p_activos, '[]'::jsonb))
    loop
        insert into public.actualidad_evento_activos (
            evento_id, ticker, nombre_activo, mercado,
            tipo_vinculo, relevancia, justificacion, vigente
        ) values (
            v_evento_id,
            upper(btrim(v_activo->>'ticker')),
            coalesce(v_activo->>'nombre_activo', ''),
            coalesce(v_activo->>'mercado', ''),
            coalesce(nullif(v_activo->>'tipo_vinculo', ''), 'directo'),
            coalesce(nullif(v_activo->>'relevancia', ''), 'alta'),
            btrim(coalesce(v_activo->>'justificacion', '')),
            true
        ) on conflict (evento_id, ticker) do nothing;
    end loop;

    return jsonb_build_object(
        'evento_id', v_evento_id,
        'fuente_id', v_fuente_id,
        'actualizacion_id', v_actualizacion_id,
        'estado', 'borrador',
        'publicable', false
    );
end;
$function$;

-- 2. Publicar un acontecimiento luego de la revisión humana.
-- No permite publicar historias que siguen en_verificacion.

create or replace function public.actualidad_publicar_evento_editorial(p_evento_id uuid)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $function$
declare
    v_evento public.actualidad_eventos%rowtype;
begin
    select * into v_evento
      from public.actualidad_eventos
     where id = p_evento_id
     for update;

    if not found then
        raise exception 'No existe el acontecimiento solicitado.';
    end if;
    if v_evento.publicable then
        return jsonb_build_object('evento_id', p_evento_id, 'publicable', true, 'mensaje', 'Ya estaba publicado.');
    end if;
    if v_evento.estado_editorial = 'en_verificacion' then
        raise exception 'No se puede publicar un acontecimiento que sigue en verificación.';
    end if;
    if v_evento.vigencia = 'archivada' then
        raise exception 'No se puede publicar un acontecimiento archivado.';
    end if;
    if not exists (
        select 1 from public.actualidad_evento_fuentes ef
         where ef.evento_id = p_evento_id and ef.vigente = true
    ) then
        raise exception 'El acontecimiento necesita al menos una fuente vigente.';
    end if;
    if not exists (
        select 1 from public.actualidad_actualizaciones a
         where a.evento_id = p_evento_id and a.requiere_revision = false
    ) then
        raise exception 'El acontecimiento necesita una actualización revisada.';
    end if;

    update public.actualidad_eventos
       set publicable = true,
           requiere_revision = false,
           publicado_en = coalesce(publicado_en, now()),
           actualizado_en = now(),
           version = version + 1
     where id = p_evento_id;

    return jsonb_build_object('evento_id', p_evento_id, 'publicable', true, 'mensaje', 'Publicado.');
end;
$function$;

-- 3. Agregar una actualización con su fuente en una sola transacción.
-- El historial anterior se conserva: solo se insertan filas nuevas.

create or replace function public.actualidad_agregar_actualizacion_editorial(
    p_evento_id uuid,
    p_actualizacion jsonb,
    p_fuente jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $function$
declare
    v_fuente_id uuid;
    v_actualizacion_id uuid;
    v_url text;
begin
    if not exists (select 1 from public.actualidad_eventos where id = p_evento_id) then
        raise exception 'No existe el acontecimiento seleccionado.';
    end if;
    if jsonb_typeof(p_actualizacion) <> 'object' or jsonb_typeof(p_fuente) <> 'object' then
        raise exception 'La actualización y la fuente deben ser objetos JSON.';
    end if;
    if nullif(btrim(p_actualizacion->>'titulo'), '') is null
       or nullif(btrim(p_actualizacion->>'detalle'), '') is null then
        raise exception 'La actualización necesita título y detalle.';
    end if;
    if nullif(btrim(p_fuente->>'nombre_fuente'), '') is null
       or nullif(btrim(p_fuente->>'titulo_original'), '') is null then
        raise exception 'La fuente necesita nombre y título original.';
    end if;

    v_url := btrim(coalesce(p_fuente->>'url', ''));
    if v_url !~* '^https?://' then
        raise exception 'La fuente necesita una URL http o https válida.';
    end if;

    insert into public.actualidad_fuentes (
        tipo_fuente, nombre_fuente, titulo_original, url, dominio,
        idioma, nota_verificacion
    ) values (
        coalesce(nullif(p_fuente->>'tipo_fuente', ''), 'periodistica'),
        btrim(p_fuente->>'nombre_fuente'),
        btrim(p_fuente->>'titulo_original'),
        v_url,
        coalesce(p_fuente->>'dominio', ''),
        coalesce(p_fuente->>'idioma', ''),
        coalesce(p_fuente->>'nota_verificacion', '')
    ) on conflict (url) do nothing
    returning id into v_fuente_id;

    if v_fuente_id is null then
        select id into v_fuente_id
          from public.actualidad_fuentes
         where url = v_url;
    end if;

    insert into public.actualidad_actualizaciones (
        evento_id, tipo_cambio, titulo, detalle,
        estado_resultante, vigencia_resultante,
        fecha_informacion, requiere_revision, nota_editorial_interna
    ) values (
        p_evento_id,
        coalesce(nullif(p_actualizacion->>'tipo_cambio', ''), 'otro'),
        btrim(p_actualizacion->>'titulo'),
        btrim(p_actualizacion->>'detalle'),
        coalesce(nullif(p_actualizacion->>'estado_resultante', ''), 'en_desarrollo'),
        coalesce(nullif(p_actualizacion->>'vigencia_resultante', ''), 'activa'),
        nullif(p_actualizacion->>'fecha_informacion', '')::timestamptz,
        false,
        coalesce(p_actualizacion->>'nota_editorial_interna', '')
    ) returning id into v_actualizacion_id;

    insert into public.actualidad_actualizacion_fuentes (
        actualizacion_id, fuente_id, funcion, nota_editorial
    ) values (
        v_actualizacion_id, v_fuente_id,
        coalesce(nullif(p_fuente->>'funcion', ''), 'contexto'),
        coalesce(p_fuente->>'nota_editorial', '')
    ) on conflict do nothing;

    update public.actualidad_eventos
       set resumen_actual = coalesce(nullif(p_actualizacion->>'resumen_actual', ''), resumen_actual)
     where id = p_evento_id;

    return jsonb_build_object(
        'evento_id', p_evento_id,
        'fuente_id', v_fuente_id,
        'actualizacion_id', v_actualizacion_id,
        'mensaje', 'Actualización agregada.'
    );
end;
$function$;

-- 4. Cerrar ejecución pública: solo la clave privada del backend puede llamar.
revoke all on function public.actualidad_guardar_evento_editorial(jsonb, jsonb, jsonb, jsonb)
    from public, anon, authenticated;
revoke all on function public.actualidad_publicar_evento_editorial(uuid)
    from public, anon, authenticated;
revoke all on function public.actualidad_agregar_actualizacion_editorial(uuid, jsonb, jsonb)
    from public, anon, authenticated;

grant execute on function public.actualidad_guardar_evento_editorial(jsonb, jsonb, jsonb, jsonb)
    to service_role;
grant execute on function public.actualidad_publicar_evento_editorial(uuid)
    to service_role;
grant execute on function public.actualidad_agregar_actualizacion_editorial(uuid, jsonb, jsonb)
    to service_role;

notify pgrst, 'reload schema';

commit;
