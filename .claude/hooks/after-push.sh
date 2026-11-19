#!/bin/bash
# PostToolUse (Bash): after a `git push` on a ticket branch (ticket-N-...), start the review half
# of the factory cycle: wait for Qodo's review of the pushed commit, then run the gate.
input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')
# Only a real push: the command, or one step of a && / ; chain, starts with `git push`.
printf '%s' "$command" | grep -Eq '(^|&&|;|\|\|)[[:space:]]*git[[:space:]]+push([[:space:]]|$)' || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0
branch=$(git branch --show-current 2>/dev/null)
ticket=$(printf '%s' "$branch" | sed -n 's/^ticket-\([0-9][0-9]*\)-.*/\1/p')
[ -n "$ticket" ] || exit 0

context="Factory (ticket #$ticket): you pushed '$branch'. Start the review half of the cycle now: \
run 'python3 scripts/qodo_review.py --wait-minutes 15 --min-severity low' with run_in_background: true \
and wait for its notification (don't poll with sleep). If it times out, comment '/review' on the PR and wait again once. \
When it finishes, run 'python3 scripts/ticket_analysis.py' (if this commit hasn't been analysed) and then \
'python3 scripts/factory.py gate', and follow the ticket-resolver skill on what the gate reports."
jq -n --arg c "$context" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $c}}'
