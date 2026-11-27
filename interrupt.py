"""Stopping JARVIS mid-reply: the dashboard's Stop button / Esc, and spoken "stop".

* ``InterruptSwitch`` sits at the head of the pipeline. ``trigger()`` asks the
  pipeline task to interrupt (Pipecat's InterruptionFrame): the LLM stream is
  cancelled and queued TTS / audio output is flushed. The session keeps running.

* ``SpeechGuard`` sits right after STT. While JARVIS is talking (plus a short
  tail for room echo) whatever the mic hears is JARVIS's own voice coming back,
  so it is dropped - except a stop command, which interrupts. This replaces the
  blunt "mute the mic while the bot speaks" approach so "stop" can get through.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.turns.user_start import VADUserTurnStartStrategy

from wakeword import _word_matches

ECHO_TAIL_SECS = 1.0  # room echo + Whisper latency after the bot goes quiet
_STOP_WORDS = {"stop", "quiet", "enough", "cancel", "silence", "shush"}
_FILLER = {"hey", "ok", "okay", "please", "now", "jarvis", "talking", "be", "shut", "up", "that", "it", "just", "the"}
_TOKEN = re.compile(r"[a-z']+")


def is_stop_command(text: str) -> bool:
    """True for short commands like "stop", "JARVIS, stop", "stop talking", "be quiet".

    Deliberately strict: a sentence that merely contains "stop" ("how do I stop
    a leak?") is a question, not a command.
    """
    words = _TOKEN.findall((text or "").lower())
    if not words or len(words) > 5:
        return False
    words = ["jarvis" if _word_matches(w, "jarvis") else w for w in words]
    if not any(w in _STOP_WORDS for w in words) and words not in (["shut", "up"], ["jarvis", "shut", "up"]):
        return False
    return all(w in _STOP_WORDS or w in _FILLER for w in words)


class InterruptSwitch(FrameProcessor):
    """Pass-through processor that can interrupt the whole pipeline on demand."""

    def __init__(self, on_interrupt: Callable[[str], None] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._on_interrupt = on_interrupt

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

    async def trigger(self, reason: str = "button") -> float:
        """Interrupt now; returns the monotonic time it was requested."""
        requested = time.monotonic()
        print(f"[JARVIS] Stop requested ({reason})", flush=True)
        if self._on_interrupt:
            self._on_interrupt(reason)
        await self.push_interruption_task_frame_and_wait()
        return requested


class SpeechGuard(FrameProcessor):
    """Echo guard + spoken stop while the bot is speaking (place right after STT)."""

    def __init__(self, switch: InterruptSwitch, on_dropped: Callable[[str], None] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._switch = switch
        self._on_dropped = on_dropped
        self._speaking = False
        self._quiet_since = 0.0

    def bot_is_talking(self) -> bool:
        return self._speaking or (time.monotonic() - self._quiet_since) < ECHO_TAIL_SECS

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self._speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._speaking = False
            self._quiet_since = time.monotonic()
        elif isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            if is_stop_command(frame.text):
                if self.bot_is_talking():
                    await self._switch.trigger("voice")
                return  # a stop command is never a question for the brain
            if self.bot_is_talking():
                if self._on_dropped:
                    self._on_dropped(frame.text)
                return  # JARVIS hearing itself: drop
        await self.push_frame(frame, direction)


class EchoSafeVADUserTurnStartStrategy(VADUserTurnStartStrategy):
    """VAD turn start that ignores JARVIS's own voice coming back through the mic.

    While the bot speaks (+ echo tail) a VAD "user started" is echo: starting a
    user turn on it left an empty, never-finished turn that blocked the brain's
    follow-up answer (e.g. after a tool call). VAD frames still reach Whisper, so a
    spoken "stop" is still transcribed and handled by ``SpeechGuard``.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._speaking = False
        self._quiet_since = 0.0

    def _bot_is_talking(self) -> bool:
        return self._speaking or (time.monotonic() - self._quiet_since) < ECHO_TAIL_SECS

    async def process_frame(self, frame: Frame):
        if isinstance(frame, BotStartedSpeakingFrame):
            self._speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._speaking = False
            self._quiet_since = time.monotonic()
        elif isinstance(frame, VADUserStartedSpeakingFrame) and self._bot_is_talking():
            return None  # echo of the bot's own voice: not a user turn
        return await super().process_frame(frame)
