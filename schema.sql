-- ============================================================
-- askthispodcast.com — Supabase schema
-- Run this in your Supabase SQL editor
-- ============================================================

-- Enable the pgvector extension (one-time, per project)
create extension if not exists vector;

-- ── Podcasts ─────────────────────────────────────────────────
create table podcasts (
  id          uuid primary key default gen_random_uuid(),
  slug        text unique not null,          -- e.g. "my-podcast"
  title       text not null,
  description text,
  created_at  timestamptz default now()
);

-- ── Episodes ─────────────────────────────────────────────────
create table episodes (
  id             uuid primary key default gen_random_uuid(),
  podcast_id     uuid references podcasts(id) on delete cascade,
  episode_number int,                -- null for unnumbered episodes (teasers, season 2+)
  title          text not null,
  source_file    text not null,      -- transcript filename; stable identity for re-runs
  published_at   date,
  created_at     timestamptz default now(),
  unique (podcast_id, source_file)
);

-- ── Chunks ───────────────────────────────────────────────────
-- One row per ~500-word segment of a transcript
create table chunks (
  id           uuid primary key default gen_random_uuid(),
  podcast_id   uuid references podcasts(id) on delete cascade,
  episode_id   uuid references episodes(id) on delete cascade,
  chunk_index  int,                          -- order within episode
  content      text not null,               -- raw transcript text
  embedding    vector(1536),                -- OpenAI text-embedding-3-small
  created_at   timestamptz default now()
);

-- ── Vector similarity index ───────────────────────────────────
-- HNSW: unlike IVFFlat it needs no training data, so it can be
-- created before ingestion without hurting recall
create index on chunks
  using hnsw (embedding vector_cosine_ops);

-- ── Similarity search function ────────────────────────────────
-- Called from your backend: match_chunks(query_embedding, podcast_id, k)
create or replace function match_chunks(
  query_embedding vector(1536),
  filter_podcast_id uuid,
  match_count int default 8
)
returns table (
  episode_title   text,
  episode_number  int,
  published_at    date,
  chunk_index     int,
  content         text,
  similarity      float
)
language sql stable
as $$
  select
    e.title        as episode_title,
    e.episode_number,
    e.published_at,
    c.chunk_index,
    c.content,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  join episodes e on e.id = c.episode_id
  where c.podcast_id = filter_podcast_id
  order by c.embedding <=> query_embedding
  limit match_count;
$$;
