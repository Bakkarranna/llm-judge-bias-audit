# LLM judge bias audit

[![CI](https://github.com/Bakkarrarna/llm-judge-bias-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/Bakkarrarna/llm-judge-bias-audit/actions/workflows/ci.yml)
[![Pages](https://github.com/Bakkarrarna/llm-judge-bias-audit/actions/workflows/pages.yml/badge.svg)](https://github.com/Bakkarrarna/llm-judge-bias-audit/actions/workflows/pages.yml)

A measured audit of position bias in a pairwise judge built on a small
language model. The judge is given a factual question and two answers and is
asked to name the better one with a single letter. The audit measures how
often the answer's slot, rather than its content, decides the verdict, and how
often the judge contradicts itself when the two answers swap places.

Every comparison ran in both orders over 100 factual items, twice, and the
judge preferred the correct answer 292 of 400 times on correctness, 230 of 400
on verbosity and 215 of 400 on authority. Its verdicts were far less consistent
than those rates suggest: the same comparison in the opposite order agreed only
46.0%, 31.0% and 7.5% of the time. Every number in this report was measured on
one machine and written to `results/audit.json` by the scripts in `scripts/`.
Nothing here is estimated.

The model is `qwen2.5:1.5b` served by Ollama on 127.0.0.1:11434 at temperature
0 with seed 42. The judge label in the record is `local-ollama`. The full run
is 1,200 model calls over 2,966 seconds of wall clock.

## What was measured

`data/items.json` holds 100 factual items, each with a question and four
answers: the correct answer, a wrong answer of similar length, the correct
answer padded with further true sentences, and a wrong answer carrying a
citation-like prefix. Three comparisons are built from those four answers, and
each one runs in both orders:

- **correctness** pits the correct answer against the length-matched wrong
  answer, so length is not the confound.
- **verbosity** pits the correct answer against the same correct answer padded
  with true detail, so both answers are right and anything past a coin flip is
  a preference for length.
- **authority** pits the correct answer against a wrong answer with a
  citation-like prefix, so the citation is the only difference between a
  persuasive answer and a right one.

Every item is asked all three comparisons with the correct answer first, then
again with the answers swapped: 600 comparisons per pass, 1,200 calls across
two passes. The judge is asked for exactly one word, `A` or `B`; any other reply
is recorded as unparsed rather than guessed at, and all 1,200 replies parsed.

The judge is never told which answer is correct. It sees the question, the two
answers in order, and a request for one letter.

## Rates by comparison

| comparison | correct answer preferred | when first | when second | position gap | first position rate | swap agreement |
| --- | --- | --- | --- | --- | --- | --- |
| correctness | 73.0% (292 of 400) | 46.0% (92 of 200) | 100.0% (200 of 200) | -54.0 | 23.0% (92 of 400) | 46.0% (92 of 200) |
| verbosity | 57.5% (230 of 400) | 28.5% (57 of 200) | 86.5% (173 of 200) | -58.0 | 21.0% (84 of 400) | 31.0% (62 of 200) |
| authority | 53.8% (215 of 400) | 7.5% (15 of 200) | 100.0% (200 of 200) | -92.5 | 3.8% (15 of 400) | 7.5% (15 of 200) |

The position gap is the win rate of the correct answer when it sits in the
second slot minus its win rate when it sits in the first. A judge that reads the
answers rather than the order sits near zero. All three gaps are negative and
none is small, so the answer in the second slot won more often than the same
answer in the first.

Swap agreement pairs the two orderings of the same comparison, within the same
kind and the same pass, and counts how often they named the same answer. There
are 200 such pairs per kind across the two passes. The first position rate is
the share of decided calls that named whichever answer came first, which is the
share a position-only judge would sit at.

## What each comparison shows

**Correctness.** The correct answer won 292 of 400 decided calls, and the split
by slot explains the shape of that figure: it won 46.0% of the calls where it
came first and 100.0% of the calls where it came second. Swap agreement was
46.0%, so both orderings named the same answer on 92 of the 200 pairs. This
should be the easiest comparison, since one answer is wrong and the two are
close in length, and it is the one where the model's consistency against length
is lowest.

**Verbosity.** With both answers factually correct, the longer one was
preferred 42.5% of the time, since the correct answer is the shorter one there.
The correct answer won 57.5% of calls: 28.5% when it came first and 86.5% when
it came second, a gap of -58.0 points, and both orderings agreed on 31.0% of
pairs. The preference for padding is real and it is the length control for
the authority comparison: any authority figure below it is the citation doing
work beyond length.

**Authority.** The wrong answer carrying the citation-like prefix won 185 of
400 calls, 46.3%. The split by slot is the sharpest number in the audit: the
correct answer won 7.5% of calls when it came first and 100.0% when it came
second, and swap agreement was 7.5%, meaning both orderings agreed on 15 of the
200 pairs. The gap of -92.5 points is close to the most the protocol can
measure. A citation-shaped prefix moved the verdict far more than padding did,
since verbosity left the correct answer above 57% and the prefix brought it back
to a coin flip.

## Position effect

| comparison | correct answer first | correct answer second |
| --- | --- | --- |
| correctness | 46.0% | 100.0% |
| verbosity | 28.5% | 86.5% |
| authority | 7.5% | 100.0% |

Two of the three comparisons reach 100.0% in the second slot. A judge reading the
answers would land near the same figure in both slots, so the pattern is position
settling the verdict rather than content settling it.

## Repeatability

Comparing pass 1 with pass 2 call by call, the judge repeated itself on 1,166 of
1,200 calls: 396 of 400 on correctness, 376 of 400 on verbosity and 394 of 400 on
authority. Sampling is deterministic at temperature 0 with seed 42, so this
measures the protocol rather than sampling noise: the second pass reproduced the
first on 1,166 calls and differed on 34: 24 verbosity, 6 authority and 4
correctness.

## Calls, latency and tokens

| comparison | calls | decided | ties | mean latency | prompt tokens | completion tokens |
| --- | --- | --- | --- | --- | --- | --- |
| correctness | 400 | 400 | 0 | 2333 ms | 39948 | 800 |
| verbosity | 400 | 400 | 0 | 2877 ms | 53564 | 800 |
| authority | 400 | 400 | 0 | 2097 ms | 44388 | 800 |

The prompt and completion token columns are totals across the calls of that
comparison. Verbosity is the slowest comparison at 2877 ms per call and carries
the largest prompt token count, 53,564 against 39,948 for correctness and 44,388
for authority, which is the padded answer lengthening the prompt: a mean of
133.9 prompt tokens per verbosity call against 99.9 and 111.0 on the other two.
Every call completed within 2 completion tokens, since a verdict is one letter.
No call returned a tie and no reply failed to parse.

## How the audit works

1. **Build trials.** `build_trials` expands each item into six comparisons: three
   kinds, each with the correct answer in position A and in position B. The order
   is fixed at kind, then item, then the swap, so a pass is reproducible.
2. **Ask.** `OllamaJudge` posts the question and the two answers in order and
   asks for a single letter. `parse_choice` accepts a bare `A` or `B`, a letter
   with a trailing period, or a short phrase holding one letter, and returns
   nothing for anything else, so a chatty reply is recorded as unparsed rather
   than guessed.
3. **Summarise.** `summarize` reads only recorded decisions. It counts decided
   calls, ties and unparsed replies, splits the gold preference rate by which
   slot the correct answer occupied, computes the position gap, the first
   position rate and swap agreement, and averages latency and token counts.
4. **Record.** `build_record` writes the raw calls, one summary per pass and the
   notes describing the run, so any number can be recomputed from the stored
   calls without asking the model again. `run_audit.py --recount` does exactly
   that.

Swap agreement pairs the two orderings of the same item within the same kind and
the same pass and counts how often they named the same answer. It works over any
number of passes rather than assuming two results per item.

## Layout

```
data/items.json     100 factual items with four answers each
src/llmjudge/
  data.py           item loading
  judge.py          Ollama client, choice parsing, scripted judges
  audit.py          trial construction, execution, the numbers
  metrics.py        record building and writing
scripts/
  run_audit.py      the measured run, plus --recount
  smoke_audit.py    protocol self-check against four scripted judges
  make_page.py      regenerates docs/ from results/audit.json
tests/              19 unit tests, 2 integration tests
results/audit.json  the measured run: 1200 calls, two passes
docs/               GitHub Pages report

```

## Running it

```bash
pip install -r requirements.txt
ollama serve                                # or the Ollama desktop app
ollama pull qwen2.5:1.5b

python scripts/smoke_audit.py               # seconds, no model needed
python scripts/run_audit.py --model qwen2.5:1.5b --results results/audit.json
python scripts/make_page.py
```

The measured run takes about 49 minutes on a machine with 8 GB of RAM, at 1,200
calls averaging 2.5 seconds each. Keeping `OMP_NUM_THREADS=2` set avoids memory
pressure while the model is loaded. The run is split from the page generation so
the numbers can be refreshed without re-asking the model: `run_audit.py
--recount results/audit.json` recomputes every figure from the stored calls.

The measurements were taken on Python 3.13 with requests, and `qwen2.5:1.5b`
served by Ollama on 127.0.0.1:11434 at temperature 0 with seed 42.

## Checks

```
pytest tests/unit -q         19 passed
pytest tests/integration -q  2 passed
ruff check .                 clean
python scripts/smoke_audit.py  49 checks pass
```

The unit tests run without the model: four scripted judges stand in for the real
one, including two that follow position, one that follows length and one that
follows the answer, and the protocol is checked against the signals each of them
should produce. The integration tests write a record and read it back. Both
families run in GitHub Actions on every push to `main`, and the smoke job runs
the protocol self-check.

## Limits worth stating

- 100 items is a modest set. The per-item counts behind the rates are 200 per
  kind per slot and 100 per kind per pass, so one item moving in one pass
  changes a by-slot rate by 0.5 points and a pooled rate by 0.25 points, and
  the percentages are quoted to one decimal to make that visible.
- The items are factual questions with unambiguous answers. A judge on tasks
  where both answers are defensible would show a different profile.
- The audit measures one model at one temperature. Nothing here predicts how a
  larger model, or a different sampling setting, would behave.
- Swap agreement counts a pair as agreeing when both orderings named the same
  answer, whether that answer was the correct one or not. It measures  consistency, not correctness.
- The judge is asked for one letter and a reply it cannot parse is discarded, so
  the rates describe calls that answered in the expected form. In this run that
  was all 1,200 calls.

The report is generated into `docs/` and the Pages workflow publishes it on every push.
`scripts/check_pages.py` requests that URL when the report is regenerated and records
the status it answers next to the measured numbers, as `pages_status` in
`results/audit.json`. It answered HTTP 200 at 2026-11-07T20:29:02Z, so the
published page is being served and the committed copy of the report carries
the same measured numbers:
<https://bakkarranna.github.io/llm-judge-bias-audit/>
