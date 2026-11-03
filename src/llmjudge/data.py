"""The answer-pair items the judge is graded on."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Item:
    """One question with four answers that probe different biases."""

    id: str
    topic: str
    question: str
    gold: str
    pad: str
    wrong: str
    authority: str

    def answer(self, field: str) -> str:
        """Return one of the answer fields by name."""

        return getattr(self, field)


def load_items(path: str | Path) -> list[Item]:
    """Load the item file, which must be a JSON list of objects."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("id", "topic", "question", "gold", "pad", "wrong", "authority")
    items = []
    for index, record in enumerate(raw):
        missing = [key for key in required if key not in record]
        if missing:
            raise ValueError(f"item {index} is missing fields: {', '.join(missing)}")
        items.append(Item(**{key: record[key] for key in required}))
    return items


def item_ids(items: list[Item]) -> list[str]:
    """All item ids, in file order."""

    return [item.id for item in items]
