"""Full import-graph smoke test (requires the Pipecat extras installed).

Resolves every symbol the two builds rely on, then constructs the context, the
aggregator pair, the tool schema, and both vision handlers — all without a live
API key, mic, or camera. Usage:  ``python test_imports.py``

This complements ``test_wakeword.py`` (which needs no heavy deps). The full
audio/vision round-trip still needs a live run with an ANTHROPIC_API_KEY.
"""

from __future__ import annotations


def resolve_symbols() -> dict[str, object]:
    """Import the 27 symbols the app depends on. Raises on any failure."""
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import (
        TTSSpeakFrame,
        UserImageRawFrame,
        UserImageRequestFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
    )
    from pipecat.processors.frame_processor import FrameDirection
    from pipecat.runner.types import RunnerArguments
    from pipecat.services.anthropic.llm import AnthropicLLMService
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.local.audio import (
        LocalAudioTransport,
        LocalAudioTransportParams,
    )
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    from vision import (
        make_desktop_vision_handler,
        make_web_vision_handler,
        vision_tool_schema,
    )
    from wakeword import WakeWordGate, WakeWordProcessor
    from memory_tools import (
        recall_tool_schema,
        register_memory_tools,
        remember_tool_schema,
    )

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
        "UserImageRawFrame": UserImageRawFrame,
        "UserImageRequestFrame": UserImageRequestFrame,
        "FrameDirection": FrameDirection,
        "WakeWordGate": WakeWordGate,
        "WakeWordProcessor": WakeWordProcessor,
        "vision_tool_schema": vision_tool_schema,
        "make_desktop_vision_handler": make_desktop_vision_handler,
        "make_web_vision_handler": make_web_vision_handler,
        "remember_tool_schema": remember_tool_schema,
        "recall_tool_schema": recall_tool_schema,
        "register_memory_tools": register_memory_tools,
    }


def main() -> None:
    symbols = resolve_symbols()
    total = len(symbols)
    resolved = sum(1 for v in symbols.values() if v is not None)
    for name, obj in symbols.items():
        print(f"[OK] {name} -> {obj}")

    # Construct the pieces that don't need a key / device.
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
    )

    from vision import (
        make_desktop_vision_handler,
        make_web_vision_handler,
        vision_tool_schema,
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

    tools = ToolsSchema(standard_tools=[vision_tool_schema(), *mem_schemas])
    context = LLMContext(messages=[{"role": "system", "content": "test"}], tools=tools)
    aggregators = LLMContextAggregatorPair(context)
    assert aggregators.user() is not None
    assert aggregators.assistant() is not None
    assert callable(make_desktop_vision_handler(0))
    assert callable(make_web_vision_handler())
    print("\nContext, aggregators, tool schema, vision handlers, and memory tools construct cleanly.")

    print(f"\n{resolved}/{total} symbols resolve")
    if resolved != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
