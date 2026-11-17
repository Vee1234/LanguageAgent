-- Shared cache. Content is shared by everyone; progress belongs to one user.
--   shared, read-only for users, written only by generate-word (service role):
--     words, word_forms, notes (generated), cards
--   per user (RLS user_id = auth.uid()):
--     user_cards (review progress, keyed by user + card), user_notes (the user's own notes and edits)
-- Existing per-user words, notes and cards are carried over.

-- 1. Copy the old per-user data aside, then drop the old tables (their policies go with them).
create temporary table old_words as select * from public.words;
create temporary table old_notes as select * from public.notes;
create temporary table old_cards as select * from public.cards;

drop function if exists public.save_word(text, text, text, jsonb);
drop table public.cards, public.notes, public.words;

-- 2. Shared content.
create table public.words (
  id         uuid primary key default gen_random_uuid(),
  language   text not null,
  lemma      text not null,
  lemma_key  text not null, -- trim + NFC + lower-case (logic.ts normalizeKey); the cache key
  created_at timestamptz not null default now(),
  unique (language, lemma_key)
);

-- Every form anyone has typed ("maisons", "maison") → its word, so repeat lookups skip Gemini.
create table public.word_forms (
  language text not null,
  form_key text not null,
  word_id  uuid not null references public.words (id) on delete cascade,
  primary key (language, form_key)
);

create table public.notes (
  id         uuid primary key default gen_random_uuid(),
  word_id    uuid not null references public.words (id) on delete cascade,
  kind       text not null check (kind in (
               'definition', 'example', 'register', 'emotional_colour', 'usage_conditions',
               'notable_use', 'lyric')),
  body       text not null,
  created_at timestamptz not null default now(),
  unique (word_id, kind),
  constraint notes_register_value check (
    kind <> 'register' or body in ('Frozen', 'Formal', 'Consultative', 'Casual', 'Intimate'))
);

create table public.cards (
  id         uuid primary key default gen_random_uuid(),
  word_id    uuid not null references public.words (id) on delete cascade,
  kind       text not null default 'definition' check (kind in ('definition')),
  created_at timestamptz not null default now(),
  unique (word_id, kind)
);

-- 3. Per-user progress and notes.
create table public.user_cards (
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  card_id       uuid not null references public.cards (id) on delete cascade,
  surface_form  text not null,
  due_at        timestamptz not null default now(),
  interval_days real not null default 0,
  ease          real not null default 2.5,
  reps          integer not null default 0,
  created_at    timestamptz not null default now(),
  primary key (user_id, card_id)
);
create index user_cards_user_due on public.user_cards (user_id, due_at);
create index user_cards_user_recent on public.user_cards (user_id, created_at desc, card_id desc);

create table public.user_notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  word_id    uuid not null references public.words (id) on delete cascade,
  kind       text not null check (kind in (
               'definition', 'example', 'register', 'emotional_colour', 'usage_conditions',
               'notable_use', 'lyric', 'user')),
  body       text not null,
  created_at timestamptz not null default now(),
  unique (user_id, word_id, kind),
  constraint user_notes_register_value check (
    kind <> 'register' or body in ('Frozen', 'Formal', 'Consultative', 'Casual', 'Intimate'))
);

-- 4. Access. Shared tables: any signed-in user can read; nobody but the service role can write
--    (no write policies, and table write grants revoked as a second layer).
alter table public.words      enable row level security;
alter table public.word_forms enable row level security;
alter table public.notes      enable row level security;
alter table public.cards      enable row level security;
alter table public.user_cards enable row level security;
alter table public.user_notes enable row level security;

create policy "read shared words"      on public.words      for select to authenticated using (true);
create policy "read shared word forms" on public.word_forms for select to authenticated using (true);
create policy "read shared notes"      on public.notes      for select to authenticated using (true);
create policy "read shared cards"      on public.cards      for select to authenticated using (true);

revoke insert, update, delete, truncate on public.words, public.word_forms, public.notes, public.cards
  from anon, authenticated;

create policy "own user_cards" on public.user_cards for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy "own user_notes" on public.user_notes for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- 5. Move the old data. Where two users had the same word, the earliest generated text wins.
--
--    ASSUMPTION (Bug 7, accepted 2026-11-17): every old note marked source = 'generated', and every
--    old lemma, is Gemini's original text. The old review screen *allowed* edits and old save_word
--    labelled every field 'generated', so the label itself can't prove this. It holds here only
--    because this project has a single user who confirmed they never edited before saving.
--    Do NOT run this step on a database where users may have edited fields before saving: there,
--    copy old notes into user_notes instead, and let generate-word fill the shared notes afresh.
insert into public.words (language, lemma, lemma_key, created_at)
select distinct on (language, lower(normalize(btrim(lemma), NFC)))
       language, btrim(lemma), lower(normalize(btrim(lemma), NFC)), created_at
