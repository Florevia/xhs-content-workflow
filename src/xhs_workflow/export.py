from __future__ import annotations

import subprocess
import webbrowser
from pathlib import Path

from xhs_workflow.packages import extract_package_fields
from xhs_workflow.prompts import read_text


CREATOR_URL = "https://creator.xiaohongshu.com"


def copy_to_clipboard(value: str) -> bool:
    """Copy text on macOS using pbcopy; return False when unavailable."""
    try:
        process = subprocess.run(
            ["pbcopy"],
            input=value,
            text=True,
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return process.returncode == 0


def load_copy_fields(package_path: Path) -> dict[str, str]:
    """Load package fields that are safe to copy into the official creator UI."""
    return extract_package_fields(read_text(package_path))


def open_creator_platform() -> None:
    """Open the official creator platform for manual publishing."""
    webbrowser.open(CREATOR_URL)
