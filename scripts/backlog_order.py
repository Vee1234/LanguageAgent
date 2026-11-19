"""Build order for the backlog: foundations first, and within each category the ticket that
would be most painful to change later.

How tickets are structured, the change-cost rubric and the category order are in
docs/backlog.md. The scores are judgments made when a ticket is written; this file only does
the ordering, so the same backlog always gives the same order.

Usage:
    python3 scripts/backlog_order.py order [--repo OWNER/NAME] [--input response.json] [--json]
    python3 scripts/backlog_order.py score --stores-data y --trust-boundary n \
        --shared-contract y --external n
"""
from __future__ import annotations

import argparse
import heapq
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

BACKLOG_DOC = Path(__file__).resolve().parent.parent / "docs" / "backlog.md"
EPIC_LABEL = "epic"
CATEGORY_PREFIX = "category:"
COST_PREFIX = "change-cost:"


@dataclass
class Issue:
    number: int
    title: str
    state: str  # "OPEN" or "CLOSED"
    labels: list[str]
    parent: int | None
    body: str


@dataclass
class Entry:
    number: int
    title: str
    category: str
    cost: int
    dependants: int        # open tickets that need this one, directly or indirectly
    blocked_by: list[int]  # open tickets this one still needs


@dataclass
class Plan:
    order: list[Entry] = field(default_factory=list)
    triage: list[tuple[int, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cycle: list[int] = field(default_factory=list)  # tickets in, or waiting behind, a cycle
    blocked: list[tuple[int, list[int]]] = field(default_factory=list)  # waiting on unordered open work
    next: int | None = None


# --- change cost ---------------------------------------------------------------

def change_cost(*, stores_data: bool, trust_boundary: bool, shared_contract: bool, external: bool) -> int:
    """The highest level that applies (docs/backlog.md, "Change-cost rubric")."""
    if stores_data:
        return 5
    if trust_boundary:
        return 4
    if shared_contract:
        return 3
    if external:
        return 2
    return 1


# --- parsing -------------------------------------------------------------------

_HEADING = re.compile(r"^#{1,6}\s")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def _section(text: str, name: str) -> list[str]:
    """Lines under the heading `## <name>`, up to the next heading. Fenced code blocks are
    examples, not structure: nothing inside them is read, and a `#` line there isn't a heading."""
    lines, inside, fence = [], False, None
    for line in text.splitlines():
        m = _FENCE.match(line)
        if fence:
            if m and m.group(1) == fence:
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        if _HEADING.match(line):
            inside = re.match(rf"^##\s+{re.escape(name)}\s*$", line, re.IGNORECASE) is not None
            continue
        if inside:
            lines.append(line)
    return lines


def parse_depends_on(body: str) -> list[int]:
    """Ticket numbers listed as `- #N` under `## Depends on`; mentions elsewhere don't count."""
    deps = []
    for line in _section(body or "", "Depends on"):
        m = re.match(r"^\s*[-*]\s*#(\d+)\b", line)
        if m:
            deps.append(int(m.group(1)))
    return deps


def parse_category_order(doc: str) -> list[str]:
    """The numbered list under `## Category order`, e.g. "1. `core` — foundations"."""
    order = []
    for line in _section(doc, "Category order"):
        m = re.match(r"^\s*\d+\.\s+`?([a-z0-9][a-z0-9-]*)`?", line)
        if m:
            order.append(m.group(1))
    return order


def parse_graphql(resp: dict) -> list[Issue]:
    """Issues from one page of the GraphQL response that `fetch_issues` asks for."""
    nodes = resp["data"]["repository"]["issues"]["nodes"]
    for n in nodes:
        if (n["labels"].get("pageInfo") or {}).get("hasNextPage"):
            raise ValueError(f"#{n['number']} has more labels than the query reads; "
                             "its category and change cost can't be trusted")
    return [
        Issue(
            number=n["number"],
            title=n["title"],
            state=n["state"],
            labels=[label["name"] for label in n["labels"]["nodes"]],
            parent=(n.get("parent") or {}).get("number"),
            body=n.get("body") or "",
        )
        for n in nodes
    ]


# --- ordering ------------------------------------------------------------------

def order_backlog(issues: list[Issue], category_order: list[str]) -> Plan:
    plan = Plan()
    by_num = {i.number: i for i in issues}
    rank = {c: r for r, c in enumerate(category_order)}

    children: dict[int, list[int]] = defaultdict(list)
    for i in issues:
        if i.parent in by_num:
            children[i.parent].append(i.number)

    def is_open(n: int) -> bool:
        return by_num[n].state == "OPEN"

    def is_epic(n: int) -> bool:
        return EPIC_LABEL in by_num[n].labels

    def open_children(n: int) -> list[int]:
        return [c for c in children[n] if is_open(c) and not is_epic(c)]

    def category_of(n: int) -> str | None:
        seen, cur = set(), n
        while cur in by_num and cur not in seen:
            seen.add(cur)
            if is_epic(cur):
                for label in by_num[cur].labels:
                    if label.startswith(CATEGORY_PREFIX):
                        return label[len(CATEGORY_PREFIX):]
                return None
            cur = by_num[cur].parent
        return None

    def open_leaves(n: int) -> list[int]:
        """The open work items a reference to #n stands for: its open sub-issues (even if #n
        itself was closed), or else #n while it is open."""
        kids = [c for c in children[n] if is_open(c)]
        if kids:
            return [leaf for c in kids for leaf in open_leaves(c)]
        return [n] if is_open(n) and not is_epic(n) else []

    # Work items: open tickets with no open children. Containers and epics are only groupings.
    work = [i.number for i in issues if is_open(i.number) and not is_epic(i.number) and not open_children(i.number)]

    category: dict[int, str] = {}
    cost: dict[int, int] = {}
    for n in work:
        cat = category_of(n)
        costs = [l[len(COST_PREFIX):] for l in by_num[n].labels if l.startswith(COST_PREFIX)]
        if cat is None:
            plan.triage.append((n, "no category: it is not under an epic with a category:<name> label"))
        elif cat not in rank:
            plan.triage.append((n, f"category '{cat}' is not in the category order in docs/backlog.md"))
        elif len(costs) != 1 or costs[0] not in {"1", "2", "3", "4", "5"}:
            plan.triage.append((n, "needs exactly one change-cost:1..5 label (score it with the rubric)"))
        else:
            category[n], cost[n] = cat, int(costs[0])

    scheduled = set(category)

    # Dependencies, expanded through containers, keeping only what is still open.
    deps: dict[int, list[int]] = {}
    for n in work:
        found: list[int] = []
        for d in parse_depends_on(by_num[n].body):
            if d not in by_num:
                plan.warnings.append(f"#{n} depends on #{d}, which doesn't exist in this repository")
                continue
            # Depending on your own container includes you; that isn't a self-dependency.
            # Listing yourself is, and it leaves the ticket stuck like any other cycle.
            for leaf in [n] if d == n else open_leaves(d):
                if (leaf != n or d == n) and leaf not in found:
                    found.append(leaf)
        deps[n] = sorted(found)

    # Rule 1: a ticket waiting on open work that isn't ordered (triage, or something itself
    # blocked) can't be built yet, so it is listed with its blockers instead of ordered.
    blocked: dict[int, list[int]] = {}
    changed = True
    while changed:
        changed = False
        for n in sorted(scheduled - blocked.keys()):
            stopped = [d for d in deps[n] if d not in scheduled or d in blocked]
            if stopped:
                blocked[n], changed = stopped, True
    plan.blocked = sorted(blocked.items())
    scheduled -= blocked.keys()

    needed_by: dict[int, set[int]] = defaultdict(set)  # direct dependants among scheduled tickets
    for n in scheduled:
        for d in deps[n]:
            if d in scheduled:
                needed_by[d].add(n)

    def all_dependants(n: int) -> set[int]:
        seen: set[int] = set()
        stack = list(needed_by[n])
        while stack:
            d = stack.pop()
            if d not in seen:
                seen.add(d)
                stack.extend(needed_by[d])
        seen.discard(n)
        return seen

    dependants = {n: all_dependants(n) for n in scheduled}

    # A blocker inherits the earliest category of anything waiting on it.
    effective = {n: min([rank[category[n]]] + [rank[category[d]] for d in dependants[n]]) for n in scheduled}
    for n in sorted(scheduled):
        if effective[n] < rank[category[n]]:
            by = min(d for d in dependants[n] if rank[category[d]] == effective[n])
            plan.warnings.append(
                f"#{n} ({category[n]}) is pulled ahead of its category because #{by} "
                f"({category[by]}) depends on it; consider moving it to '{category[by]}'"
            )

    waiting = {n: sum(1 for d in deps[n] if d in scheduled) for n in scheduled}
    ready = [(effective[n], -cost[n], -len(dependants[n]), n) for n in scheduled if waiting[n] == 0]
    heapq.heapify(ready)
    while ready:
        *_, n = heapq.heappop(ready)
        plan.order.append(Entry(n, by_num[n].title, category[n], cost[n], len(dependants[n]), deps[n]))
        for d in sorted(needed_by[n]):
            waiting[d] -= 1
            if waiting[d] == 0:
                heapq.heappush(ready, (effective[d], -cost[d], -len(dependants[d]), d))

    placed = {e.number for e in plan.order}
    plan.cycle = sorted(scheduled - placed)
    plan.next = next((e.number for e in plan.order if not e.blocked_by), None)
    return plan


# --- GitHub --------------------------------------------------------------------

QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $after, states: [OPEN, CLOSED]) {
      nodes {
        number title state body
        labels(first: 100) { nodes { name } pageInfo { hasNextPage } }
        parent { number }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def fetch_issues(repo: str) -> list[Issue]:
    owner, name = repo.split("/", 1)
    issues: list[Issue] = []
    after = None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"]
        if after:
            cmd += ["-F", f"after={after}"]
        resp = json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)
        issues += parse_graphql(resp)
        page = resp["data"]["repository"]["issues"]["pageInfo"]
        if not page["hasNextPage"]:
            return issues
        after = page["endCursor"]


def current_repo() -> str:
    out = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def render(plan: Plan) -> str:
    out = ["## Build order", ""]
    if not plan.order:
        out.append("_Nothing is ready to order._")
    for i, e in enumerate(plan.order, 1):
        mark = "▶ " if e.number == plan.next else ""
        line = f"{i}. {mark}#{e.number} [{e.category}] {e.title} (change cost {e.cost}, {e.dependants} depend on it)"
        if e.blocked_by:
            line += " · waits for " + ", ".join(f"#{d}" for d in e.blocked_by)
        out.append(line)
    if plan.triage:
        out += ["", "## Needs triage (not ordered)", ""]
        out += [f"- #{n}: {why}" for n, why in plan.triage]
    if plan.blocked:
        out += ["", "## Blocked: waiting on tickets that aren't ordered", ""]
        out += [f"- #{n} waits for " + ", ".join(f"#{d}" for d in ds) for n, ds in plan.blocked]
    if plan.cycle:
        out += ["", "## Stuck: in or behind a dependency cycle", ""]
        out.append(", ".join(f"#{n}" for n in plan.cycle))
    if plan.warnings:
        out += ["", "## Warnings", ""]
        out += [f"- {w}" for w in plan.warnings]
    return "\n".join(out)


def _yes(s: str) -> bool:
    if s.lower() in ("y", "yes", "true", "1"):
        return True
    if s.lower() in ("n", "no", "false", "0"):
        return False
    raise argparse.ArgumentTypeError(f"expected y or n, got {s!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="change cost from the rubric answers")
    for flag in ("--stores-data", "--trust-boundary", "--shared-contract", "--external"):
        s.add_argument(flag, type=_yes, required=True)

    o = sub.add_parser("order", help="print the build order")
    o.add_argument("--repo", help="OWNER/NAME (default: this checkout's GitHub repo)")
    o.add_argument("--input", help="a saved GraphQL response instead of calling GitHub")
    o.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "score":
        print(json.dumps({"change_cost": change_cost(
            stores_data=args.stores_data, trust_boundary=args.trust_boundary,
            shared_contract=args.shared_contract, external=args.external)}))
        return 0

    issues = parse_graphql(json.loads(Path(args.input).read_text())) if args.input \
        else fetch_issues(args.repo or current_repo())
    plan = order_backlog(issues, parse_category_order(BACKLOG_DOC.read_text()))
    print(json.dumps(asdict(plan), indent=2) if args.json else render(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
