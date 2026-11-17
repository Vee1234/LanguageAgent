# AGENTS.md

## Project

A personal, phone-first language-learning app that turns each word into a rich flashcard
and schedules it for spaced repetition. The front end is a React + Vite PWA (`app/`). The backend
is Supabase: Postgres with RLS (`supabase/migrations/`) and a Deno Edge Function,
`supabase/functions/generate-word/`, which calls Gemini and caches each word's card for every
user. The Python modules at the root (`cardModels/`, `cardGenerators/`, `GeminiClient.py`,
`AnkiConnection.py`) are the original Anki card generator.

### Vision

Knowing a word means knowing more than its translation. It means knowing how formal it is, what
it implies, where it has been used, and when a native speaker would choose it. Language learning
should build that depth, then carry it into real reading and conversation. It should make learning a language fun, accessible and immersive, and save language
learners time.

### Mission

Build a personal, phone-first language app that:

- **Captures** words wherever I meet them: typed in, picked out of a screenshot, or suggested
  from the words I already know.
- **Enriches** each word automatically with its definition, examples, register, connotations,
  notable uses and song lyrics, alongside my own notes.
- **Schedules** it for spaced-repetition review, so it actually sticks.
- **Puts it to use** through register ranking, comprehension questions on real texts, and spoken
  conversations with an AI that marks my grammar, vocabulary and pronunciation.

It should be free to run, private by default, and easy for others to fork and host themselves.

More detail: `docs/architecture.md`, `docs/features.md`, `docs/roadmap.md`.

## Setup

Full walkthrough (Supabase project, migrations, secrets, function deploy): `docs/setup.md`.

```sh
pip install python-dotenv pytest          # Python side; Gemini key in the root .env
cd app && cp .env.example .env.local      # fill in the Supabase URL and anon key
npm install
npm run dev                               # serves the PWA on your LAN
```

## Verification

Run all three before you push. All of them must pass.

```sh
python3 -m pytest -q          # Python tests in tests/
npm --prefix app test         # Vitest: app/src/**/*.test.ts(x), including the Edge Function logic in app/src/server/
npm --prefix app run build    # tsc type-check + Vite build
```

## Development workflow: test-driven

Every new feature or behaviour change follows red → green → refactor:

1. **Write the tests first**, while planning the change. Python tests go in `tests/` (pytest).
   App and Edge Function tests go in `app/src/**/*.test.ts(x)` (Vitest). Edge Function logic
   lives in `logic.ts` so that it can be tested there.
2. **Red:** run them and confirm that they fail *for the expected reason*, not because of an
   import error or a typo.
3. **Green:** write the minimum code that makes them pass, then rerun them.
4. **Refactor:** clean up, then rerun. They must still pass.

Docs-only and config-only changes don't need tests.

## Project rules

Each rule comes from a real bug found in review (see `LessonsLearned.md`, L1–L10).

### 1. The Prove-You're-a-User Rule: elevated access requires a real signed-in user
**Applies to:** `supabase/functions/**` and any future server code that uses the service-role key.
Secrets (the Gemini key and the service-role key) live only in Edge Functions, never in `app/`.
Before any code path uses service-role access, it must establish who the caller is and refuse
anyone who isn't a real signed-in user. A token with a valid signature isn't enough on its own,
because the anon key is itself a valid JWT.
**Why:** the service role bypasses RLS. If it trusts a token without checking for a user, anyone
holding the public anon key can write to shared tables. (L5)

### 2. The Model-Is-Not-a-Firewall Rule: user text to an LLM is constrained in code, and its output is validated in code
**Applies to:** every Gemini call (`supabase/functions/generate-word/logic.ts`, `GeminiClient.py`, `cardGenerators/`).
Restrict user input with a code-enforced allowlist (e.g. the word's character set and length).
Keep it out of the instructions, so that it's passed only as data. Validate the model's output
against the expected schema before storing it.
**Why:** generated cards are cached and shown to *every* user. If one user's input steers the
model, that user's prompt injection reaches everyone else. Asking the model to "treat this as
data" isn't a control. (L6)

### 3. The Database-Is-the-Truth Rule: bounded reads, real counts, and the database picks the winner
**Applies to:** Supabase queries in `app/src/` and `supabase/functions/`, and to the schema in `supabase/migrations/`.
- Every read of a collection that grows with use is bounded and keyset-paged by a stable cursor
  (e.g. `created_at` + `id`), never fetched all at once or paged by offset.
- Any count shown to the user comes from the database (`count: "exact"`), never from how many
  rows the client happened to receive.
- When concurrent requests can write the same shared record, a unique constraint decides which
  write wins (e.g. `unique (language, form_key)` on shared words), and every request continues with the row that was *actually
  stored*, not the value it computed.
**Why:** Supabase silently caps responses at 1,000 rows, so "My words" lost data and showed a
wrong count. And two users adding the same word at the same time could each believe their own
version had been saved. (L3, L7)

### 4. The Screen-Never-Lies Rule: what's on screen belongs to this user, is real, and survives failures
**Applies to:** React components and client state in `app/src/`.
- Client state that holds user data lives inside the subtree keyed by `session.user.id`, so
  switching users discards it.
- A missing value must look missing. Don't let a control's default stand in for data nobody
  chose, and never save that default as if the user had chosen it.
- A failed network read is a normal state. Show a visible retry, and never discard data already
  on screen.
**Why:** RLS only controls what's *fetched*. The browser kept user A's words visible to user B,
and an unsaved card could have been saved under the wrong account. Default values and blank
error screens mislead the user in similar ways. (L1, L4, L8)

### 5. The No-Untested-Behaviour Rule: every behaviour change ships with a test that fails without it
**Applies to:** all code in `app/src/`, `supabase/functions/`, and the Python modules and `tests/`.
A PR that changes behaviour must include a test that fails without the change and passes with
it (see *Development workflow* above). A fix for a reported bug includes a regression test that
reproduces that bug.
**Why:** each Day 1 bug was fixed red-first. That way the test proves the fix addresses the
reported failure and keeps it from coming back.

## Review scope

**Don't leave review comments on the development and learning workflow.** It's personal tooling
for how I learn and build, not part of the product:

- `.claude/` (skills, hooks, settings)
- `BugReview/`
- `LessonsLearned.md`, `docs/WorkflowLessons.md`, `docs/LearningRubric.md`
- `scripts/qodo_review.py`, `scripts/learning_score.py`
- `tests/test_qodo_review.py`, `tests/test_learning_score.py`, `tests/test_feature_commit_hook.py`

Focus reviews on the product: `app/`, `supabase/`, and the Python card modules.
