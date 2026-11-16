# Roadmap — Own Flashcard App

A skeleton build path, not a full design doc. Each phase ends in something you can
use on your phone. Feature numbers refer to `features.md`. How the pieces connect,
and their compatibility concerns: `architecture.md`.

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
- [ ] **Hosting.** Static front end on free public hosting (Cloudflare Pages / Vercel /
      Netlify). The URL and the app's code are public; your data stays behind Supabase login + RLS.
      Optional: Cloudflare Access (free) in front of Cloudflare Pages, so only your email
      can even load the page. Tailscale only if a Python service is ever added (Oracle VM + `tailscale serve`).
- [ ] **Scheduler.** SM-2 (hand-written, ~20 lines) or FSRS (the `ts-fsrs` npm library).
- [ ] **OPEN — Other users and Gemini cost.** The app is meant for other users too, but
      Phase 1 and `architecture.md` §5 still assume a single user. Decide, per feature, who
      pays for each Gemini call:
  - *Host pays:* per-user quotas / rate limits, or a paid tier.
  - *User pays:* bring-your-own Gemini key, or self-host a fork.
  - *Shared cache:* generate content once per word + language and reuse it across users.
    **DECIDED (2026-11-16): use the shared cache.** `words` and generated `notes` are shared
    and read-only for users (written only by the `generate-word` Edge Function); `cards`,
    user notes and decks are per-user. Not yet migrated: the current schema is still per-user.
  - Until decided, sign-ups and auth below are marked **OPEN**.
- [ ] **Schema.** Minimal draft to start from:

  | Table | Key columns |
  |---|---|
  | `words` | id, user_id, language, lemma, surface_form, created_at |
  | `cards` | id, user_id, word_id, front, back, due_at, interval_days, ease, reps |
  | `notes` | id, user_id, word_id, kind (`definition` / `example` / `emotional_colour` / `usage_conditions` / `notable_use` / `lyric` / `user`), body, source (`generated` / `user`) |

  Phase 1's tables are in `supabase/migrations/`; setup steps are in `setup.md`.
  | `decks` | id, user_id, name, description, language, is_public (default false), forked_from_deck_id, created_at |
  | `deck_words` | deck_id, word_id |

  Store `lemma` on every word from day one. Features 3 and 5 depend on it.

  **Public decks (feature 10):**
  - RLS: owners have full access to their own decks. Any signed-in user can *read* a deck
    where `is_public = true`, plus that deck's `deck_words`, `words` and generated `notes`.
    A user's own (`source = 'user'`) notes stay private.
  - "Add to my collection" **copies** the deck, its words and notes into the user's
    account, setting `forked_from_deck_id`, and creates fresh `cards` for them. Review
    progress is personal, so cards are never shared.
  - Search: by `name`, `description`, `language` (Postgres full-text search is enough to start).

**Done when:** these six choices are written down here.

---

## Phase 1 — Vertical slice: add a word → review it

The smallest loop that makes the app useful.

- [ ] Supabase project, Auth, tables from Phase 0.
      **OPEN:** "just you" or open to other users? See Phase 0, "Other users and Gemini cost".
- [ ] Lock it down:
  - Row-level security on **every** table (`user_id = auth.uid()`). A table without it
    is readable by anyone using the public anon key.
  - **OPEN:** disable new sign-ups once your account exists, so strangers can't use your
    Gemini quota? Only valid while the app is single-user. See Phase 0, "Other users and Gemini cost".
  - Keep JWT verification on for every Edge Function (the default).
  - Gemini key only in Edge Function secrets, never in client code.
- [ ] Deploy the client to the hosting from Phase 0: web app manifest (`"display": "standalone"`),
      icon, `noindex` meta tag. Then use **Add to Home Screen** on your phone.
- [ ] Edge Function `generate-word`: word + language → **one** Gemini call returning JSON
      (lemma, definition, example, register, notable use). Replaces the six separate
      calls in `LanguageUsageCardGenerator.py`. Validate the JSON before saving.
- [ ] Client: "Add word" screen → calls `generate-word` → saves word, notes, and a card.
- [ ] Client: "Review" screen → shows due cards → you grade → scheduler updates `due_at`.

**Done when:** you add a word on your phone and review it the next day.

---

## Phase 2 — Organise and enrich (features 1, 4, 7)

- [ ] Edit / add your own notes on a word (feature 1). Plain database writes from the client.
- [ ] Decks: create, add words, review by deck (feature 4).
- [ ] Edge Function `fetch-lyric`: Musixmatch lookup → stored as a note (feature 7).
      The free plan returns partial lyrics only.

**Done when:** you use the app daily without missing anything from Anki.

---

## Phase 3 — Input shortcuts (features 3, 5)

- [ ] Screenshot import (feature 3): upload to Storage → Edge Function sends image to
      Gemini → returns highlighted words + lemmas → you confirm → `generate-word` each.
- [ ] Unknown-word finder (feature 5): one-off local Python script loads a frequency
      list into a `frequency` table → SQL query for top lemmas not in `words` → new deck.
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
