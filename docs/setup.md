# Setup — Add-word slice (Phase 1)

Gets the "add a word → Gemini card → saved in Supabase" flow running. No Docker needed:
everything runs against a hosted Supabase project.

## 1. Create the Supabase project (browser)
1. Sign up at supabase.com → **New project**. Pick a region near you and save the database password.
2. **Project Settings → API**: copy the **Project URL** and the **anon public** key.
3. **Authentication → Users → Add user → Create new user**: your email + a password,
   tick **Auto Confirm User**. (The app has no sign-up form yet; see roadmap Phase 0,
   "Other users and Gemini cost".)

## 2. Install the Supabase CLI and link this repo
```sh
brew install supabase/tap/supabase
supabase login
cd ~/Language-Agent
supabase init          # once; creates supabase/config.toml. Answer "no" to the editor prompts.
supabase link --project-ref YOUR-PROJECT-REF   # the ref is the subdomain in the Project URL
```

## 3. Create the tables
```sh
supabase db push --remote   # runs supabase/migrations/*.sql on the linked project
                            # (without --remote, newer CLIs target a local Docker stack)
```

## 4. Deploy the Gemini Edge Function
```sh
supabase secrets set GEMINI_API_KEY=your-key       # same key as the root .env
# optional: supabase secrets set GEMINI_MODEL=<model> (default gemini-3.1-flash-lite; leave it unset unless you need another)
supabase functions deploy generate-word --use-api  # --use-api: bundle without Docker
```

Hosted changes ask for confirmation; run these in your own terminal, or add `--yes` to confirm
up front (needed when an agent runs them).

If adding a word fails, the function logs show Gemini's status (Dashboard → Edge Functions →
`generate-word` → Logs, the `Gemini error` line):
- **503:** Gemini is overloaded. It's temporary; try again later (retries are #67).
- **404:** your key can't use that model. Check `GEMINI_MODEL`, or unset it to use the default.

## 5. Run the app
```sh
cd app
cp .env.example .env.local   # fill in the URL and anon key from step 1
npm install
npm run dev                  # prints a Local and a Network URL
```
Open the Network URL on your phone (same Wi-Fi) to try it there.

## Checking it worked
- **Table Editor** shows a row in `words`, one per filled field in `notes`, and one in `cards`.
- Errors from the function: **Edge Functions → generate-word → Logs**.
