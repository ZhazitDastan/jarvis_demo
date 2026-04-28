"""
_discovery.py — автоматическое обнаружение установленных приложений.

Сканирует ярлыки (.lnk) из Start Menu, извлекает путь к .exe,
добавляет в APP_REGISTRY. Результат кэшируется в _app_cache.json.

Порядок работы:
  1. Синхронно: загружаем кэш → APP_REGISTRY доступен сразу
  2. Фоновый поток: полный пересканирует Start Menu → обновляем кэш и APP_REGISTRY
  3. watchdog Observer: следит за Start Menu — мгновенно добавляет/удаляет
     приложения при установке/удалении (без перезапуска Jarvis)
"""

import json
import os
import pathlib
import subprocess
import threading
import time

_CACHE_FILE = pathlib.Path(__file__).parent / "_app_cache.json"
_OBSERVERS: list = []   # хранит watchdog Observer для остановки при выходе
_CACHE_TTL  = 86400   # 24 часа

_START_DIRS = [
    pathlib.Path(os.environ.get("APPDATA", ""))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    pathlib.Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs"),
]

# Имена-мусор которые не стоит добавлять в реестр
_SKIP_NAMES = {
    "uninstall", "удалить", "readme", "read me", "help", "справка",
    "release notes", "changelog", "license", "лицензия", "shortcut",
    "website", "сайт", "support", "поддержка",
}


def _should_skip(name: str) -> bool:
    n = name.lower()
    return any(skip in n for skip in _SKIP_NAMES)


# ── Сканирование ──────────────────────────────────────────────────────────────

def _resolve_lnk(lnk_path: str) -> str | None:
    """Возвращает путь к .exe из .lnk файла (win32com или PowerShell)."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            shell  = win32com.client.Dispatch("WScript.Shell")
            target = shell.CreateShortcut(lnk_path).TargetPath
            if target and target.lower().endswith(".exe"):
                return target
            return None
        finally:
            pythoncom.CoUninitialize()
    except ImportError:
        pass
    except Exception:
        return None

    # Fallback: PowerShell для одного файла
    script = f"""
$sh = New-Object -ComObject WScript.Shell
$t = $sh.CreateShortcut('{lnk_path}').TargetPath
if ($t -and $t.ToLower().EndsWith('.exe')) {{ Write-Output $t }}
"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            capture_output=True, text=True, timeout=5,
        )
        t = r.stdout.strip()
        return t if t else None
    except Exception:
        return None


def _scan_via_wincom() -> list[dict]:
    """Быстрое чтение .lnk через win32com (если установлен pywin32)."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()   # обязательно для каждого фонового потока
    try:
        shell   = win32com.client.Dispatch("WScript.Shell")
        results = []
        for start_dir in _START_DIRS:
            if not start_dir.exists():
                continue
            for lnk in start_dir.rglob("*.lnk"):
                try:
                    target = shell.CreateShortcut(str(lnk)).TargetPath
                    if target and target.lower().endswith(".exe"):
                        results.append({"name": lnk.stem, "path": target})
                except Exception:
                    pass
        return results
    finally:
        pythoncom.CoUninitialize()


def _scan_via_powershell() -> list[dict]:
    """Пакетное чтение .lnk через PowerShell (fallback, ~3–5 сек)."""
    existing = [str(d) for d in _START_DIRS if d.exists()]
    if not existing:
        return []

    dirs_ps = ", ".join(f'"{d}"' for d in existing)
    script = f"""
$sh = New-Object -ComObject WScript.Shell
$out = @()
foreach ($dir in @({dirs_ps})) {{
    Get-ChildItem $dir -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue |
    ForEach-Object {{
        try {{
            $t = $sh.CreateShortcut($_.FullName).TargetPath
            if ($t -and $t.ToLower().EndsWith('.exe')) {{
                $out += [PSCustomObject]@{{name=$_.BaseName; path=$t}}
            }}
        }} catch {{}}
    }}
}}
$out | ConvertTo-Json -Compress
"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            capture_output=True, text=True, timeout=25,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return data or []
    except Exception:
        pass
    return []


def scan() -> list[dict]:
    """Попытка win32com, при ошибке — PowerShell."""
    try:
        return _scan_via_wincom()
    except ImportError:
        return _scan_via_powershell()


# ── Кэш ───────────────────────────────────────────────────────────────────────

