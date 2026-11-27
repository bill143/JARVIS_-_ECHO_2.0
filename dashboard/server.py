"""FastAPI app for the JARVIS dashboard: REST controls + a WebSocket event stream.

Security model (it is a local app, but any web page can fire requests at
127.0.0.1): the server binds to 127.0.0.1 only, rejects foreign ``Host``
headers (DNS rebinding), and requires a random per-launch token on every API
call and on the WebSocket. Only the page this server renders gets the token.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from pathlib import Path
from typing import Any, Literal, Protocol

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dashboard.bus import EventBus
from dashboard.memory_api import add_memory_routes

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
TOKEN_HEADER = "X-JARVIS-Token"
TOKEN_PLACEHOLDER = "__JARVIS_TOKEN__"
STATIC_ASSETS = ("app.css", "app.js", "memory.css", "memory.js")
MAX_SAY_CHARS = 2000
MEMORY_LIMIT_MAX = 200


class DashboardController(Protocol):
    """What the dashboard can ask the running assistant to do."""

    def models(self) -> list[str]: ...
    async def say(self, text: str) -> None: ...
    async def set_muted(self, muted: bool) -> None: ...
    async def look(self, source: Literal["camera", "screen"]) -> None: ...
    async def set_model(self, model: str) -> None: ...
    async def stop(self) -> None: ...


class SayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_SAY_CHARS)


class MuteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    muted: bool


class LookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["camera", "screen"]


class ModelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=100)


def _ok(data: Any = None, status: int = 200) -> JSONResponse:
    return JSONResponse({"success": True, "data": data}, status_code=status)


def _err(code: str, message: str, status: int) -> JSONResponse:
    request_id = uuid.uuid4().hex[:12]
    logger.info("dashboard %s %s (request %s)", status, code, request_id)
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message, "requestId": request_id}},
        status_code=status,
    )


def create_app(
    bus: EventBus,
    controller: DashboardController,
    memory=None,
    *,
    people=None,
    port: int = 8090,
    token: str | None = None,
) -> FastAPI:
    token = token or secrets.token_urlsafe(32)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    allowed_origins = {f"http://{h}" for h in allowed_hosts}
    app = FastAPI(title="JARVIS dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token

    def _authorized(request: Request) -> bool:
        return secrets.compare_digest(request.headers.get(TOKEN_HEADER, ""), token)

    @app.middleware("http")
    async def host_guard(request: Request, call_next):
        if request.headers.get("host", "") not in allowed_hosts:
            return _err("BAD_HOST", "Unknown host.", 403)
        return await call_next(request)

    def render_page(filename: str) -> HTMLResponse:
        html = (STATIC_DIR / filename).read_text(encoding="utf-8")
        # Cache-bust assets so an updated JARVIS never runs a stale cached UI.
        for asset in STATIC_ASSETS:
            if f"/static/{asset}\"" in html:
                version = int((STATIC_DIR / asset).stat().st_mtime)
                html = html.replace(f"/static/{asset}\"", f"/static/{asset}?v={version}\"")
        ws_sources = " ".join(f"ws://{h}" for h in sorted(allowed_hosts))
        headers = {
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
                f"connect-src 'self' {ws_sources}; frame-ancestors 'none'; base-uri 'none'; "
                "form-action 'self'; object-src 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
        }
        return HTMLResponse(html.replace(TOKEN_PLACEHOLDER, token), headers=headers)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return render_page("index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    add_memory_routes(
        app, authorized=_authorized, ok=_ok, err=_err, render_page=render_page, memory=memory, people=people
    )

    @app.get("/api/state")
    async def state(request: Request):
        if not _authorized(request):
            return _err("UNAUTHORIZED", "Missing or invalid dashboard token.", 401)
        return _ok({**bus.snapshot(), "models": controller.models()})

    @app.get("/api/memory")
    async def memory_list(
        request: Request,
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=50, ge=1, le=MEMORY_LIMIT_MAX),
    ):
        if not _authorized(request):
            return _err("UNAUTHORIZED", "Missing or invalid dashboard token.", 401)
        if memory is None:
            return _ok({"enabled": False, "items": [], "total": 0})
        query = q.strip()
        try:
            if query:
                records = await asyncio.to_thread(memory.search, query, limit)
            else:
                records = await asyncio.to_thread(memory.recent, limit)
            total = await asyncio.to_thread(memory.count)
        except Exception as exc:
            logger.warning("memory read failed: %s", exc)
            return _err("MEMORY_UNAVAILABLE", "Could not read the memory store.", 500)
        items = [{"id": r.id, "text": r.text, "created_at": r.created_at} for r in records]
        return _ok({"enabled": True, "items": items, "total": total})

    async def _control(request: Request, body_model, action):
        if not _authorized(request):
            return _err("UNAUTHORIZED", "Missing or invalid dashboard token.", 401)
        try:
            payload = await request.json()
        except ValueError:
            return _err("BAD_JSON", "Request body must be JSON.", 400)
        try:
            body = body_model.model_validate(payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(p) for p in first.get("loc", ())) or "body"
            return _err("VALIDATION_ERROR", f"{field}: {first.get('msg', 'invalid')}", 400)
        try:
            result = await action(body)
        except ValueError as exc:
            return _err("INVALID", str(exc), 422)
        except Exception as exc:
            logger.warning("dashboard control failed: %s", exc)
            return _err("CONTROL_FAILED", "JARVIS could not do that.", 500)
        return _ok(result)

    @app.post("/api/say")
    async def say(request: Request):
        async def act(body: SayBody):
            await controller.say(body.text.strip())
            return {"queued": True}

        return await _control(request, SayBody, act)

    @app.post("/api/stop")
    async def stop(request: Request):
        if not _authorized(request):
            return _err("UNAUTHORIZED", "Missing or invalid dashboard token.", 401)
        try:
            await controller.stop()
        except Exception as exc:
            logger.warning("stop failed: %s", exc)
            return _err("CONTROL_FAILED", "JARVIS could not stop.", 500)
        return _ok({"stopped": True})

    @app.post("/api/mute")
    async def mute(request: Request):
        async def act(body: MuteBody):
            await controller.set_muted(body.muted)
            return {"muted": body.muted}

        return await _control(request, MuteBody, act)

    @app.post("/api/look")
    async def look(request: Request):
        async def act(body: LookBody):
            await controller.look(body.source)
            return {"queued": True}

        return await _control(request, LookBody, act)

    @app.post("/api/model")
    async def model(request: Request):
        async def act(body: ModelBody):
            if body.model not in controller.models():
                raise ValueError(f"Unknown model {body.model!r}.")
            await controller.set_model(body.model)
            return {"model": body.model}

        return await _control(request, ModelBody, act)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin")
        host_ok = websocket.headers.get("host", "") in allowed_hosts
        token_ok = secrets.compare_digest(websocket.query_params.get("token", ""), token)
        if not host_ok or not token_ok or (origin is not None and origin not in allowed_origins):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        queue = bus.subscribe()
        try:
            await websocket.send_json({"type": "snapshot", **bus.snapshot(), "models": controller.models()})
            while True:
                await websocket.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            bus.unsubscribe(queue)

    return app
