"""Offline tests for MCP config parsing (pure stdlib, no Pipecat/mcp).

Run directly:  python test_mcp_config.py
"""

from __future__ import annotations

import json
import os
import tempfile

from mcp_config import (
    load_mcp_server_configs,
    mcp_enabled,
    transport_of,
    validate_server_config,
)

SAMPLE = {
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
        },
        "weather": {"url": "https://example.com/mcp", "transport": "http"},
        "legacy": {"url": "https://example.com/sse", "transport": "sse"},
    }
}


def _clear_env() -> None:
    for k in ("MCP_SERVERS", "MCP_CONFIG_FILE", "MCP_ENABLED"):
        os.environ.pop(k, None)


def test_disabled_and_empty_by_default() -> None:
    _clear_env()
    assert mcp_enabled() is False
    assert load_mcp_server_configs() == {}


def test_enabled_flag() -> None:
    os.environ["MCP_ENABLED"] = "true"
    assert mcp_enabled() is True
    os.environ["MCP_ENABLED"] = "false"
    assert mcp_enabled() is False


def test_inline_json_parsing_and_transport() -> None:
    _clear_env()
    os.environ["MCP_SERVERS"] = json.dumps(SAMPLE)
    servers = load_mcp_server_configs()
    assert set(servers) == {"filesystem", "weather", "legacy"}
    assert transport_of(servers["filesystem"]) == "stdio"
    assert transport_of(servers["weather"]) == "http"
    assert transport_of(servers["legacy"]) == "sse"
    # A bare url with no transport defaults to streamable http.
    assert transport_of({"url": "https://x"}) == "http"
    _clear_env()


def test_file_based_config() -> None:
    _clear_env()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "mcp.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(SAMPLE, fh)
        os.environ["MCP_CONFIG_FILE"] = path
        servers = load_mcp_server_configs()
        assert "filesystem" in servers
    _clear_env()


def test_bad_json_raises() -> None:
    _clear_env()
    os.environ["MCP_SERVERS"] = "{not json"
    try:
        load_mcp_server_configs()
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for malformed JSON")
    _clear_env()


def test_validate_requires_exactly_one_of_command_or_url() -> None:
    for bad in ({}, {"command": "x", "url": "y"}, {"command": "x", "args": "notalist"}):
        try:
            validate_server_config("s", bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")
    # Good ones don't raise.
    validate_server_config("s", {"command": "npx", "args": ["a"]})
    validate_server_config("s", {"url": "https://x"})


def main() -> None:
    checks = [
        ("disabled + empty by default", test_disabled_and_empty_by_default),
        ("enabled flag", test_enabled_flag),
        ("inline json + transport classify", test_inline_json_parsing_and_transport),
        ("file-based config", test_file_based_config),
        ("bad json raises", test_bad_json_raises),
        ("validate command/url rules", test_validate_requires_exactly_one_of_command_or_url),
    ]
    try:
        for name, fn in checks:
            fn()
            print(f"  ok - {name}")
    finally:
        _clear_env()
    print(f"\nmcp_config: {len(checks)}/{len(checks)} checks passed")


if __name__ == "__main__":
    main()
