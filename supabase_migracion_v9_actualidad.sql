-- ============================================================================
-- NAPO | Migración v9: modelo editorial de Actualidad
--
-- OBJETIVO
--   Crear la estructura persistente para acontecimientos, fuentes, historial,
--   relaciones con activos y vínculos entre acontecimientos.
--
-- SEGURIDAD
--   Estas tablas son de uso EXCLUSIVO del backend de confianza (Streamlit).
--   Se habilita RLS y se revocan permisos de PUBLIC, anon y authenticated.
--   Se otorgan permisos al rol service_role, que debe usarse SOLO desde Secrets
--   del servidor. Nunca colocar una clave secreta en GitHub ni en el navegador.
--
-- ALCANCE
--   - No modifica ni borra reportes, eventos (analítica), noticias_shorts ni
--     ninguna otra tabla existente.
--   - No inserta noticias ficticias ni datos de demostración.
--   - No conecta todavía la interfaz de Streamlit con estas tablas.
--   - Las actualizaciones editoriales son append-only desde la API REST:
--     service_role puede leer e insertar, pero no editar ni borrar historial.
--
-- EJECUCIÓN
--   Supabase Dashboard > SQL Editor > New query > pegar el archivo completo.
--   Ejecutar una sola vez. Es una migración aditiva e idempotente en sus objetos
--   principales; no usarla para intentar reparar manualmente tablas homónimas.
-- ============================================================================

begin;

-- 1. ACONTECIMIENTOS ---------------------------------------------------------
-- Un acontecimiento representa una historia/noticia persistente. Sus cambios
-- se registran en actualidad_actualizaciones, no sobrescribiendo el historial.

create table if not exists public.actualidad_eventos (
    id uuid primary key default gen_random_uuid(),
    titular text not null check (length(btrim(titular)) > 0),
    resumen_actual text not null default '',

    alcance text not null default 'empresa'
        check (alcance in ('global', 'pais', 'sector', 'empresa', 'instrumento')),
    paises text[] not null default array[]::text[],
    sectores text[] not null default array[]::text[],

    estado_editorial text not null default 'en_verificacion'
        check (estado_editorial in (
            'en_verificacion', 'reportada', 'confirmada', 'en_desarrollo',
            'actualizada', 'desmentida', 'retirada'
        )),
    -- La vigencia es distinta del estado editorial:
    -- una historia puede estar confirmada y luego cerrarse sin ser falsa.
    vigencia text not null default 'activa'
        check (vigencia in ('activa', 'cerrada', 'archivada')),
    importancia text not null default 'media'
        check (importancia in ('alta', 'media', 'baja')),

    fecha_acontecimiento timestamptz,
    publicado_en timestamptz,
    idioma_redaccion text not null default 'es-AR',
    origen_ingesta text not null default 'manual'
        check (origen_ingesta in ('manual', 'api', 'rss', 'importado')),
    clave_deduplicacion text,
    requiere_revision boolean not null default true,
    publicable boolean not null default false,
    notas_editoriales_internas text not null default '',

    creado_en timestamptz not null default now(),
    actualizado_en timestamptz not null default now(),
    version integer not null default 1 check (version >= 1)
);

create index if not exists actualidad_eventos_actualizado_idx
    on public.actualidad_eventos (actualizado_en desc);
create index if not exists actualidad_eventos_estado_vigencia_idx
    on public.actualidad_eventos (estado_editorial, vigencia, publicable);
create index if not exists actualidad_eventos_paises_gin_idx
    on public.actualidad_eventos using gin (paises);
create index if not exists actualidad_eventos_sectores_gin_idx
    on public.actualidad_eventos using gin (sectores);
create index if not exists actualidad_eventos_dedup_idx
    on public.actualidad_eventos (clave_deduplicacion)
    where clave_deduplicacion is not null;

-- 2. FUENTES -----------------------------------------------------------------
-- Una fila representa una publicación/documento concreto, no solo el nombre
-- del medio. Se conserva la URL original y sus fechas para poder auditarla.
-- No almacenamos el artículo completo: guardamos metadatos y notas breves.

create table if not exists public.actualidad_fuentes (
    id uuid primary key default gen_random_uuid(),
    tipo_fuente text not null
        check (tipo_fuente in ('primaria', 'periodistica', 'mercado')),
    nombre_fuente text not null check (length(btrim(nombre_fuente)) > 0),
    titulo_original text not null check (length(btrim(titulo_original)) > 0),
    url text not null unique check (url ~* '^https?://'),
    dominio text not null default '',
    idioma text not null default '',
    publicado_en timestamptz,
    consultado_en timestamptz not null default now(),
    estado_fuente text not null default 'activa'
        check (estado_fuente in ('activa', 'retirada', 'reemplazada')),
    nota_verificacion text not null default '',
    creado_en timestamptz not null default now()
);

create index if not exists actualidad_fuentes_publicado_idx
    on public.actualidad_fuentes (publicado_en desc);
