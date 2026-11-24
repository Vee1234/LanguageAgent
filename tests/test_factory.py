import pytest

from scripts.factory import gate, should_block

HEAD = "a" * 40


def analysis(passed=True, needs_user=False, head=HEAD, failing=()):
    return {"head": head, "passed": passed, "needs_user": needs_user,
            "items": [{"text": t, "status": "failing"} for t in failing], "problems": []}


def review(fresh=True, findings=()):
    return {"fresh": fresh, "findings": list(findings)}


def f(fp, relevance=3):
    return {"fingerprint": fp, "title": f"finding {fp}", "relevance": relevance, "category": "in-scope"}


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


def test_the_next_ticket_is_backlog_orders_next_unless_one_is_queued_or_stuck():
    assert choose_next(7, {3: ["enhancement"], 7: []}) == 7
    assert choose_next(7, {3: ["ready-for-agent"], 7: []}) is None
    assert choose_next(7, {3: ["agent-stuck"], 7: []}) is None
    assert choose_next(None, {}) is None
