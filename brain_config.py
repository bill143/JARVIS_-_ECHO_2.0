"""Brain (LLM) config helpers shared by ``assistant.py`` and ``assistant_web.py``."""

from __future__ import annotations

import os

PLACEHOLDER_KEY_MARKERS = ("your-key", "change-me")


def real_secret(*names: str) -> str | None:
    """Return the first non-blank, non-placeholder value among env vars ``names``.

    ``.env.example`` ships ``ANTHROPIC_API_KEY=sk-ant-your-key-here``; a copied but
    unedited ``.env`` must count as "no key", not silently select a dead brain.
    """
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value and not any(marker in value.lower() for marker in PLACEHOLDER_KEY_MARKERS):
            return value
    return None


def echo_base_url() -> str | None:
    """``ECHO_BASE_URL`` with blank treated as unset."""
    return (os.getenv("ECHO_BASE_URL") or "").strip() or None
