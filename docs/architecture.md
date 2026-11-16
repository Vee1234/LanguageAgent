# Architecture — The Application Chain

Every application in the stack, what it does, what it connects to, and what can go wrong
between them. Feature numbers refer to `features.md`; phases refer to `roadmap.md`.
 ────────────                          ───────
 GitHub repo ──► Supabase CLI ──────►  ┌─ Supabase ─────────────────────────┐
     │          (migrations, deploy)   │  Auth ─► Postgres + RLS            │
     │                                 │  Storage                           │
     └──► Static host ──► Phone PWA ──►│  Edge Functions ──► Gemini API     │
         (Cloudflare Pages/Vercel)  │  │                 ──► Musixmatch     │
                                    │  │                 ──► Azure (opt.)   │
                                    │  └────────────────────────────────────┘
                                    └──────────────────────► Gemini Live (voice, direct)

---

## Build & ship

### 1. GitHub repo
- **Purpose:** source of truth for everything, including the schema. Others fork it to copy the setup.
- **Before → after:** — → feeds the Supabase CLI (backend) and the static host (front end).
- **Concerns:** never commit secrets; `.env.example` lists every variable with no values.

### 2. Supabase CLI (needs Node)
- **Purpose:** applies `supabase/migrations/*.sql` (`db push`), sets secrets, deploys Edge
  Functions, generates TypeScript types from the schema.
- **Before → after:** reads the repo → writes to the Supabase project.
- **Concerns:**
  - Local dev (`supabase start`) needs Docker. Deploying doesn't, though older CLI versions did.
  - Regenerate types whenever the schema changes, or the client and functions drift from the DB.

### 3. Static host — Cloudflare Pages / Vercel (+ optional Cloudflare Access)
- **Purpose:** builds the front end from the repo and serves it over HTTPS.
- **Before → after:** repo → PWA on the phone.
- **Concerns:**
  - Supabase URL + anon key are injected as build-time env vars.
  - **Cloudflare Access + installed PWA can conflict.** An iPhone home-screen app keeps
    its own cookies, separate from Safari, so the Access login may bounce out to Safari,
    and manifest/icon requests can be blocked. Test early.

---

## Runtime

### 4. Front end (PWA) on the phone
- **Purpose:** the screens (add word, review, decks, practice), the spaced-repetition
  scheduler (e.g. `ts-fsrs`), a manifest (home-screen install), a service worker (offline cache).
- **Before → after:** served by the static host → calls Supabase Auth / DB / Storage
  directly, Edge Functions for anything needing a secret, Gemini Live directly for voice.
- **Concerns** (most iPhone-specific risk lives here):
  - **Login:** on iPhone, magic-link emails open in Safari, not the home-screen app, so the
    session never reaches the app. Use a one-time code or a password.
  - **Storage:** iPhone may clear site data. The phone is a cache; Supabase is the source of truth.
  - **Audio format:** Safari's `MediaRecorder` gives AAC/MP4; Gemini Live and Azure want
    16 kHz PCM. Capture with an AudioWorklet and resample. Audio only starts after a tap.
  - **Push notifications** need iOS 16.4+ and the app installed to the home screen.
  - **Framework** still undecided. A Vite-based setup with `vite-plugin-pwa` is the common choice.

### 5. Supabase Auth
- **Purpose:** login; issues the JWT (login token) every later call carries.
- **Before → after:** PWA logs in → Postgres RLS and Edge Functions trust the JWT.
- **Concerns:**
  - Set **Site URL / redirect URLs** to your deployed domain.
  - **OPEN:** turn off sign-ups once your account exists? Only valid while the app is
    single-user. Depends on the "Other users and Gemini cost" decision in `roadmap.md` Phase 0.

### 6. Postgres + RLS (via Supabase's auto-generated REST API)
- **Purpose:** words, cards, notes, decks, the frequency list, exercises.
- **Before → after:** PWA reads/writes directly. Edge Functions write generated content.
  The one-off Python frequency-list script loads into it via a connection string.
- **Concerns:**
  - RLS on every table.
  - Free projects pause after ~1 week idle; the free tier also caps the database at 500 MB.

### 7. Supabase Storage
- **Purpose:** screenshots (feature 3) and chat audio (feature 6).
- **Before → after:** PWA uploads → Edge Functions read and forward to Gemini / Azure.
- **Concerns:**
  - Buckets need their own access policies, separate from table RLS.
  - Delete audio after processing to stay within the free 1 GB.

### 8. Edge Functions (Deno, TypeScript)
- **Purpose:** the only place secrets live. Call external APIs, validate output, write to the DB.
- **Before → after:** called by the PWA with its JWT → call Gemini / Musixmatch / Azure → write to Postgres.
- **Concerns:**
  - **CORS:** the browser calls them from another domain, so handle the `OPTIONS`
    preflight request and return CORS headers.
  - Deno isn't Node. `npm:` packages mostly work, but not ones with native code. Plain
    `fetch` to REST APIs is the safest option.
  - Time/CPU limits: keep each function to about one LLM call.

---

## External services

### 9. Gemini API (text + vision)
- **Purpose:** card content, notes, synonyms and register rankings, screenshot word
  extraction, post-chat marking.
- **Before → after:** called only from Edge Functions.
- **Concerns:**
  - Use structured output (a JSON schema) so responses validate reliably.
  - Keep the model ID in an env var, because models get deprecated.
  - Free-tier rate limits; Google may use free-tier inputs to improve its products.

### 10. Gemini Live API (realtime voice)
- **Purpose:** the feature 6 conversation.
- **Before → after:** phone connects directly using a short-lived token from an Edge
  Function → transcript goes through 8 → 9 for marking.
- **Concerns:**
  - PCM audio only (see 4).
  - Ephemeral tokens are recent — check Gemini's current docs.

### 11. Musixmatch
- **Purpose:** lyric lines (feature 7).
- **Before → after:** Edge Function → result saved as a note.
- **Concerns:**
  - Free plan returns partial lyrics; its terms restrict how lyrics are displayed.
  - Self-hosters need their own key, so make the feature optional.

### 12. Azure Pronunciation Assessment (optional, later)
- **Purpose:** pronunciation scoring (feature 6).
- **Before → after:** Storage audio → Edge Function → Azure → results in Postgres.
- **Concerns:**
  - Needs an Azure account (extra setup for self-hosters).
  - Language support varies — check yours.
  - Same PCM audio issue as 4.

---

## Possible later additions (not in v1)
- **Python service on an Oracle VM + Tailscale:** only for self-hosted pronunciation
  models or spaCy-style processing. Connects to the same Postgres.
- **Web Push:** review reminders, sent by a scheduled Edge Function via the Web Push protocol.

## Test early
1. Login inside the installed PWA (no magic links).
2. Audio capture format on iPhone.
3. Cloudflare Access with the installed PWA (if you use Access).
