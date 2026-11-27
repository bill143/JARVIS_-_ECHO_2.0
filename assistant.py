"""JARVIS & ECHO 2.0 — desktop build (local microphone + speaker).

Fully-local voice stack; ECHO (or Claude direct) as the brain:

    mic --> Whisper (STT) --> wake-word gate --> LLM --> Kokoro (TTS) --> speaker

STT (Whisper), TTS (Kokoro) and VAD (Silero) all run locally; only the LLM call
leaves the machine. A live dashboard window runs alongside at
http://127.0.0.1:8090 (see ``dashboard/``).

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
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.turns.user_mute import FunctionCallUserMuteStrategy
from pipecat.turns.user_start import TranscriptionUserTurnStartStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)

from brain_config import echo_base_url, real_secret, resolve_echo_key
from dashboard import EventBus
from dashboard.runtime import start_dashboard
from dashboard.taps import BotAudioTap, BotTap, HeardTap, MicState, MicTap, ToolTap, UserTap
from interrupt import EchoSafeVADUserTurnStartStrategy, InterruptSwitch, SpeechGuard
from memory import build_memory, memory_enabled
from people import PeopleStore
from toolbox.runtime import ToolboxRuntime
from toolbox.store import ToolboxStore
from people_tools import people_index, register_people_tools
from vision_tools import set_face_hook
from wakeword import WakeWordProcessor, gate_from_env
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

# Route JARVIS's thinking through ECHO (the multi-provider proxy) when
# configured; otherwise fall back to calling Anthropic directly. ECHO speaks an
# OpenAI-compatible API, so we point an OpenAILLMService at it.
ECHO_BASE_URL = echo_base_url()  # e.g. http://localhost:4000/v1
# Whichever of ECHO_API_KEY / ECHO_MASTER_KEY the proxy actually accepts (a stale
# ECHO_API_KEY after a master-key rotation used to break every LLM call).
ECHO_API_KEY = resolve_echo_key(ECHO_BASE_URL)
# Default: ECHO's free 'brain' alias (Groq -> local Ollama -> paid clouds); set e.g. gemini-3.1-pro-preview
# or tier-realtime to use a funded cloud model instead.
ECHO_MODEL = (os.getenv("ECHO_MODEL") or "").strip() or "brain"
ANTHROPIC_API_KEY = real_secret("ANTHROPIC_API_KEY")


def _optional_int_env(name: str):
    """Parse an optional integer env var; blank/invalid -> None (use OS default)."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


# Explicit audio device indices (PyAudio). Leave unset to use the OS defaults.
# Run `python mic_test.py` to list device indices and levels, then set e.g.
# AUDIO_INPUT_DEVICE_INDEX=3 to force a specific microphone.
AUDIO_INPUT_DEVICE_INDEX = _optional_int_env("AUDIO_INPUT_DEVICE_INDEX")
# Or choose the microphone by (part of) its name, e.g. AUDIO_INPUT_DEVICE_NAME=ATR4650.
# Windows reshuffles device indices as USB devices come and go; names are stable.
AUDIO_INPUT_DEVICE_NAME = (os.getenv("AUDIO_INPUT_DEVICE_NAME") or "").strip()


def _input_device_by_name(name: str):
    """Index of the first input device (MME first, as Pipecat opens it) whose name contains ``name``."""
    try:
        import pyaudio
    except ImportError:
        return None
    pa = pyaudio.PyAudio()
    try:
        wanted = name.lower()
        matches = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0 and wanted in str(info.get("name", "")).lower():
                matches.append((info.get("hostApi", 99), i))
        return min(matches)[1] if matches else None
    finally:
        pa.terminate()


# A device NAME wins over an index when both are set (names survive re-plugging).
_MIC_SOURCE = "AUDIO_INPUT_DEVICE_INDEX"
if AUDIO_INPUT_DEVICE_NAME:
    _by_name = _input_device_by_name(AUDIO_INPUT_DEVICE_NAME)
    if _by_name is not None:
        AUDIO_INPUT_DEVICE_INDEX = _by_name
        _MIC_SOURCE = f"AUDIO_INPUT_DEVICE_NAME={AUDIO_INPUT_DEVICE_NAME}"
    else:
        print(f"[JARVIS] No microphone matches AUDIO_INPUT_DEVICE_NAME={AUDIO_INPUT_DEVICE_NAME!r}; "
              "falling back to AUDIO_INPUT_DEVICE_INDEX / the OS default.", flush=True)
