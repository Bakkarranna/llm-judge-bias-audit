"""The judge: a strict pairwise preference reader.

The protocol asks the judge to compare two answers and reply with exactly one
word. Every reply is recorded raw, then parsed. A reply the parser cannot read
counts as a failed call rather than being guessed at, because a judge that
cannot follow the output contract is a finding in itself.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

JUDGE_TEMPLATE = (
    "You are grading two answers to the same question. "
    "Decide which answer is better and reply with exactly one word: A or B.\n\n"
    "Question: {question}\n\n"
    "Answer A: {first}\n\n"
    "Answer B: {second}\n\n"
    "Your reply (A or B):"
)

VALID_CHOICES = ("A", "B", "TIE")


def parse_choice(raw: str) -> str | None:
    """Read a judge reply as A, B, TIE or None.

    The audit measures how often the model answers in the requested format, so
    the parser accepts ordinary variation ("answer a", "A.", " b ") but rejects
    anything that carries no single unambiguous choice.
    """

    text = " ".join(str(raw).strip().lower().split())
    if not text:
        return None
    if text in {"a", "b", "tie"}:
        return text.upper()
    if text.startswith("answer "):
        remainder = text[len("answer ") :].strip(" .:\t")
        if remainder in {"a", "b", "tie"}:
            return remainder.upper()
    if len(text) == 2 and text[1] == "." and text[0] in "ab":
        return text[0].upper()
    if text.startswith(("choice ", "option ")):
        remainder = text.split(" ", 1)[1].strip(" .:\t")
        if remainder in {"a", "b", "tie"}:
            return remainder.upper()
    return None


@dataclass(frozen=True)
class Decision:
    """One judge call, exactly as it came back."""

    choice: str | None
    raw: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    model: str

    @property
    def parsed(self) -> bool:
        """Whether the reply carried a readable choice."""

        return self.choice in VALID_CHOICES


class Judge:
    """The interface the audit measures."""

    policy_aware = False
    """True when the judge may be told which side is correct.

    Only scripted judges set this; a real model is never given the answer.
    """

    def decide(
        self,
        question: str,
        first: str,
        second: str,
        *,
        first_is_correct: bool | None = None,
    ) -> Decision:
        """Compare two answers and return the decision.

        ``first_is_correct`` tells a scripted judge which side holds the
        correct answer. A real model is never given that information.
        """

        raise NotImplementedError


class OllamaJudge(Judge):
    """A local Ollama model used as the judge."""

    def __init__(
        self,
        model: str = "qwen2.5:1.5b",
        url: str = "http://127.0.0.1:11434",
        timeout_s: float = 90.0,
    ) -> None:
        self.model = model
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s

    def decide(
        self,
        question: str,
        first: str,
        second: str,
        *,
        first_is_correct: bool | None = None,
    ) -> Decision:
        prompt = JUDGE_TEMPLATE.format(question=question, first=first, second=second)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "seed": 42},
        }
        response = requests.post(f"{self.url}/api/generate", json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        body = response.json()
        raw = str(body.get("response", "")).strip()
        return Decision(
            choice=parse_choice(raw),
            raw=raw,
            latency_ms=float(body.get("total_duration", 0)) / 1e6,
            prompt_tokens=int(body.get("prompt_eval_count", 0)),
            completion_tokens=int(body.get("eval_count", 0)),
            model=self.model,
        )

    def available(self) -> bool:
        """Whether the local server answers, so a caller can stop early."""

        try:
            response = requests.get(f"{self.url}/api/tags", timeout=5.0)
            response.raise_for_status()
        except requests.RequestException:
            return False
        return True


class ScriptedJudge(Judge):
    """A judge with a fixed policy, used to test the audit itself.

    Policies:

    ``first``
        Always pick the first answer, which is pure position bias.
    ``second``
        Always pick the second answer.
    ``longer``
        Pick the longer answer; equal lengths fall back to the answer that sorts
        first, so the choice never depends on position. This is verbosity bias.
    ``correct``
        Pick whichever answer is correct: a judge with no bias.
    """

    def __init__(self, policy: str, model: str = "scripted") -> None:
        if policy not in {"first", "second", "longer", "correct"}:
            raise ValueError(f"unknown policy: {policy}")
        self.policy = policy
        self.model = model
        self.policy_aware = True

    def decide(
        self,
        question: str,
        first: str,
        second: str,
        *,
        first_is_correct: bool | None = None,
    ) -> Decision:
        if self.policy == "first":
            choice = "A"
        elif self.policy == "second":
            choice = "B"
        elif self.policy == "longer":
            # Equal lengths fall back to the answer that sorts first, so the
            # policy depends on the answers alone and never on their position.
            if len(second) > len(first):
                choice = "B"
            elif len(first) > len(second):
                choice = "A"
            else:
                choice = "A" if first <= second else "B"
        else:
            if first_is_correct is None:
                raise ValueError("the correct policy needs first_is_correct")
            choice = "A" if first_is_correct else "B"
        return Decision(
            choice=choice,
            raw=choice,
            latency_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            model=self.model,
        )
