# 🛰️ ECHO — Telegram Markets Assistant (n8n)

**ECHO** is the trading/markets agent that runs under **JARVIS**. It's a Telegram bot
built in **n8n** that handles **text, voice, and image** messages, remembers your
conversation, and can use Gmail, Google Calendar, Contacts, and web search.

This folder contains `ECHO.json` — an n8n workflow you import into your **hosted
n8n Cloud** account. No Docker, no self-hosting, no tunnels required.

---

## 🧠 What ECHO does

| You send… | ECHO does… |
|-----------|------------|
| **Text** | Answers with its markets persona + tools + memory |
| **Voice note** | Transcribes it (Whisper) → answers → replies **with a voice note** (`nova`) |
| **Photo** (e.g. a chart screenshot) | Describes it with the vision model, then **feeds that into the agent** so ECHO reasons about it with full persona, tools, and memory |

**Tools wired to the agent:** Google Search (SerpAPI), Get/Send Email (Gmail),
Get/Set Calendar (Google Calendar), Contacts (Pinecone vector store).

> **Honesty rule:** ECHO is told it does **not** yet have a live market-data feed or a
> backtesting engine. If you ask it to pull live quotes, backtest, or place a trade, it
> will say those aren't wired in yet instead of inventing numbers.

---

## 🔌 What you need before importing

