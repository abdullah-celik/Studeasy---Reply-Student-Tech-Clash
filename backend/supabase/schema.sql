-- Studeasy schema. Idempotent: safe to re-run in the Supabase SQL editor after updates.
-- Every table carries user_id so Row Level Security can scope rows to the student.
-- The backend uses the service-role key (bypasses RLS) and filters by user_id itself;
-- RLS protects the data if the frontend ever reads tables directly with supabase-js.

-- pgvector lives in the extensions schema (Supabase best practice).
create extension if not exists vector with schema extensions;

-- Courses ------------------------------------------------------------------
create table if not exists courses (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    name        text not null,
    description text,
    created_at  timestamptz not null default now()
);

-- Uploaded documents (originals are NOT stored, only their text chunks) ------
create table if not exists documents (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    filename    text not null,
    status      text not null default 'processing'
                check (status in ('processing', 'ready', 'failed')),
    chunk_count int  not null default 0,
    error       text,
    created_at  timestamptz not null default now()
);

-- Text chunks + embeddings ---------------------------------------------------
-- The vector size must match the AI provider: 1024 for Mistral (mistral-embed),
-- 1536 for OpenAI (text-embedding-3-small). To switch provider, replace every 1024 in this file.
-- Embedding is nullable: after a switch the backend re-embeds rows that have none.
create table if not exists chunks (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    content     text not null,
    location    text not null,          -- e.g. "page 3", "slide 7", "section: Intro"
    embedding   extensions.vector(1024)
);
create index if not exists chunks_course_idx on chunks (course_id);

-- Existing databases: resize the column if the provider changed. Keeps the chunk text,
-- clears the old vectors (the backend fills them in again on startup).
do $$
begin
    alter table chunks alter column embedding drop not null;
    if (select atttypmod from pg_attribute
        where attrelid = 'public.chunks'::regclass and attname = 'embedding') <> 1024 then
        drop index if exists chunks_embedding_idx;
        alter table chunks alter column embedding type extensions.vector(1024) using null;
    end if;
end $$;
create index if not exists chunks_embedding_idx on chunks using hnsw (embedding extensions.vector_cosine_ops);

-- Mastery map: one row per (student, course, concept) ----------------------
create table if not exists mastery (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    concept     text not null,
    score       real not null default 0,  -- 0..1
    attempts    int  not null default 0,
    updated_at  timestamptz not null default now(),
    unique (user_id, course_id, concept)
);

-- Quizzes ------------------------------------------------------------------
create table if not exists quizzes (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    topic       text,
    created_at  timestamptz not null default now()
);

create table if not exists questions (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users(id) on delete cascade,
    quiz_id          uuid not null references quizzes(id) on delete cascade,
    type             text not null check (type in ('multiple_choice', 'true_false', 'open')),
    prompt           text not null,
    options          jsonb not null default '[]'::jsonb,
    answer           text not null,      -- never sent to the client before answering
    explanation      text not null,
    concept          text not null,
    source_chunk_ids uuid[] not null default '{}',
    position         int not null default 0
);

create table if not exists answers (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    question_id uuid not null references questions(id) on delete cascade,
    response    text not null,
    correct     boolean not null,
    score       real not null,
    feedback    text not null,
    created_at  timestamptz not null default now()
);

-- Flashcards with SM-2 scheduling state ------------------------------------
create table if not exists flashcards (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    front       text not null,
    back        text not null,
    concept     text not null,
    ease        real not null default 2.5,
    interval    int  not null default 0,   -- days
    repetitions int  not null default 0,
    due_at      timestamptz not null default now(),
    created_at  timestamptz not null default now()
);
create index if not exists flashcards_due_idx on flashcards (user_id, course_id, due_at);

-- Exams (drive the study planner) ------------------------------------------
create table if not exists exams (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    title       text not null,
    exam_date   date not null,
    created_at  timestamptz not null default now()
);

-- Chat history (used as conversation memory for the tutor) -----------------
create table if not exists chat_messages (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    role        text not null check (role in ('user', 'assistant')),
    content     text not null,
    created_at  timestamptz not null default now()
);
create index if not exists chat_messages_course_idx on chat_messages (course_id, created_at);

-- Student preferences (opt-in switches for optional modules) ---------------
create table if not exists user_preferences (
    user_id       uuid primary key references auth.users(id) on delete cascade,
    reels_enabled boolean not null default false,
    updated_at    timestamptz not null default now()
);

-- Reels: short swipeable study cards, generated per student on demand --------
create table if not exists reels (
    id               uuid primary key default gen_random_uuid(),
    seq              bigint generated always as identity,   -- feed order
    user_id          uuid not null references auth.users(id) on delete cascade,
    course_id        uuid not null references courses(id) on delete cascade,
    type             text not null
                     check (type in ('explainer', 'quiz', 'flashcard', 'myth_fact', 'mnemonic')),
    concept          text not null,
    content          jsonb not null,      -- quiz answers live here; the API strips them
    source_chunk_ids uuid[] not null default '{}',
    flashcard_id     uuid references flashcards(id) on delete cascade,
    seen_at          timestamptz,
    created_at       timestamptz not null default now()
);
create index if not exists reels_feed_idx on reels (user_id, course_id, seen_at, seq);

