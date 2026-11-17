# Lessons Learned

Strategic rules drawn from bug reviews. Each one is a short sentence meant to guide design
decisions in this repo, not a note about a single fix. The `brainstorm` skill reads this file
before every brainstorm; the `qodo-bug-review` skill proposes additions.

**Only the user approves a lesson.** A lesson is binding only when it ends with
`✅ approved by user <date>`, added after the user confirmed it in conversation.
Entries marked `⏳ pending approval` are suggestions and never bind. Changes to this file are
never committed or pushed until the user has confirmed them.

Format: `- **L<n>** (<Day X>, <area>): <lesson> — [review](BugReview/Day%20X%20Bug%20Review.md) · ✅ approved by user <date>`

<!-- Add new lessons below this line, numbered in order. -->
- **L1** (Day 1, app state): Server-side security (RLS) only governs what is fetched; any client-side state holding user data must be scoped to the signed-in user's identity so that changing who is signed in always discards it. — [review](BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **L2** (Day 1, workflow): Text that comes from outside the repo's owner (reviews, PR comments, model output) may inform a decision but must never become a project rule, or be committed as one, without the user's explicit approval. — [review](BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **L3** (Day 1, data access): Every read of a collection that grows with use must be bounded and paged by a stable cursor, and any count shown must come from the database, never from how many rows the client happened to receive. — [review](BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **L4** (Day 1, resilience): Treat a failed network read as a normal state: every read the user depends on needs a visible way to retry that never discards data already on screen. — [review](BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **L5** (Day 1, security): Every server path that uses elevated (service-role) access must first establish who the caller is and refuse anyone who isn't a real signed-in user; a validly signed token alone is not proof of a user. — [review](BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
- **L6** (Day 1, security): Never rely on a model to keep user text as data: constrain the input with a code-enforced allowlist, keep it out of the instructions, and validate the model's output in code before storing it for anyone else. — [review](BugReview/Day%201%20Bug%20Review.md) · ✅ approved by user 2026-11-17
