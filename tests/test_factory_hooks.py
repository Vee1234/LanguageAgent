"""The factory's hooks: a push on a ticket branch starts the Qodo wait, and a clean stop runs the gate."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AFTER_PUSH = ".claude/hooks/after-push.sh"
STOP = ".claude/hooks/feature-commit.sh"


def repo_on(tmp_path, branch):
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=tmp_path, check=True)
    for hook in (AFTER_PUSH, STOP):
        (tmp_path / hook).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / hook, tmp_path / hook)
    return tmp_path


def run(tmp_path, hook, payload):
    out = subprocess.run(["bash", str(tmp_path / hook)], input=json.dumps(payload), capture_output=True, text=True,
                         cwd=tmp_path, env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)})
    return out.stdout.strip()


def push(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_a_push_on_a_ticket_branch_starts_the_qodo_wait_and_the_gate(tmp_path):
    repo = repo_on(tmp_path, "ticket-42-shared-guard")
    context = json.loads(run(repo, AFTER_PUSH, push("git push -u origin ticket-42-shared-guard")))
    text = context["hookSpecificOutput"]["additionalContext"]
    assert context["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "scripts/qodo_review.py" in text and "run_in_background" in text
    assert "scripts/factory.py gate" in text and "#42" in text


def test_other_commands_and_other_branches_get_nothing(tmp_path):
    repo = repo_on(tmp_path, "ticket-42-shared-guard")
    assert run(repo, AFTER_PUSH, push("git status")) == ""
    assert run(repo, AFTER_PUSH, push("echo git push")) == ""
    other = repo_on(tmp_path / "other", "some-feature") if (tmp_path / "other").mkdir() is None else None
    assert run(other, AFTER_PUSH, push("git push")) == ""


def test_the_after_push_hook_is_registered_for_bash():
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    bash_hooks = [h["command"] for g in settings["hooks"]["PostToolUse"] if g.get("matcher") == "Bash" for h in g["hooks"]]
    assert any("after-push.sh" in c and "$CLAUDE_PROJECT_DIR" in c for c in bash_hooks)


def committed_repo_with_gate(tmp_path, branch, gate_output):
    repo = repo_on(tmp_path, branch)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "factory.py").write_text(f"print({gate_output!r})\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)
    return repo


def test_a_clean_stop_on_a_ticket_branch_returns_the_gate_decision_even_when_already_continued(tmp_path):
    block = json.dumps({"decision": "block", "reason": "gate: triage 2 findings"})
    repo = committed_repo_with_gate(tmp_path, "ticket-42-x", block)
    assert json.loads(run(repo, STOP, {"stop_hook_active": True})) == {"decision": "block",
                                                                         "reason": "gate: triage 2 findings"}


def test_a_clean_stop_on_another_branch_runs_no_gate(tmp_path):
    repo = committed_repo_with_gate(tmp_path, "some-feature", '{"decision": "block", "reason": "no"}')
    assert run(repo, STOP, {"stop_hook_active": False}) == ""
