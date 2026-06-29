from __future__ import annotations

from pathlib import Path


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8")


def render_prompt(template: str, values: dict[str, object]) -> str:
    """Replace named placeholders without treating JSON braces as formatting syntax."""
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered
