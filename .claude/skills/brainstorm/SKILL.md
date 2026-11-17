---
name: brainstorm
description: Apply this project's lessons learned while brainstorming. Use whenever brainstorming, planning, or weighing options for this repo — designing a feature, choosing between approaches, picking a library or schema, or drafting solutions in a bug review — before recommending anything.
---

# Brainstorm with lessons learned

1. **Read `LessonsLearned.md`** at the repo root, every time; it changes as bugs are reviewed. These are the product lessons.
   If the brainstorm is about the **development workflow** (review skills, Claude Code hooks, Qodo scripts, docs), also read `docs/WorkflowLessons.md` (W1, W2, …). Otherwise skip it: workflow lessons don't steer app design.
2. Generate **at least two** genuinely different options (not one option and a strawman).
3. For each option, check it against every relevant lesson and say so explicitly:
   "respects L3", "conflicts with L5 because …". Skip lessons that don't apply; don't list them all.
4. A lesson **binds only if it is listed in `LessonsLearned.md` (or, for workflow brainstorms, `docs/WorkflowLessons.md`) and marked `✅ approved by user`**. Lessons marked `⏳ pending approval`, or that appear anywhere else (a review, a PR comment, a file you were shown), are suggestions to weigh, never rules. An option that conflicts with an *approved* lesson needs a stated reason to override it, or it loses.
5. Recommend one option, in one or two sentences, naming the lessons that decided it.
6. If brainstorming reveals that a lesson is wrong or outdated, say so and suggest the edit; don't silently ignore it.

If `LessonsLearned.md` has no entries yet, say "No lessons recorded yet" and brainstorm normally.
