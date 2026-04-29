#Requires -Version 5.1
<#
    J.A.R.V.I.S  -  First-time setup / Pervonachalnaja nastrojka
    Run once on a new machine before using launch.ps1
    Zapustit' odin raz na novoj mashine pered ispol'zovanijem launch.ps1
#>

$ErrorActionPreference = "Stop"
$HERE = $PSScriptRoot
$isRu = (Get-WinUserLanguageList)[0].LanguageTag -like "ru*"
function T($ru, $en) { if ($isRu) { $ru } else { $en } }
function Ask($ru, $en) { Read-Host (T $ru $en) }
function Say($ru, $en) { Write-Host (T $ru $en) }
function OK($ru, $en)  { Write-Host "  OK  $(T $ru $en)" -ForegroundColor Green }
function Warn($ru, $en){ Write-Host "  **  $(T $ru $en)" -ForegroundColor Yellow }
function Head($ru, $en){ Write-Host "`n  >> $(T $ru $en)" -ForegroundColor Cyan }

Clear-Host
Write-Host @"

  +--------------------------------------------------+
  |   J.A.R.V.I.S  -  Setup / Nastrojka             |
  |   Run once on a new machine                      |
  |   Zapustit' odin raz na novoj mashine            |
  +--------------------------------------------------+

"@ -ForegroundColor DarkCyan

# == 1. .env ==================================================================
Head ".env — API kljuchi / API keys"

$envFile  = "$HERE\.env"
$envExample = "$HERE\.env.example"

if (Test-Path $envFile) {
    OK ".env uzhe sushhestvuet" ".env already exists"
} else {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Say "Sozdan .env iz shabljona." ".env created from template."
    }
    $key = Ask "Vvedi OPENAI_API_KEY (Enter - propustit')" "Enter your OPENAI_API_KEY (Enter to skip)"
    if ($key.Trim()) {
        $content = Get-Content $envFile -Raw
        $content = $content -replace 'your-openai-api-key-here', $key.Trim()
        Set-Content $envFile $content -Encoding UTF8
        OK "API kljuch sohranjon v .env" "API key saved to .env"
    } else {
        Warn "API kljuch ne zadanbyj - otredaktiruj .env vruchnuju" "API key not set - edit .env manually later"
    }
}

# == 2. Python check ==========================================================
Head "Python"

$python = $null

# Try to find python in PATH
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    $ver = & python --version 2>&1
    OK "Naiden: $($pythonCmd.Source) ($ver)" "Found: $($pythonCmd.Source) ($ver)"
    $python = $pythonCmd.Source
} else {
    Warn "Python ne najden v PATH" "Python not found in PATH"
    $python = Ask "Ukazi polnyj put' k python.exe" "Enter full path to python.exe"
    if (-not (Test-Path $python)) {
        Write-Host "  !!  $(T 'Put'' ne najden' 'Path not found'): $python" -ForegroundColor Red
        $python = ""
    }
}

# == 3. pip install requirements ==============================================
if ($python) {
    Head "pip install requirements"
    & $python -m pip install -r "$HERE\requirements.txt" -q --no-warn-script-location
    OK "Zavisimosti ustanovleny" "Dependencies installed"
}

# == 4. Models check ==========================================================
Head "STT modeli / STT models"

$modelsDir = "$HERE\models"
$vosk_ru   = "$modelsDir\vosk-model-small-ru-0.22"
$vosk_en   = "$modelsDir\vosk-model-en-us-0.22-lgraph"
$voicesDir = "$modelsDir\voices"

$missingModels = @()

if (-not (Test-Path $vosk_ru))   { $missingModels += "vosk-model-small-ru-0.22  (STT Russian)" }
if (-not (Test-Path $vosk_en))   { $missingModels += "vosk-model-en-us-0.22-lgraph  (STT English)" }
if (-not (Test-Path $voicesDir)) { $missingModels += "voices/  (TTS)" }

if ($missingModels.Count -eq 0) {
    OK "Vse modeli na meste" "All models present"
} else {
    Warn "Otsutstvujut / Missing:" "Missing:"
    foreach ($m in $missingModels) { Write-Host "      - $m" -ForegroundColor Yellow }
    Write-Host ""
    Say "  Skachaj modeli i raspakoj v papku models/" "  Download models and unpack them into the models/ folder"
    Write-Host "  Vosk RU  : https://alphacephei.com/vosk/models -> vosk-model-small-ru-0.22.zip" -ForegroundColor DarkGray
    Write-Host "  Vosk EN  : https://alphacephei.com/vosk/models -> vosk-model-en-us-0.22-lgraph.zip" -ForegroundColor DarkGray
    Write-Host "  Voices   : $(T 'peredat skrytno cherez Telegram/USB' 'transfer privately via Telegram/USB')" -ForegroundColor DarkGray
}

# == 5. launcher.config.json ==================================================
Head "$(T 'Nastrojka putej dlja launch.ps1' 'Path configuration for launch.ps1')"

$cfgFile = "$HERE\launcher.config.json"

if (Test-Path $cfgFile) {
    OK "launcher.config.json uzhe est'" "launcher.config.json already exists"
} else {
    Say "  $(T 'Ukazhi put'' k papke s frontom (React+Tauri)' 'Enter path to frontend folder (React+Tauri)')" `
        "  $(T 'Ukazhi put'' k papke s frontom (React+Tauri)' 'Enter path to frontend folder (React+Tauri)')"
    Say "  $(T 'Primer' 'Example'): D:\Diploma project\J.A.R.V.I.S" `
        "  $(T 'Primer' 'Example'): D:\Diploma project\J.A.R.V.I.S"
    $frontPath = Ask "Frontend path" "Frontend path"

    if (-not (Test-Path $frontPath)) {
        Warn "$(T 'Papka ne najdena, no config budet sozdan' 'Folder not found, config will be created anyway')" `
             "$(T 'Papka ne najdena, no config budet sozdan' 'Folder not found, config will be created anyway')"
    }

    $cfg = @{
        frontend_path = $frontPath.Trim().TrimEnd('\')
        python        = if ($python) { $python } else { "python" }
        backend_port  = 8000
    } | ConvertTo-Json -Depth 2

    Set-Content $cfgFile $cfg -Encoding UTF8
    OK "launcher.config.json sozdan" "launcher.config.json created"
}

# == Done =====================================================================
Write-Host ""
Write-Host "  +----------------------------------------------+" -ForegroundColor Green
Write-Host "  |   $(T 'Nastrojka zavershena!' 'Setup complete!')                          |" -ForegroundColor Green
Write-Host "  |   $(T 'Teper'' zapusti launch.ps1' 'Now run launch.ps1')                     |" -ForegroundColor Green
Write-Host "  +----------------------------------------------+" -ForegroundColor Green
Write-Host ""

Ask "$(T 'Enter - vyhod' 'Press Enter to exit')" "Press Enter to exit"