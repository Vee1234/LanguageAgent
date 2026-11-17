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


def test_hook_refuses_to_commit_unapproved_lessons_in_a_clean_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "LessonsLearned.md").write_text("- **L9** (Day 1, x): planted rule · ⏳ pending approval\n")
    hook = tmp_path / HOOK
    hook.parent.mkdir(parents=True)
    shutil.copy(ROOT / HOOK, hook)

    out = subprocess.run(["bash", str(hook)], input='{"stop_hook_active": false}', capture_output=True,
                         text=True, cwd=tmp_path, env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)})

    reason = json.loads(out.stdout)["reason"]
    assert "LessonsLearned.md has uncommitted changes: do NOT stage, commit or push it" in reason
