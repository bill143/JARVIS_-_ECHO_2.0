"""
JARVIS · Alloy — a real-time voice + vision assistant.

Built on GetStream's Vision Agents framework:
    you (browser webcam + mic)  ->  Stream edge  ->  Deepgram (speech->text)
        ->  Claude (the brain + the eyes)  ->  ElevenLabs (text->voice)  ->  back to you

Run it with:   uv run agent.py run
(That opens a demo page in your browser — allow camera + microphone and start talking.)
"""

import logging

from dotenv import load_dotenv
from vision_agents.core import Agent, AgentLauncher, Runner, User
from vision_agents.plugins import anthropic, deepgram, elevenlabs, getstream

logging.basicConfig(level=logging.INFO)
load_dotenv()  # read API keys from the .env file the setup script created

# ---------------------------------------------------------------------------
# Personality — edit this freely.
# ---------------------------------------------------------------------------
INSTRUCTIONS = (
    "Your name is Alloy, a witty, friendly assistant working under JARVIS. "
    "You can SEE the user through their camera and HEAR them through their microphone. "
    "Keep your replies short and conversational, like a real phone call. "
    "Do not use markdown, emojis, or special characters — your words are spoken aloud. "
    "When the user shows you something or asks what you can see, describe it plainly."
)

# Claude is both the language model AND the vision model.
# Want it cheaper / faster? change this to "claude-sonnet-4-6".
LLM_MODEL = "claude-opus-4-8"


async def create_agent(**kwargs) -> Agent:
    """Wire the assistant together from swappable building blocks."""
    return Agent(
        edge=getstream.Edge(),  # Stream's low-latency audio/video transport
        agent_user=User(name="Alloy", id="agent"),
        instructions=INSTRUCTIONS,
        processors=[],  # add vision processors here (e.g. YOLO, Moondream) — see README
        llm=anthropic.LLM(LLM_MODEL),  # Claude — brain + vision
        stt=deepgram.STT(eager_turn_detection=True),  # speech -> text, with built-in turn-taking
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
