"""Memory page API: Facts (Obsidian memories) and People (profiles, photos, faces).

Mounted by ``dashboard.server.create_app``; every route requires the dashboard
token. Photos are validated, re-encoded (metadata stripped) and stored locally by
``PeopleStore``; face encodings are computed on this machine.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 15 * 1024 * 1024
MAX_PHOTOS_PER_UPLOAD = 12
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/octet-stream"}


class FactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class PersonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    relationship: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=160)
    role: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    notes: str = Field(default="", max_length=8000)
    facts: list[str] = Field(default_factory=list, max_length=100)


def add_memory_routes(app: FastAPI, *, authorized: Callable, ok: Callable, err: Callable, render_page: Callable,
                      memory=None, people=None) -> None:
    def deny():
        return err("UNAUTHORIZED", "Missing or invalid dashboard token.", 401)

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

    @app.get("/memory")
    async def memory_page():
        return render_page("memory.html")

    # ---------------------------------------------------------------- Facts
    def facts_editable():
        return memory is not None and hasattr(memory, "update") and hasattr(memory, "delete")

    @app.post("/api/memory")
    async def add_fact(request: Request):
        if not authorized(request):
            return deny()
        if memory is None:
            return err("MEMORY_DISABLED", "Memory is disabled.", 409)
        body, problem = await body_of(request, FactBody)
        if problem:
            return problem
        record = await asyncio.to_thread(memory.add, body.text.strip(), {"source": "dashboard"})
        return ok({"id": record.id, "text": record.text, "created_at": record.created_at}, 201)

    @app.put("/api/memory/{record_id}")
    async def edit_fact(record_id: str, request: Request):
        if not authorized(request):
            return deny()
        if not facts_editable():
            return err("NOT_SUPPORTED", "This memory backend can't edit facts.", 409)
        body, problem = await body_of(request, FactBody)
        if problem:
            return problem
        try:
            record = await asyncio.to_thread(memory.update, record_id, body.text.strip())
        except KeyError:
            return err("NOT_FOUND", "No such fact.", 404)
        return ok({"id": record.id, "text": record.text, "created_at": record.created_at})

    @app.delete("/api/memory/{record_id}")
    async def delete_fact(record_id: str, request: Request):
        if not authorized(request):
            return deny()
        if not facts_editable():
            return err("NOT_SUPPORTED", "This memory backend can't delete facts.", 409)
        try:
            await asyncio.to_thread(memory.delete, record_id)
        except KeyError:
            return err("NOT_FOUND", "No such fact.", 404)
        return ok({"deleted": record_id})

    # ---------------------------------------------------------------- People
    def no_people():
        return err("PEOPLE_DISABLED", "The people store is not available.", 409)

    def person_json(person) -> dict:
        data = person.as_dict()
        data["photos"] = [{"id": p.id, "has_face": p.has_face, "created_at": p.created_at} for p in person.photos]
        return data

    @app.get("/api/people")
    async def list_people(request: Request, q: str = Query(default="", max_length=200)):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        found = await asyncio.to_thread(people.list, q)
        return ok({"items": [person_json(p) for p in found], "total": len(found)})

    @app.post("/api/people")
    async def create_person(request: Request):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        body, problem = await body_of(request, PersonBody)
        if problem:
            return problem
        person = await asyncio.to_thread(people.create, body.model_dump())
        return ok(person_json(person), 201)

    @app.get("/api/people/{person_id}")
    async def get_person(person_id: str, request: Request):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        try:
            return ok(person_json(await asyncio.to_thread(people.get, person_id)))
        except KeyError:
            return err("NOT_FOUND", "No such person.", 404)

    @app.put("/api/people/{person_id}")
    async def update_person(person_id: str, request: Request):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        body, problem = await body_of(request, PersonBody)
        if problem:
            return problem
        try:
            person = await asyncio.to_thread(people.update, person_id, body.model_dump())
        except KeyError:
            return err("NOT_FOUND", "No such person.", 404)
        return ok(person_json(person))

    @app.delete("/api/people/{person_id}")
    async def delete_person(person_id: str, request: Request):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        try:
            await asyncio.to_thread(people.delete, person_id)
        except KeyError:
            return err("NOT_FOUND", "No such person.", 404)
        return ok({"deleted": person_id})

    async def read_upload(upload: UploadFile) -> bytes:
        data = await upload.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise ValueError(f"{upload.filename}: larger than 15 MB")
        if (upload.content_type or "application/octet-stream") not in ALLOWED_TYPES:
            raise ValueError(f"{upload.filename}: only JPG, PNG or WebP images")
        return data

    @app.post("/api/people/{person_id}/photos")
    async def upload_photos(person_id: str, request: Request, files: list[UploadFile] = File(...)):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        from people.faces import PhotoError, prepare_photo  # noqa: PLC0415 - heavy import, only when used

        if not files or len(files) > MAX_PHOTOS_PER_UPLOAD:
            return err("VALIDATION_ERROR", f"Send 1-{MAX_PHOTOS_PER_UPLOAD} photos at a time.", 400)
        try:
            await asyncio.to_thread(people.get, person_id)
        except KeyError:
            return err("NOT_FOUND", "No such person.", 404)
        results = []
        for upload in files:
            try:
                raw = await read_upload(upload)
                jpeg, encoding = await asyncio.to_thread(prepare_photo, raw)
            except (ValueError, PhotoError) as exc:
                results.append({"file": upload.filename, "ok": False, "error": str(exc)})
                continue
            photo = await asyncio.to_thread(people.add_photo, person_id, jpeg, encoding)
            results.append({"file": upload.filename, "ok": True, "id": photo.id, "has_face": photo.has_face})
        person = await asyncio.to_thread(people.get, person_id)
        return ok({"results": results, "person": person_json(person)}, 201)

    @app.get("/api/people/{person_id}/photos/{photo_id}")
    async def get_photo(person_id: str, photo_id: str, request: Request):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        try:
            path = await asyncio.to_thread(people.photo_path, person_id, photo_id)
        except KeyError:
            return err("NOT_FOUND", "No such photo.", 404)
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

    @app.delete("/api/people/{person_id}/photos/{photo_id}")
    async def delete_photo(person_id: str, photo_id: str, request: Request):
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        try:
            await asyncio.to_thread(people.delete_photo, person_id, photo_id)
        except KeyError:
            return err("NOT_FOUND", "No such photo.", 404)
        return ok({"deleted": photo_id})

    @app.post("/api/people/recognize")
    async def recognize_photo(request: Request, file: UploadFile = File(...)):
        """Run recognition on an uploaded photo (the People tab's 'Test recognition')."""
        if not authorized(request):
            return deny()
        if people is None:
            return no_people()
        from people.faces import PhotoError, decode_image, describe_faces, recognize  # noqa: PLC0415

        try:
            rgb = await asyncio.to_thread(decode_image, await read_upload(file))
        except (ValueError, PhotoError) as exc:
            return err("VALIDATION_ERROR", str(exc), 400)
        matches = await asyncio.to_thread(recognize, rgb, people.encodings())
        return ok({
            "summary": describe_faces(matches) or "No face found in this photo.",
            "faces": [{"name": m.name, "person_id": m.person_id, "confidence": m.confidence} for m in matches],
        })
