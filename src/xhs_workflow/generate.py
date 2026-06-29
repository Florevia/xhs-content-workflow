from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from xhs_workflow.claude_client import ClaudeClient
from xhs_workflow.image_prompt_profiles import build_image_prompts, resolve_image_profile_name
from xhs_workflow.packages import package_from_result, write_publish_package
from xhs_workflow.prompts import read_text, render_prompt
from xhs_workflow.topics import Topic, load_topics


SYSTEM_PROMPT = "你是一个小红书内容策略专家和合规审稿人。请严格按用户要求输出 JSON，不要输出多余解释。"


def build_generation_prompt(root: Path, topic: Mapping[str, Any] | Topic) -> str:
    """Build the note-generation prompt from local docs and one topic row."""
    template = read_text(root / "prompts" / "generate_note.md")
    values = {
        "brand_guide": read_text(root / "docs" / "brand_guide.md"),
        "content_pillars": read_text(root / "docs" / "content_pillars.md"),
        "compliance_rules": read_text(root / "docs" / "compliance_rules.md"),
        "topic": _get(topic, "topic"),
        "category": _get(topic, "category"),
        "audience": _get(topic, "audience"),
        "angle": _get(topic, "angle"),
    }
    return render_prompt(template, values)


def generate_publish_packages(root: Path, status: str = "draft") -> list[Path]:
    """Generate publish packages for topics in the requested status."""
    topics = load_topics(root / "data" / "topics.csv", status=status)
    client = ClaudeClient(root)
    output_paths: list[Path] = []

    for topic in topics:
        prompt = build_generation_prompt(root, topic)
        result = client.complete_json(prompt, SYSTEM_PROMPT)
        result = finalize_generation_result(root, topic, result)
        package = package_from_result(topic, result)
        output_paths.append(write_publish_package(package, root / "output" / "publish_packages"))

    return output_paths


def _get(topic: Mapping[str, Any] | Topic, key: str) -> Any:
    if isinstance(topic, Mapping):
        return topic.get(key, "")
    return getattr(topic, key)


def finalize_generation_result(
    root: Path,
    topic: Mapping[str, Any] | Topic,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Fill deterministic image prompts when Claude returns only profile intent or suggestions."""
    finalized = dict(result)
    manual_prompts = _as_list(finalized.get("image_prompts"))
    if manual_prompts:
        finalized["image_prompts"] = manual_prompts
        return finalized

    profile_name = resolve_image_profile_name(
        root / "config" / "image_prompt_profiles.json",
        category=str(_get(topic, "category")),
        audience=str(_get(topic, "audience")),
        angle=str(_get(topic, "angle")),
        topic=str(_get(topic, "topic")),
        requested_profile=str(finalized.get("image_profile", "")),
    )
    finalized["image_profile"] = profile_name
    finalized["image_prompts"] = build_image_prompts(
        config_path=root / "config" / "image_prompt_profiles.json",
        topic=str(_get(topic, "topic")),
        category=str(_get(topic, "category")),
        audience=str(_get(topic, "audience")),
        angle=str(_get(topic, "angle")),
        recommended_title=str(finalized.get("recommended_title", "")).strip(),
        cover_texts=_as_list(finalized.get("cover_texts")),
        body=str(finalized.get("body", "")).strip(),
        image_suggestions=_as_list(finalized.get("image_suggestions")),
        image_profile=profile_name,
    )
    return finalized


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []
