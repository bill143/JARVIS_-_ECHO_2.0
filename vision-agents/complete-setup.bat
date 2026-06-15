@echo off
REM ============================================================
REM   JARVIS . Alloy  -  COMPLETE SETUP  (one double-click)
REM   ----------------------------------------------------------
REM   1. Scans your computer (read-only "Computer Setup Search")
REM   2. Installs uv + an isolated Python 3.13 + all libraries
REM   3. Asks for your API keys once (saved locally to .env)
REM   4. Launches Alloy in your browser
REM
REM   Just double-click this file. Nothing else to do.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo    JARVIS . Alloy  -  COMPLETE SETUP
echo ============================================================
echo.
echo   This one file does everything: scans your PC, installs
echo   what's needed, asks for your keys once, and launches Alloy.
echo.

REM ----- Phase 1: Computer Setup Search (read-only scan) -----
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scan.ps1"
if errorlevel 1 (
    echo  !! Could not run the system scan. Continuing to setup anyway...
    echo.
)

echo Press any key to begin installation ^(or close this window to stop^)...
pause >nul
echo.

REM ----- Phases 2-4: install + keys + launch (reuse setup.bat) -----
call "%~dp0setup.bat"
