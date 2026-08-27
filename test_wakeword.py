"""Unit tests for the wake-word gate logic.

Runs with **no heavy deps** (no Pipecat, no API key) — just the pure
``WakeWordGate``. Usage:  ``python test_wakeword.py``
"""

from wakeword import WakeWordGate, parse_phrases


class FakeClock:
    """A controllable monotonic clock for deterministic window tests."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _gate(clock: FakeClock, phrases=("hey jarvis", "jarvis"), window=15.0) -> WakeWordGate:
    return WakeWordGate(list(phrases), window_seconds=window, time_func=clock)


def run_tests() -> None:
    cases = []

    def check(name: str, condition: bool) -> None:
        cases.append((name, condition))
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {name}")

    # 1. Always-on mode (no phrases) forwards everything verbatim.
    clock = FakeClock()
    g = _gate(clock, phrases=())
    check("always-on forwards text", g.feed("what time is it") == "what time is it")

    # 2. Asleep + no wake phrase -> dropped.
    clock = FakeClock()
    g = _gate(clock)
    check("asleep drops non-wake utterance", g.feed("what time is it") is None)

    # 3. Wake phrase + question in one breath -> wakes and forwards remainder.
    clock = FakeClock()
    g = _gate(clock)
    check(
        "wake + question forwards remainder",
        g.feed("hey jarvis what time is it") == "what time is it",
    )

    # 4. Bare wake phrase wakes but forwards nothing.
    clock = FakeClock()
    g = _gate(clock)
    check("bare wake phrase forwards None", g.feed("jarvis") is None)

    # 5. After waking, a follow-up within the window is forwarded.
    clock = FakeClock()
    g = _gate(clock)
    g.feed("hey jarvis")
    clock.advance(5)
    check("follow-up within window forwarded", g.feed("and the weather?") == "and the weather?")

    # 6. After the window expires, follow-ups are dropped again.
    clock = FakeClock()
    g = _gate(clock)
    g.feed("hey jarvis")
    clock.advance(20)  # window is 15s
    check("follow-up after window dropped", g.feed("are you there") is None)

    # 7. Wake matching is case-insensitive.
    clock = FakeClock()
    g = _gate(clock)
    check("case-insensitive wake", g.feed("HEY JARVIS hello") == "hello")

    # 8. Wake phrase mid-sentence still triggers.
    clock = FakeClock()
    g = _gate(clock)
    check("mid-sentence wake triggers", g.feed("ok hey jarvis stop") == "stop")

    # Bonus sanity check on the parser (not counted in the headline 8).
    check("parse_phrases handles empty", parse_phrases("") == [])
    check("parse_phrases trims + lowercases", parse_phrases("Hey JARVIS, Jarvis") == ["hey jarvis", "jarvis"])

    passed = sum(1 for _, ok in cases if ok)
    total = len(cases)
    print(f"\n{passed}/{total} checks passed")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    run_tests()
