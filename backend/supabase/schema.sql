-- Studeasy schema. Run once in the Supabase SQL editor.
-- Every table carries user_id so Row Level Security can scope rows to the student.
-- The backend uses the service-role key (bypasses RLS) and filters by user_id itself;
-- RLS protects the data if the frontend ever reads tables directly with supabase-js.

create extension if not exists vector;

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

-- Text chunks + embeddings (dimension must match EMBEDDING_DIMENSIONS) -------
create table if not exists chunks (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    course_id   uuid not null references courses(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    content     text not null,
    location    text not null,          -- e.g. "page 3", "slide 7", "section: Intro"
    embedding   vector(1536) not null
);
create index if not exists chunks_course_idx on chunks (course_id);
create index if not exists chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);

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

-- Row Level Security: a student only ever sees their own rows -------------
do $$
declare t text;
begin
    foreach t in array array['courses','documents','chunks','mastery','quizzes',
                             'questions','answers','flashcards','exams','chat_messages']
    loop
        execute format('alter table %I enable row level security', t);
        execute format('drop policy if exists owner_all on %I', t);
        execute format(
            'create policy owner_all on %I for all using (user_id = auth.uid()) with check (user_id = auth.uid())',
            t);
    end loop;
end $$;

-- Vector search used by the retrieval service ------------------------------
create or replace function match_chunks(
    query_embedding vector(1536),
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
as $$
    select c.id, c.document_id, c.content, c.location, d.filename,
           1 - (c.embedding <=> query_embedding) as similarity
    from chunks c
    join documents d on d.id = c.document_id
    where c.course_id = p_course_id
      and c.user_id = p_user_id
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- Only the backend (service role) should call match_chunks.
revoke execute on function match_chunks(vector, uuid, uuid, int) from public, anon, authenticated;
