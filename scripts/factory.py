"""The factory gate: is this ticket's PR finished?

A ticket PR is finished when (1) the ticket analysis passed on the PR's head commit,
(2) Qodo has reviewed that same commit, and (3) every finding at or above the relevance
threshold either has a verdict that clears it or has gone from the review. The rules and
the verdict vocabulary are in docs/factory.md.

Usage:
    python3 scripts/factory.py gate [--pr N] [--threshold 2] [--hook]
    python3 scripts/factory.py verdict --fingerprint FP --verdict confirmed --tag L4 --test tests/x.py::test_y [--fix SHA]
    python3 scripts/factory.py verdict --fingerprint FP --verdict not-a-bug --reason missing-context --note "…"
    python3 scripts/factory.py verdict --fingerprint FP --verdict out-of-scope --new-ticket 70
    python3 scripts/factory.py feedback [--pr N]
    python3 scripts/factory.py merge [--pr N] [--final]  # merge if the owner approved and nothing serious was waved through
    python3 scripts/factory.py next [--dry-run]    # label the next ticket ready-for-agent
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import approvals, qodo_review, review_triage  # noqa: E402
from scripts.ticket_analysis import PASSING, state_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs" / "review-ledger.jsonl"
DEFAULT_THRESHOLD = 2
CLEARING = {"not-a-bug", "out-of-scope", "workflow"}


# --- the gate (pure) -------------------------------------------------------------

def gate(head: str, analysis: dict | None, review: dict, verdicts: dict[str, dict],
         threshold: int = DEFAULT_THRESHOLD) -> dict:
    """status: work (the agent has something to do), wait (for Qodo), user (a check only the
    user can do), or pass."""
    actions: list[dict] = []
    needs_user = False
    if analysis is None or analysis.get("head") != head:
        actions.append({"kind": "run-analysis",
                        "detail": f"run the ticket analysis on {head[:7]}: python3 scripts/ticket_analysis.py"})
    else:
        failing = [i for i in analysis["items"] if i["status"] not in PASSING and i["status"] != "needs-user"]
        needs_user = analysis.get("needs_user", False)
        if failing or analysis.get("problems"):
            detail = "; ".join([f"{i['status']}: {i['text']}" for i in failing] + analysis.get("problems", []))
            actions.append({"kind": "fix-criteria", "detail": detail})

    below = []
    if review["fresh"]:
        for f in review["findings"]:
            v = verdicts.get(f["fingerprint"])
            if f["relevance"] < threshold:
                below.append(f)
            elif v is None:
                actions.append({"kind": "triage", "fingerprint": f["fingerprint"],
                                "detail": f"give a verdict on '{f['title']}' (relevance {f['relevance']}, {f['category']})"})
            elif v["verdict"] == "confirmed":
                actions.append({"kind": "fix-finding", "fingerprint": f["fingerprint"],
                                "detail": f"'{f['title']}' is confirmed and still open: fix it test-first and push"})

    if actions:
        status = "work"
    elif not review["fresh"]:
        status = "wait"
    elif needs_user:
        status = "user"
    else:
        status = "pass"
    return {"status": status, "actions": actions, "below_threshold": below}


def should_block(previous: dict | None, head: str, digest: str) -> bool:
    """Block the stop again only if something changed since the last block."""
    return previous is None or previous.get("head") != head or previous.get("digest") != digest


# --- auto-merge (pure) -----------------------------------------------------------

AUTO_MERGE_LABEL = "auto-merge-ok"   # only the repo owner's adding it counts
MAX_ROUNDS = 3                       # gate rounds with work left before the agent stops for help
_ROUND = re.compile(r"^<!-- factory-round head=([0-9a-f]{40}) -->", re.M)


def serious(f: dict) -> bool:
    """A finding only a fix or the user may clear: high or worse, or a medium bug (something not
    working as intended, security included). Unknown severity or kind counts as serious. Findings
    outside the diff or only on workflow files are not this PR's to merge on."""
    if f.get("category") not in {"in-scope", "unplaced"}:
        return False
    sev, kind = f.get("severity"), f.get("kind", "unknown")
    if sev not in review_triage.SEVERITY_BASE or sev in {"high", "critical"}:
        return True
    return sev == "medium" and kind in {"bug", "unknown"}


