# Roadmap — Own Flashcard App

A skeleton build path, not a full design doc. Each phase ends in something you can
use on your phone. Feature numbers refer to `features.md`.

**Stack:** Supabase (Postgres, Auth, Storage, Edge Functions) + a phone client.
Python only if feature 6's pronunciation scoring ever needs a self-hosted model.

---

## Phase 0 — Decisions (no code)

- [ ] **Phone client.** Pick one:
  - *PWA* (a web app you add to your home screen): free, no App Store, and the mic works for feature 6.
  - *Expo / React Native*: feels more native. But keeping it installed on an iPhone
    long-term needs a paid Apple developer account.
  - Leaning: PWA.
- [ ] **Repo.** New repo, or a `app/` + `supabase/` folder in this one? The current
      Python code becomes reference material for the prompts either way.
- [ ] **Scheduler.** SM-2 (hand-written, ~20 lines) or FSRS (the `ts-fsrs` npm library).
- [ ] **Schema.** Minimal draft to start from:

  | Table | Key columns |
  |---|---|
  | `words` | id, user_id, language, lemma, surface_form, created_at |
  | `cards` | id, word_id, front, back, due_at, interval_days, ease, reps |
  | `notes` | id, word_id, kind (`register` / `famous_use` / `example` / `description` / `user`), body, source (`generated` / `user`) |
  | `sets` | id, user_id, name |
  | `set_words` | set_id, word_id |

  Store `lemma` on every word from day one. Features 3 and 5 depend on it.

**Done when:** these four choices are written down here.

---

## Phase 1 — Vertical slice: add a word → review it

The smallest loop that makes the app useful.

- [ ] Supabase project, Auth (just you), tables from Phase 0 with row-level security on.
- [ ] Edge Function `generate-word`: word + language → **one** Gemini call returning JSON
      (lemma, definition, example, register, notable use). Replaces the six separate
      calls in `LanguageUsageCardGenerator.py`. Validate the JSON before saving.
- [ ] Client: "Add word" screen → calls `generate-word` → saves word, notes, and a card.
- [ ] Client: "Review" screen → shows due cards → you grade → scheduler updates `due_at`.

**Done when:** you add a word on your phone and review it the next day.

---

## Phase 2 — Organise and enrich (features 1, 4, 7)

- [ ] Edit / add your own notes on a word (feature 1). Plain database writes from the client.
- [ ] Sets: create, add words, review by set (feature 4).
- [ ] Edge Function `fetch-lyric`: Musixmatch lookup → stored as a note (feature 7).
      The free plan returns partial lyrics only.

**Done when:** you use the app daily without missing anything from Anki.

---

## Phase 3 — Input shortcuts (features 3, 5)

- [ ] Screenshot import (feature 3): upload to Storage → Edge Function sends image to
      Gemini → returns highlighted words + lemmas → you confirm → `generate-word` each.
- [ ] Unknown-word finder (feature 5): one-off local Python script loads a frequency
      list into a `frequency` table → SQL query for top lemmas not in `words` → new set.
      Open: is the source a frequency list, or content you've read?

---

## Phase 4 — Practice modes (features 2, 6)

- [ ] Register ranking (feature 2): Edge Function generates synonyms + the model's
      ranking + reasons (ties allowed) → stored → the client scores your order with partial credit.
- [ ] Audio chat (feature 6), in this order:
  1. Live conversation: client ↔ Gemini Live API, using a short-lived token from an Edge Function.
  2. Post-chat marking: transcript → Edge Function → grammar, vocab, naturalness feedback.
  3. Pronunciation: hosted service first (e.g. Azure Pronunciation Assessment);
     Python + self-hosted model only if that is not good enough.

---

## Parked / reference

- `archive/DESIGN.md`, `archive/.design-brief.md`: the previous Notes → Anki Shortcut design (superseded).
- `archive/gameplan.md`: an earlier multi-agent learning-system idea (not this app).
- `api-shapes.md`: generated from the current Python card classes.
