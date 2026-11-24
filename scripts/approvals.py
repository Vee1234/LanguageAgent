"""Tickets waiting in the project board's Needs Approval column.

The factory moves a ticket there when its PR is built and reviewed but only the owner may merge
it (docs/factory.md, "Running on its own"). This lists them, and moves a ticket there.

Usage:
    python3 scripts/approvals.py            # list the tickets waiting for approval
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


def render(tickets: list[dict]) -> str:
    if not tickets:
        return "No tickets are waiting in Needs Approval."
    lines = [f"{len(tickets)} ticket(s) waiting in Needs Approval:"]
    for t in tickets:
        prs = ", ".join(f"PR #{p}" for p in t.get("prs", [])) or "no open PR"
        lines.append(f"- #{t['number']} {t['title']} ({prs}) {t['url']}")
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


def waiting() -> list[dict]:
    repo, owner, number = _project()
    tickets = needs_approval(_items(owner, number), repo)
    prs = json.loads(_gh("pr", "list", "--state", "open", "--json", "number,body,headRefName"))
    for t in tickets:
        t["prs"] = [p["number"] for p in prs
                    if re.search(rf"^Closes #{t['number']}\s*$", p["body"] or "", re.M)
                    or p["headRefName"].startswith(f"ticket-{t['number']}-")]
    return tickets


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
        report = render(waiting())
    except (subprocess.SubprocessError, LookupError, json.JSONDecodeError, KeyError) as e:
        if not args.hook:
            raise
        report = f"Couldn't read the Needs Approval column: {e}"
    if args.hook:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
              "Approvals check after the push: tell the user this in one or two lines.\n" + report}}))
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
