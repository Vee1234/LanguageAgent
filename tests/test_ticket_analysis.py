import pytest

from scripts.ticket_analysis import analyse, parse_items, split_test_id

TICKET = """## Goal
Do it.

## Acceptance criteria
- [ ] [code] Given a, then b.
- [ ] [use] On the phone, see c.
- [ ] [use] The screen shows d.

## Edge or failure case
- [ ] [code] Empty input is refused.

## Out of scope
- Not this.
"""

GOOD_PR = """Closes #42

**Ticket:** [#42 T](u)

## Acceptance criteria
- [x] [code] Given a, then b. — test: tests/test_a.py::test_b, app/src/A.test.tsx > shows b
- [x] [use] On the phone, see c. — user: confirmed on iPhone
- [x] [use] The screen shows d. — seen: d appears after saving (screenshot in PR)

## Edge or failure case
- [x] [code] Empty input is refused. — test: tests/test_a.py::test_empty

## Summary
x
"""


def passing(_id):
    return True


def statuses(result):
    return {i["text"]: i["status"] for i in result["items"]}


def test_items_are_parsed_with_their_kind_and_evidence():
    items = parse_items(GOOD_PR, "Acceptance criteria")
    assert items[0] == {"checked": True, "kind": "code", "text": "Given a, then b.",
                        "tests": ["tests/test_a.py::test_b", "app/src/A.test.tsx > shows b"], "seen": None, "user": None}
    assert items[1]["user"] == "confirmed on iPhone"
    assert items[2]["seen"].startswith("d appears")


def test_ticket_items_have_no_evidence():
    assert parse_items(TICKET, "Edge or failure case") == [
        {"checked": False, "kind": "code", "text": "Empty input is refused.", "tests": [], "seen": None, "user": None}]


@pytest.mark.parametrize("test_id, expected", [
    ("tests/test_a.py::test_b", ("pytest", "tests/test_a.py::test_b", None)),
    ("app/src/A.test.tsx > shows b", ("vitest", "src/A.test.tsx", "shows b")),
])
def test_test_ids_name_their_runner(test_id, expected):
    assert split_test_id(test_id) == expected


def test_an_unknown_test_id_is_refused():
    with pytest.raises(ValueError):
        split_test_id("it works")


def test_a_complete_pr_passes():
    r = analyse(42, TICKET, GOOD_PR, "ticket-42-thing", passing)
    assert r["passed"] and not r["needs_user"] and r["problems"] == []
    assert set(statuses(r).values()) == {"pass", "user-confirmed", "agent-checked"}


def test_the_pr_must_close_this_ticket_from_its_own_branch():
    r = analyse(42, TICKET, GOOD_PR.replace("Closes #42", "Closes #4"), "ticket-41-thing", passing)
    assert not r["passed"]
    assert any("Closes #42" in p for p in r["problems"])
    assert any("ticket-42-" in p for p in r["problems"])


def test_a_criterion_dropped_or_reworded_in_the_pr_fails():
    r = analyse(42, TICKET, GOOD_PR.replace("Given a, then b.", "Given a, then roughly b."), "ticket-42-x", passing)
    assert statuses(r)["Given a, then b."] == "dropped"
    assert any("not in the ticket" in p for p in r["problems"])
    assert not r["passed"]


def test_an_unticked_criterion_is_not_done():
    r = analyse(42, TICKET, GOOD_PR.replace("- [x] [code] Empty", "- [ ] [code] Empty"), "ticket-42-x", passing)
    assert statuses(r)["Empty input is refused."] == "not-done"


def test_a_code_criterion_needs_tests_and_they_must_pass():
    no_test = GOOD_PR.replace(" — test: tests/test_a.py::test_empty", "")
    assert statuses(analyse(42, TICKET, no_test, "ticket-42-x", passing))["Empty input is refused."] == "no-evidence"
    failing = analyse(42, TICKET, GOOD_PR, "ticket-42-x", lambda t: t != "tests/test_a.py::test_empty")
    assert statuses(failing)["Empty input is refused."] == "failing"
    assert not failing["passed"]


def test_a_code_criterion_with_an_unknown_test_id_has_no_evidence():
    pr = GOOD_PR.replace("tests/test_a.py::test_empty", "it works")
    assert statuses(analyse(42, TICKET, pr, "ticket-42-x", passing))["Empty input is refused."] == "no-evidence"


def test_a_phone_check_seen_only_by_the_agent_needs_the_user():
    pr = GOOD_PR.replace("— user: confirmed on iPhone", "— seen: looked fine in the browser")
    r = analyse(42, TICKET, pr, "ticket-42-x", passing)
    assert statuses(r)["On the phone, see c."] == "needs-user"
    assert r["needs_user"] and not r["passed"]


def test_a_use_criterion_without_evidence_has_no_evidence():
    pr = GOOD_PR.replace(" — seen: d appears after saving (screenshot in PR)", "")
    assert statuses(analyse(42, TICKET, pr, "ticket-42-x", passing))["The screen shows d."] == "no-evidence"


def test_a_ticket_without_criteria_cannot_pass():
    r = analyse(42, "## Goal\nx\n", GOOD_PR, "ticket-42-x", passing)
    assert not r["passed"]
    assert any("no acceptance criteria" in p for p in r["problems"])


# --- the trusted judge: PR code runs only in a sealed container -----------------

from scripts import ticket_analysis as ta  # noqa: E402

HEAD_SHA = "c" * 40


def test_a_sandboxed_command_runs_in_a_throwaway_container_with_no_network():
    assert ta.sandboxed(["python3", "-m", "pytest"], None) == ["python3", "-m", "pytest"]
    assert ta.sandboxed(["python3", "-m", "pytest"], "factory-pr") == [
        "docker", "run", "--rm", "--network", "none", "factory-pr", "python3", "-m", "pytest"]


def fake_run(seen, code=0):
    class R:
        returncode = code
    return lambda cmd, **kw: seen.append(cmd) or R()


def test_named_tests_and_the_checks_run_in_the_sandbox(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(ta.subprocess, "run", fake_run(seen))
    assert ta.run_test("tests/test_a.py::test_b", sandbox="factory-pr")
    assert seen[-1][:6] == ["docker", "run", "--rm", "--network", "none", "factory-pr"]
    pr = {"number": 7, "body": GOOD_PR, "headRefName": "ticket-42-x", "headRefOid": HEAD_SHA}
    monkeypatch.setattr(ta, "_gh_json", lambda *a: pr if a[0] == "pr" else {"body": TICKET})
    seen.clear()
    out = tmp_path / "analysis.json"
    ta.main(["--pr", "7", "--sandbox", "factory-pr", "--expect-head", HEAD_SHA, "--out", str(out)])
    assert seen and all(c[:2] == ["docker", "run"] for c in seen)  # nothing from the PR ran on the host
    assert __import__("json").loads(out.read_text())["head"] == HEAD_SHA


def test_the_judge_refuses_a_pr_whose_head_moved(monkeypatch, tmp_path, capsys):
    seen = []
    monkeypatch.setattr(ta.subprocess, "run", fake_run(seen))
    pr = {"number": 7, "body": GOOD_PR, "headRefName": "ticket-42-x", "headRefOid": "d" * 40}
    monkeypatch.setattr(ta, "_gh_json", lambda *a: pr if a[0] == "pr" else {"body": TICKET})
    out = tmp_path / "analysis.json"
    code = ta.main(["--pr", "7", "--sandbox", "factory-pr", "--expect-head", HEAD_SHA, "--out", str(out)])
    assert code == 3 and not out.exists() and seen == []
    assert "moved" in capsys.readouterr().err
