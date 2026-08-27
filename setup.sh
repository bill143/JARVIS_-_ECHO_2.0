#!/usr/bin/env bash
#
#  JARVIS & ECHO 2.0  -  One-step setup & launch (macOS / Linux)
#  ------------------------------------------------------------
#  This script will:
#    1. Check that Python 3 is installed
#    2. Create a virtual environment (.venv)
#    3. Install all required libraries (Pipecat + local Whisper/Kokoro voice stack)
#    4. Ask for your Claude API key (only the first time) and save it to .env
#    5. Launch the assistant (desktop build: local mic + speaker)
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

# ----- 4. Collect the Claude API key (only if .env doesn't exist yet) -----
if [ -f ".env" ]; then
  ok ".env already exists - skipping the key question."
else
  echo ""
  say "Let's set up your Claude API key. Paste it when asked, then press Enter."
  echo "    (Get one from: https://console.anthropic.com -> API Keys)"
  echo ""

  printf "%s " "${BOLD}Anthropic API Key (sk-ant-...):${RESET}" >&2
  read -r ANTHROPIC_API_KEY
  while [ -z "$ANTHROPIC_API_KEY" ]; do
    printf "%s\n" "${YELLOW}!! ${RESET}That can't be empty." >&2
    printf "%s " "${BOLD}Anthropic API Key (sk-ant-...):${RESET}" >&2
    read -r ANTHROPIC_API_KEY
  done

  # Seed the rest of the config from the example file, then drop in the key.
  if [ -f ".env.example" ]; then
    cp .env.example .env
    # Replace the placeholder key line. Escape sed-significant chars in the key
    # (backslash, the '|' delimiter, and '&' which expands to the whole match).
    if command -v sed >/dev/null 2>&1; then
      esc_key=$(printf '%s' "$ANTHROPIC_API_KEY" | sed -e 's/[\\&|]/\\&/g')
      sed -i.bak "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$esc_key|" .env && rm -f .env.bak
    else
      echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" >> .env
    fi
  else
    echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" > .env
  fi

  ok "Saved your key to .env (this file is git-ignored and stays on your machine)."
fi

# ----- 5. Launch -----
echo ""
say "Starting JARVIS & ECHO 2.0 (desktop build)..."
echo ""
echo "${GREEN}${BOLD}  Almost there!${RESET}"
echo "  - Allow microphone access if your OS asks."
echo "  - Say ${BOLD}\"Hey JARVIS\"${RESET} to wake it, then talk."
echo "  - Ask ${BOLD}\"what can you see?\"${RESET} to trigger the webcam."
echo ""
echo "  Prefer the browser (WebRTC) build instead?  Run:  ${CYAN}$VENV_PY assistant_web.py${RESET}"
echo "  Press ${BOLD}Ctrl+C${RESET} in this window to stop the assistant."
echo ""

exec "$VENV_PY" assistant.py
