"""
JARVIS · Alloy — a real-time voice + vision assistant.

  you (browser webcam + mic) ─▶ Stream edge ─▶ Deepgram (speech→text)
        ─▶ Claude  (the brain)  ──▶ ElevenLabs (text→voice) ─▶ back to you
                    │
                    └─ calls tools when needed:
                         look / read_text / find_object  →  Moondream (the eyes)
                         get_weather · get_current_time · remember · recall · search_web

Claude does the reasoning, persona, and conversation, and calls a tool whenever it
needs to see, look something up, or remember a note.

Run it with:   uv run agent.py run
(That opens a demo page in your browser — allow camera + microphone and start talking.)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import av
import moondream as md
from dotenv import load_dotenv
from PIL import Image

from vision_agents.core import Agent, AgentLauncher, Runner, User
from vision_agents.core.processors.base_processor import VideoProcessor
from vision_agents.core.utils.examples import get_weather_by_location
from vision_agents.core.utils.video_forwarder import VideoForwarder
from vision_agents.plugins import anthropic, deepgram, elevenlabs, getstream

try:  # optional — only needed for the search_web tool
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alloy")
load_dotenv()  # read API keys from the .env file the setup script created

# ---------------------------------------------------------------------------
# Personality + the honesty rule. Claude only uses an ability when it CALLS the
# matching tool, so we tell it plainly what it can do and to admit what it can't.
# ---------------------------------------------------------------------------
INSTRUCTIONS = (
    "Your name is Alloy, a witty, friendly assistant working under JARVIS. "
    "You HEAR the user through their microphone and speak back. "
    "You have these tools — call the right one instead of guessing:\n"
    "- look(question): see through the user's camera.\n"
    "- read_text(): read any text the user is showing the camera.\n"
    "- find_object(object_name): check whether something is visible on camera.\n"
    "- get_weather(location): current weather.\n"
    "- get_current_time(): today's date and the current time.\n"
    "- remember(note) / recall(): jot down and look up notes during the chat.\n"
    "- search_web(query): look up current facts, news, or things you don't know.\n"
    "Whenever the question is visual, call look/read_text/find_object. "
    "Whenever it needs fresh or factual info you're unsure of, call search_web. "
    "Honesty rule: if you don't have a tool for what's asked (sending email, booking, "
    "controlling devices), say so plainly. Never invent facts, numbers, prices, or results. "
    "Keep replies short and conversational, like a phone call. "
    "Do not use markdown, emojis, or special characters — your words are spoken aloud."
)

# Claude is the brain. Want it cheaper / faster? change to "claude-sonnet-4-6".
LLM_MODEL = "claude-opus-4-8"

# How often to grab a webcam frame to keep "latest" fresh (1/sec is plenty for Q&A).
VISION_FPS = 1

# Where remember()/recall() store notes (git-ignored).
NOTES_FILE = Path(__file__).with_name("notes.json")


class WebcamEyes(VideoProcessor):
    """A tiny processor that just remembers the most recent webcam frame.

    The vision tools (look / read_text / find_object) read `latest_image` and ask
    Moondream about it. We keep only the latest frame — that's all on-demand Q&A needs.
    """

    def __init__(self, fps: int = VISION_FPS):
        super().__init__()
        self.fps = fps
        self._latest: Optional[Image.Image] = None
        self._forwarder: Optional[VideoForwarder] = None

    def name(self) -> str:
        return "webcam_eyes"

    async def process_video(
        self,
        incoming_track,
        participant_id: Optional[str] = None,
        shared_forwarder: Optional[VideoForwarder] = None,
    ):
        # The Agent calls this when the user's camera track arrives.
        if shared_forwarder is not None:
            self._forwarder = shared_forwarder
            self._forwarder.add_frame_handler(
                self._on_frame, fps=float(self.fps), name="webcam_eyes"
            )
        else:
            self._forwarder = VideoForwarder(
                incoming_track,  # type: ignore[arg-type]
                max_buffer=30,
                fps=self.fps,
                name="webcam_eyes_forwarder",
            )
            self._forwarder.add_frame_handler(self._on_frame)
        logger.info("👁️  WebcamEyes is now watching the camera")

    async def _on_frame(self, frame: av.VideoFrame):
        try:
            self._latest = Image.fromarray(frame.to_ndarray(format="rgb24"))
        except Exception:
            logger.exception("Could not read a webcam frame")

    async def stop_processing(self) -> None:
        self._forwarder = None
        self._latest = None

    @property
    def latest_image(self) -> Optional[Image.Image]:
        return self._latest


def _load_notes() -> list[str]:
    try:
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_notes(notes: list[str]) -> None:
    NOTES_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")


def build_brain(eyes: WebcamEyes) -> anthropic.LLM:
    """Claude as the LLM, with tools wired in. Claude decides when to call each."""
    llm = anthropic.LLM(LLM_MODEL)
    moondream_client = md.vl(api_key=os.getenv("MOONDREAM_API_KEY"))
    tavily = (
        TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        if TavilyClient and os.getenv("TAVILY_API_KEY")
        else None
    )

    async def _ask_moondream(question: str) -> str:
        image = eyes.latest_image
        if image is None:
            return "I can't see anything yet — the camera may still be starting up."
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: moondream_client.query(image, question)["answer"]
        )

    # ----- Vision tools (Moondream) -----
    @llm.register_function(
        name="look",
        description=(
            "Look through the user's camera right now. Pass a specific question about "
            "what to look for. Returns a short description of what is currently visible."
        ),
    )
    async def look(question: str) -> str:
        return await _ask_moondream(question)

    @llm.register_function(
        name="read_text",
        description="Read and transcribe any text the user is showing to the camera (a label, sign, page, screen).",
    )
    async def read_text() -> str:
        return await _ask_moondream(
            "Transcribe any text visible in this image, exactly. If there is no text, say 'no text visible'."
        )

    @llm.register_function(
        name="find_object",
        description="Check whether a specific object is currently visible on the user's camera.",
    )
    async def find_object(object_name: str) -> str:
        image = eyes.latest_image
        if image is None:
            return "I can't see anything yet — the camera may still be starting up."
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: moondream_client.detect(image, object_name)
        )
        count = len(result.get("objects", [])) if isinstance(result, dict) else 0
        if count == 0:
            return f"I don't see any {object_name} on camera right now."
        return f"Yes — I can see {count} {object_name} on camera."

    # ----- Instant tools -----
    @llm.register_function(
        name="get_weather",
        description="Get the current weather for a city or location.",
    )
    async def get_weather(location: str) -> dict:
        return await get_weather_by_location(location)

    @llm.register_function(
        name="get_current_time",
        description="Get today's date and the current local time.",
    )
    async def get_current_time() -> str:
        return datetime.now().astimezone().strftime("%A, %B %d, %Y at %I:%M %p %Z")

    @llm.register_function(
        name="remember",
        description="Save a short note so you can recall it later in this conversation.",
    )
    async def remember(note: str) -> str:
        notes = _load_notes()
        notes.append(note)
        _save_notes(notes)
        return f"Got it, I'll remember that. ({len(notes)} note(s) saved.)"

    @llm.register_function(
        name="recall",
        description="List the notes you've been asked to remember.",
    )
    async def recall() -> str:
        notes = _load_notes()
        if not notes:
            return "I don't have any notes saved yet."
        return "Here's what I remember: " + "; ".join(notes)

    # ----- Web search (optional — needs TAVILY_API_KEY) -----
    @llm.register_function(
        name="search_web",
        description="Search the web for current information, news, or facts you are unsure about.",
    )
    async def search_web(query: str) -> str:
        if tavily is None:
            return "Web search isn't set up — there's no Tavily API key configured."
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            lambda: tavily.search(query, max_results=5, include_answer=True),
        )
        answer = res.get("answer") if isinstance(res, dict) else None
        items = (res.get("results") or [])[:3] if isinstance(res, dict) else []
        snippets = [
            f"- {it.get('title', '')}: {(it.get('content', '') or '')[:200]}" for it in items
        ]
        out = (answer + "\n\n" if answer else "") + "\n".join(snippets)
        return out.strip() or "I couldn't find anything useful for that."

    return llm


async def create_agent(**kwargs) -> Agent:
    """Wire the assistant together from swappable building blocks."""
    eyes = WebcamEyes()
    return Agent(
        edge=getstream.Edge(),  # Stream's low-latency audio/video transport
        agent_user=User(name="Alloy", id="agent"),
        instructions=INSTRUCTIONS,
        processors=[eyes],  # keeps the latest webcam frame for the vision tools
        llm=build_brain(eyes),  # Claude + all the tools
        stt=deepgram.STT(eager_turn_detection=True),  # speech -> text (+ turn taking)
        tts=elevenlabs.TTS(model_id="eleven_flash_v2_5"),  # text -> natural voice
    )


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs) -> None:
    """Create a call, join it, greet the user, then run until the call ends."""
    call = await agent.create_call(call_type, call_id)
    async with agent.join(call):
        await agent.simple_response("Hey, I'm Alloy. I can see and hear you now. What's up?")
        await agent.finish()  # keep running until you leave the call


if __name__ == "__main__":
    Runner(AgentLauncher(create_agent=create_agent, join_call=join_call)).cli()