Create these accounts/keys first (each has the credential you'll connect inside n8n):

1. **Telegram bot** — message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the **bot token**.
2. **OpenAI** — an API key from https://platform.openai.com/api-keys (chat, vision, Whisper, TTS).
3. **Google account** — for Gmail + Google Calendar (OAuth, connected inside n8n).
4. **SerpAPI** — https://serpapi.com (web/Google search).
5. **Pinecone** — https://www.pinecone.io — an index named `n8n` with a `contacts` namespace
   (only needed if you want the Contacts tool; you can delete that node otherwise).

---

## 🚀 Import into n8n Cloud (browser only)

1. Log into your **n8n Cloud** workspace.
2. Top-right **`⋯` → `Import from File`** (or **Workflows → Add workflow → Import from File…**).
3. Select **`ECHO.json`** from this folder. The full graph loads.
4. The workflow imports as **inactive** — that's expected. You'll connect credentials next,
   then activate.

> The JSON contains **no secrets** — only credential *names*. On import you'll see
> "credential not set" markers; that's normal. Connect your own in the next step.

---

## 🔑 Connect your credentials (one-time, in the n8n UI)

Open each node below and pick/create **your own** credential from the dropdown:

| Node(s) | Credential to set |
|---------|-------------------|
| Receive Message, Get Audio File, Download Image, Text Response, Audio Response | **Telegram API** (your bot token) |
| OpenAI Chat Model, Analyze Image, Transcribe, Generate Audio, Embeddings OpenAI | **OpenAI API** |
| Get Emails, Send Email | **Gmail OAuth2** |
| Get Calendar, Set Calendar | **Google Calendar OAuth2** |
| Google Search | **SerpAPI** |
| Contacts | **Pinecone API** |

### Calendar note
Both calendar nodes are set to **`primary`**, which means *the calendar of whatever Google
account you connect*. You don't need to paste a calendar ID. If you want a different
calendar, open Get/Set Calendar and pick it from the list.

---

## 🔐 Lock it down (REQUIRED — do this before activating)

A Telegram bot replies to **anyone** who finds it. Because ECHO can send email from your
Gmail, read your inbox, and write to your calendar, you must restrict it to **yourself**.

This workflow ships **closed by default**: the **`Authorized?`** node (right after
*Receive Message*) drops every message whose sender ID isn't on the allowlist, and the
placeholder allowlist is `0`, so **nobody** gets through until you set your own ID.

**To set your ID:**

1. In Telegram, message [@userinfobot](https://t.me/userinfobot) — it replies with your
   numeric **user ID** (e.g. `123456789`).
2. In n8n, open the **`Authorized?`** node → in the condition, replace the right-hand
   value `0` with your number.
3. Need to allow more than one person? Add another condition with their ID (the node uses
   **OR**), or use the Telegram trigger's built-in *Restrict to chat IDs* field as a second layer.

> The `false` branch of `Authorized?` is intentionally left unconnected, so unauthorized
> messages are silently dropped — the bot doesn't even reply, which avoids confirming it exists.

### Other hardening already built in
- **Untrusted-input handling:** the system prompt marks all message/voice/image/email/search
  content as *untrusted data* and tells ECHO never to obey instructions hidden inside it
  (defense against prompt-injection → tool abuse). Image content is wrapped in
  `<image_caption>` / `<vision_analysis>` tags.
- **Name sanitized:** your Telegram display name is stripped to safe characters and wrapped in
  `<user_display_name>` before it reaches the model, so a malicious display name can't inject.
- **Email/calendar confirmation:** ECHO is instructed to confirm the recipient and details
  with you in chat before using Send Email or Set Calendar.

> ⚠️ The email/calendar confirmation is a *soft* control (a prompt instruction), not a hard
> gate. If you want a hard guarantee, see "Optional: stronger Send Email controls" below.

### Optional: stronger Send Email controls
For a real security boundary (not just a prompt), add **before** the Send Email node either:
- a **Code/IF node** that rejects any `recipient_email` whose domain isn't on an allowlist, or
- a **Telegram inline-button approval** step so you tap "Send" before any email goes out.

Ask if you'd like this wired in — it's a small follow-up.

## ▶️ Activate & test

1. Click **Active** (top-right toggle) to switch the workflow on. This registers the
   Telegram webhook automatically (n8n Cloud gives you a public URL — no tunnel needed).
2. Open Telegram, find your bot, and send:
   - `Hello ECHO` → text reply
   - 🎤 a **voice note** → voice reply
   - 📊 a **chart screenshot** with a caption like *"what's this setup?"* → ECHO reasons about it

If a node errors, open the latest execution (left sidebar → **Executions**) to see which
node and why — almost always a credential that hasn't been connected yet.

---

## 🛠️ Customize

- **Persona / rules:** edit the **AI Agent → System Message**.
- **Voice:** change `nova` in the **Generate Audio** node (OpenAI voices: `alloy`, `echo`,
  `fable`, `onyx`, `nova`, `shimmer`).
- **Memory length:** **Window Buffer Memory → Context Window Length** (default 20 turns).
- **Don't need Contacts/Pinecone?** Delete the **Contacts** and **Embeddings OpenAI** nodes.

---

## 🔧 What was fixed vs. the original tutorial workflow

- **Calendar de-hardcoded:** the tutorial author's calendar (`leonvanzyldev@gmail.com`) was
  baked into both calendar nodes → now `primary` (your connected account).
- **Image lane now reaches the agent:** photos used to be described and sent straight back,
  bypassing ECHO's persona, tools, and memory. Now the vision description is fed into the
  AI Agent, so chart screenshots get a real ECHO answer (and a voice reply if you asked by voice).
- **Photo size index hardened:** `message.photo[2]` (crashes on small images with fewer sizes)
  → `message.photo[message.photo.length - 1]` (always the largest available size).
- **Name expression hardened:** the greeting now reads `first_name` from **Receive Message**
  instead of the Switch node, so it resolves reliably across all three input lanes.

**Security hardening added on top:**
- **Sender allowlist (`Authorized?` node):** the bot was open to anyone; it's now closed by
  default and only responds to allowlisted Telegram IDs (see "Lock it down" above).
- **Prompt-injection defenses:** untrusted-data system rules, delimiter-wrapped image content,
  sanitized display name, and confirm-before-send guidance for email/calendar.

---

*Part of the **JARVIS & ECHO 2.0** project. ECHO is the markets agent; the LiveKit
voice/vision assistant in the repo root is the real-time companion.*
