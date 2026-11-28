"""Tests for vision_tools with REAL hardware: webcam frame, screenshot, vision model.

Needs the webcam (CAMERA_NAME, default "C920"), a desktop session, and a local
Ollama with the vision model pulled (``ollama pull qwen2.5vl:7b``). The vision
call goes to Ollama's OpenAI-compatible /v1 directly (no key needed); in
JARVIS the same ``describe_image`` goes through ECHO's ``vision-dev`` alias.

Run:  python test_vision_tools.py
"""

from __future__ import annotations

import asyncio
import os

import cv2
import numpy as np

from vision_tools import (
    LOOK_CAMERA_FUNCTION_NAME,
    LOOK_SCREEN_FUNCTION_NAME,
    MAX_IMAGE_WIDTH,
    CaptureError,
    VisionConfig,
    _make_handler,
    capture_camera_jpeg,
    capture_screen_jpeg,
    describe_image,
    find_camera,
    look_camera_schema,
    look_screen_schema,
    register_vision_tools,
)

CAMERA_NAME = os.getenv("CAMERA_NAME", "C920")
OLLAMA_V1 = os.getenv("OLLAMA_V1_URL", "http://localhost:11434/v1")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
LOCAL_CONFIG = VisionConfig(base_url=OLLAMA_V1, api_key="ollama", model=OLLAMA_VISION_MODEL)


def _decode(jpeg: bytes) -> np.ndarray:
    assert jpeg[:3] == b"\xff\xd8\xff", "not a JPEG"
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, "JPEG does not decode"
    return img


def test_find_camera_by_name() -> None:
    _, _, name = find_camera(CAMERA_NAME)
    assert CAMERA_NAME.lower() in name.lower(), name
    try:
        find_camera("no-such-camera-xyz")
    except CaptureError:
        pass
    else:
        raise AssertionError("expected CaptureError for unknown camera")


def test_real_camera_frame() -> None:
    img = _decode(capture_camera_jpeg(CAMERA_NAME))
    h, w = img.shape[:2]
    assert w <= MAX_IMAGE_WIDTH and h > 100 and w > 100, (w, h)
    assert float(img.std()) > 2.0, "frame is flat (camera covered or not delivering)"


def test_real_screenshot() -> None:
    img = _decode(capture_screen_jpeg())
    h, w = img.shape[:2]
    assert w <= MAX_IMAGE_WIDTH and h > 100, (w, h)
    assert float(img.std()) > 2.0, "screenshot is flat"


def test_vision_model_reads_screenshot() -> None:
    text = asyncio.run(describe_image(capture_screen_jpeg(), "What is on this screen?", LOCAL_CONFIG))
    assert len(text) > 20, text
    print(f"      vision-model said: {text[:160]!r}")


class _FakeParams:
    def __init__(self, question: str) -> None:
        self.arguments = {"question": question}
        self.result = None

    async def result_callback(self, result, **_kwargs) -> None:
        self.result = result


def test_handler_end_to_end_with_real_camera() -> None:
    params = _FakeParams("What do you see?")
    handler = _make_handler(lambda: capture_camera_jpeg(CAMERA_NAME), "webcam", LOCAL_CONFIG)
    asyncio.run(handler(params))
    assert params.result and "description" in params.result, params.result
    assert len(params.result["description"]) > 20


def test_handler_reports_capture_failure() -> None:
    def broken():
        raise CaptureError("unplugged")

    params = _FakeParams("What do you see?")
    asyncio.run(_make_handler(broken, "webcam", LOCAL_CONFIG)(params))
    assert "error" in params.result and "unplugged" in params.result["error"]


class _FakeLLM:
    def __init__(self) -> None:
        self.registered: dict[str, object] = {}

    def register_function(self, name, handler, **options) -> None:
        self.registered[name] = handler
        self.options = getattr(self, "options", {})
        self.options[name] = options


def test_registration() -> None:
    llm = _FakeLLM()
    schemas = register_vision_tools(llm, "http://localhost:4000/v1", "test-key")
    assert set(llm.registered) == {LOOK_CAMERA_FUNCTION_NAME, LOOK_SCREEN_FUNCTION_NAME}
    assert [s.name for s in schemas] == [look_camera_schema().name, look_screen_schema().name]
    assert register_vision_tools(_FakeLLM(), None, None) == []


