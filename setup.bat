@echo off
REM ============================================================
REM   JARVIS & ECHO 2.0  -  One-step setup & launch (Windows)
REM   ----------------------------------------------------------
REM   This script will:
REM     1. Check that Python is installed
REM     2. Create a virtual environment (.venv)
REM     3. Install all required libraries
REM     4. Download the voice-detection model files
REM     5. Ask for your API keys (only the first time) -> .env
REM     6. Launch the assistant
REM
REM   Just double-click setup.bat  (or run it from a terminal).
REM ============================================================
setlocal enabledelayedexpansion

REM Always run from the folder this script lives in.
cd /d "%~dp0"

echo.
echo ===========================================
echo    JARVIS ^& ECHO 2.0  -  Setup ^& Launch
echo ===========================================
echo.

REM ----- 1. Find Python -----
echo ==^> Checking for Python...
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo.
    echo  !! Python was not found.
    echo     Please install it from https://www.python.org/downloads/
    echo     IMPORTANT: tick "Add python.exe to PATH" during install, then run this again.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo  OK  Found %%v

REM ----- 2. Create the virtual environment -----
if not exist ".venv" (
    echo ==^> Creating virtual environment (.venv)...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo  !! Failed to create the virtual environment.
        pause
        exit /b 1
    )
    echo  OK  Virtual environment created.
) else (
    echo  OK  Virtual environment already exists.
)

set "VENV_PY=.venv\Scripts\python.exe"

REM ----- 3. Install the libraries -----
echo ==^> Upgrading pip and installing libraries (this can take a few minutes)...
"%VENV_PY%" -m pip install -U pip >nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo  !! Library installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)
echo  OK  Libraries installed.

REM ----- 4. Download the voice-detection model files -----
echo ==^> Downloading model files (Silero VAD / turn detector)...
"%VENV_PY%" assistant.py download-files
echo  OK  Model files ready.

REM ----- 5. Collect API keys (only if .env doesn't exist yet) -----
if exist ".env" (
    echo  OK  .env already exists - skipping the key questions.
    goto launch
)

echo.
echo ==^> Let's set up your API keys. Paste each one when asked, then press Enter.
echo     (Get them from: livekit.cloud, console.deepgram.com, platform.openai.com)
echo.

:ask_livekit_url
set "LIVEKIT_URL="
set /p "LIVEKIT_URL=LiveKit URL (wss://...): "
if not defined LIVEKIT_URL ( echo  !! That can't be empty. & goto ask_livekit_url )

:ask_livekit_key
set "LIVEKIT_API_KEY="
set /p "LIVEKIT_API_KEY=LiveKit API Key: "
if not defined LIVEKIT_API_KEY ( echo  !! That can't be empty. & goto ask_livekit_key )

:ask_livekit_secret
set "LIVEKIT_API_SECRET="
set /p "LIVEKIT_API_SECRET=LiveKit API Secret: "
if not defined LIVEKIT_API_SECRET ( echo  !! That can't be empty. & goto ask_livekit_secret )

:ask_deepgram
set "DEEPGRAM_API_KEY="
set /p "DEEPGRAM_API_KEY=Deepgram API Key: "
if not defined DEEPGRAM_API_KEY ( echo  !! That can't be empty. & goto ask_deepgram )

:ask_openai
set "OPENAI_API_KEY="
set /p "OPENAI_API_KEY=OpenAI API Key: "
if not defined OPENAI_API_KEY ( echo  !! That can't be empty. & goto ask_openai )

(
    echo LIVEKIT_URL=!LIVEKIT_URL!
    echo LIVEKIT_API_KEY=!LIVEKIT_API_KEY!
    echo LIVEKIT_API_SECRET=!LIVEKIT_API_SECRET!
    echo DEEPGRAM_API_KEY=!DEEPGRAM_API_KEY!
    echo OPENAI_API_KEY=!OPENAI_API_KEY!
) > .env

echo  OK  Saved your keys to .env (this file is git-ignored and stays on your machine).

:launch
echo.
echo ==^> Starting JARVIS ^& ECHO 2.0...
echo.
echo   Almost there!
echo   1. Open the playground:  https://agents-playground.livekit.io/
echo   2. Connect it to the SAME LiveKit project as your keys.
echo   3. Allow your microphone (and camera, for vision) and start talking.
echo.
echo   Press Ctrl+C in this window to stop the assistant.
echo.

"%VENV_PY%" assistant.py start

pause
