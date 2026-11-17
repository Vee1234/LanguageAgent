# Language Agent

**An immersive, phone-first language-learning platform.** Every word you learn is connected
to how the language is really lived: its register and connotations, the songs and lyrics
that use it, clips where it's spoken, and the culture around it. Spaced-repetition
flashcards are one tool inside that, there to make the immersion stick.

## Vision

Knowing a language means knowing how it is lived. A word isn't learned until you know how
formal it is, what it implies, where it turns up in songs, films and culture, and when a
native speaker would choose it. Language learning should be fun, accessible and immersive,
and save language learners time.

Full vision and mission: [`docs/vision.md`](docs/vision.md).

## What it does today

- **Add a word.** Gemini builds it a profile: definition, example, register (frozen →
  intimate), emotional colour, when it's used, a notable use and a lyric.
- **My words.** Every word you've added, with its full profile, paged so it scales.
- **Shared cache.** Each word's profile is generated once and shared by every user. Your
  own progress and edits stay private.
- **Sign-in** with Supabase Auth. Row-level security keeps each user's data their own.

## Where it's going

- Clips where a word is spoken, linked and played in an embedded player
- Full song lyrics (Musixmatch)
- Spaced-repetition review and decks
- Import words from a screenshot of what you're reading
- Comprehension questions on real texts
- Register-ranking practice
- Spoken conversations with an AI that marks grammar, vocabulary and pronunciation

The full list is in [`docs/features.md`](docs/features.md) and the build order is in
[`docs/roadmap.md`](docs/roadmap.md). Work is tracked in
[GitHub issues](https://github.com/Vee1234/LanguageAgent/issues).

## Stack

- **App:** React + Vite PWA, in [`app/`](app/)
- **Backend:** Supabase: Postgres with row-level security
  ([`supabase/migrations/`](supabase/migrations/)) and the `generate-word` Edge Function
  ([`supabase/functions/`](supabase/functions/)), which calls Gemini
- **Original Anki generator:** the Python modules at the root (`cardModels/`,
  `cardGenerators/`, `GeminiClient.py`, `AnkiConnection.py`)

More detail: [`docs/architecture.md`](docs/architecture.md).

## Getting started

The full walkthrough (Supabase project, migrations, secrets, deploying the function) is in
[`docs/setup.md`](docs/setup.md).

```sh
cd app && cp .env.example .env.local   # fill in your Supabase URL and anon key
npm install
npm run dev                            # serves the app on your local network
```

## Tests

```sh
python3 -m pytest -q          # Python tests
npm --prefix app test         # Vitest: app and Edge Function logic
npm --prefix app run build    # type-check and build
```

## Contributing

Changes are made test-first. Project rules and the review scope are in
[`AGENTS.md`](AGENTS.md).
