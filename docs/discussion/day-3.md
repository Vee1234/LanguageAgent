<!-- discussion-post {"day": 3, "url": "https://github.com/orgs/qodo-hackathon/discussions/5", "repeat": "## Ticket → branch → PR", "repeat_labels": ["Ticket link:", "Branch and PR link:", "Acceptance criteria checked, with observed results and evidence:", "Relevant edge or failure case and result:", "Qodo findings I investigated, including any missed or irrelevant feedback:", "What reached the coding agent and what changed in the fix:"]} -->
<!-- Draft of the Day 3 comment for https://github.com/orgs/qodo-hackathon/discussions/5. Fill it with scripts/discussion_post.py as the work happens; post it only after the user approves the text. -->

## My ticketing connection
Ticketing system: GitHub Issues: epics → issues → sub-issues, ordered by `scripts/backlog_order.py`, on a GitHub Projects board (projects/3).
Connection used (MCP or CLI): CLI: the GitHub CLI (`gh issue list`, `gh issue view`, and `gh api graphql` inside the ordering script).
How I checked the agent could list and read my tickets: The agent ran `gh issue list --state open` (58 open tickets, e.g. #64 Register ranking practice screen) and `gh issue view 6`, which read back #6's goal, dependencies, standards, acceptance criteria, edge case and Out of scope line. `backlog_order.py order` then ordered the whole backlog and marked #6 ▶.

<!-- ticket #6 -->
## Ticket → branch → PR
Ticket link: https://github.com/Vee1234/LanguageAgent/issues/6 (Release the shared cache: run the migration and deploy generate-word)
Branch and PR link: Not recorded
Acceptance criteria checked, with observed results and evidence: Not recorded
Relevant edge or failure case and result: Not recorded
Qodo findings I investigated, including any missed or irrelevant feedback: Not recorded
What reached the coding agent and what changed in the fix: Not recorded

## What I learned
Did the factory deliver what the tickets asked for? Not recorded
What I updated in the rules, skills, or review setup, and why (or why no update was needed): Not recorded
