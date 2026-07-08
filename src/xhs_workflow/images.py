from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import date
from pathlib import Path


DEFAULT_CHATGPT_SCRIPT_PATH = Path("/Users/lilin/.claude/skills/lilin-rednote/scripts/chatgpt_automation.py")
DEFAULT_PROMPTS_PATH = Path("/Users/lilin/.claude/skills/lilin-rednote/temp/prompts.json")
# chatgpt_automation.py imports `xhs.bridge`, which lives in the xiaohongshu-skills
# scripts folder rather than next to the script itself, so it must be added to
# PYTHONPATH explicitly for the subprocess call below.
DEFAULT_XHS_SKILLS_SCRIPTS_DIR = Path("/Users/lilin/.claude/skills/xiaohongshu-skills/scripts")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLISHED_IMAGES_ROOT = PROJECT_ROOT / "output" / "published_images"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGES_PER_BATCH = 8
# Gemini 看到「小红书风格」时容易误生成帖子底部 UI（点赞栏、假账号名等），统一追加负向约束
FORBIDDEN_SOCIAL_UI_MARKER = "不要模拟社交媒体帖子界面"
FORBIDDEN_SOCIAL_UI_CONSTRAINTS = (
    "不要模拟社交媒体帖子界面，"
    "不要出现点赞/收藏/分享/评论按钮栏，"
    "不要出现底部账号名或@用户名，"
    "不要出现小红书App界面截图或UI mockup，"
    "纯信息图内容，不做帖子预览样式"
)


def finalize_image_prompt(prompt: str) -> str:
    """Append social-UI bans so Gemini does not fake Xiaohongshu post chrome."""
    text = str(prompt).strip()
    if not text or FORBIDDEN_SOCIAL_UI_MARKER in text:
        return text
    return f"{text}，{FORBIDDEN_SOCIAL_UI_CONSTRAINTS}"


def chunk_prompts(prompts: list[str], max_batch: int = MAX_IMAGES_PER_BATCH) -> list[list[str]]:
    """Split prompts into fixed-order batches for multi-image ChatGPT generation."""
    cleaned = [str(prompt).strip() for prompt in prompts if str(prompt).strip()]
    if max_batch <= 0:
        raise ValueError("max_batch must be positive")
    return [cleaned[index:index + max_batch] for index in range(0, len(cleaned), max_batch)]


def build_combined_batch_prompt(prompts_in_batch: list[str], count: int) -> str:
    """Concatenate per-slide prompts into one message for a single ChatGPT turn."""
    cleaned = [str(prompt).strip() for prompt in prompts_in_batch if str(prompt).strip()]
    if not cleaned:
        raise ValueError("Cannot build a batch prompt without slide prompts")
    return "\n\n---\n\n".join(cleaned)


def write_chatgpt_batches(prompts: list[str], output_path: Path = DEFAULT_PROMPTS_PATH) -> Path:
    """Write grouped multi-image prompts in the format consumed by ChatGPT automation."""
    output_path = output_path if output_path.is_absolute() else output_path.absolute()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = [str(prompt).strip() for prompt in prompts if str(prompt).strip()]
    batches = chunk_prompts(cleaned)
    payload = []
    start_index = 1
    for batch_index, batch in enumerate(batches, 1):
        count = len(batch)
        end_index = start_index + count - 1
        combined_prompt = build_combined_batch_prompt(batch, count=count)
        payload.append(
            {
                "batch_index": batch_index,
                "start_index": start_index,
                "end_index": end_index,
                "count": count,
                "prompt": finalize_image_prompt(combined_prompt),
            }
        )
        start_index = end_index + 1
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


def build_chatgpt_command(
    prompts_path: Path,
    script_path: Path | None = None,
    output_dir: Path | None = None,
) -> list[str]:
    """Build the command that runs the ChatGPT image automation script."""
    prompt_arg = prompts_path if prompts_path.is_absolute() else prompts_path.absolute()
    script_arg = script_path or get_chatgpt_script_path()
    command = ["python3", str(script_arg), "--prompts", str(prompt_arg)]
    if output_dir is not None:
        output_arg = output_dir if output_dir.is_absolute() else output_dir.absolute()
        command.extend(["--output-dir", str(output_arg)])
    return command


# ChatGPT 网页自动化偶发首次发送后检测不到图片（页面渲染较慢/首次打开标签页），
# 这是已知瞬时故障（见 AGENTS.md 错误修复记录 2026-07-08），因此默认重试一次再判定失败。
DEFAULT_GENERATE_RETRIES = 1


