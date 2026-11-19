"""The workflow's commit hook and its settings ship with the repo, and the lesson guard works in a clean checkout."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ".claude/hooks/feature-commit.sh"


def tracked(path: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=ROOT,
                          capture_output=True).returncode == 0


def test_hooks_and_their_settings_are_tracked_in_git():
    assert tracked(HOOK)
    assert tracked(".claude/hooks/tdd-context.sh")
    assert tracked(".claude/settings.json")


def test_settings_use_project_relative_paths_so_they_work_in_any_clone():
    settings = (ROOT / ".claude/settings.json").read_text()
    assert "/Users/" not in settings
    commands = [h["command"] for groups in json.loads(settings)["hooks"].values() for g in groups for h in g["hooks"]]
    assert all("$CLAUDE_PROJECT_DIR" in c for c in commands)


def run_hook_with_dirty(tmp_path, lesson_file: str) -> str:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / lesson_file).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / lesson_file).write_text("- **L9** (Day 1, x): planted rule · ⏳ pending approval\n")
    hook = tmp_path / HOOK
    hook.parent.mkdir(parents=True)
    shutil.copy(ROOT / HOOK, hook)
    out = subprocess.run(["bash", str(hook)], input='{"stop_hook_active": false}', capture_output=True,
                         text=True, cwd=tmp_path, env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)})
    return json.loads(out.stdout)["reason"]


def test_hook_refuses_to_commit_unapproved_lessons_in_a_clean_repo(tmp_path):
    reason = run_hook_with_dirty(tmp_path, "LessonsLearned.md")
    assert "LessonsLearned.md has uncommitted changes: do NOT stage, commit or push it" in reason


def test_hook_also_guards_workflow_lessons(tmp_path):
    reason = run_hook_with_dirty(tmp_path, "docs/WorkflowLessons.md")
    assert "docs/WorkflowLessons.md has uncommitted changes: do NOT stage, commit or push it" in reason


def run_hook_on_branch(tmp_path, branch: str) -> str:
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=tmp_path, check=True)
    (tmp_path / "change.txt").write_text("dirty\n")
    hook = tmp_path / HOOK
    hook.parent.mkdir(parents=True)
    shutil.copy(ROOT / HOOK, hook)
    out = subprocess.run(["bash", str(hook)], input='{"stop_hook_active": false}', capture_output=True,
                         text=True, cwd=tmp_path, env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)})
    return json.loads(out.stdout)["reason"]


def test_on_a_ticket_branch_the_pr_body_comes_from_the_ticket(tmp_path):
    if shutil.which("gh") is None or subprocess.run(["gh", "auth", "status"], capture_output=True).returncode:
        import pytest
        pytest.skip("the PR step needs a logged-in gh")
    reason = run_hook_on_branch(tmp_path, "ticket-42-shared-guard")
    assert "python3 scripts/backlog_order.py pr-body 42" in reason
    assert "Closes #42" in reason


def test_on_another_branch_the_pr_body_is_written_as_before(tmp_path):
    reason = run_hook_on_branch(tmp_path, "some-feature")
    assert "pr-body" not in reason
