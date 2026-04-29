#Requires -Version 5.1
<#
    J.A.R.V.I.S Desktop Launcher
    Pulls latest git changes, rebuilds only what changed,
    then starts the Python backend + Tauri desktop app.

    Paths are read from launcher.config.json (machine-specific, gitignored).
    Run setup.ps1 first if launcher.config.json does not exist.
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "J.A.R.V.I.S - Launcher"

# ── Fixed paths (launcher lives in the backend repo) ─────────────────────────
$BACKEND_PATH = $PSScriptRoot          # always = folder of this script
$BACKEND_PORT = 8000

# ── Read machine-specific config ─────────────────────────────────────────────
$CFG_FILE = "$BACKEND_PATH\launcher.config.json"

if (-not (Test-Path $CFG_FILE)) {
    Write-Host ""
    Write-Host "  !! launcher.config.json not found." -ForegroundColor Red
    Write-Host "     Run setup.ps1 first to configure paths." -ForegroundColor Yellow
    Write-Host "     Zapusti setup.ps1 dlja nastrojki putej." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter / Enter - vyhod"
    exit 1
}

$cfg           = Get-Content $CFG_FILE -Raw | ConvertFrom-Json
$FRONTEND_PATH = $cfg.frontend_path
$TAURI_EXE     = "$FRONTEND_PATH\src-tauri\target\release\app.exe"

# Python: from config, then PATH, then common install locations
$PYTHON = $cfg.python
if (-not $PYTHON -or $PYTHON -eq "python") {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $PYTHON = $found.Source }
}
if ($cfg.backend_port) { $BACKEND_PORT = $cfg.backend_port }

# ── Language auto-detect ──────────────────────────────────────────────────────
$isRu = (Get-WinUserLanguageList)[0].LanguageTag -like "ru*"
function T($ru, $en) { if ($isRu) { $ru } else { $en } }

function Step($ru, $en) { Write-Host "`n  >> $(T $ru $en)" -ForegroundColor Cyan }
function OK($ru, $en)   { Write-Host "     OK  $(T $ru $en)" -ForegroundColor Green }
function Warn($ru, $en) { Write-Host "     **  $(T $ru $en)" -ForegroundColor Yellow }
function Dot($ru, $en)  { Write-Host "      .  $(T $ru $en)" -ForegroundColor DarkGray }
function Fail($ru, $en) {
    Write-Host "`n  !! $(T $ru $en)`n" -ForegroundColor Red
    Read-Host (T "Enter - vyhod" "Press Enter to exit")
    exit 1
}

Clear-Host
Write-Host @"

   +------------------------------------------+
   |   J . A . R . V . I . S                  |
   |   Desktop Launcher  v1.0                  |
   |   Backend: Python/FastAPI  |  UI: Tauri   |
   +------------------------------------------+

"@ -ForegroundColor DarkCyan

# == 1. Git pull - backend ====================================================
Step "Obnovlenie bekenda..." "Updating backend..."
Set-Location $BACKEND_PATH

$prevBack = git rev-parse HEAD 2>$null
if ($LASTEXITCODE -ne 0) {
    Warn "Git ne naiden v bekende, propuskaju pull" "Git not found in backend, skipping pull"
} else {
    $pullFailed = $false
    try { $null = git pull --ff-only -q 2>&1; if ($LASTEXITCODE -ne 0) { $pullFailed = $true } }
    catch { $pullFailed = $true }
    if ($pullFailed) {
        Warn "Net remote-vetvki, propuskaju pull" "No remote tracking branch, skipping pull"
    } else {
        $curBack = git rev-parse HEAD
        if ($prevBack -ne $curBack) {
            OK "Backend obnovlen" "Backend updated"
            Write-Host "     ->  $($curBack.Substring(0,7))" -ForegroundColor DarkGray
        } else {
            OK "Backend aktualen  [$($curBack.Substring(0,7))]" "Backend is up to date  [$($curBack.Substring(0,7))]"
        }
    }
}

# == 2. Git pull - frontend ===================================================
Step "Obnovlenie frontenda..." "Updating frontend..."
Set-Location $FRONTEND_PATH

$reactChanged = $false
$tauriChanged = $false

