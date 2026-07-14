from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FILENAME_FORBIDDEN_CHARS = r'[\\/:*?"<>|]'
PACKAGE_SECTIONS = {
    "title": "推荐标题",
    "body": "正文",
    "hashtags": "话题",
}


@dataclass(frozen=True)
class PublishPackage:
    topic_id: str
    topic: str
    category: str
    audience: str
    angle: str
    titles: list[str]
    recommended_title: str
    cover_texts: list[str]
    body: str
    hashtags: list[str]
    image_suggestions: list[str]
    image_profile: str
    image_prompts: list[str]
    image_paths: list[str]
    publish_time_suggestion: str
    compliance_check: dict[str, Any]
    raw: dict[str, Any]
    review_status: str = "draft"
    publish_status: str = "draft"


def safe_filename(value: str) -> str:
    """Return a filesystem-safe name while keeping readable Chinese titles."""
    cleaned = re.sub(FILENAME_FORBIDDEN_CHARS, "_", value).strip()
    return cleaned or "untitled"


def package_from_result(topic: Any, result: dict[str, Any]) -> PublishPackage:
    """Convert Claude JSON output into a normalized publish package."""
    return PublishPackage(
        topic_id=topic.id,
        topic=topic.topic,
        category=topic.category,
        audience=topic.audience,
        angle=topic.angle,
        titles=_as_list(result.get("titles")),
        recommended_title=str(result.get("recommended_title", "")).strip(),
        cover_texts=_as_list(result.get("cover_texts")),
        body=str(result.get("body", "")).strip(),
        hashtags=[tag.lstrip("#") for tag in _as_list(result.get("hashtags"))],
        image_suggestions=_as_list(result.get("image_suggestions")),
        image_profile=str(result.get("image_profile", "")).strip(),
        image_prompts=_as_list(result.get("image_prompts")) or _as_list(result.get("image_suggestions")),
        image_paths=_as_list(result.get("image_paths")),
        publish_time_suggestion=str(result.get("publish_time_suggestion", "")).strip(),
        compliance_check=dict(result.get("compliance_check") or {}),
        raw=result,
    )


def write_publish_package(package: PublishPackage, output_dir: Path) -> Path:
    """Write a Markdown package for humans plus raw JSON for later automation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = safe_filename(f"{package.topic_id}_{package.topic}")
    markdown_path = output_dir / f"{base_name}.md"
    json_path = output_dir / f"{base_name}.json"

    markdown_path.write_text(render_package_markdown(package), encoding="utf-8")
    json_path.write_text(json.dumps(package_to_dict(package), ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path


def package_to_dict(package: PublishPackage) -> dict[str, Any]:
    """Convert a package to the machine-readable JSON used by automation."""
    data = dict(package.raw)
    data.update(
        {
            "topic_id": package.topic_id,
            "topic": package.topic,
            "category": package.category,
            "audience": package.audience,
            "angle": package.angle,
            "titles": package.titles,
            "recommended_title": package.recommended_title,
            "cover_texts": package.cover_texts,
            "body": package.body,
            "hashtags": package.hashtags,
            "image_suggestions": package.image_suggestions,
            "image_profile": package.image_profile,
            "image_prompts": package.image_prompts,
            "image_paths": package.image_paths,
            "publish_time_suggestion": package.publish_time_suggestion,
            "compliance_check": package.compliance_check,
            "review_status": package.review_status,
            "publish_status": package.publish_status,
        }
    )
    return data


def render_package_markdown(package: PublishPackage) -> str:
    """Render a publish package that can be reviewed and copied manually."""
    titles = "\n".join(f"{index}. {title}" for index, title in enumerate(package.titles, 1))
    cover_texts = "\n\n".join(package.cover_texts)
    image_suggestions = "\n".join(
        f"{index}. {suggestion}"
        for index, suggestion in enumerate(package.image_suggestions, 1)
    )
    hashtags = " ".join(f"#{tag.lstrip('#')}" for tag in package.hashtags)
    compliance = package.compliance_check
    risk_level = compliance.get("risk_level", "unknown")
    risks = _format_list(compliance.get("risks", []))
    rewrite_suggestions = _format_list(compliance.get("rewrite_suggestions", []))
    research_section = _render_research_summary(package.raw.get("research_brief") if package.raw else None)

    return f"""# 发布包：{package.topic}

## 基础信息
- ID: {package.topic_id}
- 分类: {package.category}
- 目标用户: {package.audience}
- 角度: {package.angle}
{research_section}
## 推荐标题
{package.recommended_title}

## 备选标题
{titles}

## 封面文案
{cover_texts}

## 正文
{package.body}

## 话题
{hashtags}

## 配图建议
{image_suggestions}

## 图片提示词模板
{package.image_profile or "手写 prompts"}

## 发布时间建议
{package.publish_time_suggestion}

## 合规检查
风险等级：{risk_level}

风险点：
{risks}

修改建议：
{rewrite_suggestions}

## 人工审核区
- 审核状态：draft
- 是否需要重写：
- 发布日期：
- 小红书链接：
- 备注：
"""


def _render_research_summary(brief: Any) -> str:
    """Render a short research summary section when a brief is present."""
    if not isinstance(brief, dict):
        return ""
    query = str(brief.get("query_summary") or "").strip() or "（未填写）"
    facts = brief.get("facts") if isinstance(brief.get("facts"), list) else []
    viewpoints = brief.get("viewpoints") if isinstance(brief.get("viewpoints"), list) else []
    return f"""
## 联网资料摘要
- 检索意图：{query}
- 事实锚点：{len(facts)} 条
- 外部观点：{len(viewpoints)} 条

"""


def extract_package_fields(markdown: str) -> dict[str, str]:
    """Extract title, body, and hashtags for a local copy helper."""
    return {
        field: _extract_section(markdown, heading)
        for field, heading in PACKAGE_SECTIONS.items()
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _format_list(values: Any) -> str:
    items = _as_list(values)
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items)


def _extract_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*\n(?P<content>.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group("content").strip() if match else ""
