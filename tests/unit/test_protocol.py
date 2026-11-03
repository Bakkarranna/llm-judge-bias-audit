"""Tests for the parser and the audit arithmetic."""

from __future__ import annotations

import pytest

from llmjudge.audit import (
    Trial,
    build_trials,
    label,
    repeatability,
    run_trials,
    summarize,
)
from llmjudge.judge import ScriptedJudge, parse_choice


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A", "A"),
        (" a ", "A"),
        ("Answer B", "B"),
        ("b.", "B"),
        ("TIE", "TIE"),
        ("tie", "TIE"),
        ("Choice A", "A"),
        ("", None),
        ("I prefer the second one", None),
        ("A or B", None),
        ("neither", None),
        ("AA", None),
    ],
)
def test_parse_choice(raw, expected):
    assert parse_choice(raw) == expected


def test_build_trials_covers_every_item_twice_per_kind(items):
    trials = build_trials(items)
    assert len(trials) == 3 * 2 * len(items)
    for kind in ("correctness", "verbosity", "authority"):
        same = [trial for trial in trials if trial.kind == kind]
        assert len(same) == 2 * len(items)
        for item in items:
            orders = {trial.gold_first for trial in same if trial.item_id == item.id}
            assert orders == {True, False}


def test_a_correct_judge_scores_full_marks(items):
    trials = build_trials(items)
    results = run_trials(ScriptedJudge("correct"), trials)
    for kind in ("correctness", "verbosity", "authority"):
        summary = summarize(kind, [r for r in results if r.trial.kind == kind])
        assert summary.gold_preference_rate == 1.0
        assert summary.position_gap == 0.0
        assert summary.swap_agreement == 1.0


def test_a_first_position_judge_shows_a_full_gap(items):
    trials = build_trials(items)
    results = run_trials(ScriptedJudge("first"), trials)
    summary = summarize("correctness", results)
    assert summary.gold_first_rate == 1.0
    assert summary.gold_second_rate == 0.0
    assert summary.position_gap == 1.0
    assert summary.first_position_rate == 1.0


def test_a_verbosity_biased_judge_prefers_the_padded_answer(items):
    trials = [trial for trial in build_trials(items) if trial.kind == "verbosity"]
    results = run_trials(ScriptedJudge("longer"), trials)
    summary = summarize("verbosity", results)
    assert summary.gold_preference_rate == 0.0
    assert summary.swap_agreement == 1.0
    assert summary.calls == 2 * len(items)


def test_labels_are_position_free(items):
    item = items[0]
    gold_first = Trial(
        kind="correctness",
        item_id=item.id,
        question=item.question,
        first=item.gold,
        second=item.wrong,
        gold_first=True,
    )
    swapped = Trial(
        kind="correctness",
        item_id=item.id,
        question=item.question,
        first=item.wrong,
        second=item.gold,
        gold_first=False,
    )
    from llmjudge.audit import TrialResult

    def make(trial, choice):
        return TrialResult(
            trial=trial, choice=choice, raw=choice, latency_ms=0.0,
            prompt_tokens=0, completion_tokens=0,
        )

    assert label(make(gold_first, "A")) == "gold"
    assert label(make(swapped, "A")) == "other"
    assert label(make(gold_first, "B")) == "other"
    assert label(make(gold_first, "TIE")) == "tie"
    assert label(make(gold_first, None)) is None


def test_summarize_counts_unparsed_replies_separately():
    item = Trial(
        kind="correctness",
        item_id="x",
        question="q",
        first="a",
        second="b",
        gold_first=True,
    )
    from llmjudge.audit import TrialResult

    def make(choice):
        return TrialResult(
            trial=item, choice=choice, raw=str(choice), latency_ms=1.0,
            prompt_tokens=2, completion_tokens=1,
        )

    summary = summarize("correctness", [make("A"), make(None), make("TIE")])
    assert summary.calls == 3
    assert summary.parsed == 2
    assert summary.decided == 1
    assert summary.ties == 1
    assert summary.gold_preference_rate == 1.0
    assert summary.swap_agreement == 0.0


def test_repeatability_compares_same_comparisons(items):
    trials = build_trials(items)
    first = run_trials(ScriptedJudge("first"), trials)
    second = run_trials(ScriptedJudge("second"), trials)
    agree = repeatability(first, second)
    # The two judges never pick the same position, so no comparison repeats.
    assert agree["correctness"] == 0.0
    assert agree["authority"] == 0.0
    assert agree["overall"] == 0.0
    assert repeatability(first, first)["overall"] == 1.0
    same = repeatability(
        run_trials(ScriptedJudge("correct"), trials), run_trials(ScriptedJudge("correct"), trials)
    )
    assert same["overall"] == 1.0
