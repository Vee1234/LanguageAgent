#!/bin/bash
# UserPromptSubmit hook: reminds Claude of the project's red-green-refactor workflow on every prompt.
cat > /dev/null  # discard the prompt payload; this hook only adds context

context='Project workflow (TDD) for any NEW FEATURE or behaviour change — skip for docs, config, questions or brainstorming-only replies:
1. While planning the feature, write unit tests for it first (Python: tests/ with pytest; app: app/src/**/*.test.ts(x) with Vitest).
2. RED: run them and confirm they FAIL for the expected reason. Show the failing output.
3. GREEN: write the minimum code to make them pass; rerun and confirm they PASS.
4. REFACTOR: clean up, rerun, still green.
Test commands: `python3 -m pytest -q` and `npm --prefix app test`.
When you finish, the Stop hook reruns the suites and, if green, has you commit, push and open/update the PR.'

jq -n --arg ctx "$context" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
