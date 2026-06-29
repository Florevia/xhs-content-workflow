from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from xhs_workflow.images import generate_images
from xhs_workflow.publish import publish_package


ImageGenerator = Callable[[list[str]], list[Path]]
Publisher = Callable[[Path, list[Path]], dict[str, Any]]


class ReviewRejected(RuntimeError):
    """Raised when the human content review does not approve publishing."""


def auto_publish_package(
    package_path: Path,
    approved: bool,
    image_generator: ImageGenerator = generate_images,
    publisher: Publisher = publish_package,
) -> dict[str, Any]:
    """Run image generation and publish after the review gate approves."""
    if not approved:
        raise ReviewRejected("Content review rejected publishing")

    package = load_package(package_path)
    image_paths = [Path(path) for path in package.get("image_paths", []) if str(path).strip()]
    if not image_paths:
        prompts = [str(prompt) for prompt in package.get("image_prompts", []) if str(prompt).strip()]
        if not prompts:
            raise ValueError("Cannot generate images without image_prompts")
        image_paths = image_generator(prompts)
        update_image_paths(package_path, image_paths)

    return publisher(package_path, image_paths)


def load_package(package_path: Path) -> dict[str, Any]:
    """Load a machine-readable package JSON file."""
    return json.loads(package_path.read_text(encoding="utf-8"))


def update_image_paths(package_path: Path, image_paths: list[Path]) -> None:
    """Record generated image paths on the package JSON file."""
    package = load_package(package_path)
    package["image_paths"] = [str(path) for path in image_paths]
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
