"""JARVIS & ECHO 2.0 — browser build (WebRTC microphone).

Closest to the old LiveKit UX: you talk to JARVIS in the browser. Same brain and
same local voice stack (Whisper + Kokoro + Silero) as the desktop build — only
the transport and the greeting trigger differ. Voice-only this phase (vision is
quarantined in ``/deferred``).

Pipecat's development runner serves a ready-made web client and handles all the
WebRTC signalling, so there's nothing else to wire up.

Run:  ``python assistant_web.py``   then open the printed URL (default
http://localhost:7860).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from wakeword import WakeWordProcessor, gate_from_env
from brain_guard import ValidatedOpenAILLMService
from brain_config import echo_base_url, real_secret, resolve_echo_key
from memory_tools import register_memory_tools
from time_tools import register_time_tools
from vision_tools import register_vision_tools
from mcp_tools import register_mcp_tools

load_dotenv()

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "JARVIS")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
# "cpu" works everywhere. "cuda"/"auto" need the CUDA 12 runtime (cuBLAS + cuDNN)
# on PATH; without it faster-whisper fails every segment with
# "cublas64_12.dll is not found" whenever an NVIDIA GPU is present.
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu").strip().lower() or "cpu"
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8" if WHISPER_DEVICE == "cpu" else "default")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
GREETING = os.getenv("GREETING", "Hey, JARVIS here. How can I help?")

# Route through ECHO (OpenAI-compatible) when configured, else Anthropic direct.
ECHO_BASE_URL = echo_base_url()  # e.g. http://localhost:4000/v1
ECHO_API_KEY = resolve_echo_key(ECHO_BASE_URL)
# Default: ECHO's free 'brain' alias (Groq -> local Ollama -> paid clouds); set e.g. gemini-3.1-pro-preview
# or tier-realtime to use a funded cloud model instead.
ECHO_MODEL = (os.getenv("ECHO_MODEL") or "").strip() or "brain"
ANTHROPIC_API_KEY = real_secret("ANTHROPIC_API_KEY")


def build_llm():
    """Return the LLM service: ECHO proxy if configured, else Anthropic direct."""
    if ECHO_BASE_URL:
        if not ECHO_API_KEY:
            raise SystemExit(
                "ECHO_BASE_URL is set but ECHO_API_KEY (or ECHO_MASTER_KEY) is empty. "
                "Add ECHO's key to your .env so JARVIS can authenticate to the proxy."
            )
        print(f"[JARVIS] Brain: ECHO -> {ECHO_BASE_URL} (model {ECHO_MODEL})", flush=True)
        # Validates/retries the reply after a tool call (no empty or non-English answers).
        return ValidatedOpenAILLMService(
            base_url=ECHO_BASE_URL,
            api_key=ECHO_API_KEY,
            model=ECHO_MODEL,
        )
    print(f"[JARVIS] Brain: Anthropic direct (model {ANTHROPIC_MODEL})", flush=True)
    return AnthropicLLMService(
        api_key=ANTHROPIC_API_KEY,
        model=ANTHROPIC_MODEL,
    )


def system_prompt() -> str:
    return (
        f"Your name is {ASSISTANT_NAME}. You are a witty, helpful voice assistant. "
        "Think the problem through step by step silently before you answer, but only "
        "ever SAY the short conclusion: one to three conversational sentences. "
        "Your interface with the user is voice, so avoid unpronounceable punctuation, "
        "markdown, lists, and emojis. Use your tools instead of guessing: "
        "get_current_time for the time or date; remember and recall for anything the "
        "user wants kept or asks you to remember; look_camera when they say things like "
        "'what do you see' or 'look at this'; look_screen when they ask what is on "
        "their screen. Answer from what the tools return."
    )


async def run_bot(transport: BaseTransport) -> None:
    stt = WhisperSTTService(
        model=WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
    )
    tts = KokoroTTSService(voice_id=KOKORO_VOICE)
    llm = build_llm()

    # Cross-session memory (remember/recall) and any configured MCP servers.
    mcp_schemas, mcp_clients = await register_mcp_tools(llm)  # keep clients alive for the session
    tools = ToolsSchema(
        standard_tools=[
            *register_time_tools(llm),
            *register_memory_tools(llm),
            *register_vision_tools(llm, ECHO_BASE_URL, ECHO_API_KEY),
            *mcp_schemas,
        ]
    )

    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt()}],
        tools=tools,
    )
    # Pipecat 1.x runs VAD in the user aggregator; TransportParams no longer has a
    # vad_analyzer field (it was silently ignored), which left Whisper deaf.
    aggregators = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            # The wake gate drops non-wake speech, leaving a turn with no transcript;
            # Pipecat's default would still run the LLM for it (and Anthropic rejects
            # a context with no user message). Never answer what the gate filtered.
            empty_user_turn=None,
        ),
    )

    wake_gate = WakeWordProcessor(gate_from_env())

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            wake_gate,
            aggregators.user(),
            llm,
            tts,
            transport.output(),
            aggregators.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True, enable_metrics=False),
    )

    @transport.event_handler("on_client_connected")
    async def _on_client_connected(transport, client):  # noqa: ANN001
        # Greet as soon as the browser connects.
        await task.queue_frames([TTSSpeakFrame(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def _on_client_disconnected(transport, client):  # noqa: ANN001
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


async def bot(runner_args: RunnerArguments) -> None:
    """Entry point the Pipecat dev runner calls when a browser connects."""
    transport = SmallWebRTCTransport(
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,          # voice-only: no video track this phase
        ),
        webrtc_connection=runner_args.webrtc_connection,
    )
    await run_bot(transport)


if __name__ == "__main__":
    if not ECHO_BASE_URL and not ANTHROPIC_API_KEY:
        raise SystemExit(
            "No brain configured: ECHO_BASE_URL is blank and ANTHROPIC_API_KEY is empty "
            "or still the .env.example placeholder. Set ECHO_BASE_URL (+ ECHO_API_KEY) to "
            "route through ECHO, or a real ANTHROPIC_API_KEY to call Anthropic directly."
        )
    from pipecat.runner.run import main

    main()
