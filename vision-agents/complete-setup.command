#!/usr/bin/env bash
#
#  JARVIS · Alloy — COMPLETE SETUP (macOS: double-click this file)
#  ---------------------------------------------------------------
#  1. Scans your computer (read-only "Computer Setup Search")
#  2. Installs uv + an isolated Python 3.13 + all libraries
#  3. Asks for your API keys once (saved locally to .env)
#  4. Launches Alloy in your browser
#
#  macOS: double-click runs it. Linux: run `bash complete-setup.command`.
#
cd "$(dirname "$0")"

if [ -t 1 ]; then C="$(printf '\033[36m')"; G="$(printf '\033[32m')"; Y="$(printf '\033[33m')"; B="$(printf '\033[1m')"; R="$(printf '\033[0m')"; else C=""; G=""; Y=""; B=""; R=""; fi

echo ""
echo "${B}============================================================${R}"
echo "${B}   JARVIS · Alloy  —  COMPLETE SETUP${R}"
echo "${B}============================================================${R}"
echo ""
echo "  This one file does everything: scans your Mac, installs"
echo "  what's needed, asks for your keys once, and launches Alloy."
echo ""

# ----- Phase 1: Computer Setup Search (read-only) -----
echo "${C}==> Computer Setup Search - getting to know your machine...${R}"
echo ""
OS="$(uname -srm)"
CORES="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo '?')"
if command -v sysctl >/dev/null 2>&1; then
  RAMGB="$(echo "scale=1; $(sysctl -n hw.memsize 2>/dev/null)/1073741824" | bc 2>/dev/null)"
else
  RAMGB="$(awk '/MemTotal/{printf "%.1f", $2/1048576}' /proc/meminfo 2>/dev/null)"
fi
FREEGB="$(df -Pg . 2>/dev/null | awk 'NR==2{print $4}')"
PYV="$(python3 --version 2>&1 || echo 'not found (that is OK)')"
if command -v uv >/dev/null 2>&1; then UVS="already installed"; else UVS="will be installed for you"; fi
if ping -c 1 -t 2 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then NET="connected"; else NET="NOT detected"; fi
HAS_GPU="$(command -v nvidia-smi >/dev/null 2>&1 && echo yes || echo no)"

printf "  OS ............ %s\n" "$OS"
printf "  Cores ......... %s\n" "$CORES"
printf "  Memory ........ %s GB\n" "${RAMGB:-?}"
printf "  Free disk ..... %s GB\n" "${FREEGB:-?}"
printf "  Python ........ %s\n" "$PYV"
printf "  uv ............ %s\n" "$UVS"
printf "  Internet ...... %s\n" "$NET"
echo ""
echo "${C}==> What this means:${R}"
[ "$NET" = "NOT detected" ] && echo "${Y}  ! No internet - connect first; setup downloads the libraries.${R}"
if [ "$HAS_GPU" = "yes" ]; then
  echo "  + NVIDIA GPU found - local AI models are possible later if you want."
else
  echo "  + No dedicated GPU needed - Alloy uses CLOUD vision (Moondream)."
fi
echo "  + uv installs an isolated Python 3.13, so your system Python does not matter."
echo "${G}  Verdict: this machine can run Alloy using cloud AI services. Continuing...${R}"
echo ""

read -r -p "Press Enter to begin installation (or close this window to stop)... " _ || true
echo ""

# ----- Phases 2-4: install + keys + launch -----
exec bash "$(dirname "$0")/setup.sh"