def _load_cache() -> list[dict]:
    try:
        if _CACHE_FILE.exists():
            if time.time() - _CACHE_FILE.stat().st_mtime < _CACHE_TTL:
                return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_cache(items: list[dict]) -> None:
    try:
        _CACHE_FILE.write_text(
            json.dumps(items, ensure_ascii=False, indent=None),
            encoding="utf-8",
        )
    except Exception:
        pass


# ── Интеграция с APP_REGISTRY ─────────────────────────────────────────────────

def _merge(items: list[dict], registry: dict) -> None:
    """Добавляет найденные приложения в registry (не перезаписывает ручные)."""
    for item in items:
        name = item.get("name", "")
        path = item.get("path", "")
        if not name or not path:
            continue
        if _should_skip(name):
            continue
        key = name.lower()
        if key in registry:      # ручная запись приоритетнее
            continue
        if not os.path.exists(path):
            continue
        registry[key] = {
            "open":    [path],
            "process": os.path.basename(path),
            "shell":   False,
        }


def _remove_by_lnk(lnk_path: str, registry: dict) -> None:
    """Удаляет из registry запись, добавленную auto-discovery для данного .lnk."""
    key = pathlib.Path(lnk_path).stem.lower()
    entry = registry.get(key)
    if entry and not entry.get("_manual"):
        del registry[key]
        print(f"    [discovery] Удалено приложение: {key}")


# ── watchdog: следим за Start Menu в реальном времени ─────────────────────────

def _start_watcher(registry: dict) -> None:
    """Запускает watchdog Observer на папки Start Menu."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("    [discovery] watchdog не установлен — живое обнаружение недоступно")
        return

    # Дебаунс: установщики создают несколько .lnk сразу, ждём 2 сек после последнего
    _pending: dict[str, str] = {}   # lnk_path → "add" | "remove"
    _lock   = threading.Lock()
    _timer: list = [None]

    def _flush():
        with _lock:
            batch = dict(_pending)
            _pending.clear()
        for lnk_path, action in batch.items():
            if action == "add":
                exe = _resolve_lnk(lnk_path)
                if exe:
                    name = pathlib.Path(lnk_path).stem
                    _merge([{"name": name, "path": exe}], registry)
                    print(f"    [discovery] Новое приложение: {name}")
            else:
                _remove_by_lnk(lnk_path, registry)

    def _schedule(lnk_path: str, action: str):
        with _lock:
            _pending[lnk_path] = action
            if _timer[0] is not None:
                _timer[0].cancel()
            t = threading.Timer(2.0, _flush)
            t.daemon = True
            t.start()
            _timer[0] = t

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory and event.src_path.lower().endswith(".lnk"):
                _schedule(event.src_path, "add")

        def on_deleted(self, event):
            if not event.is_directory and event.src_path.lower().endswith(".lnk"):
                _schedule(event.src_path, "remove")

        def on_moved(self, event):
            if event.src_path.lower().endswith(".lnk"):
                _schedule(event.src_path, "remove")
            if event.dest_path.lower().endswith(".lnk"):
                _schedule(event.dest_path, "add")

    observer = Observer()
    handler  = _Handler()
    watched  = 0
    for d in _START_DIRS:
        if d.exists():
            observer.schedule(handler, str(d), recursive=True)
            watched += 1

    if watched == 0:
        return

    observer.daemon = True
    observer.start()

    # Выставляем daemon на внутренних потоках watchdog (на случай если они не наследуют флаг)
    for emitter in getattr(observer, "_emitters", []):
        try:
            emitter.daemon = True
        except Exception:
            pass

    _OBSERVERS.append(observer)
    print(f"    [discovery] watchdog запущен — слежу за {watched} папками Start Menu")


# ── Точка входа ───────────────────────────────────────────────────────────────

def start(registry: dict) -> None:
    """
    Запускает автообнаружение.
    1. Сразу загружает кэш в registry (синхронно, быстро).
    2. Фоновый поток пересканирует Start Menu и обновляет registry + кэш.
    3. watchdog Observer следит за Start Menu в реальном времени.
    """
    cached = _load_cache()
    if cached:
        _merge(cached, registry)
        print(f"    [discovery] Загружено из кэша: {len(cached)} приложений")

    def _bg():
        items = scan()
        if items:
            _save_cache(items)
            before = len(registry)
            _merge(items, registry)
            added = len(registry) - before
            print(f"    [discovery] Сканирование готово: {len(items)} ярлыков, "
                  f"добавлено новых: {added}")

    threading.Thread(target=_bg, daemon=True, name="app-discovery").start()
    _start_watcher(registry)