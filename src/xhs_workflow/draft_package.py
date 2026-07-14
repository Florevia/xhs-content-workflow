from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xhs_workflow.image_prompt_profiles import build_image_prompts, resolve_image_profile_name
from xhs_workflow.packages import PublishPackage, write_publish_package
from xhs_workflow.research import MISSING_RESEARCH_NOTE


DEFAULT_OUTPUT_DIR = Path("output/publish_packages")


class DraftValidationError(ValueError):
    """Raised when a local no-API draft is missing publishable fields."""


def create_package_from_draft(
    draft_path: Path,
    output_dir: Path,
    config_path: Path | None = None,
) -> Path:
    """Create a standard publish package from a local JSON draft."""
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    _validate_draft(draft)
    image_prompts, image_profile = _resolve_draft_image_assets(draft, config_path)
    compliance_check = _resolve_draft_compliance(draft)
    research_brief = draft.get("research_brief")
    raw = {
        **draft,
        "image_profile": image_profile,
        "image_prompts": image_prompts,
        "compliance_check": compliance_check,
    }
    if isinstance(research_brief, dict):
        raw["research_brief"] = research_brief
    else:
        raw.pop("research_brief", None)

    package = PublishPackage(
        topic_id=str(draft.get("topic_id") or draft.get("id") or draft_path.stem),
        topic=str(draft.get("topic") or draft.get("recommended_title") or draft_path.stem),
        category=str(draft.get("category", "")),
        audience=str(draft.get("audience", "")),
        angle=str(draft.get("angle", "")),
        titles=_as_list(draft.get("titles")) or [str(draft["recommended_title"]).strip()],
        recommended_title=str(draft["recommended_title"]).strip(),
        cover_texts=_as_list(draft.get("cover_texts")),
        body=str(draft["body"]).strip(),
        hashtags=[tag.lstrip("#") for tag in _as_list(draft["hashtags"])],
        image_suggestions=_as_list(draft.get("image_suggestions")) or image_prompts,
        image_profile=image_profile,
        image_prompts=image_prompts,
        image_paths=_as_list(draft.get("image_paths")),
        publish_time_suggestion=str(draft.get("publish_time_suggestion", "")),
        compliance_check=compliance_check,
        raw=raw,
        review_status=str(draft.get("review_status", "draft")),
        publish_status=str(draft.get("publish_status", "draft")),
    )
    return write_publish_package(package, output_dir)


def _resolve_draft_compliance(draft: dict[str, Any]) -> dict[str, Any]:
    compliance = dict(draft.get("compliance_check") or {"risk_level": "manual"})
    research_brief = draft.get("research_brief")
    if isinstance(research_brief, dict):
        return compliance
    risks = [str(item).strip() for item in (compliance.get("risks") or []) if str(item).strip()]
    if MISSING_RESEARCH_NOTE not in risks:
        risks.append(MISSING_RESEARCH_NOTE)
    compliance["risks"] = risks
    return compliance


def _validate_draft(draft: dict[str, Any]) -> None:
    required_fields = ("recommended_title", "body", "hashtags")
    missing = [field for field in required_fields if not _has_value(draft.get(field))]
    if not _has_any_image_inputs(draft):
        missing.append("image_prompts/image_suggestions/image_profile")
    if missing:
        raise DraftValidationError(f"Draft is missing required fields: {', '.join(missing)}")


def _has_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return bool(str(value or "").strip())


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _has_any_image_inputs(draft: dict[str, Any]) -> bool:
    for key in ("image_prompts", "image_suggestions", "image_profile"):
        if _has_value(draft.get(key)):
            return True
    return False


def _resolve_draft_image_assets(
    draft: dict[str, Any],
    config_path: Path | None,
) -> tuple[list[str], str]:
    manual_prompts = _as_list(draft.get("image_prompts"))
    if manual_prompts:
        return manual_prompts, ""

    image_profile = resolve_image_profile_name(
        config_path,
        category=str(draft.get("category", "")),
        audience=str(draft.get("audience", "")),
        angle=str(draft.get("angle", "")),
        topic=str(draft.get("topic", "")),
        requested_profile=str(draft.get("image_profile", "")),
    )
    generated_prompts = build_image_prompts(
        config_path=config_path,
        topic=str(draft.get("topic") or draft.get("recommended_title", "")),
        category=str(draft.get("category", "")),
        audience=str(draft.get("audience", "")),
        angle=str(draft.get("angle", "")),
        recommended_title=str(draft.get("recommended_title", "")),
        cover_texts=_as_list(draft.get("cover_texts")),
        body=str(draft.get("body", "")),
        image_suggestions=_as_list(draft.get("image_suggestions")),
        image_profile=image_profile,
    )
    return generated_prompts, image_profile