def generate_images(
    prompts: list[str],
    output_dir: Path | None = None,
    prompts_path: Path = DEFAULT_PROMPTS_PATH,
    script_path: Path | None = None,
    retries: int = DEFAULT_GENERATE_RETRIES,
) -> list[Path]:
    """Generate images through the ChatGPT automation script and return image paths.

    Retries the whole ChatGPT batch once (by default) on transient "0 images
    returned" failures before raising, since a single flaky attempt should not
    fail the entire publish flow.
    """
    attempts = max(1, retries + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _generate_images_once(prompts, output_dir=output_dir, prompts_path=prompts_path, script_path=script_path)
        except RuntimeError as error:
            last_error = error
            if attempt >= attempts:
                raise
    raise last_error or RuntimeError("ChatGPT image generation failed")


def _generate_images_once(
    prompts: list[str],
    output_dir: Path | None,
    prompts_path: Path,
    script_path: Path | None,
) -> list[Path]:
    prompt_file = write_chatgpt_batches(prompts, _resolve_prompts_path(prompts_path))
    command = build_chatgpt_command(prompt_file, script_path=script_path, output_dir=output_dir)
    result = subprocess.run(command, text=True, capture_output=True, check=False, env=_build_chatgpt_env())
    parsed = parse_generated_image_paths(result.stdout)
    if parsed:
        expected_count = len([prompt for prompt in prompts if str(prompt).strip()])
        try:
            return validate_generated_image_paths(parsed, expected_count=expected_count)
        except RuntimeError:
            if result.returncode != 0:
                raise
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ChatGPT image generation failed")
    expected_count = len([prompt for prompt in prompts if str(prompt).strip()])
    return validate_generated_image_paths(parsed, expected_count=expected_count)


def get_chatgpt_script_path() -> Path:
    """Resolve ChatGPT automation script path from env or default location."""
    return Path(os.getenv("CHATGPT_SCRIPT_PATH", str(DEFAULT_CHATGPT_SCRIPT_PATH)))


def get_xhs_skills_scripts_dir() -> Path:
    """Resolve the xiaohongshu-skills scripts directory providing the `xhs` package."""
    return Path(os.getenv("XHS_SKILLS_SCRIPTS_DIR", str(DEFAULT_XHS_SKILLS_SCRIPTS_DIR)))


def _build_chatgpt_env() -> dict[str, str]:
    """Ensure the ChatGPT subprocess can import `xhs.bridge` regardless of caller PYTHONPATH."""
    env = os.environ.copy()
    scripts_dir = str(get_xhs_skills_scripts_dir())
    existing = env.get("PYTHONPATH", "")
    parts = [scripts_dir] + [part for part in existing.split(os.pathsep) if part and part != scripts_dir]
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def parse_generated_image_paths(output: str) -> list[Path]:
    """Parse absolute image paths from ChatGPT automation output."""
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
    """Ensure ChatGPT returned usable local image files."""
    cleaned = [Path(path) for path in image_paths if str(path).strip()]
    if expected_count is not None and len(cleaned) < expected_count:
        raise RuntimeError(f"ChatGPT returned {len(cleaned)} images, expected {expected_count}")

    missing = [str(path) for path in cleaned if not path.exists()]
    if missing:
        raise RuntimeError(f"Generated image files do not exist: {', '.join(missing)}")

    unsupported = [str(path) for path in cleaned if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES]
    if unsupported:
        raise RuntimeError(f"Generated files are not supported images: {', '.join(unsupported)}")

    ensure_no_duplicate_images(cleaned)
    return cleaned


def ensure_no_duplicate_images(image_paths: list[Path]) -> None:
    """Raise if any two generated images are byte-identical.

    Guards against ChatGPT automation bugs (e.g. clicking the wrong download
    button, or a blob-capture fallback grabbing a stale image) that silently
    save the same picture under multiple `image_N` filenames.
    """
    seen: dict[str, Path] = {}
    duplicates: list[tuple[Path, Path]] = []
    for path in image_paths:
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        if digest in seen:
            duplicates.append((seen[digest], path))
        else:
            seen[digest] = path

    if duplicates:
        details = ", ".join(f"{a.name} == {b.name}" for a, b in duplicates)
        raise RuntimeError(
            f"Generated images contain duplicate content, refusing to publish: {details}"
        )


def _resolve_prompts_path(prompts_path: Path) -> Path:
    """Avoid overwriting another in-flight ChatGPT batch prompt file."""
    if prompts_path != DEFAULT_PROMPTS_PATH:
        return prompts_path
    return prompts_path.parent / f"batches_{os.getpid()}_{uuid.uuid4().hex}.json"


def write_gemini_prompts(prompts: list[str], output_path: Path = DEFAULT_PROMPTS_PATH) -> Path:
    """Backward-compatible alias for older callers."""
    return write_chatgpt_batches(prompts, output_path)


def build_gemini_command(
    prompts_path: Path,
    script_path: Path | None = None,
    output_dir: Path | None = None,
) -> list[str]:
    """Backward-compatible alias for older callers."""
    return build_chatgpt_command(prompts_path, script_path=script_path, output_dir=output_dir)


def get_gemini_script_path() -> Path:
    """Backward-compatible alias for older callers."""
    return get_chatgpt_script_path()


def _build_gemini_env() -> dict[str, str]:
    """Backward-compatible alias for older callers."""
    return _build_chatgpt_env()


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
