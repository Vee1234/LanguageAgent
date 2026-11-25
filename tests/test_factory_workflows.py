"""The factory workflows: the owner's token lives only in jobs that run trusted code from master."""
import re
from pathlib import Path

RUN = (Path(__file__).resolve().parent.parent / ".github/workflows/factory-run.yml").read_text()


def jobs(text: str) -> dict[str, str]:
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z0-9-]*):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def test_the_run_is_split_into_build_verify_and_merge_jobs():
    j = jobs(RUN)
    assert {"build", "verify", "merge"} <= j.keys()
    needs = re.search(r"needs: \[([^\]]*)\]", j["merge"]).group(1).replace(" ", "").split(",")
    assert {"start", "build", "verify"} <= set(needs)


def test_the_owners_token_is_only_in_jobs_on_a_fresh_checkout_of_master_without_the_agent():
    holders = {name: text for name, text in jobs(RUN).items() if "FACTORY_TOKEN" in text}
    assert "merge" in holders and "build" not in holders and "verify" not in holders
    for name, text in holders.items():
        assert "ref: ${{ github.event.repository.default_branch }}" in text, name
        assert "claude-code-action" not in text, name



def test_the_start_job_refuses_a_ticket_that_is_not_the_owners_own_before_anything_runs():
    start = jobs(RUN)["start"]
    assert "python3 scripts/factory.py check-ticket" in start
    assert start.index("check-ticket") < start.index("approvals.py set")


def test_the_agent_job_has_no_oidc_token_and_is_denied_merging_api_calls_and_pushes_to_master():
    build = jobs(RUN)["build"]
    assert "id-token" not in build
    denied = re.search(r'--disallowedTools "([^"]*)"', build).group(1)
    for rule in ["Bash(gh pr merge:*)", "Bash(gh api:*)", "Bash(git push origin master:*)",
                 "Bash(git push origin HEAD:master:*)", "Bash(git push --force:*)"]:
        assert rule in denied, rule


def allowed_tools() -> list[str]:
    build = jobs(RUN)["build"]
    m = re.search(r'--allowedTools "([^"]*)"', build)
    assert m, "the headless agent needs an allowlist: nobody is there to approve a prompt"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def test_the_agent_may_run_exactly_the_commands_the_ticket_workflow_needs():
    allowed = allowed_tools()
    for tool in ["Read", "Edit", "Write", "Glob", "Grep",
                 "Bash(python3 -m pytest:*)", "Bash(npm --prefix app:*)",
                 "Bash(python3 scripts/factory.py:*)", "Bash(python3 scripts/qodo_review.py:*)",
                 "Bash(python3 scripts/ticket_analysis.py:*)", "Bash(python3 scripts/backlog_order.py:*)",
                 "Bash(git status:*)", "Bash(git diff:*)", "Bash(git add:*)", "Bash(git commit:*)",
                 "Bash(git checkout:*)", "Bash(git branch:*)", "Bash(git ls-remote:*)", "Bash(git push)",
                 "Bash(git push -u origin ticket-:*)", "Bash(gh pr create:*)", "Bash(gh pr view:*)",
                 "Bash(gh pr list:*)", "Bash(gh pr diff:*)", "Bash(gh pr edit:*)", "Bash(gh pr comment:*)",
                 "Bash(gh issue view:*)", "Bash(gh issue list:*)"]:
        assert tool in allowed, tool


def test_the_allowlist_never_opens_merging_the_api_the_forum_or_any_command():
    allowed = allowed_tools()
    assert "Bash" not in allowed and not any(t in allowed for t in ["Bash(*)", "Bash(:*)"])
    for t in allowed:
        assert not t.startswith(("Bash(gh pr merge", "Bash(gh api", "Bash(gh issue edit", "Bash(gh label")), t
        assert "discussion_post" not in t, t  # forum posts need the owner's approval first


NEXT = (Path(__file__).resolve().parent.parent / ".github/workflows/factory-next.yml").read_text()


def test_the_merge_job_starts_the_next_ticket_and_factory_next_only_takes_the_owners_hand_merges():
    # The merge job runs `next` after its cleanup (no race with the ready label). factory-next's
    # merge trigger is for PRs the owner merged by hand, so the two never both run on one merge.
    assert "factory.py merge" in jobs(RUN)["merge"]
    cond = re.search(r"^    if: (.*?)^    runs-on:", NEXT, re.M | re.S).group(1)
    assert "'needs-approval'" in cond and "'agent-stuck'" in cond and "labels.*.name" in cond
