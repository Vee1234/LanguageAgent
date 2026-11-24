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