$prevFront = git rev-parse HEAD 2>$null
if ($LASTEXITCODE -ne 0) {
    Warn "Git ne naiden vo frontende, propuskaju pull" "Git not found in frontend, skipping pull"
} else {
    $pullFailed = $false
    try { $null = git pull --ff-only -q 2>&1; if ($LASTEXITCODE -ne 0) { $pullFailed = $true } }
    catch { $pullFailed = $true }
    if ($pullFailed) {
        Warn "Net remote-vetvki, propuskaju pull" "No remote tracking branch, skipping pull"
    } else {
        $curFront = git rev-parse HEAD

        if ($prevFront -ne $curFront) {
            $changed      = git diff $prevFront $curFront --name-only 2>$null
            $reactChanged = ($changed | Where-Object { $_ -match '^(src|public|index\.html|vite\.config|tailwind|postcss|package)' }).Count -gt 0
            $tauriChanged = ($changed | Where-Object { $_ -match '^src-tauri' }).Count -gt 0

            OK "Frontend obnovlen" "Frontend updated"
            Write-Host "     ->  $($curFront.Substring(0,7))" -ForegroundColor DarkGray

            if ($tauriChanged)     { Warn "Izmenilsja Rust/Tauri - peresborka ~3-10 min" "Rust/Tauri changed - rebuild ~3-10 min" }
            elseif ($reactChanged) { Warn "Izmenilsja React - peresborka ~30-60 sek" "React source changed - rebuild ~30-60 sec" }
        } else {
            OK "Frontend aktualen  [$($curFront.Substring(0,7))]" "Frontend is up to date  [$($curFront.Substring(0,7))]"
        }
    }
}

# == 3. Build - only when needed ==============================================
$noExe = -not (Test-Path $TAURI_EXE)

if ($noExe -or $reactChanged -or $tauriChanged) {
    Step "Sborka prilozhenija..." "Building application..."
    Set-Location $FRONTEND_PATH

    if ($noExe) {
        Warn "Pervyj zapusk - polnaja sborka (5-10 min)..." "First run - full build (5-10 min)..."
    } else {
        Warn "Zapuskajem cargo tauri build..." "Running cargo tauri build..."
    }

    if ($reactChanged -or $noExe) {
        Dot "npm install..." "npm install..."
        npm install --silent 2>&1 | Out-Null
    }

    Dot "npm run tauri:build..." "npm run tauri:build..."
    npm run tauri:build
    if ($LASTEXITCODE -ne 0) { Fail "Sborka upala. Prover' oshibki vyshe." "Build failed. Check errors above." }
    OK "Sborka zavershena" "Build complete"
}

if (-not (Test-Path $TAURI_EXE)) {
    Fail "Binarnik ne najden: $TAURI_EXE" "Binary not found: $TAURI_EXE"
}

# == 4. Start Python backend ==================================================
Step "Zapusk bekenda (port $BACKEND_PORT)..." "Starting backend (port $BACKEND_PORT)..."
Set-Location $BACKEND_PATH

if (-not (Test-Path $PYTHON)) {
    Fail "Python ne najden: $PYTHON  ->  otredaktiruj launcher.config.json" `
         "Python not found: $PYTHON  ->  edit launcher.config.json"
}

# Kill stale process on same port
$old = Get-NetTCPConnection -LocalPort $BACKEND_PORT -ErrorAction SilentlyContinue | Select-Object -First 1
if ($old) {
    Stop-Process -Id (Get-Process -Id $old.OwningProcess -EA SilentlyContinue).Id -Force -EA SilentlyContinue
    Start-Sleep -Milliseconds 500
}

$backend = Start-Process `
    -FilePath     $PYTHON `
    -ArgumentList "-m", "uvicorn", "api.server:app",
                  "--host", "127.0.0.1",
                  "--port", "$BACKEND_PORT" `
    -WorkingDirectory $BACKEND_PATH `
    -WindowStyle  Hidden `
    -PassThru

OK "Backend zapushchen  [PID $($backend.Id)]" "Backend started  [PID $($backend.Id)]"

# Wait for API
Dot "Ozhidanije API..." "Waiting for API..."
$tries = 0
do {
    Start-Sleep -Milliseconds 500
    $tries++
    try   { $r = Invoke-WebRequest "http://127.0.0.1:$BACKEND_PORT/status" -TimeoutSec 1 -UseBasicParsing -EA Stop }
    catch { $r = $null }
} while (-not $r -and $tries -lt 20)

if ($tries -ge 20) { Warn "Backend dolgo ne otvechaet - zapuskajem prilozhenie" "Backend slow to respond - launching app anyway" }
else               { OK "Backend otvechaet" "Backend is responding" }

# == 5. Start Tauri app =======================================================
Step "Zapusk J.A.R.V.I.S..." "Launching J.A.R.V.I.S..."
$app = Start-Process -FilePath $TAURI_EXE -PassThru
OK "Prilozhenie otkryto  [PID $($app.Id)]" "Application launched  [PID $($app.Id)]"

Write-Host ""
Write-Host "  $(T 'Eto okno mozhno svernut''' 'You can minimise this window') - $(T 'ono zakroetsja vmeste s prilozhenijem' 'it closes when the app exits')." -ForegroundColor DarkGray
Write-Host ""

# == 6. Wait for close ========================================================
$app.WaitForExit()

Step "Prilozhenie zakryto. Ostanovka bekenda..." "App closed. Stopping backend..."
Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
OK "Gotovo." "Done."
Start-Sleep -Seconds 1