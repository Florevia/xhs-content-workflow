from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TOPIC_STATUS = "draft"


@dataclass(frozen=True)
class Topic:
    id: str
    topic: str
    category: str
    audience: str
    angle: str
    status: str


def load_topics(path: Path, status: str = DEFAULT_TOPIC_STATUS) -> list[Topic]:
    """Load topic rows with the requested review status."""
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = [row for row in reader if row.get("status", "").strip() == status]

    return [
        Topic(
            id=row.get("id", "").strip(),
            topic=row.get("topic", "").strip(),
            category=row.get("category", "").strip(),
            audience=row.get("audience", "").strip(),
            angle=row.get("angle", "").strip(),
            status=row.get("status", "").strip(),
        )
        for row in rows
    ]
