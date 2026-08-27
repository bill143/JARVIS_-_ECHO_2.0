"""Full import-graph smoke test (requires the Pipecat extras installed).

Resolves every symbol the two voice-only builds rely on, then constructs the
context, the aggregator pair, the tool schema, and the memory + MCP wiring — all
without a live API key or mic. Also asserts the SCOPE LOCK: vision must NOT be
importable from the shipped root (it is quarantined in ``/deferred``).

Usage:  ``python test_imports.py``

This complements ``test_wakeword.py`` (which needs no heavy deps). The full
audio round-trip still needs a live run with a mic and ECHO/Anthropic.
"""

from __future__ import annotations


def resolve_symbols() -> dict[str, object]:
    """Import every symbol the voice-only app depends on. Raises on any failure."""
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import TTSSpeakFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
    )
    from pipecat.runner.types import RunnerArguments
    from pipecat.services.anthropic.llm import AnthropicLLMService
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.services.mcp_service import MCPClient
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.local.audio import (
        LocalAudioTransport,
        LocalAudioTransportParams,
    )
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    from wakeword import WakeWordGate, WakeWordProcessor
    from memory_tools import (
        recall_tool_schema,
        register_memory_tools,
        remember_tool_schema,
    )
    from mcp_tools import build_server_params, register_mcp_tools

    return {
        "Pipeline": Pipeline,
        "PipelineTask": PipelineTask,
        "PipelineParams": PipelineParams,
        "PipelineRunner": PipelineRunner,
        "LLMContext": LLMContext,
        "LLMContextAggregatorPair": LLMContextAggregatorPair,
        "AnthropicLLMService": AnthropicLLMService,
        "OpenAILLMService": OpenAILLMService,
        "WhisperSTTService": WhisperSTTService,
        "KokoroTTSService": KokoroTTSService,
        "SileroVADAnalyzer": SileroVADAnalyzer,
        "LocalAudioTransport": LocalAudioTransport,
        "LocalAudioTransportParams": LocalAudioTransportParams,
        "SmallWebRTCTransport": SmallWebRTCTransport,
        "TransportParams": TransportParams,
        "RunnerArguments": RunnerArguments,
        "ToolsSchema": ToolsSchema,
        "FunctionSchema": FunctionSchema,
        "FunctionCallParams": FunctionCallParams,
        "TTSSpeakFrame": TTSSpeakFrame,
        "WakeWordGate": WakeWordGate,
        "WakeWordProcessor": WakeWordProcessor,
        "remember_tool_schema": remember_tool_schema,
        "recall_tool_schema": recall_tool_schema,
        "register_memory_tools": register_memory_tools,
        "MCPClient": MCPClient,
        "register_mcp_tools": register_mcp_tools,
        "build_server_params": build_server_params,
    }


def assert_vision_quarantined() -> None:
    """SCOPE LOCK: vision must not be importable from a shipped module."""
    import importlib

    try:
        importlib.import_module("vision")
    except ModuleNotFoundError:
        return  # correct: vision is quarantined in /deferred
    raise SystemExit("SCOPE VIOLATION: 'vision' is importable from the shipped root")


def main() -> None:
    assert_vision_quarantined()

    symbols = resolve_symbols()
    total = len(symbols)
    resolved = sum(1 for v in symbols.values() if v is not None)
    for name, obj in symbols.items():
        print(f"[OK] {name} -> {obj}")

    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
    )

    # Exercise the memory tools against a throwaway local vault + stub LLM.
    import os
    import tempfile

    from memory_tools import register_memory_tools

    with tempfile.TemporaryDirectory() as vault:
        os.environ.update(
            MEMORY_ENABLED="true", MEMORY_BACKEND="obsidian", OBSIDIAN_VAULT_PATH=vault
        )

        class _StubLLM:
            def __init__(self):
                self.registered = []

            def register_function(self, name, handler):
                self.registered.append(name)

        stub = _StubLLM()
        mem_schemas = register_memory_tools(stub)
        assert len(mem_schemas) == 2, "expected remember+recall schemas"
        assert set(stub.registered) == {"remember", "recall"}

    # MCP: build real ServerParameters from configs, and confirm register is a
    # safe no-op when disabled (default).
    import asyncio

    from mcp_tools import build_server_params, register_mcp_tools

    stdio_params = build_server_params({"command": "npx", "args": ["-y", "srv"]})
    http_params = build_server_params({"url": "https://example.com/mcp"})
    assert stdio_params.command == "npx"
    assert http_params.url.endswith("/mcp")
    os.environ.pop("MCP_ENABLED", None)
    mcp_schemas, mcp_clients = asyncio.run(register_mcp_tools(stub))
    assert mcp_schemas == [] and mcp_clients == [], "MCP must be a no-op when disabled"

    tools = ToolsSchema(standard_tools=[*mem_schemas, *mcp_schemas])
    context = LLMContext(messages=[{"role": "system", "content": "test"}], tools=tools)
    aggregators = LLMContextAggregatorPair(context)
    assert aggregators.user() is not None
    assert aggregators.assistant() is not None
    print("\nVision quarantined; context, aggregators, tools, memory, and MCP wiring construct cleanly.")

    print(f"\n{resolved}/{total} symbols resolve")
    if resolved != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
