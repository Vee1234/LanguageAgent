-- Allow a 'register' note: one of Frozen / Formal / Consultative / Casual / Intimate.
alter table public.notes drop constraint notes_kind_check;
alter table public.notes add constraint notes_kind_check check (kind in (
  'definition', 'example', 'register', 'emotional_colour', 'usage_conditions',
  'notable_use', 'lyric', 'user'));

alter table public.notes add constraint notes_register_value check (
  kind <> 'register' or body in ('Frozen', 'Formal', 'Consultative', 'Casual', 'Intimate'));
