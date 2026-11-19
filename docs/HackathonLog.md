# Hackathon log

How each day of the Qodo hackathon was tackled: the workflow, reviews, rules and tooling, not
the language app itself. Kept by the `hackathon-log` skill (`.claude/skills/hackathon-log/`).
Days are hackathon tasks, not calendar dates.

## Day 1: Review a PR with Qodo and act on the findings

### Challenge
Inferred from the repo, because the challenge text wasn't recorded (paste it to replace this):
run Qodo review on a pull request, investigate each finding against the code, and fix what's
real.

### Key decisions
- **Fetch Qodo's review with a script, not by copying it.** It waits until Qodo has analysed
  the PR's current head commit, and keeps only open high and medium findings, so a stale or
  partial review is never worked on. Evidence: `scripts/qodo_review.py`, commits `e9d453e`, `75ff21d`.
- **One bug per section, with a fixed write-up.** Each bug gets its root cause, at least two
  solutions, the chosen fix and its biggest weakness, and a red/green/refactor record.
  Evidence: `BugReview/Day 1 Bug Review.md`, `.claude/skills/qodo-bug-review/`.
- **A learning score decides who fixes what.** Findings that score 1–3 are fixed by the agent;
  findings that score 4–5 are worked through together, so the user learns the concept.
  Evidence: `docs/LearningRubric.md`, `scripts/learning_score.py`, commit `c9abdbe`.
- **Lessons bind only after the user approves them.** Reviews propose lessons; only lessons
  marked approved count (L2). Product lessons L1–L10 are in `LessonsLearned.md`, and workflow
  lessons W1–W3 are in their own file. Evidence: commits `6f3c15d`, `cf30fbc`, `0215cd6`.
- **Brainstorm with the lessons.** The `brainstorm` skill reads the approved lessons and checks
  every option against them before recommending one. Evidence: `.claude/skills/brainstorm/`.
- **Hooks ship with the repo (W3).** A TDD reminder runs on every prompt. A Stop hook runs the
  tests and, if they're green, has the agent commit, push and open or update the PR.
  Evidence: `.claude/settings.json`, `.claude/hooks/`, commit `878413f`.
- **One review round per run, started only by the user.** `/qodo-bug-review` doesn't run on
  its own, and it stops after one round. Evidence: commits `80018c1`, `55070c4`.
- **Days are tasks, not dates.** Day 2's bugs were filed under Day 1. Evidence: commit `0a100d2`.

### Limitations
- The review fetch depends on the layout of Qodo's comment (W1). If Qodo changes its format,
  the parser needs updating.
- The learning-score answers are judgments; the script only makes them consistent.
- The Stop hook blocks only once per stop, to prevent loops, so a second stop goes through
  even if the tests are still red.
