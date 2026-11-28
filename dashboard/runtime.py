"""Glue between the running Pipecat pipeline and the dashboard server.

``JarvisController`` turns dashboard actions into pipeline frames, so typed
text and the Look buttons take exactly the same path as speech after the wake
gate: the user aggregator appends the message, the brain answers (calling
tools as needed) and Kokoro speaks the reply.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Literal

import uvicorn
from pipecat.frames.frames import LLMMessagesAppendFrame, LLMUpdateSettingsFrame
from pipecat.services.settings import LLMSettings

from dashboard.bus import EventBus
from dashboard.health import HealthMonitor, load_fallbacks
from dashboard.server import create_app
from dashboard.taps import MicState
from dashboard.window import open_app_window
from vision_tools import add_seen_listener, set_face_hook

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8090
SELECTABLE_MODELS = ("brain", "local-dev", "groq-dev")
ECHO_CONFIG = Path(__file__).resolve().parent.parent / "echo" / "config.yaml"
LOOK_PROMPTS = {
    "camera": "Look through my camera and tell me what you see.",
    "screen": "Look at my screen and tell me what's on it.",
}


class JarvisController:
    def __init__(self, bus: EventBus, task, mic: MicState, model: str, fallbacks: dict[str, list[str]],
                 stop_switch=None):
        self._bus = bus
        self._stop_switch = stop_switch
        self._task = task
        self._mic = mic
        self._model = model
        self._fallbacks = fallbacks

    def models(self) -> list[str]:
        models = list(SELECTABLE_MODELS)
        if self._model not in models:
            models.insert(0, self._model)
        return models

    def model_config(self) -> dict:
        return {"model": self._model, "fallbacks": self._fallbacks.get(self._model, [])}

    async def say(self, text: str, source: str = "typed") -> None:
        self._bus.publish("user", text=text, source=source)
        self._bus.publish("status", state="thinking")
        await self._task.queue_frames(
            [LLMMessagesAppendFrame(messages=[{"role": "user", "content": text}], run_llm=True)]
        )

    async def look(self, source: Literal["camera", "screen"]) -> None:
        await self.say(LOOK_PROMPTS[source], source="button")

    async def stop(self) -> None:
        """Cut JARVIS off mid-reply (LLM stream cancelled, TTS + audio flushed)."""
        if self._stop_switch is None:
            raise RuntimeError("Stop is not wired into this pipeline")
        await self._stop_switch.trigger("button")

    async def set_muted(self, muted: bool) -> None:
        self._mic.muted = muted
        self._bus.publish("muted", muted=muted)

    async def set_model(self, model: str) -> None:
        await self._task.queue_frames([LLMUpdateSettingsFrame(delta=LLMSettings(model=model))])
        self._model = model
        print(f"[JARVIS] Brain switched from the dashboard -> {model}", flush=True)
        self._bus.publish("config", config=self.model_config())


async def start_dashboard(
    bus: EventBus,
    task,
    mic: MicState,
    *,
    model: str,
    mic_name: str,
    echo_base_url: str | None,
    vision_model: str | None,
    memory=None,
    stop_switch=None,
    people=None,
    toolbox=None,
) -> JarvisController | None:
    """Start the dashboard server (+ health checks, + app window). Never raises:
    if the dashboard can't start, JARVIS keeps working voice-only."""
    bus.bind_loop()
    port = int(os.getenv("DASHBOARD_PORT", str(DEFAULT_PORT)))
    fallbacks = load_fallbacks(ECHO_CONFIG)
    controller = JarvisController(bus, task, mic, model, fallbacks, stop_switch)
    bus.publish("config", config={**controller.model_config(), "mic": mic_name, "vision_model": vision_model})

    def on_seen(source: str, description: str, jpeg: bytes | None) -> None:
        if jpeg is None:  # capture failed: show the reason in the panel
            bus.publish("seen", source=source, description=description, image=None, error=True)
            return
        image = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        bus.publish("seen", source=source, description=description, image=image, error=False)

    add_seen_listener(on_seen)

    try:
        app = create_app(bus, controller, memory, people=people, toolbox=toolbox, port=port)
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="websockets")
        )
        serve_task = asyncio.create_task(server.serve())
        for _ in range(100):  # up to ~10 s for the socket to bind
            if server.started or serve_task.done():
                break
            await asyncio.sleep(0.1)
        if not server.started:
            print(f"[JARVIS] Dashboard could not start on 127.0.0.1:{port} (port busy?); voice continues.", flush=True)
            return None
    except Exception as exc:
        print(f"[JARVIS] Dashboard failed to start: {exc}; voice continues.", flush=True)
        return None

    required = {"vision": "qwen2.5vl:7b", "local_brain": "qwen2.5:14b-instruct"} if vision_model else {}
    HealthMonitor(bus, echo_base_url, required_models=required).start()

    url = f"http://127.0.0.1:{port}/"
    print(f"[JARVIS] Dashboard: {url}", flush=True)
    if os.getenv("DASHBOARD_OPEN", "true").strip().lower() in {"1", "true", "yes", "on"}:
        how = open_app_window(url)
        print(f"[JARVIS] Dashboard window opened ({how})", flush=True)
    return controller
