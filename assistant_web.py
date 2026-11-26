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
)
from pipecat.runner.types import RunnerArguments
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from wakeword import WakeWordProcessor, gate_from_env
from brain_config import echo_base_url, real_secret
from memory_tools import register_memory_tools
from mcp_tools import register_mcp_tools

load_dotenv()

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "JARVIS")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
GREETING = os.getenv("GREETING", "Hey, JARVIS here. How can I help?")

# Route through ECHO (OpenAI-compatible) when configured, else Anthropic direct.
ECHO_BASE_URL = echo_base_url()  # e.g. http://localhost:4000/v1
ECHO_API_KEY = real_secret("ECHO_API_KEY", "ECHO_MASTER_KEY")
ECHO_MODEL = os.getenv("ECHO_MODEL", "gemini-3.1-pro-preview")
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
        return OpenAILLMService(
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
        "Your interface with the user is voice. Keep answers short and "
        "conversational. Avoid unpronounceable punctuation, markdown, and emojis."
    )


async def run_bot(transport: BaseTransport) -> None:
    stt = WhisperSTTService(model=WHISPER_MODEL)
    tts = KokoroTTSService(voice_id=KOKORO_VOICE)
    llm = build_llm()

    # Cross-session memory (remember/recall) and any configured MCP servers.
    mcp_schemas, mcp_clients = await register_mcp_tools(llm)  # keep clients alive for the session
    tools = ToolsSchema(standard_tools=[*register_memory_tools(llm), *mcp_schemas])

    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt()}],
        tools=tools,
    )
    aggregators = LLMContextAggregatorPair(context)

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
            vad_analyzer=SileroVADAnalyzer(),
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
