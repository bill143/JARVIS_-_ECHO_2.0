"""Tests for the JARVIS dashboard: event bus, REST API, WebSocket, health config.

Offline (no mic, no models). Run:  python test_dashboard.py
"""

from __future__ import annotations

import os
import struct
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import brain_config
from dashboard.bus import EventBus
from dashboard.health import echo_root, load_fallbacks
from dashboard.server import TOKEN_HEADER, create_app
from dashboard.taps import pcm16_level
from memory.obsidian import ObsidianMemory

TOKEN = "test-token-123"
HOST = {"host": "127.0.0.1:8090"}
AUTH = {**HOST, TOKEN_HEADER: TOKEN}


class FakeController:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.said: list[str] = []
        self.looks: list[str] = []
        self.model = "brain"

    def models(self) -> list[str]:
        return ["brain", "local-dev", "groq-dev"]

    async def say(self, text: str) -> None:
        self.said.append(text)
        self.bus.publish("user", text=text, source="typed")

    async def set_muted(self, muted: bool) -> None:
        self.bus.publish("muted", muted=muted)

    async def look(self, source: str) -> None:
        self.looks.append(source)

    async def stop(self) -> None:
        self.stops = getattr(self, "stops", 0) + 1
        self.bus.publish("interrupted", reason="button")

    async def set_model(self, model: str) -> None:
        self.model = model
        self.bus.publish("config", config={"model": model})


def make(memory=None):
    bus = EventBus()
    controller = FakeController(bus)
    client = TestClient(create_app(bus, controller, memory, port=8090, token=TOKEN))
    return bus, controller, client


# ---------------------------------------------------------------- bus
def test_bus_snapshot_and_transcript() -> None:
    bus = EventBus()
    bus.publish("status", state="listening")
    bus.publish("heard", text="hello there")
    bus.publish("mic_level", level=0.4)  # ephemeral: not in transcript
    bus.publish("seen", source="screen", description="a chart", image="data:image/jpeg;base64,AAA")
    snap = bus.snapshot()
    assert snap["status"] == "listening"
    kinds = [e["type"] for e in snap["transcript"]]
    assert kinds == ["heard", "seen"], kinds
    assert "image" not in snap["transcript"][1], "transcript must not carry images"
    assert snap["last_seen"]["image"].startswith("data:image/jpeg")


# ---------------------------------------------------------------- REST
def test_index_injects_token_and_security_headers() -> None:
    _, _, client = make()
    r = client.get("/", headers=HOST)
    assert r.status_code == 200 and TOKEN in r.text and "__JARVIS_TOKEN__" not in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_rejects_foreign_host_and_missing_token() -> None:
    _, _, client = make()
    assert client.get("/", headers={"host": "evil.example:8090"}).status_code == 403
    r = client.get("/api/state", headers=HOST)
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.json()["error"]["requestId"]


def test_state_includes_models() -> None:
    bus, _, client = make()
    bus.publish("status", state="speaking")
    data = client.get("/api/state", headers=AUTH).json()["data"]
    assert data["status"] == "speaking" and data["models"] == ["brain", "local-dev", "groq-dev"]


def test_say_validates_and_queues() -> None:
    _, controller, client = make()
    assert client.post("/api/say", json={"text": ""}, headers=AUTH).status_code == 400
    assert client.post("/api/say", json={"text": "hi", "x": 1}, headers=AUTH).status_code == 400
    assert client.post("/api/say", json={"text": "x" * 2001}, headers=AUTH).status_code == 400
    r = client.post("/api/say", json={"text": "  what time is it?  "}, headers=AUTH)
    assert r.status_code == 200 and r.json() == {"success": True, "data": {"queued": True}}
    assert controller.said == ["what time is it?"]


def test_look_mute_and_model() -> None:
    bus, controller, client = make()
    assert client.post("/api/look", json={"source": "fridge"}, headers=AUTH).status_code == 400
    assert client.post("/api/look", json={"source": "screen"}, headers=AUTH).status_code == 200
    assert controller.looks == ["screen"]
    assert client.post("/api/mute", json={"muted": True}, headers=AUTH).json()["data"] == {"muted": True}
    assert bus.get("muted") is True
    assert client.post("/api/model", json={"model": "gpt-9"}, headers=AUTH).status_code == 422
    assert client.post("/api/model", json={"model": "local-dev"}, headers=AUTH).status_code == 200
    assert controller.model == "local-dev" and bus.get("config")["model"] == "local-dev"