def _with_fake_devices(cameras, outcomes, fn):
    """Run ``fn`` with find_cameras/_grab_frame replaced (no hardware needed)."""
    import vision_tools as vt

    real_find, real_grab = vt.find_cameras, vt._grab_frame
    queue = list(outcomes)
    vt.find_cameras = lambda _name="C920": list(cameras)
    vt._grab_frame = lambda _i, _b: queue.pop(0)
    try:
        return fn()
    finally:
        vt.find_cameras, vt._grab_frame = real_find, real_grab


_DSHOW_MSMF = [(0, 700, "Logi Webcam C920e"), (0, 1400, "Logi Webcam C920e")]


def test_capture_falls_back_to_next_backend() -> None:
    frame = (np.random.default_rng(1).random((240, 320, 3)) * 255).astype(np.uint8)
    jpeg = _with_fake_devices(_DSHOW_MSMF, [("busy", None), ("ok", frame)], capture_camera_jpeg)
    assert _decode(jpeg).shape[:2] == (240, 320)


def test_capture_errors_are_precise() -> None:
    def expect(cameras, outcomes, needle):
        try:
            _with_fake_devices(cameras, outcomes, capture_camera_jpeg)
        except CaptureError as exc:
            assert needle in str(exc), str(exc)
        else:
            raise AssertionError("expected CaptureError")

    expect(_DSHOW_MSMF, [("busy", None), ("busy", None)], "is busy - another app")
    expect(_DSHOW_MSMF, [("busy", None), ("blank", None)], "sent no picture")
    expect([], [], "is connected")


def test_failed_look_reaches_the_dashboard() -> None:
    import vision_tools as vt

    seen = []
    vt.add_seen_listener(lambda source, description, jpeg: seen.append((source, description, jpeg)))
    try:
        def broken():
            raise CaptureError("The Logi Webcam C920e is busy - another app is using it")

        params = _FakeParams("What do you see?")
        asyncio.run(_make_handler(broken, "webcam", LOCAL_CONFIG)(params))
        assert "busy" in params.result["error"]
        assert seen and seen[-1][0] == "webcam" and seen[-1][2] is None and "busy" in seen[-1][1]
    finally:
        vt._SEEN_LISTENERS.clear()


def test_looks_survive_interruptions() -> None:
    """Looks stay synchronous (one clean answer) with a long enough timeout, and the
    desktop build mutes the mic during tool calls so speech can't cancel them."""
    from pathlib import Path

    llm = _FakeLLM()
    register_vision_tools(llm, "http://localhost:4000/v1", "test-key")
    for name in (LOOK_CAMERA_FUNCTION_NAME, LOOK_SCREEN_FUNCTION_NAME):
        opts = llm.options[name]
        assert opts.get("cancel_on_interruption") is not False, opts  # not async
        assert opts["timeout_secs"] >= 120, opts
    source = (Path(__file__).parent / "assistant.py").read_text(encoding="utf-8")
    assert "FunctionCallUserMuteStrategy()" in source


TESTS = [
    ("find camera by name (not index)", test_find_camera_by_name),
    ("real webcam frame -> valid JPEG", test_real_camera_frame),
    ("real screenshot (primary monitor) -> valid JPEG", test_real_screenshot),
    ("vision model describes a real screenshot", test_vision_model_reads_screenshot),
    ("look_camera handler end-to-end (real frame + model)", test_handler_end_to_end_with_real_camera),
    ("handler reports capture failure", test_handler_reports_capture_failure),
    ("tools register only with an endpoint", test_registration),
    ("capture falls back DSHOW -> MSMF", test_capture_falls_back_to_next_backend),
    ("capture errors are precise (busy / no picture / missing)", test_capture_errors_are_precise),
    ("failed look reaches the dashboard panel", test_failed_look_reaches_the_dashboard),
    ("looks survive interruptions (mic muted during tools)", test_looks_survive_interruptions),
]

if __name__ == "__main__":
    passed = 0
    for label, fn in TESTS:
        try:
            fn()
            passed += 1
            print(f"  ok - {label}")
        except Exception as exc:  # report and keep going
            print(f"  FAIL - {label}: {exc!r}")
    print(f"\nvision_tools: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
