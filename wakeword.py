"""Wake-word ("Hey JARVIS") gate — fully local, no extra models.

This is a *text* gate that sits on the Whisper transcript. Until it hears one
of the configured wake phrases (default "hey jarvis" / "jarvis") it drops every
transcript. Once woken it stays awake for a short window (~15s) so you can keep
talking without repeating the phrase.

Two pieces live here:

* ``WakeWordGate`` — pure-Python logic with **no Pipecat dependency**, so it can
  be unit-tested without installing the heavy voice stack (see
  ``test_wakeword.py``).
* ``WakeWordProcessor`` — a thin Pipecat ``FrameProcessor`` that wraps the gate
  and plugs into the pipeline right after STT. Only defined when Pipecat is
  importable, so importing this module never drags in the voice stack.

To swap in a real acoustic wake-word model (openWakeWord / Porcupine) later,
replace ``WakeWordGate.feed`` with a call into that model — the pipeline wiring
stays the same.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional


def parse_phrases(raw: Optional[str]) -> list[str]:
    """Parse a comma-separated ``WAKE_PHRASES`` value into a normalized list.

    An empty / unset value means "always on" (no wake word required).
    """
    if not raw:
        return []
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


class WakeWordGate:
    """Decide whether a transcript should reach the LLM.

    Parameters
    ----------
    phrases:
        Wake phrases to listen for (already lower-cased). Empty == always on.
    window_seconds:
        How long JARVIS stays awake after the last accepted utterance.
    time_func:
        Monotonic clock; injectable so tests can control the passage of time.
    """

    def __init__(
        self,
        phrases: list[str],
        window_seconds: float = 15.0,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self.phrases = [p.lower() for p in phrases]
        self.window_seconds = window_seconds
        self._now = time_func
        self._awake_until: float = 0.0

    @property
    def always_on(self) -> bool:
        return not self.phrases

    def is_awake(self) -> bool:
        if self.always_on:
            return True
        return self._now() < self._awake_until

    def _wake(self) -> None:
        self._awake_until = self._now() + self.window_seconds

    def feed(self, transcript: str) -> Optional[str]:
        """Feed a final transcript through the gate.

        Returns the text that should be forwarded to the LLM, or ``None`` if the
        utterance should be dropped (asleep, or it was *only* the wake phrase).
        """
        text = (transcript or "").strip()

        # Always-on mode: forward everything, never gate.
        if self.always_on:
            return text or None

        # Already awake within the window: forward and refresh the window.
        if self.is_awake():
            self._wake()
            return text or None

        # Asleep: look for a wake phrase anywhere in the utterance.
        lowered = text.lower()
        for phrase in self.phrases:
            idx = lowered.find(phrase)
            if idx != -1:
                self._wake()
                # Forward whatever the user said *after* the wake phrase, so
                # "hey jarvis what time is it" wakes AND asks in one breath.
                remainder = text[idx + len(phrase):].strip(" ,.!?-")
                return remainder or None

        # Asleep and no wake phrase heard: drop it.
        return None


def gate_from_env(time_func: Callable[[], float] = time.monotonic) -> WakeWordGate:
    """Build a ``WakeWordGate`` from ``WAKE_PHRASES`` / ``WAKE_WINDOW_SECONDS``."""
    phrases = parse_phrases(os.getenv("WAKE_PHRASES", "hey jarvis,jarvis"))
    try:
        window = float(os.getenv("WAKE_WINDOW_SECONDS", "15"))
    except ValueError:
        window = 15.0
    return WakeWordGate(phrases, window_seconds=window, time_func=time_func)


# ---------------------------------------------------------------------------
# Pipecat processor (only when the voice stack is installed).
# ---------------------------------------------------------------------------
try:
    from pipecat.frames.frames import Frame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    _PIPECAT_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only without the extras
    _PIPECAT_AVAILABLE = False


if _PIPECAT_AVAILABLE:

    class WakeWordProcessor(FrameProcessor):
        """Gate ``TranscriptionFrame``s using a :class:`WakeWordGate`.

        Place this immediately after the STT service and before the user
        context aggregator. Final transcripts that don't pass the gate are
        swallowed; everything else flows through untouched.
        """

        def __init__(self, gate: Optional[WakeWordGate] = None, **kwargs) -> None:
            super().__init__(**kwargs)
            self._gate = gate or gate_from_env()

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)

            if isinstance(frame, TranscriptionFrame):
                forwarded = self._gate.feed(frame.text)
                if forwarded is None:
                    # Dropped (asleep or wake-phrase only) — don't push it on.
                    return
                # Forward the (possibly trimmed) transcript downstream.
                frame.text = forwarded
                await self.push_frame(frame, direction)
                return

            await self.push_frame(frame, direction)
