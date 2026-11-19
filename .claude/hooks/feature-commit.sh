#!/bin/bash
# Stop hook: when Claude finishes a turn with uncommitted or unpushed work,
# run the test suites, then block the stop once and ask Claude to
#   - fix the tests (if red), or
#   - commit + push + open/update a PR (if green and the work is a finished feature).
# Claude decides whether it is a finished feature and writes the commit message and PR description.

input=$(cat)
active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false')

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

dirty=$(git status --porcelain)
ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)
branch=$(git branch --show-current)

if [ -z "$dirty" ] && [ "$ahead" = "0" ]; then
  # Everything is committed and pushed. On a ticket branch, the factory gate decides whether the
  # ticket is finished. It blocks again only when its state changed, so this can't loop forever
  # even when Claude is already continuing because of this hook.
  if printf '%s' "$branch" | grep -Eq '^ticket-[0-9]+-' && [ -f scripts/factory.py ]; then
    python3 scripts/factory.py gate --hook 2>/dev/null || true
  fi
  exit 0
fi

# Already continued once because of this hook: let Claude stop (prevents loops).
if [ "$active" = "true" ]; then
  exit 0
fi

# --- Run the test suites -------------------------------------------------
failures=""
py_out=$(python3 -m pytest -q 2>&1); py_status=$?
# pytest exit 5 = no tests collected; treat as pass
if [ $py_status -ne 0 ] && [ $py_status -ne 5 ]; then
  failures+=$'\n--- pytest ---\n'"$(printf '%s' "$py_out" | tail -25)"
fi
if [ -f app/package.json ] && [ -d app/node_modules ]; then
  app_out=$(npm --prefix app test --silent 2>&1); app_status=$?
  if [ $app_status -ne 0 ]; then
    failures+=$'\n--- app (vitest) ---\n'"$(printf '%s' "$app_out" | tail -25)"
  fi
fi

if [ -n "$failures" ]; then
  reason="Feature commit hook: tests are RED, so do not commit. If you are mid red-green-refactor and these failures are the expected RED step, say so and stop; otherwise fix the code until the suites pass.$failures"
  jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
  exit 0
fi

# --- Green: commit, push, PR ----------------------------------------------
default_branch=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')
default_branch=${default_branch:-master}

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  pr_step="Then make sure a PR exists for '$branch' into '$default_branch': check with 'gh pr view $branch'. \
If there is none, create it with 'gh pr create --base $default_branch --head $branch --title <title> --body <body>'. \
If one exists, update its body with 'gh pr edit $branch --body <body>' so it covers the new commits. \
The body should have: a Summary (what the feature does and why), a Changes list, and a Testing section (which tests were added and that they pass), \
ending with the line: 🤖 Generated with [Claude Code](https://claude.com/claude-code)"
else
  pr_step="Skip the PR: the GitHub CLI (gh) is not installed or not logged in — tell the user to run 'brew install gh' and 'gh auth login'."
fi

# A ticket branch (ticket-N-...) gets its PR body from the ticket, so it always says "Closes #N".
ticket=$(printf '%s' "$branch" | sed -n 's/^ticket-\([0-9][0-9]*\)-.*/\1/p')
if [ -n "$ticket" ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  pr_step="Then make sure a PR exists for '$branch' into '$default_branch': check with 'gh pr view $branch'. \
This is ticket #$ticket's branch: generate the body with 'python3 scripts/backlog_order.py pr-body $ticket > <file>' \
(it fills .github/pull_request_template.md with Closes #$ticket, the ticket link and its acceptance criteria), \
then fill in its Summary, Changes and Testing sections. If there is no PR, create it with \
'gh pr create --base $default_branch --head $branch --title <title> --body-file <file>'. \
If one exists, never start from the template again: run 'python3 scripts/backlog_order.py pr-body $ticket --pr $branch > <file>', \
which keeps its ticked criteria, their evidence and the Review and verification section and adds any criteria the ticket gained, \
update Summary, Changes and Testing in that file, then 'gh pr edit $branch --body-file <file>'."
fi

if [ "$branch" = "$default_branch" ]; then
  pr_step="You are on the default branch '$branch': do not open a PR. Ask the user before pushing directly to it."
fi

# Lesson files only change with the user's explicit approval (L2): never auto-commit them.
lessons_step=""
for lessons in LessonsLearned.md docs/WorkflowLessons.md; do
  if git status --porcelain -- "$lessons" | grep -q .; then
    lessons_step+="$lessons has uncommitted changes: do NOT stage, commit or push it. Show the user the exact lesson text and ask them to approve it; only after they confirm in conversation, mark it '✅ approved by user <date>' and commit it on a later turn. "
  fi
done

reason="Feature commit hook: tests are GREEN. ${lessons_step} The repo has uncommitted changes and/or $ahead unpushed commit(s) on '$branch'. \
If this turn finished a new feature (or a complete, working change), commit it now with a descriptive message \
— stage specific files, never .env, .env.local or other secrets — then push with 'git push' (use 'git push -u origin $branch' if there is no upstream). \
Group unrelated changes into separate commits. $pr_step \
If the work is unfinished or only exploratory, do not commit; just stop and say so briefly."

jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
