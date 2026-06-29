from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


DEFAULT_GEMINI_SCRIPT_PATH = Path("/Users/lilin/.claude/skills/lilin-rednote/scripts/gemini_automation.py")
DEFAULT_PROMPTS_PATH = Path("/Users/lilin/.claude/skills/lilin-rednote/temp/prompts.json")


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


def build_gemini_command(
    prompts_path: Path,
    script_path: Path | None = None,
) -> list[str]:
    """Build the command that runs the existing Gemini image automation script."""
    prompt_arg = prompts_path if prompts_path.is_absolute() else prompts_path.absolute()
    script_arg = script_path or get_gemini_script_path()
    return ["python3", str(script_arg), "--prompts", str(prompt_arg)]


def generate_images(
    prompts: list[str],
    prompts_path: Path = DEFAULT_PROMPTS_PATH,
    script_path: Path | None = None,
) -> list[Path]:
    """Generate images through the existing Gemini script and return image paths."""
    prompt_file = write_gemini_prompts(prompts, prompts_path)
    command = build_gemini_command(prompt_file, script_path=script_path)
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Gemini image generation failed")
    return parse_generated_image_paths(result.stdout)


def get_gemini_script_path() -> Path:
    """Resolve Gemini script path from env or default location."""
    return Path(os.getenv("GEMINI_SCRIPT_PATH", str(DEFAULT_GEMINI_SCRIPT_PATH)))


def parse_generated_image_paths(output: str) -> list[Path]:
    """Parse absolute image paths from Gemini script output."""
    paths: list[Path] = []
    for line in output.splitlines():
        match = re.search(r"(/[^\s]+\.(?:jpg|jpeg|png|webp))", line, re.IGNORECASE)
        if match:
            paths.append(Path(match.group(1)))
    return paths
