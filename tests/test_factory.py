import pytest

from scripts.factory import gate, should_block

HEAD = "a" * 40


def analysis(passed=True, needs_user=False, head=HEAD, failing=()):
    return {"head": head, "passed": passed, "needs_user": needs_user,
            "items": [{"text": t, "status": "failing"} for t in failing], "problems": []}


def review(fresh=True, findings=()):
    return {"fresh": fresh, "findings": list(findings)}


def f(fp, relevance=3, severity="medium", kind="rule-violation"):
    # not serious by default: a medium rule violation is the agent's to fix
    return {"fingerprint": fp, "title": f"finding {fp}", "relevance": relevance, "category": "in-scope",
            "severity": severity, "kind": kind}


def actions(result):
    return [a["kind"] for a in result["actions"]]


def test_everything_done_passes():
    r = gate(HEAD, analysis(), review(), verdicts={})
    assert r["status"] == "pass" and r["actions"] == []


def test_analysis_must_have_been_run_on_this_head():
    assert actions(gate(HEAD, None, review(), {})) == ["run-analysis"]
    stale = gate(HEAD, analysis(head="b" * 40), review(), {})
    assert actions(stale) == ["run-analysis"] and stale["status"] == "work"


def test_failing_criteria_must_be_fixed():
    r = gate(HEAD, analysis(passed=False, failing=["Given a"]), review(), {})
    assert actions(r) == ["fix-criteria"] and r["status"] == "work"
    assert "Given a" in r["actions"][0]["detail"]


def test_an_untriaged_relevant_finding_must_be_triaged():
    r = gate(HEAD, analysis(), review(findings=[f("x", 2)]), {})
    assert actions(r) == ["triage"] and r["status"] == "work"


def test_a_finding_below_the_threshold_is_listed_but_does_not_block():
    r = gate(HEAD, analysis(), review(findings=[f("x", 1)]), {})
    assert r["status"] == "pass"
    assert [b["fingerprint"] for b in r["below_threshold"]] == ["x"]


def test_a_confirmed_finding_still_open_must_be_fixed():
    r = gate(HEAD, analysis(), review(findings=[f("x")]), {"x": {"verdict": "confirmed"}})
    assert actions(r) == ["fix-finding"]


def test_a_not_a_bug_or_out_of_scope_verdict_clears_the_finding():
    r = gate(HEAD, analysis(), review(findings=[f("x"), f("y")]),
             {"x": {"verdict": "not-a-bug"}, "y": {"verdict": "out-of-scope"}})
    assert r["status"] == "pass"


def test_waiting_for_qodo_when_there_is_nothing_else_to_do():
    assert gate(HEAD, analysis(), review(fresh=False), {})["status"] == "wait"


def test_work_comes_before_waiting():
    r = gate(HEAD, analysis(passed=False, failing=["x"]), review(fresh=False), {})
    assert r["status"] == "work"


def test_old_findings_are_not_used_while_qodo_reviews_the_new_head():
    r = gate(HEAD, analysis(), review(fresh=False, findings=[f("x")]), {})
    assert r["status"] == "wait" and actions(r) == []


def test_a_phone_check_left_for_the_user_ends_the_loop_with_the_user():
    r = gate(HEAD, analysis(passed=False, needs_user=True), review(), {})
    assert r["status"] == "user" and actions(r) == []


def test_the_threshold_can_be_raised():
    r = gate(HEAD, analysis(), review(findings=[f("x", 3)]), {}, threshold=4)
    assert r["status"] == "pass"


def test_the_hook_blocks_again_only_after_progress():
    state = {"head": HEAD, "digest": "d1"}
    assert should_block(None, HEAD, "d1")
    assert not should_block(state, HEAD, "d1")
    assert should_block(state, HEAD, "d2")
    assert should_block(state, "b" * 40, "d1")


# --- auto-merge --------------------------------------------------------------

from scripts.factory import approved_by_owner, count_rounds, merge_decision, round_marker  # noqa: E402

PASS = {"status": "pass", "actions": [], "below_threshold": []}


def sf(fp="x", severity="medium", kind="bug", category="in-scope"):
    return {"fingerprint": fp, "title": f"finding {fp}", "severity": severity, "kind": kind,
            "category": category, "relevance": 3}


