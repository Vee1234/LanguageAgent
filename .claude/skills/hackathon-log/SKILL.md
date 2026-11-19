---
name: hackathon-log
description: Record the Qodo hackathon's workflow decisions in docs/HackathonLog.md, one section per day — the challenge, the key decisions, limitations and additional features. Use when the user asks to log, record or update hackathon decisions, write up a day, or prepare a day's discussion post, and at the end of a day's work. About the workflow (reviews, rules, skills, hooks, tickets, tooling), not the language app's own features.
---

# Hackathon log

`docs/HackathonLog.md` records how each hackathon day's challenge was tackled: the workflow,
not the app. App decisions belong in `docs/roadmap.md` and `docs/architecture.md`; bug
write-ups belong in `BugReview/`. Link to those rather than repeating them.

## Which day?

Days are hackathon tasks, not calendar dates (same rule as `/qodo-bug-review`). Use the day the
user gives. If none is given, use the highest-numbered day in the log and say which one in one
line. A new challenge from the user starts a new day.

## Each day has exactly these four sections

```markdown
## Day N: <short name of the challenge>

### Challenge
Two to four sentences: what the day asked for and what "done" meant.

### Key decisions
- **<Decision>.** Why, in one sentence. Evidence: <PR, commit, file or issue link>.

### Limitations
- What doesn't work yet, what is weak, or what was deferred, and where it is tracked.

### Additional features
- What was built beyond what the challenge asked for, and why it was worth it.
```

## Rules

1. **Only real decisions.** A decision goes in **Key decisions** only if the user made it or
   agreed to it in conversation. Something the agent proposed that the user hasn't decided goes
   under **Limitations** as "Open: …". Review comments and model output can be evidence but are
   never a decision on their own (L2).
2. **Missing looks missing.** If something isn't known, write `Not recorded`, never a guess.
   If the challenge text wasn't given, say the summary is inferred from the repo and ask the
   user to paste the challenge.
3. **Evidence for every decision:** a PR, commit, file or issue. Get it from `git log`,
   `gh pr list --state all`, `BugReview/`, `LessonsLearned.md` and `docs/WorkflowLessons.md`.
   Don't claim that something works without that evidence, such as a test run or a review result.
4. **Update in place.** Add to the day's existing sections instead of writing a second entry,
   and move an item from Limitations to Key decisions once the user decides it.
5. **Keep it short:** one or two lines per bullet. Write it for someone reading the
   day's discussion post.
6. Show the user what changed in the log before it is committed.