AUDIO_OUTPUT_DEVICE_INDEX = _optional_int_env("AUDIO_OUTPUT_DEVICE_INDEX")


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


def system_prompt(people_line: str = "") -> str:
    return (
        f"Your name is {ASSISTANT_NAME}. You are a witty, helpful voice assistant. "
        "Think the problem through step by step silently before you answer, but only "
        "ever SAY the short conclusion: one to three conversational sentences. "
        "Your interface with the user is voice, so avoid unpronounceable punctuation, "
        "markdown, lists, and emojis. Use your tools instead of guessing: "
        "get_current_time for the time or date; remember and recall for anything the "
        "user wants kept or asks you to remember; look_camera when they say things like "
        "'what do you see' or 'look at this'; look_screen when they ask what is on "
        "their screen; lookup_person / list_people for anyone the user knows. "
        "Answer from what the tools return. When a look names a recognized person, use "
        "that name; never guess who someone is."
        + (f" {people_line}" if people_line else "")
    )


def report_microphone() -> str:
    """Print which input device JARVIS will open (index + name) at startup.

    This only *queries* device metadata — it never opens a capture stream. An
    earlier version opened a short probe stream here, but on Windows that extra
    open/close left the device handing digital silence to the pipeline that
    opened it a moment later. Run ``python mic_test.py`` to check live levels.
    """
    try:
        import pyaudio
    except ImportError:
        return "unknown"
    pa = pyaudio.PyAudio()
    try:
        index = AUDIO_INPUT_DEVICE_INDEX
        if index is None:
            info = pa.get_default_input_device_info()
            index = int(info["index"])
            source = "OS default"
        else:
            info = pa.get_device_info_by_index(index)
            source = _MIC_SOURCE
        print(f"[JARVIS] Microphone: {source} -> index {index} ({info['name']})", flush=True)
        return f"{info['name']} (index {index})"
    except Exception as exc:  # noqa: BLE001 - purely diagnostic
        print(f"[JARVIS] Microphone check failed: {exc}", flush=True)
        return "unknown"
    finally:
        pa.terminate()


