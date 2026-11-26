# The factory cycle

How a ticket goes from the backlog to a finished PR, and how review feedback is used before
the next ticket. The skills follow this file. The rules are enforced by
`scripts/ticket_analysis.py`, `scripts/review_triage.py` and `scripts/factory.py`, and by two
hooks in `.claude/hooks/`.

```
ticket created ──▶ PR opened ──▶ ticket analysis ──▶ Qodo review ──▶ gate
(backlog-order)    (ticket-resolver)  (ticket-analysis)                │
                        ▲                                              │ work: fix, triage, re-analyse
                        └──────────────── ticket-resolver ◀────────────┘
                                                                       │ pass
                                                          step 7: use the feedback ──▶ next ticket
```

The cycle repeats until the **gate passes**:
- the ticket analysis passed on the PR's head commit;
- Qodo has reviewed that same commit;
- no finding at or above the relevance threshold is left without a clearing verdict.

**When it stops (the retry limit).** A *round* is a pushed commit that has been analysed and
reviewed by Qodo and still has work left. It is recorded once per commit as a
`<!-- factory-round head=SHA -->` PR comment, counted only from the factory's job token or the
owner. For the first **3** rounds every finding is the agent's to fix, serious ones included.
From the 4th commit on, only **high and critical** findings are (an unreadable severity counts
as high). Once none of those is left, the gate's status is `handover`: the agent posts one PR
comment listing the medium and low findings for the owner, and stops. So it stops at whichever
comes first: nothing open, or, after 3 rounds, nothing high or critical open. The owner merges.

## Hooks

| Hook | When | What it does |
|---|---|---|
| `after-push.sh` (PostToolUse, Bash) | After a `git push` on a `ticket-N-…` branch | Tells the agent to wait for Qodo's review of the pushed commit in the background, then run the analysis and the gate. |
| `feature-commit.sh` (Stop) | When the agent stops with everything committed and pushed on a `ticket-N-…` branch | Runs `factory.py gate --hook`. With work left, it blocks the stop with the next actions. It blocks again only if the head commit or the actions changed, so it can't loop on a stuck state. Waiting for Qodo, waiting for the user, or a pass all let the agent stop. |

## Ticket analysis

`python3 scripts/ticket_analysis.py [--pr N]` checks the PR against its ticket and saves the
result for the PR's head commit. It checks that:

- the PR says `Closes #N` and is on a `ticket-N-…` branch;
- every criterion and edge case in the ticket is in the PR, word for word, and the PR has none
  the ticket doesn't;
- each ticked `[code]` item names its tests (`— test: tests/x.py::test_y` or
  `— test: app/src/X.test.tsx > name`), and they **pass when run**;
- each ticked `[use]` item has evidence: `— seen: …` (the agent ran the app and saw it) or
  `— user: …` (the user confirmed it). A `[use]` item about the **phone** needs `user:`;
- the three verification commands from AGENTS.md pass.

## Relevance of a Qodo finding (0–5)

Relevance is worked out only from fixed structure: the files under the finding's
`## Fix Focus Areas` heading, the **Applies to** paths of the review standards in AGENTS.md,
the PR's changed files, and Qodo's severity.

| Category | When | Relevance |
|---|---|---|
| `workflow` | Every file it names is under standard 5 (Product only) | 0 |
| `outside-diff` | None of its files is changed in this PR | 1 |
| `unplaced` | It names no files | severity |
| `in-scope` | Otherwise | severity, +1 if a product standard (1–4) covers its files; at most 5 |

Severity: low 1, medium 2, high 3, critical 4. An unreadable severity counts as **high**.

**Threshold: 2.** Findings below it are listed but don't block the gate. Change it with `--threshold`.

## Verdicts

Every finding at or above the threshold needs a verdict, recorded with
`python3 scripts/factory.py verdict …` in `docs/review-ledger.jsonl`. The ledger is
versioned, because later tickets read it.

| Verdict | Needs | Clears the gate? |
|---|---|---|
| `confirmed` | `--tag` and `--test` (the regression test that failed first); `--fix <commit>` once fixed | Only once the finding is gone from Qodo's review of a later commit |
| `not-a-bug` | `--reason`: `missing-context`, `by-design` or `wrong`, and a `--note` | Yes |
| `out-of-scope` | `--new-ticket N`, filed with `backlog-order` | Yes |
| `workflow` | Only for findings on standard-5 files | Yes |

A **tag** names what the finding is about. It must be an approved lesson (`L4`, `W1`), a review
standard (`Std1`–`Std5`), or `new:<slug>` for something no rule covers yet. The script rejects
any other tag, including lessons still waiting for approval.

## Where findings point (step 7)

`python3 scripts/factory.py feedback` applies these counting rules to the whole ledger:

| Signal | Points to |
|---|---|
| The same tag `confirmed` in **2** tickets | **A project rule.** For an existing lesson or standard: clarify it, or add a check. For `new:`: propose a lesson. |
| The same tag `confirmed` in **3 or more** tickets | **A skill**, or a step in one: the same fix keeps being needed. |
| A `not-a-bug` verdict with reason `missing-context` | **Review context:** what Qodo needed (the ticket, a doc, an Applies to path). |
| Any `workflow` finding | **Review context:** Qodo reviewed files standard 5 excludes, so check the standards it uses are on `master`. |
| A `confirmed` finding with no test or fix, or still open in the latest review | **Feedback didn't reach the fix.** |
| A criterion that failed the analysis at a commit where Qodo raised nothing in scope | **A requirement the review missed.** |
| `workflow` findings, and `not-a-bug` with reason `wrong` or `by-design` | **Noise:** irrelevant findings. |

These are proposals. A rule, lesson or skill changes only after the user approves it (L2).

## Running it from a label

You and Claude pick the next ticket together in conversation; nothing picks or labels tickets on
its own. Then **you** add `ready-for-agent` to it. `.github/workflows/factory-run.yml` starts only
when the repo owner adds that label, and runs one ticket at a time (at most 3 hours each):

1. The agent builds the ticket test-first (ticket-resolver) and opens the PR.
2. Before opening it, and before every push, it checks its diff against the **approved** lessons
   in `LessonsLearned.md` and the `AGENTS.md` standards for the files it changed.
3. It waits for Qodo's review, which takes a while, then runs the gate and fixes what it says,
   serious findings included, push after push, until the gate says `pass` or `handover` (see
   *When it stops* above). It ends with one PR comment: a summary, or the findings left for you.
4. **You merge.** The agent never merges and never changes labels.

If the run fails or times out, a separate job labels the ticket `agent-stuck` with a link to the run.

Locked down: the agent uses the job's own token (never yours), can read the ticket but not edit
it, and may run only an allowlist of commands; `master`'s ruleset blocks pushes to it.
Setup: the repo secret `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) and the labels
`ready-for-agent` and `agent-stuck`.

