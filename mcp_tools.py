"""MCP agent tools for JARVIS.

Connects JARVIS to one or more Model Context Protocol servers (configured via
``mcp_config``) and exposes their tools to the LLM — turning JARVIS into an agent
that can use filesystem, web, database, or any other MCP server's capabilities
alongside its built-in memory tools.

Built on Pipecat's official ``MCPClient`` (``pipecat-ai[mcp]``). The connection
and tool discovery are async, so :func:`register_mcp_tools` is awaited from the
async pipeline setup in ``assistant.py`` / ``assistant_web.py``.
"""

from __future__ import annotations

import logging

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.mcp_service import MCPClient

from mcp_config import (
    load_mcp_server_configs,
    mcp_enabled,
    transport_of,
)

logger = logging.getLogger(__name__)


def build_server_params(cfg: dict):
    """Turn a parsed server config into the right Pipecat ServerParameters."""
    # Imported here so importing this module's helpers doesn't force the mcp deps
    # until a server is actually configured.
    from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
    from mcp.client.stdio import StdioServerParameters

    transport = transport_of(cfg)
    if transport == "stdio":
        return StdioServerParameters(
            command=cfg["command"],
            args=list(cfg.get("args", [])),
            env=cfg.get("env"),
            cwd=cfg.get("cwd"),
        )
    if transport == "sse":
        return SseServerParameters(url=cfg["url"], headers=cfg.get("headers"))
    return StreamableHttpParameters(url=cfg["url"], headers=cfg.get("headers"))


async def register_mcp_tools(llm) -> tuple[list[FunctionSchema], list[MCPClient]]:
    """Connect to every configured MCP server and register its tools on ``llm``.

    Returns ``(tool_schemas, clients)``. The caller MUST keep a reference to the
    returned clients for the lifetime of the session so their tool handlers stay
    usable. A server that fails to connect is skipped with a warning — it never
    breaks the voice loop. Returns empty lists when MCP is disabled/unconfigured.
    """
    if not mcp_enabled():
        return [], []

    try:
        configs = load_mcp_server_configs()
    except ValueError as exc:
        logger.warning("MCP disabled — bad config: %s", exc)
        return [], []

    schemas: list[FunctionSchema] = []
    clients: list[MCPClient] = []
    for name, cfg in configs.items():
        try:
            client = MCPClient(server_params=build_server_params(cfg))
            tools_schema = await client.register_tools(llm)
            schemas.extend(tools_schema.standard_tools)
            clients.append(client)
            logger.info("MCP server '%s' connected (%d tools).", name, len(tools_schema.standard_tools))
        except Exception as exc:  # one bad server shouldn't sink the rest
            logger.warning("MCP server '%s' skipped: %s", name, exc)
    return schemas, clients
