from scripts.backlog_order import (
    Issue,
    change_cost,
    order_backlog,
    parse_category_order,
    parse_depends_on,
    parse_graphql,
)

ORDER = ["core", "review", "decks"]


def epic(n, category):
    return Issue(n, f"Epic: {category}", "OPEN", ["epic", f"category:{category}"], None, "")


def ticket(n, parent, cost=None, deps=(), state="OPEN", title=None):
    labels = [f"change-cost:{cost}"] if cost is not None else []
    body = "## Goal\nSomething.\n\n## Depends on\n" + "".join(f"- #{d}\n" for d in deps)
    return Issue(n, title or f"T{n}", state, labels, parent, body)


def numbers(plan):
    return [e.number for e in plan.order]


# --- change cost -------------------------------------------------------------

def test_change_cost_is_the_highest_level_that_applies():
    assert change_cost(stores_data=True, trust_boundary=True, shared_contract=True, external=True) == 5
    assert change_cost(stores_data=False, trust_boundary=True, shared_contract=True, external=False) == 4
    assert change_cost(stores_data=False, trust_boundary=False, shared_contract=True, external=True) == 3
    assert change_cost(stores_data=False, trust_boundary=False, shared_contract=False, external=True) == 2


def test_change_cost_is_1_when_the_change_is_local():
    assert change_cost(stores_data=False, trust_boundary=False, shared_contract=False, external=False) == 1


# --- parsing -----------------------------------------------------------------

def test_depends_on_reads_only_its_own_section():
    body = (
        "## Goal\nLike #99, but better.\n\n"
        "## Depends on\n- #12 card contract\n- #15\n\n"
        "## Out of scope\n- #77 is a later ticket\n"
    )
    assert parse_depends_on(body) == [12, 15]


def test_depends_on_is_empty_when_none_or_missing():
    assert parse_depends_on("## Depends on\n- None\n") == []
    assert parse_depends_on("## Goal\nNo deps section, mentions #4.\n") == []


def test_category_order_is_read_from_its_numbered_section():
    doc = "# Backlog\n\n1. not this list\n\n## Category order\n\n1. core\n2. review\n3. decks\n\n## Rubric\n1. other\n"
    assert parse_category_order(doc) == ["core", "review", "decks"]


def test_graphql_nodes_become_issues():
    resp = {"data": {"repository": {"issues": {
        "nodes": [{
            "number": 8, "title": "Review", "state": "OPEN", "body": "b",
            "labels": {"nodes": [{"name": "change-cost:3"}]},
            "parent": {"number": 2},
        }, {
            "number": 2, "title": "Epic", "state": "OPEN", "body": "",
            "labels": {"nodes": [{"name": "epic"}]}, "parent": None,
        }],
        "pageInfo": {"hasNextPage": False, "endCursor": None},
    }}}}
    issues = parse_graphql(resp)
    assert issues[0] == Issue(8, "Review", "OPEN", ["change-cost:3"], 2, "b")
    assert issues[1].parent is None


# --- ordering ----------------------------------------------------------------

def test_core_comes_before_features_and_cost_orders_within_a_category():
    issues = [
        epic(1, "core"), epic(2, "review"),
        ticket(10, 2, cost=5),
        ticket(11, 1, cost=1),
        ticket(12, 1, cost=4),
    ]
    assert numbers(order_backlog(issues, ORDER)) == [12, 11, 10]


def test_category_is_inherited_through_the_parent_chain():
    issues = [epic(1, "core"), ticket(5, 1), ticket(6, 5, cost=2)]  # 5 is a container
    plan = order_backlog(issues, ORDER)
    assert [(e.number, e.category) for e in plan.order] == [(6, "core")]


def test_ties_on_cost_go_to_the_ticket_more_work_depends_on():
    issues = [
        epic(1, "core"),
        ticket(10, 1, cost=3),
        ticket(11, 1, cost=3),
        ticket(12, 1, cost=1, deps=[11]),
        ticket(13, 1, cost=1, deps=[12]),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan)[:2] == [11, 10]
    assert {e.number: e.dependants for e in plan.order}[11] == 2  # 12 directly, 13 through 12


