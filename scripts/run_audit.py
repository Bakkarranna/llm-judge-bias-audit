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

from llmjudge.audit import KINDS, Trial, TrialResult, build_trials, run_trials  # noqa: E402
from llmjudge.data import load_items  # noqa: E402
from llmjudge.judge import OllamaJudge  # noqa: E402
from llmjudge.metrics import build_record, load_record, write_record  # noqa: E402


def rebuild_passes(calls: list[dict], per_pass: int) -> list[list[TrialResult]]:
    """Rebuild the per-pass results a record holds, from its raw calls.

    The stored calls carry everything the metrics read -- the comparison, its
    orderings, the reply and its cost -- so a record can be re-measured without
    asking the model again. The question and answer text are not needed here
    and are left empty.
    """

    results: list[TrialResult] = []
    for call in calls:
        trial = Trial(
            kind=call["kind"],
            item_id=call["item"],
            question="",
            first="",
            second="",
            gold_first=call["gold_first"],
        )
        results.append(
            TrialResult(
                trial=trial,
                choice=call["choice"],
                raw=call["reply"],
                latency_ms=call["latency_ms"],
                prompt_tokens=call["prompt_tokens"],
                completion_tokens=call["completion_tokens"],
            )
        )
    return [results[index : index + per_pass] for index in range(0, len(results), per_pass)]


def notes_for(items: int, trials: int, passes: int, elapsed: float) -> str:
    """The provenance note stored with every record."""

    return (
        f"{items} items, {trials} comparisons per pass, {passes} passes, "
        f"temperature 0 and seed 42, {elapsed:.0f} s of wall clock. "
        "The judge is asked for exactly one word, A or B; any other reply is "
        "counted as unparsed rather than guessed at."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5:1.5b")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--items", default=str(ROOT / "data" / "items.json"))
    parser.add_argument("--results", default=str(ROOT / "results" / "audit.json"))
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--limit-items", type=int, default=0)
    parser.add_argument(
        "--recount",
        default="",
        help="recompute the numbers in a stored record from its calls, with no "
        "new model calls",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.recount:
        return recount(args)

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
            notes=notes_for(
                len(items), len(trials), len(passes), time.time() - started
            ),
        )
        write_record(checkpoint, args.results)
        print(f"  checkpoint written to {args.results}", flush=True)
    elapsed = time.time() - started

    record = build_record(
        model=args.model,
        items=items,
        passes=passes,
        judge_label="local-ollama",
        notes=notes_for(len(items), len(trials), args.passes, elapsed),
    )
    path = write_record(record, args.results)
    print(f"wrote {path}")
    return 0


def recount(args: argparse.Namespace) -> int:
    """Rewrite a stored record's numbers with the metrics of the current code."""

    stored = load_record(args.recount)
    items = load_items(args.items)
    if len(items) != stored["items"]:
        print(
            f"{args.recount} holds {stored['items']} items but {args.items} holds "
            f"{len(items)}"
        )
        return 2

    calls = stored["calls"]
    per_pass = len(calls) // stored["calls_per_item"]
    record = build_record(
        model=stored["model"],
        items=items,
        passes=rebuild_passes(calls, per_pass),
        judge_label=stored["judge"],
        notes=stored["notes"],
    )
    path = write_record(record, args.results)
    print(f"recounted {len(calls)} calls from {args.recount} into {path}")
    for kind in KINDS:
        summary = record["kinds"][kind]
        print(
            f"  {kind:<12} gold {summary['gold_preference_rate']:.3f} "
            f"swap {summary['swap_agreement']:.3f} ties {summary['ties']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