def merge_decision(gate_result: dict, findings: list[dict], approved: bool, rounds: int,
                   max_rounds: int = MAX_ROUNDS) -> dict:
    """merge, continue (the agent keeps going or waits for Qodo), user (only the user can finish
    it), or stuck (the retry limit was reached with work left)."""
    status = gate_result["status"]
    if status == "work":
        if rounds >= max_rounds:
            return {"decision": "stuck", "reasons": [f"{rounds} rounds and the gate still has work: "
                                                     + "; ".join(a["detail"] for a in gate_result["actions"])]}
        return {"decision": "continue", "reasons": []}
    if status == "wait":
        return {"decision": "continue", "reasons": ["waiting for Qodo's review of the head commit"]}
    if status == "user":
        return {"decision": "user", "reasons": ["a needs-user check in the ticket analysis"]}
    if not approved:
        return {"decision": "user", "reasons": [f"the owner has not labelled this ticket {AUTO_MERGE_LABEL}"]}
    cleared = [f for f in findings if serious(f)]
    if cleared:
        return {"decision": "user", "reasons": [
            f"serious finding cleared by the agent's own verdict, not by a fix: '{f['title']}' "
            f"({f.get('severity')}, {f.get('kind', 'unknown')})" for f in cleared]}
    return {"decision": "merge", "reasons": []}


def round_marker(head: str) -> str:
    return f"<!-- factory-round head={head} -->"


def count_rounds(comments: list[str]) -> int:
    """Rounds are distinct heads the gate found work on, from markers that start a PR comment."""
    return len({m for c in comments for m in _ROUND.findall(c)})


def approved_by_owner(events: list[dict], owner: str, label: str = AUTO_MERGE_LABEL) -> bool:
    """True when the label's latest change was the owner adding it. Removing it withdraws
    approval, and anyone else adding it (a bot, the agent) does not count."""
    approved = False
    for e in events:
        if (e.get("label") or {}).get("name") != label:
            continue
        if e.get("event") == "unlabeled":
            approved = False
        elif e.get("event") == "labeled":
            approved = (e.get("actor") or {}).get("login") == owner
    return approved

# --- GitHub, the ledger and local state ------------------------------------------

def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def latest_verdicts(entries: list[dict], pr: int) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in entries:  # later lines win, so a verdict can be updated (e.g. adding the fix commit)
        if e.get("pr") == pr:
            out[e["fingerprint"]] = e
    return out


def pr_info(pr: str | None) -> dict:
    info = json.loads(_gh("pr", "view", *([pr] if pr else []), "--json",
                          "number,headRefOid,headRefName,body,files"))
    m = re.search(r"^Closes #(\d+)\s*$", info["body"] or "", re.M) or re.match(r"^ticket-(\d+)-", info["headRefName"])
    info["ticket"] = int(m.group(1)) if m else None
    info["changed"] = [f["path"] for f in info.get("files", [])]
    return info


def current_review(info: dict) -> dict:
    repo = _gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    comment = qodo_review._latest_review(repo, info["number"])
    if not comment or not qodo_review.is_fresh(comment["body"], info["headRefOid"]):
        return {"fresh": False, "findings": []}
    parsed = qodo_review.parse_summary(comment["body"])
    if parsed["count"] is None:
        return {"fresh": False, "findings": []}
    globs = review_triage.standard_globs((ROOT / "AGENTS.md").read_text())
    findings = [review_triage.triage(i, info["changed"], globs) for i in parsed["items"]]
    (state_dir() / f"review-{info['headRefOid']}.json").write_text(json.dumps(findings, indent=2))
    return {"fresh": True, "findings": findings}


