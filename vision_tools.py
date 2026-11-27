"""JARVIS "eyes" — ``look_camera`` and ``look_screen`` tools.

The brain (e.g. Groq llama-3.3-70b) is text-only, so these tools do the seeing
themselves: capture one image (webcam frame or primary-monitor screenshot),
send it with the user's question to a vision model behind ECHO (alias
``vision-dev``, a local Ollama VLM by default), and hand the brain back a text
description to answer from.

Capture runs in a worker thread so the audio event loop never blocks.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from dataclasses import dataclass

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

logger = logging.getLogger(__name__)

LOOK_CAMERA_FUNCTION_NAME = "look_camera"
LOOK_SCREEN_FUNCTION_NAME = "look_screen"

DEFAULT_CAMERA_NAME = "C920"
DEFAULT_VISION_MODEL = "vision-dev"
MAX_IMAGE_WIDTH = 1280
JPEG_QUALITY = 85
CAMERA_WARMUP_FRAMES = 5  # first frames after open are often dark / unexposed
VISION_TIMEOUT_SECS = 120.0


class CaptureError(RuntimeError):
    """Raised when a camera frame or screenshot can't be captured."""


# Called as listener(source, description, jpeg_bytes_or_None) after every look.
_SEEN_LISTENERS: list = []


def add_seen_listener(listener) -> None:
    """Register ``listener(source, description, jpeg_or_None)`` for every look.

    ``jpeg`` is ``None`` when the capture itself failed (``description`` then
    holds the error), so displays can show the failure instead of nothing.
    """
    _SEEN_LISTENERS.append(listener)


def _notify_seen(source: str, description: str, jpeg: bytes | None) -> None:
    for listener in list(_SEEN_LISTENERS):
        try:
            listener(source, description, jpeg)
        except Exception as exc:  # a display hook must never break the answer
            logger.warning("seen listener failed: %s", exc)


