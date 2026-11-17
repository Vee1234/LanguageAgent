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

## Project rules

### 1. The More-Than-a-Translation Rule: a card is never just a translation
**Applies to:** card generation (`supabase/functions/generate-word/`, `cardGenerators/`, `cardModels/`)
and the card screens in `app/src/`.
Every generated card must include the word's register, its connotations (`emotional_colour`) and
at least one example sentence, alongside the definition. If one of these is missing, the card shows it as missing. It's
never quietly filled in or left out.
**Why:** this is the vision. Knowing a word means knowing how formal it is, what it implies and when a
native speaker would choose it, and a bare translation teaches none of that.

### 2. The Real-World Rule: examples sound like real use, not a textbook
**Applies to:** example sentences, notable uses and lyrics, in the Gemini prompts
(`supabase/functions/generate-word/logic.ts`, `cardGenerators/`) and in any future feature that adds
examples.
Where possible, examples come from how the word is really used: song lyrics, real texts and notable
uses. Generated examples must sound like something a native speaker would actually say, in the
register the card gives. Invented textbook sentences ("The cat is on the table") don't count.
**Why:** immersion. The aim is to carry words into real reading and conversation, so learners need to
meet a word the way they'll meet it in the wild.

### 3. The Where-I-Met-It Rule: a word keeps the context it came from
**Applies to:** word capture (adding a word by typing it, from a screenshot or from a text) and the
schema in `supabase/migrations/`.
When a word is captured from a screenshot or a text, the sentence it appeared in is saved with the
learner's card and shown on it. Code that adds a word from a source must not drop that context.
**Why:** a word is easier to remember when it's tied to where you found it. Your own encounter with a
word is the most immersive example the app can show.

### 4. The No-Untested-Behaviour Rule: every behaviour change ships with a test that fails without it
**Applies to:** all code in `app/src/`, `supabase/functions/`, and the Python modules and `tests/`.
A PR that changes behaviour must include a test that fails without the change and passes with it (see
*Development workflow* above). A fix for a reported bug includes a regression test that reproduces
that bug.
**Why:** a test that was red first proves the change does what it claims, and it keeps a fixed bug
from coming back.

## Review scope

**Don't leave review comments on the development and learning workflow.** It's personal tooling
for how I learn and build, not part of the product:

- `.claude/` (skills, hooks, settings)
- `BugReview/`
- `LessonsLearned.md`, `docs/WorkflowLessons.md`, `docs/LearningRubric.md`
- `scripts/qodo_review.py`, `scripts/learning_score.py`
- `tests/test_qodo_review.py`, `tests/test_learning_score.py`, `tests/test_feature_commit_hook.py`

Focus reviews on the product: `app/`, `supabase/`, and the Python card modules.
