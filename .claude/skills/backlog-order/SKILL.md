---
name: backlog-order
description: Sort and structure this repo's GitHub backlog. Use when asked what to build next, to order or prioritise tickets, to file, split or score a ticket, to place a ticket under an epic, or to pick up the next ticket from the backlog. Orders tickets foundations first (core, then features in a set order) and, within each category, the ticket most painful to change later first.
---

# Backlog order

The rules are in `docs/backlog.md`: the epic → issue → sub-issue structure, the ticket
template, the change-cost rubric, the ordering rules and the category order. Read it every
time; it changes. The ordering itself is done by `scripts/backlog_order.py`, never by hand,
so the same backlog always gives the same order.

## Order the backlog ("what's next?")

1. Run `python3 scripts/backlog_order.py order` (it calls `gh`; add `--json` for raw data).
2. Report the build order, marking the **▶ next** ticket, then each section the script printed:
   **Needs triage**, **Stuck** (a dependency cycle) and **Warnings**. Don't reorder anything
   yourself or explain away a warning.
3. For each triage ticket, propose the fix: its epic, or its change-cost answers (below).
   For each "pulled ahead" warning, say whether the ticket should move to the earlier category.
4. Labels, parents and ticket bodies are visible on GitHub. Make those changes only after the
   user agrees, then rerun step 1.

## File, split or score a ticket

1. **Split** until each ticket is one PR whose acceptance criteria are each marked `[code]`
   (a test that fails first) or `[use]` (steps on the phone and what to see), with at least one
   edge or failure case and an **Out of scope** line. Use the template in `docs/backlog.md`.
2. **Place it.** Something every feature builds on goes under the `core` epic; otherwise under
   its feature's epic. Put it in `## Depends on` as `- #N` lines, one per ticket.
3. **Score it.** Answer the four rubric questions, each with a one-line reason, then run
   `python3 scripts/backlog_order.py score --stores-data … --trust-boundary … --shared-contract … --external …`.
   Put the answers in the ticket's `## Change cost` section and add the `change-cost:N` label.
   If a question is unclear, ask the user. Never pick an answer to get a particular order.
4. **Show the user the draft** (title, parent, body, labels) before creating or editing it on GitHub.

GitHub commands:

```sh
gh issue create --title "…" --body-file body.md --label change-cost:3
gh issue edit 42 --add-label change-cost:5
# Make #42 a sub-issue of #7 (the API takes the child's internal id, not its number):
gh api -X POST repos/{owner}/{repo}/issues/7/sub_issues -F sub_issue_id="$(gh api repos/{owner}/{repo}/issues/42 -q .id)"
# A new epic needs its labels:
gh label create epic; gh label create category:lyrics
```

## Pick up the next ticket

1. Take the **▶** ticket from the order. If it has an unanswered decision, or needs the
   user's own accounts or phone (deploys, store setup), say so and stop.
2. Read it in full with `gh issue view N`, and check that its dependencies are closed.
3. Create a branch `ticket-N-<short-name>` from the default branch, and build it test-first
   (see AGENTS.md), within the ticket's **Out of scope** line.
4. Open the PR with `Closes #N`, the ticket's link, and its acceptance criteria copied in,
   each ticked only once a test or a check on the phone shows it.