@dataclass(frozen=True)
class VisionConfig:
    base_url: str
    api_key: str
    model: str = DEFAULT_VISION_MODEL
    timeout: float = VISION_TIMEOUT_SECS


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def _encode_jpeg(bgr) -> bytes:
    import cv2  # noqa: PLC0415 - optional desktop dependency

    height, width = bgr.shape[:2]
    if width > MAX_IMAGE_WIDTH:
        scale = MAX_IMAGE_WIDTH / width
        bgr = cv2.resize(bgr, (MAX_IMAGE_WIDTH, int(height * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        raise CaptureError("JPEG encoding failed")
    return buf.tobytes()


def find_cameras(name: str = DEFAULT_CAMERA_NAME) -> list[tuple[int, int, str]]:
    """Every ``(index, backend, full_name)`` whose name contains ``name``, best first.

    Chosen by name, not index: Windows device order changes as devices come
    and go (virtual cameras such as OBS register too). DirectShow first, then
    Media Foundation, so a device one backend can't open gets a second chance.
    """
    import cv2  # noqa: PLC0415
    from cv2_enumerate_cameras import enumerate_cameras  # noqa: PLC0415

    wanted = name.strip().lower()
    found: list[tuple[int, int, str]] = []
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
        for cam in enumerate_cameras(backend):
            if wanted in cam.name.lower():
                found.append((cam.index, backend, cam.name))
    return found


def find_camera(name: str = DEFAULT_CAMERA_NAME) -> tuple[int, int, str]:
    """The best ``(index, backend, full_name)`` for ``name``; raises if none exists."""
    cameras = find_cameras(name)
    if not cameras:
        raise CaptureError(f"No camera whose name contains {name!r} is connected")
    return cameras[0]


def _grab_frame(index: int, backend: int):
    """Open, read a few frames (auto-exposure settles), release.

    Returns ``("ok", frame)``, ``("busy", None)`` if the device won't open, or
    ``("blank", None)`` if it opened but delivered nothing usable.
    """
    import cv2  # noqa: PLC0415

    cap = cv2.VideoCapture(index, backend)
    try:
        if not cap.isOpened():
            return "busy", None
        frame = None
        for _ in range(CAMERA_WARMUP_FRAMES):
            ok, candidate = cap.read()
            if ok and candidate is not None:
                frame = candidate
        if frame is None or float(frame.std()) < 1.0:  # all-black/flat = no picture
            return "blank", None
        return "ok", frame
    finally:
        cap.release()  # always free the device for other apps


def capture_camera_jpeg(name: str = DEFAULT_CAMERA_NAME) -> bytes:
    """Grab one frame from the named webcam and return it as JPEG bytes.

    Tries every matching device/backend in turn and raises a precise
    :class:`CaptureError` (not connected / busy in another app / no picture).
    """
    cameras = find_cameras(name)
    if not cameras:
        raise CaptureError(f"No camera whose name contains {name!r} is connected")
    outcomes = []
    for index, backend, _full_name in cameras:
        status, frame = _grab_frame(index, backend)
        if status == "ok":
            return _encode_jpeg(frame)
        outcomes.append(status)
    label = cameras[0][2]
    if "blank" in outcomes:
        raise CaptureError(
            f"The {label} opened but sent no picture (lens covered or privacy shutter closed?)"
        )
    raise CaptureError(f"The {label} is busy - another app (a browser tab, Teams, OBS) is using it")


def capture_screen_jpeg() -> bytes:
    """Screenshot the primary monitor and return it as JPEG bytes."""
    import mss  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    with mss.MSS() as sct:
        monitors = sct.monitors[1:]  # [0] is the union of all monitors
        if not monitors:
            raise CaptureError("No monitor found")
        primary = next((m for m in monitors if m.get("is_primary")), monitors[0])
        shot = sct.grab(primary)
    bgra = np.asarray(shot)
    return _encode_jpeg(np.ascontiguousarray(bgra[:, :, :3]))


# ---------------------------------------------------------------------------
# Vision model call (OpenAI-compatible: ECHO, or Ollama's /v1 directly)
# ---------------------------------------------------------------------------
async def describe_image(jpeg: bytes, question: str, config: VisionConfig) -> str:
    """Ask the vision model ``question`` about ``jpeg``; return its text answer."""
    from openai import AsyncOpenAI  # noqa: PLC0415

    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    prompt = (
        f"{question.strip() or 'Describe what you see.'}\n"
        "Answer factually and concisely (2-4 sentences). Mention any readable text "
        "that matters. If unsure, say so."
    )
    client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key, timeout=config.timeout)
    try:
        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
    finally:
        await client.close()
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Vision model returned an empty answer")
    return text


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
_QUESTION_PROPERTY = {
    "question": {
        "type": "string",
        "description": "What the user wants to know about the image, in their words.",
    }
}


def look_camera_schema() -> FunctionSchema:
    return FunctionSchema(
        name=LOOK_CAMERA_FUNCTION_NAME,
        description=(
            "Look through the user's webcam right now. Call this when the user asks "
            "'what do you see', 'look at this', what they are holding or wearing, or "
            "anything about the room in front of the camera."
        ),
        properties=_QUESTION_PROPERTY,
        required=["question"],
    )


def look_screen_schema() -> FunctionSchema:
    return FunctionSchema(
        name=LOOK_SCREEN_FUNCTION_NAME,
        description=(
            "Take a screenshot of the user's primary monitor and look at it. Call this "
            "when the user asks 'what's on my screen', to read or explain something "
            "on screen, or about an app or error message they are looking at."
        ),
        properties=_QUESTION_PROPERTY,
        required=["question"],
    )


def _make_handler(capture, source: str, config: VisionConfig):
    async def handler(params: FunctionCallParams) -> None:
        question = str((params.arguments or {}).get("question", "") or "")
        try:
            jpeg = await asyncio.to_thread(capture)
        except Exception as exc:  # camera busy/unplugged, no display, ...
            logger.warning("%s capture failed: %s", source, exc)
            print(f"[JARVIS] Could not capture the {source}: {exc}", flush=True)
            _notify_seen(source, f"Could not capture the {source}: {exc}", None)
            await params.result_callback(
                {"error": f"Could not capture the {source}: {exc}. Tell the user exactly this, briefly."}
            )
            return
        try:
            description = await describe_image(jpeg, question, config)
        except Exception as exc:
            logger.warning("%s vision call failed: %s", source, exc)
            print(f"[JARVIS] Vision model failed on the {source}: {type(exc).__name__}: {exc}", flush=True)
            _notify_seen(source, "The vision model could not describe this image.", jpeg)
            await params.result_callback(
                {"error": f"The vision model could not look at the {source}. Tell the user briefly."}
            )
            return
        print(f"[JARVIS] Saw ({source}, {len(jpeg)} bytes): {description!r}", flush=True)
        _notify_seen(source, description, jpeg)
        await params.result_callback(
            {"source": source, "description": description, "note": "Answer the user from this."}
        )

    return handler


def register_vision_tools(llm, base_url: str | None, api_key: str | None) -> list[FunctionSchema]:
    """Wire ``look_camera`` / ``look_screen`` onto the LLM when a vision endpoint exists.

    Uses ECHO (``base_url``/``api_key``) with ``VISION_MODEL`` (default
    ``vision-dev``). Returns the schemas to add to the ToolsSchema, or ``[]``
    when vision is disabled or no endpoint is configured.
    """
    if os.getenv("VISION_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return []
    if not base_url or not api_key:
        logger.warning("Vision disabled: it needs ECHO (ECHO_BASE_URL + key).")
        return []
    config = VisionConfig(
        base_url=base_url,
        api_key=api_key,
        model=(os.getenv("VISION_MODEL") or "").strip() or DEFAULT_VISION_MODEL,
    )
    camera_name = (os.getenv("CAMERA_NAME") or "").strip() or DEFAULT_CAMERA_NAME
    # A look can take a while (capture + vision model). Don't let the user's next
    # words ("hello? what do you see?") cancel it: Pipecat cancels in-flight
    # function calls on interruption by default, which made JARVIS report a
    # camera failure that never happened.
    llm.register_function(
        LOOK_CAMERA_FUNCTION_NAME,
        _make_handler(lambda: capture_camera_jpeg(camera_name), "webcam", config),
        cancel_on_interruption=False,
        timeout_secs=VISION_TIMEOUT_SECS + 30,
    )
    llm.register_function(
        LOOK_SCREEN_FUNCTION_NAME,
        _make_handler(capture_screen_jpeg, "screen", config),
        cancel_on_interruption=False,
        timeout_secs=VISION_TIMEOUT_SECS + 30,
    )
    print(f"[JARVIS] Eyes: webcam '{camera_name}' + primary screen via {config.model}", flush=True)
    _start_warm_up(config)
    return [look_camera_schema(), look_screen_schema()]


def _tiny_jpeg() -> bytes:
    import numpy as np  # noqa: PLC0415

    return _encode_jpeg(np.zeros((32, 32, 3), dtype=np.uint8))


async def warm_up(config: VisionConfig) -> None:
    """Load the vision model now (through the real ECHO path) so the first look is fast."""
    try:
        await describe_image(_tiny_jpeg(), "Reply with the single word: ready.", config)
        print(f"[JARVIS] Eyes warmed up ({config.model} loaded)", flush=True)
    except Exception as exc:  # warm-up is an optimisation; looks still work without it
        print(f"[JARVIS] Eyes warm-up skipped: {type(exc).__name__}", flush=True)


def _start_warm_up(config: VisionConfig) -> None:
    if os.getenv("VISION_WARMUP", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        asyncio.get_running_loop().create_task(warm_up(config))
    except RuntimeError:
        pass  # no running loop (e.g. unit tests): skip