def test_a_dependency_always_comes_first_even_if_it_costs_less():
    issues = [epic(1, "core"), ticket(10, 1, cost=1), ticket(11, 1, cost=5, deps=[10])]
    assert numbers(order_backlog(issues, ORDER)) == [10, 11]


def test_closed_tickets_are_done_and_satisfy_dependencies():
    issues = [epic(1, "core"), ticket(10, 1, cost=5, state="CLOSED"), ticket(11, 1, cost=2, deps=[10])]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [11]
    assert plan.order[0].blocked_by == []
    assert plan.next == 11


def test_depending_on_a_container_means_depending_on_its_open_children():
    issues = [
        epic(1, "core"), epic(2, "review"),
        ticket(5, 1),                      # container
        ticket(6, 5, cost=1),
        ticket(7, 5, cost=1, state="CLOSED"),
        ticket(20, 2, cost=5, deps=[5]),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [6, 20]
    assert {e.number: e.blocked_by for e in plan.order}[20] == [6]


def test_missing_cost_or_category_goes_to_triage_not_a_default():
    issues = [
        epic(1, "core"),
        ticket(10, 1),                    # no change-cost label
        ticket(11, None, cost=3),         # no epic above it
        ticket(12, 1, cost=2),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [12]
    assert sorted(n for n, _ in plan.triage) == [10, 11]
    reasons = dict(plan.triage)
    assert "change-cost" in reasons[10]
    assert "category" in reasons[11]


def test_a_category_missing_from_the_order_goes_to_triage():
    issues = [epic(1, "lyrics"), ticket(10, 1, cost=2)]
    plan = order_backlog(issues, ORDER)
    assert plan.order == []
    assert "lyrics" in dict(plan.triage)[10]


def test_a_blocker_in_a_later_category_is_pulled_forward_and_flagged():
    issues = [
        epic(1, "core"), epic(2, "review"), epic(3, "decks"),
        ticket(10, 1, cost=1, deps=[30]),
        ticket(20, 2, cost=5),
        ticket(30, 3, cost=1),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [30, 10, 20]
    assert any("#30" in w and "#10" in w for w in plan.warnings)


def test_unknown_dependencies_are_warned_about():
    issues = [epic(1, "core"), ticket(10, 1, cost=2, deps=[404])]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [10]
    assert any("#404" in w for w in plan.warnings)


def test_a_cycle_is_reported_instead_of_ordered():
    issues = [
        epic(1, "core"),
        ticket(10, 1, cost=2, deps=[11]),
        ticket(11, 1, cost=2, deps=[10]),
        ticket(12, 1, cost=1),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [12]
    assert sorted(plan.cycle) == [10, 11]


def test_next_is_the_first_ticket_with_nothing_open_blocking_it():
    issues = [
        epic(1, "core"),
        ticket(10, 1, cost=5, deps=[11]),
        ticket(11, 1),                    # in triage, still open
        ticket(12, 1, cost=1),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [12]
    assert plan.next == 12


# --- Day 3 review regressions ------------------------------------------------

def test_fenced_examples_are_not_dependencies():
    fence = "```markdown\n## Depends on\n- #99\n```\n"
    before = "## Goal\nLike this:\n\n" + fence + "\n## Depends on\n- #12\n"
    after = "## Depends on\n- #12\n\n## Notes\n" + fence
    assert parse_depends_on(before) == [12]
    assert parse_depends_on(after) == [12]


def test_a_comment_inside_a_fence_does_not_end_the_section():
    body = "## Depends on\n- #12\n```sh\n# a shell comment\n```\n- #15\n"
    assert parse_depends_on(body) == [12, 15]


def test_a_ticket_waiting_on_triage_work_is_kept_out_of_the_order():
    issues = [
        epic(1, "core"),
        ticket(10, 1, cost=5, deps=[11]),
        ticket(11, 1),                    # in triage, still open
        ticket(13, 1, cost=4, deps=[10]), # waits on 10, so on 11 too
        ticket(12, 1, cost=1),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [12]
    assert dict(plan.blocked) == {10: [11], 13: [10]}


def test_a_closed_parent_with_open_sub_issues_still_blocks():
    issues = [
        epic(1, "core"),
        ticket(5, 1, state="CLOSED"),     # closed container
        ticket(6, 5, cost=1),             # its sub-issue is still open
        ticket(20, 1, cost=5, deps=[5]),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [6, 20]
    assert {e.number: e.blocked_by for e in plan.order}[20] == [6]


def test_a_ticket_that_lists_itself_is_stuck_not_scheduled():
    issues = [epic(1, "core"), ticket(10, 1, cost=2, deps=[10]), ticket(12, 1, cost=1)]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [12]
    assert plan.cycle == [10]


def test_depending_on_your_own_container_is_not_a_self_dependency():
    issues = [
        epic(1, "core"),
        ticket(5, 1),
        ticket(6, 5, cost=1, deps=[5]),
        ticket(7, 5, cost=1),
    ]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [7, 6]
    assert plan.cycle == []


def test_truncated_labels_fail_loudly():
    import pytest
    node = {"number": 3, "title": "T", "state": "OPEN", "body": "", "parent": None,
            "labels": {"nodes": [{"name": "epic"}], "pageInfo": {"hasNextPage": True}}}
    resp = {"data": {"repository": {"issues": {"nodes": [node]}}}}
    with pytest.raises(ValueError, match="#3"):
        parse_graphql(resp)


def test_the_real_backlog_doc_starts_with_core_and_lists_every_category():
    from scripts.backlog_order import BACKLOG_DOC
    order = parse_category_order(BACKLOG_DOC.read_text())
    assert order[0] == "core"
    assert len(order) == len(set(order)) == 10


# --- tickets with pull requests ------------------------------------------------

def with_prs(issue, open_prs=(), closed_prs=()):
    issue.open_prs, issue.closed_prs = list(open_prs), list(closed_prs)
    return issue


def test_a_ticket_with_an_open_pr_is_in_review_and_never_next():
    issues = [epic(1, "core"), with_prs(ticket(10, 1, cost=5), open_prs=[77]), ticket(11, 1, cost=1)]
    plan = order_backlog(issues, ORDER)
    assert numbers(plan) == [10, 11]
    assert plan.order[0].in_review == [77]
    assert plan.next == 11


def test_work_that_depends_on_a_ticket_in_review_is_not_next():
    issues = [epic(1, "core"), with_prs(ticket(10, 1, cost=5), open_prs=[77]), ticket(11, 1, cost=1, deps=[10])]
    plan = order_backlog(issues, ORDER)
    assert plan.next is None


def test_a_pr_closed_without_merging_is_reported_on_its_ticket():
    from scripts.backlog_order import render
    issues = [epic(1, "core"), with_prs(ticket(10, 1, cost=5), closed_prs=[78])]
    plan = order_backlog(issues, ORDER)
    assert plan.order[0].closed_prs == [78]
    assert "#78 closed without merging" in render(plan)


def test_in_review_is_shown_in_the_listing():
    from scripts.backlog_order import render
    issues = [epic(1, "core"), with_prs(ticket(10, 1, cost=5), open_prs=[77])]
    assert "in review: PR #77" in render(order_backlog(issues, ORDER))


def test_graphql_reads_open_and_closed_unmerged_prs_but_not_merged_ones():
    node = {
        "number": 8, "title": "T", "state": "OPEN", "body": "",
        "labels": {"nodes": []}, "parent": None,
        "closedByPullRequestsReferences": {"nodes": [
            {"number": 77, "state": "OPEN"}, {"number": 78, "state": "CLOSED"}, {"number": 79, "state": "MERGED"},
        ]},
    }
    resp = {"data": {"repository": {"issues": {"nodes": [node], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}
    issue = parse_graphql(resp)[0]
    assert (issue.open_prs, issue.closed_prs) == ([77], [78])
