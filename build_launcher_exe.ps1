#Requires -Version 5.1
<#
    Converts launch.ps1 to JARVIS.exe using ps2exe.
    Run once. Administrator rights are NOT required.

    Konvertiruet launch.ps1 v JARVIS.exe cherez ps2exe.
    Zapustit' odin raz. Prava administratora ne nuzhny.
#>

$ErrorActionPreference = "Stop"
$HERE = $PSScriptRoot

# Language auto-detect
$isRu = (Get-WinUserLanguageList)[0].LanguageTag -like "ru*"
function T($ru, $en) { if ($isRu) { $ru } else { $en } }

Write-Host @"

  +----------------------------------------------+
  |   J.A.R.V.I.S  -  Build Launcher .exe        |
  |   launch.ps1  ->  JARVIS.exe                  |
  |                                               |
  |   $(T 'Preobrazuet skript v .exe fajl' 'Converts the script into a .exe file')              |
  +----------------------------------------------+

"@ -ForegroundColor DarkCyan

# == 1. Install ps2exe if missing =============================================
Write-Host (T "Proverka ps2exe..." "Checking for ps2exe...") -ForegroundColor Cyan

if (-not (Get-Module -ListAvailable -Name ps2exe)) {
    Write-Host (T "  Ustanavlivaju ps2exe (nuzhen internet)..." "  Installing ps2exe (requires internet)...") -ForegroundColor Yellow
    Install-Module -Name ps2exe -Scope CurrentUser -Force -AllowClobber
    Write-Host "  OK  $(T 'ps2exe ustanovlen' 'ps2exe installed')" -ForegroundColor Green
} else {
    Write-Host "  OK  $(T 'ps2exe uzhe ustanovlen' 'ps2exe already installed')" -ForegroundColor Green
}

# == 2. Find icon =============================================================
$iconPaths = @(
    "D:\Diploma project\J.A.R.V.I.S\src-tauri\icons\icon1.ico",
    "D:\Diploma project\J.A.R.V.I.S\src-tauri\icons\icon.ico",
    "$HERE\icon.ico"
)
$icon = $iconPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($icon) {
    Write-Host "  OK  $(T 'Ikonka najdena' 'Icon found'): $icon" -ForegroundColor Green
} else {
    Write-Host "  **  $(T 'Ikonka ne najdena - exe bez ikonki' 'Icon not found - exe will use default icon')" -ForegroundColor Yellow
}

# == 3. Build exe =============================================================
Write-Host ""
Write-Host (T "Sobirajem JARVIS.exe..." "Building JARVIS.exe...") -ForegroundColor Cyan

$outFile  = "$HERE\JARVIS.exe"
$inFile   = "$HERE\launch.ps1"

if (-not (Test-Path $inFile)) {
    Write-Host "  !!  $(T 'Fajl launch.ps1 ne najden' 'File launch.ps1 not found'): $inFile" -ForegroundColor Red
    Read-Host (T "Enter - vyhod" "Press Enter to exit")
    exit 1
}

$params = @{
    InputFile   = $inFile
    OutputFile  = $outFile
    NoConsole   = $false
    Title       = "J.A.R.V.I.S Launcher"
    Description = "J.A.R.V.I.S Desktop Launcher - starts Python backend + Tauri app"
    Company     = "Jarvis Project"
    Version     = "1.0.0"
}
if ($icon) { $params.IconFile = $icon }

Invoke-PS2EXE @params

# == 4. Result ================================================================
if (Test-Path $outFile) {
    $sizeKb = [math]::Round((Get-Item $outFile).Length / 1KB)
    Write-Host ""
    Write-Host "  OK  JARVIS.exe  ($sizeKb KB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "  $(T 'Raspolozhenije' 'Location')  :  $outFile" -ForegroundColor White
    Write-Host "  $(T 'Sledujushhij shag' 'Next step')  :  $(T 'Peretashhi JARVIS.exe na rabochij stol' 'Drag JARVIS.exe to your Desktop')" -ForegroundColor White
    Write-Host ""
    Write-Host "  $(T 'Dvojnoj klik' 'Double-click')  ->  $(T 'git pull + zapusk' 'git pull + launch')" -ForegroundColor DarkCyan
    Write-Host ""
} else {
    Write-Host "  !!  $(T 'Sborka ne udalas''' 'Build failed. Check errors above.')" -ForegroundColor Red
    exit 1
}

Read-Host (T "Enter - vyhod" "Press Enter to exit")