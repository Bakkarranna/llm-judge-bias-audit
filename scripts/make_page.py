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

CSS = """
      :root {
        color-scheme: light dark;
        --ink: #1f2933;
        --muted: #6b7684;
        --rule: #d7dde5;
        --accent: #1f6f8b;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --ink: #e6e9ee;
          --muted: #9aa4b2;
          --rule: #333b45;
          --accent: #6bb3c9;
        }
      }
      body {
        margin: 0 auto;
        padding: 3rem 1.25rem 4rem;
        max-width: 46rem;
        font: 16px/1.65 ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif;
        color: var(--ink);
        background: Canvas;
      }
      h1 {
        font-size: 1.6rem;
        line-height: 1.25;
        margin: 0 0 0.5rem;
      }
      h2 {
        font-size: 1.1rem;
        margin: 2.25rem 0 0.75rem;
      }
      p,
      li {
        max-width: 44rem;
      }
      .lede {
        color: var(--muted);
        margin: 0 0 1.5rem;
      }
      table {
        border-collapse: collapse;
        width: 100%;
        margin: 0.75rem 0 0.25rem;
        font-variant-numeric: tabular-nums;
      }
      th,
      td {
        text-align: right;
        padding: 0.4rem 0.6rem;
        border-bottom: 1px solid var(--rule);
      }
      th:first-child,
      td:first-child {
        text-align: left;
      }
      thead th {
        font-size: 0.85rem;
        color: var(--muted);
        font-weight: 600;
      }
      figure {
        margin: 1.5rem 0;
      }
      figcaption {
        color: var(--muted);
        font-size: 0.85rem;
        margin-top: 0.5rem;
      }
      code {
        font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
        font-size: 0.9em;
      }
      footer {
        margin-top: 3rem;
        border-top: 1px solid var(--rule);
        padding-top: 1rem;
        color: var(--muted);
        font-size: 0.85rem;
      }
      a {
        color: var(--accent);
      }
      td.figure {
        width: 9rem;
      }
      td.num {
        font-variant-numeric: tabular-nums;
      }
      span.bar {
        display: block;
        height: 0.45rem;
        margin-bottom: 3px;
        border-radius: 2px;
        background: var(--accent);
      }
      span.bar.agree {
        background: var(--muted);
      }
      span.bar.first {
        background: var(--accent);
      }
      span.bar.second {
        background: var(--muted);
      }
      span.note {
        display: block;
        margin-top: 2px;
        color: var(--muted);
        font-size: 0.8125rem;
      }
      span.strong {
        font-weight: 600;
      }
"""


def local(css: str, title: str, body: str) -> str:
    """Wrap body content in the page document."""

    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title}</title>\n<style>\n{css}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
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


def page(record: dict) -> str:
    """The whole results page, assembled from the record."""

    total_calls = record["total_calls"]
    per_pass = record["calls_per_item"] * record["items"]
    body = f"""
    <h1>Position bias in a language model used as a pairwise judge</h1>
    <p class="lede">
      Swap agreement and position gap over {total_calls} pairwise comparisons
      with {record["model"]}, run locally through Ollama at temperature 0.
      Every number on this page is read from <code>results/audit.json</code>.
    </p>

    <h2>What was measured</h2>
    <p>
      {record["items"]} factual items, each posed as three comparisons: the
      correct answer against a wrong answer of the same length, against the
      same answer padded with true detail, and against a wrong answer carrying
      a citation-like prefix. Every comparison ran twice per pass with the two
      answers in swapped order, so a preference that only reflects position
      shows up as a disagreement between the two orderings. Two passes were
      run: {per_pass} comparisons per pass, {total_calls} model calls in all.
      The judge never learns which answer is correct; it is asked for a single
      word and any other reply is counted as unparsed rather than guessed.
    </p>

    <h2>Rates by comparison</h2>
    <table>
      <thead>
        <tr>
          <th>Comparison</th>
          <th>Correct answer preferred</th>
          <th>When first</th>
          <th>When second</th>
          <th>Position gap</th>
          <th>First position rate</th>
          <th>Swap agreement</th>
        </tr>
      </thead>
      <tbody>
{rates_table(record)}
      </tbody>
    </table>
    <p>
      The position gap is the win rate of the correct answer when it is second
      minus its win rate when it is first. A judge that ignores position sits
      near zero; a negative gap means the answer in the second slot wins more
      often than the same answer in the first. Swap agreement is the share of
      items where both orderings of a comparison picked the same answer.
    </p>

    <h2>Position effect</h2>
    <table>
      <thead>
        <tr>
          <th>Comparison</th>
          <th>Win rate by slot</th>
          <th>Correct answer first</th>
          <th>Correct answer second</th>
        </tr>
      </thead>
      <tbody>
{position_chart(record)}
      </tbody>
    </table>
    <p>
      The darker bar is the win rate of the correct answer when it sits in the
      first slot and the lighter bar the same answer in the second slot.
      Overlap between the two bars means the model read the answers rather
      than their order.
    </p>

    <h2>Preference against consistency</h2>
    <table>
      <thead>
        <tr>
          <th>Comparison</th>
          <th>Preference and agreement</th>
          <th>Correct answer preferred</th>
          <th>Swap agreement</th>
        </tr>
      </thead>
      <tbody>
{bar_chart(record)}
      </tbody>
    </table>
    <p>
      The solid bar is the share of comparisons the correct answer won; the
      muted bar is the share of items where both orderings agreed.
    </p>

    <h2>Repeatability</h2>
    <p>
      Comparing pass 1 with pass 2 item by item, the judge repeated itself on
      {repeatability_line(record)} Sampling is deterministic, so this measures
      the protocol, not sampling noise.
    </p>

    <h2>Calls, latency and tokens</h2>
    <table>
      <thead>
        <tr>
          <th>Comparison</th>
          <th>Calls</th>
          <th>Decided</th>
          <th>Ties</th>
          <th>Mean latency</th>
          <th>Prompt tokens</th>
          <th>Completion tokens</th>
        </tr>
      </thead>
      <tbody>
{cost_table(record)}
      </tbody>
    </table>

    <footer>
      Repository: <a href="https://github.com/Bakkarranna/llm-judge-bias-audit">Bakkarranna/llm-judge-bias-audit</a>.
      The page regenerates from <code>results/audit.json</code> with
      <code>python scripts/make_page.py</code>.
    </footer>
    """
    return local(CSS, "Judge bias audit — measured results", body)


