<!-- discussion-post {"day": 3, "url": "https://github.com/orgs/qodo-hackathon/discussions/5", "repeat": "## Ticket → branch → PR", "repeat_labels": ["Ticket link:", "Branch and PR link:", "Acceptance criteria checked, with observed results and evidence:", "Relevant edge or failure case and result:", "Qodo findings I investigated, including any missed or irrelevant feedback:", "What reached the coding agent and what changed in the fix:"]} -->
<!-- Draft of the Day 3 comment for https://github.com/orgs/qodo-hackathon/discussions/5. Fill it with scripts/discussion_post.py as the work happens; post it only after the user approves the text. -->

## My ticketing connection
Ticketing system: GitHub Issues (epics → issues → sub-issues, on a GitHub Projects board)
Connection used (MCP or CLI): CLI, the GitHub CLI (`gh`)
How I checked the agent could list and read my tickets: The agent ran `gh issue list` (58 open tickets) and `gh issue view` on each ticket, which read back its goal, acceptance criteria, edge case and out-of-scope.

<!-- ticket #6 -->
## Ticket → branch → PR
Ticket link: https://github.com/Vee1234/LanguageAgent/issues/6
Branch and PR link: `ticket-6-release-shared-cache` → https://github.com/Vee1234/LanguageAgent/pull/68
Acceptance criteria checked, with observed results and evidence: - ✅ Migration applies without errors: `supabase migration list --remote` shows the shared-cache migration applied.
- ❌ A new word on the phone appears in My words: it worked from the Mac, but on the phone Gemini returned 503 "high demand" (function logs). Left open; follow-up #67.
- ✅ [use] **The migration applies without errors.** `supabase db push --remote`: "Remote database is up to date"; `supabase migration list --remote` shows 20261117000000 (shared cache) applied on production. It had already been applied before this ticket.
- ❌ [use] **After the deploy, a new word on the phone works and appears in My words.** Deployed: generate-word ACTIVE, version 5, 21:29 UTC. A new word worked from the Mac browser (*chien*, with a complete card: definition, example, register Casual, emotional colour, usage, notable use, lyric). On the phone, new words failed with 502: the function logs show Gemini 503 "This model is currently experiencing high demand", then 404 after switching `GEMINI_MODEL` to a model the key can't use. Not met; the user merged with it open. Follow-up: #67 (retry, plus a Try again message).
- [x] [use] After the deploy, a new word appears in My words: added **chien** (French). My words shows it (2 words) with a complete card: definition, example, register Casual, emotional colour, when it's used, notable use and lyric (screenshot, 2026-11-23 21:44). Checked in the browser on the Mac against the deployed function, not yet on the phone as the criterion says.
  The first phone attempt failed: Gemini returned 503 (overloaded) and the app showed a dead-end "Gemini request failed". A retry a few minutes later worked. The phone check caught a gap the tests didn't: no retry on a transient Gemini outage, filed as #67 (https://github.com/Vee1234/LanguageAgent/issues/67, under core, waits for #35).
- [ ] [use] Deploy, then a new word on the phone appears in My words: deployed (`supabase functions list`: generate-word ACTIVE, version 5, updated 2026-11-23 21:29:57 UTC, verify_jwt on); phone check pending.
- [x] [use] The migration applies without errors: `supabase db push --remote` said "Remote database is up to date" (no pending migrations), and `supabase migration list --remote` shows 20261117000000 (shared cache) applied on the hosted project. It had already been applied earlier, so the ticket's premise ("written but not deployed") was out of date for the schema.
Relevant edge or failure case and result: The same word from two accounts gives one shared `words` row and two `user_cards` rows. ✅ A query on production returned 1 / 2 / 2.
Qodo findings I investigated, including any missed or irrelevant feedback: No findings on the PR, which was docs only. The real problem, Gemini overload in production, was something only the phone check could catch.
What reached the coding agent and what changed in the fix: The function logs did. The 503 became ticket #67 (retry and "try again"), and a 404 from a model switch became a note in `docs/setup.md`.

<!-- ticket #36 -->
## Ticket → branch → PR
Ticket link: https://github.com/Vee1234/LanguageAgent/issues/36
Branch and PR link: `ticket-36-card-completeness` → https://github.com/Vee1234/LanguageAgent/pull/70
Acceptance criteria checked, with observed results and evidence: - ✅ `cardFields` returns definition, register, emotional colour and example, each with a value or marked missing: test in `cards.test.ts`, red first, then green.
- ✅ My own note overrides the generated one: test in `cards.test.ts`.
- ✅ `<Card>` shows "Missing" and never a default: test in `Card.test.tsx`.
- ✅ My words renders through `<Card>`: test in `Words.test.tsx`.
- ✅ A word saved before register existed shows register as missing: *dégager* shows "Register: Missing" (checked in the browser on my Mac; I accepted that instead of the phone).
Relevant edge or failure case and result: An empty or whitespace-only note counts as missing ✅ (test in `cards.test.ts`).
Qodo findings I investigated, including any missed or irrelevant feedback: No findings on either commit. It missed nothing the ticket asked for: every criterion was checked by a test or by hand.
What reached the coding agent and what changed in the fix: No review findings. The ticket analysis flagged one criterion as "no evidence" because its test name contained commas; the agent renamed the test and the check passed.

## What I learned
Did the factory deliver what the tickets asked for? #6 partly: the release is live and the shared cache works across accounts, but new words failed while Gemini was overloaded (follow-up #67). #36 yes: all six checks pass, five from tests that failed first.
What I updated in the rules, skills, or review setup, and why (or why no update was needed): I added a skill step that fills this post from evidence as each ticket moves. No rule change: Qodo found nothing on either PR, and the tickets' own checks caught what mattered (the Gemini outage on #6).
- `docs/setup.md`: GEMINI_MODEL and reading 503 vs 404.
- Skills: a `discussion_post.py` script plus ticket-resolver and hackathon-log steps (PR #66), so this comment is filled in from evidence as the ticket moves.
- No new review rule: Qodo had no findings to learn from on a docs-only release PR.