create table if not exists reel_views (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    reel_id     uuid not null references reels(id) on delete cascade,
    watch_ms    int not null default 0,
    completed   boolean not null default false,
    created_at  timestamptz not null default now()
);
create index if not exists reel_views_session_idx on reel_views (user_id, created_at);

-- Chat threads: several conversations per course --------------------------
create table if not exists chats (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    title       text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
-- Messages sent without a chat_id (older clients) keep a null chat_id.
alter table chat_messages add column if not exists chat_id uuid references chats(id) on delete cascade;

-- Flashcard decks: one per generation, so students can browse earlier sets ---
create table if not exists flashcard_decks (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    topic       text,
    created_at  timestamptz not null default now()
);
-- Cards created by reels have no deck.
alter table flashcards add column if not exists deck_id uuid references flashcard_decks(id) on delete cascade;

-- Saved study plans (GET /plan stays stateless; POST /plans stores one) ------
create table if not exists study_plans (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references auth.users(id) on delete cascade,
    course_id     uuid not null references courses(id) on delete cascade,
    daily_minutes int  not null,
    summary       text not null,
    days          jsonb not null,
    created_at    timestamptz not null default now()
);

-- Row Level Security: a student only ever sees their own rows -------------
do $$
declare t text;
begin
    foreach t in array array['courses','documents','chunks','mastery','quizzes',
                             'questions','answers','flashcards','exams','chat_messages',
                             'user_preferences','reels','reel_views',
                             'chats','flashcard_decks','study_plans']
    loop
        execute format('alter table %I enable row level security', t);
        execute format('drop policy if exists owner_all on %I', t);
        execute format(
            'create policy owner_all on %I for all to authenticated '
            'using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)',
            t);
    end loop;
end $$;

-- Vector search used by the retrieval service ------------------------------
create or replace function match_chunks(
    query_embedding extensions.vector(1024),
    p_course_id uuid,
    p_user_id uuid,
    match_count int default 6
)
returns table (
    id uuid,
    document_id uuid,
    content text,
    location text,
    filename text,
    similarity float
)
language sql stable
set search_path = public, extensions
as $$
    select c.id, c.document_id, c.content, c.location, d.filename,
           1 - (c.embedding <=> query_embedding) as similarity
    from chunks c
    join documents d on d.id = c.document_id
    where c.course_id = p_course_id
      and c.user_id = p_user_id
      and c.embedding is not null
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- Only the backend (service role) should call match_chunks.
revoke execute on function match_chunks(extensions.vector, uuid, uuid, int) from public, anon, authenticated;
grant execute on function match_chunks(extensions.vector, uuid, uuid, int) to service_role;

-- Indexes on foreign keys (used by ownership filters and cascading deletes) -------
create index if not exists courses_user_idx        on courses (user_id);
create index if not exists documents_course_idx    on documents (course_id);
create index if not exists documents_user_idx      on documents (user_id);
create index if not exists chunks_document_idx     on chunks (document_id);
create index if not exists chunks_user_idx         on chunks (user_id);
create index if not exists mastery_course_idx      on mastery (course_id);
create index if not exists quizzes_course_idx      on quizzes (course_id);
create index if not exists quizzes_user_idx        on quizzes (user_id);
create index if not exists questions_quiz_idx      on questions (quiz_id);
create index if not exists questions_user_idx      on questions (user_id);
create index if not exists answers_question_idx    on answers (question_id);
create index if not exists answers_user_idx        on answers (user_id);
create index if not exists flashcards_course_idx   on flashcards (course_id);
create index if not exists exams_course_idx        on exams (course_id);
create index if not exists exams_user_idx          on exams (user_id);
create index if not exists chat_messages_user_idx  on chat_messages (user_id);
create index if not exists reels_course_idx        on reels (course_id);
create index if not exists reels_flashcard_idx     on reels (flashcard_id);
create index if not exists reel_views_reel_idx     on reel_views (reel_id);
create index if not exists chats_course_idx        on chats (user_id, course_id, updated_at);
create index if not exists chat_messages_chat_idx  on chat_messages (chat_id, created_at);
create index if not exists flashcard_decks_course_idx on flashcard_decks (user_id, course_id, created_at);
create index if not exists flashcards_deck_idx     on flashcards (deck_id);
create index if not exists study_plans_course_idx  on study_plans (user_id, course_id, created_at);

-- Data API access ----------------------------------------------------------
-- The backend talks to PostgREST with the service role; newer projects don't always
-- auto-grant new tables, so grant explicitly. `authenticated` gets table access too so
-- the frontend may read its own rows with supabase-js; RLS limits it to the owner.
grant usage on schema public to service_role, authenticated;
grant select, insert, update, delete on all tables in schema public to service_role;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to service_role, authenticated;
