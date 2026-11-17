"""Learning score (1-5) for a review finding: how much the user would learn by fixing it themselves.

The criteria and their meaning are in docs/LearningRubric.md. The answers are judgments; this file
only does the arithmetic, so the same answers always give the same score.

Usage:
    python3 scripts/learning_score.py --product y --transferable y --multi-user n \
        --new-concept y --trade-off y --ux n
Prints {"score": 4, "handled_by": "together"}.
"""
from __future__ import annotations

import argparse
import json
import sys

# Scores at or below this are fixed by the agent; above it, the user and agent work through it together.
AGENT_MAX = 3


def learning_score(*, product: bool, transferable: bool, multi_user: bool,
                   new_concept: bool, trade_off: bool, ux: bool) -> int:
    """1 for a workflow bug; otherwise 1 + one per yes (capped at 5), then the cap and the floor."""
    if not product:
        return 1
    score = min(5, 1 + sum([transferable, multi_user, new_concept, trade_off, ux]))
    if not new_concept and not trade_off:  # cap: nothing new and nothing to decide
        score = min(score, 2)
    if multi_user:  # floor, applied last so it wins: who-sees-what bugs always go to the user
        score = max(score, 4)
    return score


def handled_by(score: int) -> str:
    return "agent" if score <= AGENT_MAX else "together"


def _yes(s: str) -> bool:
    if s.lower() in ("y", "yes", "true", "1"):
        return True
    if s.lower() in ("n", "no", "false", "0"):
        return False
    raise argparse.ArgumentTypeError(f"expected y or n, got {s!r}")


def average_score(scores):
    # Rule 5 probe: deliberately sloppy (off-by-one, no empty check). Qodo should NOT comment here.
    return sum(scores) / (len(scores) - 1)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for flag in ("product", "transferable", "multi-user", "new-concept", "trade-off", "ux"):
        p.add_argument(f"--{flag}", type=_yes, required=True, metavar="y|n")
    a = p.parse_args(argv)
    score = learning_score(product=a.product, transferable=a.transferable, multi_user=a.multi_user,
                           new_concept=a.new_concept, trade_off=a.trade_off, ux=a.ux)
    print(json.dumps({"score": score, "handled_by": handled_by(score)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
