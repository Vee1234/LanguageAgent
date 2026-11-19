# Backlog

How tickets are structured and the order they are built in. The `backlog-order` skill
(`.claude/skills/backlog-order/`) follows this file, and `scripts/backlog_order.py` reads the
category order from it.

**Principle:** build the foundations first, then add features on top. Within each category,
start with the ticket that would be most painful to change later.

## Structure: epics, issues and sub-issues

Tickets are GitHub issues, nested with GitHub's sub-issues.

| Level | What it is | Labels |
|---|---|---|
| **Epic** | One category: `core` or a feature. | `epic`, `category:<name>` |
| **Issue** | A foundation or a slice of the feature, under its epic. | `change-cost:N` if it has no sub-issues |
| **Sub-issue** | One PR's worth of work, under its issue. | `change-cost:N` |

- A ticket's category comes from the epic above it, so only epics carry `category:` labels.
- A ticket with open sub-issues is a grouping, not a work item. Only tickets with no open
  sub-issues get built, and each is one branch and one PR.
- `core` holds what every feature builds on: schema, security, shared components, release.
  A feature epic holds only what that feature needs.

## Ticket template

```markdown
## Goal
One sentence: what the user can do afterwards.

## Depends on
- #12 (a ticket that must be closed first; one per line, or "- None")

## Standards
L8, Std 1 (the lessons and review standards this ticket must follow)

## Acceptance criteria
- [code] Given … when … then … (becomes a test that fails first)
- [use] On the phone: steps → what I should see

## Edge or failure case
- At least one.

## Out of scope
- What this ticket must not build.

## Change cost
N: stores data? y/n · trust boundary? y/n · shared contract? y/n · external? y/n (one-line reason)
```

The script reads only the `- #N` lines under `## Depends on`. A `#N` mentioned anywhere else
isn't counted as a dependency. Depending on a ticket that has sub-issues means depending on
all of its open sub-issues.

## Change-cost rubric

How painful is this to change once it has shipped and other work is built on it? Answer the
four questions. The cost is the highest level that applies.

| Cost | Question | Why it hurts to change later | Examples here |
|---|---|---|---|
| **5** | **Stores data:** does it create or change the shape of data that gets saved? | Saved rows need a migration or a backfill, and old rows may never get the value (Bug 13). | A migration, the scheduler's stored fields, the "where I met it" sentence |
| **4** | **Trust boundary:** does it decide who can read or write what, or what model output gets stored for everyone? | Mistakes leak data or spend quota, and fixes must be retrofitted to every path (L1, L5, L6). | RLS, the caller check in Edge Functions, sign-ups, rate limits |
| **3** | **Shared contract:** do other tickets build on its shape (API, RPC, component, pure function)? | Every consumer changes with it. | The card-completeness component, the word detail screen |
| **2** | **External:** does it commit to a third-party service, host or library? | Switching means a rewrite of the integration. | Musixmatch, hosting, Gemini Live |
| **1** | None of these: a change local to one screen. | Cheap to change. | Empty states, wording, layout |

Score it with:

```sh
python3 scripts/backlog_order.py score --stores-data y --trust-boundary n --shared-contract y --external n
```

## Ordering rules

`python3 scripts/backlog_order.py order` applies these, in this order:

1. **Dependencies first.** A ticket never comes before an open ticket it depends on.
2. **Category order** (below). A ticket that something in an earlier category depends on is
   pulled forward to that category and flagged; usually it belongs in that category.
3. **Higher change cost first.**
4. **More dependants first:** the ticket that more open work needs, directly or indirectly.
5. **Lower issue number first.**

A ticket with no category, a category that isn't listed below, or no single `change-cost`
label goes to **Needs triage**. It isn't ordered and isn't given a default (L8).
A ticket that depends on open work that isn't ordered (in triage, or itself blocked) goes to
**Blocked**, with what it waits for. A ticket that lists itself in `## Depends on` is **Stuck**.
Code blocks in a ticket are examples: nothing inside them is read as a dependency.
The first ordered ticket with nothing open blocking it is marked **▶**: that's the next one to build.

## Category order

1. `core`: schema, security, shared components and release
2. `review`: spaced-repetition review
3. `notes`: my own notes on a word
4. `decks`: decks
5. `backfill`: filling in missing shared notes
6. `lyrics`: song lyrics
7. `screenshot-import`: words from a screenshot
8. `word-finder`: words I don't know yet
9. `register-ranking`: register-ranking practice
10. `audio-chat`: spoken conversation with feedback