def load_analysis(head: str) -> dict | None:
    p = state_dir() / f"analysis-{head}.json"
    return json.loads(p.read_text()) if p.exists() else None


def repo_name() -> str:
    return _gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()


def pr_comments(number: int) -> list[str]:
    return json.loads(_gh("api", f"repos/{repo_name()}/issues/{number}/comments", "--paginate",
                          "--jq", "[.[].body]") or "[]")


def record_round(info: dict) -> int:
    """Mark this head as a round with work (once per head) and return the number of rounds."""
    comments = pr_comments(info["number"])
    if not any(c.startswith(round_marker(info["headRefOid"])) for c in comments):
        body = f"{round_marker(info['headRefOid'])}\nFactory round on {info['headRefOid'][:7]}: the gate has work left."
        _gh("pr", "comment", str(info["number"]), "--body", body)
        comments.append(body)
    return count_rounds(comments)


def ticket_approved(ticket: int) -> bool:
    repo = repo_name()
    events = json.loads(_gh("api", f"repos/{repo}/issues/{ticket}/events", "--paginate", "--jq", "[.[]]") or "[]")
    return approved_by_owner(events, repo.split("/")[0])


def render(info: dict, result: dict) -> str:
    out = [f"## Factory gate: PR #{info['number']} (ticket #{info['ticket']}) at {info['headRefOid'][:7]}: "
           f"{result['status'].upper()}", ""]
    out += [f"- {a['kind']}: {a['detail']}" for a in result["actions"]] or ["- Nothing left to do on this PR."]
    if result["below_threshold"]:
        out += ["", "Below the relevance threshold (listed, not blocking):"]
        out += [f"- [{f['relevance']}, {f['category']}] {f['title']} ({f['fingerprint']})" for f in result["below_threshold"]]
    return "\n".join(out)


NEXT = {
    "work": "Do the actions below (ticket-resolver), push, and the cycle continues.",
    "wait": "Qodo hasn't reviewed this commit yet: run `python3 scripts/qodo_review.py --wait-minutes 15 "
            "--min-severity low` in the background and continue when it finishes.",
    "user": "Only the user can finish this: ask them to do the needs-user checks with the exact steps.",
    "pass": "The ticket passed. Do step 7 of ticket-resolver (`python3 scripts/factory.py feedback`) before the next ticket.",
}


# --- commands --------------------------------------------------------------------

def cmd_gate(args) -> int:
    info = pr_info(args.pr)
    head = info["headRefOid"]
    result = gate(head, load_analysis(head), current_review(info), latest_verdicts(read_ledger(), info["number"]),
                  args.threshold)
    report = render(info, result) + "\n\n" + NEXT[result["status"]]
    if not args.hook:
        print(report)
        return 0 if result["status"] == "pass" else 1
    # Stop hook: block only when the agent has work, and only once per unchanged state.
    state_file = state_dir() / f"gate-{info['number']}.json"
    previous = json.loads(state_file.read_text()) if state_file.exists() else None
    digest = hashlib.sha1(json.dumps(result["actions"], sort_keys=True).encode()).hexdigest()
    if result["status"] == "work" and record_round(info) >= MAX_ROUNDS:
        print(json.dumps({"systemMessage": f"Factory gate: PR #{info['number']} reached the retry limit "
                                           f"({MAX_ROUNDS} rounds). Run `python3 scripts/factory.py merge` "
                                           "to label it agent-stuck, then stop and tell the user what is stuck."}))
    elif result["status"] == "work" and should_block(previous, head, digest):
        state_file.write_text(json.dumps({"head": head, "digest": digest}))
        print(json.dumps({"decision": "block", "reason": "Factory gate (ticket-resolver): " + report}))
    elif result["status"] == "work":
        print(json.dumps({"systemMessage": f"Factory gate: no progress on PR #{info['number']} since the last "
                                           "check, so the loop stops here. Tell the user what is stuck."}))
    else:
        print(json.dumps({"systemMessage": f"Factory gate: PR #{info['number']} is {result['status']}. "
                                           + NEXT[result["status"]]}))
    return 0


