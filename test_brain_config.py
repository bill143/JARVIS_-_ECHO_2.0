"""Offline tests for brain_config (no network). Run:  python test_brain_config.py"""

from __future__ import annotations

import os

from brain_config import echo_base_url, real_secret

VARS = ("ANTHROPIC_API_KEY", "ECHO_API_KEY", "ECHO_MASTER_KEY", "ECHO_BASE_URL")


def _set(**values: str) -> None:
    for name in VARS:
        os.environ.pop(name, None)
    os.environ.update(values)


def test_placeholder_key_is_unset() -> None:
    _set(ANTHROPIC_API_KEY="sk-ant-your-key-here")
    assert real_secret("ANTHROPIC_API_KEY") is None


def test_blank_and_missing_are_unset() -> None:
    _set(ANTHROPIC_API_KEY="   ")
    assert real_secret("ANTHROPIC_API_KEY") is None
    _set()
    assert real_secret("ANTHROPIC_API_KEY") is None


def test_real_key_passes_and_is_trimmed() -> None:
    _set(ANTHROPIC_API_KEY="  sk-ant-api03-abc  ")
    assert real_secret("ANTHROPIC_API_KEY") == "sk-ant-api03-abc"


def test_fallback_order() -> None:
    _set(ECHO_API_KEY="change-me", ECHO_MASTER_KEY="sk-echo-real")
    assert real_secret("ECHO_API_KEY", "ECHO_MASTER_KEY") == "sk-echo-real"


def test_echo_base_url_blank_is_none() -> None:
    _set(ECHO_BASE_URL="  ")
    assert echo_base_url() is None
    _set(ECHO_BASE_URL=" http://localhost:4000/v1 ")
    assert echo_base_url() == "http://localhost:4000/v1"


TESTS = [
    ("placeholder key is unset", test_placeholder_key_is_unset),
    ("blank/missing are unset", test_blank_and_missing_are_unset),
    ("real key passes + trimmed", test_real_key_passes_and_is_trimmed),
    ("fallback order", test_fallback_order),
    ("blank ECHO_BASE_URL is None", test_echo_base_url_blank_is_none),
]

if __name__ == "__main__":
    for label, fn in TESTS:
        fn()
        print(f"  ok - {label}")
    print(f"\nbrain_config: {len(TESTS)}/{len(TESTS)} checks passed")
