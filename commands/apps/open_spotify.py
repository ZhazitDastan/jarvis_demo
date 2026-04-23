import subprocess
import os
import webbrowser

COMMAND_NAME = "open_spotify"
DESCRIPTION = "Открыть Spotify"
PARAMETERS = {}
REQUIRED = []

_SPOTIFY_PATHS = [
    os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "Spotify.exe"),
]


def handler() -> str:
    for path in _SPOTIFY_PATHS:
        if os.path.exists(path):
            subprocess.Popen([path])
            return "Открываю Spotify"
    webbrowser.open("https://open.spotify.com")
    return "Открываю Spotify в браузере"