from scripts.factory import gate, should_block

HEAD = "a" * 40


def analysis(passed=True, needs_user=False, head=HEAD, failing=()):
    return {"head": head, "passed": passed, "needs_user": needs_user,
            "items": [{"text": t, "status": "failing"} for t in failing], "problems": []}


def review(fresh=True, findings=()):
    return {"fresh": fresh, "findings": list(findings)}


def f(fp, relevance=3, severity="medium", category="in-scope"):
    return {"fingerprint": fp, "title": f"finding {fp}", "relevance": relevance, "category": category,
            "severity": severity}


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
    r = gate(HEAD, analysis(), review(findings=[f("x", 1, category="outside-diff")]), {})
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
    r = gate(HEAD, analysis(), review(findings=[f("x", 3, category="outside-diff")]), {}, threshold=4)
    assert r["status"] == "pass"


def test_the_hook_blocks_again_only_after_progress():
    state = {"head": HEAD, "digest": "d1"}
    assert should_block(None, HEAD, "d1")
    assert not should_block(state, HEAD, "d1")
    assert should_block(state, HEAD, "d2")
    assert should_block(state, "b" * 40, "d1")


# --- the stopping rule: everything for 3 rounds, then only high and critical ------

def test_for_the_first_three_rounds_every_finding_is_work():
    r = gate(HEAD, analysis(), review(findings=[f("m"), f("l", severity="low")]), {}, rounds=2)
    assert actions(r) == ["triage", "triage"] and r["left"] == []


def test_after_three_rounds_only_high_and_critical_findings_are_work():
    fs = [f("h", severity="high"), f("c", severity="critical"), f("m"), f("l", severity="low")]
    r = gate(HEAD, analysis(), review(findings=fs), {}, rounds=3)
    assert [a["fingerprint"] for a in r["actions"]] == ["h", "c"] and r["status"] == "work"
    assert [x["fingerprint"] for x in r["left"]] == ["m", "l"]


def test_once_no_high_finding_is_left_the_rest_is_handed_to_the_owner():
    r = gate(HEAD, analysis(), review(findings=[f("m"), f("l", severity="low")]), {}, rounds=4)
    assert r["status"] == "handover" and r["actions"] == [] and len(r["left"]) == 2


def test_an_unreadable_severity_counts_as_high_after_the_limit():
    r = gate(HEAD, analysis(), review(findings=[f("u", severity="unknown")]), {}, rounds=3)
    assert actions(r) == ["triage"]


def test_nothing_open_passes_whatever_the_round():
    assert gate(HEAD, analysis(), review(), {}, rounds=7)["status"] == "pass"


def test_failing_criteria_are_always_work_even_after_the_limit():
    assert actions(gate(HEAD, analysis(failing=["x"]), review(), {}, rounds=5)) == ["fix-criteria"]


def test_a_head_is_checked_only_once_it_is_analysed_and_reviewed():
    assert gate(HEAD, None, review(), {})["checked"] is False
    assert gate(HEAD, analysis(failing=["x"]), review(fresh=False), {})["checked"] is False
    assert gate(HEAD, analysis(failing=["x"]), review(), {})["checked"] is True


# --- rounds: one per checked head with work left, from trusted PR comments ------

from scripts.factory import count_rounds, round_marker  # noqa: E402


def test_rounds_count_distinct_heads_from_the_markers_in_pr_comments():
    comments = [round_marker("a" * 40) + " round 1", "unrelated", round_marker("b" * 40), round_marker("a" * 40),
                "quoted <!-- factory-round head=nonsense -->"]
    assert count_rounds(comments) == 2


