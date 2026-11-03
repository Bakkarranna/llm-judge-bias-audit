"""Rendering the results page and the figures from a record.

Everything written here comes from the record: no number is computed twice by
hand or typed into the template.
"""

from __future__ import annotations

import json
from pathlib import Path

KIND_TITLE = {
    "correctness": "Correctness",
    "verbosity": "Verbosity",
    "authority": "Authority",
}

COMPARISON_NOTE = {
    "correctness": "correct answer against a length-matched wrong answer",
    "verbosity": "correct answer against the same answer padded with true detail",
    "authority": "correct answer against a wrong answer with a citation-like prefix",
}

KINDS = ("correctness", "verbosity", "authority")


def local(css: str, title: str, body: str) -> str:
    """Wrap body content in the page document."""

    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title}</title>\n<style>\n{css}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def pct(value: float) -> str:
    """Format a rate as a percentage with one decimal."""

    return f"{value * 100:.1f}%"


def bar_chart(record: dict) -> str:
    """Inline bars for the gold preference rate and the swap agreement."""

    rows = []
    for kind in KINDS:
        entry = record["kinds"][kind]
        rows.append(
            "<tr><th scope=\"row\">{title}</th>"
            "<td class=\"figure\"><span class=\"bar gold\" style=\"width:{gold:.1f}%\"></span>"
            "<span class=\"bar agree\" style=\"width:{agree:.1f}%\"></span></td>"
            "<td class=\"num\">{gold_pct}</td><td class=\"num\">{agree_pct}</td></tr>".format(
                title=KIND_TITLE[kind],
                gold=entry["gold_preference_rate"] * 100,
                agree=entry["swap_agreement"] * 100,
                gold_pct=pct(entry["gold_preference_rate"]),
                agree_pct=pct(entry["swap_agreement"]),
            )
        )
    return "\n".join(rows)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    record = json.loads(
        (root / "results" / "audit.json").read_text(encoding="utf-8")
    )

    for relative in ("docs/results.json",):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"wrote {root / 'docs' / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
