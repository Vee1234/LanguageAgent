import pytest

from scripts.review_triage import (
    fingerprint,
    focus_files,
    matches,
    patterns,
    standard_globs,
    triage,
    validate_tag,
)

PROMPT = """The issue below was found during a code review.

## Issue description
It mentions
- app/src/fake.ts
in passing.

## Fix Focus Areas
- app/src/cards.ts[76-83]
- app/src/AddWord.tsx[48-60]

## Recommended Fix
- not/a/file.ts
"""


def finding(title="Something breaks", severity="medium", files=("app/src/cards.ts",)):
    areas = "".join(f"- {f}[1-2]\n" for f in files)
    return {"title": title, "severity": severity,
            "prompt": f"## Issue description\nx\n\n## Fix Focus Areas\n{areas}\n## Recommended Fix\ny\n"}


GLOBS = {1: ["app/src/**"], 5: [".claude/**", "scripts/backlog_order.py"]}


# --- parsing -----------------------------------------------------------------

def test_focus_files_come_only_from_their_section_without_line_ranges():
    assert focus_files(PROMPT) == ["app/src/cards.ts", "app/src/AddWord.tsx"]


def test_focus_files_are_empty_without_the_section():
    assert focus_files("## Issue description\n- app/src/x.ts\n") == []


AGENTS = """# AGENTS.md

## Five review standards

1. **More than a translation.**
   - **Applies to:** card generation (`supabase/functions/generate-word/**`, `cardGenerators/**`)
     and the card screens in `app/src/**`.
   - **Rule:** Every card shows `register`.

5. **Product only.**
   - **Applies to:** `.claude/**`, `BugReview/**`, `LessonsLearned.md`,
     `scripts/qodo_review.py`.
   - **Rule:** Don't comment on `docs/other.md`.

## Most opinionated rule
- **Applies to:** `ignored/**`
"""


def test_standard_globs_read_each_applies_to_including_wrapped_lines():
    assert standard_globs(AGENTS) == {
        1: ["supabase/functions/generate-word/**", "cardGenerators/**", "app/src/**"],
        5: [".claude/**", "BugReview/**", "LessonsLearned.md", "scripts/qodo_review.py"],
    }


@pytest.mark.parametrize("path, pattern, expected", [
    ("app/src/x/y.ts", "app/src/**", True),
    (".claude/skills/a/SKILL.md", ".claude/**", True),
    ("LessonsLearned.md", "LessonsLearned.md", True),
    ("app/src/cards.ts", "app/*", False),
    ("scripts/qodo_review.py", "scripts/*.py", True),
    ("scripts/sub/x.py", "scripts/*.py", False),
    ("app/src/a.test.ts", "app/src/**/*.test.ts", True),
])
def test_glob_matching(path, pattern, expected):
    assert matches(path, pattern) is expected


# --- relevance ---------------------------------------------------------------

def test_a_finding_only_on_standard_5_files_is_workflow_with_relevance_0():
    t = triage(finding(severity="high", files=[".claude/hooks/x.sh", "scripts/backlog_order.py"]),
               changed=[".claude/hooks/x.sh", "scripts/backlog_order.py"], globs=GLOBS)
    assert (t["category"], t["relevance"]) == ("workflow", 0)


def test_a_finding_outside_the_pr_diff_has_relevance_1():
    t = triage(finding(severity="critical", files=["app/src/other.ts"]), changed=["app/src/cards.ts"], globs=GLOBS)
    assert (t["category"], t["relevance"]) == ("outside-diff", 1)


def test_in_scope_relevance_is_severity_plus_one_when_a_product_standard_applies():
    on_card = triage(finding(severity="medium", files=["app/src/cards.ts"]), changed=["app/src/cards.ts"], globs=GLOBS)
    assert (on_card["category"], on_card["relevance"], on_card["standards"]) == ("in-scope", 3, [1])
    elsewhere = triage(finding(severity="medium", files=["supabase/x.ts"]), changed=["supabase/x.ts"], globs=GLOBS)
    assert (elsewhere["relevance"], elsewhere["standards"]) == (2, [])


def test_an_unknown_severity_counts_as_high():
    t = triage(finding(severity="unknown", files=["supabase/x.ts"]), changed=["supabase/x.ts"], globs=GLOBS)
    assert t["relevance"] == 3


def test_a_finding_naming_no_files_is_unplaced_and_scored_by_severity():
    t = triage({"title": "x", "severity": "low", "prompt": "no areas"}, changed=["a.ts"], globs=GLOBS)
    assert (t["category"], t["relevance"]) == ("unplaced", 1)


def test_a_finding_on_workflow_and_product_files_is_not_workflow():
    t = triage(finding(severity="low", files=[".claude/x.md", "app/src/y.ts"]),
               changed=[".claude/x.md", "app/src/y.ts"], globs=GLOBS)
    assert (t["category"], t["relevance"]) == ("in-scope", 2)


