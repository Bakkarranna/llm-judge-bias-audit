"""The record written by a run, checked with scripted judges."""

from __future__ import annotations

import json

from llmjudge.audit import build_trials, run_trials
from llmjudge.judge import ScriptedJudge
from llmjudge.metrics import build_record, write_record


def test_record_holds_every_call_and_the_summaries(items):
    trials = build_trials(items)
    passes = [run_trials(ScriptedJudge("correct"), trials) for _ in range(2)]
    record = build_record(
        model="scripted",
        items=items,
        passes=passes,
        judge_label="scripted",
        notes="test",
    )
    assert record["total_calls"] == len(passes[0]) * 2
    assert len(record["calls"]) == record["total_calls"]
    for kind in ("correctness", "verbosity", "authority"):
        entry = record["kinds"][kind]
        assert entry["gold_preference_rate"] == 1.0
        assert entry["parsed"] == entry["calls"]
    assert record["repeatability"]["pass1_vs_pass2"]["overall"] == 1.0


def test_a_biased_judge_is_visible_in_the_record(items, tmp_path):
    trials = build_trials(items)
    passes = [run_trials(ScriptedJudge("longer"), trials)]
    record = build_record(
        model="scripted",
        items=items,
        passes=passes,
        judge_label="scripted",
        notes="test",
    )
    assert record["kinds"]["verbosity"]["gold_preference_rate"] == 0.0
    assert record["kinds"]["verbosity"]["swap_agreement"] == 1.0
    assert record["calls_per_item"] == 1

    path = write_record(record, tmp_path / "audit.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["total_calls"] == record["total_calls"]
