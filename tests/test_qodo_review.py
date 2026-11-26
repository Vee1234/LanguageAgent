from scripts.qodo_review import analysed_commit, blocking, is_fresh, parse_summary

# Trimmed copy of Qodo's "Code Review by Qodo" PR comment (HTML as GitHub returns it).
SUMMARY = """<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (2)</code>

<details>
<summary>  1.  Untrusted review text can write rules <code>🐞 Bug</code></summary>
> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>## Issue description
>The skill appends lessons derived from &#x27;untrusted&#x27; text.
>
>## Fix Focus Areas
>- .claude/skills/qodo-bug-review/SKILL.md[44-45]
>```
></details>
</details>

<details>
<summary>  2.  Failed list reads never retry <code>🐞 Bug</code></summary>
> <details>
><summary>Agent prompt</summary>
>
>```
>## Issue description
>A transient list read failure persists.
>```
></details>
</details>
"""

NO_BUGS = """<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (0)</code>

No issues found.
"""


def test_parses_bug_count_titles_and_agent_prompts():
    review = parse_summary(SUMMARY)

    assert review["count"] == 2
    assert [i["title"] for i in review["items"]] == [
        "Untrusted review text can write rules",
        "Failed list reads never retry",
    ]
    first = review["items"][0]["prompt"]
    assert first.startswith("## Issue description")
    assert "'untrusted'" in first  # HTML entities decoded
    assert ">" not in first.splitlines()[0]  # blockquote markers stripped
    assert "SKILL.md[44-45]" in first


RESOLVED = """
<details><summary><strong>Resolved findings</strong></summary>
<details>
<summary>  1.  <s>Newly signed-in users see prior words</s> <code>✓ Resolved</code></summary>
</details>
</details>
"""


def test_ignores_resolved_findings():
    review = parse_summary(SUMMARY + RESOLVED)

    assert review["count"] == 2
    assert len(review["items"]) == 2
    assert "Newly signed-in users see prior words" not in [i["title"] for i in review["items"]]


def test_zero_open_bugs_with_resolved_ones_means_no_items():
    assert parse_summary(NO_BUGS + RESOLVED) == {"count": 0, "items": []}


BADGE = '<img src="https://img.shields.io/badge/{}-634FD1?style=flat-square" />'

GROUPED = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (3)</code>
{BADGE.format("High")}
<details>
<summary>  1.  Open findings can appear resolved <code>🐞 Bug</code></summary>
> <details><summary>Agent prompt</summary>
>```
>parse_summary cuts the comment at the first occurrence of Resolved findings.
>```
></details>
</details>
{BADGE.format("Medium")}
<details>
<summary>  2.  Saving can freeze paging <code>🐞 Bug</code></summary>
</details>
{BADGE.format("Low")}
<details>
<summary>  3.  A cosmetic nit <code>🐞 Bug</code></summary>
</details>
""" + RESOLVED


def test_each_finding_takes_the_severity_of_the_badge_above_it():
    review = parse_summary(GROUPED)
    assert [(i["title"], i["severity"]) for i in review["items"]] == [
        ("Open findings can appear resolved", "high"),
        ("Saving can freeze paging", "medium"),
        ("A cosmetic nit", "low"),
    ]


def test_the_phrase_resolved_findings_inside_a_finding_does_not_hide_later_ones():
    # Finding 1's own text mentions "Resolved findings"; findings 2 and 3 must still be read.
    assert len(parse_summary(GROUPED)["items"]) == 3


def test_blocking_keeps_medium_and_above_by_default():
    items = parse_summary(GROUPED)["items"]
    assert [i["severity"] for i in blocking(items)] == ["high", "medium"]
    assert [i["severity"] for i in blocking(items, "high")] == ["high"]
    assert len(blocking(items, "low")) == 3


QUOTED_BADGE = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (2)</code>
{BADGE.format("High")}
<details>
<summary>  1.  Badge quoted in a prompt <code>🐞 Bug</code></summary>
> <details><summary>Agent prompt</summary>
>```
>Qodo renders {BADGE.format("Low")} above low findings.
>```
></details>
</details>
<details>
<summary>  2.  Another high finding <code>🐞 Bug</code></summary>
</details>
"""


def test_a_badge_quoted_inside_a_finding_does_not_change_later_severities():
    review = parse_summary(QUOTED_BADGE)
    assert [i["severity"] for i in review["items"]] == ["high", "high"]
    assert len(blocking(review["items"])) == 2