def cmd_verdict(args) -> int:
    info = pr_info(args.pr)
    findings = {f["fingerprint"]: f for f in current_review(info)["findings"]}
    previous = latest_verdicts(read_ledger(), info["number"]).get(args.fingerprint)
    f = findings.get(args.fingerprint) or previous
    if f is None:
        raise SystemExit(f"no finding {args.fingerprint} in Qodo's review of {info['headRefOid'][:7]}")
    if args.verdict not in review_triage.VERDICTS:
        raise SystemExit(f"verdict must be one of {sorted(review_triage.VERDICTS)}")
    if args.verdict == "not-a-bug" and args.reason not in review_triage.REASONS:
        raise SystemExit(f"not-a-bug needs --reason, one of {sorted(review_triage.REASONS)}, and a --note")
    if args.verdict == "out-of-scope" and not args.new_ticket:
        raise SystemExit("out-of-scope needs --new-ticket: file the ticket first (backlog-order)")
    if args.verdict == "confirmed" and not (args.tag and args.test):
        raise SystemExit("confirmed needs --tag and --test (the regression test that failed first)")
    if args.tag:
        lessons = (ROOT / "LessonsLearned.md").read_text() + (ROOT / "docs" / "WorkflowLessons.md").read_text()
        review_triage.validate_tag(args.tag, lessons)
    entry = {"ticket": info["ticket"], "pr": info["number"], "commit": info["headRefOid"],
             "fingerprint": args.fingerprint, "title": f["title"], "category": f["category"],
             "relevance": f["relevance"], "verdict": args.verdict, "tag": args.tag, "reason": args.reason,
             "note": args.note, "test": args.test, "fix": args.fix, "new_ticket": args.new_ticket}
    entry = {k: v for k, v in entry.items() if v is not None}
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"recorded {args.verdict} for {args.fingerprint} ({f['title']})")
    return 0


def cmd_feedback(args) -> int:
    info = pr_info(args.pr)
    review = current_review(info)
    open_fps = {f["fingerprint"] for f in review["findings"]}
    out = review_triage.patterns(read_ledger(), info["number"], open_fps)

    # Requirements the review missed: criteria that failed analysis at a commit Qodo reviewed
    # without raising anything in scope.
    missed = []
    for a_file in sorted(state_dir().glob("analysis-*.json")):
        a = json.loads(a_file.read_text())
        r_file = state_dir() / f"review-{a.get('head')}.json"
        if a.get("pr") != info["number"] or not r_file.exists():
            continue
        in_scope = [f for f in json.loads(r_file.read_text()) if f["category"] == "in-scope"]
        for i in a["items"]:
            if i["status"] not in PASSING and i["status"] != "needs-user" and not in_scope:
                missed.append(f"{i['text']} ({i['status']} at {a['head'][:7]}; Qodo raised nothing in scope)")

    lines = [f"## Feedback for PR #{info['number']} (ticket #{info['ticket']})", "", "**Where the findings point:**"]
    lines += [f"- {p['kind']} ({p['tag']}, tickets {p['tickets']}): {p['why']}" for p in out["points"]] or ["- Nothing yet."]
    lines += ["", "**Feedback that reached the fix:**"]
    lines += [f"- {e['title']}: test {e['test']}, fix {e['fix'][:7]}" for e in out["reached"]] or ["- None recorded."]
    lines += ["", "**Feedback that did not reach the fix:**"]
    lines += [f"- {e['title']}: {e['why']}" for e in out["not_reached"]] or ["- None."]
    lines += ["", "**Missed by the review:**"] + ([f"- {m}" for m in missed] or ["- None found."])
    lines += ["", "**Irrelevant (noise):**"]
    lines += [f"- {e['title']} ({e.get('reason') or e['category']})" for e in out["noise"]] or ["- None."]
    print("\n".join(lines))
    return 0


