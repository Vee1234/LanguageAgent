"""Ticket analysis: does a PR deliver what its ticket asked for?

Compares the PR's acceptance criteria and edge case with the ticket's, runs the tests each
`[code]` criterion names, and checks the evidence recorded for each `[use]` criterion. The
result is tied to the PR's head commit (W2) and saved for the factory gate.

PR criterion lines carry their evidence after an em dash:
    - [x] [code] Given a, then b. — test: tests/test_a.py::test_b, app/src/A.test.tsx > shows b
    - [x] [use] The screen shows d. — seen: d appears after saving (screenshot below)
    - [x] [use] On the phone, see c. — user: confirmed on iPhone

Usage:
    python3 scripts/ticket_analysis.py [--pr N] [--no-verify] [--json]
    python3 scripts/ticket_analysis.py --pr N --sandbox IMAGE --expect-head SHA --out PATH   # CI judge
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = ("Acceptance criteria", "Edge or failure case")
PASSING = {"pass", "agent-checked", "user-confirmed"}
VERIFY = [["python3", "-m", "pytest", "-q"], ["npm", "--prefix", "app", "test", "--silent"],
          ["npm", "--prefix", "app", "run", "build", "--silent"]]

_ITEM = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(?:\[(code|use)\]\s*)?(.+?)\s*$")


def _section(text: str, name: str) -> list[str]:
    lines, inside, fence = [], False, False
    for line in text.splitlines():
        if re.match(r"^\s{0,3}(```|~~~)", line):
            fence = not fence
            continue
        if fence:
            continue
        if re.match(r"^#{1,6}\s", line):
            inside = re.match(rf"^##\s+{re.escape(name)}\s*$", line, re.IGNORECASE) is not None
            continue
        if inside:
            lines.append(line)
    return lines


def _norm(text: str) -> str:
    return " ".join(text.split())


def parse_items(body: str, section: str) -> list[dict]:
    items = []
    for line in _section(body or "", section):
        m = _ITEM.match(line)
        if not m:
            continue
        text, *evidence = m.group(3).split(" — ")
        item = {"checked": m.group(1) in "xX", "kind": m.group(2), "text": _norm(text),
                "tests": [], "seen": None, "user": None}
        for part in evidence:
            key, _, value = part.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "test":
                item["tests"] += [t.strip() for t in value.split(",") if t.strip()]
            elif key in ("seen", "user") and value:
                item[key] = value
        items.append(item)
    return items


def split_test_id(test_id: str) -> tuple[str, str, str | None]:
    """("pytest", node id, None) or ("vitest", file relative to app/, test name)."""
    if re.fullmatch(r"tests/\S+\.py::\S+", test_id):
        return ("pytest", test_id, None)
    m = re.fullmatch(r"app/(\S+\.test\.tsx?)\s+>\s+(.+)", test_id)
    if m:
        return ("vitest", m.group(1), m.group(2).strip())
    raise ValueError(f"not a test id: {test_id!r} (use tests/x.py::test_name or app/src/X.test.tsx > test name)")


def _status(item: dict | None, run_test: Callable[[str], bool]) -> str:
    if item is None:
        return "dropped"
    if not item["checked"]:
        return "not-done"
    if item["kind"] == "code":
        if not item["tests"]:
            return "no-evidence"
        try:
            for t in item["tests"]:
                split_test_id(t)
        except ValueError:
            return "no-evidence"
        return "pass" if all(run_test(t) for t in item["tests"]) else "failing"
    if item["kind"] == "use":
        if item["user"]:
            return "user-confirmed"
        if not item["seen"]:
            return "no-evidence"
        return "needs-user" if "phone" in item["text"].lower() else "agent-checked"
    return "no-kind"


def analyse(number: int, ticket_body: str, pr_body: str, branch: str, run_test: Callable[[str], bool]) -> dict:
    problems: list[str] = []
    closes = re.search(r"^Closes #(\d+)\s*$", pr_body or "", re.M)
    if not closes or int(closes.group(1)) != number:
        problems.append(f"the PR description must say Closes #{number}")
    on_branch = re.match(r"^ticket-(\d+)-", branch or "")
    if not on_branch or int(on_branch.group(1)) != number:
        problems.append(f"the branch must be named ticket-{number}-<short-name>")

    wanted = [i for s in SECTIONS for i in parse_items(ticket_body, s)]
    if not wanted:
        problems.append(f"ticket #{number} has no acceptance criteria: split or rewrite it before building")
    delivered = {i["text"]: i for s in SECTIONS for i in parse_items(pr_body, s)}
    texts = {w["text"] for w in wanted}
    for text in delivered:
        if text not in texts:
            problems.append(f"PR criterion not in the ticket: {text!r}")

    items = [{"text": w["text"], "kind": w["kind"], "status": _status(delivered.get(w["text"]), run_test)}
             for w in wanted]
    needs_user = any(i["status"] == "needs-user" for i in items)
    passed = not problems and bool(items) and all(i["status"] in PASSING for i in items)
    return {"ticket": number, "passed": passed, "needs_user": needs_user, "items": items, "problems": problems}


# --- running it for real -------------------------------------------------------

def sandboxed(cmd: list[str], sandbox: str | None) -> list[str]:
    """In CI the PR's code runs only inside a throwaway container built from it (sandbox is the
    image): no network, no token, no access to this judge's files. Only the exit code comes back.
    The command is an argument list, never a shell string."""
    return cmd if sandbox is None else ["docker", "run", "--rm", "--network", "none", sandbox, *cmd]


def run_test(test_id: str, sandbox: str | None = None) -> bool:
    runner, target, name = split_test_id(test_id)
    if runner == "pytest":
        cmd = ["python3", "-m", "pytest", "-q", target]
    else:
        cmd = ["npm", "--prefix", "app", "exec", "--", "vitest", "run", target, "-t", re.escape(name)]
    return subprocess.run(sandboxed(cmd, sandbox), cwd=ROOT, capture_output=True).returncode == 0


def state_dir() -> Path:
    git_dir = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.strip()
    d = (ROOT / git_dir / "factory").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gh_json(*args: str) -> dict:
    return json.loads(subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout)


def render(r: dict) -> str:
    out = [f"## Ticket analysis: #{r['ticket']} at {r['head'][:7]}: {'PASS' if r['passed'] else 'NOT DONE'}", ""]
    out += [f"- {i['status']}: [{i['kind']}] {i['text']}" for i in r["items"]]
    if r["problems"]:
        out += ["", "Problems:"] + [f"- {p}" for p in r["problems"]]
    if r["needs_user"]:
        out += ["", "Waiting for the user to check the phone criteria marked needs-user."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check a PR against its ticket")
    p.add_argument("--pr", help="PR number or branch (default: the current branch's PR)")
    p.add_argument("--no-verify", action="store_true", help="skip the three verification commands")
    p.add_argument("--json", action="store_true")
    p.add_argument("--sandbox", metavar="IMAGE", help="run the PR's tests and checks in this Docker image (CI)")
    p.add_argument("--expect-head", metavar="SHA", help="refuse unless the PR's head is this commit (CI)")
    p.add_argument("--out", metavar="PATH", help="write the result here instead of the git state dir")
    args = p.parse_args(argv)

    pr = _gh_json("pr", "view", *([args.pr] if args.pr else []), "--json", "number,body,headRefName,headRefOid")
    if args.expect_head and pr["headRefOid"] != args.expect_head:
        print(f"The PR's head moved to {pr['headRefOid'][:7]}; this run checked out {args.expect_head[:7]}. "
              "Nothing was analysed: the next run checks the new head.", file=sys.stderr)
        return 3
    closes = re.search(r"^Closes #(\d+)\s*$", pr["body"] or "", re.M)
    on_branch = re.match(r"^ticket-(\d+)-", pr["headRefName"])
    if not (closes or on_branch):
        print("This PR names no ticket: no 'Closes #N' line and not a ticket-N-* branch.", file=sys.stderr)
        return 2
    number = int((closes or on_branch).group(1))
    ticket = _gh_json("issue", "view", str(number), "--json", "body")

    r = analyse(number, ticket["body"], pr["body"], pr["headRefName"], lambda t: run_test(t, args.sandbox))
    if not args.no_verify:
        for cmd in VERIFY:
            if subprocess.run(sandboxed(cmd, args.sandbox), cwd=ROOT, capture_output=True).returncode:
                r["problems"].append(f"verification failed: {' '.join(cmd)}")
                r["passed"] = False
    r["head"], r["pr"] = pr["headRefOid"], pr["number"]
    out = Path(args.out) if args.out else state_dir() / f"analysis-{r['head']}.json"
    out.write_text(json.dumps(r, indent=2))
    print(json.dumps(r, indent=2) if args.json else render(r))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
