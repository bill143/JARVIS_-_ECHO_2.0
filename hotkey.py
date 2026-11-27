"""Global "stop speaking" hotkey (default Ctrl+Alt+S) that works from any window.

Uses the Win32 ``RegisterHotKey`` API through ctypes: a true system-wide hotkey,
no keyboard hook (nothing sees other keystrokes), no admin rights and no extra
dependency. A small daemon thread owns the registration and its message loop;
each press schedules ``on_press()`` onto the asyncio loop JARVIS runs on.

Set ``STOP_HOTKEY`` in ``.env`` to change it (e.g. ``ctrl+shift+space``), or to
``off`` to disable it. On non-Windows systems it logs and does nothing.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

DEFAULT_HOTKEY = "ctrl+alt+s"

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_MODIFIERS = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN, "super": MOD_WIN,
}
_NAMED_KEYS = {
    "space": 0x20, "esc": 0x1B, "escape": 0x1B, "pause": 0x13, "enter": 0x0D,
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}


@dataclass(frozen=True)
class HotkeySpec:
    text: str
    modifiers: int
    vk: int


def parse_hotkey(text: str) -> HotkeySpec:
    """``"ctrl+alt+s"`` -> modifiers + virtual-key code. Raises ValueError if invalid."""
    parts = [p.strip().lower() for p in (text or "").split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    *mods, key = parts
    modifiers = 0
    for mod in mods:
        if mod not in _MODIFIERS:
            raise ValueError(f"unknown modifier {mod!r}")
        modifiers |= _MODIFIERS[mod]
    if not modifiers:
        raise ValueError("a global hotkey needs at least one modifier (ctrl/alt/shift/win)")
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    else:
        raise ValueError(f"unknown key {key!r}")
    return HotkeySpec(text="+".join(parts), modifiers=modifiers, vk=vk)


def hotkey_from_env() -> HotkeySpec | None:
    raw = (os.getenv("STOP_HOTKEY") or DEFAULT_HOTKEY).strip()
    if raw.lower() in {"off", "none", "false", "0", "disabled"}:
        return None
    return parse_hotkey(raw)


class GlobalHotkey:
    """Owns one system-wide hotkey for the life of the process."""

    _HOTKEY_ID = 0xB0B

    def __init__(self, spec: HotkeySpec, on_press: Callable[[], Awaitable[object]],
                 loop: asyncio.AbstractEventLoop) -> None:
        self.spec = spec
        self._on_press = on_press
        self._loop = loop
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self.registered = False
        self.error = ""

    def start(self, timeout: float = 2.0) -> bool:
        """Register the hotkey; True when Windows accepted it."""
        if sys.platform != "win32":
            self.error = "global hotkeys are only supported on Windows"
            return False
        self._thread = threading.Thread(target=self._run, name="jarvis-stop-hotkey", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.registered

    def stop(self) -> None:
        if self._thread_id:
            import ctypes  # noqa: PLC0415

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def _fire(self) -> None:
        asyncio.run_coroutine_threadsafe(self._on_press(), self._loop)

    def _run(self) -> None:
        import ctypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        ok = user32.RegisterHotKey(None, self._HOTKEY_ID, self.spec.modifiers | MOD_NOREPEAT, self.spec.vk)
        if not ok:
            self.error = f"Windows refused {self.spec.text} (another app may own it; error {ctypes.GetLastError()})"
            self._ready.set()
            return
        self.registered = True
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                    self._fire()
        finally:
            user32.UnregisterHotKey(None, self._HOTKEY_ID)


def start_stop_hotkey(on_press: Callable[[], Awaitable[object]]) -> GlobalHotkey | None:
    """Register the stop hotkey from ``STOP_HOTKEY`` and log the outcome."""
    try:
        spec = hotkey_from_env()
    except ValueError as exc:
        print(f"[JARVIS] Stop hotkey disabled: bad STOP_HOTKEY ({exc})", flush=True)
        return None
    if spec is None:
        print("[JARVIS] Stop hotkey disabled (STOP_HOTKEY=off)", flush=True)
        return None
    hotkey = GlobalHotkey(spec, on_press, asyncio.get_running_loop())
    if hotkey.start():
        print(f"[JARVIS] Stop hotkey registered: {spec.text.upper()} (works from any window)", flush=True)
        return hotkey
    print(f"[JARVIS] Stop hotkey NOT registered: {hotkey.error}", flush=True)
    return None
