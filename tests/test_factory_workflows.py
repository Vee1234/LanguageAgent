"""The factory workflow: you add ready-for-agent, the agent builds, self-checks and works
through Qodo's review until the gate passes or hands over. It never merges."""
import re
from pathlib import Path

RUN = (Path(__file__).resolve().parent.parent / ".github/workflows/factory-run.yml").read_text()


def jobs(text: str) -> dict[str, str]:
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z0-9-]*):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def steps(job: str) -> list[str]:
    return re.split(r"^      - ", job, flags=re.M)[1:]


def test_only_the_owner_adding_ready_for_agent_starts_a_run_and_one_runs_at_a_time():
    assert re.search(r"^on:\n  issues:\n    types: \[labeled\]", RUN, re.M)
    build = jobs(RUN)["build"]
    assert "github.event.label.name == 'ready-for-agent'" in build
    assert "github.event.sender.login == github.repository_owner" in build
    assert re.search(r"^concurrency:\n  group: factory\n  cancel-in-progress: false", RUN, re.M)
    assert "timeout-minutes:" in build


def test_the_agent_runs_with_the_jobs_own_token_and_cannot_edit_tickets():
    build = jobs(RUN)["build"]
    assert "FACTORY_TOKEN" not in RUN  # never the owner's token
    assert "github_token: ${{ github.token }}" in build
    assert "issues: read" in build and "issues: write" not in build and "id-token" not in build


def allowed() -> list[str]:
    m = re.search(r'--allowedTools "([^"]*)"', jobs(RUN)["build"])
    assert m, "an agent with nobody to approve prompts needs an allowlist"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def test_the_agent_may_run_exactly_the_commands_its_workflow_needs():
    a = allowed()
    for tool in ["Read", "Edit", "Write", "Glob", "Grep", "Bash(python3 -m pytest:*)", "Bash(npm --prefix app:*)",
                 "Bash(python3 scripts/factory.py:*)", "Bash(python3 scripts/qodo_review.py:*)",
                 "Bash(python3 scripts/ticket_analysis.py:*)", "Bash(git status:*)", "Bash(git diff:*)",
                 "Bash(git add:*)", "Bash(git commit:*)", "Bash(git checkout:*)", "Bash(git push)",
                 "Bash(git push -u origin ticket-:*)", "Bash(gh pr create:*)", "Bash(gh pr view:*)",
                 "Bash(gh pr comment:*)", "Bash(gh issue view:*)"]:
        assert tool in a, tool
    assert "Bash" not in a and "Bash(*)" not in a
    for t in a:
        assert not t.startswith(("Bash(gh pr merge", "Bash(gh api", "Bash(gh issue edit", "Bash(gh label")), t
        assert "discussion_post" not in t, t  # forum posts need the owner's approval first
    denied = re.search(r'--disallowedTools "([^"]*)"', jobs(RUN)["build"]).group(1)
    for rule in ["Bash(gh pr merge:*)", "Bash(gh api:*)", "Bash(git push origin master:*)", "Bash(git push --force:*)"]:
        assert rule in denied, rule


def test_the_agent_self_checks_then_works_through_qodo_until_the_gate_says_stop():
    prompt = jobs(RUN)["build"].split("prompt: |", 1)[1].split("claude_args:", 1)[0]
    for must in ["LessonsLearned.md", "AGENTS.md", "approved", "python3 scripts/qodo_review.py",
                 "python3 scripts/factory.py gate", "pass", "handover", "Never merge"]:
        assert must in prompt, must
    assert prompt.index("LessonsLearned.md") < prompt.index("qodo_review.py")  # self-check before Qodo


def test_a_failed_or_timed_out_run_marks_the_ticket_stuck_from_a_separate_job():
    stuck = jobs(RUN)["stuck"]
    assert "needs: build" in stuck
    assert "needs.build.result == 'failure'" in stuck and "needs.build.result == 'cancelled'" in stuck
    assert "issues: write" in stuck and "--add-label agent-stuck" in stuck and "--remove-label ready-for-agent" in stuck
    assert "claude-code-action" not in stuck and "actions/checkout" not in stuck  # runs no repo code


def test_the_ticket_is_checked_to_be_the_owners_own_before_the_agent_starts():
    build = jobs(RUN)["build"]
    assert "python3 scripts/factory.py check-ticket" in build
    assert build.index("check-ticket") < build.index("claude-code-action")
