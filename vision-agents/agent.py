"""
JARVIS · Alloy — a real-time voice + vision assistant.

  you (browser webcam + mic) ─▶ Stream edge ─▶ Deepgram (speech→text)
        ─▶ Claude  (the brain)  ──▶ ElevenLabs (text→voice) ─▶ back to you
                    │
                    └─ calls the `look` tool ─▶ Moondream (the eyes) ─▶ describes the webcam

Claude does the reasoning, persona, and conversation. Whenever it needs to SEE,
it calls the `look` tool, which runs Moondream's vision model on the latest
webcam frame and returns a description for Claude to reason about.

Run it with:   uv run agent.py run
(That opens a demo page in your browser — allow camera + microphone and start talking.)
"""

import asyncio
import logging
import os
from typing import Optional

import av
import moondream as md
from dotenv import load_dotenv
from PIL import Image

from vision_agents.core import Agent, AgentLauncher, Runner, User
from vision_agents.core.processors.base_processor import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder
from vision_agents.plugins import anthropic, deepgram, elevenlabs, getstream

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alloy")
load_dotenv()  # read API keys from the .env file the setup script created

# ---------------------------------------------------------------------------
# Personality — edit this freely. Note the explicit instruction to use `look`:
# Claude only "sees" when it calls that tool, so we tell it when to.
# ---------------------------------------------------------------------------
INSTRUCTIONS = (
    "Your name is Alloy, a witty, friendly assistant working under JARVIS. "
    "You HEAR the user through their microphone, and you can SEE through their camera "
    "by calling the `look` tool. "
    "Whenever the user asks what you can see, asks about something they are showing you, "
    "or the answer depends on the camera, CALL the `look` tool with a specific question, "
    "then answer naturally using what it returns. "
    "Keep replies short and conversational, like a phone call. "
    "Do not use markdown, emojis, or special characters — your words are spoken aloud."
)

# Claude is the brain. Want it cheaper / faster? change to "claude-sonnet-4-6".
LLM_MODEL = "claude-opus-4-8"

# How often to grab a webcam frame to keep "latest" fresh (1/sec is plenty for Q&A).
VISION_FPS = 1


class WebcamEyes(VideoProcessor):
    """A tiny processor that just remembers the most recent webcam frame.

    The `look` tool reads `latest_image` and asks Moondream about it. We keep
    only the latest frame (not a stream) — that's all on-demand Q&A needs.
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


def build_brain(eyes: WebcamEyes) -> anthropic.LLM:
    """Claude as the LLM, with a `look` tool wired to Moondream's vision model."""
    llm = anthropic.LLM(LLM_MODEL)
    moondream_client = md.vl(api_key=os.getenv("MOONDREAM_API_KEY"))

    @llm.register_function(
        name="look",
        description=(
            "Look through the user's camera right now. Pass a specific question about "
            "what to look for (e.g. 'what is the person holding?'). Returns a short "
            "description of what is currently visible."
        ),
    )
    async def look(question: str) -> str:
        image = eyes.latest_image
        if image is None:
            return "I can't see anything yet — the camera may still be starting up."
        loop = asyncio.get_event_loop()
        # Moondream's SDK is synchronous — run it off the event loop.
        return await loop.run_in_executor(
            None, lambda: moondream_client.query(image, question)["answer"]
        )

    return llm


async def create_agent(**kwargs) -> Agent:
    """Wire the assistant together from swappable building blocks."""
    eyes = WebcamEyes()
    return Agent(
        edge=getstream.Edge(),  # Stream's low-latency audio/video transport
        agent_user=User(name="Alloy", id="agent"),
        instructions=INSTRUCTIONS,
        processors=[eyes],  # keeps the latest webcam frame for the `look` tool
        llm=build_brain(eyes),  # Claude + the Moondream-backed `look` tool
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