def test_stop_endpoint() -> None:
    bus, controller, client = make()
    assert client.post("/api/stop", json={}, headers=HOST).status_code == 401
    r = client.post("/api/stop", json={}, headers=AUTH)
    assert r.status_code == 200 and r.json()["data"] == {"stopped": True}
    assert controller.stops == 1
    assert bus.snapshot()["transcript"][-1]["type"] == "interrupted"


def test_memory_list_and_search() -> None:
    with tempfile.TemporaryDirectory() as vault:
        store = ObsidianMemory(vault)
        store.add("The truck is parked in bay 7.")
        store.add("Favourite coffee is a flat white.")
        _, _, client = make(memory=store)
        everything = client.get("/api/memory", headers=AUTH).json()["data"]
        assert everything["enabled"] and everything["total"] == 2 and len(everything["items"]) == 2
        hits = client.get("/api/memory", params={"q": "truck"}, headers=AUTH).json()["data"]["items"]
        assert hits and "bay 7" in hits[0]["text"]
    _, _, client = make(memory=None)
    assert client.get("/api/memory", headers=AUTH).json()["data"]["enabled"] is False


# ---------------------------------------------------------------- WebSocket
def test_websocket_requires_token() -> None:
    _, _, client = make()
    try:
        with client.websocket_connect("/ws?token=wrong", headers=HOST) as ws:
            ws.receive_json()
    except WebSocketDisconnect as exc:
        assert exc.code == 1008
    else:
        raise AssertionError("websocket accepted a bad token")


def test_websocket_snapshot_then_live_events() -> None:
    bus, _, client = make()
    bus.publish("reply", text="It is ten past four.")
    with client.websocket_connect(f"/ws?token={TOKEN}", headers=HOST) as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["models"]
        assert snap["transcript"][-1]["text"] == "It is ten past four."
        client.post("/api/say", json={"text": "hello JARVIS"}, headers=AUTH)
        event = ws.receive_json()
        assert event["type"] == "user" and event["text"] == "hello JARVIS" and event["source"] == "typed"


# ---------------------------------------------------------------- helpers
def test_audio_level() -> None:
    assert pcm16_level(b"") == 0.0
    assert pcm16_level(struct.pack("<4h", 0, 0, 0, 0)) == 0.0
    assert pcm16_level(struct.pack("<2h", 32000, -32000)) == 1.0
    assert 0 < pcm16_level(struct.pack("<2h", 1000, -1000)) < 0.5


def test_fallback_chain_from_real_echo_config() -> None:
    chains = load_fallbacks(Path(__file__).parent / "echo" / "config.yaml")
    assert chains["brain"][0] == "local-dev", chains.get("brain")
    assert load_fallbacks(Path("does-not-exist.yaml")) == {}
    assert echo_root("http://localhost:4000/v1") == "http://localhost:4000"


def test_resolve_echo_key_skips_stale_key() -> None:
    saved = {k: os.environ.get(k) for k in ("ECHO_API_KEY", "ECHO_MASTER_KEY")}
    try:
        os.environ["ECHO_API_KEY"] = "stale-old-key"
        os.environ["ECHO_MASTER_KEY"] = "current-master-key"
        accepts_master = lambda _url, key, _t: key == "current-master-key"  # noqa: E731
        assert brain_config.resolve_echo_key("http://x/v1", probe=accepts_master) == "current-master-key"
        rejects_all = lambda *_: False  # noqa: E731
        assert brain_config.resolve_echo_key("http://x/v1", probe=rejects_all) == "stale-old-key"
        assert brain_config.resolve_echo_key(None, probe=rejects_all) == "stale-old-key"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


TESTS = [
    ("bus snapshot + transcript", test_bus_snapshot_and_transcript),
    ("index: token injected + security headers", test_index_injects_token_and_security_headers),
    ("rejects foreign Host and missing token", test_rejects_foreign_host_and_missing_token),
    ("GET /api/state", test_state_includes_models),
    ("POST /api/say validation + queue", test_say_validates_and_queues),
    ("look / mute / model controls", test_look_mute_and_model),
    ("POST /api/stop interrupts", test_stop_endpoint),
    ("memory list + search (real Obsidian store)", test_memory_list_and_search),
    ("websocket rejects bad token", test_websocket_requires_token),
    ("websocket snapshot then live events", test_websocket_snapshot_then_live_events),
    ("audio level meter math", test_audio_level),
    ("fallback chain from echo/config.yaml", test_fallback_chain_from_real_echo_config),
    ("ECHO key resolution skips a stale key", test_resolve_echo_key_skips_stale_key),
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
    print(f"\ndashboard: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
