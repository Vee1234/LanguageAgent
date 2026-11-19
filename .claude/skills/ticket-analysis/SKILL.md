---
name: ticket-analysis
description: Check a ticket's PR against the ticket — compare the code and PR with the ticket's goal, acceptance criteria and edge case, run the tests each criterion names, and test the real behaviour in the running app. Use after a ticket PR is opened or updated, when the factory gate asks for run-analysis, or when asked whether a ticket is done. Part of the factory cycle in docs/factory.md, between ticket-resolver rounds.
---

# Ticket analysis

The question is **did this PR deliver the ticket**, not "is the code good" (that's the review).
A clean Qodo review never means the ticket is done. Rules: `docs/factory.md`, "Ticket analysis".

## 1. Read both sides

- Read the ticket with `gh issue view N`: goal, acceptance criteria, edge case, Out of scope.
- Read the PR's diff with `gh pr diff`, and its description.

## 2. Compare the code with the ticket

For each criterion, find the code that delivers it and the test that proves it. Check two more things:
- **Nothing outside Out of scope was built.** List any extra behaviour you find.
- **The goal is met as a whole**, not only criterion by criterion.

These are judgments. Write each one as a finding in the PR's Review and verification section,
never as a tick.

## 3. Test the real behaviour

- **`[code]`:** each ticked item names its tests after `— test:`. The script runs them.
- **`[use]`:** run the app (`npm --prefix app run dev`) and follow the criterion's steps,
  including the edge or failure case. Record exactly what you saw after `— seen:`, with a
  screenshot where it helps.
  - Anything about the **phone**, or that needs the user's accounts, goes to the user with the
    exact steps. Write `— user: …` only with what the user reported.
- **Untested:** if a criterion can't be tested as written, it isn't done. Say so, and say how
  to rewrite it.

## 4. Run the analysis

```sh
python3 scripts/ticket_analysis.py --pr <PR>
```

The script checks `Closes #N` and the branch, that no criterion was dropped or reworded, that
the named tests pass, that every `[use]` item has evidence, and the three verification commands.
It saves the result for the PR's head commit, where the gate reads it. A new commit needs a new analysis.

## 5. Report

Report the result to `ticket-resolver` as the list of items that aren't `pass`, `agent-checked`
or `user-confirmed`, plus your findings from step 2. Copy the result into the PR's
**Review and verification** section. Don't tick anything the script didn't pass.
