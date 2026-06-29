from __future__ import annotations

import json
from pathlib import Path

from xhs_workflow.claude_client import ClaudeClient
from xhs_workflow.prompts import read_text, render_prompt


SYSTEM_PROMPT = "你是小红书内容合规审核员。请严格输出 JSON，不要输出多余解释。"


def build_review_prompt(root: Path, note: str) -> str:
    """Build a compliance review prompt for one generated package."""
    template = read_text(root / "prompts" / "review_note.md")
    return render_prompt(template, {"note": note})


def review_package(root: Path, package_path: Path) -> Path:
    """Review one Markdown package and write a JSON review result next to it."""
    note = read_text(package_path)
    prompt = build_review_prompt(root, note)
    result = ClaudeClient(root).complete_json(prompt, SYSTEM_PROMPT)
    output_path = package_path.with_name(f"{package_path.stem}.review.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
