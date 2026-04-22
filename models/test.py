# tools/download_with_proxy.py
import requests, os

FILES = [
    "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx",
    "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx",
    "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx",
]

# Укажи свой прокси если есть
PROXIES = {}  # {"https": "http://127.0.0.1:7890"}

import site
TARGET = os.path.join(site.getsitepackages()[0],
         "openwakeword", "resources", "models")

for url in FILES:
    name = url.split("/")[-1]
    print(f"Скачиваю {name}...")
    r = requests.get(url, proxies=PROXIES, timeout=60, stream=True)
    with open(os.path.join(TARGET, name), "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    print(f"  ✓ {name}")