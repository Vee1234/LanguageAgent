"""Tickets waiting in the project board's Needs Approval column.

The factory moves a ticket there when its PR is built and reviewed but only the owner may merge
it (docs/factory.md, "Running on its own"). This lists them, and moves a ticket there.

Usage:
    python3 scripts/approvals.py [--all]    # list the tickets waiting for approval (first 50 unless --all)
    python3 scripts/approvals.py --hook     # the same, as PostToolUse context after a git push
    python3 scripts/approvals.py set N [--status "In Review"]   # move ticket N (default: Needs Approval)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_TITLE = "Language Agent"
STATUS_FIELD = "Status"
PROJECT_LIMIT = 1000  # gh lists only 30 projects by default
IN_REVIEW = "In Review"            # the PR is open and the Qodo cycle is running
NEEDS_APPROVAL = "Needs Approval"  # the cycle is resolved and only the owner can finish it
STAGES = ["Todo", "In progress", IN_REVIEW, NEEDS_APPROVAL, "Done"]


# --- pure ------------------------------------------------------------------------

def needs_approval(items: list[dict], repo: str) -> list[dict]:
    """This repo's issues whose board status is Needs Approval, by number."""
    out = []
    for i in items:
        c = i.get("content") or {}
        if i.get("status") == NEEDS_APPROVAL and c.get("type") == "Issue" and c.get("repository") == repo:
            out.append({"number": c["number"], "title": c.get("title", i.get("title", "")), "url": c.get("url", "")})
    return sorted(out, key=lambda t: t["number"])


REPORT_LIMIT = 50  # longer reports end with a visible "...and N more" line, never a silent cut


def render(tickets: list[dict], repo: str, limit: int | None = REPORT_LIMIT) -> str:
    """Numbers, and links built from them, only. Titles are text other people could write, and this
    report goes into the agent's context, so it never carries them."""
    if not tickets:
        return "No tickets are waiting in Needs Approval."
    lines = [f"{len(tickets)} ticket(s) waiting in Needs Approval:"]
    shown = tickets if limit is None else tickets[:limit]
    for t in shown:
        prs = ", ".join(f"PR #{int(p)} https://github.com/{repo}/pull/{int(p)}" for p in t.get("prs", [])) or "no open PR"
        lines.append(f"- #{int(t['number'])} https://github.com/{repo}/issues/{int(t['number'])} ({prs})")
    if len(shown) < len(tickets):
        lines.append(f"...and {len(tickets) - len(shown)} more: run `python3 scripts/approvals.py --all`")
    return "\n".join(lines)


def option_id(fields: dict, field: str, option: str) -> tuple[str, str]:
    """(field id, option id) by name. A missing option is an error: never skip silently."""
    for f in fields.get("fields", []):
        if f.get("name") == field:
            for o in f.get("options", []):
                if o.get("name") == option:
                    return f["id"], o["id"]
    raise LookupError(f"the project board has no '{option}' option in its '{field}' field")


def status_of(items: list[dict], repo: str, number: int) -> str | None:
    for i in items:
        c = i.get("content") or {}
        if c.get("type") == "Issue" and c.get("repository") == repo and c.get("number") == number:
            return i.get("status")
    return None


def item_id(items: list[dict], repo: str, number: int) -> str | None:
    for i in items:
        c = i.get("content") or {}
        if c.get("type") == "Issue" and c.get("repository") == repo and c.get("number") == number:
            return i["id"]
    return None


# --- GitHub ----------------------------------------------------------------------

def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30).stdout


def _project() -> tuple[str, str, str]:
    """(repo, owner, project number) of the board named PROJECT_TITLE."""
    repo = _gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    owner = repo.split("/")[0]
    projects = json.loads(_gh("project", "list", "--owner", owner, "--limit", str(PROJECT_LIMIT), "--format", "json"))["projects"]
    number = next((str(p["number"]) for p in projects if p["title"] == PROJECT_TITLE), None)
    if number is None:
        raise LookupError(f"no project board named '{PROJECT_TITLE}' for {owner}")
    return repo, owner, number


