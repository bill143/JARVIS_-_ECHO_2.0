-- ECHO/JARVIS memory schema for Supabase (Postgres + pgvector).
-- Run once in the Supabase SQL editor (or via `supabase db` migrations).
-- The embedding dimension MUST match EMBEDDINGS_DIM used by the app
-- (1536 = OpenAI text-embedding-3-small; change here AND in env if you differ).

create extension if not exists vector;

create table if not exists memories (
    id          text primary key,
    content     text not null,
    metadata    jsonb not null default '{}'::jsonb,
    embedding   vector(1536),
    created_at  timestamptz not null default now()
);

-- Approximate-nearest-neighbour index for fast cosine search.
create index if not exists memories_embedding_idx
    on memories using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create index if not exists memories_created_at_idx
    on memories (created_at desc);

-- Cosine-similarity recall. Returns the closest matches with a similarity score
-- in [0, 1] (1 = identical direction).
create or replace function match_memories(
    query_embedding vector(1536),
    match_count int default 5
)
returns table (
    id text,
    content text,
    metadata jsonb,
    created_at timestamptz,
    similarity float
)
language sql stable
as $$
    select
        m.id,
        m.content,
        m.metadata,
        m.created_at,
        1 - (m.embedding <=> query_embedding) as similarity
    from memories m
    where m.embedding is not null
    order by m.embedding <=> query_embedding
    limit match_count;
$$;
