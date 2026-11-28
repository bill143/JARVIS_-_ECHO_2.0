"""Make the brain's first reply after a tool call reliably English and non-empty.

On ECHO's ``brain`` alias (Groq llama-3.3-70b, falling back to local qwen2.5) the
answer that follows a tool result sometimes came back empty, in Thai/Chinese, or
as leaked tool-call markup (``<function=...>``). Spoken by Kokoro, that is either
silence or gibberish.

``ValidatedOpenAILLMService`` buffers ONLY the completion that follows a tool
result, checks it, and retries the same request (up to ``POST_TOOL_ATTEMPTS``)
before letting Pipecat stream it on to TTS. Retries ask LiteLLM not to fall back
to another model (``disable_fallbacks``), so a retry stays on the model JARVIS
asked for instead of drifting further down the chain. Ordinary replies are not
buffered.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from openai.types.chat import ChatCompletionChunk
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.openai.llm import OpenAILLMService

POST_TOOL_ATTEMPTS = 3
PIN_COOLDOWN_SECS = 300.0  # after a pinned retry fails (primary down), stop pinning for a while
FALLBACK_REPLY = "Sorry, I lost my train of thought there. Could you ask me that again?"
_LEAKED_TOOL_MARKUP = re.compile(r"<\s*/?\s*(function|tool_call|tool)\b|\bfunction=", re.IGNORECASE)
_MIN_LATIN_SHARE = 0.9


def _is_latin_letter(ch: str) -> bool:
    try:
        return unicodedata.name(ch).startswith("LATIN")
    except ValueError:
        return False


def reply_problem(text: str) -> str | None:
    """Why ``text`` is not a speakable English reply, or None when it is fine."""
    stripped = (text or "").strip()
    letters = [ch for ch in stripped if ch.isalpha()]
    if not letters:
        return "empty"
    if _LEAKED_TOOL_MARKUP.search(stripped):
        return "tool-call markup instead of an answer"
    latin = sum(1 for ch in letters if _is_latin_letter(ch))
    if latin / len(letters) < _MIN_LATIN_SHARE:
        return f"not English ({len(letters) - latin} of {len(letters)} letters non-Latin)"
    return None


def follows_tool_result(context: LLMContext) -> bool:
    """True when this inference is the brain's answer to a tool result."""
    messages = context.get_messages()
    return bool(messages) and messages[-1].get("role") == "tool"


class _ReplayStream:
    """An already-received chunk list, shaped like the OpenAI async stream."""

    def __init__(self, chunks: list[ChatCompletionChunk]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[ChatCompletionChunk]:
        for chunk in self._chunks:
            yield chunk

    async def close(self) -> None:
        return None


def _text_chunk(template: ChatCompletionChunk | None, model: str, text: str) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate(
        {
            "id": template.id if template else "jarvis-fallback",
            "object": "chat.completion.chunk",
            "created": template.created if template else 0,
            "model": (template.model if template else None) or model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        }
    )


def summarize_chunks(chunks: list[ChatCompletionChunk]) -> tuple[str, bool, str]:
    """(reply text, whether it calls tools, model that served it)."""
    text, has_tool_calls, served_by = [], False, ""
    for chunk in chunks:
        served_by = chunk.model or served_by
        for choice in chunk.choices or []:
            delta = choice.delta
            if delta is None:
                continue
            if delta.tool_calls:
                has_tool_calls = True
            if delta.content:
                text.append(delta.content)
    return "".join(text), has_tool_calls, served_by


class ValidatedOpenAILLMService(OpenAILLMService):
    """OpenAI-compatible LLM whose post-tool replies are validated and retried."""

    def __init__(self, *args: Any, post_tool_attempts: int = POST_TOOL_ATTEMPTS, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._post_tool_attempts = max(1, post_tool_attempts)
        self._pin_model = False
        self._pin_broken_until = 0.0

    def build_chat_completion_params(self, params_from_context):  # type: ignore[override]
        params = super().build_chat_completion_params(params_from_context)
        if self._pin_model:
            self._merge_extra_body(params, {"disable_fallbacks": True})
        return params

    async def _receive(self, context: LLMContext, pin_model: bool) -> list[ChatCompletionChunk]:
        self._pin_model = pin_model
        try:
            stream = await super().get_chat_completions(context)
        finally:
            self._pin_model = False
        chunks: list[ChatCompletionChunk] = []
        try:
            async for chunk in stream:
                chunks.append(chunk)
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                await close()
        return chunks

    async def get_chat_completions(self, context: LLMContext):  # type: ignore[override]
        if not follows_tool_result(context):
            return await super().get_chat_completions(context)
        chunks: list[ChatCompletionChunk] = []
        pin = False  # the first try uses ECHO's normal fallback chain
        for attempt in range(1, self._post_tool_attempts + 1):
            try:
                chunks = await self._receive(context, pin_model=pin)
            except Exception as exc:  # noqa: BLE001 - a failed retry must not kill the turn
                if attempt == 1:
                    raise
                # The pinned primary is down (the first answer came from a fallback):
                # retry through the chain again rather than give up.
                logger.warning(f"[brain] post-tool retry {attempt} failed: {type(exc).__name__}: {exc}")
                pin = False
                self._pin_broken_until = time.monotonic() + PIN_COOLDOWN_SECS
                continue
            # Retries stay on the requested model (no drift down the chain) unless
            # that model was just found to be down.
            pin = time.monotonic() >= self._pin_broken_until
            text, has_tool_calls, served_by = summarize_chunks(chunks)
            problem = None if has_tool_calls else reply_problem(text)
            if problem is None:
                if attempt > 1:
                    logger.info(f"[brain] post-tool reply OK on attempt {attempt} ({served_by})")
                return _ReplayStream(chunks)
            logger.warning(
                f"[brain] post-tool reply rejected (attempt {attempt}/{self._post_tool_attempts}, "
                f"{served_by or 'unknown model'}): {problem}: {text[:80]!r}"
            )
        logger.error("[brain] no usable post-tool reply; speaking the fallback line")
        usage = [c for c in chunks if c.usage]
        return _ReplayStream([_text_chunk(chunks[0] if chunks else None, self._settings.model, FALLBACK_REPLY), *usage])
