"""User-triggered webcam vision for JARVIS.

Claude calls a single ``see`` tool when the user asks something that needs eyes
("what can you see?", "am I holding anything?"). Two transports, two ways to get
the frame:

* **Desktop** (``assistant.py``) — there is no video track, so we grab a frame
  straight off the local webcam with OpenCV and append it to the LLM context.
* **Browser / WebRTC** (``assistant_web.py``) — the browser already streams
  video, so we ask Pipecat for the latest frame from that track via a
  ``UserImageRequestFrame(append_to_context=True)``; no server-side camera.

Both paths funnel the image into the context so Claude's vision can describe it
on the next turn. The tool schema is shared.
"""

from __future__ import annotations

import os
from typing import Optional

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import (
    FunctionCallResultProperties,
    UserImageRawFrame,
    UserImageRequestFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import FunctionCallParams

VISION_FUNCTION_NAME = "see"


def vision_tool_schema() -> FunctionSchema:
    """The ``see`` tool exposed to Claude (shared by both builds)."""
    return FunctionSchema(
        name=VISION_FUNCTION_NAME,
        description=(
            "Capture the current webcam frame and look at it. Call this whenever "
            "the user asks about what is visible, what they are holding or wearing, "
            "or anything that requires seeing the real world right now."
        ),
        properties={
            "query": {
                "type": "string",
                "description": "What the user wants you to look for, e.g. 'what am I holding?'",
            }
        },
        required=["query"],
    )


# ---------------------------------------------------------------------------
# Desktop: OpenCV webcam capture.
# ---------------------------------------------------------------------------
def capture_webcam_frame(camera_index: int = 0) -> Optional[UserImageRawFrame]:
    """Grab one frame from the local webcam as a ``UserImageRawFrame``.

    Returns ``None`` if the camera can't be opened or read. Imports OpenCV
    lazily so the module imports fine on machines without it.
    """
    try:
        import cv2  # noqa: PLC0415 - optional, desktop-only dependency
    except Exception:
        return None

    cap = cv2.VideoCapture(camera_index)
    try:
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        # OpenCV gives BGR; Claude vision wants RGB.
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        return UserImageRawFrame(
            image=rgb.tobytes(),
            size=(width, height),
            format="RGB",
            user_id="local-webcam",
        )
    finally:
        cap.release()


def make_desktop_vision_handler(camera_index: int = 0):
    """Build the ``see`` handler for the desktop (local webcam) build."""

    async def handler(params: FunctionCallParams) -> None:
        frame = capture_webcam_frame(camera_index)
        if frame is None:
            await params.result_callback(
                {"error": "Could not access the webcam. Tell the user the camera is unavailable."}
            )
            return

        # Append the captured frame to the context, then run the LLM again so it
        # describes the image. We let the result land *before* the image so we
        # don't disturb Claude's strict tool-result ordering.
        frame.append_to_context = True
        properties = FunctionCallResultProperties(run_llm=False)
        await params.result_callback(
            {"status": "captured", "note": "Webcam frame attached; describe what you see."},
            properties=properties,
        )
        await params.llm.push_frame(frame, FrameDirection.UPSTREAM)

    return handler


# ---------------------------------------------------------------------------
# Browser / WebRTC: request a frame from the streamed video track.
# ---------------------------------------------------------------------------
def make_web_vision_handler(video_source: Optional[str] = None):
    """Build the ``see`` handler for the WebRTC build.

    Instead of touching a camera, we ask Pipecat to pull the latest frame from
    the browser's video track and append it to the context.
    """

    async def handler(params: FunctionCallParams) -> None:
        request = UserImageRequestFrame(
            user_id="webrtc-client",
            append_to_context=True,
            video_source=video_source,
            function_name=params.function_name,
            tool_call_id=params.tool_call_id,
        )
        properties = FunctionCallResultProperties(run_llm=False)
        await params.result_callback(
            {"status": "looking", "note": "Requested the latest webcam frame; describe what you see."},
            properties=properties,
        )
        await params.llm.push_frame(request, FrameDirection.UPSTREAM)

    return handler


def camera_index_from_env() -> int:
    try:
        return int(os.getenv("CAMERA_INDEX", "0"))
    except ValueError:
        return 0
