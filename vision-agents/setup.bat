@echo off
REM ============================================================
REM   JARVIS . Alloy  -  Voice + Vision Assistant  (Windows)
REM   ----------------------------------------------------------
REM   Installs uv, creates an isolated Python 3.13 environment
REM   (uv downloads Python for you - your system Python version
REM   does not matter), installs the libraries, collects your
REM   API keys into .env, and launches the assistant.
REM
REM   Just double-click setup.bat  (or run it from a terminal).
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===============================================
echo    JARVIS . Alloy  -  Voice + Vision Assistant
echo ===============================================
echo.

REM ----- 1. Ensure uv is installed -----
where uv >nul 2>&1
if errorlevel 1 (
    echo ==^> Installing uv ^(a fast Python package ^& version manager^)...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>&1
if errorlevel 1 (
    echo.
    echo  !! uv was installed but isn't on your PATH yet.
    echo     Close this window, open a new one, and run setup.bat again.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('uv --version 2^>^&1') do echo  OK  %%v

REM ----- 2. Create an isolated Python 3.13 environment -----
echo ==^> Creating a Python 3.13 environment ^(uv fetches Python if needed^)...
uv venv --python 3.13
if errorlevel 1 ( echo  !! Failed to create the environment. & pause & exit /b 1 )
echo  OK  Environment ready (.venv).

REM ----- 3. Install the libraries -----
echo ==^> Installing libraries ^(the first run can take a few minutes^)...
uv pip install -r requirements.txt
if errorlevel 1 ( echo  !! Library install failed. Check your internet connection. & pause & exit /b 1 )
echo  OK  Libraries installed.

REM ----- 4. Collect API keys (first run only) -----
if exist ".env" (
    echo  OK  .env already exists - skipping the key questions.
    goto launch
)

echo.
echo ==^> Paste each API key when asked, then press Enter.
echo     (Stream: getstream.io  Anthropic: console.anthropic.com  Deepgram: console.deepgram.com  ElevenLabs: elevenlabs.io)
echo.

:ask_stream_key
set "STREAM_API_KEY="
set /p "STREAM_API_KEY=Stream API Key: "
if not defined STREAM_API_KEY ( echo  !! That can't be empty. & goto ask_stream_key )

:ask_stream_secret
set "STREAM_API_SECRET="
set /p "STREAM_API_SECRET=Stream API Secret: "
if not defined STREAM_API_SECRET ( echo  !! That can't be empty. & goto ask_stream_secret )

:ask_anthropic
set "ANTHROPIC_API_KEY="
set /p "ANTHROPIC_API_KEY=Anthropic API Key: "
if not defined ANTHROPIC_API_KEY ( echo  !! That can't be empty. & goto ask_anthropic )

:ask_deepgram
set "DEEPGRAM_API_KEY="
set /p "DEEPGRAM_API_KEY=Deepgram API Key: "
if not defined DEEPGRAM_API_KEY ( echo  !! That can't be empty. & goto ask_deepgram )

:ask_elevenlabs
set "ELEVENLABS_API_KEY="
set /p "ELEVENLABS_API_KEY=ElevenLabs API Key: "
if not defined ELEVENLABS_API_KEY ( echo  !! That can't be empty. & goto ask_elevenlabs )

(
    echo STREAM_API_KEY=!STREAM_API_KEY!
    echo STREAM_API_SECRET=!STREAM_API_SECRET!
    echo ANTHROPIC_API_KEY=!ANTHROPIC_API_KEY!
    echo DEEPGRAM_API_KEY=!DEEPGRAM_API_KEY!
    echo ELEVENLABS_API_KEY=!ELEVENLABS_API_KEY!
) > .env
echo  OK  Saved your keys to .env (git-ignored - stays on your machine).

:launch
echo.
echo ==^> Launching Alloy...
echo.
echo   A demo page will open in your browser.
echo   Allow your camera and microphone, then just start talking.
echo   Press Ctrl+C here to stop.
echo.

uv run agent.py run
pause