def test_only_round_markers_the_factory_or_the_owner_posted_count(monkeypatch):
    import json
    from scripts import factory
    monkeypatch.setattr(factory, "repo_name", lambda: "o/r")
    fake = "\n".join(round_marker(c * 40) for c in "bcd")
    comments = [{"body": fake, "user": {"login": "stranger"}},
                {"body": round_marker("e" * 40), "user": {"login": "github-actions[bot]"}},
                {"body": round_marker("f" * 40), "user": {"login": "o"}},
                {"body": round_marker("0" * 40), "user": None}]
    monkeypatch.setattr(factory, "_gh", lambda *a: json.dumps(comments))
    assert count_rounds(factory.pr_comments(1)) == 2


def test_a_round_is_recorded_once_per_head(monkeypatch):
    from scripts import factory
    posted = []
    monkeypatch.setattr(factory, "pr_comments", lambda n: list(posted))
    monkeypatch.setattr(factory, "_gh", lambda *a: posted.append(a[a.index("--body") + 1]) or "")
    info = {"number": 7, "headRefOid": HEAD}
    assert factory.record_round(info) == 1 and factory.record_round(info) == 1 and len(posted) == 1


def test_earlier_rounds_never_count_the_head_being_checked():
    from scripts.factory import earlier_rounds
    comments = [round_marker("b" * 40), round_marker("c" * 40), round_marker(HEAD)]
    assert earlier_rounds(comments, HEAD) == 2 and earlier_rounds(comments, "d" * 40) == 3


def run_gate(monkeypatch, tmp_path, prior, findings, checked=True):
    import argparse
    import contextlib
    import io
    import json
    from scripts import factory
    posted = []
    info = {"number": 7, "ticket": 4, "headRefOid": HEAD, "headRefName": "ticket-4-x", "changed": []}
    monkeypatch.setattr(factory, "pr_info", lambda pr: info)
    monkeypatch.setattr(factory, "current_review", lambda i: review(fresh=checked, findings=findings))
    monkeypatch.setattr(factory, "load_analysis", lambda h: analysis())
    monkeypatch.setattr(factory, "read_ledger", lambda: [])
    monkeypatch.setattr(factory, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(factory, "pr_comments", lambda n: [round_marker(c * 40) for c in "bcdef"[:prior]] + posted)
    monkeypatch.setattr(factory, "_gh", lambda *a: posted.append(a[a.index("--body") + 1]) or "")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        factory.cmd_gate(argparse.Namespace(pr="7", threshold=2, hook=True))
    return json.loads(out.getvalue()), posted


def test_the_fourth_head_hands_medium_findings_to_the_owner(monkeypatch, tmp_path):
    msg, posted = run_gate(monkeypatch, tmp_path, prior=3, findings=[f("m")])
    assert "handover" in msg["systemMessage"] and "finding m" in msg["systemMessage"] and posted == []


def test_a_checked_head_with_work_is_recorded_as_a_round_and_the_agent_keeps_going(monkeypatch, tmp_path):
    msg, posted = run_gate(monkeypatch, tmp_path, prior=1, findings=[f("m")])
    assert msg["decision"] == "block" and len(posted) == 1
    msg, posted = run_gate(monkeypatch, tmp_path, prior=1, findings=[f("m")], checked=False)
    assert posted == []  # Qodo hasn't reviewed this head: not a round yet


def test_an_in_scope_low_finding_is_work_in_the_first_rounds_whatever_its_relevance():
    low = f("l", relevance=1, severity="low")
    assert actions(gate(HEAD, analysis(), review(findings=[low]), {}, rounds=0)) == ["triage"]
    after = gate(HEAD, analysis(), review(findings=[low]), {}, rounds=3)
    assert after["status"] == "handover" and [x["fingerprint"] for x in after["left"]] == ["l"]


def test_findings_outside_the_diff_or_on_workflow_files_stay_below_the_threshold():
    fs = [f("o", relevance=1, category="outside-diff"), f("w", relevance=0, category="workflow")]
    r = gate(HEAD, analysis(), review(findings=fs), {}, rounds=0)
    assert r["status"] == "pass" and len(r["below_threshold"]) == 2