def _people_store():
    """Local people store (SQLite + photos), mirrored into the Obsidian vault if one is set."""
    if os.getenv("PEOPLE_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    vault = None
    if os.getenv("MEMORY_BACKEND", "obsidian").strip().lower() == "obsidian":
        vault = os.getenv("OBSIDIAN_VAULT_PATH", "./memory_vault")
    try:
        store = PeopleStore(vault=vault)
    except Exception as exc:  # people are optional; voice keeps working
        print(f"[JARVIS] People store disabled: {exc}", flush=True)
        return None
    print(f"[JARVIS] People: {len(store.list())} known, stored in {store.dir}", flush=True)
    return store


def _face_hook(store):
    """look_camera -> "I see Mike (confidence 0.71)." using only enrolled photos, offline."""

    def hook(jpeg: bytes):
        from people.faces import decode_image, describe_faces, recognize  # heavy; loaded on first look

        known = store.encodings()
        return describe_faces(recognize(decode_image(jpeg), known))

    return hook


def _dashboard_memory():
    """A read-only handle on the same memory store the tools write to (or None)."""
    if not memory_enabled():
        return None
    try:
        return build_memory()
    except Exception as exc:  # memory misconfigured: the dashboard just hides it
        print(f"[JARVIS] Dashboard memory panel disabled: {exc}", flush=True)
        return None


async def run() -> None:
    mic_name = report_microphone()
    bus = EventBus()
    mic = MicState()
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            input_device_index=AUDIO_INPUT_DEVICE_INDEX,
            output_device_index=AUDIO_OUTPUT_DEVICE_INDEX,
        )
    )

    stt = WhisperSTTService(
        model=WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
    )
    tts = KokoroTTSService(voice_id=KOKORO_VOICE)
    llm = build_llm()

    # Cross-session memory (remember/recall) and any configured MCP servers.
    mcp_schemas, mcp_clients = await register_mcp_tools(llm)  # keep clients alive for the session
    vision_schemas = register_vision_tools(llm, ECHO_BASE_URL, ECHO_API_KEY)
    people = _people_store()
    if people is not None and vision_schemas:
        set_face_hook(_face_hook(people))
    # Built-in tool groups (switchable on the Skills & Tools page). MCP servers from
    # .env (MCP_SERVERS) still work and are listed as their own group.
    builtin = {
        "Clock": register_time_tools(llm),
        "Memory": register_memory_tools(llm),
        "Eyes": vision_schemas,
        "People": register_people_tools(llm, people),
        "MCP (.env)": mcp_schemas,
    }
    tools = ToolsSchema(standard_tools=[s for group in builtin.values() for s in group])

    base_prompt = system_prompt(people_index(people))
    context = LLMContext(
        messages=[{"role": "system", "content": base_prompt}],
        tools=tools,
    )
    # Skills & Tools: MCP servers added on the dashboard, switches, SKILL.md skills.
    toolbox = None
    if os.getenv("TOOLBOX_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            toolbox = ToolboxRuntime(llm, context, ToolboxStore(), builtin, base_prompt=base_prompt)
            await toolbox.start()
        except Exception as exc:  # tools are optional; voice keeps working
            print(f"[JARVIS] Toolbox disabled: {exc}", flush=True)
            toolbox = None
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
            # Ignore the mic while a tool runs, so "hello? what do you see?" during
            # a slow look can't cancel it (Pipecat cancels in-flight calls).
            user_mute_strategies=[FunctionCallUserMuteStrategy()],
            # Speech alone never cuts JARVIS off: his own voice bleeds from the
            # speakers into the mic. Interrupting is explicit - the dashboard's
            # Stop button / Esc, or a spoken "stop" (SpeechGuard) - and the guard
            # drops everything else heard while he talks (echo).
            user_turn_strategies=UserTurnStrategies(
                start=[
                    EchoSafeVADUserTurnStartStrategy(enable_interruptions=False),
                    TranscriptionUserTurnStartStrategy(enable_interruptions=False),
                ]
            ),
        ),
    )

    wake_gate = WakeWordProcessor(gate_from_env())
    stop_switch = InterruptSwitch(on_interrupt=lambda reason: bus.publish("interrupted", reason=reason))
    speech_guard = SpeechGuard(stop_switch)

    pipeline = Pipeline(
        [
            transport.input(),
            stop_switch,             # Stop button / Esc / spoken "stop" interrupt from here
            MicTap(bus, mic),        # dashboard: mic level meter + mute
            stt,
            speech_guard,            # while JARVIS talks: drop echo, act on "stop"
            HeardTap(bus),           # dashboard: everything Whisper heard
            wake_gate,               # drop everything until "hey jarvis"
            UserTap(bus),            # dashboard: requests that got through
            aggregators.user(),
            llm,
            ToolTap(bus),            # dashboard: tool calls
            tts,
            BotAudioTap(bus),        # dashboard: speech level for the orb
            transport.output(),
            BotTap(bus),             # dashboard: speaking state + reply text
            aggregators.assistant(),
        ]
    )

    # The desktop build is an always-listening, wake-word assistant: it must not
    # shut itself down after Pipecat's default 300s of no bot activity.
    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True, enable_metrics=False),
        idle_timeout_secs=None,
    )

    # The dashboard window (http://127.0.0.1:8090). Optional: voice works without it.
    if os.getenv("DASHBOARD_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}:
        await start_dashboard(
            bus,
            task,
            mic,
            model=ECHO_MODEL if ECHO_BASE_URL else ANTHROPIC_MODEL,
            mic_name=mic_name,
            echo_base_url=ECHO_BASE_URL,
            vision_model=(os.getenv("VISION_MODEL") or "vision-dev") if vision_schemas else None,
            memory=_dashboard_memory(),
            stop_switch=stop_switch,
            people=people,
            toolbox=toolbox,
        )

    # Greet on startup.
    await task.queue_frames([TTSSpeakFrame(GREETING)])

    runner = PipelineRunner(handle_sigint=True)
    await runner.run(task)


def main() -> None:
    if not ECHO_BASE_URL and not ANTHROPIC_API_KEY:
        raise SystemExit(
            "No brain configured: ECHO_BASE_URL is blank and ANTHROPIC_API_KEY is empty "
            "or still the .env.example placeholder. Set ECHO_BASE_URL (+ ECHO_API_KEY) to "
            "route through ECHO, or a real ANTHROPIC_API_KEY to call Anthropic directly."
        )
    asyncio.run(run())


if __name__ == "__main__":
    main()
