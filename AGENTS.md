# AGENTS.md

## Project

An immersive, phone-first language-learning platform. Each word is connected to how the
language is lived (its register and connotations, songs and lyrics, clips and culture), and
spaced-repetition flashcards are one tool that makes that immersion stick. The front end is a
React + Vite PWA (`app/`). The backend is Supabase: Postgres with RLS (`supabase/migrations/`)
and a Deno Edge Function, `supabase/functions/generate-word/`, which calls Gemini and caches
each word's profile for every user. The Python modules at the root (`cardModels/`,
`cardGenerators/`, `GeminiClient.py`, `AnkiConnection.py`) are the original Anki card generator.

### Vision

Knowing a language means knowing how it is lived. A word isn't learned until you know how
formal it is, what it implies, where it turns up in songs, films and culture, and when a
native speaker would choose it. Language learning should be immersion in that living
language: real music, clips, texts and conversation, not lists of translations. It should
make learning a language fun, accessible and immersive, and save language learners time.

Flashcards and practice are tools that make the immersion stick. They are not the
destination.

### Mission

Build a phone-first, immersive language-learning platform that:

- **Captures** words wherever I meet them: typed in, picked out of a screenshot, or
  suggested from the words I already know.
- **Immerses** each word in the culture it lives in: clips where it is spoken, songs and
  lyrics that use it, notable uses and its cultural context.
- **Enriches** it with its definition, examples, register and connotations, alongside my
  own notes.
- **Reinforces** it with spaced-repetition flashcards, so what I meet actually sticks.
- **Puts it to use** through register ranking, comprehension questions on real texts,
  and spoken conversations with an AI that marks my grammar, vocabulary and pronunciation.

It should be free to run, private by default, and easy for others to fork and host
themselves.

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

## Five review standards

1. **More than a translation: a card is never just a translation.**
   - **Applies to:** card generation (`supabase/functions/generate-word/**`, `cardGenerators/**`,
     `cardModels/**`) and the card screens in `app/src/**`.
   - **Rule:** Every generated card must include the word's definition, register, connotations
     (`emotional_colour`) and at least one example sentence. If one of these is missing, the card
     must show it as missing. Never quietly fill it in with a default or leave it out.
   - **Why:** This is the app's vision. Knowing a word means knowing how formal it is, what it
     implies and when a native speaker would choose it, and a bare translation teaches none of that.

2. **Real-world examples: examples sound like real use, not a textbook.**
   - **Applies to:** Gemini prompts and output checks (`supabase/functions/generate-word/logic.ts`,
     `cardGenerators/**`) and any feature that adds example sentences, notable uses or lyrics.
   - **Rule:** Prefer examples from how the word is really used: song lyrics, real texts and notable
     uses. Generated examples must sound like something a native speaker would actually say, in the
     register the card gives. Reject invented textbook sentences ("The cat is on the table").
   - **Why:** Immersion. Learners need to meet a word the way they'll meet it in real reading and
     conversation.

3. **Where I met it: a captured word keeps the context it came from.**
   - **Applies to:** word capture (typed, from a screenshot or from a text) in `app/src/**` and
     `supabase/functions/**`, and the schema in `supabase/migrations/**`.
   - **Rule:** When a word is captured from a screenshot or a text, save the sentence it appeared in
     with the learner's card and show it on the card. Code that adds a word from a source must not
     drop that context.
   - **Why:** A word is easier to remember when it's tied to where you found it. The learner's own
     encounter with a word is the most immersive example the app can show.

4. **No untested behaviour: every behaviour change ships with a test that fails without it.**
   - **Applies to:** `app/src/**`, `supabase/functions/**`, the Python modules and `tests/**`.
   - **Rule:** A PR that changes behaviour must include a test that fails without the change and
     passes with it (see *Development workflow* above). A bug fix includes a regression test that
     reproduces the bug. Docs-only and config-only changes are exempt.
   - **Why:** A test that was red first proves the change does what it claims, and it keeps a fixed
     bug from coming back.

5. **Product only: don't review the personal learning and development workflow.**
   - **Applies to:** `.claude/**`, `BugReview/**`, `LessonsLearned.md`, `docs/WorkflowLessons.md`,
     `docs/LearningRubric.md`, `docs/backlog.md`, `docs/HackathonLog.md`, `scripts/qodo_review.py`, `scripts/learning_score.py`,
     `scripts/backlog_order.py`, `tests/test_qodo_review.py`, `tests/test_learning_score.py`,
     `tests/test_feature_commit_hook.py`, `tests/test_backlog_order.py`.
   - **Rule:** Don't leave review comments, suggestions or findings on these files. Focus reviews on
     the product: `app/`, `supabase/` and the Python card modules.
   - **Why:** These files are the maintainer's own tooling for learning and building (skills, hooks,
     bug-review write-ups and lessons), not part of the app. Comments on them are noise.

## Most opinionated rule for Qodo Day 2

> **More than a translation:** a card is never just a translation. Every card carries the word's
> register, connotations and a real example, and anything missing looks missing.

**Why this exists:** the whole app is built on the idea that knowing a word means knowing how it is
lived: how formal it is, what it implies and when a native speaker would choose it. A flashcard app
that shows only a translation would be easier to build, and it would teach the wrong thing.
