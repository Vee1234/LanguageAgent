# Day 3 Bug Review

Source for every bug: Qodo review of PR #21 (backlog order skill), commit `78676d9`.
All seven are in the development workflow (`scripts/backlog_order.py`, the `backlog-order` skill),
so each scores **1/5 (agent)** by the rubric's gate.

**Review-scope note:** bugs 6 and 7 are in `.claude/skills/backlog-order/SKILL.md`. Standard 5
(Product only) says `.claude/**` shouldn't be reviewed, so Qodo didn't apply it here. Both
findings were real, though, and cheap to fix.

## Bug 1: Fenced examples are read as real dependencies
**Source:** Qodo review (PR #21) · **Severity:** High · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow, because it's the backlog tooling, not the app. Score 1.

### Reported issue
A `## Depends on` example inside a code block in a ticket body is parsed as a live dependency.

### Root cause
`scripts/backlog_order.py:80` (`_section`) treats every line as structure. It doesn't know about code
fences, so a fenced `## Depends on` / `- #99` starts a section, and a `# comment` inside a fenced
shell block ends the real one. Failure scenario: a ticket that pastes the template from
`docs/backlog.md` (which is itself fenced and lists `- #12`) gains a dependency on #12 and is ordered
behind it.

### Solutions considered
1. **Track fences in `_section`.** Lines between matching fences are skipped. Pros: fixes every
   reader of sections (dependencies and the category order). Cons: only handles standard ``` and ~~~ fences.
2. **Strip fenced blocks before parsing.** Pros: simple. Cons: a regex over the whole body
   mishandles an unclosed fence and is harder to read. Both options respect W1.

### Chosen solution
Option 1: it follows W1 (anchor on the fixed structure, never on text that quoted content could also contain) at the one place sections are read.

### Biggest weakness
Indented (4-space) code blocks are not treated as code; an example written that way still counts.

### Implementation (TDD)
- **Red:** `test_fenced_examples_are_not_dependencies` failed with `assert [99, 12] == [12]`; `test_a_comment_inside_a_fence_does_not_end_the_section` failed with `assert [12] == [12, 15]`.
- **Green:** `_section` skips everything between a fence and its matching closer: pytest `79 passed`.
- **Refactor:** none needed.

### Lesson learned
> Covered by W1, so no new lesson.

## Bug 2: Tickets blocked by triage work appear in the build order
**Source:** Qodo review (PR #21) · **Severity:** High · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow. Score 1.

### Reported issue
A ticket that depends on an open ticket in triage is still placed in the build order.

### Root cause
`scripts/backlog_order.py:231`: `waiting` counts only *scheduled* dependencies, so a dependency
that was sent to triage counts as satisfied. The old test (`test_next_is_the_first_ticket_with_nothing_open_blocking_it`)
asserted this behaviour, which broke ordering rule 1 in `docs/backlog.md` ("a ticket never comes
before an open ticket it depends on"). Failure scenario: #10 (cost 5) depends on unscored #11, so #10
is listed first with "waits for #11", and a dependant of #10 is ordered as if #10 could be built.

### Solutions considered
1. **New "Blocked" section.** A ticket whose open dependencies aren't all ordered, worked out
   transitively, is taken out of the order and listed with its blockers. Pros: the order only holds buildable work;
   the blocker is named (L8: missing looks missing). Cons: one more section to read.
2. **Keep it in the order with "waits for".** Pros: no change to the output. Cons: breaks rule 1
   and lets a ticket's position depend on work that has no place yet.

### Chosen solution
Option 1: it's the only one consistent with rule 1. It is computed to a fixpoint, so a ticket waiting behind a blocked ticket is blocked too.

### Biggest weakness
If a triage ticket is a blocker, everything behind it disappears from the order until the ticket is triaged. That is correct, but the order can look much shorter.

### Implementation (TDD)
- **Red:** `test_a_ticket_waiting_on_triage_work_is_kept_out_of_the_order` failed with `assert [10, 13, 12] == [12]`; the updated `test_next_is_…` failed with `assert [10, 12] == [12]`.
- **Green:** a `Plan.blocked` list, computed before ordering and rendered as "Blocked: waiting on tickets that aren't ordered". Skill step 2 and `docs/backlog.md` now mention it. pytest `79 passed`.
- **Refactor:** none needed.

### Lesson learned
> None: proposed W4 was rejected by the user.

## Bug 3: A closed parent with open sub-issues satisfies a dependency
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow. Score 1.

### Reported issue
Depending on a closed parent counts as done even though its sub-issues are still open.

### Root cause
`scripts/backlog_order.py:163`: `open_leaves` returned `[]` as soon as the referenced ticket was closed,
before looking at its children. `docs/backlog.md:53` says that depending on a ticket with sub-issues
means depending on all of its open sub-issues. Failure scenario: container #5 is closed early while
#6 is open, and #20, which depends on #5, is ordered before #6.

### Solutions considered
1. **Look at open sub-issues first, whatever the parent's state.** Pros: matches the doc. Cons: a
   parent closed on purpose as "won't do" still blocks through its open children.
2. **Warn instead.** Treat the closed parent as done, but flag its open children. Pros: respects an
   intentional close. Cons: the order would still be wrong by the doc's own rule.

### Chosen solution
Option 1: the doc defines the meaning, and open sub-issues are open work.

### Biggest weakness
Abandoning a parent now needs its sub-issues closed too, otherwise its dependants stay behind them.

### Implementation (TDD)
- **Red:** `test_a_closed_parent_with_open_sub_issues_still_blocks` failed with `assert [20, 6] == [6, 20]`.
- **Green:** `open_leaves` expands open children first. pytest `79 passed`.
- **Refactor:** none needed.

### Lesson learned
> None.

## Bug 4: A ticket that lists itself can be picked next
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow. Score 1.

### Reported issue
A ticket that lists its own number under `## Depends on` is scheduled as if it were free.

### Root cause
`scripts/backlog_order.py:198`: `leaf != n` drops self-references. It exists so that depending on
your own container doesn't count as depending on yourself, but it also dropped an explicit `- #N` on #N.
Failure scenario: a mistyped self-dependency is silently ignored and the ticket is marked ▶.

### Solutions considered
1. **Keep explicit self-edges, so the ticket is reported as Stuck (a 1-cycle).** Pros: reuses the cycle
   report; the container case is unchanged. Cons: "Stuck" reads as a cycle rather than a typo.
2. **Drop it with a warning.** Pros: the ticket stays buildable. Cons: it guesses what the author meant.

### Chosen solution
Option 1: report rather than guess, and the container case is guarded by a new test.

### Biggest weakness
The Stuck section doesn't say *why* a single ticket is stuck; the reader has to spot the self-reference.

### Implementation (TDD)
- **Red:** `test_a_ticket_that_lists_itself_is_stuck_not_scheduled` failed with `assert [10, 12] == [12]`. The guard `test_depending_on_your_own_container_is_not_a_self_dependency` passed before and after.
- **Green:** only an explicit `d == n` keeps the self-edge. pytest `79 passed`.
- **Refactor:** none needed.

### Lesson learned
> None.

## Bug 5: Labels beyond the first 20 are silently dropped
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow. Score 1.

### Reported issue
The GraphQL query reads only 20 labels per issue, so a ticket's category or change-cost label can be cut off.

### Root cause
`scripts/backlog_order.py:256`: `labels(first: 20)` with no check for more pages. Failure scenario:
an issue with 21 labels whose `change-cost:` label falls outside the first 20 goes to triage
for "no change cost", although it has one.

### Solutions considered
1. **Read up to 100 (GitHub's maximum) and fail loudly, naming the issue, if there are more.** Pros:
   small; no silent truncation. Cons: an issue with more than 100 labels stops the whole order.
2. **Paginate labels for each issue.** Pros: complete. Cons: an extra query per affected issue, for a case that is very unlikely here.

### Chosen solution
Option 1: never treat a capped page as the whole set (the same idea as L3); the error says exactly which issue to fix.

### Biggest weakness
It fails instead of degrading: one over-labelled issue blocks ordering until its labels are trimmed.

### Implementation (TDD)
- **Red:** `test_truncated_labels_fail_loudly` failed with `DID NOT RAISE <class 'ValueError'>`.
- **Green:** `labels(first: 100) { … pageInfo { hasNextPage } }`; `parse_graphql` raises `ValueError` naming the issue. pytest `79 passed`.
- **Refactor:** none needed.

### Lesson learned
> None.

## Bug 6: New repositories can't file scored tickets
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow, since it's a skill doc. Score 1.

### Reported issue
The skill uses `change-cost:N` labels without creating them, so `gh issue create --label` fails in a fork.

### Root cause
`.claude/skills/backlog-order/SKILL.md:37-46`: label creation is shown only for epic and category labels.

### Solutions considered
1. **An idempotent setup line:** `gh label create "change-cost:$n" --force` for 1–5. Pros: safe to rerun. Cons: none worth noting.
2. **A setup script.** Pros: testable. Cons: a new file for a five-line loop.

### Chosen solution
Option 1.

### Biggest weakness
It's documentation: nothing checks that an agent runs it.

### Implementation (TDD)
Docs-only (AGENTS.md exempts these from tests).

### Lesson learned
> None: a one-off documentation gap.

## Bug 7: Rescoring a ticket sends it to triage
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow, since it's a skill doc. Score 1.

### Reported issue
`gh issue edit --add-label` adds a second `change-cost:` label, and the script then sends the ticket to triage.

### Root cause
`.claude/skills/backlog-order/SKILL.md:41`: the example only adds a label. The script requires exactly one (`scripts/backlog_order.py:182`).

### Solutions considered
1. **Swap in one edit:** `--remove-label change-cost:<old> --add-label change-cost:<new>`, after checking the current label. Pros: matches the script's rule. Cons: the agent must read the old label first.
2. **Let the script pick the newest label.** Cons: it guesses (conflicts with L8's "never default").

### Chosen solution
Option 1.

### Biggest weakness
Still relies on the agent following the doc. The script does catch a mistake, though, by sending the ticket to triage.

### Implementation (TDD)
Docs-only.

### Lesson learned
> None.

## Proposed workflow lesson
W4 (on planning tools reporting every item they can't place) was proposed and **rejected by the user on 2026-11-19**. No lesson was added.

# Round 2 (PR #21 at `5eb2d80`)

Three medium findings, all workflow, each scored **1/5 (agent)**. Bugs 9 and 10 are again in
`.claude/**`, which standard 5 says Qodo shouldn't review.

## Bug 8: An old PR can hide an active review
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow, since it's backlog tooling. Score 1.

### Reported issue
Only the first 10 PRs that close an issue are read, so an open PR beyond them goes unseen.

### Root cause
`scripts/backlog_order.py:337`: `closedByPullRequestsReferences(first: 10, …)` has no `pageInfo` check. Failure scenario:
a ticket with 10 closed attempts and an 11th, open PR isn't marked "in review", so it's marked ▶
and built a second time.

### Solutions considered
1. **Read up to 100 and fail loudly, naming the issue, if there are more** (the same approach as bug 5). Pros: consistent; tiny. Cons: one such issue stops the whole order.
2. **Paginate the connection for that issue.** Pros: complete. Cons: an extra query path for an extremely rare case.

### Chosen solution
Option 1, for consistency with bug 5's fix.

### Biggest weakness
It's a repeat of bug 5: each new GitHub connection added to the query needs the same check, and nothing enforces it yet.

### Implementation (TDD)
- **Red:** `test_truncated_closing_prs_fail_loudly` failed with `DID NOT RAISE <class 'ValueError'>`.
- **Green:** `first: 100` plus `pageInfo { hasNextPage }`; `parse_graphql` raises `ValueError` naming the issue. pytest `92 passed`.
- **Refactor:** none needed.

### Lesson learned
> None: proposed W5 was rejected by the user.

## Bug 9: Unpushed ticket work goes undetected
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow, since it's a skill doc. Score 1.

### Reported issue
The prior-work check only looks at remote branches.

### Root cause
`.claude/skills/ticket-resolver/SKILL.md:19`: only `git ls-remote`. Failure scenario: work on a local
`ticket-12-…` that was never pushed is missed, a second branch is created, and the agent may switch away with uncommitted changes.

### Solutions considered
1. **Also check `git branch --list`, and require a clean `git status` before switching.** Pros: covers both. Cons: still relies on the agent following the doc.
2. **A script that does the prior-work check.** Pros: testable. Cons: more code than the case needs today.

### Chosen solution
Option 1. Never deleting a local branch without asking protects the only copy of unpushed work.

### Biggest weakness
Docs only; branches not named `ticket-N-*` are still missed.

### Implementation (TDD)
Docs-only.

### Lesson learned
> None.

## Bug 10: Completed tickets can be rebuilt on request
**Source:** Qodo review (PR #21) · **Severity:** Medium · **Learning score:** 1/5 (agent)

### Learning score
Gate: workflow, since it's a skill doc. Score 1.

### Reported issue
A merged PR for the ticket has no instruction, so a named, finished ticket can be built again.

### Root cause
`.claude/skills/ticket-resolver/SKILL.md:20-24`: cases for an open PR, a closed-unmerged PR and a
bare branch, but none for a merged PR. `gh pr list --state all` returns merged PRs too.

### Solutions considered
1. **A "Merged PR" case: report it as resolved and stop; a follow-up goes through `backlog-order`.** Also match `CLOSED` vs `MERGED` explicitly. Pros: closes the gap. Cons: none worth noting.
2. **Rely on the ticket being closed.** Cons: a reopened ticket or `Closes` in a non-default branch breaks it.

### Chosen solution
Option 1.

### Biggest weakness
Docs only.

### Implementation (TDD)
Docs-only.

### Lesson learned
> None.

## Low finding (not fixed)
- *Ticket text can steer the agent's build* (low): listed for the user, not fixed.

## Proposed workflow lesson (round 2)
W5 (capped GitHub connections must check `pageInfo`) was proposed and **rejected by the user on 2026-11-19**. No lesson was added.
