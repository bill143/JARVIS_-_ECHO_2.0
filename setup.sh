#!/usr/bin/env bash
#
#  JARVIS & ECHO 2.0  -  One-step setup & launch (macOS / Linux)
#  ------------------------------------------------------------
#  This script will:
#    1. Check that Python 3 is installed
#    2. Create a virtual environment (.venv)
#    3. Install all required libraries
#    4. Download the voice-detection model files
#    5. Ask for your API keys (only the first time) and save them to .env
#    6. Launch the assistant
#
#  Just run:  bash setup.sh
#
set -e

# ----- pretty colors (fall back to plain text if unsupported) -----
if [ -t 1 ]; then
  BOLD="$(printf '\033[1m')"; GREEN="$(printf '\033[32m')"
  YELLOW="$(printf '\033[33m')"; CYAN="$(printf '\033[36m')"; RESET="$(printf '\033[0m')"
else
  BOLD=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi

say()  { printf "%s\n" "${CYAN}==>${RESET} ${BOLD}$*${RESET}"; }
ok()   { printf "%s\n" "${GREEN}OK ${RESET} $*"; }
warn() { printf "%s\n" "${YELLOW}!! ${RESET} $*"; }

# Always run from the folder this script lives in.
cd "$(dirname "$0")"

echo ""
echo "${BOLD}===========================================${RESET}"
echo "${BOLD}   JARVIS & ECHO 2.0  -  Setup & Launch${RESET}"
echo "${BOLD}===========================================${RESET}"
echo ""

# ----- 1. Find Python 3 -----
say "Checking for Python 3..."
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1 && python -c 'import sys; exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null; then
  PY=python
else
  warn "Python 3 was not found."
  echo "    Please install it from https://www.python.org/downloads/ and run this script again."
  exit 1
fi
ok "Found $($PY --version 2>&1)"

# ----- 2. Create the virtual environment -----
if [ ! -d ".venv" ]; then
  say "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv
  ok "Virtual environment created."
else
  ok "Virtual environment already exists."
fi

# Use the venv's python/pip directly (no need to 'activate').
VENV_PY=".venv/bin/python"

# ----- 3. Install the libraries -----
say "Upgrading pip and installing libraries (this can take a few minutes)..."
"$VENV_PY" -m pip install -U pip >/dev/null
"$VENV_PY" -m pip install -r requirements.txt
ok "Libraries installed."

# ----- 4. Download the voice-detection model files -----
say "Downloading model files (Silero VAD / turn detector)..."
"$VENV_PY" assistant.py download-files
ok "Model files ready."

# ----- 5. Collect API keys (only if .env doesn't exist yet) -----
if [ -f ".env" ]; then
  ok ".env already exists - skipping the key questions."
else
  echo ""
  say "Let's set up your API keys. Paste each one when asked, then press Enter."
  echo "    (Get them from: livekit.cloud, console.deepgram.com, platform.openai.com)"
  echo ""

  ask() {  # usage: VALUE=$(ask "Prompt text")
    # Prompts go to stderr so they're visible but NOT captured by $(...).
    # Only the typed value is written to stdout (and thus captured).
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

  LIVEKIT_URL=$(ask "LiveKit URL (wss://...):")
  LIVEKIT_API_KEY=$(ask "LiveKit API Key:")
  LIVEKIT_API_SECRET=$(ask "LiveKit API Secret:")
  DEEPGRAM_API_KEY=$(ask "Deepgram API Key:")
  OPENAI_API_KEY=$(ask "OpenAI API Key:")

  {
    echo "LIVEKIT_URL=$LIVEKIT_URL"
    echo "LIVEKIT_API_KEY=$LIVEKIT_API_KEY"
    echo "LIVEKIT_API_SECRET=$LIVEKIT_API_SECRET"
    echo "DEEPGRAM_API_KEY=$DEEPGRAM_API_KEY"
    echo "OPENAI_API_KEY=$OPENAI_API_KEY"
  } > .env

  ok "Saved your keys to .env (this file is git-ignored and stays on your machine)."
fi

# ----- 6. Launch -----
echo ""
say "Starting JARVIS & ECHO 2.0..."
echo ""
echo "${GREEN}${BOLD}  Almost there!${RESET}"
echo "  1. Open the playground:  ${CYAN}https://agents-playground.livekit.io/${RESET}"
echo "  2. Connect it to the SAME LiveKit project as your keys."
echo "  3. Allow your microphone (and camera, for vision) and start talking."
echo ""
echo "  Press ${BOLD}Ctrl+C${RESET} in this window to stop the assistant."
echo ""

exec "$VENV_PY" assistant.py start
