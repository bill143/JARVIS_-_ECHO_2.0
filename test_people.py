"""Tests for People (store, API, photos, offline recognition, brain tools) and the /memory page.

Uses scikit-image's public-domain NASA "astronaut" portrait as the known face
(test dependency: ``pip install scikit-image``). Run:  python test_people.py
"""

from __future__ import annotations

import asyncio
import tempfile
import warnings
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from dashboard.bus import EventBus
from dashboard.server import TOKEN_HEADER, create_app
from memory.obsidian import ObsidianMemory
from people.faces import MATCH_DISTANCE, FaceMatch, decode_image, describe_faces, prepare_photo, recognize
from people.store import PeopleStore
from people_tools import people_index, register_people_tools

TOKEN = "people-test-token"
HOST = {"host": "127.0.0.1:8090"}
AUTH = {**HOST, TOKEN_HEADER: TOKEN}


def _png(rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", rgb[:, :, ::-1])
    assert ok
    return buf.tobytes()


def astronaut_png() -> bytes:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from skimage import data  # noqa: PLC0415
    return _png(np.ascontiguousarray(data.astronaut()[:, :, :3]))


def astronaut_variant_png() -> bytes:
    """A different 'photo' of the same person: mirrored, brighter, re-scaled."""
    rgb = decode_image(astronaut_png())
    rgb = np.ascontiguousarray(rgb[:, ::-1])
    rgb = np.clip(rgb.astype(np.int16) + 25, 0, 255).astype(np.uint8)
    rgb = cv2.resize(rgb, (430, 430), interpolation=cv2.INTER_AREA)
    return _png(rgb)


def no_face_png() -> bytes:
    rng = np.random.default_rng(7)
    return _png((rng.random((200, 300, 3)) * 255).astype(np.uint8))


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


def make_client(tmp: Path):
    store = PeopleStore(data_dir=tmp / "data", vault=tmp / "vault")
    memory = ObsidianMemory(tmp / "vault")
    client = TestClient(create_app(EventBus(), _Controller(), memory, people=store, port=8090, token=TOKEN))
    return store, memory, client


# ---------------------------------------------------------------- store
def test_store_crud_softdelete_and_mirror() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        store = PeopleStore(data_dir=tmp / "data", vault=tmp / "vault")
        mike = store.create({"name": "Mike Rowe", "relationship": "foreman", "company": "ABC Concrete",
                             "role": "Superintendent", "phone": "555-0100", "facts": ["Drives a blue F-250", ""]})
        note = tmp / "vault" / "JARVIS" / "People" / "Mike Rowe.md"
        assert note.exists() and "Superintendent" in note.read_text(encoding="utf-8")
        assert mike.facts == ["Drives a blue F-250"]
        assert [p.name for p in store.find("mike")] == ["Mike Rowe"]
        renamed = store.update(mike.id, {"name": "Michael Rowe"})
        assert renamed.phone == "555-0100", "partial update must keep other fields"
        assert not note.exists() and (note.parent / "Michael Rowe.md").exists()
        store.delete(mike.id)
        assert store.list() == [] and store.find("michael") == []
        assert not (note.parent / "Michael Rowe.md").exists()
        try:
            store.get(mike.id)
        except KeyError:
            pass
        else:
            raise AssertionError("deleted person still readable")
        store.close()


def test_groups_migration_keeps_people_and_files_by_relationship() -> None:
    import sqlite3

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        old = PeopleStore(data_dir=tmp / "data", vault=None)  # create the schema
        old.close()
        db = sqlite3.connect(tmp / "data" / "people.db")
        db.execute("DROP TABLE person_groups")  # simulate a database from before groups existed
        db.execute("DROP TABLE groups")
        db.execute("DROP TABLE meta")
        rows = [("a1", "Ann Worker", "Coworker"), ("b2", "Bea Spouse", "wife"), ("c3", "Cal Pal", "friend"),
                ("d4", "Dan Prop", "rugby teammate"), ("e5", "Eve Client", "client")]
        for pid, name, rel in rows:
            db.execute("INSERT INTO people (id, name, relationship, created_at, updated_at) VALUES (?,?,?,?,?)",
                       (pid, name, rel, "2026-11-27T00:00:00+00:00", "2026-11-27T00:00:00+00:00"))
        db.commit()
        db.close()

        store = PeopleStore(data_dir=tmp / "data", vault=tmp / "vault")
        counts = {g["name"]: g["count"] for g in store.groups()}
        assert counts == {"Coworkers": 1, "Family": 1, "Friends": 1, "Rugby": 1}, counts
        assert len(store.list()) == 5 and store.get("e5").groups == []  # nobody lost, client left ungrouped
        note = (tmp / "vault" / "JARVIS" / "People" / "Ann Worker.md").read_text(encoding="utf-8")
        assert "tags: [person, coworkers]" in note and "**Groups:** Coworkers" in note
        store.close()
        again = PeopleStore(data_dir=tmp / "data", vault=None)  # migration runs once only
        assert len(again.groups()) == 4
        again.close()


def test_groups_api_create_assign_filter_rename_delete() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        store, _memory, client = make_client(tmp)
        a = client.post("/api/people", json={"name": "Al Adams", "relationship": "Coworker"}, headers=AUTH).json()["data"]
        b = client.post("/api/people", json={"name": "Bo Brown"}, headers=AUTH).json()["data"]
        groups = {g["name"]: g for g in client.get("/api/people/groups", headers=AUTH).json()["data"]["items"]}
        assert set(groups) == {"Coworkers", "Friends", "Family", "Rugby"}

        golf = client.post("/api/people/groups", json={"name": "Golf"}, headers=AUTH).json()["data"]
        dup = client.post("/api/people/groups", json={"name": "golf"}, headers=AUTH)
        assert dup.status_code == 409  # names are unique, case-insensitive
        r = client.post(f"/api/people/groups/{golf['id']}/members", json={"person_ids": [a["id"], b["id"]]}, headers=AUTH)
        assert r.json()["data"]["added"] == 2
        listed = client.get("/api/people", params={"group": golf["id"]}, headers=AUTH).json()["data"]
        assert [p["name"] for p in listed["items"]] == ["Al Adams", "Bo Brown"]
        assert {g["name"]: g["count"] for g in listed["groups"]}["Golf"] == 2
        searched = client.get("/api/people", params={"group": golf["id"], "q": "bo"}, headers=AUTH).json()["data"]
        assert [p["name"] for p in searched["items"]] == ["Bo Brown"]  # filter + search combine

        # edit form: exact multi-select (Bo leaves Golf, joins Friends)
        body = {"name": "Bo Brown", "groups": [groups["Friends"]["id"]]}
        bo = client.put(f"/api/people/{b['id']}", json=body, headers=AUTH).json()["data"]
        assert bo["groups"] == [groups["Friends"]["id"]]

        renamed = client.put(f"/api/people/groups/{golf['id']}", json={"name": "Golf Club"}, headers=AUTH).json()["data"]
        assert renamed["name"] == "Golf Club"
        note = (tmp / "vault" / "JARVIS" / "People" / "Al Adams.md").read_text(encoding="utf-8")
        assert "golf-club" in note and "coworkers" in note

        assert client.delete(f"/api/people/groups/{golf['id']}", headers=AUTH).status_code == 200
        people = client.get("/api/people", headers=AUTH).json()["data"]
        assert people["total"] == 2 and golf["id"] not in [g["id"] for g in people["groups"]]  # people kept
        assert client.get("/api/people", params={"group": golf["id"]}, headers=AUTH).json()["data"]["items"] == []
        assert "golf" not in (tmp / "vault" / "JARVIS" / "People" / "Al Adams.md").read_text(encoding="utf-8")
        assert client.delete(f"/api/people/groups/{golf['id']}", headers=AUTH).status_code == 404
        store.close()


# ---------------------------------------------------------------- recognition
def test_recognizes_enrolled_face_offline() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = PeopleStore(data_dir=Path(d) / "data")
        eileen = store.create({"name": "Eileen Collins", "relationship": "astronaut"})
        jpeg, encoding = prepare_photo(astronaut_png())
        assert encoding is not None, "no face found in the enrolment photo"
        store.add_photo(eileen.id, jpeg, encoding)
        matches = recognize(decode_image(astronaut_variant_png()), store.encodings())
        named = [m for m in matches if m.name]
        assert named and named[0].name == "Eileen Collins" and named[0].distance <= MATCH_DISTANCE, matches
        assert describe_faces(named).startswith("I see Eileen Collins (confidence ")
        assert recognize(decode_image(no_face_png()), store.encodings()) == []
        store.close()


def test_unknown_face_and_no_enrolments() -> None:
    assert describe_faces([]) is None
    assert describe_faces([FaceMatch(None, None, 0.9)]) == "Someone I don't recognize."
    assert describe_faces([FaceMatch("1", "Mike", 0.3), FaceMatch(None, None, 0.8)]) == (
        "I see Mike (confidence 0.70) and someone I don't recognize."
    )
    matches = recognize(decode_image(astronaut_png()), [])  # nobody enrolled
    assert matches and all(m.name is None for m in matches)


# ---------------------------------------------------------------- API
def test_people_api_crud_and_photos() -> None:
    with tempfile.TemporaryDirectory() as d:
        store, _, client = make_client(Path(d))
        assert client.get("/api/people", headers=HOST).status_code == 401
        assert client.post("/api/people", json={"name": ""}, headers=AUTH).status_code == 400
        assert client.post("/api/people", json={"name": "X", "email": "not-an-email"}, headers=AUTH).status_code == 400
        assert client.post("/api/people", json={"name": "X", "ssn": "1"}, headers=AUTH).status_code == 400
        created = client.post("/api/people", json={"name": "Eileen Collins", "relationship": "astronaut",
                                                   "facts": ["First woman to pilot the Space Shuttle"]}, headers=AUTH)
        assert created.status_code == 201, created.text
        pid = created.json()["data"]["id"]
        files = [("files", ("eileen.png", astronaut_png(), "image/png")),
                 ("files", ("noise.png", no_face_png(), "image/png")),
                 ("files", ("notes.txt", b"hello", "text/plain"))]
        up = client.post(f"/api/people/{pid}/photos", files=files, headers=AUTH)
        assert up.status_code == 201, up.text
        results = up.json()["data"]["results"]
        assert [r["ok"] for r in results] == [True, True, False], results
        assert results[0]["has_face"] is True and results[1]["has_face"] is False
        photo_id = results[0]["id"]
        img = client.get(f"/api/people/{pid}/photos/{photo_id}", headers=AUTH)
        assert img.status_code == 200 and img.content[:3] == b"\xff\xd8\xff", "stored as clean JPEG"
        rec = client.post("/api/people/recognize", files={"file": ("v.png", astronaut_variant_png(), "image/png")},
                          headers=AUTH).json()["data"]
        assert rec["summary"].startswith("I see Eileen Collins"), rec
        updated = client.put(f"/api/people/{pid}", json={"name": "Eileen Collins", "role": "Commander"}, headers=AUTH)
        assert updated.json()["data"]["role"] == "Commander"
        assert client.delete(f"/api/people/{pid}/photos/{photo_id}", headers=AUTH).status_code == 200
        assert client.get(f"/api/people/{pid}/photos/{photo_id}", headers=AUTH).status_code == 404
        assert client.delete(f"/api/people/{pid}", headers=AUTH).status_code == 200
        assert client.get("/api/people", headers=AUTH).json()["data"]["total"] == 0
        store.close()


def test_facts_crud_and_memory_page() -> None:
    with tempfile.TemporaryDirectory() as d:
        store, memory, client = make_client(Path(d))
        page = client.get("/memory", headers=HOST)
        assert page.status_code == 200 and TOKEN in page.text and "memory.js?v=" in page.text
        assert "blob:" in page.headers["content-security-policy"]
        assert client.get("/static/memory.js", headers=HOST).status_code == 200
        added = client.post("/api/memory", json={"text": "Gate code is 4321."}, headers=AUTH)
        assert added.status_code == 201
        fid = added.json()["data"]["id"]
        edited = client.put(f"/api/memory/{fid}", json={"text": "Gate code is 9876."}, headers=AUTH)
        assert edited.json()["data"]["text"] == "Gate code is 9876."
        assert [r.text for r in memory.recent(5)] == ["Gate code is 9876."]
        assert client.delete(f"/api/memory/{fid}", headers=AUTH).status_code == 200
        assert memory.count() == 0
        assert client.delete(f"/api/memory/{fid}", headers=AUTH).status_code == 404
        store.close()


# ---------------------------------------------------------------- brain
class _Params:
    def __init__(self, **arguments) -> None:
        self.arguments = arguments
        self.result = None

    async def result_callback(self, result, **_kwargs) -> None:
        self.result = result


class _LLM:
    def __init__(self) -> None:
        self.fns = {}

    def register_function(self, name, handler, **_kw) -> None:
        self.fns[name] = handler


def test_brain_tools_and_prompt_index() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = PeopleStore(data_dir=Path(d) / "data")
        store.create({"name": "Mike Rowe", "relationship": "foreman", "company": "ABC Concrete", "phone": "555-0100"})
        line = people_index(store)
        assert line.startswith("People you know: Mike Rowe (foreman, at ABC Concrete)"), line
        llm = _LLM()
        schemas = register_people_tools(llm, store)
        assert [s.name for s in schemas] == ["lookup_person", "list_people"]
        params = _Params(name="Mike")
        asyncio.run(llm.fns["lookup_person"](params))
        assert params.result["found"] and params.result["people"][0]["phone"] == "555-0100"
        missing = _Params(name="Zelda")
        asyncio.run(llm.fns["lookup_person"](missing))
        assert missing.result["found"] is False
        listing = _Params()
        asyncio.run(llm.fns["list_people"](listing))
        assert listing.result["count"] == 1
        assert people_index(None) == "" and register_people_tools(_LLM(), None) == []
        store.close()


def test_look_camera_names_recognized_person() -> None:
    import vision_tools as vt

    class _Cfg:  # describe_image replaced below; config unused
        pass

    real_describe = vt.describe_image

    async def fake_describe(_jpeg, _question, _config):
        return "A person in an orange flight suit in front of a flag."

    vt.describe_image = fake_describe
    vt.set_face_hook(lambda _jpeg: "I see Eileen Collins (confidence 0.62).")
    try:
        params = _Params(question="what do you see?")
        asyncio.run(vt._make_handler(lambda: b"\xff\xd8\xff-fake", "webcam", _Cfg())(params))
        assert params.result["people"] == "I see Eileen Collins (confidence 0.62)."
        assert params.result["description"].startswith("I see Eileen Collins")
        screen = _Params(question="what's on screen?")
        asyncio.run(vt._make_handler(lambda: b"\xff\xd8\xff-fake", "screen", _Cfg())(screen))
        assert "people" not in screen.result, "screens are never face-matched"
    finally:
        vt.describe_image = real_describe
        vt.set_face_hook(None)
        vt._SEEN_LISTENERS.clear()


TESTS = [
    ("store CRUD + soft delete + Obsidian mirror", test_store_crud_softdelete_and_mirror),
    ("groups migration: people kept, filed by relationship, once", test_groups_migration_keeps_people_and_files_by_relationship),
    ("groups API: create, assign, filter+search, rename, delete", test_groups_api_create_assign_filter_rename_delete),
    ("recognizes an enrolled face offline", test_recognizes_enrolled_face_offline),
    ("unknown face / nobody enrolled", test_unknown_face_and_no_enrolments),
    ("people API: CRUD, multi-photo upload, recognize", test_people_api_crud_and_photos),
    ("facts API CRUD + /memory page route", test_facts_crud_and_memory_page),
    ("brain tools + system-prompt people index", test_brain_tools_and_prompt_index),
    ("look_camera names a recognized person", test_look_camera_names_recognized_person),
]

if __name__ == "__main__":
    passed = 0
    for label, fn in TESTS:
        try:
            fn()
            passed += 1
            print(f"  ok - {label}")
        except Exception as exc:
            print(f"  FAIL - {label}: {exc!r}")
    print(f"\npeople: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
