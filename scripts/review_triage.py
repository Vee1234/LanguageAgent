"""Deterministic triage of Qodo findings, and what the review ledger points to.

Relevance (0-5) comes only from fixed structure: the files in a finding's "## Fix Focus Areas"
section (W1), the review standards' Applies to paths in AGENTS.md, the PR's changed files and
Qodo's severity. Verdicts on what's left are judgments, but they come from a closed list, and
tags must name an approved lesson, a review standard or a new slug. The rules are in
docs/factory.md.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

SEVERITY_BASE = {"low": 1, "medium": 2, "high": 3, "critical": 4}
UNKNOWN_SEVERITY = 3  # a severity we can't read counts as high: missing looks missing, never low
WORKFLOW_STANDARD = 5
VERDICTS = {"confirmed", "not-a-bug", "out-of-scope", "workflow"}
REASONS = {"missing-context", "by-design", "wrong"}


# --- parsing ---------------------------------------------------------------------

def focus_files(prompt: str) -> list[str]:
    """The paths listed under Qodo's `## Fix Focus Areas` heading, without their line ranges."""
    files, inside = [], False
    for line in (prompt or "").splitlines():
        if re.match(r"^#{1,6}\s", line):
            inside = re.match(r"^##\s+Fix Focus Areas\s*$", line) is not None
            continue
        m = re.match(r"^\s*[-*]\s+`?([^\s`\[]+)`?(?:\[[^\]]*\])?\s*$", line) if inside else None
        if m and m.group(1) not in files:
            files.append(m.group(1))
    return files


def standard_globs(agents_md: str) -> dict[int, list[str]]:
    """{standard number: the backticked paths in its **Applies to:** text}, from the
    `## Five review standards` section of AGENTS.md. Applies to text can wrap over lines."""
    globs: dict[int, list[str]] = {}
    inside, current, collecting = False, None, False
    for line in agents_md.splitlines():
        if re.match(r"^#{1,6}\s", line):
            inside = re.match(r"^##\s+Five review standards\s*$", line) is not None
            current, collecting = None, False
            continue
        if not inside:
            continue
        item = re.match(r"^(\d+)\.\s+\*\*", line)
        if item:
            current, collecting = int(item.group(1)), False
            continue
        if current is None:
            continue
        if "**Applies to:**" in line:
            collecting = True
            line = line.split("**Applies to:**", 1)[1]
        elif re.match(r"^\s*-\s+\*\*", line):
            collecting = False
        if collecting:
            globs.setdefault(current, []).extend(re.findall(r"`([^`]+)`", line))
    return globs


def matches(path: str, pattern: str) -> bool:
    """Glob match where `*` stays within one folder and `**` crosses folders."""
    rx = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx, i = rx + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            rx, i = rx + ".*", i + 2
        elif pattern[i] == "*":
            rx, i = rx + "[^/]*", i + 1
        elif pattern[i] == "?":
            rx, i = rx + "[^/]", i + 1
        else:
            rx, i = rx + re.escape(pattern[i]), i + 1
    return re.fullmatch(rx, path) is not None


# --- triage ----------------------------------------------------------------------

def fingerprint(finding: dict) -> str:
    """Stable across review rounds: the title's words and the files, not line ranges."""
    words = " ".join(re.findall(r"[a-z0-9]+", finding["title"].lower()))
    key = words + "|" + ",".join(sorted(focus_files(finding.get("prompt", ""))))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def triage(finding: dict, changed: list[str], globs: dict[int, list[str]]) -> dict:
    files = focus_files(finding.get("prompt", ""))
    base = SEVERITY_BASE.get(finding.get("severity", ""), UNKNOWN_SEVERITY)
    workflow = globs.get(WORKFLOW_STANDARD, [])
    product = {n: g for n, g in globs.items() if n != WORKFLOW_STANDARD}
    standards = sorted(n for n, gs in product.items() if any(matches(f, g) for f in files for g in gs))

    if not files:
        category, relevance = "unplaced", base
    elif all(any(matches(f, g) for g in workflow) for f in files):
        category, relevance = "workflow", 0
    elif not any(f in changed for f in files):
        category, relevance = "outside-diff", 1
    else:
        category, relevance = "in-scope", min(5, base + (1 if standards else 0))
    return {"fingerprint": fingerprint(finding), "title": finding["title"], "severity": finding.get("severity"),
            "kind": finding.get("kind", "unknown"), "files": files, "category": category, "relevance": relevance, "standards": standards}


