# JARVIS · Alloy — "Computer Setup Search"
# A friendly read-only scan: learns your machine and reports what it can run.
# (Read-only — it changes nothing.)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host ""
Write-Host "==> Computer Setup Search - getting to know your machine..." -ForegroundColor Cyan
Write-Host ""

$os     = Get-CimInstance Win32_OperatingSystem
$cpu    = Get-CimInstance Win32_Processor | Select-Object -First 1
$cores  = $env:NUMBER_OF_PROCESSORS
$ramGB  = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round(((Get-PSDrive C).Free) / 1GB, 1)
$gpu    = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', '
$nvidia = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$pyCmd  = Get-Command python -ErrorAction SilentlyContinue
$pyVer  = if ($pyCmd) { (python --version) 2>&1 } else { 'not found (that is OK)' }
$uvOK   = [bool](Get-Command uv -ErrorAction SilentlyContinue)
$net    = Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet

Write-Host ("  OS ................ {0}" -f $os.Caption)
Write-Host ("  CPU ............... {0}" -f $cpu.Name.Trim())
Write-Host ("  Logical cores ..... {0}" -f $cores)
Write-Host ("  Memory ............ {0} GB" -f $ramGB)
Write-Host ("  Free disk (C:) .... {0} GB" -f $freeGB)
Write-Host ("  Graphics .......... {0}" -f $gpu)
Write-Host ("  Python ............ {0}" -f $pyVer)
Write-Host ("  uv ................ {0}" -f $(if ($uvOK) { 'already installed' } else { 'will be installed for you' }))
Write-Host ("  Internet .......... {0}" -f $(if ($net) { 'connected' } else { 'NOT detected' }))
Write-Host ""

Write-Host "==> What this means:" -ForegroundColor Cyan
if (-not $net) {
    Write-Host "  ! No internet detected - please connect first; setup needs to download the libraries." -ForegroundColor Yellow
}
if ($nvidia) {
    Write-Host "  + NVIDIA GPU found - you could run AI models locally later if you ever want to."
} else {
    Write-Host "  + No NVIDIA GPU - and that's fine. Alloy uses CLOUD vision (Moondream), so no GPU is needed."
}
if ($ramGB -lt 8) {
    Write-Host ("  ! Memory is on the low side ({0} GB) - cloud services keep things light, so you should be OK." -f $ramGB) -ForegroundColor Yellow
} else {
    Write-Host ("  + {0} GB of memory is plenty for this." -f $ramGB)
}
if ($freeGB -lt 5) {
    Write-Host ("  ! Only {0} GB free on C: - try to free up a couple GB for Python + libraries." -f $freeGB) -ForegroundColor Yellow
}
Write-Host "  + uv will install an isolated Python 3.13, so your system Python does not matter."
Write-Host ""
Write-Host "  Verdict: this machine can run Alloy using cloud AI services. Continuing to setup..." -ForegroundColor Green
Write-Host ""
