"""Service health (ECHO, Ollama, vision model) and the brain's fallback chain."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from dashboard.bus import EventBus

logger = logging.getLogger(__name__)

HEALTH_INTERVAL_SECS = 5.0
PROBE_TIMEOUT_SECS = 3.0
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def load_fallbacks(config_path: Path) -> dict[str, list[str]]:
    """``{alias: [fallback, ...]}`` from ECHO's LiteLLM config (empty if unreadable)."""
    try:
        import yaml  # noqa: PLC0415

        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # missing file / bad yaml: chain display is best-effort
        logger.warning("Could not read ECHO fallbacks from %s: %s", config_path, exc)
        return {}
    chains: dict[str, list[str]] = {}
    for item in (config.get("router_settings") or {}).get("fallbacks") or []:
        for alias, chain in (item or {}).items():
            chains[str(alias)] = [str(c) for c in chain or []]
    return chains


def echo_root(echo_base_url: str | None) -> str | None:
    """``http://localhost:4000/v1`` -> ``http://localhost:4000``."""
    if not echo_base_url:
        return None
    root = echo_base_url.rstrip("/")
    return root[: -len("/v1")] if root.endswith("/v1") else root


async def check_services(
    client: httpx.AsyncClient,
    echo_url: str | None,
    ollama_url: str,
    required_models: dict[str, str],
) -> dict[str, dict]:
    """One health pass. ``required_models`` maps a label to an Ollama model name."""
    services: dict[str, dict] = {}

    if echo_url:
        try:
            r = await client.get(f"{echo_url}/health/liveliness", timeout=PROBE_TIMEOUT_SECS)
            services["echo"] = {"ok": r.status_code == 200, "detail": f"HTTP {r.status_code}"}
        except httpx.HTTPError as exc:
            services["echo"] = {"ok": False, "detail": type(exc).__name__}
    else:
        services["echo"] = {"ok": False, "detail": "not configured"}

    installed: set[str] = set()
    try:
        r = await client.get(f"{ollama_url}/api/tags", timeout=PROBE_TIMEOUT_SECS)
        r.raise_for_status()
        installed = {m.get("name", "") for m in r.json().get("models", [])}
        services["ollama"] = {"ok": True, "detail": f"{len(installed)} models"}
    except (httpx.HTTPError, ValueError) as exc:
        services["ollama"] = {"ok": False, "detail": type(exc).__name__}

    for label, model in required_models.items():
        present = model in installed or f"{model}:latest" in installed
        services[label] = {"ok": present, "detail": model if present else f"{model} not pulled"}
    return services


class HealthMonitor:
    def __init__(
        self,
        bus: EventBus,
        echo_base_url: str | None,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        required_models: dict[str, str] | None = None,
    ) -> None:
        self._bus = bus
        self._echo = echo_root(echo_base_url)
        self._ollama = ollama_url.rstrip("/")
        self._models = required_models or {}
        self._task: asyncio.Task | None = None

    async def run_once(self) -> dict[str, dict]:
        async with httpx.AsyncClient() as client:
            services = await check_services(client, self._echo, self._ollama, self._models)
        self._bus.publish("health", services=services)
        return services

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception as exc:  # never let health checks kill JARVIS
                logger.warning("Health check failed: %s", exc)
            await asyncio.sleep(HEALTH_INTERVAL_SECS)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
