"""Pipecat processors that report pipeline activity to the dashboard bus.

They pass every frame through untouched — except ``MicTap``, which drops mic
audio while the dashboard has the mic muted. Placement (see assistant.py):

    input -> MicTap -> STT -> HeardTap -> wake gate -> UserTap -> user agg
          -> LLM -> ToolTap -> TTS -> BotAudioTap -> output -> BotTap -> asst agg
"""

from __future__ import annotations

import struct
import time

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    FunctionCallInProgressFrame,
    InputAudioRawFrame,
    LLMFullResponseStartFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from dashboard.bus import EventBus

LEVEL_INTERVAL_SECS = 0.08  # ~12 level updates/s is plenty for a meter
FULL_SCALE_RMS = 6000.0  # RMS that maps to a full meter


def pcm16_level(audio: bytes) -> float:
    """0..1 loudness of 16-bit little-endian PCM (RMS, clipped)."""
    count = len(audio) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", audio[: count * 2])
    rms = (sum(s * s for s in samples) / count) ** 0.5
    return min(1.0, rms / FULL_SCALE_RMS)


class MicState:
    """Shared mute flag (set by the dashboard, read by MicTap)."""

    def __init__(self) -> None:
        self.muted = False


class _Tap(FrameProcessor):
    def __init__(self, bus: EventBus, **kwargs) -> None:
        super().__init__(**kwargs)
        self._bus = bus


class MicTap(_Tap):
    def __init__(self, bus: EventBus, mic: MicState, **kwargs) -> None:
        super().__init__(bus, **kwargs)
        self._mic = mic
        self._last = 0.0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            if self._mic.muted:
                return  # muted: JARVIS hears nothing
            now = time.monotonic()
            if now - self._last >= LEVEL_INTERVAL_SECS:
                self._last = now
                self._bus.publish("mic_level", level=round(pcm16_level(frame.audio), 3))
        await self.push_frame(frame, direction)


class HeardTap(_Tap):
    """Every final transcript, before the wake gate decides."""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            self._bus.publish("heard", text=frame.text.strip())
        await self.push_frame(frame, direction)


class UserTap(_Tap):
    """Transcripts the wake gate let through: a real request to JARVIS."""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            self._bus.publish("user", text=frame.text.strip(), source="voice")
            self._bus.publish("status", state="thinking")
        await self.push_frame(frame, direction)


class ToolTap(_Tap):
    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, FunctionCallInProgressFrame):
            self._bus.publish("tool", name=frame.function_name, arguments=frame.arguments or {})
        elif isinstance(frame, LLMFullResponseStartFrame):
            self._bus.publish("status", state="thinking")
        await self.push_frame(frame, direction)


class BotAudioTap(_Tap):
    def __init__(self, bus: EventBus, **kwargs) -> None:
        super().__init__(bus, **kwargs)
        self._last = 0.0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSAudioRawFrame):
            now = time.monotonic()
            if now - self._last >= LEVEL_INTERVAL_SECS:
                self._last = now
                self._bus.publish("bot_level", level=round(pcm16_level(frame.audio), 3))
        await self.push_frame(frame, direction)


class BotTap(_Tap):
    """Speaking state + the spoken reply text (streamed, then finalized)."""

    def __init__(self, bus: EventBus, **kwargs) -> None:
        super().__init__(bus, **kwargs)
        self._reply: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bus.publish("status", state="speaking")
        elif isinstance(frame, TTSTextFrame) and frame.text.strip():
            self._reply.append(frame.text.strip())
            self._bus.publish("reply_chunk", text=" ".join(self._reply))
        elif isinstance(frame, BotStoppedSpeakingFrame):
            if self._reply:
                self._bus.publish("reply", text=" ".join(self._reply))
                self._reply = []
            self._bus.publish("status", state="listening")
        await self.push_frame(frame, direction)