def decide(gate_result=PASS, findings=(), approved=True, rounds=1):
    return merge_decision(gate_result, list(findings), approved=approved, rounds=rounds)


def test_a_passed_approved_ticket_with_no_serious_findings_merges():
    assert decide()["decision"] == "merge"
    # a low finding, or a medium rule violation cleared by a verdict, is not serious
    assert decide(findings=[sf(severity="low"), sf("y", kind="rule-violation")])["decision"] == "merge"


def test_a_ticket_the_owner_did_not_approve_waits_for_the_user():
    r = decide(approved=False)
    assert r["decision"] == "user" and "auto-merge-ok" in r["reasons"][0]


@pytest.mark.parametrize("finding", [
    sf(severity="high", kind="rule-violation"),
    sf(severity="critical", kind="requirement-gap"),
    sf(severity="unknown", kind="rule-violation"),
    sf(severity="medium", kind="bug"),
    sf(severity="medium", kind="unknown"),
    sf(severity="high", category="unplaced"),
])
def test_a_serious_finding_the_agent_cleared_itself_needs_the_user(finding):
    # The gate passed, so the agent gave it a not-a-bug or out-of-scope verdict. For a serious
    # finding only a fix (it is gone from the review) or the user may clear it.
    r = decide(findings=[finding])
    assert r["decision"] == "user" and finding["title"] in r["reasons"][0]


def test_serious_findings_outside_the_diff_or_on_workflow_files_do_not_stop_a_merge():
    assert decide(findings=[sf(severity="high", category="outside-diff"),
                            sf("y", severity="critical", category="workflow")])["decision"] == "merge"


@pytest.mark.parametrize("status, decision", [("work", "continue"), ("wait", "continue"), ("user", "user")])
def test_an_unfinished_gate_never_merges(status, decision):
    assert decide(gate_result={**PASS, "status": status}, rounds=1)["decision"] == decision


def test_the_agent_stops_for_help_after_the_retry_limit():
    work = {**PASS, "status": "work"}
    assert decide(gate_result=work, rounds=2)["decision"] == "continue"
    assert decide(gate_result=work, rounds=3)["decision"] == "stuck"
    assert decide(rounds=5)["decision"] == "merge"  # rounds only matter while there is work left


def test_rounds_count_distinct_heads_from_the_markers_in_pr_comments():
    comments = [round_marker("a" * 40) + " round 1", "unrelated", round_marker("b" * 40), round_marker("a" * 40),
                "quoted <!-- factory-round head=nonsense -->"]
    assert count_rounds(comments) == 2


def labeled(label, actor, kind="labeled"):
    return {"event": kind, "label": {"name": label}, "actor": {"login": actor}}


def test_only_the_owner_adding_the_label_approves_auto_merge():
    assert approved_by_owner([labeled("auto-merge-ok", "Vee1234")], "Vee1234")
    assert not approved_by_owner([labeled("auto-merge-ok", "github-actions[bot]")], "Vee1234")
    assert not approved_by_owner([labeled("other", "Vee1234")], "Vee1234")
    assert not approved_by_owner([], "Vee1234")


def test_removing_the_label_withdraws_approval_and_a_bot_cannot_restore_it():
    events = [labeled("auto-merge-ok", "Vee1234"), labeled("auto-merge-ok", "x", "unlabeled")]
    assert not approved_by_owner(events, "Vee1234")
    assert not approved_by_owner(events + [labeled("auto-merge-ok", "claude[bot]")], "Vee1234")
    assert approved_by_owner(events + [labeled("auto-merge-ok", "Vee1234")], "Vee1234")


from scripts.factory import choose_next  # noqa: E402


def entry(n, blocked_by=(), in_review=(), closed_prs=()):
    from scripts.backlog_order import Entry
    return Entry(n, f"T{n}", "core", 3, 0, list(blocked_by), list(in_review), list(closed_prs))


