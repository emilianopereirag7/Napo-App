-- NAPO · tablas nuevas (medición de uso y noticias en Shorts)
-- Pegar en Supabase > SQL Editor > New query > Run.
-- No toca la tabla de reportes que ya tenés.

create table if not exists public.eventos (
  id bigint generated always as identity primary key,
  creado timestamptz not null default now(),
  tipo text not null,
  detalle text not null default '',
  sesion text not null default ''
);
create index if not exists eventos_creado_idx on public.eventos (creado desc);
alter table public.eventos enable row level security;

create table if not exists public.noticias_shorts (
  id bigint generated always as identity primary key,
  creado timestamptz not null default now(),
  video_id text not null unique,
  titulo text not null,
  canal text not null default '',
  nota text not null default ''
);
create index if not exists noticias_shorts_creado_idx on public.noticias_shorts (creado desc);
alter table public.noticias_shorts enable row level security;
