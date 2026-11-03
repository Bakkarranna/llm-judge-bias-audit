#!/usr/bin/env python3
"""Run the audit against a real judge and write results/audit.json.

Examples:
    python scripts/run_audit.py --model qwen2.5:1.5b --results results/audit.json

The measured run is committed to the repository, so the README and the results
page quote numbers produced by this script and nothing else.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llmjudge.audit import KINDS, build_trials, run_trials  # noqa: E402
from llmjudge.data import load_items  # noqa: E402
from llmjudge.judge import OllamaJudge  # noqa: E402
from llmjudge.metrics import build_record, write_record  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5:1.5b")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--items", default=str(ROOT / "data" / "items.json"))
    parser.add_argument("--results", default=str(ROOT / "results" / "audit.json"))
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--limit-items", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    judge = OllamaJudge(model=args.model, url=args.url)

    if not judge.available():
        print(f"no model server at {args.url}; start Ollama and pull {args.model}")
        return 2

    items = load_items(args.items)
    if args.limit_items:
        items = items[: args.limit_items]
    trials = build_trials(items)

    passes = []
    started = time.time()
    for index in range(args.passes):
        label = f"pass {index + 1}/{args.passes}"
        results = run_trials(judge, trials)
        passes.append(results)
        parsed = sum(1 for result in results if result.choice in {"A", "B", "TIE"})
        print(f"{label}: {len(results)} calls, {parsed} parsed", flush=True)
        for kind in KINDS:
            same_kind = [result for result in results if result.trial.kind == kind]
            from llmjudge.audit import summarize

            summary = summarize(kind, same_kind)
            print(
                f"  {kind:<12} gold {summary.gold_preference_rate:.3f} "
                f"swap {summary.swap_agreement:.3f} ties {summary.ties}",
                flush=True,
            )
        # Each pass takes minutes, so the record is written as the run goes and
        # an interruption loses the pass in flight and nothing else.
        checkpoint = build_record(
            model=args.model,
            items=items,
            passes=passes,
            judge_label="local-ollama",
            notes=(
                f"{len(items)} items, {len(trials)} comparisons per pass, "
                f"{args.passes} passes, temperature 0 and seed 42. "
                "The judge is asked for exactly one word, A or B; any other reply "
                "is counted as unparsed rather than guessed at."
            ),
            elapsed_seconds=time.time() - started,
        )
        write_record(checkpoint, args.results)
        print(f"  checkpoint written to {args.results}", flush=True)
    elapsed = time.time() - started

    record = build_record(
        model=args.model,
        items=items,
        passes=passes,
        judge_label="local-ollama",
        notes=(
            f"{len(items)} items, {len(trials)} comparisons per pass, "
            f"{args.passes} passes, temperature 0 and seed 42, {elapsed:.0f} s total. "
            "The judge is asked for exactly one word, A or B; any other reply is "
            "counted as unparsed rather than guessed at."
        ),
    )
    path = write_record(record, args.results)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
