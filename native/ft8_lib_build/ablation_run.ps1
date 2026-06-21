# ablation_run.ps1 — Start OpenWSFZ with a specific config DLL, run a harness scenario,
# collect owsfz-all.txt, then stop OpenWSFZ.
#
# Usage (from repo root):
#   .\native\ft8_lib_build\ablation_run.ps1 -CfgN 2 -Scenario s7-compounding.json -RunDir cfg2-s7
#
# Prereqs: OpenWSFZ must NOT be running, config.json in AppData must exist.

param(
    [int]    $CfgN,           # 1, 2, 3, or 4
    [string] $Scenario,       # e.g. "s7-compounding.json"
    [string] $RunDir,         # relative to qa/rr-study/results/d009-ablation-2026-06-21/
    [switch] $SkipStart       # if set, don't start/stop OpenWSFZ (for testing)
)

$ErrorActionPreference = "Stop"
$Repo   = "D:\Projects\claude\OpenWSFZ"
$AllTxt = "$Repo\ALL.TXT"
$DllSrc = "$Repo\native\ft8_lib_build\libft8_cfg${CfgN}.dll"
$DllDst = "$Repo\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll"
$DllRun = "$Repo\src\OpenWSFZ.Daemon\bin\Debug\net10.0\libft8.dll"
$AbDir  = "$Repo\qa\rr-study\results\d009-ablation-2026-06-21"
$FullRunDir = "$AbDir\$RunDir"

Write-Host ""
Write-Host "=== Ablation run: Config $CfgN | $Scenario | $RunDir ===" -ForegroundColor Cyan

# Step 1: Copy cfgN DLL to source dir and Debug output dir
Write-Host "[1] Deploying cfg${CfgN} DLL..." -ForegroundColor Yellow
Copy-Item -Force $DllSrc $DllDst
Copy-Item -Force $DllSrc $DllRun
Write-Host "    $DllSrc -> $DllDst (src)"
Write-Host "    $DllSrc -> $DllRun (run)"

# Step 2: Start OpenWSFZ
$proc = $null
if (-not $SkipStart) {
    Write-Host "[2] Starting OpenWSFZ (dotnet run --no-build)..." -ForegroundColor Yellow
    $proc = Start-Process "dotnet" `
        -ArgumentList "run --project src/OpenWSFZ.Daemon --no-build" `
        -WorkingDirectory $Repo `
        -PassThru
    Write-Host "    PID: $($proc.Id)"

    # Wait for startup (decode cycles are 15 sec; let it align to first boundary)
    Write-Host "    Waiting 20s for startup and cycle alignment..."
    Start-Sleep -Seconds 20
}

# Step 3: Create run dir and clear ALL.TXT
Write-Host "[3] Preparing run directory and clearing ALL.TXT..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $FullRunDir | Out-Null
Set-Content -Path $AllTxt -Value "" -NoNewline

# Step 4: Run harness
Write-Host "[4] Running harness: $Scenario -> $RunDir..." -ForegroundColor Yellow
Set-Location "$Repo\qa\rr-study"
$harness = "python harness/run_scenario.py scenarios/$Scenario --run-dir results/d009-ablation-2026-06-21/$RunDir"
Write-Host "    CMD: $harness"

# Run synchronously (this will take 25-30 min; use background from calling script)
Invoke-Expression $harness
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: harness failed with exit $LASTEXITCODE" -ForegroundColor Red
}

# Step 5: Collect owsfz-all.txt
Write-Host "[5] Collecting owsfz-all.txt..." -ForegroundColor Yellow
Set-Location $Repo
$AllTxtDest = "$FullRunDir\owsfz-all.txt"
if (Test-Path $AllTxt) {
    Copy-Item -Force $AllTxt $AllTxtDest
    $lines = (Get-Content $AllTxt | Measure-Object -Line).Lines
    Write-Host "    Copied $lines lines -> $AllTxtDest"
} else {
    Write-Host "    WARNING: ALL.TXT not found!" -ForegroundColor Red
}

# Step 6: Stop OpenWSFZ
if ($proc -and -not $SkipStart) {
    Write-Host "[6] Stopping OpenWSFZ (PID $($proc.Id))..." -ForegroundColor Yellow
    try {
        Stop-Process -Id $proc.Id -Force
        Write-Host "    Stopped."
    } catch {
        Write-Host "    Process already stopped or not found." -ForegroundColor Gray
    }
}

Write-Host "=== Done: $RunDir ===" -ForegroundColor Green
