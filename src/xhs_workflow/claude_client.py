from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "claude-sonnet-4-5"


class ClaudeConfigError(RuntimeError):
    """Raised when Claude API configuration is incomplete."""


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from an env file without extra dependencies."""
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from raw Claude text or a Markdown fence."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _strip_markdown_fence(stripped)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


class ClaudeClient:
    """Small wrapper around Anthropic Messages API."""

    def __init__(self, root: Path):
        load_env_file(root / ".env")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ClaudeConfigError("ANTHROPIC_API_KEY is not configured")

        try:
            from anthropic import Anthropic
        except ImportError as error:
            raise ClaudeConfigError(
                "anthropic package is not installed; run `pip install -r requirements.txt`"
            ) from error

        self._client = Anthropic(api_key=api_key)
        self._model = os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)

    def complete_json(self, prompt: str, system: str, max_tokens: int = 4000) -> dict[str, Any]:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return extract_json_object(_message_text(message))

    def complete_json_with_web_search(
        self,
        prompt: str,
        system: str,
        max_tokens: int = 4000,
        max_uses: int | None = None,
    ) -> dict[str, Any]:
        """Complete a JSON response with Anthropic web_search enabled."""
        uses = max_uses
        if uses is None:
            raw = os.getenv("CLAUDE_WEB_SEARCH_MAX_USES", "5").strip()
            uses = int(raw) if raw else 5

        message = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": uses,
                    "allowed_callers": ["direct"],
                }
            ],
        )
        return extract_json_object(_message_text(message))


def _message_text(message: Any) -> str:
    """Join all text blocks from a Messages API response."""
    chunks: list[str] = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", "") or "")
        elif isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text") or ""))
    if chunks:
        return "".join(chunks)
    # Fallback for simple mock objects used in older tests.
    first = message.content[0]
    return first.text if hasattr(first, "text") else str(first)


def _strip_markdown_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