def cmd_merge(args) -> int:
    """Merge the PR if the gate passed, the owner approved the ticket and no serious finding was
    cleared by the agent's own verdict. Otherwise hand it to the user or mark it stuck."""
    info = pr_info(args.pr)
    head, n = info["headRefOid"], str(info["number"])
    review = current_review(info)
    result = gate(head, load_analysis(head), review, latest_verdicts(read_ledger(), info["number"]))
    rounds = record_round(info) if result["status"] == "work" else count_rounds(pr_comments(info["number"]))
    approved = bool(info["ticket"]) and ticket_approved(info["ticket"])
    d = merge_decision(result, review["findings"], approved, rounds)
    if args.final and d["decision"] == "continue":
        # The run is over, so nothing will continue it: hand it to the user rather than leave it hanging.
        d = {"decision": "stuck", "reasons": ["the run ended before the gate finished: "
                                              + ("; ".join(d["reasons"]) or result["status"])]}
    print(render(info, result) + f"\n\nAuto-merge: {d['decision'].upper()}" + "".join(f"\n- {r}" for r in d["reasons"]))
    labels = {"user": "needs-approval", "stuck": "agent-stuck"}
    if d["decision"] == "merge":
        _gh("pr", "merge", n, "--squash", "--delete-branch", "--match-head-commit", head)
        return 0
    if d["decision"] in labels:
        _gh("pr", "edit", n, "--add-label", labels[d["decision"]])
        if info["ticket"]:
            _gh("issue", "edit", str(info["ticket"]), "--remove-label", "ready-for-agent", "--add-label", labels[d["decision"]])
        _gh("pr", "comment", n, "--body", f"Factory: **{labels[d['decision']]}** at {head[:7]}\n\n"
            + "\n".join(f"- {r}" for r in d["reasons"]))
        if d["decision"] == "user" and info["ticket"]:
            approvals.set_needs_approval(info["ticket"])  # the board's Needs Approval column
    return 1


READY_LABEL = "ready-for-agent"
HOLD_LABELS = {READY_LABEL, "agent-stuck"}  # one ticket at a time, and a stuck one waits for the user


def choose_next(plan_next: int | None, open_labels: dict[int, list[str]]) -> int | None:
    """The ticket to label next: none while a ticket is queued or stuck, else backlog order's next."""
    if any(HOLD_LABELS & set(ls) for ls in open_labels.values()):
        return None
    return plan_next


def cmd_next(args) -> int:
    from scripts import backlog_order
    repo = repo_name()
    issues = backlog_order.fetch_issues(repo)
    plan = backlog_order.order_backlog(issues, backlog_order.parse_category_order(backlog_order.BACKLOG_DOC.read_text()))
    chosen = choose_next(plan.next, {i.number: i.labels for i in issues if i.state == "OPEN"})
    if chosen is None:
        print("Nothing to label: a ticket is already ready-for-agent or agent-stuck, or nothing is unblocked.")
        return 0
    print(f"Next: #{chosen}")
    if not args.dry_run:
        _gh("issue", "edit", str(chosen), "--add-label", READY_LABEL)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--pr")
    g.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    g.add_argument("--hook", action="store_true", help="print a Stop-hook decision instead of a report")
    v = sub.add_parser("verdict")
    v.add_argument("--pr")
    v.add_argument("--fingerprint", required=True)
    v.add_argument("--verdict", required=True)
    for opt in ("--tag", "--reason", "--note", "--test", "--fix"):
        v.add_argument(opt)
    v.add_argument("--new-ticket", type=int)
    fb = sub.add_parser("feedback")
    fb.add_argument("--pr")
    mg = sub.add_parser("merge")
    mg.add_argument("--pr")
    mg.add_argument("--final", action="store_true", help="the agent's run is over: unfinished means stuck")
    nx = sub.add_parser("next")
    nx.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    return {"gate": cmd_gate, "verdict": cmd_verdict, "feedback": cmd_feedback,
            "merge": cmd_merge, "next": cmd_next}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
