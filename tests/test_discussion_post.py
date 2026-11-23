import pytest

from scripts.discussion_post import (
    add_ticket,
    discussion_number,
    extract_template,
    new_draft,
    render_post,
    set_field,
)

BODY = """# Day 3: Connect your factory

Some intro with an example:

```sh
gh issue list
```

## Show your factory at work

Copy this template into a comment below. Repeat the ticket section for each ticket.

```markdown
## My ticketing connection
Ticketing system:
Connection used (MCP or CLI):

## Ticket → branch → PR
Ticket link:
Branch and PR link:

## What I learned
Did the factory deliver what the tickets asked for?
```
"""

URL = "https://github.com/orgs/qodo-hackathon/discussions/5"


def draft():
    return new_draft(extract_template(BODY), day=3, url=URL)


def test_day_n_is_discussion_n_plus_2():
    assert discussion_number(3) == 5
    assert discussion_number(1) == 3


def test_the_template_is_the_last_markdown_fence_not_other_code():
    t = extract_template(BODY)
    assert t.splitlines()[0] == "## My ticketing connection"
    assert "gh issue list" not in t
    assert t.rstrip().endswith("Did the factory deliver what the tickets asked for?")


def test_a_post_without_a_template_is_refused():
    with pytest.raises(ValueError, match="template"):
        extract_template("# Day 9\nNo template here.\n```sh\nls\n```\n")


def test_a_new_draft_shows_every_field_as_not_recorded():
    d = draft()
    assert "Ticketing system: Not recorded" in d
    assert "Did the factory deliver what the tickets asked for? Not recorded" in d
    assert URL in d


def test_setting_a_field_replaces_not_recorded():
    d = set_field(draft(), "Ticketing system", "GitHub Issues")
    assert "Ticketing system: GitHub Issues" in d
    assert "Ticketing system: Not recorded" not in d


def test_a_question_label_keeps_its_question_mark():
    d = set_field(draft(), "Did the factory deliver what the tickets asked for?", "Yes, #35.")
    assert "Did the factory deliver what the tickets asked for? Yes, #35." in d


def test_a_value_can_span_lines_and_be_replaced_again():
    d = set_field(draft(), "Ticketing system", "GitHub Issues\n- via gh")
    d = set_field(d, "Ticketing system", "GitHub Issues")
    assert "- via gh" not in d
    assert "Connection used (MCP or CLI): Not recorded" in d


def test_append_adds_to_a_field_instead_of_replacing_it():
    d = set_field(draft(), "Ticketing system", "GitHub Issues")
    d = set_field(d, "Ticketing system", "- second line", append=True)
    assert "Ticketing system: GitHub Issues\n- second line" in d


def test_an_unknown_field_is_refused():
    with pytest.raises(KeyError, match="Ticket number"):
        set_field(draft(), "Ticket number", "35")


def test_each_ticket_gets_its_own_section():
    d = add_ticket(draft(), 35)
    d = add_ticket(d, 36)
    d = set_field(d, "Ticket link", "#35 link", ticket=35)
    d = set_field(d, "Ticket link", "#36 link", ticket=36)
    post = render_post(d)
    assert post.count("## Ticket → branch → PR") == 2
    assert post.index("Ticket link: #35 link") < post.index("Ticket link: #36 link")
    assert post.index("Ticket link: #36 link") < post.index("## What I learned")


def test_adding_a_ticket_twice_is_a_no_op():
    d = add_ticket(draft(), 35)
    assert add_ticket(d, 35) == d


def test_a_ticket_field_needs_its_ticket_section():
    with pytest.raises(KeyError, match="#40"):
        set_field(add_ticket(draft(), 35), "Ticket link", "x", ticket=40)


def test_a_ticket_field_needs_a_ticket():
    with pytest.raises(KeyError, match="ticket"):
        set_field(add_ticket(draft(), 35), "Ticket link", "x")


def test_the_post_drops_the_draft_notes_but_keeps_not_recorded():
    post = render_post(add_ticket(draft(), 35))
    assert "<!--" not in post
    assert "Branch and PR link: Not recorded" in post
