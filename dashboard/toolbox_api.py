"""Skills & Tools page API. Every route needs the dashboard token.

Secrets are write-only: the API accepts a value, stores it via ToolboxStore and
only ever returns secret *names*. Request bodies and errors never echo values.
"""

from __future__ import annotations

import asyncio

import io
import logging
import zipfile
from collections.abc import Callable

from fastapi import FastAPI, File, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from toolbox.store import presets

logger = logging.getLogger(__name__)

MAX_SKILL_BYTES = 512 * 1024
MAX_ZIP_BYTES = 5 * 1024 * 1024


class ServerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    transport: str = Field(pattern=r"^(stdio|http|sse)$")
    command: str = Field(default="", max_length=500)
    args: list[str] = Field(default_factory=list, max_length=40)
    cwd: str = Field(default="", max_length=500)
    url: str = Field(default="", max_length=500)
    secret_env: list[str] = Field(default_factory=list, max_length=20)
    auth_secret: str = Field(default="", max_length=64)


class ToggleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class SecretBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=64)
    value: str = Field(min_length=1, max_length=8000, repr=False)


def skill_files_from_upload(filename: str, data: bytes) -> list[tuple[str, str]]:
    """``[(source, SKILL.md text)]`` from a SKILL.md file or a .zip of skill folders."""
    if filename.lower().endswith(".zip"):
        if len(data) > MAX_ZIP_BYTES:
            raise ValueError("Zip is larger than 5 MB.")
        found = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.filename.replace("\\", "/").split("/")[-1] == "SKILL.md" and info.file_size <= MAX_SKILL_BYTES:
                    found.append((f"{filename}:{info.filename}", archive.read(info).decode("utf-8", "replace")))
        if not found:
            raise ValueError("No SKILL.md found inside the zip.")
        return found
    if len(data) > MAX_SKILL_BYTES:
        raise ValueError("SKILL.md is larger than 512 KB.")
    return [(filename, data.decode("utf-8", "replace"))]


