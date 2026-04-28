import subprocess
import config

COMMAND_NAME = "open_settings"
DESCRIPTION = (
    "Open Windows Settings / Открыть настройки Windows. "
    "RU triggers: открой настройки, настройки windows, открой параметры системы. "
    "EN triggers: open settings, open windows settings, system settings."
)
PARAMETERS = {
    "section": {
        "type": "string",
        "description": (
            "Optional settings section. "
            "Examples: display, sound, network, bluetooth, apps, privacy, update. "
            "Примеры: экран, звук, сеть, блютус, приложения, конфиденциальность, обновления."
        ),
    }
}
REQUIRED = []

_SECTIONS = {
    "display":           "ms-settings:display",
    "экран":             "ms-settings:display",
    "sound":             "ms-settings:sound",
    "звук":              "ms-settings:sound",
    "network":           "ms-settings:network",
    "сеть":              "ms-settings:network",
    "wifi":              "ms-settings:network-wifi",
    "вайфай":            "ms-settings:network-wifi",
    "bluetooth":         "ms-settings:bluetooth",
    "блютус":            "ms-settings:bluetooth",
    "apps":              "ms-settings:appsfeatures",
    "приложения":        "ms-settings:appsfeatures",
    "privacy":           "ms-settings:privacy",
    "конфиденциальность":"ms-settings:privacy",
    "update":            "ms-settings:windowsupdate",
    "обновления":        "ms-settings:windowsupdate",
    "nightlight":        "ms-settings:nightlight",
    "ночной свет":       "ms-settings:nightlight",
    "power":             "ms-settings:powersleep",
    "питание":           "ms-settings:powersleep",
    "accounts":          "ms-settings:accounts",
    "аккаунты":          "ms-settings:accounts",
}


def handler(section: str = "") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    uri = _SECTIONS.get(section.lower().strip(), "ms-settings:")
    subprocess.Popen(["start", uri], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return "Opening Settings." if is_en else "Открываю настройки."