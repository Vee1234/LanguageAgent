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