create index if not exists actualidad_fuentes_tipo_idx
    on public.actualidad_fuentes (tipo_fuente, consultado_en desc);

-- 3. ACTUALIZACIONES ---------------------------------------------------------
-- Cada corrección, confirmación, desmentida o novedad agrega una fila nueva.
-- No se permite UPDATE/DELETE desde service_role por la API REST.

create table if not exists public.actualidad_actualizaciones (
    id uuid primary key default gen_random_uuid(),
    orden bigint generated always as identity unique,
    evento_id uuid not null
        references public.actualidad_eventos(id) on delete restrict,
    tipo_cambio text not null
        check (tipo_cambio in (
            'publicacion_inicial', 'contexto', 'corroboracion', 'confirmacion',
            'respuesta_oficial', 'desmentida', 'correccion', 'cierre', 'otro'
        )),
    titulo text not null check (length(btrim(titulo)) > 0),
    detalle text not null check (length(btrim(detalle)) > 0),
    estado_resultante text not null
        check (estado_resultante in (
            'en_verificacion', 'reportada', 'confirmada', 'en_desarrollo',
            'actualizada', 'desmentida', 'retirada'
        )),
    vigencia_resultante text not null default 'activa'
        check (vigencia_resultante in ('activa', 'cerrada', 'archivada')),
    fecha_informacion timestamptz,
    requiere_revision boolean not null default true,
    nota_editorial_interna text not null default '',
    creado_en timestamptz not null default now()
);

create index if not exists actualidad_actualizaciones_evento_fecha_idx
    on public.actualidad_actualizaciones (evento_id, creado_en desc, orden desc);
create index if not exists actualidad_actualizaciones_fecha_idx
    on public.actualidad_actualizaciones (creado_en desc);

-- Cada actualización insertada sincroniza el estado visible del acontecimiento
-- con la actualización de fecha más reciente. La historia anterior no se toca.
create or replace function public.actualidad_sincronizar_evento_desde_actualizacion()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    update public.actualidad_eventos as e
       set estado_editorial = ultima.estado_resultante,
           vigencia = ultima.vigencia_resultante,
           actualizado_en = ultima.creado_en,
           version = e.version + 1
      from (
          select a.estado_resultante, a.vigencia_resultante, a.creado_en
            from public.actualidad_actualizaciones as a
           where a.evento_id = new.evento_id
           order by a.creado_en desc, a.orden desc
           limit 1
      ) as ultima
     where e.id = new.evento_id;

    return new;
end;
$$;

drop trigger if exists actualidad_actualizaciones_sync_evento
    on public.actualidad_actualizaciones;
create trigger actualidad_actualizaciones_sync_evento
after insert on public.actualidad_actualizaciones
for each row execute function public.actualidad_sincronizar_evento_desde_actualizacion();

-- 4. FUENTES DEL ACONTECIMIENTO ---------------------------------------------
-- Relación general entre el acontecimiento y las publicaciones utilizadas.

create table if not exists public.actualidad_evento_fuentes (
    evento_id uuid not null
        references public.actualidad_eventos(id) on delete restrict,
    fuente_id uuid not null
        references public.actualidad_fuentes(id) on delete restrict,
    funcion text not null default 'contexto'
        check (funcion in (
            'fuente_inicial', 'corroboracion', 'contexto',
            'respuesta_oficial', 'rectificacion', 'contrapunto'
        )),
    nota_editorial text not null default '',
    vigente boolean not null default true,
    creado_en timestamptz not null default now(),
    primary key (evento_id, fuente_id, funcion)
);

create index if not exists actualidad_evento_fuentes_fuente_idx
    on public.actualidad_evento_fuentes (fuente_id);

-- 5. FUENTES DE CADA ACTUALIZACIÓN ------------------------------------------
-- Permite saber qué documento respalda específicamente una desmentida,
-- confirmación o corrección; no solo qué fuentes estuvieron asociadas al caso.

create table if not exists public.actualidad_actualizacion_fuentes (
    actualizacion_id uuid not null
        references public.actualidad_actualizaciones(id) on delete restrict,
    fuente_id uuid not null
        references public.actualidad_fuentes(id) on delete restrict,
    funcion text not null default 'contexto'
        check (funcion in (
            'fuente_inicial', 'corroboracion', 'contexto',
            'respuesta_oficial', 'rectificacion', 'contrapunto'
        )),
    nota_editorial text not null default '',
    creado_en timestamptz not null default now(),
    primary key (actualizacion_id, fuente_id, funcion)
);

create index if not exists actualidad_actualizacion_fuentes_fuente_idx
    on public.actualidad_actualizacion_fuentes (fuente_id);

-- 6. ACTIVOS VINCULADOS ------------------------------------------------------
-- El vínculo es explícito y exige una justificación editorial. Compartir sector
-- no alcanza para asociar automáticamente una noticia a otro ticker.