def _items(owner: str, number: str) -> list[dict]:
    return json.loads(_gh("project", "item-list", number, "--owner", owner, "--limit", "500", "--format", "json"))["items"]


def report(read_board, read_labelled, repo: str, limit: int | None = REPORT_LIMIT) -> str:
    """What is waiting for the owner, from two sources: the board's Needs Approval column and open
    PRs labelled needs-approval. A source that can't be read is said plainly, and "nothing
    waiting" is said only when both were read and are empty."""
    problems, board, labelled = [], [], {}
    try:
        board = list(read_board())
    except Exception as e:
        problems.append(f"Couldn't read the board: {e}")
    try:
        labelled = dict(read_labelled())
    except Exception as e:
        problems.append(f"Couldn't read the needs-approval PRs: {e}")
    if not problems and not board and not labelled:
        return "No tickets are waiting in Needs Approval."
    tickets = [{"number": n, "prs": labelled.get(n, [])} for n in sorted(set(board) | set(labelled))]
    lines = problems + ([render(tickets, repo, limit)] if tickets else ["Nothing found in what could be read."])
    out = "\n".join(lines)
    for n in sorted(set(labelled) - set(board)):
        out = out.replace(f"- #{n} ", f"- #{n} [on the label but not the board] ", 1)
    return out


def _board_numbers(repo: str, owner: str, number: str) -> list[int]:
    return [t["number"] for t in needs_approval(_items(owner, number), repo)]


def _labelled_prs() -> dict[int, list[int]]:
    prs = json.loads(_gh("pr", "list", "--state", "open", "--label", "needs-approval", "--limit", "500",
                         "--json", "number,body,headRefName"))
    out: dict[int, list[int]] = {}
    for p in prs:
        m = re.search(r"^Closes #(\d+)\s*$", p["body"] or "", re.M) or re.match(r"^ticket-(\d+)-", p["headRefName"])
        if m:
            out.setdefault(int(m.group(1)), []).append(p["number"])
    return out


def current_report(limit: int | None = REPORT_LIMIT) -> str:
    try:
        repo, owner, number = _project()
    except Exception as e:
        repo = _gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
        return report(lambda: (_ for _ in ()).throw(e), _labelled_prs, repo, limit)
    return report(lambda: _board_numbers(repo, owner, number), _labelled_prs, repo, limit)


def set_status(ticket: int, status: str) -> bool:
    """Move a ticket to a board column (adding it to the board if needed). False if it was already there."""
    repo, owner, number = _project()
    items = _items(owner, number)
    if status_of(items, repo, ticket) == status:
        return False
    pid = json.loads(_gh("project", "view", number, "--owner", owner, "--format", "json"))["id"]
    field, option = option_id(json.loads(_gh("project", "field-list", number, "--owner", owner, "--format", "json")),
                              STATUS_FIELD, status)
    iid = item_id(items, repo, ticket)
    if iid is None:  # not on the board yet: add it
        iid = json.loads(_gh("project", "item-add", number, "--owner", owner, "--format", "json",
                             "--url", f"https://github.com/{repo}/issues/{ticket}"))["id"]
    _gh("project", "item-edit", "--id", iid, "--project-id", pid, "--field-id", field,
        "--single-select-option-id", option)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--hook", action="store_true")
    p.add_argument("--all", action="store_true", help=f"list every ticket, not just the first {REPORT_LIMIT}")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("set")
    s.add_argument("ticket", type=int)
    s.add_argument("--status", default=NEEDS_APPROVAL, choices=STAGES)
    args = p.parse_args(argv)
    if args.cmd == "set":
        set_status(args.ticket, args.status)
        print(f"#{args.ticket} moved to {args.status}")
        return 0
    try:
        text = current_report(None if args.all else REPORT_LIMIT)
    except Exception as e:  # even the repo name couldn't be read: say so, never a traceback
        text = f"Couldn't check Needs Approval: {e}"
    if args.hook:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
              "Approvals check after the push: tell the user this in one or two lines.\n" + text}}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
