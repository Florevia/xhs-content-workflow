from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from xhs_workflow.images import generate_images, resolve_daily_image_dir
from xhs_workflow.publish import publish_package, update_publish_status


ImageGenerator = Callable[[list[str], Path], list[Path]]
Publisher = Callable[[Path, list[Path]], dict[str, Any]]


class ReviewRejected(RuntimeError):
    """Raised when the human content review does not approve publishing."""


APPROVED_REVIEW_STATUSES = {"approved", "reviewed", "pass", "passed"}
BLOCKED_REVIEW_STATUSES = {"rejected", "blocked", "failed"}
HIGH_RISK_LEVELS = {"high"}


def auto_publish_package(
    package_path: Path,
    approved: bool,
    image_generator: ImageGenerator | None = None,
    publisher: Publisher = publish_package,
    require_reviewed_package: bool = False,
) -> dict[str, Any]:
    """Run image generation and publish after the review gate approves."""
    generate = image_generator or _default_image_generator
    package = load_package(package_path)
    ensure_publish_allowed(package, approved=approved, require_reviewed_package=require_reviewed_package)
    image_paths = [Path(path) for path in package.get("image_paths", []) if str(path).strip()]

    try:
        if not image_paths:
            prompts = [str(prompt) for prompt in package.get("image_prompts", []) if str(prompt).strip()]
            if not prompts:
                raise ValueError("Cannot generate images without image_prompts")
            update_publish_status(package_path, status="image_generating")
            image_output_dir = resolve_daily_image_dir(package_path)
            image_paths = generate(prompts, image_output_dir)
            update_image_paths(package_path, image_paths)
            update_publish_status(package_path, status="image_ready")

        update_publish_status(package_path, status="publishing")
        result = publisher(package_path, image_paths)
        update_publish_status(package_path, status="published", cli_output=result)
        return result
    except Exception as error:
        update_publish_status(package_path, status="failed", error=str(error))
        raise


def ensure_publish_allowed(
    package: dict[str, Any],
    *,
    approved: bool,
    require_reviewed_package: bool = False,
) -> None:
    """Validate the human/compliance gates before any side effects."""
    if not approved:
        raise ReviewRejected("Content review rejected publishing")

    review_status = str(package.get("review_status", "")).strip().lower()
    if review_status in BLOCKED_REVIEW_STATUSES:
        raise ReviewRejected(f"Package review status blocks publishing: {review_status}")
    if require_reviewed_package and review_status not in APPROVED_REVIEW_STATUSES:
        raise ReviewRejected("Unattended publishing requires review_status=approved")

    compliance = package.get("compliance_check") or {}
    risk_level = str(compliance.get("risk_level", "")).strip().lower() if isinstance(compliance, dict) else ""
    if risk_level in HIGH_RISK_LEVELS:
        raise ReviewRejected("High-risk content cannot be published automatically")


def _default_image_generator(prompts: list[str], output_dir: Path) -> list[Path]:
    """Generate images into the daily publish directory."""
    return generate_images(prompts, output_dir=output_dir)


def load_package(package_path: Path) -> dict[str, Any]:
    """Load a machine-readable package JSON file."""
    return json.loads(package_path.read_text(encoding="utf-8"))


def update_image_paths(package_path: Path, image_paths: list[Path]) -> None:
    """Record generated image paths on the package JSON file."""
    package = load_package(package_path)
    package["image_paths"] = [str(path) for path in image_paths]
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