from old_words
order by language, lower(normalize(btrim(lemma), NFC)), created_at;

create temporary table word_map as
select o.id as old_id, o.user_id, o.surface_form, w.id as new_id
from old_words o
join public.words w
  on w.language = o.language and w.lemma_key = lower(normalize(btrim(o.lemma), NFC));

insert into public.word_forms (language, form_key, word_id)
select distinct w.language, f.form_key, w.id
from word_map m
join public.words w on w.id = m.new_id
cross join lateral (values (lower(normalize(btrim(m.surface_form), NFC))), (w.lemma_key)) as f (form_key)
on conflict do nothing;

insert into public.notes (word_id, kind, body, created_at)
select distinct on (m.new_id, n.kind) m.new_id, n.kind, n.body, n.created_at
from old_notes n
join word_map m on m.old_id = n.word_id
where n.source = 'generated' and n.kind <> 'user'
order by m.new_id, n.kind, n.created_at
on conflict do nothing;

insert into public.cards (word_id) select id from public.words;

insert into public.user_cards (user_id, card_id, surface_form, due_at, interval_days, ease, reps, created_at)
select distinct on (m.user_id, c.id)
       m.user_id, c.id, m.surface_form, oc.due_at, oc.interval_days, oc.ease, oc.reps, oc.created_at
from old_cards oc
join word_map m on m.old_id = oc.word_id
join public.cards c on c.word_id = m.new_id and c.kind = 'definition'
order by m.user_id, c.id, oc.created_at;

insert into public.user_notes (user_id, word_id, kind, body, created_at)
select distinct on (m.user_id, m.new_id, n.kind) m.user_id, m.new_id, n.kind, n.body, n.created_at
from old_notes n
join word_map m on m.old_id = n.word_id
where n.source = 'user'
order by m.user_id, m.new_id, n.kind, n.created_at desc
on conflict do nothing;

drop table old_words, old_notes, old_cards, word_map;

-- 6. Writing shared content: one transaction per new word. Service role only.
--    If another request stored the same lemma first, keep theirs and return its id.
create function public.insert_shared_word(
  p_language  text,
  p_lemma     text,
  p_lemma_key text,
  p_fields    jsonb
) returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_id   uuid;
  v_kind text;
  v_body text;
begin
  insert into public.words (language, lemma, lemma_key)
  values (p_language, p_lemma, p_lemma_key)
  on conflict (language, lemma_key) do nothing
  returning id into v_id;

  if v_id is null then
    select id into v_id from public.words where language = p_language and lemma_key = p_lemma_key;
    return v_id;
  end if;

  for v_kind, v_body in select key, value from jsonb_each_text(p_fields) loop
    if v_kind <> 'lemma' and coalesce(btrim(v_body), '') <> '' then
      insert into public.notes (word_id, kind, body) values (v_id, v_kind, v_body);
    end if;
  end loop;

  insert into public.cards (word_id) values (v_id);
  return v_id;
end;
$$;

revoke execute on function public.insert_shared_word(text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.insert_shared_word(text, text, text, jsonb) to service_role;

-- 7. Saving a word for the signed-in user: start studying its cards, and store their edits as
--    personal notes (shared notes are never edited). Returns how many new cards were added:
--    0 means the word was already theirs. security invoker: RLS on user_cards / user_notes applies.
create function public.save_card(
  p_word_id      uuid,
  p_surface_form text,
  p_user_notes   jsonb default '{}'::jsonb
) returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_added integer;
  v_kind  text;
  v_body  text;
begin
  insert into public.user_cards (card_id, surface_form)
  select c.id, p_surface_form from public.cards c where c.word_id = p_word_id
  on conflict (user_id, card_id) do nothing;
  get diagnostics v_added = row_count;

  for v_kind, v_body in select key, value from jsonb_each_text(coalesce(p_user_notes, '{}'::jsonb)) loop
    if coalesce(btrim(v_body), '') <> '' then
      insert into public.user_notes (word_id, kind, body) values (p_word_id, v_kind, btrim(v_body))
      on conflict (user_id, word_id, kind) do update set body = excluded.body;
    end if;
  end loop;

  return v_added;
end;
$$;

revoke execute on function public.save_card(uuid, text, jsonb) from public, anon;
grant execute on function public.save_card(uuid, text, jsonb) to authenticated;