create table if not exists public.actualidad_evento_activos (
    evento_id uuid not null
        references public.actualidad_eventos(id) on delete restrict,
    ticker text not null check (ticker = upper(btrim(ticker)) and length(ticker) > 0),
    nombre_activo text not null default '',
    mercado text not null default '',
    tipo_vinculo text not null default 'directo'
        check (tipo_vinculo in ('directo', 'transversal', 'referencia', 'benchmark')),
    relevancia text not null default 'media'
        check (relevancia in ('alta', 'media', 'baja')),
    justificacion text not null check (length(btrim(justificacion)) > 0),
    vigente boolean not null default true,
    creado_en timestamptz not null default now(),
    primary key (evento_id, ticker)
);

create index if not exists actualidad_evento_activos_ticker_idx
    on public.actualidad_evento_activos (ticker, vigente, evento_id);

-- 7. RELACIONES ENTRE ACONTECIMIENTOS ---------------------------------------
-- Una nueva historia puede estar relacionada con otra sin fusionar sus
-- historiales. Ej.: respuesta posterior, aclaración o hecho independiente.

create table if not exists public.actualidad_evento_relaciones (
    evento_id uuid not null
        references public.actualidad_eventos(id) on delete restrict,
    evento_relacionado_id uuid not null
        references public.actualidad_eventos(id) on delete restrict,
    tipo_relacion text not null
        check (tipo_relacion in (
            'relacionado', 'respuesta_a', 'aclara', 'contradice', 'deriva_de'
        )),
    nota text not null default '',
    vigente boolean not null default true,
    creado_en timestamptz not null default now(),
    primary key (evento_id, evento_relacionado_id, tipo_relacion),
    check (evento_id <> evento_relacionado_id)
);

create index if not exists actualidad_evento_relaciones_relacionado_idx
    on public.actualidad_evento_relaciones (evento_relacionado_id);

-- 8. SEGURIDAD ---------------------------------------------------------------
-- Todas las tablas quedan cerradas para accesos directos anon/authenticated.
-- La interfaz Streamlit lee/escribe del lado servidor con SUPABASE_KEY.
-- La clave debe ser secret/service_role y permanecer exclusivamente en Secrets.

alter table public.actualidad_eventos enable row level security;
alter table public.actualidad_fuentes enable row level security;
alter table public.actualidad_actualizaciones enable row level security;
alter table public.actualidad_evento_fuentes enable row level security;
alter table public.actualidad_actualizacion_fuentes enable row level security;
alter table public.actualidad_evento_activos enable row level security;
alter table public.actualidad_evento_relaciones enable row level security;

revoke all privileges on table
    public.actualidad_eventos,
    public.actualidad_fuentes,
    public.actualidad_actualizaciones,
    public.actualidad_evento_fuentes,
    public.actualidad_actualizacion_fuentes,
    public.actualidad_evento_activos,
    public.actualidad_evento_relaciones
from public, anon, authenticated, service_role;

-- Backend: permisos mínimos explícitos desde Streamlit/servicios de confianza.
-- Primero se revocan también posibles permisos heredados por DEFAULT PRIVILEGES;
-- luego se concede únicamente lo que necesita cada tabla.
grant usage on schema public to service_role;
grant select, insert, update on table public.actualidad_eventos to service_role;
grant select, insert on table public.actualidad_fuentes to service_role;
grant select, insert on table public.actualidad_actualizaciones to service_role;
grant select, insert, update on table public.actualidad_evento_fuentes to service_role;
grant select, insert on table public.actualidad_actualizacion_fuentes to service_role;
grant select, insert, update on table public.actualidad_evento_activos to service_role;
grant select, insert, update on table public.actualidad_evento_relaciones to service_role;

-- La columna identity `orden` posee una secuencia propia. Revocamos cualquier
-- permiso por defecto y concedemos solo USAGE/SELECT al backend.
do $$
declare
    v_secuencia regclass;
begin
    v_secuencia := pg_get_serial_sequence(
        'public.actualidad_actualizaciones', 'orden'
    )::regclass;

    if v_secuencia is null then
        raise exception 'No se encontró la secuencia identity de actualidad_actualizaciones.orden';
    end if;

    execute format(
        'revoke all privileges on sequence %s from PUBLIC, anon, authenticated, service_role',
        v_secuencia
    );
    execute format(
        'grant usage, select on sequence %s to service_role',
        v_secuencia
    );
end;
$$;

grant execute on function public.actualidad_sincronizar_evento_desde_actualizacion() to service_role;
revoke execute on function public.actualidad_sincronizar_evento_desde_actualizacion() from public, anon, authenticated;

commit;

-- NOTA: no se crean políticas anon/authenticated deliberadamente. La publicación
-- pública, si se decide más adelante, debe hacerse mediante una vista/endpoint
-- que exponga únicamente campos editoriales aprobados, nunca notas internas.