def add_toolbox_routes(app: FastAPI, *, authorized: Callable, ok: Callable, err: Callable,
                       render_page: Callable, toolbox=None) -> None:
    def deny():
        return err("UNAUTHORIZED", "Missing or invalid dashboard token.", 401)

    def unavailable():
        return err("TOOLBOX_DISABLED", "The toolbox is not running.", 409)

    async def body_of(request: Request, model):
        try:
            payload = await request.json()
        except ValueError:
            return None, err("BAD_JSON", "Request body must be JSON.", 400)
        try:
            return model.model_validate(payload), None
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(p) for p in first.get("loc", ())) or "body"
            return None, err("VALIDATION_ERROR", f"{field}: {first.get('msg', 'invalid')}", 400)

    async def guarded(request: Request, action):
        if not authorized(request):
            return deny()
        if toolbox is None:
            return unavailable()
        try:
            return await action()
        except KeyError:
            return err("NOT_FOUND", "Not found.", 404)
        except ValueError as exc:
            return err("INVALID", str(exc), 422)

    @app.get("/tools")
    async def tools_page():
        return render_page("tools.html")

    @app.get("/api/toolbox")
    async def snapshot(request: Request):
        async def action():
            catalog = [{"id": pid, "name": p["name"], "about": p["about"], "needs": p["needs"],
                        "added": any(s.get("preset") == pid for s in toolbox.store.servers())}
                       for pid, p in presets().items()]
            return ok({**toolbox.snapshot(), "catalog": catalog, "skills_folder": str(toolbox.store.skills_dir)})
        return await guarded(request, action)

    @app.post("/api/toolbox/servers")
    async def add_server(request: Request):
        async def action():
            body, problem = await body_of(request, ServerBody)
            if problem:
                return problem
            server = await toolbox.add_server(body.model_dump())
            return ok({"id": server["id"]}, 201)
        return await guarded(request, action)

    @app.post("/api/toolbox/presets/{preset_id}")
    async def add_preset(preset_id: str, request: Request):
        async def action():
            server = await toolbox.add_preset(preset_id)
            return ok({"id": server["id"]}, 201)
        return await guarded(request, action)

    @app.post("/api/toolbox/servers/{server_id}/test")
    async def test_server(server_id: str, request: Request):
        async def action():
            try:
                tools = await toolbox.test_server(server_id)
            except (KeyError, ValueError):
                raise
            except Exception as exc:  # connection failures are an answer, not a server error
                return ok({"ok": False, "error": (str(exc) or type(exc).__name__)[:300], "tools": []})
            return ok({"ok": True, "tools": tools})
        return await guarded(request, action)

    @app.put("/api/toolbox/servers/{server_id}")
    async def toggle_server(server_id: str, request: Request):
        async def action():
            body, problem = await body_of(request, ToggleBody)
            if problem:
                return problem
            await toolbox.set_server_enabled(server_id, body.enabled)
            return ok({"enabled": body.enabled})
        return await guarded(request, action)

    @app.delete("/api/toolbox/servers/{server_id}")
    async def remove_server(server_id: str, request: Request):
        async def action():
            await toolbox.remove_server(server_id)
            return ok({"deleted": server_id})
        return await guarded(request, action)

    @app.put("/api/toolbox/tools/{tool}")
    async def toggle_tool(tool: str, request: Request):
        async def action():
            body, problem = await body_of(request, ToggleBody)
            if problem:
                return problem
            await toolbox.set_tool_enabled(tool, body.enabled)
            return ok({"tool": tool, "enabled": body.enabled})
        return await guarded(request, action)

    @app.post("/api/toolbox/skills")
    async def import_skills(request: Request, files: list[UploadFile] = File(...)):
        async def action():
            imported, problems = [], []
            for upload in files[:20]:
                data = await upload.read(MAX_ZIP_BYTES + 1)
                try:
                    for source, text in skill_files_from_upload(upload.filename or "SKILL.md", data):
                        try:
                            imported.append(toolbox.store.import_skill(text, source=source)["name"])
                        except ValueError as exc:
                            problems.append(f"{source}: {exc}")
                except (ValueError, zipfile.BadZipFile) as exc:
                    problems.append(f"{upload.filename}: {exc}")
            toolbox.refresh_skills()
            return ok({"imported": imported, "problems": problems}, 201 if imported else 200)
        return await guarded(request, action)

    @app.post("/api/toolbox/skills/rescan")
    async def rescan_skills(request: Request):
        async def action():
            result = await asyncio.to_thread(toolbox.store.scan_skill_folder)
            if result["imported"]:
                toolbox.refresh_skills()
            return ok({**result, "folder": str(toolbox.store.skills_dir)})
        return await guarded(request, action)

    @app.put("/api/toolbox/skills/{name}")
    async def toggle_skill(name: str, request: Request):
        async def action():
            body, problem = await body_of(request, ToggleBody)
            if problem:
                return problem
            toolbox.store.set_skill_enabled(name, body.enabled)
            toolbox.refresh_skills()
            return ok({"name": name, "enabled": body.enabled})
        return await guarded(request, action)

    @app.delete("/api/toolbox/skills/{name}")
    async def remove_skill(name: str, request: Request):
        async def action():
            toolbox.store.remove_skill(name)
            toolbox.refresh_skills()
            return ok({"deleted": name})
        return await guarded(request, action)

    @app.post("/api/toolbox/secrets")
    async def set_secret(request: Request):
        async def action():
            body, problem = await body_of(request, SecretBody)
            if problem:
                return problem
            toolbox.store.set_secret(body.name, body.value)
            logger.info("dashboard: secret %s set", body.name)  # name only, never the value
            return ok({"name": body.name, "set": True}, 201)
        return await guarded(request, action)

    @app.delete("/api/toolbox/secrets/{name}")
    async def delete_secret(name: str, request: Request):
        async def action():
            toolbox.store.delete_secret(name)
            return ok({"deleted": name})
        return await guarded(request, action)
