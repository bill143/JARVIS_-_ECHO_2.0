"""JARVIS & ECHO 2.0 — desktop build (local microphone + speaker).

Fully-local voice stack with Claude as the brain:

    mic --> Whisper (STT) --> wake-word gate --> Claude --> Kokoro (TTS) --> speaker

Only the Claude API call leaves your machine. STT (Whisper), TTS (Kokoro),
VAD (Silero) and the webcam all run locally. Say "what can you see?" to trigger
the webcam (see ``vision.py``).

Run:  ``python assistant.py``
"""

from __future__ import annotations

import asyncio
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
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)

from vision import (
    VISION_FUNCTION_NAME,
    camera_index_from_env,
    make_desktop_vision_handler,
    vision_tool_schema,
)
from wakeword import WakeWordProcessor, gate_from_env

load_dotenv()

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "JARVIS")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
GREETING = os.getenv("GREETING", "Hey, JARVIS here. How can I help?")

# Route JARVIS's thinking through ECHO (the multi-provider proxy) when
# configured; otherwise fall back to calling Anthropic directly. ECHO speaks an
# OpenAI-compatible API, so we point an OpenAILLMService at it.
ECHO_BASE_URL = os.getenv("ECHO_BASE_URL")  # e.g. http://localhost:4000/v1
ECHO_API_KEY = os.getenv("ECHO_API_KEY") or os.getenv("ECHO_MASTER_KEY")
ECHO_MODEL = os.getenv("ECHO_MODEL", "tier-realtime")


def build_llm():
    """Return the LLM service: ECHO proxy if configured, else Anthropic direct."""
    if ECHO_BASE_URL:
        return OpenAILLMService(
            base_url=ECHO_BASE_URL,
            api_key=ECHO_API_KEY or "not-set",
            model=ECHO_MODEL,
        )
    return AnthropicLLMService(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model=ANTHROPIC_MODEL,
    )


def system_prompt() -> str:
    return (
        f"Your name is {ASSISTANT_NAME}. You are a witty, helpful voice assistant. "
        "Your interface with the user is voice and vision. Keep answers short and "
        "conversational. Avoid unpronounceable punctuation, markdown, and emojis. "
        f"When the user asks about what is visible, call the '{VISION_FUNCTION_NAME}' tool."
    )


async def run() -> None:
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    )

    stt = WhisperSTTService(model=WHISPER_MODEL)
    tts = KokoroTTSService(voice_id=KOKORO_VOICE)
    llm = build_llm()

    # Register the vision tool (local webcam via OpenCV).
    llm.register_function(VISION_FUNCTION_NAME, make_desktop_vision_handler(camera_index_from_env()))
    tools = ToolsSchema(standard_tools=[vision_tool_schema()])

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
            wake_gate,               # drop everything until "hey jarvis"
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

    # Greet on startup.
    await task.queue_frames([TTSSpeakFrame(GREETING)])

    runner = PipelineRunner(handle_sigint=True)
    await runner.run(task)


def main() -> None:
    if not ECHO_BASE_URL and not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Set ECHO_BASE_URL to route through ECHO, or ANTHROPIC_API_KEY to call "
            "Anthropic directly. Copy .env.example to .env to configure."
        )
    asyncio.run(run())


if __name__ == "__main__":
    main()
