from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_XHS_CLI_PATH = Path("/Users/lilin/.claude/skills/xiaohongshu-skills/scripts/cli.py")
DEFAULT_TEMP_DIR = Path("/Users/lilin/.claude/skills/lilin-rednote/temp")


def prepare_publish_files(package: dict[str, Any], temp_dir: Path = DEFAULT_TEMP_DIR) -> tuple[Path, Path]:
    """Write title and content files for the Xiaohongshu CLI."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    title_file = temp_dir / "title.txt"
    content_file = temp_dir / "content.txt"

    title = str(package.get("recommended_title", "")).strip()
    body = str(package.get("body", "")).strip()
    hashtags = format_hashtags(package.get("hashtags", []))

    title_file.write_text(title, encoding="utf-8")
    content_file.write_text(f"{body}\n\n{hashtags}".strip(), encoding="utf-8")
    return title_file, content_file


def format_hashtags(hashtags: list[str] | str) -> str:
    """Format hashtag values for Xiaohongshu body text."""
    if isinstance(hashtags, str):
        return hashtags.strip()
    return " ".join(f"#{tag.lstrip('#')}" for tag in hashtags if str(tag).strip())


def build_publish_command(
    title_file: Path,
    content_file: Path,
    images: list[Path],
    cli_path: Path | None = None,
) -> list[str]:
    """Build the allowed xiaohongshu-skills publish command."""
    cli_arg = cli_path or get_xhs_cli_path()
    command = [
        "python3",
        str(cli_arg),
        "publish",
        "--title-file",
        str(_absolute_path(title_file)),
        "--content-file",
        str(_absolute_path(content_file)),
        "--images",
    ]
    command.extend(str(_absolute_path(image)) for image in images)
    return command


def publish_package(
    package_path: Path,
    images: list[Path],
    temp_dir: Path = DEFAULT_TEMP_DIR,
    cli_path: Path | None = None,
) -> dict[str, Any]:
    """Publish one reviewed package through the Xiaohongshu CLI."""
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if not images:
        raise ValueError("Cannot publish without images")

    title_file, content_file = prepare_publish_files(package, temp_dir=temp_dir)
    command = build_publish_command(title_file, content_file, images, cli_path=cli_path)
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        update_publish_status(package_path, status="failed", error=result.stderr or result.stdout)
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Xiaohongshu publish failed")

    output = _parse_cli_json(result.stdout)
    note_url = str(output.get("note_url") or output.get("url") or "")
    update_publish_status(package_path, status="published", note_url=note_url, cli_output=output)
    return output


def update_publish_status(
    package_path: Path,
    status: str,
    note_url: str = "",
    error: str = "",
    cli_output: dict[str, Any] | None = None,
) -> None:
    """Update machine-readable publish status on a package JSON file."""
    data = json.loads(package_path.read_text(encoding="utf-8"))
    data["publish_status"] = status
    if note_url:
        data["note_url"] = note_url
    if error:
        data["publish_error"] = error.strip()
    if cli_output is not None:
        data["publish_cli_output"] = cli_output
    package_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_cli_json(output: str) -> dict[str, Any]:
    stripped = output.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {"raw_output": stripped}


def _absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else path.absolute()


def get_xhs_cli_path() -> Path:
    """Resolve Xiaohongshu CLI path from env or default location."""
    return Path(os.getenv("XHS_CLI_PATH", str(DEFAULT_XHS_CLI_PATH)))
