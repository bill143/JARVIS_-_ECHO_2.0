@echo off
REM ============================================================
REM   JARVIS & ECHO 2.0  -  One-step setup & launch (Windows)
REM   ----------------------------------------------------------
REM   This script will:
REM     1. Check that Python is installed
REM     2. Create a virtual environment (.venv)
REM     3. Install all required libraries (Pipecat + local voice stack)
REM     4. Ask for your Claude API key (only the first time) -> .env
REM     5. Launch the assistant (desktop build: local mic + speaker)
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

REM ----- 4. Collect the Claude API key (only if .env doesn't exist yet) -----
if exist ".env" (
    echo  OK  .env already exists - skipping the key question.
    goto launch
)

echo.
echo ==^> Let's set up your Claude API key. Paste it when asked, then press Enter.
echo     (Get one from: https://console.anthropic.com -^> API Keys)
echo.

:ask_anthropic
set "ANTHROPIC_API_KEY="
set /p "ANTHROPIC_API_KEY=Anthropic API Key (sk-ant-...): "
if not defined ANTHROPIC_API_KEY ( echo  !! That can't be empty. & goto ask_anthropic )

REM Write the key. Everything else has a sensible default in the code, but you
REM can copy .env.example to .env yourself to tweak the model, voice, wake word, etc.
echo ANTHROPIC_API_KEY=!ANTHROPIC_API_KEY!> .env

echo  OK  Saved your key to .env (this file is git-ignored and stays on your machine).

:launch
echo.
echo ==^> Starting JARVIS ^& ECHO 2.0 (desktop build)...
echo.
echo   Almost there!
echo   - Allow microphone access if Windows asks.
echo   - Say "Hey JARVIS" to wake it, then talk.
echo   - Ask "what can you see?" to trigger the webcam.
echo.
echo   Prefer the browser (WebRTC) build?  Run:  "%VENV_PY%" assistant_web.py
echo   Press Ctrl+C in this window to stop the assistant.
echo.

"%VENV_PY%" assistant.py

pause
