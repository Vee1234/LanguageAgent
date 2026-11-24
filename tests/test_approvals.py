import pytest

from scripts.approvals import NEEDS_APPROVAL, needs_approval, option_id, render, item_id

REPO = "Vee1234/LanguageAgent"


def item(n, status, typ="Issue", repo=REPO, title=None):
    return {"id": f"PVTI_{n}", "status": status, "title": title or f"T{n}",
            "content": {"number": n, "type": typ, "repository": repo, "title": title or f"T{n}",
                        "url": f"https://github.com/{repo}/issues/{n}"}}


def test_lists_only_this_repos_issues_in_needs_approval_in_number_order():
    items = [item(9, NEEDS_APPROVAL), item(3, "Todo"), item(4, NEEDS_APPROVAL),
             item(5, NEEDS_APPROVAL, typ="PullRequest"), item(6, NEEDS_APPROVAL, repo="x/other"),
             {"id": "draft", "status": NEEDS_APPROVAL, "title": "a draft note", "content": {"type": "DraftIssue"}}]
    assert [t["number"] for t in needs_approval(items, REPO)] == [4, 9]


def test_render_says_plainly_when_nothing_waits():
    assert render([]) == "No tickets are waiting in Needs Approval."
    out = render([{"number": 4, "title": "Ship it", "url": "u4", "prs": [71]}])
    assert "#4 Ship it" in out and "PR #71" in out


FIELDS = {"fields": [{"id": "F1", "name": "Priority", "options": [{"id": "p", "name": NEEDS_APPROVAL}]},
                     {"id": "F2", "name": "Status", "options": [{"id": "o1", "name": "Todo"},
                                                                 {"id": "o2", "name": NEEDS_APPROVAL}]}]}


def test_option_id_is_found_by_field_and_option_name():
    assert option_id(FIELDS, "Status", NEEDS_APPROVAL) == ("F2", "o2")


def test_a_missing_status_option_is_an_error_not_a_silent_skip():
    with pytest.raises(LookupError, match="Needs Approval"):
        option_id({"fields": [{"id": "F2", "name": "Status", "options": [{"id": "o1", "name": "Todo"}]}]},
                  "Status", NEEDS_APPROVAL)


def test_item_id_finds_this_repos_issue_on_the_board():
    items = [item(4, "Todo", repo="x/other"), item(4, "Todo")]
    assert item_id(items, REPO, 4) == "PVTI_4" and items[1]["id"] == "PVTI_4"
    assert item_id(items, REPO, 99) is None
