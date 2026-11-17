import pytest

from scripts.learning_score import handled_by, learning_score

# The user's own labels for the bugs reviewed so far (docs/LearningRubric.md, "Calibration").
# Answers: product, transferable, multi_user, new_concept, trade_off, ux.
CALIBRATION = [
    ("D1 B1 previous user's words stay on screen", dict(product=True, transferable=True, multi_user=True, new_concept=True, trade_off=True, ux=False), "together"),
    ("D1 B2 untrusted review text plants lessons", dict(product=False, transferable=True, multi_user=False, new_concept=True, trade_off=True, ux=False), "agent"),
    ("D1 B3 paging past 1,000 words", dict(product=True, transferable=True, multi_user=False, new_concept=True, trade_off=True, ux=True), "together"),
    ("D1 B4 failed reads never retry", dict(product=True, transferable=True, multi_user=False, new_concept=True, trade_off=True, ux=True), "together"),
    ("D1 B5 a non-bug still writes a lesson", dict(product=False, transferable=False, multi_user=False, new_concept=False, trade_off=True, ux=False), "agent"),
]


@pytest.mark.parametrize("name, answers, expected", CALIBRATION, ids=[c[0] for c in CALIBRATION])
def test_matches_the_users_labels(name, answers, expected):
    assert handled_by(learning_score(**answers)) == expected


def test_workflow_bugs_score_1_whatever_the_other_answers():
    assert learning_score(product=False, transferable=True, multi_user=True, new_concept=True, trade_off=True, ux=True) == 1


def test_starts_at_1_and_adds_one_per_yes_capped_at_5():
    none = dict(transferable=False, multi_user=False, new_concept=False, trade_off=False, ux=False)
    assert learning_score(product=True, **none) == 1
    assert learning_score(product=True, **{**none, "transferable": True, "new_concept": True}) == 3
    assert learning_score(product=True, transferable=True, multi_user=True, new_concept=True, trade_off=True, ux=True) == 5


def test_multi_user_or_data_safety_is_at_least_4():
    assert learning_score(product=True, transferable=False, multi_user=True, new_concept=False, trade_off=True, ux=False) == 4


def test_nothing_new_and_no_trade_off_caps_at_2():
    assert learning_score(product=True, transferable=True, multi_user=False, new_concept=False, trade_off=False, ux=True) == 2


def test_the_multi_user_floor_beats_the_cap():
    # Even an obvious, already-seen fix stays with the user when it is about who can see what data.
    assert learning_score(product=True, transferable=False, multi_user=True, new_concept=False, trade_off=False, ux=False) == 4


def test_3_and_below_is_handled_by_the_agent_4_and_above_together():
    assert [handled_by(s) for s in range(1, 6)] == ["agent", "agent", "agent", "together", "together"]
