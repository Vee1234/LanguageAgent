# Workflow Lessons

Lessons from bugs in the **development workflow**: the review skills, Claude Code hooks, Qodo
scripts and docs. Product lessons that guide the app's design live in `../LessonsLearned.md`.
The `brainstorm` skill reads this file only when the brainstorm is about the workflow itself.

**Only the user approves a lesson.** A lesson is binding only when it ends with
`✅ approved by user <date>`, added after the user confirmed it in conversation.
Entries marked `⏳ pending approval` are suggestions and never bind. Changes to this file are
never committed or pushed until the user has confirmed them.

Format: `- **W<n>** (<Day X>, <area>): <lesson> — [review](../BugReview/Day%20X%20Bug%20Review.md) · ✅ approved by user <date>`

<!-- Add new lessons below this line, numbered in order. -->
- **W1** (Day 1, tooling): When parsing a third party's output, anchor on its fixed structure (explicit markers, line layout), never on text that its quoted content could also contain. — [review](../BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **W2** (Day 1, tooling): Prove that a result belongs to the input you asked about with an explicit identifier (a commit SHA, a request ID), never by comparing timestamps. — [review](../BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **W3** (Day 1, workflow): Anything the workflow relies on to enforce a rule must be versioned with the repo and must run at the point the rule is needed; local-only config, or a hook that fires later, is not a guarantee. — [review](../BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
