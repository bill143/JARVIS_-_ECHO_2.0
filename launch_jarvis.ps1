<#
.SYNOPSIS
  One-click JARVIS: starts Ollama, ECHO and JARVIS (each only if not already
  running) and opens the dashboard window. Used by the "JARVIS" desktop shortcut.

.PARAMETER MicName
  Part of the microphone's name (e.g. "ATR4650"). Picked by name, not index.
.PARAMETER CameraName
  Part of the webcam's name for the eyes (default "C920").
.PARAMETER Model
  ECHO model alias for the brain (default "brain": Groq free tier, then local
  Ollama, then paid clouds once funded). Overrides ECHO_MODEL from .env.
#>
param(
    [string]$MicName = $env:AUDIO_INPUT_DEVICE_NAME,
    [string]$CameraName = "C920",
    [string]$Model = "brain"
)

$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot
$LogDir = Join-Path $env:LOCALAPPDATA "JARVIS\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$EchoUrl = "http://127.0.0.1:4000"
$DashboardUrl = "http://127.0.0.1:8090/"

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Http([string]$Url, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return $true }
        } catch { Start-Sleep -Milliseconds 700 }
    }
    return $false
}

function Show-Problem([string]$Message) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($Message, "JARVIS", "OK", "Warning") | Out-Null
}

# 1) Ollama (local brain fallback + eyes)
if (-not (Test-Port 11434)) {
    $ollamaApp = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
    if (Test-Path $ollamaApp) {
        Start-Process -FilePath $ollamaApp -WindowStyle Hidden
    } elseif (Get-Command ollama -ErrorAction SilentlyContinue) {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    } else {
        Show-Problem "Ollama is not installed. JARVIS will run, but without the local model and eyes."
    }
}

# 2) ECHO (the model router) - reads its keys from echo\.env itself.
if (-not (Test-Port 4000)) {
    $litellm = Join-Path $Repo "echo\.venv\Scripts\litellm.exe"
    if (-not (Test-Path $litellm)) { Show-Problem "ECHO is not installed ($litellm missing)."; exit 1 }
    $env:PYTHONIOENCODING = "utf-8"
    Start-Process -FilePath $litellm -ArgumentList "--config", "config.yaml", "--port", "4000" `
        -WorkingDirectory (Join-Path $Repo "echo") -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "echo.log") -RedirectStandardError (Join-Path $LogDir "echo.err.log")
    if (-not (Wait-Http "$EchoUrl/health/liveliness" 90)) {
        Show-Problem "ECHO did not start within 90 seconds. See $LogDir\echo.err.log"
        exit 1
    }
}

# 3) JARVIS (voice + dashboard). If it is already running, just show the window.
if (Test-Port 8090) {
    $edge = (Get-Command msedge -ErrorAction SilentlyContinue).Source
    if (-not $edge) { $edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe" }
    if (Test-Path $edge) {
        Start-Process -FilePath $edge -ArgumentList "--app=$DashboardUrl", "--user-data-dir=$env:LOCALAPPDATA\JARVIS\edge-app"
    } else {
        Start-Process $DashboardUrl
    }
    exit 0
}

$env:ECHO_BASE_URL = "$EchoUrl/v1"
$env:ECHO_MODEL = $Model
if ($MicName) { $env:AUDIO_INPUT_DEVICE_NAME = $MicName }
$env:CAMERA_NAME = $CameraName
$env:DASHBOARD_OPEN = "true"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
Remove-Item Env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue  # never inherit a dev-tool proxy

$python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { Show-Problem "JARVIS is not installed ($python missing). Run setup.bat first."; exit 1 }
Start-Process -FilePath $python -ArgumentList "assistant.py" -WorkingDirectory $Repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $LogDir "jarvis.log") -RedirectStandardError (Join-Path $LogDir "jarvis.err.log")
# JARVIS opens its own dashboard window as soon as the server is up.
