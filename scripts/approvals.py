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
        if t.get("prs", []) is None:  # the PR list couldn't be read: claim nothing
            prs = "PR: unknown"
        else:
            prs = ", ".join(f"PR #{int(p)} https://github.com/{repo}/pull/{int(p)}" for p in t.get("prs", [])) or "no open PR"
        tag = "[on the label but not the board] " if t.get("off_board") else ""
        lines.append(f"- #{int(t['number'])} {tag}https://github.com/{repo}/issues/{int(t['number'])} ({prs})")
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


def all_items(fetch) -> list[dict]:
    """Every item on the board. fetch(limit) returns gh's {"items", "totalCount"}: read the total
    first, then that many, and fail if fewer came back. A short read must never look like a
    smaller board (report() shows the error)."""
    total = fetch(1)["totalCount"]
    if total == 0:
        return []
    items = fetch(total)["items"]
    if len(items) < total:
        raise LookupError(f"read {len(items)} of {total} board items")
    return items


def _items(owner: str, number: str) -> list[dict]:
    return all_items(lambda limit: json.loads(_gh("project", "item-list", number, "--owner", owner,
                                                  "--limit", str(limit), "--format", "json")))


def pr_ticket(pr: dict) -> int | None:
    """The ticket an open PR is for: its `Closes #N` line, else its ticket-N-* branch."""
    m = re.search(r"^Closes #(\d+)\s*$", pr.get("body") or "", re.M) or re.match(r"^ticket-(\d+)-", pr.get("headRefName") or "")
    return int(m.group(1)) if m else None


def report(read_board, read_prs, repo: str, limit: int | None = REPORT_LIMIT) -> str:
    """What is waiting for the owner: tickets in the board's Needs Approval column, and tickets
    whose open PR is labelled needs-approval. Each ticket's PRs come from all open PRs, not the
    label, so a PR the merge job hasn't labelled yet still shows. A source that can't be read is
    said plainly, and nothing is claimed from it: "PR: unknown", never "no open PR", and no
    "not on the board" tag. "Nothing waiting" only when both were read and are empty."""
    problems, board, prs = [], None, None
    try:
        board = set(read_board())
    except Exception as e:
        problems.append(f"Couldn't read the board: {e}")
    try:
        prs = list(read_prs())
    except Exception as e:
        problems.append(f"Couldn't read the open PRs: {e}")
    by_ticket: dict[int, list[int]] = {}
    labelled: set[int] = set()
    for p in prs or []:
        t = pr_ticket(p)
        if t is None:
            continue
        by_ticket.setdefault(t, []).append(p["number"])
        if "needs-approval" in {l.get("name") for l in p.get("labels") or []}:
            labelled.add(t)
    waiting = sorted((board or set()) | labelled)
    if not problems and not waiting:
        return "No tickets are waiting in Needs Approval."
    tickets = [{"number": n, "prs": None if prs is None else sorted(by_ticket.get(n, [])),
                "off_board": board is not None and n not in board} for n in waiting]
    return "\n".join(problems + ([render(tickets, repo, limit)] if tickets else ["Nothing found in what could be read."]))


def _board_numbers(repo: str, owner: str, number: str) -> list[int]:
    return [t["number"] for t in needs_approval(_items(owner, number), repo)]


def _open_prs() -> list[dict]:
    # every open PR (no label filter, which goes through GitHub's search); matched to tickets in report()
    return json.loads(_gh("pr", "list", "--state", "open", "--limit", "500",
                          "--json", "number,body,headRefName,labels"))


def current_report(limit: int | None = REPORT_LIMIT) -> str:
    try:
        repo, owner, number = _project()
    except Exception as e:
        repo = _gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
        return report(lambda: (_ for _ in ()).throw(e), _open_prs, repo, limit)
    return report(lambda: _board_numbers(repo, owner, number), _open_prs, repo, limit)


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
