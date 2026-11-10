create extension if not exists pgcrypto;

create table if not exists public.jaguar_memories (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    kind text not null check (
        kind in ('project', 'preference', 'decision', 'task_result', 'procedure')
    ),
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    importance real not null default 0.5 check (importance between 0 and 1),
    confidence real not null default 1.0 check (confidence between 0 and 1),
    search_vector tsvector generated always as (
        to_tsvector('english', coalesce(content, ''))
    ) stored,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists jaguar_memories_user_created_idx
    on public.jaguar_memories (user_id, created_at desc);
create index if not exists jaguar_memories_search_idx
    on public.jaguar_memories using gin (search_vector);

create table if not exists public.jaguar_preferences (
    user_id text primary key,
    preferences jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists public.jaguar_task_results (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    kind text not null,
    title text not null,
    detail text not null default '',
    status text not null default 'ok',
    created_at timestamptz not null default now()
);

create index if not exists jaguar_task_results_user_created_idx
    on public.jaguar_task_results (user_id, created_at desc);

alter table public.jaguar_memories enable row level security;
alter table public.jaguar_preferences enable row level security;
alter table public.jaguar_task_results enable row level security;

revoke all on public.jaguar_memories from anon, authenticated;
revoke all on public.jaguar_preferences from anon, authenticated;
revoke all on public.jaguar_task_results from anon, authenticated;
grant all on public.jaguar_memories to service_role;
grant all on public.jaguar_preferences to service_role;
grant all on public.jaguar_task_results to service_role;

create or replace function public.search_jaguar_memories(
    p_user_id text,
    p_query text,
    p_limit integer default 4,
    p_kind text default null
)
returns table (
    id uuid,
    kind text,
    content text,
    metadata jsonb,
    importance real,
    confidence real,
    created_at timestamptz,
    score real
)
language sql
stable
set search_path = public, pg_temp
as $$
    select
        m.id,
        m.kind,
        m.content,
        m.metadata,
        m.importance,
        m.confidence,
        m.created_at,
        ts_rank_cd(m.search_vector, query.query)::real as score
    from public.jaguar_memories as m
    cross join lateral (
        select websearch_to_tsquery('english', coalesce(p_query, '')) as value
    ) as query
    where m.user_id = p_user_id
      and m.search_vector @@ query.value
      and (p_kind is null or m.kind = p_kind)
    order by ts_rank_cd(m.search_vector, query.value) desc,
             m.importance desc,
             m.created_at desc
    limit greatest(1, least(coalesce(p_limit, 4), 50));
$$;

revoke all on function public.search_jaguar_memories(text, text, integer, text)
    from public, anon, authenticated;
grant execute on function public.search_jaguar_memories(text, text, integer, text)
    to service_role;
