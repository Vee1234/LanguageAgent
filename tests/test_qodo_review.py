from scripts.qodo_review import is_fresh, parse_summary

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


def test_zero_bugs_means_no_items():
    assert parse_summary(NO_BUGS) == {"count": 0, "items": []}


def test_not_a_qodo_review():
    assert parse_summary("<h3>PR Summary by Qodo</h3> …")["count"] is None


def test_only_a_review_updated_after_the_commit_counts_as_fresh():
    commit = "2026-11-17T10:00:00+00:00"
    assert is_fresh("2026-11-17T10:04:00Z", commit)
    assert not is_fresh("2026-11-17T09:59:00Z", commit)
