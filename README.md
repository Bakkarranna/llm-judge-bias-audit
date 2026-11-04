# LLM judge bias audit

[![CI](https://github.com/Bakkarranna/llm-judge-bias-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/Bakkarranna/llm-judge-bias-audit/actions/workflows/ci.yml)
[![Pages](https://github.com/Bakkarranna/llm-judge-bias-audit/actions/workflows/pages.yml/badge.svg)](https://github.com/Bakkarranna/llm-judge-bias-audit/actions/workflows/pages.yml)

A measured audit of position bias in a pairwise judge built on a small
language model. The judge is given a factual question and two answers and is
asked to name the better one with a single letter. The audit measures how
often the answer's slot, rather than its content, decides the verdict, and how
often the judge contradicts itself when the two answers swap places.

Every comparison ran in both orders over 24 factual items, twice, and the judge
preferred the correct answer 66 of 96 times on correctness, 60 of 96 on
verbosity and 50 of 96 on authority. Its verdicts were far less consistent than
those rates suggest: the same comparison in the opposite order agreed only
37.5%, 33.3% and 4.2% of the time. Every number in this report was measured on
one machine and written to `results/audit.json` by the scripts in `scripts/`.
Nothing here is estimated.

The model is `qwen2.5:1.5b` served by Ollama on 127.0.0.1:11434 at temperature
0 with seed 42. The judge label in the record is `local-ollama`. The full run
is 288 model calls over 821 seconds.

## What was measured

`data/items.json` holds 24 factual items, each with a question and four
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
again with the answers swapped: 144 comparisons per pass, 288 calls across two
passes. The judge is asked for exactly one word, `A` or `B`; any other reply is
recorded as unparsed rather than guessed at, and all 288 replies parsed.

The judge is never told which answer is correct. It sees the question, the two
answers in order, and a request for one letter.

## Rates by comparison

| comparison | correct answer preferred | when first | when second | position gap | first position rate | swap agreement |
| --- | --- | --- | --- | --- | --- | --- |
| correctness | 68.8% (66 of 96) | 37.5% | 100.0% | -62.5% | 18.8% | 37.5% |
| verbosity | 62.5% (60 of 96) | 50.0% | 75.0% | -25.0% | 37.5% | 33.3% |
| authority | 52.1% (50 of 96) | 4.2% | 100.0% | -95.8% | 2.1% | 4.2% |

The position gap is the win rate of the correct answer when it sits in the
second slot minus its win rate when it sits in the first. A judge that reads the
answers rather than the order sits near zero. All three gaps are negative and
none is small, so the answer in the second slot won more often than the same
answer in the first.

Swap agreement is the share of items where both orderings of a comparison
named the same answer. The first position rate is the share of decided calls
that named whichever answer came first, which is the share a position-only judge
would sit at.

## What each comparison shows

**Correctness.** The correct answer won 66 of 96 decided calls, and the split by
slot explains the shape of that figure: it won 37.5% of the calls where it came
first and 100.0% of the calls where it came second. Swap agreement was 37.5%, so
both orderings named the same answer on 9 of the 24 items. This should be the
easiest comparison, since one answer is wrong and the two are close in length,
and it is the one where the model's consistency against length is lowest.

**Verbosity.** With both answers factually correct, the longer one was preferred
62.5% of the time. The correct answer won 50.0% of calls when it came first and
75.0% when it came second, a gap of -25.0%, and both orderings agreed on 33.3%
of items. The preference for padding is real and it is the length control for
the authority comparison: any authority figure below it is the citation doing
work beyond length.

**Authority.** The wrong answer carrying the citation-like prefix won 46 of 96
calls, 47.9%. The split by slot is the sharpest number in the audit: the correct
answer won 4.2% of calls when it came first and 100.0% when it came second, and
swap agreement was 4.2%, meaning both orderings agreed on 1 of 24 items. The gap
of -95.8% is close to the most the protocol can measure. A citation-shaped
prefix moved the verdict far more than padding did, since verbosity left the
correct answer above 60% and the prefix dropped it to a coin flip.
END_A

## Position effect

| comparison | correct answer first | correct answer second |
| --- | --- | --- |
| correctness | 37.5% | 100.0% |
| verbosity | 50.0% | 75.0% |
| authority | 4.2% | 100.0% |

Two of the three comparisons reach 100.0% in the second slot. A judge reading the
answers would land near the same figure in both slots, so the pattern is position
settling the verdict rather than content settling it.

## Repeatability

Comparing pass 1 with pass 2 item by item, the judge named the same answer on 24
of 24 items in every comparison kind. Sampling is deterministic at temperature 0
with seed 42, so this measures the protocol rather than sampling noise: the
second pass reproduced the first exactly.

## Calls, latency and tokens

| comparison | calls | decided | ties | mean latency | prompt tokens | completion tokens |
| --- | --- | --- | --- | --- | --- | --- |
| correctness | 96 | 96 | 0 | 2198 ms | 9380 | 192 |
| verbosity | 96 | 96 | 0 | 3183 ms | 12808 | 192 |
| authority | 96 | 96 | 0 | 2203 ms | 10336 | 192 |

Verbosity is the slowest comparison at 3183 ms per call and carries the largest
prompt token count, 12808 against 9380 for correctness and 10336 for authority,
which is the padded answer lengthening the prompt. Every call completed within
192 completion tokens, since a verdict is one letter. No call returned a tie and
no reply failed to parse.
END_B

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
counts how often they named the same answer. It works over any number of passes
rather than assuming two results per item.
END_C

## Layout

```
data/items.json     24 factual items with four answers each
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
results/audit.json  the measured run: 288 calls, two passes
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

The measured run takes about 14 minutes on a machine with 8 GB of RAM, at 288
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
python scripts/smoke_audit.py  8 checks pass
```

The unit tests run without the model: four scripted judges stand in for the real
one, including two that follow position, one that follows length and one that
follows the answer, and the protocol is checked against the signals each of them
should produce. The integration tests write a record and read it back. Both
families run in GitHub Actions on every push to `main`, and the smoke job runs
the protocol self-check.

## Limits worth stating

- 24 items is a small set. The per-item counts behind the rates are 24, so one
  item moving changes a rate by about four points and the percentages are quoted
  to one decimal to make that visible.
- The items are factual questions with unambiguous answers. A judge on tasks
  where both answers are defensible would show a different profile.
- The audit measures one model at one temperature. Nothing here predicts how a
  larger model, or a different sampling setting, would behave.
- Swap agreement counts an item as agreeing when both orderings named the same
  answer, whether that answer was the correct one or not. It measures
  consistency, not correctness.
- The judge is asked for one letter and a reply it cannot parse is discarded, so
  the rates describe calls that answered in the expected form. In this run that
  was all 288 calls.

The report is published as GitHub Pages from `docs/`:
<https://bakkarranna.github.io/llm-judge-bias-audit/>
