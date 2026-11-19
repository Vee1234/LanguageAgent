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
from scripts import qodo_review, review_triage  # noqa: E402
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
    if result["status"] == "work" and should_block(previous, head, digest):
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
    args = p.parse_args(argv)
    return {"gate": cmd_gate, "verdict": cmd_verdict, "feedback": cmd_feedback}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
