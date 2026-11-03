#!/usr/bin/env python3
"""Self-check of the audit protocol.

The protocol is only worth running on a real model if it reports the right
signals for judges whose behaviour is known in advance. Four scripted judges
cover the cases that matter: two that follow the position, one that follows the
length, and one that follows the answer.

Run: python scripts/smoke_audit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llmjudge.audit import KINDS, build_trials, run_trials, summarize  # noqa: E402
from llmjudge.data import load_items  # noqa: E402
from llmjudge.judge import ScriptedJudge, parse_choice  # noqa: E402


def check(condition: bool, message: str, failures: list[str]) -> None:
    """Record one assertion without stopping the run."""

    print(("  PASS  " if condition else "  FAIL  ") + message)
    if not condition:
        failures.append(message)


def main() -> int:
    items = load_items(ROOT / "data" / "items.json")
    by_kind = {
        kind: [trial for trial in build_trials(items) if trial.kind == kind]
        for kind in KINDS
    }
    failures: list[str] = []

    print("item file")
    check(len(items) >= 20, f"{len(items)} items loaded", failures)

    # A judge that follows the answer keeps its preference when the answers are
    # swapped; a judge that follows the position flips it. Both show up as
    # single numbers in the protocol, so both are checked here.
    expectations = {
        "first": {"swap_agreement": 0.0},
        "second": {"swap_agreement": 0.0},
        "longer": {"swap_agreement": 1.0},
        "correct": {"swap_agreement": 1.0},
    }

    for policy, expected in expectations.items():
        judge = ScriptedJudge(policy)
        print(f"scripted judge: {policy}")
        for kind, trials in by_kind.items():
            results = run_trials(judge, trials)
            summary = summarize(kind, results)
            check(
                summary.parsed == summary.calls,
                f"{kind}: every reply parses ({summary.parsed}/{summary.calls})",
                failures,
            )
            check(
                abs(summary.swap_agreement - expected["swap_agreement"]) < 1e-9,
                f"{kind}: swap agreement {expected['swap_agreement']:.1f} for this judge "
                f"(got {summary.swap_agreement:.2f})",
                failures,
            )
            if policy == "correct":
                check(
                    summary.gold_preference_rate == 1.0,
                    f"{kind}: gold preferred every time (got {summary.gold_preference_rate:.2f})",
                    failures,
                )
                check(
                    summary.position_gap == 0.0,
                    f"{kind}: no position gap (got {summary.position_gap:.2f})",
                    failures,
                )
            if policy in {"first", "second"}:
                check(
                    abs(summary.position_gap) == 1.0,
                    f"{kind}: full position gap (got {summary.position_gap:+.2f})",
                    failures,
                )
            if policy == "longer" and kind != "correctness":
                # On both of these tests gold is the shorter answer, so a judge
                # that follows length must show a gold preference rate of zero.
                check(
                    summary.gold_preference_rate == 0.0,
                    f"{kind}: padded answer preferred over gold (gold rate "
                    f"{summary.gold_preference_rate:.2f})",
                    failures,
                )

    print("parser")
    readable = {"A": "A", " a ": "A", "Answer B": "B", "b.": "B", "TIE": "TIE", "tie": "TIE"}
    for text, expected in readable.items():
        check(parse_choice(text) == expected, f"parses {text!r} as {expected}", failures)
    for text in ("", "I prefer the second one", "A or B", "neither"):
        check(parse_choice(text) is None, f"rejects {text!r}", failures)

    print()
    if failures:
        print(f"FAILED {len(failures)} checks")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("All protocol checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
