from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from xhs_workflow.claude_client import ClaudeClient
from xhs_workflow.prompts import read_text, render_prompt
from xhs_workflow.topics import Topic


RESEARCH_SYSTEM_PROMPT = (
    "你是小红书内容调研助手。必须使用 web_search 联网检索公开资料，"
    "禁止仅凭训练记忆编造事实或观点。只输出 JSON，不要多余解释。"
)

SKIP_RESEARCH_ENV = "XHS_SKIP_RESEARCH"
SKIP_RESEARCH_NOTE = "已跳过联网检索(XHS_SKIP_RESEARCH)"
MISSING_RESEARCH_NOTE = "未联网核验"


class ResearchError(RuntimeError):
    """Raised when web research fails or returns an invalid brief."""


def build_research_prompt(root: Path, topic: Mapping[str, Any] | Topic) -> str:
    """Build the research prompt from the research template and one topic."""
    template = read_text(root / "prompts" / "research_note.md")
    values = {
        "topic": _get(topic, "topic"),
        "category": _get(topic, "category"),
        "audience": _get(topic, "audience"),
        "angle": _get(topic, "angle"),
        "today": date.today().isoformat(),
    }
    return render_prompt(template, values)


def validate_research_brief(payload: Any) -> dict[str, Any]:
    """Normalize and validate a research_brief JSON object."""
    if not isinstance(payload, dict):
        raise ResearchError("research_brief 必须是 JSON 对象")
    if "facts" not in payload or "viewpoints" not in payload:
        raise ResearchError("research_brief 缺少 facts 或 viewpoints 字段")

    return {
        "query_summary": str(payload.get("query_summary") or "").strip(),
        "as_of": str(payload.get("as_of") or date.today().isoformat()).strip(),
        "facts": _as_dict_list(payload.get("facts")),
        "viewpoints": _as_dict_list(payload.get("viewpoints")),
        "gaps": _as_str_list(payload.get("gaps")),
        "risk_notes": _as_str_list(payload.get("risk_notes")),
    }


def format_research_brief_for_prompt(brief: Mapping[str, Any] | None) -> str:
    """Serialize a research brief for injection into the generation prompt."""
    if not brief:
        return "（无联网资料：未提供 research_brief）"
    return json.dumps(dict(brief), ensure_ascii=False, indent=2)


def research_topic(
    root: Path,
    topic: Mapping[str, Any] | Topic,
    client: ClaudeClient | Any | None = None,
) -> dict[str, Any] | None:
    """Run Claude web search and return a validated research_brief, or None when skipped."""
    if os.getenv(SKIP_RESEARCH_ENV, "").strip() == "1":
        return None

    active_client = client or ClaudeClient(root)
    prompt = build_research_prompt(root, topic)
    try:
        raw = active_client.complete_json_with_web_search(prompt, RESEARCH_SYSTEM_PROMPT)
    except ResearchError:
        raise
    except Exception as error:
        raise ResearchError(f"联网检索失败: {error}") from error

    try:
        return validate_research_brief(raw)
    except ResearchError:
        raise
    except Exception as error:
        raise ResearchError(f"research_brief 校验失败: {error}") from error


def _get(topic: Mapping[str, Any] | Topic, key: str) -> Any:
    if isinstance(topic, Mapping):
        return topic.get(key, "")
    return getattr(topic, key)


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
