# 🤖 JARVIS & ECHO 2.0

A real-time **Voice + Vision AI assistant** you can talk to in your browser. It listens,
thinks, talks back, and can even *see* through your webcam when you ask it to.

Built on the excellent [svpino/livekit-assistant](https://github.com/svpino/livekit-assistant),
repackaged so a **complete beginner can get it running with one command**.

---

## ✨ What it does

- 🎙️ **Hears you** in real time (Deepgram speech-to-text)
- 🧠 **Thinks** with OpenAI **GPT-4o**
- 🗣️ **Talks back** with OpenAI text-to-speech (the `alloy` voice)
- 👀 **Sees** through your webcam — but only when you ask (e.g. *"What am I holding?"*),
  to save bandwidth and money
- 🔁 **Lets you interrupt** it mid-sentence, just like a real conversation

| Job | Service |
|-----|---------|
| Real-time room / audio / video | **LiveKit** |
| Speech → text | **Deepgram** |
| Brain + voice | **OpenAI GPT-4o** |
| Detecting when you're speaking | **Silero VAD** |

---

## ✅ Before you start: get 3 free API keys

You'll need keys from three services. Each has a free tier — keep these tabs open,
the setup script will ask you to paste them.

1. **LiveKit** → https://cloud.livekit.io → *Settings → Keys*
   - You'll copy **three** values: the **URL** (starts with `wss://`), the **API Key**, and the **API Secret**.
2. **Deepgram** → https://console.deepgram.com → create an **API Key**.
3. **OpenAI** → https://platform.openai.com/api-keys → create a **secret key** (starts with `sk-`).

> 💡 You don't need to set any environment variables by hand. The setup script collects
> these keys and saves them to a private `.env` file for you.

---

## 🚀 One-step setup (this is the whole thing)

### Windows

Download/clone this project, then **double-click `setup.bat`**.
(Or, in a terminal opened in this folder, run `setup.bat`.)

### macOS / Linux

Open a terminal in this folder and run:

```bash
bash setup.sh
```

That single command will automatically:

1. ✅ Check you have Python 3
2. 📦 Create a virtual environment and install every library
3. ⬇️ Download the voice-detection model files
4. 🔑 Ask you to paste your API keys (first run only) and save them to `.env`
5. ▶️ Launch the assistant

---

## 💬 Talk to it

Once the script says it's running:

1. Open the **LiveKit hosted playground**: **https://agents-playground.livekit.io/**
2. Connect it to the **same LiveKit project** your keys came from.
3. Allow your **microphone** (and **camera**, for vision) when the browser asks.
4. Start talking! Try:
   - *"Tell me a joke."*
   - *"What do you see right now?"* 👀 (triggers the webcam)
   - *"Am I wearing glasses?"* 👀

To stop the assistant, press **Ctrl + C** in the terminal window.

---

## 🧰 Requirements

- **Python 3.9+** (3.10 or newer recommended) — get it at https://www.python.org/downloads/
  - On Windows, tick **"Add python.exe to PATH"** during install.
- An internet connection
- A microphone (and a webcam if you want the vision features)

---

## ❓ Troubleshooting

| Problem | Fix |
|--------|-----|
| `Python was not found` | Install Python from python.org and re-run the setup script. On Windows, make sure you ticked **Add to PATH**. |
| Re-run setup later | Just run `setup.bat` / `bash setup.sh` again. It reuses the existing setup and skips the questions if `.env` exists. |
| Entered a wrong key | Delete the `.env` file and run the setup script again to re-enter your keys. |
| The assistant won't join | Make sure the playground is connected to the **same** LiveKit project your keys belong to. |

---

## 🔒 A note on safety

Your API keys are stored only in the local `.env` file, which is listed in `.gitignore`
so it is **never** uploaded to GitHub. Never share your `.env` or paste real keys into a
public place.

---

## 🛠️ Want to customize?

Open `assistant.py` and edit the `ASSISTANT_NAME` and `VOICE` values near the top, or tweak
the personality in the system message. (`VOICE` must be one of OpenAI's voices:
`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`.)

---

*Original project by [Santiago Valdarrama (svpino)](https://github.com/svpino/livekit-assistant).
This fork focuses on a one-command, beginner-friendly setup.*
