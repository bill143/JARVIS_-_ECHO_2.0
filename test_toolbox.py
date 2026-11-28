"""Tests for the Skills & Tools system: store, live MCP runtime, API, page.

Uses the real read-only Documents MCP server (stdio) against a temp folder.
Run:  python test_toolbox.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.aggregators.llm_context import LLMContext

from dashboard.bus import EventBus
from dashboard.server import TOKEN_HEADER, create_app
from toolbox.runtime import ToolboxRuntime
from toolbox.store import ToolboxStore, parse_skill_md

TOKEN = "toolbox-test-token"
HOST = {"host": "127.0.0.1:8090"}
AUTH = {**HOST, TOKEN_HEADER: TOKEN}
REPO = str(Path(__file__).resolve().parent)
SKILL = """---
name: rfi-writer
description: Draft a construction RFI from a short spoken question.
---
1. Ask for the spec section if missing.
2. Write: Subject, Question, Suggested resolution.
"""
SECRET_VALUE = "super-secret-value-123"


def docs_server(root: str, name: str = "Docs test") -> dict:
    return {"name": name, "transport": "stdio", "command": sys.executable,
            "args": ["-m", "mcp_servers.documents_server", root], "cwd": REPO}


class FakeLLM:
    def __init__(self) -> None:
        self.fns = {}

    def register_function(self, name, handler, **_kw) -> None:
        self.fns[name] = handler


def clock_schema() -> FunctionSchema:
    return FunctionSchema(name="get_current_time", description="clock", properties={}, required=[])


def context_tool_names(context: LLMContext) -> list[str]:
    tools = context.tools
    return [t.name for t in tools.standard_tools] if isinstance(tools, ToolsSchema) else []


# ---------------------------------------------------------------- store
def test_store_presets_validation_secrets_skills() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = ToolboxStore(Path(d))
        assert {s["preset"] for s in store.servers()} == {"documents", "fetch"}, "free tools pre-wired"
        for bad, msg in [({"name": "", "transport": "stdio", "command": "x"}, "Name"),
                         ({"name": "a", "transport": "ftp"}, "Type"),
                         ({"name": "a", "transport": "stdio"}, "command"),
                         ({"name": "a", "transport": "http", "url": "file:///x"}, "URL"),
                         ({"name": "a", "transport": "stdio", "command": "x", "secret_env": ["bad name"]}, "Secret")]:
            try:
                store.add_server(bad)
            except ValueError as exc:
                assert msg in str(exc), (bad, exc)
            else:
                raise AssertionError(f"accepted {bad}")
        store.set_secret("GITHUB_TOKEN", SECRET_VALUE)
        assert store.secret_names() == ["GITHUB_TOKEN"]
        assert SECRET_VALUE not in (Path(d) / "config.json").read_text(encoding="utf-8")
        assert store.resolve_secrets(["GITHUB_TOKEN", "MISSING_ONE"]) == ({"GITHUB_TOKEN": SECRET_VALUE}, ["MISSING_ONE"])
        assert parse_skill_md(SKILL)[0]["name"] == "rfi-writer"
        for bad in ["no frontmatter", "---\nname: Bad Name\ndescription: x\n---\nbody", "---\nname: ok\n---\nbody",
                    "---\nname: ok\ndescription: x\n---\n"]:
            try:
                parse_skill_md(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted bad skill {bad!r}")
        store.import_skill(SKILL)
        assert "Suggested resolution" in store.skill_body("rfi-writer")
        store.set_skill_enabled("rfi-writer", False)
        store.remove_skill("rfi-writer")
        assert store.skills() == []


# ---------------------------------------------------------------- live runtime
def test_runtime_adds_server_live_and_switches_tools() -> None:
    async def scenario(tmp: Path) -> None:
        docs = tmp / "docs"
        docs.mkdir()
        (docs / "punch-list.txt").write_text("Bay 7: replace damaged door closer.", encoding="utf-8")
        store = ToolboxStore(tmp / "toolbox", seed_presets=False)
        llm = FakeLLM()
        context = LLMContext(messages=[{"role": "system", "content": "BASE."}],
                             tools=ToolsSchema(standard_tools=[clock_schema()]))
        runtime = ToolboxRuntime(llm, context, store, {"Clock": [clock_schema()]}, base_prompt="BASE.")
        await runtime.start()
        try:
            assert context_tool_names(context) == ["get_current_time"]
            server = await runtime.add_server(docs_server(str(docs)))
            names = context_tool_names(context)
            assert {"list_directory", "read_text_file", "search_files"} <= set(names), names
            assert "read_text_file" in llm.fns, "tool handler registered on the brain"
            tested = [t["name"] for t in await runtime.test_server(server["id"])]
            assert tested == ["list_directory", "read_text_file", "search_files"], tested
            await runtime.set_tool_enabled("search_files", False)
            assert "search_files" not in context_tool_names(context)
            await runtime.set_tool_enabled("get_current_time", False)
            assert "get_current_time" not in context_tool_names(context)
            store.import_skill(SKILL)
            runtime.refresh_skills()
            assert "read_skill" in context_tool_names(context)
            system = context.messages[0]["content"]
            assert "rfi-writer" in system and system.startswith("BASE.")
            await runtime.set_server_enabled(server["id"], False)
            assert "read_text_file" not in context_tool_names(context)
            assert runtime.snapshot()["servers"][0]["status"]["state"] == "off"
            await runtime.remove_server(server["id"])
            assert store.servers() == []
        finally:
            await runtime.close()

    with tempfile.TemporaryDirectory() as d:
        asyncio.run(scenario(Path(d)))


def test_documents_server_is_read_only_and_jailed() -> None:
    async def scenario(tmp: Path) -> None:
        from pipecat.services.mcp_service import MCPClient  # noqa: PLC0415

        from toolbox.runtime import server_params  # noqa: PLC0415

        (tmp / "inside.txt").write_text("hello from inside", encoding="utf-8")
        (tmp.parent / "outside-secret.txt").write_text("nope", encoding="utf-8")
        store = ToolboxStore(tmp / ".tb", seed_presets=False)
        client = MCPClient(server_params=server_params({**docs_server(str(tmp)), "secret_env": []}, store))
        await client.start()
        try:
            assert "hello from inside" in await client._call_tool_text("read_text_file", {"path": "inside.txt"})
            escaped = await client._call_tool_text("read_text_file", {"path": "../outside-secret.txt"})
            assert "nope" not in escaped and "outside" in escaped.lower(), escaped
            tool_names = [t.name for t in (await client.get_tools_schema()).standard_tools]
            assert not any(w in n for n in tool_names for w in ("write", "delete", "move", "create")), tool_names
        finally:
            await client.close()

    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "root"
        root.mkdir()
        asyncio.run(scenario(root))


# ---------------------------------------------------------------- API + page
class _Controller:
    def models(self):
        return ["brain"]

    async def say(self, text):
        pass

    async def set_muted(self, muted):
        pass

    async def look(self, source):
        pass

    async def set_model(self, model):
        pass

    async def stop(self):
        pass


def test_api_and_page() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "docs").mkdir()
        store = ToolboxStore(tmp / "toolbox", seed_presets=False)
        context = LLMContext(messages=[{"role": "system", "content": "BASE."}])
        runtime = ToolboxRuntime(FakeLLM(), context, store, {"Clock": [clock_schema()]}, base_prompt="BASE.")
        with TestClient(create_app(EventBus(), _Controller(), toolbox=runtime, port=8090, token=TOKEN)) as client:
            page = client.get("/tools", headers=HOST)
            assert page.status_code == 200 and TOKEN in page.text and "tools.js?v=" in page.text
            assert client.get("/api/toolbox", headers=HOST).status_code == 401
            snap = client.get("/api/toolbox", headers=AUTH).json()["data"]
            assert {c["id"] for c in snap["catalog"]} >= {"documents", "fetch", "gmail", "google_calendar"}
            assert snap["builtin"][0]["name"] == "get_current_time"
            bad = client.post("/api/toolbox/secrets", json={"name": "bad", "value": "x"}, headers=AUTH)
            assert bad.status_code in (400, 422)
            saved = client.post("/api/toolbox/secrets", json={"name": "API_TOKEN", "value": SECRET_VALUE}, headers=AUTH)
            assert saved.status_code == 201 and SECRET_VALUE not in saved.text
            body = client.get("/api/toolbox", headers=AUTH).text
            assert "API_TOKEN" in body and SECRET_VALUE not in body, "secret values must never be returned"
            added = client.post("/api/toolbox/servers", json=docs_server(str(tmp / "docs")), headers=AUTH)
            assert added.status_code == 201, added.text
            sid = added.json()["data"]["id"]
            servers = client.get("/api/toolbox", headers=AUTH).json()["data"]["servers"]
            server = next(s for s in servers if s["id"] == sid)
            assert server["status"]["state"] == "connected" and len(server["tools"]) == 3, server
            tested = client.post(f"/api/toolbox/servers/{sid}/test", json={}, headers=AUTH).json()["data"]
            assert tested["ok"] and len(tested["tools"]) == 3
            assert client.put("/api/toolbox/tools/search_files", json={"enabled": False}, headers=AUTH).status_code == 200
            assert client.put("/api/toolbox/tools/nope", json={"enabled": False}, headers=AUTH).status_code == 404
            files = [("files", ("SKILL.md", SKILL.encode(), "text/markdown")),
                     ("files", ("bad.md", b"no frontmatter", "text/markdown"))]
            imported = client.post("/api/toolbox/skills", files=files, headers=AUTH).json()["data"]
            assert imported["imported"] == ["rfi-writer"] and len(imported["problems"]) == 1
            assert client.delete(f"/api/toolbox/servers/{sid}", headers=AUTH).status_code == 200
        config = json.loads((tmp / "toolbox" / "config.json").read_text(encoding="utf-8"))
        assert SECRET_VALUE not in json.dumps(config)


def _skill_md(name: str) -> str:
    return chr(10).join(["---", f"name: {name}", f"description: Test skill {name}.", "---", f"Do the {name} thing.", ""])


def test_skills_folder_scan_nested_and_zip() -> None:
    import zipfile

    with tempfile.TemporaryDirectory() as tmp:
        store = ToolboxStore(Path(tmp), seed_presets=False)
        drop = store.skills_dir
        (drop / "single-skill").mkdir()
        (drop / "single-skill" / "SKILL.md").write_text(_skill_md("single-skill"), encoding="utf-8")
        pack = drop / "My Skill Pack" / "estimating"          # folder of skill folders
        (pack / "takeoff-helper").mkdir(parents=True)
        (pack / "takeoff-helper" / "SKILL.md").write_text(_skill_md("takeoff-helper"), encoding="utf-8")
        (drop / "broken").mkdir()
        (drop / "broken" / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")
        with zipfile.ZipFile(drop / "bundle.zip", "w") as z:
            z.writestr("bundle/zip-skill-one/SKILL.md", _skill_md("zip-skill-one"))
            z.writestr("bundle/zip-skill-two/SKILL.md", _skill_md("zip-skill-two"))
            z.writestr("__MACOSX/bundle/._SKILL.md", "junk")
            z.writestr("../escape/SKILL.md", _skill_md("escape-attempt"))   # read in memory only

        first = store.scan_skill_folder()
        names = sorted(first["imported"])
        assert names == ["escape-attempt", "single-skill", "takeoff-helper", "zip-skill-one", "zip-skill-two"], first
        assert any("broken/SKILL.md" in p for p in first["problems"]), first["problems"]
        assert not (Path(tmp).parent / "escape").exists()  # nothing written outside the store
        assert {s["name"] for s in store.skills()} >= set(names)
        assert "Do the takeoff-helper thing." in store.skill_body("takeoff-helper")

        second = store.scan_skill_folder()      # safe to repeat
        assert second["imported"] == second["updated"] == second["removed"] == [], second
        sig = store.folder_signature()
        assert sig == store.folder_signature()  # stable when nothing changes

        # an edited dropped skill is re-imported, keeping its on/off switch
        store.set_skill_enabled("takeoff-helper", False)
        edited = _skill_md("takeoff-helper").replace("Test skill", "Edited skill")
        (pack / "takeoff-helper" / "SKILL.md").write_text(edited, encoding="utf-8")
        assert store.folder_signature() != sig
        third = store.scan_skill_folder()
        assert third["updated"] == ["takeoff-helper"], third
        entry = next(x for x in store.skills() if x["name"] == "takeoff-helper")
        assert entry["description"].startswith("Edited") and entry["enabled"] is False

        # removing the pack, the zip and a skill folder drops those skills
        import shutil
        shutil.rmtree(drop / "My Skill Pack")
        (drop / "bundle.zip").unlink()
        shutil.rmtree(drop / "single-skill")
        fourth = store.scan_skill_folder()
        assert sorted(fourth["removed"]) == ["escape-attempt", "single-skill", "takeoff-helper", "zip-skill-one", "zip-skill-two"], fourth
        assert store.skills() == []


def test_large_skill_library_uses_search_not_prompt() -> None:
    import types

    from toolbox import runtime as rt

    with tempfile.TemporaryDirectory() as tmp:
        store = ToolboxStore(Path(tmp), seed_presets=False)
        fake = types.SimpleNamespace(store=store)
        store.import_skill(_skill_md("rfi-drafter").replace("Test skill rfi-drafter", "Draft a construction RFI"))
        small = rt.ToolboxRuntime._skills_prompt(fake)
        assert "rfi-drafter" in small and "find_skills" not in small  # few skills: listed inline
        for i in range(rt.SKILLS_INLINE_MAX + 5):
            store.import_skill(_skill_md(f"filler-skill-{i}"))
        big = rt.ToolboxRuntime._skills_prompt(fake)
        assert "find_skills" in big and "filler-skill-3" not in big and len(big) < 400, big
        hits = [m["name"] for m in rt.ToolboxRuntime.find_skills(fake, "please draft an RFI")]
        assert hits and hits[0] == "rfi-drafter", hits
        assert rt.ToolboxRuntime.find_skills(fake, "the and of") == []


TESTS = [
    ("store: presets, validation, write-only secrets, skills", test_store_presets_validation_secrets_skills),
    ("runtime: add server live -> brain has its tools; switches", test_runtime_adds_server_live_and_switches_tools),
    ("documents server is read-only and jailed to its folder", test_documents_server_is_read_only_and_jailed),
    ("API + /tools page (no secret ever returned)", test_api_and_page),
    ("skills folder: nested + zips load, edits update, deletions remove", test_skills_folder_scan_nested_and_zip),
    ("big skill library: search tool instead of listing all in the prompt", test_large_skill_library_uses_search_not_prompt),
]

if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    passed = 0
    for label, fn in TESTS:
        try:
            fn()
            passed += 1
            print(f"  ok - {label}")
        except Exception as exc:
            print(f"  FAIL - {label}: {exc!r}")
    print(f"\ntoolbox: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
