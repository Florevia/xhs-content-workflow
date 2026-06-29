from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xhs_workflow.prompts import render_prompt

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "image_prompt_profiles.json"
MATCH_FIELD_NAMES = {
    "categories": "category",
    "audiences": "audience",
    "angles": "angle",
}


def load_image_prompt_profiles(config_path: Path | None = None) -> dict[str, Any]:
    """Load the image prompt profile configuration."""
    path = config_path or DEFAULT_CONFIG_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_image_profile_name(
    config_path: Path | None = None,
    *,
    category: str,
    audience: str,
    angle: str,
    topic: str = "",
    requested_profile: str = "",
) -> str:
    """Choose the most appropriate image prompt profile for a topic."""
    config = load_image_prompt_profiles(config_path)
    profiles = list(config.get("profiles") or [])
    if requested_profile and any(profile.get("name") == requested_profile for profile in profiles):
        return requested_profile

    best_name = str(config.get("fallback_profile", "")).strip()
    best_score = 0
    normalized_topic = _normalize_text(topic)

    for profile in profiles:
        score = 0
        match = profile.get("match") or {}
        for config_key, value_name in MATCH_FIELD_NAMES.items():
            values = {_normalize_text(item) for item in match.get(config_key, []) if str(item).strip()}
            current = _normalize_text(locals()[value_name])
            if current and current in values:
                score += 2

        keywords = {_normalize_text(item) for item in match.get("keywords", []) if str(item).strip()}
        if normalized_topic and any(keyword and keyword in normalized_topic for keyword in keywords):
            score += 1

        if score > best_score:
            best_score = score
            best_name = str(profile.get("name", "")).strip()

    return best_name


def build_image_prompts(
    *,
    config_path: Path | None = None,
    topic: str,
    category: str,
    audience: str,
    angle: str,
    recommended_title: str,
    cover_texts: list[str],
    body: str,
    image_suggestions: list[str],
    image_profile: str = "",
) -> list[str]:
    """Render deterministic image prompts from a selected profile."""
    config = load_image_prompt_profiles(config_path)
    profile_name = resolve_image_profile_name(
        config_path,
        category=category,
        audience=audience,
        angle=angle,
        topic=topic,
        requested_profile=image_profile,
    )
    profile = _get_profile(config, profile_name)
    suggestions = _resolve_image_suggestions(profile, image_suggestions)

    base_requirements = _as_list(config.get("global_quality_rules", {}).get("base_requirements"))
    negative_constraints = _as_list(config.get("global_quality_rules", {}).get("negative_constraints"))
    negative_constraints.extend(_as_list(profile.get("negative_constraints")))

    context = {
        "topic": topic,
        "category": category,
        "audience": audience,
        "angle": angle,
        "recommended_title": recommended_title,
        "cover_text": cover_texts[0].strip() if cover_texts else recommended_title,
        "body_summary": _summarize_body(body),
    }
    prompts: list[str] = []
    total_slides = len(suggestions)
    prompts.append(
        _build_slide_prompt(
            template=str(profile.get("cover_template", "")).strip(),
            base_context=context,
            image_suggestion=suggestions[0],
            slide_index=1,
            total_slides=total_slides,
            slide_role="封面图",
            base_requirements=base_requirements,
            negative_constraints=negative_constraints,
        )
    )

    if total_slides == 1:
        return _validate_prompts(prompts)

    closing_template = str(profile.get("closing_template", "")).strip()
    content_templates = _as_list(profile.get("content_templates"))
    middle_suggestions = suggestions[1:-1] if closing_template else suggestions[1:]
    for index, suggestion in enumerate(middle_suggestions, start=2):
        template = content_templates[(index - 2) % len(content_templates)] if content_templates else ""
        prompts.append(
            _build_slide_prompt(
                template=template,
                base_context=context,
                image_suggestion=suggestion,
                slide_index=index,
                total_slides=total_slides,
                slide_role="内容图",
                base_requirements=base_requirements,
                negative_constraints=negative_constraints,
            )
        )

    if closing_template:
        prompts.append(
            _build_slide_prompt(
                template=closing_template,
                base_context=context,
                image_suggestion=suggestions[-1],
                slide_index=total_slides,
                total_slides=total_slides,
                slide_role="结尾图",
                base_requirements=base_requirements,
                negative_constraints=negative_constraints,
            )
        )

    return _validate_prompts(prompts)


def _get_profile(config: dict[str, Any], profile_name: str) -> dict[str, Any]:
    for profile in config.get("profiles", []):
        if str(profile.get("name", "")).strip() == profile_name:
            return profile
    raise ValueError(f"Unknown image prompt profile: {profile_name}")


def _resolve_image_suggestions(profile: dict[str, Any], image_suggestions: list[str]) -> list[str]:
    suggestions = [item.strip() for item in image_suggestions if item.strip()]
    if suggestions:
        return suggestions
    defaults = _as_list(profile.get("default_image_suggestions"))
    if defaults:
        return defaults
    raise ValueError("Cannot build image prompts without image suggestions or profile defaults")


def _compose_prompt(
    *,
    template: str,
    context: dict[str, str],
    base_requirements: list[str],
    negative_constraints: list[str],
) -> str:
    parts = [render_prompt(template, context)]
    parts.extend(base_requirements)
    parts.extend(negative_constraints)
    return "，".join(part for part in parts if str(part).strip())


def _build_slide_prompt(
    *,
    template: str,
    base_context: dict[str, str],
    image_suggestion: str,
    slide_index: int,
    total_slides: int,
    slide_role: str,
    base_requirements: list[str],
    negative_constraints: list[str],
) -> str:
    prompt_context = dict(base_context)
    prompt_context["image_suggestion"] = image_suggestion
    prompt_context["slide_index"] = str(slide_index)
    prompt_context["total_slides"] = str(total_slides)
    prompt_context["slide_role"] = slide_role
    return _compose_prompt(
        template=template,
        context=prompt_context,
        base_requirements=base_requirements,
        negative_constraints=negative_constraints,
    )


def _validate_prompts(prompts: list[str]) -> list[str]:
    cleaned = [prompt.strip() for prompt in prompts if prompt.strip()]
    if not cleaned:
        raise ValueError("Image prompt rendering produced no prompts")
    if len(cleaned) > 10:
        return cleaned[:10]
    return cleaned


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _summarize_body(body: str) -> str:
    stripped = str(body).strip().replace("\n", " ")
    return stripped[:80]


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []
