from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from datetime import date
from pathlib import Path


DEFAULT_GEMINI_SCRIPT_PATH = Path("/Users/lilin/.claude/skills/lilin-rednote/scripts/gemini_automation.py")
DEFAULT_PROMPTS_PATH = Path("/Users/lilin/.claude/skills/lilin-rednote/temp/prompts.json")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLISHED_IMAGES_ROOT = PROJECT_ROOT / "output" / "published_images"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def write_gemini_prompts(prompts: list[str], output_path: Path = DEFAULT_PROMPTS_PATH) -> Path:
    """Write prompts in the format consumed by lilin-rednote Gemini automation."""
    output_path = output_path if output_path.is_absolute() else output_path.absolute()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "index": index,
            "type": "封面图" if index == 1 else "内容图",
            "prompt": prompt,
        }
        for index, prompt in enumerate(prompts, 1)
        if prompt.strip()
    ]
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def resolve_daily_image_dir(
    package_path: Path | None = None,
    *,
    root: Path = DEFAULT_PUBLISHED_IMAGES_ROOT,
    when: date | None = None,
) -> Path:
    """Return output/published_images/MM-DD[/package_stem] for the publish day."""
    target_day = when or date.today()
    daily_dir = root / target_day.strftime("%m-%d")
    if package_path is not None:
        daily_dir = daily_dir / package_path.stem
    daily_dir.mkdir(parents=True, exist_ok=True)
    return daily_dir


def build_gemini_command(
    prompts_path: Path,
    script_path: Path | None = None,
    output_dir: Path | None = None,
) -> list[str]:
    """Build the command that runs the existing Gemini image automation script."""
    prompt_arg = prompts_path if prompts_path.is_absolute() else prompts_path.absolute()
    script_arg = script_path or get_gemini_script_path()
    command = ["python3", str(script_arg), "--prompts", str(prompt_arg)]
    if output_dir is not None:
        output_arg = output_dir if output_dir.is_absolute() else output_dir.absolute()
        command.extend(["--output-dir", str(output_arg)])
    return command


def generate_images(
    prompts: list[str],
    output_dir: Path | None = None,
    prompts_path: Path = DEFAULT_PROMPTS_PATH,
    script_path: Path | None = None,
) -> list[Path]:
    """Generate images through the existing Gemini script and return image paths."""
    prompt_file = write_gemini_prompts(prompts, _resolve_prompts_path(prompts_path))
    command = build_gemini_command(prompt_file, script_path=script_path, output_dir=output_dir)
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Gemini image generation failed")
    expected_count = len([prompt for prompt in prompts if str(prompt).strip()])
    return validate_generated_image_paths(parse_generated_image_paths(result.stdout), expected_count=expected_count)


def get_gemini_script_path() -> Path:
    """Resolve Gemini script path from env or default location."""
    return Path(os.getenv("GEMINI_SCRIPT_PATH", str(DEFAULT_GEMINI_SCRIPT_PATH)))


def parse_generated_image_paths(output: str) -> list[Path]:
    """Parse absolute image paths from Gemini script output."""
    json_paths = _parse_json_image_paths(output)
    if json_paths:
        return json_paths

    paths: list[Path] = []
    for line in output.splitlines():
        match = re.search(r"(/[^\s]+\.(?:jpg|jpeg|png|webp))", line, re.IGNORECASE)
        if match:
            paths.append(Path(match.group(1)))
    return paths


def validate_generated_image_paths(image_paths: list[Path], expected_count: int | None = None) -> list[Path]:
    """Ensure Gemini returned usable local image files."""
    cleaned = [Path(path) for path in image_paths if str(path).strip()]
    if expected_count is not None and len(cleaned) < expected_count:
        raise RuntimeError(f"Gemini returned {len(cleaned)} images, expected {expected_count}")

    missing = [str(path) for path in cleaned if not path.exists()]
    if missing:
        raise RuntimeError(f"Generated image files do not exist: {', '.join(missing)}")

    unsupported = [str(path) for path in cleaned if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES]
    if unsupported:
        raise RuntimeError(f"Generated files are not supported images: {', '.join(unsupported)}")

    return cleaned


def _resolve_prompts_path(prompts_path: Path) -> Path:
    """Avoid overwriting another in-flight Gemini prompt file."""
    if prompts_path != DEFAULT_PROMPTS_PATH:
        return prompts_path
    return prompts_path.parent / f"prompts_{os.getpid()}_{uuid.uuid4().hex}.json"


def _parse_json_image_paths(output: str) -> list[Path]:
    stripped = output.strip()
    if not stripped:
        return []
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    return [Path(value) for value in _walk_image_path_values(payload)]


def _walk_image_path_values(value: object) -> list[str]:
    if isinstance(value, str) and Path(value).suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
        return [value]
    if isinstance(value, list):
        paths: list[str] = []
        for item in value:
            paths.extend(_walk_image_path_values(item))
        return paths
    if isinstance(value, dict):
        paths: list[str] = []
        for item in value.values():
            paths.extend(_walk_image_path_values(item))
        return paths
    return []