def test_the_next_ticket_is_backlog_orders_next_unless_one_is_queued_or_stuck():
    order = [entry(7), entry(8)]
    assert choose_next(order, {3: ["enhancement"], 7: []}) == (7, [])
    assert choose_next(order, {3: ["ready-for-agent"], 7: []}) == (None, [])
    assert choose_next(order, {3: ["agent-stuck"], 7: []}) == (None, [])
    assert choose_next([], {}) == (None, [])


def test_blocked_or_in_review_tickets_are_skipped():
    assert choose_next([entry(5, blocked_by=[2]), entry(6, in_review=[60]), entry(7)], {}) == (7, [])


def test_a_ticket_whose_pr_was_closed_unmerged_is_held_for_the_owner_and_the_next_one_is_picked():
    # Qodo (PR #71, high): a rejected ticket must not restart without the owner's decision.
    chosen, held = choose_next([entry(37, closed_prs=[70]), entry(38)], {})
    assert chosen == 38 and held == [(37, [70])]


def test_held_tickets_are_reported_even_while_the_queue_is_busy():
    assert choose_next([entry(37, closed_prs=[70]), entry(38)], {9: ["ready-for-agent"]}) == (None, [(37, [70])])


def test_next_moves_a_held_ticket_to_needs_approval_and_explains_once(monkeypatch):
    import argparse
    from scripts import approvals, backlog_order, factory
    calls, moved = [], []
    plan = backlog_order.Plan(order=[entry(37, closed_prs=[70]), entry(38)])
    monkeypatch.setattr(factory, "repo_name", lambda: "o/r")
    monkeypatch.setattr(backlog_order, "fetch_issues", lambda repo: [])
    monkeypatch.setattr(backlog_order, "order_backlog", lambda issues, order: plan)
    monkeypatch.setattr(factory, "_gh", lambda *a: calls.append(a) or "")
    monkeypatch.setattr(approvals, "set_status", lambda t, s: moved.append((t, s)) or len(moved) == 1)
    monkeypatch.setattr(factory, "trusted_ticket", lambda n: True)
    for _ in range(2):  # a second run must not comment again
        factory.cmd_next(argparse.Namespace(dry_run=False))
    assert moved[0] == (37, approvals.NEEDS_APPROVAL)
    comments = [c for c in calls if c[:2] == ("issue", "comment")]
    assert len(comments) == 1 and "#70" in comments[0][-1]
    assert ("issue", "edit", "38", "--add-label", "ready-for-agent") in calls


def run_merge(monkeypatch, approved, findings=()):
    import argparse
    from scripts import approvals, factory
    calls, moved = [], []
    info = {"number": 71, "ticket": 4, "headRefOid": HEAD, "changed": []}
    monkeypatch.setattr(factory, "pr_info", lambda pr: info)
    monkeypatch.setattr(factory, "current_review", lambda i: review(findings=findings))
    monkeypatch.setattr(factory, "load_analysis", lambda h: analysis())
    monkeypatch.setattr(factory, "read_ledger", lambda: [])
    monkeypatch.setattr(factory, "pr_comments", lambda n: [])
    monkeypatch.setattr(factory, "ticket_approved", lambda t: approved)
    monkeypatch.setattr(factory, "_gh", lambda *a: calls.append(a) or "")
    monkeypatch.setattr(approvals, "set_status", lambda t, s: moved.append(t) if s == approvals.NEEDS_APPROVAL else None)
    code = factory.cmd_merge(argparse.Namespace(pr="71", final=True, analysis=None))
    return code, calls, moved


def test_a_ticket_needing_approval_moves_to_the_needs_approval_column(monkeypatch):
    code, calls, moved = run_merge(monkeypatch, approved=False)
    assert code == 1 and moved == [4]
    assert not any(c[:2] == ("pr", "merge") for c in calls)


def test_an_approved_ticket_merges_and_stays_out_of_needs_approval(monkeypatch):
    code, calls, moved = run_merge(monkeypatch, approved=True)
    assert code == 0 and moved == []
    assert ("pr", "merge", "71", "--squash", "--delete-branch", "--match-head-commit", HEAD) in calls



# --- serious findings come back to the user, after the lower ones -------------

