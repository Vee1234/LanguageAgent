# Learning Rubric

How `/qodo-bug-review` decides which findings Claude fixes alone and which the user works
through with Claude. Each finding gets a **learning score from 1 to 5**: how valuable it is for a
junior software engineer to solve it themselves.

- **1–3 → Claude fixes it** in the loop: brainstorm, TDD, write-up, proposed lesson.
- **4–5 → we do it together:** Claude explains the concept and asks a guiding question, and doesn't hand over the fix.

The answers below are judgments; `scripts/learning_score.py` does the arithmetic, so the same
answers always give the same score. Record every answer with a **one-line reason**.

## Step A: gate
Is the bug in the **product**: the app, the database and its schema or RLS, the Edge Function, or the
data model? Or is it in the **development workflow**: the review skills, Claude Code hooks, Qodo
scripts, docs?
- Workflow → **score 1**. Stop.
- Product → start at **1** and add one per "yes" below.

## Step B: five questions (+1 each)

| # | Question | Yes when… |
|---|---|---|
| **Q1 Transferable** | Would the same concept apply in a *different* project or stack? | It's a principle (access control, paging, retries, consistency, caching, validating untrusted input), not a quirk of this code or library. |
| **Q2 Multi-user and data safety** | Does it affect **who can see or change which data**, shared versus personal data, or data being lost, corrupted or wrongly kept? | RLS, auth, leaks between users, a shared cache, writes that overwrite someone else's data. |
| **Q3 New concept** | Is the concept **not** already in an approved lesson (`LessonsLearned.md`) or in **Concepts covered** below? | Look it up; don't guess. |
| **Q4 Real trade-off** | Are there **at least two genuinely different fixes**, each with a real downside? | Not a one-line fix with one obvious answer. |
| **Q5 User experience** | Does fixing it improve the experience against **one of Nielsen's 10 usability heuristics**? Name the number. | See the list below. A change the user never notices is "no". |

Nielsen's 10 usability heuristics:
1. Visibility of system status
2. Match between the system and the real world
3. User control and freedom
4. Consistency and standards
5. Error prevention
6. Recognition rather than recall
7. Flexibility and efficiency of use
8. Aesthetic and minimalist design
9. Help users recognise, diagnose and recover from errors
10. Help and documentation

## Step C: adjustments, applied in this order (product bugs only; a workflow bug stays at 1 even if Q2 would be yes)
1. **Cap:** if Q3 and Q4 are both "no" (nothing new, nothing to decide), the score is **at most 2**.
2. **Floor:** if Q2 is "yes", the score is **at least 4**. Multi-user and data-safety bugs always go to the user, and this beats the cap.
3. The score never exceeds **5**.

**When unsure, answer "yes".** A higher score means we work through it together, so mistakes err
towards learning, not towards Claude quietly fixing it.

"Hook" in the examples means a **React hook** (`useEffect`, state, effects). Claude Code hooks are
workflow, so they score 1.

## Calibration (the user's own labels)

| Bug | Gate | Q1 | Q2 | Q3 | Q4 | Q5 | Score | User |
|---|---|---|---|---|---|---|---|---|
| D1 B1: previous user's words stay on screen | product | ✓ | ✓ | ✓ | ✓ | ✗ | 5 | learn |
| D1 B2: untrusted review text plants lessons | workflow | | | | | | 1 | no |
| D1 B3: paging past 1,000 words | product | ✓ | ✗ | ✓ | ✓ | ✓ #1 | 5 | learn |
| D1 B4: failed reads never retry | product | ✓ | ✗ | ✓ | ✓ | ✓ #9 | 5 | learn |
| D1 B5: a non-bug still writes a lesson | workflow | | | | | | 1 | no |

`tests/test_learning_score.py` checks that these answers give these outcomes.

## Concepts covered
Concepts the user has already worked through; Q3 is "no" for a finding about one of these. Add a
line when a 4–5 finding has been worked through together.

- Client state must be scoped to the signed-in user (keyed remount): D1 B1
- Paging large collections with a stable keyset cursor; counts from the database: D1 B3
- Treating a failed network read as a normal state, with retry: D1 B4
- Row-level security and ownership of rows you reference: discussed on Day 1
- Separating shared content from per-user progress (join table with a composite key): discussed on Day 1
- Authentication vs authorisation: a genuine token isn't a user; check the caller first in service-role code: D1 B6
- Prompt injection and defence in depth: allowlist input, isolate instructions, validate output in code: D1 B11