# --- tags and verdicts -----------------------------------------------------------

def approved_ids(lessons_text: str) -> set[str]:
    ids = set()
    for line in lessons_text.splitlines():
        m = re.match(r"^\s*-\s+\*\*([LW]\d+)\*\*", line)
        if m and "✅ approved by user" in line:
            ids.add(m.group(1))
    return ids


def validate_tag(tag: str, lessons_text: str) -> None:
    if tag in approved_ids(lessons_text):
        return
    if re.fullmatch(r"Std[1-5]", tag) or re.fullmatch(r"new:[a-z0-9]+(?:-[a-z0-9]+)*", tag):
        return
    raise ValueError(f"tag {tag!r} must be an approved lesson (L#/W#), a review standard (Std1-Std5) "
                     "or new:<lowercase-slug>")


# --- what the ledger points to ---------------------------------------------------

def patterns(entries: list[dict], pr: int, open_fingerprints: set[str]) -> dict:
    """Where the recorded findings point, by fixed counting rules (docs/factory.md)."""
    points: list[dict] = []
    tickets_by_tag: dict[str, set[int]] = defaultdict(set)
    for e in entries:
        if e.get("verdict") == "confirmed" and e.get("tag"):
            tickets_by_tag[e["tag"]].add(e["ticket"])
    for tag, tickets in sorted(tickets_by_tag.items()):
        ts = sorted(tickets)
        if len(ts) >= 3:
            points.append({"kind": "skill", "tag": tag, "tickets": ts,
                           "why": f"the same fix was needed in {len(ts)} tickets: make it a skill or a checklist step"})
        elif len(ts) == 2:
            kind = "propose-rule" if tag.startswith("new:") else "clarify-rule"
            why = ("not covered by any rule, and it happened twice" if kind == "propose-rule"
                   else f"{tag} already covers it and it was still broken twice: clarify it or add a check")
            points.append({"kind": kind, "tag": tag, "tickets": ts, "why": why})

    for e in entries:
        if e.get("verdict") == "not-a-bug" and e.get("reason") == "missing-context":
            points.append({"kind": "review-context", "tag": e.get("tag"), "tickets": [e["ticket"]],
                           "why": f"Qodo lacked context on '{e['title']}': {e.get('note', 'say what it needed')}"})
    workflow_tickets = sorted({e["ticket"] for e in entries if e.get("category") == "workflow"})
    if workflow_tickets:
        points.append({"kind": "review-context", "tag": "Std5", "tickets": workflow_tickets,
                       "why": "Qodo reviewed files standard 5 excludes: check the standards it uses are on master"})

    reached, not_reached = [], []
    for e in entries:
        if e.get("pr") != pr or e.get("verdict") != "confirmed":
            continue
        if not e.get("test"):
            not_reached.append({**e, "why": "no regression test recorded"})
        elif not e.get("fix"):
            not_reached.append({**e, "why": "no fix commit recorded"})
        elif e["fingerprint"] in open_fingerprints:
            not_reached.append({**e, "why": "still open in the latest review"})
        else:
            reached.append(e)

    noise = [e for e in entries if e.get("category") == "workflow"
             or (e.get("verdict") == "not-a-bug" and e.get("reason") in {"wrong", "by-design"})]
    return {"points": points, "reached": reached, "not_reached": not_reached, "noise": noise}