def test_relevance_is_capped_at_5():
    t = triage(finding(severity="critical", files=["app/src/y.ts"]), changed=["app/src/y.ts"], globs=GLOBS)
    assert t["relevance"] == 5


def test_fingerprint_ignores_line_ranges_case_and_punctuation():
    a = finding(title="PR updates erase completed checks!", files=["app/src/a.ts"])
    b = finding(title="pr updates  erase completed checks", files=["app/src/a.ts"])
    b["prompt"] = b["prompt"].replace("[1-2]", "[40-90]")
    assert fingerprint(a) == fingerprint(b)
    assert fingerprint(a) != fingerprint(finding(title="PR updates erase completed checks", files=["app/src/b.ts"]))


# --- tags --------------------------------------------------------------------

LESSONS = """- **L3** (Day 1, data): Page it. — review · ✅ approved by user 2026-11-17
- **L11** (Day 3, x): Pending one. — review · ⏳ pending approval
- **W1** (Day 1, tooling): Anchor on structure. — review · ✅ approved by user 2026-11-17
"""


def test_a_tag_is_an_approved_lesson_a_standard_or_a_new_slug():
    for tag in ["L3", "W1", "Std2", "new:retry-banner"]:
        validate_tag(tag, LESSONS)
    for tag in ["L99", "L11", "Std9", "new:Bad Slug", "retry"]:
        with pytest.raises(ValueError):
            validate_tag(tag, LESSONS)


# --- what the ledger points to -------------------------------------------------

def entry(ticket, tag="L4", verdict="confirmed", pr=None, fp=None, **kw):
    return {"ticket": ticket, "pr": pr or ticket + 100, "fingerprint": fp or f"fp{ticket}{tag}", "title": "t",
            "category": kw.pop("category", "in-scope"), "verdict": verdict, "tag": tag, **kw}


def test_a_confirmed_tag_in_two_tickets_points_to_a_rule():
    out = patterns([entry(1, "L4"), entry(2, "L4"), entry(3, "new:retry"), entry(4, "new:retry")],
                   pr=0, open_fingerprints=set())
    kinds = {(p["tag"], p["kind"]) for p in out["points"]}
    assert ("L4", "clarify-rule") in kinds
    assert ("new:retry", "propose-rule") in kinds


def test_a_confirmed_tag_in_one_ticket_points_nowhere_yet():
    out = patterns([entry(1, "L4"), entry(1, "L4", fp="other")], pr=0, open_fingerprints=set())
    assert out["points"] == []


def test_a_confirmed_tag_in_three_tickets_points_to_a_skill():
    out = patterns([entry(1), entry(2), entry(3)], pr=0, open_fingerprints=set())
    assert [(p["tag"], p["kind"], p["tickets"]) for p in out["points"]] == [("L4", "skill", [1, 2, 3])]


def test_missing_context_points_to_review_context():
    out = patterns([entry(1, verdict="not-a-bug", reason="missing-context", note="Qodo didn't know X")],
                   pr=0, open_fingerprints=set())
    assert [p["kind"] for p in out["points"]] == ["review-context"]


def test_workflow_findings_point_to_review_context_once():
    es = [entry(1, category="workflow", verdict="workflow", fp="a"), entry(1, category="workflow", verdict="workflow", fp="b")]
    out = patterns(es, pr=0, open_fingerprints=set())
    assert [p["kind"] for p in out["points"]] == ["review-context"]
    assert len(out["noise"]) == 2


def test_feedback_reached_the_fix_only_with_a_test_a_fix_and_the_finding_gone():
    es = [entry(1, pr=9, fp="a", test="tests/t.py::test_a", fix="abc123"),
          entry(1, pr=9, fp="b", test="tests/t.py::test_b"),
          entry(1, pr=9, fp="c", test="tests/t.py::test_c", fix="abc123")]
    out = patterns(es, pr=9, open_fingerprints={"c"})
    assert [e["fingerprint"] for e in out["reached"]] == ["a"]
    assert {e["fingerprint"]: e["why"] for e in out["not_reached"]} == {
        "b": "no fix commit recorded", "c": "still open in the latest review"}


def test_wrong_and_by_design_findings_are_noise():
    es = [entry(1, verdict="not-a-bug", reason="wrong", fp="a"), entry(1, verdict="not-a-bug", reason="by-design", fp="b"),
          entry(1, verdict="out-of-scope", new_ticket=70, fp="c")]
    out = patterns(es, pr=0, open_fingerprints=set())
    assert sorted(e["fingerprint"] for e in out["noise"]) == ["a", "b"]


def test_triage_keeps_the_finding_kind_and_an_absent_kind_is_unknown():
    with_kind = {**finding(files=["app/src/cards.ts"]), "kind": "rule-violation"}
    assert triage(with_kind, changed=["app/src/cards.ts"], globs=GLOBS)["kind"] == "rule-violation"
    assert triage(finding(), changed=["app/src/cards.ts"], globs=GLOBS)["kind"] == "unknown"
