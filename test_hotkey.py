"""Tests for the global stop hotkey (hotkey.py)."""

from __future__ import annotations

import asyncio
import os
import sys

from hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    GlobalHotkey,
    hotkey_from_env,
    parse_hotkey,
)


def test_default_is_ctrl_alt_s():
    os.environ.pop("STOP_HOTKEY", None)
    spec = hotkey_from_env()
    assert spec.modifiers == MOD_CONTROL | MOD_ALT
    assert spec.vk == ord("S")
    assert spec.text == "ctrl+alt+s"


def test_parse_named_keys_and_case():
    spec = parse_hotkey(" Ctrl + Shift + Space ")
    assert spec.modifiers == MOD_CONTROL | MOD_SHIFT
    assert spec.vk == 0x20
    assert parse_hotkey("alt+f12").vk == 0x7B


def test_parse_rejects_invalid():
    for bad in ["", "s", "ctrl+", "hyper+s", "ctrl+alt+??"]:
        try:
            parse_hotkey(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid hotkey {bad!r}")


def test_env_off_disables():
    os.environ["STOP_HOTKEY"] = "off"
    try:
        assert hotkey_from_env() is None
    finally:
        os.environ.pop("STOP_HOTKEY", None)


def test_real_hotkey_fires_callback():
    """Register an unused combo, synthesize the key press, expect the callback."""
    if sys.platform != "win32":
        return  # Win32 RegisterHotKey only
    import ctypes

    async def scenario():
        fired = asyncio.Event()

        async def on_press():
            fired.set()

        spec = parse_hotkey("ctrl+alt+shift+f11")
        hk = GlobalHotkey(spec, on_press, asyncio.get_running_loop())
        assert hk.start(), hk.error
        try:
            user32 = ctypes.windll.user32
            keyup = 0x0002
            keys = (0x11, 0x12, 0x10, 0x7A)  # ctrl, alt, shift, F11
            for vk in keys:
                user32.keybd_event(vk, 0, 0, 0)
            for vk in reversed(keys):
                user32.keybd_event(vk, 0, keyup, 0)
            await asyncio.wait_for(fired.wait(), timeout=2.0)
        finally:
            hk.stop()

    asyncio.run(scenario())


TESTS = [
    ("default hotkey is Ctrl+Alt+S", test_default_is_ctrl_alt_s),
    ("parses named keys, spaces and case", test_parse_named_keys_and_case),
    ("rejects invalid hotkeys", test_parse_rejects_invalid),
    ("STOP_HOTKEY=off disables it", test_env_off_disables),
    ("a real system-wide hotkey press reaches the callback", test_real_hotkey_fires_callback),
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
    print(f"\nhotkey: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
