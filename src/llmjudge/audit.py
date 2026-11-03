"""The audit protocol and its numbers.

Three tests run over the same items, each twice: once with the correct answer
in position A and once with the answers swapped. The swap is what makes the
numbers interpretable, because a preference that follows the answer is
discrimination while a preference that follows the position is position bias.

``correctness``
    The correct answer against a length-matched wrong answer. The two answers
    are close in length by construction, so brevity is not the confound.
``verbosity``
    The correct answer against the same correct answer padded with extra true
    sentences. Both answers are right, so anything beyond a coin flip is a
    preference for length.
``authority``
    The correct answer against a wrong answer carrying a citation-like prefix.
    The padded answer is the length control: if the judge picks the cited
    answer more often than it picks the padded one, the citation itself is
    doing work beyond length.

Every number a report quotes comes from :func:`summarize`, which reads only
recorded decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import Item
from .judge import Decision, Judge

KINDS = ("correctness", "verbosity", "authority")

COMPARISON_FIELD = {
    "correctness": "wrong",
    "verbosity": "pad",
    "authority": "authority",
}

DECIDED = {"A", "B"}


@dataclass(frozen=True)
class Trial:
    """One comparison: a question, two answers in order, and the label."""

    kind: str
    item_id: str
    question: str
    first: str
    second: str
    gold_first: bool


def build_trials(items: list[Item], kinds: tuple[str, ...] = KINDS) -> list[Trial]:
    """Every comparison, in a fixed order: kind, then item, then the swap."""

    trials: list[Trial] = []
    for kind in kinds:
        field = COMPARISON_FIELD[kind]
        for item in items:
            comparison = item.answer(field)
            trials.append(
                Trial(
                    kind=kind,
                    item_id=item.id,
                    question=item.question,
                    first=item.gold,
                    second=comparison,
                    gold_first=True,
                )
            )
            trials.append(
                Trial(
                    kind=kind,
                    item_id=item.id,
                    question=item.question,
                    first=comparison,
                    second=item.gold,
                    gold_first=False,
                )
            )
    return trials


@dataclass(frozen=True)
class TrialResult:
    """A trial plus the decision the judge returned for it."""

    trial: Trial
    choice: str | None
    raw: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int

    def key(self) -> tuple[str, str, bool]:
        """Identify this comparison, ignoring which pass it came from."""

        return (self.trial.kind, self.trial.item_id, self.trial.gold_first)


def choose(judge: Judge, trial: Trial) -> Decision:
    """Ask the judge about one comparison.

    A scripted judge learns which side holds the correct answer; a real model
    never does.
    """

    return judge.decide(
        trial.question,
        trial.first,
        trial.second,
        first_is_correct=trial.gold_first if judge.policy_aware else None,
    )


def run_trials(judge: Judge, trials: list[Trial]) -> list[TrialResult]:
    """Run every trial once and record the decision exactly as it came back."""

    results = []
    for trial in trials:
        decision = choose(judge, trial)
        results.append(
            TrialResult(
                trial=trial,
                choice=decision.choice,
                raw=decision.raw,
                latency_ms=decision.latency_ms,
                prompt_tokens=decision.prompt_tokens,
                completion_tokens=decision.completion_tokens,
            )
        )
    return results


def label(result: TrialResult) -> str | None:
    """Which answer the judge preferred, independent of position.

    ``gold`` is the correct answer, ``other`` the comparison answer, ``tie`` a
    refusal, and ``None`` a reply the parser could not read. Labels are
    position-free, so the two orderings of an item can be compared directly.
    """

    if result.choice == "TIE":
        return "tie"
    if result.choice not in DECIDED:
        return None
    return "gold" if (result.choice == "A") == result.trial.gold_first else "other"


@dataclass(frozen=True)
class KindSummary:
    """Measured numbers for one test."""

    kind: str
    calls: int
    parsed: int
    ties: int
    decided: int
    gold_choices: int
    gold_preference_rate: float
    gold_first_rate: float
    gold_second_rate: float
    position_gap: float
    first_position_rate: float
    swap_agreement: float
    mean_latency_ms: float
    prompt_tokens: int
    completion_tokens: int

    def as_dict(self) -> dict:
        """The summary as plain numbers, ready to serialise."""

        return {
            "kind": self.kind,
            "calls": self.calls,
            "parsed": self.parsed,
            "ties": self.ties,
            "decided": self.decided,
            "gold_choices": self.gold_choices,
            "gold_preference_rate": round(self.gold_preference_rate, 4),
            "gold_preferred_when_first": round(self.gold_first_rate, 4),
            "gold_preferred_when_second": round(self.gold_second_rate, 4),
            "position_gap": round(self.position_gap, 4),
            "first_position_rate": round(self.first_position_rate, 4),
            "swap_agreement": round(self.swap_agreement, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def summarize(kind: str, results: list[TrialResult]) -> KindSummary:
    """Compute the reportable numbers for one test."""

    calls = len(results)
    parsed = sum(1 for result in results if result.choice in {"A", "B", "TIE"})
    ties = sum(1 for result in results if result.choice == "TIE")
    decided = [result for result in results if result.choice in DECIDED]

    gold_choices = sum(1 for result in decided if label(result) == "gold")

    when_first = [result for result in decided if result.trial.gold_first]
    when_second = [result for result in decided if not result.trial.gold_first]
    gold_first_rate = _rate(
        sum(1 for result in when_first if label(result) == "gold"), len(when_first)
    )
    gold_second_rate = _rate(
        sum(1 for result in when_second if label(result) == "gold"), len(when_second)
    )

    comparable: dict[str, list[str | None]] = {}
    for result in results:
        comparable.setdefault(result.trial.item_id, []).append(label(result))
    pairs = {item_id: marks for item_id, marks in comparable.items() if len(marks) == 2}
    agreeing = sum(1 for marks in pairs.values() if marks[0] == marks[1])

    return KindSummary(
        kind=kind,
        calls=calls,
        parsed=parsed,
        ties=ties,
        decided=len(decided),
        gold_choices=gold_choices,
        gold_preference_rate=_rate(gold_choices, len(decided)),
        gold_first_rate=gold_first_rate,
        gold_second_rate=gold_second_rate,
        position_gap=gold_first_rate - gold_second_rate,
        first_position_rate=_rate(
            sum(1 for result in decided if result.choice == "A"), len(decided)
        ),
        swap_agreement=_rate(agreeing, len(pairs)),
        mean_latency_ms=(
            sum(result.latency_ms for result in results) / calls if calls else 0.0
        ),
        prompt_tokens=sum(result.prompt_tokens for result in results),
        completion_tokens=sum(result.completion_tokens for result in results),
    )


def summarize_run(
    results: list[TrialResult], kinds: tuple[str, ...] = KINDS
) -> dict[str, KindSummary]:
    """Summarise every test in the run."""

    return {
        kind: summarize(kind, [result for result in results if result.trial.kind == kind])
        for kind in kinds
    }


def repeatability(first: list[TrialResult], second: list[TrialResult]) -> dict[str, float]:
    """How often the second pass made the same choice as the first.

    Compared per comparison rather than per test, because a judge that flips
    between passes cannot be trusted for a single pass.
    """

    earlier = {result.key(): result.choice for result in first}
    compared = [result for result in second if result.key() in earlier]
    agreeing = sum(1 for result in compared if earlier[result.key()] == result.choice)
    overall = _rate(agreeing, len(compared))

    by_kind: dict[str, float] = {}
    for kind in KINDS:
        same_kind = [result for result in compared if result.trial.kind == kind]
        agree = sum(1 for result in same_kind if earlier[result.key()] == result.choice)
        by_kind[kind] = _rate(agree, len(same_kind))
    return {"overall": overall, **by_kind}
