"""Tests for interrupt.py: stop-command matching and the speech guard.

Offline. Run:  python test_interrupt.py
"""

from __future__ import annotations

import asyncio

from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, TranscriptionFrame
from pipecat.tests.utils import run_test

import interrupt
import time

from interrupt import InterruptSwitch, SpeechGuard, contains_addressed_stop, is_stop_command


def _t(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="mic", timestamp="2026-11-27T13:00:00Z")


class FakeSwitch:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    async def trigger(self, reason: str = "button") -> float:
        self.reasons.append(reason)
        return 0.0

    def note_user_turn(self) -> None:
        return None


def test_stop_commands() -> None:
    for text in ["stop", "Stop.", "JARVIS, stop!", "Jarvis stop", "hey jarvis stop", "stop talking",
                 "be quiet", "okay stop", "Jarvan, stop.", "enough", "shut up", "Stop. Stop."]:
        assert is_stop_command(text), text
    for text in ["", "how do I stop a leak in the bay 7 roof?", "what time is it",
                 "don't stop believing", "stop by the jobsite tomorrow morning", "Hey Jarvis here"]:
        assert not is_stop_command(text), text


def test_guard_drops_echo_and_stops_on_command() -> None:
    switch = FakeSwitch()
    guard = SpeechGuard(switch)
    down, _ = asyncio.run(run_test(
        guard,
        frames_to_send=[BotStartedSpeakingFrame(), _t("Hey, JARVIS here. How can I help?"), _t("JARVIS, stop")],
        expected_down_frames=[BotStartedSpeakingFrame],
    ))
    assert switch.reasons == ["voice"], switch.reasons
    assert not any(isinstance(f, TranscriptionFrame) for f in down)


def test_guard_passes_speech_when_quiet() -> None:
    switch = FakeSwitch()
    guard = SpeechGuard(switch)
    saved = interrupt.ECHO_TAIL_SECS
    interrupt.ECHO_TAIL_SECS = 0.0  # no echo tail for this test
    try:
        down, _ = asyncio.run(run_test(
            guard,
            frames_to_send=[BotStartedSpeakingFrame(), BotStoppedSpeakingFrame(), _t("Hey JARVIS, what time is it?"), _t("stop")],
            expected_down_frames=[BotStartedSpeakingFrame, BotStoppedSpeakingFrame, TranscriptionFrame],
        ))
    finally:
        interrupt.ECHO_TAIL_SECS = saved
    texts = [f.text for f in down if isinstance(f, TranscriptionFrame)]
    assert texts == ["Hey JARVIS, what time is it?"], texts
    assert switch.reasons == [], "a stop with nothing playing must not interrupt"


def test_echo_does_not_start_a_user_turn() -> None:
    from pipecat.frames.frames import VADUserStartedSpeakingFrame

    strategy = interrupt.EchoSafeVADUserTurnStartStrategy(enable_interruptions=False)
    started = []

    async def fake_report(*_a, **_k):
        started.append(True)

    strategy.report_user_turn_started = fake_report

    async def scenario():
        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(VADUserStartedSpeakingFrame())  # echo while talking
        assert started == [], "echo started a user turn"
        await strategy.process_frame(BotStoppedSpeakingFrame())
        strategy._quiet_since -= interrupt.ECHO_TAIL_SECS + 0.1  # tail elapsed
        await strategy.process_frame(VADUserStartedSpeakingFrame())  # the user, after JARVIS stopped
        assert started == [True]

    asyncio.run(scenario())


def test_addressed_stop_inside_echo() -> None:
    # Real transcript from the live test (Bill's "Jarvis, stop" merged into JARVIS's echo).
    assert contains_addressed_stop("to maintain alignment and stability during the storm.  Jarvis, stop.  Small frontal steel beams")
    assert contains_addressed_stop("and then the slab. Jarvis please just stop talking")
    assert not contains_addressed_stop("crews stop work when the wind picks up")  # his own words, no name
    assert not contains_addressed_stop("Jarvis here, the crews stop work at noon")  # name, but not a command
    assert not contains_addressed_stop("")


def test_guard_stops_on_command_inside_echo() -> None:
    switch = FakeSwitch()
    guard = SpeechGuard(switch)
    down, _ = asyncio.run(run_test(
        guard,
        frames_to_send=[BotStartedSpeakingFrame(),
                        _t("to maintain alignment and stability during the storm.  Jarvis, stop.  Small frontal steel beams")],
        expected_down_frames=[BotStartedSpeakingFrame],
    ))
    assert switch.reasons == ["voice"], switch.reasons


def test_switch_measures_cut_and_flags_restart() -> None:
    events: list[dict] = []
    switch = InterruptSwitch(on_measured=events.append)
    switch._pending = ("hotkey", time.monotonic())  # as trigger() leaves it
    asyncio.run(run_test(
        switch,
        frames_to_send=[BotStoppedSpeakingFrame(), BotStartedSpeakingFrame()],
        expected_down_frames=[BotStoppedSpeakingFrame, BotStartedSpeakingFrame],
    ))
    assert [e["kind"] for e in events] == ["cut", "restart"], events
    assert events[0]["reason"] == "hotkey" and 0 <= events[0]["cut_ms"] < 1000, events


def test_switch_no_restart_flag_after_user_turn() -> None:
    events: list[dict] = []
    switch = InterruptSwitch(on_measured=events.append)
    switch._watch = ("button", time.monotonic())  # as a measured stop leaves it
    switch.note_user_turn()  # the user asked something new: a reply is expected
    asyncio.run(run_test(switch, frames_to_send=[BotStartedSpeakingFrame()],
                         expected_down_frames=[BotStartedSpeakingFrame]))
    assert events == [], events

TESTS = [
    ("stop command matching", test_stop_commands),
    ("guard drops echo, spoken stop interrupts", test_guard_drops_echo_and_stops_on_command),
    ("guard passes real speech when JARVIS is quiet", test_guard_passes_speech_when_quiet),
    ("JARVIS's own voice never starts a user turn", test_echo_does_not_start_a_user_turn),
    ("'JARVIS, stop' found inside a longer echo transcript", test_addressed_stop_inside_echo),
    ("guard stops on 'JARVIS, stop' glued to his own echo", test_guard_stops_on_command_inside_echo),
    ("stop measures the audio cut and flags an unprompted restart", test_switch_measures_cut_and_flags_restart),
    ("speaking after a new user turn is not flagged", test_switch_no_restart_flag_after_user_turn),
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
    print(f"\ninterrupt: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
