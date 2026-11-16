-- Phase 1 schema: words, their notes, and a review card per word.
-- Every table has row-level security: a user only ever sees their own rows.

create table public.words (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  language     text not null,
  lemma        text not null,
  surface_form text not null,
  created_at   timestamptz not null default now()
);
create unique index words_user_language_lemma on public.words (user_id, language, lemma);

create table public.notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  word_id    uuid not null references public.words (id) on delete cascade,
  kind       text not null check (kind in (
               'definition', 'example', 'emotional_colour', 'usage_conditions',
               'notable_use', 'lyric', 'user')),
  body       text not null,
  source     text not null check (source in ('generated', 'user')),
  created_at timestamptz not null default now()
);
create index notes_word_id on public.notes (word_id);

create table public.cards (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  word_id       uuid not null references public.words (id) on delete cascade,
  front         text not null,
  back          text not null,
  due_at        timestamptz not null default now(),
  interval_days real not null default 0,
  ease          real not null default 2.5,
  reps          integer not null default 0,
  created_at    timestamptz not null default now()
);
create index cards_user_due on public.cards (user_id, due_at);

alter table public.words enable row level security;
alter table public.notes enable row level security;
alter table public.cards enable row level security;

create policy "own words" on public.words for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

-- Notes and cards must belong to you AND point at one of your own words.
create policy "own notes" on public.notes for all to authenticated
  using (user_id = (select auth.uid()))
  with check (
    user_id = (select auth.uid())
    and exists (select 1 from public.words w where w.id = word_id and w.user_id = (select auth.uid()))
  );

create policy "own cards" on public.cards for all to authenticated
  using (user_id = (select auth.uid()))
  with check (
    user_id = (select auth.uid())
    and exists (select 1 from public.words w where w.id = word_id and w.user_id = (select auth.uid()))
  );

-- Saves a word, its generated notes and its first card in one transaction,
-- so a failure part-way never leaves a word without its card.
-- security invoker: runs as the calling user, so the RLS policies above still apply.
create function public.save_word(
  p_language     text,
  p_surface_form text,
  p_lemma        text,
  p_fields       jsonb
) returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_word_id uuid;
  v_kind    text;
  v_body    text;
begin
  insert into public.words (language, lemma, surface_form)
  values (p_language, p_lemma, p_surface_form)
  returning id into v_word_id;

  for v_kind, v_body in select key, value from jsonb_each_text(p_fields) loop
    if coalesce(btrim(v_body), '') <> '' then
      insert into public.notes (word_id, kind, body, source)
      values (v_word_id, v_kind, v_body, 'generated');
    end if;
  end loop;

  insert into public.cards (word_id, front, back)
  values (v_word_id, p_surface_form, coalesce(p_fields ->> 'definition', ''));

  return v_word_id;
end;
$$;

revoke execute on function public.save_word(text, text, text, jsonb) from public, anon;
grant execute on function public.save_word(text, text, text, jsonb) to authenticated;
