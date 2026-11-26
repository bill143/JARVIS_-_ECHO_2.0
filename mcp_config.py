"""MCP server configuration parsing (pure stdlib, no Pipecat/mcp imports).

Kept separate from ``mcp_tools.py`` so the parsing/validation logic can be unit
tested without the heavy Pipecat + mcp dependencies. Server definitions follow
the familiar Claude-Desktop ``mcpServers`` shape, supplied either inline via the
``MCP_SERVERS`` env var (JSON) or from a JSON file at ``MCP_CONFIG_FILE``.

Example (MCP_SERVERS or the file contents)::

    {
      "mcpServers": {
        "filesystem": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
        },
        "weather": { "url": "https://example.com/mcp", "transport": "http" }
      }
    }
"""

from __future__ import annotations

import json
import os


def mcp_enabled() -> bool:
    return os.getenv("MCP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def load_mcp_server_configs() -> dict[str, dict]:
    """Return ``{server_name: config}`` from env/file, or ``{}`` if none.

    Precedence: ``MCP_SERVERS`` (inline JSON) wins over ``MCP_CONFIG_FILE``.
    Both accept either a top-level ``{"mcpServers": {...}}`` wrapper or a bare
    ``{name: config}`` mapping. Raises ValueError on malformed JSON/shape.
    """
    raw = os.getenv("MCP_SERVERS", "").strip()
    if not raw:
        path = os.getenv("MCP_CONFIG_FILE", "").strip()
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid MCP config JSON: {exc}") from exc

    if isinstance(data, dict) and "mcpServers" in data:
        data = data["mcpServers"]
    if not isinstance(data, dict):
        raise ValueError("MCP config must be an object of {name: server_config}")

    servers: dict[str, dict] = {}
    for name, cfg in data.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"MCP server '{name}' config must be an object")
        validate_server_config(name, cfg)
        servers[name] = cfg
    return servers


def transport_of(cfg: dict) -> str:
    """Classify a server config into 'stdio' | 'sse' | 'http'."""
    if cfg.get("command"):
        return "stdio"
    explicit = str(cfg.get("transport", "")).strip().lower()
    if explicit in {"sse", "http", "streamable", "streamable-http"}:
        return "sse" if explicit == "sse" else "http"
    # A url without an explicit transport defaults to streamable HTTP.
    return "http"


def validate_server_config(name: str, cfg: dict) -> None:
    """Raise ValueError if a single server config is unusable."""
    has_command = bool(cfg.get("command"))
    has_url = bool(cfg.get("url"))
    if has_command == has_url:  # exactly one of command/url required
        raise ValueError(
            f"MCP server '{name}' must set exactly one of 'command' (stdio) or 'url' (sse/http)"
        )
    if has_command and not isinstance(cfg.get("args", []), list):
        raise ValueError(f"MCP server '{name}': 'args' must be a list")