def test_the_agent_works_on_lower_findings_first_and_leaves_serious_ones_for_the_user():
    r = gate(HEAD, analysis(), review(findings=[f("low1"), f("bad", severity="high")]), {})
    assert r["status"] == "work"
    assert [a.get("fingerprint") for a in r["actions"]] == ["low1"]
    assert [x["fingerprint"] for x in r["for_user"]] == ["bad"]


def test_once_the_lower_findings_are_resolved_a_serious_one_goes_to_the_user():
    r = gate(HEAD, analysis(), review(findings=[f("low1"), f("bad", severity="medium", kind="bug")]),
             {"low1": {"verdict": "not-a-bug"}})
    assert r["status"] == "user" and r["actions"] == []
    d = merge_decision(r, [], approved=True, rounds=1)
    assert d["decision"] == "user" and "finding bad" in " ".join(d["reasons"])


def test_a_serious_finding_goes_to_the_user_whatever_verdict_the_agent_gave():
    for v in ("confirmed", "not-a-bug", "out-of-scope"):
        r = gate(HEAD, analysis(), review(findings=[f("bad", severity="critical")]), {"bad": {"verdict": v}})
        assert r["status"] == "user", v


def test_serious_findings_never_count_as_rounds_of_agent_work():
    r = gate(HEAD, analysis(), review(findings=[f("bad", severity="high")]), {})
    assert merge_decision(r, [], approved=True, rounds=9)["decision"] == "user"


def test_the_gate_moves_the_ticket_to_in_review_while_the_qodo_cycle_runs(monkeypatch):
    import argparse
    from scripts import approvals, factory
    moved = []
    info = {"number": 71, "ticket": 4, "headRefOid": HEAD, "changed": []}
    monkeypatch.setattr(factory, "pr_info", lambda pr: info)
    monkeypatch.setattr(factory, "current_review", lambda i: review(fresh=False))
    monkeypatch.setattr(factory, "load_analysis", lambda h: analysis())
    monkeypatch.setattr(factory, "read_ledger", lambda: [])
    monkeypatch.setattr(approvals, "set_status", lambda t, s: moved.append((t, s)))
    factory.cmd_gate(argparse.Namespace(pr="71", threshold=2, hook=False))
    assert moved == [(4, "In Review")]


# --- the trusted merge job: factory code changes go to the owner ---------------

from scripts.factory import FACTORY_PATHS, protected_changes  # noqa: E402


def test_protected_changes_are_the_factorys_own_code():
    changed = ["app/src/Card.tsx", "scripts/factory.py", ".github/workflows/factory-run.yml",
               ".claude/hooks/after-push.sh", "AGENTS.md", "tests/test_x.py"]
    assert protected_changes(changed) == ["scripts/factory.py", ".github/workflows/factory-run.yml",
                                          ".claude/hooks/after-push.sh", "AGENTS.md"]
    assert {".github/**", ".claude/**", "scripts/**", "AGENTS.md"} <= set(FACTORY_PATHS)


def test_a_pr_that_changes_factory_code_never_auto_merges():
    d = merge_decision(PASS, [], approved=True, rounds=1, changed=["app/src/a.ts", "scripts/factory.py"])
    assert d["decision"] == "user" and "scripts/factory.py" in d["reasons"][0]
    assert merge_decision(PASS, [], approved=True, rounds=1, changed=["app/src/a.ts"])["decision"] == "merge"


def test_merge_uses_the_analysis_file_handed_over_by_the_verify_job(monkeypatch, tmp_path):
    import argparse, json as _json
    from scripts import approvals, factory
    calls = []
    info = {"number": 71, "ticket": 4, "headRefOid": HEAD, "changed": ["app/src/a.ts"]}
    monkeypatch.setattr(factory, "pr_info", lambda pr: info)
    monkeypatch.setattr(factory, "current_review", lambda i: review())
    monkeypatch.setattr(factory, "load_analysis", lambda h: None)  # nothing in the local state
    monkeypatch.setattr(factory, "read_ledger", lambda: [])
    monkeypatch.setattr(factory, "pr_comments", lambda n: [])
    monkeypatch.setattr(factory, "ticket_approved", lambda t: True)
    monkeypatch.setattr(factory, "_gh", lambda *a: calls.append(a) or "")
    monkeypatch.setattr(approvals, "set_status", lambda t, s: None)
    handed = tmp_path / "analysis.json"
    handed.write_text(_json.dumps(analysis()))
    assert factory.cmd_merge(argparse.Namespace(pr="71", final=True, analysis=str(handed))) == 0
    assert any(c[:2] == ("pr", "merge") for c in calls)