- Bug 14 was deferred as a product decision (now issue #12). Bug 6's remaining weakness, that
  there's no rate limit, is issue #34.

### Additional features
- A severity filter, and a loop that runs until no high or medium findings are left.
- A separate workflow-lessons file, so tooling lessons don't steer app design.
- A hook that regenerates `docs/api-shapes.md` when the card models change.

## Day 2: Write project rules that the reviewer enforces

### Challenge
Inferred from the repo, because the challenge text wasn't recorded (paste it to replace this):
write the project's rules in `AGENTS.md` so that the coding agent follows them and Qodo
imports them as review standards, including one "most opinionated rule", and show that the
review enforces them.

### Key decisions
- **`AGENTS.md` describes the product, not just the code.** It has the vision, mission, setup,
  verification commands and the TDD workflow, so both the agent and the reviewer know what the
  app is for. Evidence: commits `00382ac`, `4dbae4b`, PR #18.
- **Rules are about this app, not generic coding style.** They are: More than a translation,
  Real-world examples, Where I met it, and No untested behaviour. Evidence: commit `4dbae4b`.
- **The rules were reformatted so Qodo would import them.** Qodo didn't import the first
  version, so the rules became "Five review standards", each with Applies to (globs), Rule and
  Why. Qodo only imports from `master`. Evidence: PR #19.
- **Standard 5, Product only.** Qodo makes no comments on the maintainer's own workflow
  tooling, because they were noise. Evidence: PR #19.
- **The most opinionated rule is "More than a translation".** A card is never just a
  translation, and anything missing must look missing. Evidence: `AGENTS.md`.
- **A probe PR tested the reviewer.** PR #20 broke each standard on purpose. Qodo flagged
  standards 1–4 (three high and two medium findings) and stayed silent on the planted
  off-by-one in `scripts/learning_score.py`, as standard 5 requires. Evidence: PR #20.

### Limitations
- Rule changes reach Qodo only once they're merged to `master`.
- Standard 5 means real bugs in the tooling also go unreviewed. The off-by-one planted in
  PR #20 was ignored, as designed, but the tooling's own tests are now its only check.
- The standards are enforced by review, not by code. Day 3 adds tickets that make standard 1
  and standard 3 testable (#36, #37).
- Open: close PR #20 without merging it.

### Additional features
- Probing the reviewer with planted violations, with a table of the expected result for each standard.

## Day 3: Connect the factory to the backlog

### Challenge
Connect a ticketing system to the coding agent through MCP or a CLI. Then have the agent work
through backlog tickets one at a time, each on its own branch with a PR that includes the
ticket link and its acceptance criteria. Run Qodo review on each PR, check the delivered
behaviour against every acceptance criterion (including an edge or failure case), and feed what
the review found into the rules, skills or review setup before the next ticket.

### Key decisions
- **Use GitHub Issues as the ticketing system, through the GitHub CLI.** The tickets were
  already GitHub issues, so no new tool was needed. The cloud session read them through the
  GitHub MCP; on the laptop the agent uses `gh` (including `gh api graphql` for parent links).
- **Every acceptance criterion is checkable.** Each one is marked `[code]` (a test that fails
  first) or `[use]` (steps on the phone and what to see), and every ticket has an edge case
  and an Out of scope line. This came from comparing checklists by type of ticket with
  per-ticket Given/When/Then, and combining them.
- **Foundations first, then features.** This was compared with "start small and expand" and
  chosen because it builds the shared principles in once and limits feature creep.
- **Structure: one epic per category, then issues, then sub-issues.** The categories are
  `core`, then one per feature. Tickets inherit their category from their epic, and only
  tickets with no open sub-issues get built. Evidence: `docs/backlog.md`, epics #22–#31.
- **Within a category, build first what would be most painful to change later.** A change-cost
  rubric scores 5 for stored data, 4 for a trust boundary, 3 for a shared contract, 2 for an
  external commitment and 1 for local changes. Ties go to the ticket that more work depends on.
  A script does the ordering, so it's repeatable. Evidence: `scripts/backlog_order.py`,
  `.claude/skills/backlog-order/`, PR #21.
- **Unscored tickets go to triage, not to a default.** Evidence: #17, which stays in triage
  until it's split.
- **The backlog tooling is excluded from Qodo review** under standard 5. Evidence: PR #21.
- **The tree was created on GitHub:** 10 epics and 43 new tickets (#32–#64), with the original
  issues placed under them. The shared Gemini guard (#35) moved into `core` because nine tickets
  across four features need it.

- **Two skills: one creates tickets, one resolves them.** `backlog-order` creates, splits,
  scores and orders tickets. `ticket-resolver` takes one ticket at a time through seven steps:
  pick, read, build test-first on its own branch, open a PR with the ticket and its criteria,
  run the Qodo review, check every criterion and an edge case, and use the feedback before the
  next ticket. Using the feedback means fixing confirmed problems and repeating the checks;
  deciding whether a finding calls for a rule, a skill or more review context; checking that
  the feedback reached the fix; and noting what the review missed or got wrong. Evidence:
  `.claude/skills/ticket-resolver/`.

### Limitations
- Nearly every ticket depends on #6 (release the shared cache), which needs the user's Supabase
  login. Dependencies are all-or-nothing: there's no way to say a dependency is needed only for
  the `[use]` checks.
- The new issues aren't on the Projects board yet. Adding them needs the `project` permission
  for `gh` (`gh auth refresh -s project`).
- The scripts that built the tree were run from a scratch folder and aren't in the repo (W3).
  The tree on GitHub is now the record.
- The change-cost answers are judgments. The script only makes the ordering consistent.
- The ordering script warns when a later category blocks an earlier one, but not when one
  ticket is needed by many later categories (as #35 was).
- Qodo hasn't reviewed PR #21 yet, and no ticket has gone through the factory yet.

### Additional features
- The ordering script marks the next ticket to build (▶), detects dependency cycles, and flags
  blockers pulled ahead of their category.
- `backlog_order.py score` turns the four rubric answers into a cost.
- Each PR gets a **Review and verification** section, laid out like the Day 3 discussion post:
  criteria with evidence, the edge case, the Qodo findings and how each was classified, what the
  review missed, what reached the fix, and follow-up changes.
