"""Draft of the day's Qodo hackathon discussion comment, filled in while the work happens.

Day N's challenge is discussion N+2 in qodo-hackathon/software-factory-hackathon
(https://github.com/orgs/qodo-hackathon/discussions/<N+2>). Its template is the last ```markdown
block in the post, so nothing here is specific to one day. The draft lives in
docs/discussion/day-N.md; every field starts as "Not recorded" (L8) and is filled from evidence
as the work goes. Posting it is the user's call: `post` refuses without --confirm.

Usage:
    python3 scripts/discussion_post.py init 3                 # fetch the template, start the draft
    python3 scripts/discussion_post.py ticket 3 35            # add a section for ticket #35
    python3 scripts/discussion_post.py set 3 "Ticket link" "https://…/issues/35" --ticket 35
    python3 scripts/discussion_post.py set 3 "Qodo findings I investigated, including any missed or irrelevant feedback" - --ticket 35 --append < notes.md
    python3 scripts/discussion_post.py show 3                 # the comment as it would be posted
    python3 scripts/discussion_post.py post 3 --confirm       # only after the user approves the text
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

OWNER, REPO = "qodo-hackathon", "software-factory-hackathon"
DRAFT_DIR = Path(__file__).resolve().parent.parent / "docs" / "discussion"
MISSING = "Not recorded"

_HEADER = re.compile(r"^<!-- discussion-post (\{.*\}) -->$")
_MARKER = re.compile(r"^<!-- ticket #(\d+) -->$")
_HEADING = re.compile(r"^#{1,6}\s")


def discussion_number(day: int) -> int:
    return day + 2


# --- template ------------------------------------------------------------------

def extract_template(body: str) -> str:
    """The last ```markdown block in the post: the template the challenge asks you to copy."""
    blocks, cur = [], None
    for line in body.splitlines():
        if cur is None:
            if re.match(r"^\s{0,3}```markdown\s*$", line):
                cur = []
        elif line.strip() == "```":
            blocks.append(cur)
            cur = None
        else:
            cur.append(line)
    if not blocks:
        raise ValueError("the discussion post has no ```markdown template to copy")
    return "\n".join(blocks[-1]).strip("\n") + "\n"


def _sections(template: str) -> list[tuple[str, list[str]]]:
    secs: list[tuple[str, list[str]]] = []
    for line in template.splitlines():
        if _HEADING.match(line):
            secs.append((line.strip(), []))
        elif line.strip():
            if not secs:
                secs.append(("", []))
            secs[-1][1].append(line.strip())
    return secs


def new_draft(template: str, day: int, url: str) -> str:
    secs = _sections(template)
    repeat = next(((h, labels) for h, labels in secs if re.search(r"\bticket\b", h, re.I)), (None, []))
    meta = {"day": day, "url": url, "repeat": repeat[0], "repeat_labels": repeat[1],
            "labels": [label for _, labels in secs for label in labels]}
    out = [f"<!-- discussion-post {json.dumps(meta, ensure_ascii=False)} -->",
           f"<!-- Draft of the Day {day} comment for {url}. Fill it with scripts/discussion_post.py "
           "as the work happens; post it only after the user approves the text. -->"]
    for heading, labels in secs:
        out.append("")
        if heading:
            out.append(heading)
        out += [f"{label} {MISSING}" for label in labels]
    return "\n".join(out) + "\n"


# --- editing -------------------------------------------------------------------

def _meta(lines: list[str]) -> dict:
    m = _HEADER.match(lines[0]) if lines else None
    if not m:
        raise ValueError("not a discussion-post draft (no header line)")
    return json.loads(m.group(1))


def _labels(lines: list[str]) -> list[str]:
    """The template's field labels, as recorded in the draft's header. Never guessed from the
    lines themselves: a value line can contain a colon too."""
    meta = _meta(lines)
    if "labels" not in meta:
        raise ValueError("this draft predates the label list in its header: start it again with `init --force`")
    return sorted(set(meta["labels"]), key=len, reverse=True)


def _match(key: str, labels: list[str]) -> str | None:
    key = key.strip()
    return next((l for l in labels if l == key or l.rstrip(":") == key), None)


def _is_field(line: str, labels: list[str]) -> bool:
    return any(line == l or line.startswith(l + " ") for l in labels)


def _ticket_block(lines: list[str], number: int) -> tuple[int, int]:
    start = next((i for i, l in enumerate(lines) if l == f"<!-- ticket #{number} -->"), None)
    if start is None:
        raise KeyError(f"no section for ticket #{number}: add it with the `ticket` command first")
    end = next((i for i in range(start + 2, len(lines))
                if _HEADING.match(lines[i]) or _MARKER.match(lines[i])), len(lines))
    return start, end


def add_ticket(draft: str, number: int) -> str:
    lines = draft.rstrip("\n").splitlines()
    meta = _meta(lines)
    marker = f"<!-- ticket #{number} -->"
    if marker in lines or not meta["repeat"]:
        return draft
    heading = meta["repeat"]
    # The first ticket takes over the template's blank section.
    for i, line in enumerate(lines):
        if line == heading and not (i and _MARKER.match(lines[i - 1])):
            lines.insert(i, marker)
            return "\n".join(lines) + "\n"
    last = max(i for i, l in enumerate(lines) if l == heading)
    end = next((i for i in range(last + 1, len(lines)) if _HEADING.match(lines[i])), len(lines))
    block = [marker, heading] + [f"{l} {MISSING}" for l in meta["repeat_labels"]]
    if end == len(lines):
        lines += [""] + block
    else:
        lines[end:end] = block + [""]
    return "\n".join(lines) + "\n"


