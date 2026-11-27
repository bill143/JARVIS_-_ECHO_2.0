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

    def register_function(self, name, handler) -> None:
        self.registered[name] = handler


def test_registration() -> None:
    llm = _FakeLLM()
    schemas = register_vision_tools(llm, "http://localhost:4000/v1", "test-key")
    assert set(llm.registered) == {LOOK_CAMERA_FUNCTION_NAME, LOOK_SCREEN_FUNCTION_NAME}
    assert [s.name for s in schemas] == [look_camera_schema().name, look_screen_schema().name]
    assert register_vision_tools(_FakeLLM(), None, None) == []


TESTS = [
    ("find camera by name (not index)", test_find_camera_by_name),
    ("real webcam frame -> valid JPEG", test_real_camera_frame),
    ("real screenshot (primary monitor) -> valid JPEG", test_real_screenshot),
    ("vision model describes a real screenshot", test_vision_model_reads_screenshot),
    ("look_camera handler end-to-end (real frame + model)", test_handler_end_to_end_with_real_camera),
    ("handler reports capture failure", test_handler_reports_capture_failure),
    ("tools register only with an endpoint", test_registration),
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
