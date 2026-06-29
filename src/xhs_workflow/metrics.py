from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


METRIC_FIELDS = ("views", "likes", "saves", "comments", "shares", "follows")


def load_metrics(path: Path) -> list[dict[str, str]]:
    """Load manually maintained Xiaohongshu metrics."""
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def calculate_rates(row: dict[str, str | int]) -> dict[str, float]:
    """Calculate post performance rates from one metrics row."""
    views = _to_int(row.get("views", 0))
    if views <= 0:
        return {
            "like_rate": 0.0,
            "save_rate": 0.0,
            "comment_rate": 0.0,
            "follow_rate": 0.0,
            "engagement_rate": 0.0,
        }

    likes = _to_int(row.get("likes", 0))
    saves = _to_int(row.get("saves", 0))
    comments = _to_int(row.get("comments", 0))
    shares = _to_int(row.get("shares", 0))
    follows = _to_int(row.get("follows", 0))

    return {
        "like_rate": likes / views,
        "save_rate": saves / views,
        "comment_rate": comments / views,
        "follow_rate": follows / views,
        "engagement_rate": (likes + saves + comments + shares) / views,
    }


def summarize_metrics(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    """Group metrics rows by post and calculate latest/totals summaries."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("post_id", "")].append(row)

    summary: dict[str, dict[str, object]] = {}
    for post_id, post_rows in grouped.items():
        ordered = sorted(post_rows, key=lambda row: row.get("date", ""))
        latest = _normalize_metric_row(ordered[-1])
        totals = {
            field: sum(_to_int(row.get(field, 0)) for row in ordered)
            for field in METRIC_FIELDS
        }
        summary[post_id] = {
            "latest": latest,
            "totals": totals,
            "latest_rates": calculate_rates(latest),
        }
    return summary


def _normalize_metric_row(row: dict[str, str]) -> dict[str, str | int]:
    normalized: dict[str, str | int] = dict(row)
    for field in METRIC_FIELDS:
        normalized[field] = _to_int(row.get(field, 0))
    return normalized


def _to_int(value: str | int | object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
