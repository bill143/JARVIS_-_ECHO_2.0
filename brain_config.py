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


def _echo_accepts(base_url: str, key: str, timeout: float) -> bool:
    import httpx  # noqa: PLC0415

    try:
        response = httpx.get(
            base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def resolve_echo_key(base_url: str | None, *, probe=_echo_accepts, timeout: float = 5.0) -> str | None:
    """Pick the ECHO key the proxy actually accepts.

    Candidates, in order: ``ECHO_API_KEY`` then ``ECHO_MASTER_KEY`` (blank and
    placeholder values skipped). A stale ``ECHO_API_KEY`` left in ``.env`` after
    the master key was rotated made every LLM call fail ("400 No connected db");
    probing ``/models`` picks the working key instead. Falls back to the first
    candidate when none is accepted (so the error surfaces on the first call).
    Key values are never logged.
    """
    candidates = [k for k in (real_secret("ECHO_API_KEY"), real_secret("ECHO_MASTER_KEY")) if k]
    unique = list(dict.fromkeys(candidates))
    if not base_url or not unique:
        return unique[0] if unique else None
    for key in unique:
        if probe(base_url, key, timeout):
            return key
    return unique[0]
