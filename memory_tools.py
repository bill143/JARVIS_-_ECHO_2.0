"""Memory tools for JARVIS — ``remember`` and ``recall``.

Two function tools backed by a :class:`memory.MemoryStore` (Obsidian vault or
Supabase pgvector, chosen by env): a shared ``FunctionSchema`` plus a handler
that takes ``FunctionCallParams`` and replies via ``result_callback``.

Store calls are sync (filesystem / network), so they run in a worker thread to
avoid blocking the audio event loop.
"""

from __future__ import annotations

import asyncio
import logging

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from memory import MemoryStore, build_memory, memory_enabled

logger = logging.getLogger(__name__)

REMEMBER_FUNCTION_NAME = "remember"
RECALL_FUNCTION_NAME = "recall"


def remember_tool_schema() -> FunctionSchema:
    return FunctionSchema(
        name=REMEMBER_FUNCTION_NAME,
        description=(
            "Save a fact or preference to long-term memory so you can recall it in "
            "future conversations. Call this whenever the user tells you to remember "
            "something, or shares a durable fact about themselves, their home, or "
            "their preferences."
        ),
        properties={
            "text": {
                "type": "string",
                "description": "The fact to remember, written as a clear standalone sentence.",
            },
        },
        required=["text"],
    )


def recall_tool_schema() -> FunctionSchema:
    return FunctionSchema(
        name=RECALL_FUNCTION_NAME,
        description=(
            "Search your long-term memory for things you saved earlier. Call this "
            "when the user asks what you remember, or when answering needs a fact "
            "they told you in a past conversation."
        ),
        properties={
            "query": {
                "type": "string",
                "description": "What to look for, e.g. 'garage code' or 'favourite coffee'.",
            },
        },
        required=["query"],
    )


def make_remember_handler(store: MemoryStore):
    async def handler(params: FunctionCallParams) -> None:
        text = (params.arguments or {}).get("text", "")
        if not text or not str(text).strip():
            await params.result_callback({"error": "Nothing to remember — no text provided."})
            return
        try:
            record = await asyncio.to_thread(store.add, str(text), {"source": "voice"})
        except Exception as exc:  # don't let a storage hiccup break the call
            await params.result_callback({"error": f"Could not save that: {exc}"})
            return
        await params.result_callback(
            {"status": "saved", "id": record.id, "note": "Tell the user you'll remember that."}
        )

    return handler


def make_recall_handler(store: MemoryStore, k: int = 5):
    async def handler(params: FunctionCallParams) -> None:
        query = (params.arguments or {}).get("query", "")
        try:
            records = await asyncio.to_thread(store.search, str(query), k)
        except Exception as exc:
            await params.result_callback({"error": f"Could not search memory: {exc}"})
            return
        if not records:
            await params.result_callback(
                {"results": [], "note": "Nothing relevant in memory; tell the user you don't recall."}
            )
            return
        await params.result_callback(
            {
                "results": [{"text": r.text, "created_at": r.created_at} for r in records],
                "note": "Use these remembered facts to answer the user.",
            }
        )

    return handler


def register_memory_tools(llm) -> list[FunctionSchema]:
    """Wire ``remember``/``recall`` onto the LLM service if memory is enabled.

    Returns the tool schemas to add to the ToolsSchema (empty list if memory is
    disabled or the backend can't be built — JARVIS keeps working without it).
    """
    if not memory_enabled():
        return []
    try:
        store = build_memory()
    except Exception as exc:  # bad config shouldn't break the voice loop
        logger.warning("Memory disabled — could not build backend: %s", exc)
        return []
    llm.register_function(REMEMBER_FUNCTION_NAME, make_remember_handler(store))
    llm.register_function(RECALL_FUNCTION_NAME, make_recall_handler(store))
    logger.info("Memory enabled (%s).", type(store).__name__)
    return [remember_tool_schema(), recall_tool_schema()]
