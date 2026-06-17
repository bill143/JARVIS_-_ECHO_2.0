# 🤖 JARVIS & ECHO 2.0 — Pipecat + Claude (fully-local voice)

A real-time **Voice + Vision AI assistant** you can talk to. It listens, thinks,
talks back, and can *see* through your webcam when you ask it to.

This version runs **off LiveKit Agents onto [Pipecat](https://pipecat.ai)**, with
an **open-source / self-hosted** voice stack. STT, TTS, VAD, and the webcam all
run locally; the thinking is routed through **ECHO**.

## Two components, one system

This is a monorepo with two parts:

- **JARVIS** (this top level) — the voice front-end: mic → STT → LLM → TTS → speaker.
- **[ECHO](./echo)** — a multi-provider LLM proxy (the brain/router): one
  OpenAI-compatible endpoint with 6 tiers, 16 model aliases, fallback chains,
  Langfuse observability, and cost/token/latency logging. Built on LiteLLM.

JARVIS routes its thinking **through ECHO** when `ECHO_BASE_URL` is set (recommended),
and falls back to calling Anthropic directly when it isn't. See [`echo/README.md`](./echo/README.md)
to run the proxy.

---

## What changed

| Layer        | Before (LiveKit)       | After (Pipecat)                     |
|--------------|------------------------|-------------------------------------|
| Orchestrator | LiveKit Agents         | **Pipecat pipeline**                |
| Brain (LLM)  | OpenAI GPT-4o          | **Claude** (Sonnet 4.6 / Haiku 4.5) |
| STT          | Deepgram (cloud)       | **Whisper** (local, no key)         |
| TTS          | OpenAI `alloy` (cloud) | **Kokoro** (local ONNX, no key)     |
| VAD          | Silero                 | Silero (unchanged)                  |
| Vision       | webcam → GPT-4o        | webcam → **Claude vision** tool     |
| Transport    | browser / LiveKit      | local microphone + speaker / WebRTC |

```
mic --> Whisper (STT) --> "Hey JARVIS" gate --> Claude --> Kokoro (TTS) --> speaker
                                                  |
                                            webcam (vision tool)
```

---

## Files

- `assistant.py` — desktop build: local microphone + speaker
- `assistant_web.py` — **browser build: WebRTC mic + webcam** (closest to the old LiveKit setup)
- `vision.py` — user-triggered webcam capture (OpenCV for desktop, WebRTC video track for browser)
- `wakeword.py` — **"Hey JARVIS" wake-phrase gate** (fully local, no extra models)
- `Dockerfile` / `docker-compose.yml` — self-contained container (web build)
- `requirements.txt` — Pipecat 1.3 + the local voice stack
- `.env.example` — copy to `.env` and add your `ANTHROPIC_API_KEY`

Both builds speak a greeting first — `assistant.py` on startup, `assistant_web.py`
when the browser connects.

---

## ✅ Before you start: one key

You only need **one** key now (the brain). The voice stack is fully local.

1. **Claude** → https://console.anthropic.com → *API Keys* → create a key (starts with `sk-ant-`).

> 💡 The setup script saves it to a private `.env` file (git-ignored) for you.

---

## 🚀 One-step setup

### Windows
Double-click **`setup.bat`** (or run it from a terminal in this folder).

### macOS / Linux
```bash
bash setup.sh
```

That single command will: check Python 3 → create a venv → install everything →
ask for your Claude key (first run only) → launch the desktop assistant.

### Manual install
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then paste your ANTHROPIC_API_KEY
python assistant.py
```

First run downloads the Whisper + Kokoro model files (cached afterwards). Say
*"Hey JARVIS, what can you see?"* to trigger the webcam.

### Browser build (WebRTC — like the old LiveKit UI)
```bash
python assistant_web.py
# then open the printed URL (default http://localhost:7860)
```
The dev runner serves a ready-made web client and handles all WebRTC signalling.
JARVIS greets you as soon as the browser connects, and the webcam streams over the
WebRTC video track (no server-side camera access needed).

---

## 🗣️ Wake word ("Hey JARVIS")

By default JARVIS ignores everything until it hears **"hey jarvis"** (or just
"jarvis"), then stays awake for ~15s so you can keep talking. It's a *text* gate on
the Whisper transcript — fully local, no key, no extra model.

- Configure phrases in `.env`: `WAKE_PHRASES=hey jarvis,jarvis`
- Disable (always-on): set `WAKE_PHRASES=` (empty)
- Tune the awake window (`WAKE_WINDOW_SECONDS`) or swap in openWakeWord / Porcupine
  later — see `wakeword.py`.

---

## 🐳 Docker (self-contained)

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY
docker compose up --build   # serves the browser build on http://localhost:7860
```

The image bundles Whisper + Kokoro; the compose file mounts a `jarvis-models`
volume so the model files download once and persist. Only the Claude API call
leaves the container. (Docker runs the **web** build — the desktop build needs
host mic/speaker passthrough, which is platform-specific.)

---

## ⚙️ Configuration (`.env`)

| Variable              | Default                 | What it does                                   |
|-----------------------|-------------------------|------------------------------------------------|
| `ANTHROPIC_API_KEY`   | *(required)*            | Your Claude key                                |
| `ANTHROPIC_MODEL`     | `claude-sonnet-4-6`     | Brain model (`claude-haiku-4-5-20251001` = faster) |
| `WAKE_PHRASES`        | `hey jarvis,jarvis`     | Wake phrases (empty = always-on)               |
| `WAKE_WINDOW_SECONDS` | `15`                    | How long it stays awake after you speak        |
| `WHISPER_MODEL`       | `base`                  | STT model size (`tiny`…`large-v3`)             |
| `KOKORO_VOICE`        | `af_heart`              | TTS voice id                                   |
| `ASSISTANT_NAME`      | `JARVIS`                | Name in the system prompt                      |
| `CAMERA_INDEX`        | `0`                     | Desktop webcam index                           |

---

## 🧪 Tests & version notes

These files were written against **Pipecat 1.3.0** — the import paths, the
`LLMContext` / `LLMContextAggregatorPair` API, the service constructors
(`AnthropicLLMService`, `WhisperSTTService`, `KokoroTTSService`), and the
`UserImageRequestFrame(append_to_context=True)` fields all target that version.
The 1.x API differs significantly from 0.x, so `requirements.txt` pins `~=1.3`; if
you bump it, re-check the service imports.

- `python test_wakeword.py` — wake-word gate logic, **no heavy deps, no key**.
- `python test_imports.py` — full import graph + constructs the context, aggregator,
  tool schema, and both vision handlers (needs the extras installed, no key).

**Still needs a live run to confirm** (requires your `ANTHROPIC_API_KEY` + a mic,
which can't be exercised in a headless check):
- The full audio round-trip: mic → Whisper → Claude → Kokoro → speaker.
- The vision turn — that an injected webcam frame gets described. The desktop path
  adds the image to context directly; the WebRTC path requests it via
  `UserImageRequestFrame(append_to_context=True)`. If Claude's strict tool-result
  ordering ever complains, inject the image *after* the tool result.

### Continuous integration
`.github/workflows/ci.yml` runs on every push / PR with two jobs:
- **quick** — `py_compile` all modules + `test_wakeword.py` (no heavy deps, seconds).
- **imports** — installs system libs + `requirements.txt`, then `test_imports.py`.

---

## Desktop vs. browser — which file?

- `assistant.py` → runs on a local mic/speaker (a desktop JARVIS appliance).
- `assistant_web.py` → runs in the browser over WebRTC, matching the original
  LiveKit UX. Same brain, same voice stack, same `vision.py` — only the transport
  and the greeting trigger differ.

---

## 🔒 Safety

Your Claude key lives only in the local `.env` file, which is git-ignored so it's
**never** uploaded. Everything except the Claude API call runs on your machine.

---

*Originally based on [svpino/livekit-assistant](https://github.com/svpino/livekit-assistant);
re-platformed onto Pipecat + Claude with a fully-local voice stack.*
