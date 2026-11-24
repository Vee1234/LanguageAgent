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

## Running on its own (auto-merge)

Two GitHub Actions workflows run the cycle without a session:

```
PR merged ──▶ factory-next ──▶ label "ready-for-agent" ──▶ factory-run ──▶ factory.py merge
              (factory.py next: backlog_order's      (Claude Code: ticket-resolver      │
               next ticket, no AI)                    until the gate passes)            ▼
                                                                    merge │ needs-approval │ agent-stuck
```

- **Next ticket.** `factory.py next` labels backlog_order's next ticket: nothing open blocks it,
  it isn't already in a PR, and within its category it is the most painful to change later. It does
  nothing while any open ticket is `ready-for-agent` or `agent-stuck`, so there is one at a time.
- **One agent at a time.** `factory-run` uses a concurrency group, so two runs never take the same ticket.
- **Retry limit.** Each head the gate finds work on is a round, recorded as a
  `<!-- factory-round head=SHA -->` PR comment. After **3** rounds the gate stops blocking and
  `factory.py merge` labels the PR and ticket `agent-stuck`. A run that ends before the gate
  finishes (Qodo never reviewed, no PR) is also `agent-stuck`.
- **Who decides the merge.** You do, per ticket, before the work starts: label the ticket
  `auto-merge-ok`. Only the repo owner adding it counts; a bot or the agent adding it doesn't,
  and removing it withdraws approval. The agent runs with the job's own token, so it can't
  act as you.

`factory.py merge` merges (squash, only at the head it checked) when **all** of these hold:

1. the gate passed: the analysis passed, Qodo reviewed the head commit, every finding at or above the threshold has a clearing verdict;
2. the owner labelled the ticket `auto-merge-ok`;
3. no **serious** finding is still in Qodo's latest review. Serious means in scope (or naming no files)
   and **high or critical**, or **medium and a 🐞 Bug** (not working as intended, security included).
   An unreadable severity or kind counts as serious. A serious finding clears only by being fixed,
   never by the agent's own `not-a-bug` or `out-of-scope` verdict.

Otherwise the PR is labelled `needs-approval` with the reasons, the ticket moves to the
**Needs Approval** column of the "Language Agent" project board, and you merge it or not.
After every push, the `after-push.sh` hook lists what is in that column (the `approvals` skill;
`python3 scripts/approvals.py` on demand).
A `[use]` check about the phone needs `user:` evidence, so those tickets always come to you.

Setup: repo secrets `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) and `FACTORY_TOKEN` (a
classic token with the `repo`, `workflow` and `project` scopes: a label or merge made with
`GITHUB_TOKEN` would not start the next workflow, and the board is a user project), and the labels `ready-for-agent`,
`auto-merge-ok`, `needs-approval` and `agent-stuck`.