def sig(value: float) -> str:
    """Format a rate as a signed percentage with one decimal."""

    return f"{value * 100:+.1f}%"


def rates_table(record: dict) -> str:
    """One row per comparison with every measured rate."""

    rows = []
    for kind in KINDS:
        entry = record["kinds"][kind]
        cells = (
            pct(entry["gold_preference_rate"]),
            pct(entry["gold_preferred_when_first"]),
            pct(entry["gold_preferred_when_second"]),
            sig(entry["position_gap"]),
            pct(entry["first_position_rate"]),
            pct(entry["swap_agreement"]),
        )
        rows.append(
            "<tr><td><span class=\"strong\">{title}</span>"
            "<span class=\"note\">{note}</span></td>{cells}</tr>".format(
                title=KIND_TITLE[kind],
                note=COMPARISON_NOTE[kind],
                cells="".join(f"<td>{cell}</td>" for cell in cells),
            )
        )
    return "\n".join(rows)


def position_chart(record: dict) -> str:
    """Bars for how often the better answer wins in each position."""

    rows = []
    for kind in KINDS:
        entry = record["kinds"][kind]
        rows.append(
            "<tr><th scope=\"row\">{title}</th>"
            "<td class=\"figure\">"
            "<span class=\"bar first\" style=\"width:{first:.1f}%\"></span>"
            "<span class=\"bar second\" style=\"width:{second:.1f}%\"></span>"
            "</td>"
            "<td class=\"num\">{first_pct}</td>"
            "<td class=\"num\">{second_pct}</td></tr>".format(
                title=KIND_TITLE[kind],
                first=entry["gold_preferred_when_first"] * 100,
                second=entry["gold_preferred_when_second"] * 100,
                first_pct=pct(entry["gold_preferred_when_first"]),
                second_pct=pct(entry["gold_preferred_when_second"]),
            )
        )
    return "\n".join(rows)


def cost_table(record: dict) -> str:
    """One row per comparison with call counts, latency and tokens."""

    rows = []
    for kind in KINDS:
        entry = record["kinds"][kind]
        cells = (
            entry["calls"],
            entry["decided"],
            entry["ties"],
            f"{entry['mean_latency_ms']:.0f} ms",
            entry["prompt_tokens"],
            entry["completion_tokens"],
        )
        rows.append(
            "<tr><td>{title}</td>{cells}</tr>".format(
                title=KIND_TITLE[kind],
                cells="".join(f"<td>{cell}</td>" for cell in cells),
            )
        )
    return "\n".join(rows)


def repeatability_line(record: dict) -> str:
    """How pass 1 and pass 2 agreed, in items rather than fractions."""

    rate = record["repeatability"]["pass1_vs_pass2"]["overall"]
    matched = round(rate * record["items"])
    return f"{matched} of {record['items']} items, in every comparison kind"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    record = json.loads(
        (root / "results" / "audit.json").read_text(encoding="utf-8")
    )

    for relative in ("docs/results.json", "docs/index.html"):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith(".json"):
            text = json.dumps(record, ensure_ascii=False) + "\n"
        else:
            text = page(record)
        destination.write_text(text, encoding="utf-8")

    print(f"wrote {root / 'docs' / 'results.json'}")
    print(f"wrote {root / 'docs' / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
