import subprocess
import config

COMMAND_NAME = "night_light"
DESCRIPTION = (
    "Toggle Night Light (blue light filter) / Переключить ночной свет (фильтр синего света). "
    "RU triggers: включи ночной свет, выключи ночной свет, переключи ночной свет, "
    "защита глаз, фильтр синего света. "
    "EN triggers: enable night light, disable night light, toggle night light, blue light filter."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "enum": ["enable", "disable", "toggle"],
        "description": "enable — включить, disable — выключить, toggle — переключить (по умолчанию).",
    }
}
REQUIRED = []

# PowerShell через реестр Windows — работает на Win10/11
_PS_NIGHT_LIGHT = r"""
param([string]$Action)
$keyPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default`$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate"
try {
    $data = (Get-ItemProperty -Path $keyPath -Name "Data" -ErrorAction Stop).Data
    $isOn = $data[18] -eq 21
    $enable = if ($Action -eq "enable") { $true }
              elseif ($Action -eq "disable") { $false }
              else { -not $isOn }   # toggle
    $data[18] = if ($enable) { 21 } else { 19 }
    Set-ItemProperty -Path $keyPath -Name Data -Value $data
    # Перезапускаем ShellExperienceHost чтобы применить изменение
    Stop-Process -Name "ShellExperienceHost" -Force -ErrorAction SilentlyContinue
    Write-Output $(if ($enable) { "ON" } else { "OFF" })
} catch {
    Write-Output "ERROR: $_"
}
"""


def handler(action: str = "toggle") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", _PS_NIGHT_LIGHT, "-Action", action],
        capture_output=True, text=True, encoding="utf-8", timeout=10,
    )
    out = r.stdout.strip()

    if out == "ON":
        return "Night light enabled." if is_en else "Ночной свет включён."
    if out == "OFF":
        return "Night light disabled." if is_en else "Ночной свет выключен."

    # Fallback — открываем настройки
    subprocess.Popen(["start", "ms-settings:nightlight"], shell=True)
    return "Opening night light settings." if is_en else "Открываю настройки ночного света."