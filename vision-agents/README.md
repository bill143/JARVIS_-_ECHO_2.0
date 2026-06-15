# 👁️🗣️ JARVIS · Alloy — Voice + Vision Assistant (Claude)

A real-time assistant you talk to **in your browser** — it **hears** you, **sees** you through
your webcam, and **talks back**, powered by **Claude**. Built on
[GetStream's Vision Agents](https://github.com/GetStream/Vision-Agents).

```
 you (webcam + mic) ──▶ Stream edge ──▶ Deepgram (speech→text)
                                          │
                                          ▼
                                   Claude  (the brain)
                                          │  └─ calls look() ─▶ Moondream (the eyes) ─▶ sees the webcam
                                          ▼
        back to you ◀── ElevenLabs (text→voice) ◀──┘
```

> **Why this instead of the LiveKit version in the repo root?** It runs on **current libraries**
> and **`uv` installs the right Python for you** (3.13) — so it doesn't matter that your machine
> has Python 3.14.
>
> **How vision works:** Claude is the brain. When you ask about something on camera, Claude calls
> a **`look` tool** that runs **Moondream** (a cloud vision model — no GPU) on the latest webcam
> frame and hands the description back to Claude to answer. Same idea as the original "Alloy":
> grab the latest frame, use it only when vision is actually needed.

---

## ✅ Before you start — get 5 free API keys

Keep these tabs open; the setup script will ask you to paste each one.

| Service | What it does | Where |
|---------|--------------|-------|
| **Stream** | Real-time video/audio (333k free min/mo) | https://getstream.io/try-for-free/ → API Key **and** Secret |
| **Anthropic** | **Claude** — the brain | https://console.anthropic.com (key starts `sk-ant-`) |
| **Deepgram** | Speech-to-text | https://console.deepgram.com |
| **ElevenLabs** | The voice (text-to-speech) | https://elevenlabs.io |
| **Moondream** | **Vision** — Claude's `look` tool (cloud, no GPU) | https://console.moondream.ai |

You do **not** need to install Python yourself — `uv` handles it.

---

## 🚀 One-step setup & run

**Windows:** double-click **`setup.bat`** (or run it in a terminal).
**macOS / Linux:** `bash setup.sh`

The script will: install `uv` → create an isolated **Python 3.13** environment → install the
libraries → ask for your 4 keys (first run only) → **launch Alloy**.

When it starts, a **demo page opens in your browser** — allow your **camera** and **microphone**,
then just start talking. Press **Ctrl + C** in the terminal to stop.

> Prefer to run it by hand? `uv venv --python 3.13 && uv pip install -r requirements.txt && uv run agent.py run`

---

## 💬 Try saying

- "Hey Alloy, tell me a joke."
- "What do you see right now?" 👀
- "Read what's on this label." (hold it up to the camera)

---

## 🛠️ Customize

Open **`agent.py`**:

- **Personality** → edit the `INSTRUCTIONS` text.
- **Model** → `LLM_MODEL = "claude-opus-4-8"`. Swap to `"claude-sonnet-4-6"` for cheaper/faster.
- **Voice** → change the ElevenLabs `model_id`, or swap the whole `tts=` line to another provider
  (`cartesia.TTS()`, `deepgram.TTS()`, …).
- **Speech-to-text** → the `stt=` line (Deepgram here; AssemblyAI, Whisper, etc. are also supported).

### How the eyes are wired 👁️
Vision is **built in** via Claude's `look` tool, not left as an exercise:

- `WebcamEyes` (a small `VideoProcessor` in `agent.py`) keeps the **latest webcam frame**.
- The **`look(question)`** function is registered on Claude. When Claude calls it, it runs
  **Moondream** (cloud VQA) on that frame and returns a description.
- The system prompt tells Claude to call `look` whenever the question is visual.

Tune it by editing `agent.py`:
- `VISION_FPS` — how often the latest frame refreshes (1/sec is plenty for Q&A).
- Want richer/continuous scene tracking instead? Swap the Moondream call for a local model, or add
  a [YOLO/pose processor](https://github.com/GetStream/Vision-Agents/tree/main/examples/02_golf_coach_example)
  (see the [video-processors guide](https://visionagents.ai/guides/video-processors)).

---

## ❓ Troubleshooting

| Problem | Fix |
|---------|-----|
| `uv: command not found` after install | Close the terminal, open a new one, run setup again (PATH refresh). |
| Browser didn't open | The terminal prints a call/demo URL — open it manually. Or run `uv run agent.py run` again. |
| Wrong/expired key | Delete `.env` and run the setup script again to re-enter keys. |
| Want to re-run later | Just run `setup.bat` / `bash setup.sh` again — it reuses the env and skips the questions. |

---

## 🔒 Safety
Your keys live only in the local `.env` (git-ignored — never uploaded). Don't paste real keys into
chat or commit them.

---

*Part of **JARVIS & ECHO 2.0**. This is the real-time voice/vision companion; **ECHO** (in `/echo`)
is the Telegram markets agent. Framework: [Vision Agents](https://visionagents.ai) (MIT).*