def set_field(draft: str, key: str, value: str, ticket: int | None = None, append: bool = False) -> str:
    lines = draft.rstrip("\n").splitlines()
    meta = _meta(lines)
    labels = _labels(lines)
    label = _match(key, labels)
    if label is None:
        raise KeyError(f"no field '{key}' in the Day {meta['day']} template")
    if label in meta["repeat_labels"]:
        if ticket is None:
            raise KeyError(f"'{label}' is in the per-ticket section: give the ticket number")
        lo, hi = _ticket_block(lines, ticket)
    else:
        lo, hi = 0, len(lines)
    i = next((j for j in range(lo, hi) if lines[j] == label or lines[j].startswith(label + " ")), None)
    if i is None:
        raise KeyError(f"no field '{key}' in that section")
    j = i + 1
    while j < hi and not (_HEADING.match(lines[j]) or lines[j].startswith("<!--") or _is_field(lines[j], labels)):
        j += 1
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1  # keep the blank line that separates sections
    current = [lines[i][len(label):].strip()] + lines[i + 1:j]
    new = value.strip("\n").split("\n")
    if append and current != [MISSING]:
        new = current + new
    if new[0].lstrip().startswith(("- ", "* ")):
        lines[i:j] = [label] + new  # a list starts on its own line
    else:
        lines[i:j] = [f"{label} {new[0]}".rstrip()] + new[1:]
    return "\n".join(lines) + "\n"


def render_post(draft: str) -> str:
    lines = [l for l in draft.splitlines() if not l.startswith("<!--")]
    return "\n".join(lines).strip("\n") + "\n"


# --- GitHub --------------------------------------------------------------------

def _gh_graphql(query: str, **fields: str) -> dict:
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in fields.items():
        cmd += ["-F" if k == "number" else "-f", f"{k}={v}"]
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)


def fetch_discussion(day: int) -> dict:
    q = """query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) { discussion(number: $number) { id url title body } } }"""
    d = _gh_graphql(q, owner=OWNER, name=REPO, number=str(discussion_number(day)))["data"]["repository"]["discussion"]
    if d is None:
        raise ValueError(f"discussion #{discussion_number(day)} (Day {day}) doesn't exist yet")
    return d


def draft_path(day: int) -> Path:
    return DRAFT_DIR / f"day-{day}.md"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init", help="fetch the day's template and start the draft")
    i.add_argument("day", type=int)
    i.add_argument("--force", action="store_true", help="replace an existing draft")
    t = sub.add_parser("ticket", help="add a per-ticket section")
    t.add_argument("day", type=int)
    t.add_argument("number", type=int)
    s = sub.add_parser("set", help="fill one field (value '-' reads stdin)")
    s.add_argument("day", type=int)
    s.add_argument("label")
    s.add_argument("value")
    s.add_argument("--ticket", type=int)
    s.add_argument("--append", action="store_true")
    for name in ("show", "post"):
        c = sub.add_parser(name)
        c.add_argument("day", type=int)
    sub.choices["post"].add_argument("--confirm", action="store_true",
                                     help="required: the user has approved the exact text")
    args = p.parse_args(argv)
    path = draft_path(args.day)

    if args.cmd == "init":
        if path.exists() and not args.force:
            print(f"{path} already exists; use --force to start again", file=sys.stderr)
            return 1
        d = fetch_discussion(args.day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_draft(extract_template(d["body"]), args.day, d["url"]))
        print(f"Started {path} from {d['url']} ({d['title']})")
        return 0

    if not path.exists():
        print(f"No draft for Day {args.day}: run `init {args.day}` first", file=sys.stderr)
        return 1
    draft = path.read_text()
    if args.cmd == "ticket":
        path.write_text(add_ticket(draft, args.number))
    elif args.cmd == "set":
        value = sys.stdin.read() if args.value == "-" else args.value
        try:
            path.write_text(set_field(draft, args.label, value, ticket=args.ticket, append=args.append))
        except KeyError as e:
            print(e.args[0], file=sys.stderr)
            return 1
    elif args.cmd == "show":
        print(render_post(draft), end="")
    elif args.cmd == "post":
        body = render_post(draft)
        missing = body.count(MISSING)
        if not args.confirm:
            print(body, end="")
            print(f"\nNot posted: show the user this text ({missing} field(s) still '{MISSING}') "
                  "and rerun with --confirm once they approve it.", file=sys.stderr)
            return 1
        disc = fetch_discussion(args.day)
        m = """mutation($id: ID!, $body: String!) {
          addDiscussionComment(input: {discussionId: $id, body: $body}) { comment { url } } }"""
        out = _gh_graphql(m, id=disc["id"], body=body)
        print(out["data"]["addDiscussionComment"]["comment"]["url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