def test_merge_reads_verdicts_from_the_ledger_file_handed_over_from_the_pr(monkeypatch, tmp_path):
    # The merge job runs master's code, but the agent's verdicts are in the PR's copy of the ledger.
    import argparse, json as _json
    from scripts import approvals, factory
    calls = []
    info = {"number": 71, "ticket": 4, "headRefOid": HEAD, "changed": ["app/src/a.ts"]}
    monkeypatch.setattr(factory, "pr_info", lambda pr: info)
    monkeypatch.setattr(factory, "current_review", lambda i: review(findings=[f("x")]))
    monkeypatch.setattr(factory, "read_ledger", lambda: [])  # master's ledger: nothing for this PR
    monkeypatch.setattr(factory, "pr_comments", lambda n: [])
    monkeypatch.setattr(factory, "ticket_approved", lambda t: True)
    monkeypatch.setattr(factory, "_gh", lambda *a: calls.append(a) or "")
    monkeypatch.setattr(approvals, "set_status", lambda t, s: None)
    (tmp_path / "a.json").write_text(_json.dumps(analysis()))
    (tmp_path / "ledger.jsonl").write_text(_json.dumps({"pr": 71, "fingerprint": "x", "verdict": "not-a-bug"}) + "\n")
    code = factory.cmd_merge(argparse.Namespace(pr="71", final=True, analysis=str(tmp_path / "a.json"),
                                                ledger=str(tmp_path / "ledger.jsonl")))
    assert code == 0 and any(c[:2] == ("pr", "merge") for c in calls)



# --- only the owner's own tickets are built ------------------------------------

from scripts.factory import owner_only  # noqa: E402


def test_a_ticket_is_trusted_only_if_the_owner_wrote_it_and_only_the_owner_edited_it():
    assert owner_only({"author": "Vee1234", "editors": []}, "Vee1234")
    assert owner_only({"author": "Vee1234", "editors": ["Vee1234"]}, "Vee1234")
    assert not owner_only({"author": "stranger", "editors": []}, "Vee1234")
    assert not owner_only({"author": "Vee1234", "editors": ["Vee1234", "stranger"]}, "Vee1234")
    assert not owner_only({"author": None, "editors": []}, "Vee1234")  # a deleted account: unknown is untrusted


def test_next_skips_tickets_that_are_not_the_owners_own():
    assert choose_next([entry(7), entry(8)], {}, untrusted={7}) == (8, [])


def test_a_failed_board_move_is_said_in_the_handover_and_fails_the_step(monkeypatch):
    # Qodo (PR #71, medium): the labels must not look like a finished handover when the board move failed.
    import argparse
    from scripts import approvals, factory
    calls = []
    info = {"number": 71, "ticket": 4, "headRefOid": HEAD, "changed": []}
    monkeypatch.setattr(factory, "pr_info", lambda pr: info)
    monkeypatch.setattr(factory, "current_review", lambda i: review())
    monkeypatch.setattr(factory, "load_analysis", lambda h: analysis())
    monkeypatch.setattr(factory, "read_ledger", lambda: [])
    monkeypatch.setattr(factory, "pr_comments", lambda n: [])
    monkeypatch.setattr(factory, "ticket_approved", lambda t: False)
    monkeypatch.setattr(factory, "_gh", lambda *a: calls.append(a) or "")

    def board_down(t, s):
        calls.append(("board", t, s))
        raise TimeoutError("board timed out")
    monkeypatch.setattr(approvals, "set_status", board_down)
    code = factory.cmd_merge(argparse.Namespace(pr="71", final=True, analysis=None))
    assert code == 2
    assert calls.index(("board", 4, approvals.NEEDS_APPROVAL)) < next(i for i, c in enumerate(calls) if c[:2] == ("pr", "edit"))
    comment = next(c for c in calls if c[:2] == ("pr", "comment"))[-1]
    assert "couldn't move" in comment and "board timed out" in comment
