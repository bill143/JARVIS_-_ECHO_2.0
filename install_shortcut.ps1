<#
.SYNOPSIS
  Creates the "JARVIS" desktop shortcut that runs launch_jarvis.ps1.
.EXAMPLE
  .\install_shortcut.ps1 -MicName ATR4650
#>
param([string]$MicName = "", [string]$CameraName = "C920")

$ErrorActionPreference = "Stop"
$launcher = Join-Path $PSScriptRoot "launch_jarvis.ps1"
if (-not (Test-Path $launcher)) { throw "launch_jarvis.ps1 not found next to this script." }

$desktop = [Environment]::GetFolderPath("Desktop")
$link = Join-Path $desktop "JARVIS.lnk"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`" -CameraName `"$CameraName`""
if ($MicName) { $arguments += " -MicName `"$MicName`"" }

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7  # minimized: no console flash
$shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,190"
$shortcut.Description = "Start JARVIS (Ollama + ECHO + voice assistant) and open its dashboard"
$shortcut.Save()
Write-Output "Created $link"