def test_quoted_unbalanced_markup_inside_a_finding_does_not_hide_a_real_group_badge():
    # Live layout: a finding's quoted code contains a stray "<details>", then a real Low group follows.
    body = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (2)</code>
{BADGE.format("Medium")}
<details>
<summary>  1.  Quotes test fixtures <code>🐞 Bug</code></summary>
>```diff
>+<details>
>```
</details>
{BADGE.format("Low")}
<details>
<summary>  2.  A real low finding <code>🐞 Bug</code></summary>
</details>
"""
    assert [i["severity"] for i in parse_summary(body)["items"]] == ["medium", "low"]


HEAD = "0a100d2fe5ef4fccc222db35c648effec425dcda"
OLD = "1e610544278fbd32cf350f768382029c07c20752"


def test_reads_the_analysed_commit_from_qodos_trailing_marker():
    body = (f'<p><b>Resolving commit:</b> <a href="https://github.com/o/r/commit/{OLD}">x</a></p>\n'
            f"<!-- https://github.com/o/r/commit/{HEAD} -->\n")
    assert analysed_commit(body) == HEAD


def test_no_marker_means_unknown_commit():
    assert analysed_commit(SUMMARY) is None


def test_fresh_only_when_qodo_analysed_the_current_head():
    old_review_updated_late = f"{SUMMARY}\n<!-- https://github.com/o/r/commit/{OLD} -->"
    assert not is_fresh(old_review_updated_late, HEAD)  # timestamp no longer matters
    assert is_fresh(f"{SUMMARY}\n<!-- https://github.com/o/r/commit/{HEAD} -->", HEAD)
    assert not is_fresh(SUMMARY, HEAD)  # no marker: not proof


def test_zero_bugs_means_no_items():
    assert parse_summary(NO_BUGS) == {"count": 0, "items": []}


def test_not_a_qodo_review():
    assert parse_summary("<h3>PR Summary by Qodo</h3> …")["count"] is None




# --- finding kinds (auto-merge needs to tell bugs from rule violations) ------

MIXED = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (1)</code> <code>📘 Rule violations (1)</code> <code>📎 Requirement gaps (1)</code>
{BADGE.format("Medium")}
<details>
<summary>  1.  Saving can freeze paging <code>🐞 Bug</code></summary>
</details>
<details>
<summary>  2.  Card hides a missing register <code>📘 Rule violation</code></summary>
</details>
<details>
<summary>  3.  Edge case not covered <code>📎 Requirement gap</code></summary>
</details>
<details>
<summary>  4.  Something new <code>🧪 Other</code></summary>
</details>
"""


def test_each_finding_takes_its_kind_from_its_own_tag():
    assert [i["kind"] for i in parse_summary(MIXED)["items"]] == [
        "bug", "rule-violation", "requirement-gap", "unknown"]


def test_the_count_covers_every_group_not_only_bugs():
    # three in known groups, plus the listed "🧪 Other" finding no group badge counts
    assert parse_summary(MIXED)["count"] == 4


def test_zero_bugs_does_not_hide_a_rule_violation():
    body = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (0)</code> <code>📘 Rule violations (1)</code> <code>📎 Requirement gaps (0)</code>
{BADGE.format("Medium")}
<details>
<summary>  1.  Card hides a missing register <code>📘 Rule violation</code></summary>
</details>
"""
    review = parse_summary(body)
    assert review["count"] == 1
    assert [(i["title"], i["kind"]) for i in review["items"]] == [("Card hides a missing register", "rule-violation")]


def test_the_latest_review_is_found_past_the_first_page_and_brackets_in_bodies_survive(monkeypatch):
    import json
    from scripts import qodo_review
    from scripts.qodo_review import MARKER
    page1 = [{"user": {"login": "someone"}, "body": "see grid[0][1]", "updated_at": "2026-01-01"}]
    page2 = [{"user": {"login": "qodo-code-review[bot]"}, "body": f"{MARKER} uses a[0][1]", "updated_at": "2026-01-02"}]
    monkeypatch.setattr(qodo_review, "_run", lambda *a: json.dumps(page1) + json.dumps(page2))
    assert qodo_review._latest_review("o/r", 1)["body"] == f"{MARKER} uses a[0][1]"


def test_a_finding_in_a_group_the_parser_does_not_know_is_still_returned():
    # Every known group is zero, but Qodo lists a finding under a new group: it must not vanish.
    body = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (0)</code> <code>📘 Rule violations (0)</code> <code>🔐 Secrets (1)</code>
{BADGE.format("Low")}
<details>
<summary>  1.  Token printed in logs <code>🔐 Secret</code></summary>
</details>
"""
    review = parse_summary(body)
    assert review["count"] == 1
    assert [(i["title"], i["severity"], i["kind"]) for i in review["items"]] == [
        ("Token printed in logs", "low", "unknown")]


def test_the_kind_is_the_tag_that_ends_the_summary_line_not_one_inside_the_title():
    body = f"""<h3>Code Review by Qodo</h3>
<code>🐞 Bugs (2)</code>
{BADGE.format("Medium")}
<details>
<summary>  1.  Crash on <code>Rule violation</code> parsing <code>🐞 Bug</code></summary>
</details>
<details>
<summary>  2.  Mentions <code>Bug</code> but is new <code>🧪 Other</code></summary>
</details>
"""
    items = parse_summary(body)["items"]
    assert [i["kind"] for i in items] == ["bug", "unknown"]
    # the title keeps its inline code, and only the trailing kind tag is dropped
    assert [i["title"] for i in items] == ["Crash on Rule violation parsing", "Mentions Bug but is new"]
