"""Reporting a run, written only from measured numbers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .audit import KINDS, TrialResult, repeatability, summarize_run
from .data import Item


def build_record(
    model: str,
    items: list[Item],
    passes: list[list[TrialResult]],
    judge_label: str,
    notes: str,
) -> dict:
    """Assemble the record written to results/audit.json.

    ``passes`` holds one list of results per full pass; every derived number is
    computed here from the recorded decisions.
    """

    flat = [result for results in passes for result in results]
    per_pass = [summarize_run(results) for results in passes]

    pool: dict[str, list[TrialResult]] = {kind: [] for kind in KINDS}
    for result in flat:
        pool[result.trial.kind].append(result)

    kinds = {kind: summarize_run(pool[kind])[kind].as_dict() for kind in KINDS}

    repeat: dict[str, dict] = {}
    for index in range(len(passes) - 1):
        agree = repeatability(passes[index], passes[index + 1])
        repeat[f"pass{index + 1}_vs_pass{index + 2}"] = {
            key: round(value, 4) for key, value in agree.items()
        }

    item_texts = {item.id: item for item in items}
    raw = []
    for result in flat:
        raw.append(
            {
                "kind": result.trial.kind,
                "item": result.trial.item_id,
                "gold_first": result.trial.gold_first,
                "choice": result.choice,
                "reply": result.raw,
                "latency_ms": round(result.latency_ms, 2),
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            }
        )

    return {
        "model": model,
        "judge": judge_label,
        "items": len(item_texts),
        "calls_per_item": len(passes),
        "total_calls": len(flat),
        "kinds": kinds,
        "per_pass": [
            {kind: summary.as_dict() for kind, summary in run.items()} for run in per_pass
        ],
        "repeatability": repeat,
        "calls": raw,
        "notes": notes,
    }


def write_record(record: dict, path: str | Path) -> Path:
    """Write the record as UTF-8 JSON with a trailing newline."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target


def load_record(path: str | Path) -> dict:
    """Read a record back."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def stamp() -> str:
    """The UTC time a run started, so a record can be dated."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
