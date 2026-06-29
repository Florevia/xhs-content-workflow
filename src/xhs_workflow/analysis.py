from __future__ import annotations

import json
from pathlib import Path

from xhs_workflow.claude_client import ClaudeClient
from xhs_workflow.metrics import load_metrics, summarize_metrics
from xhs_workflow.prompts import read_text, render_prompt


SYSTEM_PROMPT = "你是小红书运营分析师。请根据数据给出具体、可执行的复盘结论。"


def render_metrics_summary(summary: dict[str, dict[str, object]]) -> str:
    """Render metrics summary as Markdown for quick human review."""
    lines = ["# 小红书数据复盘摘要", ""]
    for post_id, data in sorted(summary.items()):
        latest = data["latest"]
        rates = data["latest_rates"]
        lines.extend(
            [
                f"## 笔记 {post_id}",
                f"- 最新浏览：{latest['views']}",
                f"- 点赞率：{rates['like_rate']:.2%}",
                f"- 收藏率：{rates['save_rate']:.2%}",
                f"- 评论率：{rates['comment_rate']:.2%}",
                f"- 互动率：{rates['engagement_rate']:.2%}",
                "",
            ]
        )
    return "\n".join(lines)


def write_metrics_summary(root: Path) -> Path:
    """Read metrics.csv and write a Markdown summary."""
    rows = load_metrics(root / "data" / "metrics.csv")
    summary = summarize_metrics(rows)
    output_path = root / "output" / "metrics_summary.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_metrics_summary(summary), encoding="utf-8")
    return output_path


def analyze_metrics_with_claude(root: Path, package_path: Path) -> Path:
    """Ask Claude to analyze metrics and one post package."""
    metrics = json.dumps(
        summarize_metrics(load_metrics(root / "data" / "metrics.csv")),
        ensure_ascii=False,
        indent=2,
    )
    post = read_text(package_path)
    template = read_text(root / "prompts" / "analyze_metrics.md")
    prompt = render_prompt(template, {"metrics": metrics, "post": post})
    result = ClaudeClient(root).complete_json(prompt, SYSTEM_PROMPT)
    output_path = package_path.with_name(f"{package_path.stem}.analysis.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
