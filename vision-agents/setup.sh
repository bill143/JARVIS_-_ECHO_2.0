#!/usr/bin/env bash
#
#  JARVIS · Alloy — voice + vision assistant  ·  one-step setup (macOS / Linux)
#  ---------------------------------------------------------------------------
#  Installs uv, creates an isolated Python 3.13 environment (uv downloads
#  Python for you — your system Python version doesn't matter), installs the
#  libraries, collects your API keys into .env, and launches the assistant.
#
#  Run:  bash setup.sh
#
set -e

if [ -t 1 ]; then
  BOLD="$(printf '\033[1m')"; GREEN="$(printf '\033[32m')"
  YELLOW="$(printf '\033[33m')"; CYAN="$(printf '\033[36m')"; RESET="$(printf '\033[0m')"
else
  BOLD=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi
say()  { printf "%s\n" "${CYAN}==>${RESET} ${BOLD}$*${RESET}"; }
ok()   { printf "%s\n" "${GREEN}OK ${RESET} $*"; }
warn() { printf "%s\n" "${YELLOW}!! ${RESET} $*"; }

cd "$(dirname "$0")"

echo ""
echo "${BOLD}===============================================${RESET}"
echo "${BOLD}   JARVIS · Alloy  —  Voice + Vision Assistant${RESET}"
echo "${BOLD}===============================================${RESET}"
echo ""

# ----- 1. Ensure uv is installed -----
if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv (a fast Python package & version manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  warn "uv was installed but isn't on your PATH yet."
  echo "    Close this terminal, open a new one, and run 'bash setup.sh' again."
  exit 1
fi
ok "uv $(uv --version 2>&1)"

# ----- 2. Create an isolated Python 3.13 environment -----
say "Creating a Python 3.13 environment (uv fetches Python if you don't have it)..."
uv venv --python 3.13
ok "Environment ready (.venv)."

# ----- 3. Install the libraries -----
say "Installing libraries (the first run can take a few minutes)..."
uv pip install -r requirements.txt
ok "Libraries installed."

# ----- 4. Collect API keys (first run only) -----
if [ -f ".env" ]; then
  ok ".env already exists - skipping the key questions."
else
  echo ""
  say "Paste each API key when asked, then press Enter."
  echo "    (Stream: getstream.io · Anthropic: console.anthropic.com · Deepgram: console.deepgram.com · ElevenLabs: elevenlabs.io · Moondream: console.moondream.ai)"
  echo ""

  ask() {  # usage: VALUE=$(ask "Prompt")  — prompt goes to stderr so it isn't captured
    local prompt="$1" var
    printf "%s " "${BOLD}$prompt${RESET}" >&2
    read -r var
    while [ -z "$var" ]; do
      printf "%s\n" "${YELLOW}!! ${RESET}That can't be empty." >&2
      printf "%s " "${BOLD}$prompt${RESET}" >&2
      read -r var
    done
    printf "%s" "$var"
  }

  STREAM_API_KEY=$(ask "Stream API Key:")
  STREAM_API_SECRET=$(ask "Stream API Secret:")
  ANTHROPIC_API_KEY=$(ask "Anthropic API Key:")
  DEEPGRAM_API_KEY=$(ask "Deepgram API Key:")
  ELEVENLABS_API_KEY=$(ask "ElevenLabs API Key:")
  MOONDREAM_API_KEY=$(ask "Moondream API Key:")

  # Optional — web search. Press Enter to skip.
  printf "%s " "${BOLD}Tavily API Key (web search — press Enter to skip):${RESET}"
  read -r TAVILY_API_KEY

  {
    echo "STREAM_API_KEY=$STREAM_API_KEY"
    echo "STREAM_API_SECRET=$STREAM_API_SECRET"
    echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
    echo "DEEPGRAM_API_KEY=$DEEPGRAM_API_KEY"
    echo "ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY"
    echo "MOONDREAM_API_KEY=$MOONDREAM_API_KEY"
    echo "TAVILY_API_KEY=$TAVILY_API_KEY"
  } > .env
  ok "Saved your keys to .env (git-ignored — stays on your machine)."
fi

# ----- 5. Launch -----
echo ""
say "Launching Alloy..."
echo ""
echo "${GREEN}${BOLD}  A demo page will open in your browser.${RESET}"
echo "  Allow your ${BOLD}camera${RESET} and ${BOLD}microphone${RESET}, then just start talking."
echo "  Press ${BOLD}Ctrl+C${RESET} here to stop."
echo ""

exec uv run agent.py run
