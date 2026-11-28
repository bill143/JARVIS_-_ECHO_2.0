"""Live tool management for a running JARVIS.

``ToolboxRuntime`` owns the brain's tool list:

* built-in tools (clock, memory, eyes, people) with on/off switches,
* MCP servers from the toolbox store - connected, tested, enabled, disabled or
  removed while JARVIS runs; their tools are registered on the LLM and the shared
  ``LLMContext`` is updated, so the very next turn can use a newly added tool,
* skills (SKILL.md): their names + descriptions go in the system prompt and the
  ``read_skill`` tool returns the full instructions when the brain needs them.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.mcp_service import MCPClient

from toolbox.store import ToolboxStore

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECS = 45.0
READ_SKILL = "read_skill"
FIND_SKILLS = "find_skills"
# Up to this many enabled skills, every name + description goes in the system
# prompt. Beyond it (a 245-skill library is ~11k tokens on every request: slow,
# and over the free brain's per-minute token budget) the brain gets a find_skills
# search tool instead and only sees the matches it asks for.
SKILLS_INLINE_MAX = int(os.getenv("SKILLS_INLINE_MAX", "25") or 25)
FIND_SKILLS_LIMIT = 8
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "and", "the", "of", "for", "to", "in", "on", "with", "by", "or", "is", "it", "my", "me",
         "i", "you", "what", "how", "can", "do", "please", "jarvis", "use", "using", "from", "into", "at"}
SKILLS_WATCH_SECS = float(os.getenv("SKILLS_WATCH_SECS", "15") or 15)


def server_params(server: dict, store: ToolboxStore):
    """Pipecat/MCP connection parameters for a stored server (secrets injected here only)."""
    from mcp.client.session_group import SseServerParameters, StreamableHttpParameters  # noqa: PLC0415
    from mcp.client.stdio import StdioServerParameters  # noqa: PLC0415

    secret_values, missing = store.resolve_secrets(
        [*server.get("secret_env", []), *([server["auth_secret"]] if server.get("auth_secret") else [])]
    )
    if missing:
        raise RuntimeError(f"Missing secret(s): {', '.join(missing)}. Add them under Secrets.")
    if server["transport"] == "stdio":
        env = {**os.environ, **{k: v for k, v in secret_values.items() if k in server.get("secret_env", [])}}
        return StdioServerParameters(command=server["command"], args=server.get("args", []), env=env,
                                     cwd=server.get("cwd") or None)
    headers = {"Authorization": f"Bearer {secret_values[server['auth_secret']]}"} if server.get("auth_secret") else None
    if server["transport"] == "sse":
        return SseServerParameters(url=server["url"], headers=headers)
    return StreamableHttpParameters(url=server["url"], headers=headers)


async def probe_server(server: dict, store: ToolboxStore) -> list[dict]:
    """Connect, list tools, disconnect. Raises on failure (message is safe to show)."""
    client = MCPClient(server_params=server_params(server, store))
    try:
        await asyncio.wait_for(client.start(), CONNECT_TIMEOUT_SECS)
        schema = await client.get_tools_schema()
        return [{"name": t.name, "description": (t.description or "")[:300]} for t in schema.standard_tools]
    finally:
        try:
            await client.close()
        except Exception:  # closing a half-open stdio process must never mask the real error
            pass


class ToolboxRuntime:
    def __init__(self, llm, context, store: ToolboxStore, builtin: dict[str, list[FunctionSchema]],
                 base_prompt: str = "") -> None:
        self._llm = llm
        self._context = context
        self.store = store
        self._builtin = builtin  # group label -> schemas
        self._base_prompt = base_prompt
        self._clients: dict[str, MCPClient] = {}
        self._server_tools: dict[str, list[FunctionSchema]] = {}
        self._status: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        llm.register_function(READ_SKILL, self._read_skill)
        llm.register_function(FIND_SKILLS, self._find_skills)
        self._watch_task: asyncio.Task | None = None
        self._folder_signature: tuple | None = None

    # ---- lifecycle -----------------------------------------------------
    async def start(self) -> None:
        # Skills copied into the skills folder while JARVIS was off, then keep watching it.
        await self.sync_skill_folder()
        self._watch_task = asyncio.create_task(self._watch_skill_folder())
        for server in self.store.servers():
            if server["enabled"]:
                await self._connect(server)
            else:
                self._status[server["id"]] = {"state": "off"}
        self._apply()

    async def close(self) -> None:
        if self._watch_task is not None:
            self._watch_task.cancel()
        for server_id in list(self._clients):
            await self._disconnect(server_id)

    # ---- skills drop folder ------------------------------------------------
    async def sync_skill_folder(self) -> dict:
        """Load new / changed skills from the skills folder and drop removed ones."""
        self._folder_signature = await asyncio.to_thread(self.store.folder_signature)
        found = await asyncio.to_thread(self.store.scan_skill_folder)
        changes = [(k, found[k]) for k in ("imported", "updated", "removed") if found[k]]
        if changes:
            self._apply()
            summary = ", ".join(f"{k} {len(v)}" for k, v in changes)
            print(f"[JARVIS] Skills folder: {summary} ({', '.join(n for _, v in changes for n in v)[:300]})", flush=True)
        return found

    async def _watch_skill_folder(self) -> None:
        """Every SKILLS_WATCH_SECS, rescan only if a SKILL.md or .zip was added, changed or removed."""
        while True:
            await asyncio.sleep(SKILLS_WATCH_SECS)
            try:
                signature = await asyncio.to_thread(self.store.folder_signature)
                if signature != self._folder_signature:
                    await self.sync_skill_folder()
            except Exception as exc:  # noqa: BLE001 - the watcher must survive a bad file
                logger.warning("skills folder watch failed: %s", exc)

    async def _connect(self, server: dict) -> None:
        self._status[server["id"]] = {"state": "connecting"}
        try:
            client = MCPClient(server_params=server_params(server, self.store))
            await asyncio.wait_for(client.start(), CONNECT_TIMEOUT_SECS)
            schema = await client.register_tools(self._llm)
        except Exception as exc:
            message = str(exc) or type(exc).__name__
            self._status[server["id"]] = {"state": "error", "error": message[:300]}
            print(f"[JARVIS] Tool server '{server['name']}' failed: {message[:200]}", flush=True)
            return
        self._clients[server["id"]] = client
        self._server_tools[server["id"]] = list(schema.standard_tools)
        self._status[server["id"]] = {"state": "connected"}
        print(f"[JARVIS] Tool server '{server['name']}' connected: "
              f"{', '.join(t.name for t in schema.standard_tools)}", flush=True)

    async def _disconnect(self, server_id: str) -> None:
        client = self._clients.pop(server_id, None)
        self._server_tools.pop(server_id, None)
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                logger.warning("closing tool server failed: %s", exc)

    # ---- what the brain sees ------------------------------------------
    def _active_schemas(self) -> list[FunctionSchema]:
        disabled = self.store.disabled_builtin()
        schemas = [s for group in self._builtin.values() for s in group if s.name not in disabled]
        seen = {s.name for s in schemas}
        servers = {s["id"]: s for s in self.store.servers()}
        for server_id, tools in self._server_tools.items():
            off = set(servers.get(server_id, {}).get("disabled_tools", []))
            for tool in tools:
                if tool.name not in off and tool.name not in seen:
                    schemas.append(tool)
                    seen.add(tool.name)
        enabled = sum(1 for s in self.store.skills() if s["enabled"])
        if enabled:
            schemas.append(self._read_skill_schema())
        if enabled > SKILLS_INLINE_MAX:
            schemas.append(self._find_skills_schema())
        return schemas

    def _skills_prompt(self) -> str:
        skills = [s for s in self.store.skills() if s["enabled"]]
        if not skills:
            return ""
        if len(skills) > SKILLS_INLINE_MAX:
            return (f" You have {len(skills)} skills (written procedures for construction, estimating, "
                    f"scheduling, documents, data and more). When a request could use one, call find_skills "
                    f"with a few keywords, then read_skill with the best match's name, and follow it.")
        listing = "; ".join(f"{s['name']}: {s['description']}" for s in skills)
        return (f" Skills you have (call read_skill with the name to get the full instructions before "
                f"using one): {listing}.")

    @staticmethod
    def _find_skills_schema() -> FunctionSchema:
        return FunctionSchema(
            name=FIND_SKILLS,
            description="Search your skills library by keywords; returns the best-matching skill names and descriptions.",
            properties={"query": {"type": "string", "description": "A few keywords, e.g. 'RFI response' or 'cost estimate excel'."}},
            required=["query"],
        )

    def find_skills(self, query: str, limit: int = FIND_SKILLS_LIMIT) -> list[dict]:
        """Rank enabled skills by keyword overlap with ``query`` (name hits weigh more)."""
        words = [w for w in _WORD.findall((query or "").lower()) if w not in _STOP]
        if not words:
            return []
        scored = []
        for s in self.store.skills():
            if not s["enabled"]:
                continue
            name_words = set(_WORD.findall(s["name"].lower()))
            desc_words = _WORD.findall(s["description"].lower())
            desc_set = set(desc_words)
            score = 0.0
            for w in words:
                if w in name_words:
                    score += 3
                elif any(n.startswith(w) or w.startswith(n) for n in name_words if len(n) > 2 and len(w) > 2):
                    score += 2
                if w in desc_set:
                    score += 1
                elif len(w) > 3 and any(d.startswith(w[:5]) for d in desc_set):
                    score += 0.5
            if score:
                scored.append((score, s["name"], s["description"]))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [{"name": n, "description": d} for _, n, d in scored[:limit]]

    async def _find_skills(self, params: FunctionCallParams) -> None:
        query = str((params.arguments or {}).get("query", "")).strip()
        matches = await asyncio.to_thread(self.find_skills, query)
        if matches:
            await params.result_callback({"matches": matches})
        else:
            await params.result_callback({"matches": [], "note": "No skill matched; answer without one."})

    def _apply(self) -> None:
        self._context.set_tools(ToolsSchema(standard_tools=self._active_schemas()))
        if self._base_prompt and self._context.messages and self._context.messages[0].get("role") == "system":
            self._context.messages[0]["content"] = self._base_prompt + self._skills_prompt()

    @staticmethod
    def _read_skill_schema() -> FunctionSchema:
        return FunctionSchema(
            name=READ_SKILL,
            description="Get the full instructions of one of your skills by its exact name.",
            properties={"name": {"type": "string", "description": "The skill's name."}},
            required=["name"],
        )

    async def _read_skill(self, params: FunctionCallParams) -> None:
        name = str((params.arguments or {}).get("name", "")).strip()
        try:
            enabled = {s["name"] for s in self.store.skills() if s["enabled"]}
            if name not in enabled:
                raise KeyError(name)
            body = await asyncio.to_thread(self.store.skill_body, name)
            await params.result_callback({"name": name, "instructions": body})
        except KeyError:
            await params.result_callback({"error": f"No enabled skill named {name!r}."})

    # ---- changes from the dashboard ------------------------------------
    async def add_server(self, cfg: dict) -> dict:
        async with self._lock:
            server = self.store.add_server(cfg)
            await self._connect(server)
            self._apply()
            return server

    async def add_preset(self, preset_id: str) -> dict:
        async with self._lock:
            server = self.store.add_preset(preset_id)
            await self._connect(server)
            self._apply()
            return server

    async def test_server(self, server_id: str) -> list[dict]:
        return await probe_server(self.store.server(server_id), self.store)

    async def set_server_enabled(self, server_id: str, enabled: bool) -> dict:
        async with self._lock:
            server = self.store.update_server(server_id, {"enabled": enabled})
            await self._disconnect(server_id)
            if enabled:
                await self._connect(server)
            else:
                self._status[server_id] = {"state": "off"}
            self._apply()
            return server

    async def remove_server(self, server_id: str) -> None:
        async with self._lock:
            self.store.remove_server(server_id)
            await self._disconnect(server_id)
            self._status.pop(server_id, None)
            self._apply()

    async def set_tool_enabled(self, tool: str, enabled: bool) -> None:
        async with self._lock:
            for server_id, tools in self._server_tools.items():
                if any(t.name == tool for t in tools):
                    off = set(self.store.server(server_id).get("disabled_tools", []))
                    (off.discard if enabled else off.add)(tool)
                    self.store.update_server(server_id, {"disabled_tools": sorted(off)})
                    break
            else:
                if tool not in {s.name for g in self._builtin.values() for s in g}:
                    raise KeyError(tool)
                self.store.set_builtin_enabled(tool, enabled)
            self._apply()

    def refresh_skills(self) -> None:
        self._apply()

    # ---- read model for the page --------------------------------------
    def snapshot(self) -> dict:
        disabled = self.store.disabled_builtin()
        builtin = [{"group": group, "name": s.name, "description": (s.description or "")[:200],
                    "enabled": s.name not in disabled}
                   for group, schemas in self._builtin.items() for s in schemas]
        servers = []
        for s in self.store.servers():
            tools = self._server_tools.get(s["id"], [])
            off = set(s.get("disabled_tools", []))
            _found, missing = self.store.resolve_secrets(
                [*s.get("secret_env", []), *([s["auth_secret"]] if s.get("auth_secret") else [])]
            )
            target = s.get("url") or " ".join([os.path.basename(s.get("command", "")), *s.get("args", [])])
            servers.append({
                "id": s["id"], "name": s["name"], "transport": s["transport"], "enabled": s["enabled"],
                "preset": s.get("preset", ""), "target": target,
                "status": self._status.get(s["id"], {"state": "off"}), "missing_secrets": missing,
                "tools": [{"name": t.name, "description": (t.description or "")[:200], "enabled": t.name not in off}
                          for t in tools],
            })
        active = self._active_schemas()
        return {"builtin": builtin, "servers": servers, "skills": self.store.skills(),
                "secrets": self.store.secret_names(), "active_tool_count": len(active)}
