"""Tests for brain_guard.py: post-tool replies are validated and retried.

Run: ``python test_brain_guard.py``. No network: the OpenAI stream is faked one
level below ``ValidatedOpenAILLMService`` so the real retry logic runs.
"""

from __future__ import annotations

import asyncio
from unittest import mock

from openai.types.chat import ChatCompletionChunk
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.openai.base_llm import BaseOpenAILLMService

from brain_guard import FALLBACK_REPLY, ValidatedOpenAILLMService, reply_problem, summarize_chunks


def _chunk(text: str | None = None, model: str = "llama-3.3-70b-versatile", tool: bool = False) -> ChatCompletionChunk:
    delta: dict = {"role": "assistant"}
    if text is not None:
        delta["content"] = text
    if tool:
        delta["tool_calls"] = [{"index": 0, "id": "c1", "type": "function",
                                "function": {"name": "get_current_time", "arguments": "{}"}}]
    return ChatCompletionChunk.model_validate({
        "id": "x", "object": "chat.completion.chunk", "created": 0, "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    })


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        async def gen():
            for c in self._chunks:
                yield c
        return gen()

    async def close(self):
        return None


def _context(after_tool: bool) -> LLMContext:
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "what time is it"}]
    if after_tool:
        messages += [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "get_current_time", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": '{"time": "4:20 PM"}'},
        ]
    return LLMContext(messages=messages)


def _service() -> ValidatedOpenAILLMService:
    return ValidatedOpenAILLMService(base_url="http://127.0.0.1:9/v1", api_key="test", model="brain")


def _run_with_replies(after_tool: bool, replies, pinned_seen=None):
    """Feed ``replies`` (chunk lists, or exceptions) to successive requests."""
    service = _service()
    queue = list(replies)
    calls = {"n": 0}

    async def fake_get(self, context):
        calls["n"] += 1
        if pinned_seen is not None:
            pinned_seen.append(self._pin_model)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeStream(item)

    async def scenario():
        with mock.patch.object(BaseOpenAILLMService, "get_chat_completions", fake_get):
            stream = await service.get_chat_completions(_context(after_tool))
            text, _, _ = summarize_chunks([c async for c in stream])
            return text

    return asyncio.run(scenario()), calls["n"]


def test_reply_problem_classifies():
    assert reply_problem("It's 4:20 PM, Bill.") is None
    assert reply_problem("Café time, it's 4:20.") is None
    assert reply_problem("") == "empty"
    assert reply_problem("  ...  ") == "empty"
    assert reply_problem("ตอนนี้เวลา 4:20 น.").startswith("not English")
    assert reply_problem("现在是下午四点二十分").startswith("not English")
    assert reply_problem("<function=get_current_time>{}</function>") == "tool-call markup instead of an answer"


def test_good_post_tool_reply_passes_first_time():
    text, calls = _run_with_replies(True, [[_chunk("It's "), _chunk("4:20 PM.")]])
    assert text == "It's 4:20 PM." and calls == 1


def test_thai_reply_is_retried_pinned_to_same_model():
    pinned = []
    text, calls = _run_with_replies(True, [[_chunk("ตอนนี้เวลา 4:20")], [_chunk("It's 4:20 PM.")]], pinned)
    assert text == "It's 4:20 PM." and calls == 2
    assert pinned == [False, True], pinned  # the retry asks ECHO not to fall back


def test_empty_reply_is_retried():
    text, calls = _run_with_replies(True, [[_chunk("")], [_chunk(None)], [_chunk("It is 4:20.")]])
    assert text == "It is 4:20." and calls == 3


def test_all_bad_speaks_honest_fallback():
    text, calls = _run_with_replies(True, [[_chunk("")], [_chunk("ตอน")], [_chunk("")]])
    assert text == FALLBACK_REPLY and calls == 3


def test_failed_pinned_retry_unpins():
    pinned = []
    text, calls = _run_with_replies(
        True,
        [[_chunk("", model="qwen2.5:14b")], RuntimeError("groq 404"), [_chunk("It's 4:20.", model="qwen2.5:14b")]],
        pinned,
    )
    assert text == "It's 4:20." and calls == 3
    assert pinned == [False, True, False], pinned


def test_tool_call_reply_is_not_rejected():
    text, calls = _run_with_replies(True, [[_chunk(tool=True)]])
    assert calls == 1 and text == ""


def test_ordinary_replies_are_not_buffered_or_checked():
    text, calls = _run_with_replies(False, [[_chunk("")]])
    assert calls == 1 and text == ""


def test_pin_adds_disable_fallbacks_only_when_pinned():
    service = _service()
    unpinned = service.build_chat_completion_params({"messages": []})
    assert "disable_fallbacks" not in (unpinned.get("extra_body") or {})
    service._pin_model = True
    assert service.build_chat_completion_params({"messages": []})["extra_body"]["disable_fallbacks"] is True


TESTS = [
    ("classifies empty / Thai / Chinese / tool markup / English", test_reply_problem_classifies),
    ("good post-tool reply passes on the first try", test_good_post_tool_reply_passes_first_time),
    ("Thai post-tool reply is retried, pinned to the same model", test_thai_reply_is_retried_pinned_to_same_model),
    ("empty post-tool reply is retried", test_empty_reply_is_retried),
    ("every attempt bad -> honest fallback line, never silence", test_all_bad_speaks_honest_fallback),
    ("a pinned retry that errors falls back to the normal chain", test_failed_pinned_retry_unpins),
    ("a reply that calls another tool is passed through", test_tool_call_reply_is_not_rejected),
    ("ordinary (non-tool) replies are not buffered", test_ordinary_replies_are_not_buffered_or_checked),
    ("disable_fallbacks is sent only on pinned retries", test_pin_adds_disable_fallbacks_only_when_pinned),
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
    print(f"\nbrain_guard: {passed}/{len(TESTS)} checks passed")
    if passed != len(TESTS):
        raise SystemExit(1)
