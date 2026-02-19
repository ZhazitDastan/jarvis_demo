import os
import json
import psutil
import subprocess
import threading
import winreg
import ctypes
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timedelta
import win32api
import win32con
import win32gui


# ──────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────

def send_alt_f4(hwnd):
    """Send Alt+F4 to window — polite keyboard close"""
    win32gui.SetForegroundWindow(hwnd)
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt down
    win32api.keybd_event(win32con.VK_F4, 0, 0, 0)  # F4 down
    win32api.keybd_event(win32con.VK_F4, 0, win32con.KEYEVENTF_KEYUP, 0)  # F4 up
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)


CACHE_DIR = Path("../../cache")
CACHE_FILE = CACHE_DIR / "apps_cache.json"
CACHE_META = CACHE_DIR / "meta_cache.json"

MIN_APP_SIZE_KB = 50  # smaller than this → not a real app
MAX_APP_SIZE_MB = 500  # bigger than this → probably not a launcher
AUTO_UPDATE_HOURS = 24  # auto-reindex interval

BROWSERS = ["chrome", "firefox", "msedge", "opera", "brave", "vivaldi", "yandex"]

IGNORE_KEYWORDS = [
    "setup", "install", "uninstall", "uninst", "update", "updater",
    "patch", "redist", "vcredist", "directx", "dxsetup", "dotnet",
    "crash", "report", "helper", "register", "activate", "repair",
    "cleanup", "remover", "migration", "wizard", "bootstrap",
    "notification", "tray", "daemon", "service", "agent", "hook",
    "injector", "proxy", "handler", "monitor", "watcher", "scheduler"
]

SKIP_DIRS = [
    "windows", "system32", "syswow64", "winsxs", "servicing",
    "assembly", "microsoft.net", "windowsapps", "temp", "tmp",
    "$recycle.bin", "appdata\\local\\temp",
    "appdata\\local\\microsoft\\windows",
    "appdata\\roaming\\microsoft", "commonfiles\\microsoft"
]

# Known useful Windows built-in apps
WINDOWS_BUILTINS = [
    {"name": "calc", "exe": "calc.exe", "path": r"C:\Windows\System32\calc.exe", "size_kb": 0, "source": "builtin"},
    {"name": "notepad", "exe": "notepad.exe", "path": r"C:\Windows\System32\notepad.exe", "size_kb": 0,
     "source": "builtin"},
    {"name": "mspaint", "exe": "mspaint.exe", "path": r"C:\Windows\System32\mspaint.exe", "size_kb": 0,
     "source": "builtin"},
    {"name": "taskmgr", "exe": "taskmgr.exe", "path": r"C:\Windows\System32\taskmgr.exe", "size_kb": 0,
     "source": "builtin"},
    {"name": "explorer", "exe": "explorer.exe", "path": r"C:\Windows\explorer.exe", "size_kb": 0, "source": "builtin"},
    {"name": "cmd", "exe": "cmd.exe", "path": r"C:\Windows\System32\cmd.exe", "size_kb": 0, "source": "builtin"},
    {"name": "powershell", "exe": "powershell.exe",
     "path": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "size_kb": 0, "source": "builtin"},
    {"name": "regedit", "exe": "regedit.exe", "path": r"C:\Windows\regedit.exe", "size_kb": 0, "source": "builtin"},
    {"name": "msconfig", "exe": "msconfig.exe", "path": r"C:\Windows\System32\msconfig.exe", "size_kb": 0,
     "source": "builtin"},
    {"name": "snippingtool", "exe": "SnippingTool.exe", "path": r"C:\Windows\System32\SnippingTool.exe", "size_kb": 0,
     "source": "builtin"},
    {"name": "wordpad", "exe": "wordpad.exe", "path": r"C:\Windows\System32\wordpad.exe", "size_kb": 0,
     "source": "builtin"},
    {"name": "control", "exe": "control.exe", "path": r"C:\Windows\System32\control.exe", "size_kb": 0,
     "source": "builtin"},
]


# ──────────────────────────────────────────
#  CACHE META (timestamp)
# ──────────────────────────────────────────

def load_meta() -> dict:
    if CACHE_META.exists():
        with open(CACHE_META, "r") as f:
            return json.load(f)
    return {}


def save_meta(data: dict):
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CACHE_META, "w") as f:
        json.dump(data, f, indent=2)


def is_cache_outdated() -> bool:
    """Check if cache is older than AUTO_UPDATE_HOURS"""
    meta = load_meta()
    last_update = meta.get("last_update")
    if not last_update:
        return True
    last_dt = datetime.fromisoformat(last_update)
    return datetime.now() - last_dt > timedelta(hours=AUTO_UPDATE_HOURS)


def get_cache_age() -> str:
    meta = load_meta()
    last_update = meta.get("last_update")
    if not last_update:
        return "never"
    last_dt = datetime.fromisoformat(last_update)
    diff = datetime.now() - last_dt
    hours = int(diff.total_seconds() // 3600)
    mins = int((diff.total_seconds() % 3600) // 60)
    return f"{hours}h {mins}m ago"


# ──────────────────────────────────────────
#  FILE SIZE VALIDATION
# ──────────────────────────────────────────

def is_valid_app_size(path: str) -> bool:
    try:
        size_kb = os.path.getsize(path) / 1024
        size_mb = size_kb / 1024
        return MIN_APP_SIZE_KB <= size_kb and size_mb <= MAX_APP_SIZE_MB
    except (OSError, PermissionError):
        return False


# ──────────────────────────────────────────
#  REGISTRY & START MENU
# ──────────────────────────────────────────

def get_installed_from_registry() -> dict:
    installed = {}
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    for hive in hives:
        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(hive, reg_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        try:
                            location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                            if location and os.path.isdir(location):
                                installed[location.lower().rstrip("\\")] = True
                        except FileNotFoundError:
                            pass
                        winreg.CloseKey(subkey)
                    except (OSError, PermissionError):
                        pass
                winreg.CloseKey(key)
            except (OSError, PermissionError):
                pass
    return installed


def get_start_menu_shortcuts() -> list:
    apps = []
    start_menu_paths = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        for start_path in start_menu_paths:
            for root, _, files in os.walk(start_path):
                for file in files:
                    if file.endswith(".lnk"):
                        try:
                            shortcut = shell.CreateShortCut(os.path.join(root, file))
                            target = shortcut.Targetpath
                            if (target and target.lower().endswith(".exe")
                                    and os.path.exists(target)
                                    and not should_skip_file(os.path.basename(target))
                                    and is_valid_app_size(target)):
                                apps.append({
                                    "name": file[:-4].lower(),
                                    "exe": os.path.basename(target),
                                    "path": target,
                                    "size_kb": round(os.path.getsize(target) / 1024),
                                    "source": "startmenu"
                                })
                        except Exception:
                            pass
    except ImportError:
        pass
    return apps


# ──────────────────────────────────────────
#  DISK SCAN
# ──────────────────────────────────────────

def should_skip_dir(path: str) -> bool:
    path_lower = path.lower()
    return any(skip in path_lower for skip in SKIP_DIRS)


def should_skip_file(filename: str) -> bool:
    name_lower = filename.lower().replace(".exe", "")
    return any(keyword in name_lower for keyword in IGNORE_KEYWORDS)


def scan_drive(drive: str, installed_dirs: dict) -> list:
    results = []

    try:
        for root, dirs, files in os.walk(drive, topdown=True):
            if should_skip_dir(root):
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            root_lower = root.lower().rstrip("\\")
            is_known = any(
                root_lower == loc or root_lower.startswith(loc + "\\")
                for loc in installed_dirs
            )
            if not is_known:
                continue

            for file in files:
                if not file.lower().endswith(".exe"):
                    continue
                if should_skip_file(file):
                    continue
                full_path = os.path.join(root, file)

                # Size check — skip stubs and huge binaries
                if not is_valid_app_size(full_path):
                    continue

                size_kb = round(os.path.getsize(full_path) / 1024)
                results.append({
                    "name": file[:-4].lower(),
                    "exe": file,
                    "path": full_path,
                    "size_kb": size_kb,
                    "source": "disk"
                })
    except (PermissionError, OSError):
        pass
    return results


def get_all_drives() -> list:
    return [
        part.mountpoint
        for part in psutil.disk_partitions()
        if os.path.exists(part.mountpoint)
    ]


# ──────────────────────────────────────────
#  DEDUPLICATION & CLEANUP
# ──────────────────────────────────────────

def deduplicate(apps: list) -> list:
    # Step 1: deduplicate by exact path
    seen_paths = {}
    for app in apps:
        key = app["path"].lower()
        if key not in seen_paths:
            seen_paths[key] = app

    path_deduped = list(seen_paths.values())

    # Step 2: same name → builtin wins, otherwise keep largest file
    by_name = {}
    for app in path_deduped:
        name = app["name"]
        if name not in by_name:
            by_name[name] = app
        else:
            existing = by_name[name]
            # Builtin always wins
            if app["source"] == "builtin":
                by_name[name] = app
            # Otherwise keep largest
            elif existing["source"] != "builtin" and app["size_kb"] > existing["size_kb"]:
                by_name[name] = app

    return list(by_name.values())


def clean_cache(apps: list) -> tuple[list, int]:
    """
    Auto-clean: remove entries where .exe no longer exists on disk.
    Returns (cleaned_list, removed_count)
    """
    valid = [app for app in apps if os.path.exists(app["path"])]
    removed = len(apps) - len(valid)
    return valid, removed


# ──────────────────────────────────────────
#  INDEX BUILD
# ──────────────────────────────────────────

def build_index(force: bool = False, silent: bool = False) -> list:
    CACHE_DIR.mkdir(exist_ok=True)

    # Load from cache if fresh enough
    if not force and CACHE_FILE.exists() and not is_cache_outdated():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            apps = json.load(f)
        if not silent:
            print(f"Loaded {len(apps)} apps from cache (updated {get_cache_age()})")
        return apps

    if not silent:
        reason = "forced" if force else "cache outdated"
        print(f"Building app index ({reason})...")

    installed_dirs = get_installed_from_registry()
    shortcut_apps = get_start_menu_shortcuts()

    # Scan drives
    drives = get_all_drives()
    disk_apps = []
    lock = threading.Lock()

    def scan_and_collect(drive):
        found = scan_drive(drive, installed_dirs)
        with lock:
            disk_apps.extend(found)
        if not silent:
            print(f"  {drive} → {len(found)} apps")

    with ThreadPoolExecutor(max_workers=len(drives)) as executor:
        executor.map(scan_and_collect, drives)

    # Add built-in Windows apps (filter only existing paths)
    builtins = [app for app in WINDOWS_BUILTINS if os.path.exists(app["path"])]
    if not silent:
        print(f"Added {len(builtins)} built-in Windows apps")

    # Combine all sources
    all_apps = shortcut_apps + disk_apps

    # Clean only non-builtins (builtins bypass file existence check)
    cleaned, removed_dead = clean_cache(all_apps)

    # Add builtins AFTER cleaning, then deduplicate
    final = deduplicate(cleaned + builtins)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    save_meta({"last_update": datetime.now().isoformat()})

    if not silent:
        print(f"\nIndex built: {len(final)} apps  |  removed {removed_dead} dead entries")
        print(f"Cache saved → {CACHE_FILE}")
    return final


def background_reindex(apps_ref: list):
    """Reindex silently in background, update list in place"""

    def _task():
        print("\n[Background] Updating app index...")
        new_apps = build_index(force=True, silent=True)
        apps_ref.clear()
        apps_ref.extend(new_apps)
        print(f"[Background] Done: {len(new_apps)} apps")

    threading.Thread(target=_task, daemon=True).start()


def auto_update_scheduler(apps_ref: list):
    """Check every hour if cache needs updating, reindex if so"""

    def _loop():
        while True:
            time.sleep(3600)  # check every hour
            if is_cache_outdated():
                print("\n[Auto-update] Cache is outdated, reindexing...")
                new_apps = build_index(force=True, silent=True)
                apps_ref.clear()
                apps_ref.extend(new_apps)
                print(f"[Auto-update] Done: {len(new_apps)} apps")

    threading.Thread(target=_loop, daemon=True).start()


# ──────────────────────────────────────────
#  SEARCH
# ──────────────────────────────────────────

def search_apps(query: str, apps: list) -> list:
    q = query.lower().strip()
    exact, starts, contains = [], [], []
    for app in apps:
        name = app["name"]
        if name == q:
            exact.append(app)
        elif name.startswith(q):
            starts.append(app)
        elif q in name:
            contains.append(app)
    return exact or starts or contains


# ──────────────────────────────────────────
#  WINDOW CONTROL
# ──────────────────────────────────────────

user32 = ctypes.windll.user32
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9


def get_windows_by_name(name: str) -> list:
    name_lower = name.lower().replace(".exe", "")
    handles = []

    def enum_callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                proc = psutil.Process(pid.value)
                if name_lower in proc.name().lower():
                    handles.append(hwnd)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
    )
    user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
    return handles


def window_action(name: str, action: int, label: str):
    handles = get_windows_by_name(name)
    if not handles:
        print(f"No visible windows found for '{name}'")
        return
    for hwnd in handles:
        user32.ShowWindow(hwnd, action)
    print(f"'{name}' → {label}")


# ──────────────────────────────────────────
#  BROWSER SPECIAL HANDLING
# ──────────────────────────────────────────

def count_browser_tabs(name: str) -> int:
    name_lower = name.lower().replace(".exe", "")
    count = 0
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if name_lower in proc.info['name'].lower():
                if "--type=renderer" in " ".join(proc.info['cmdline'] or []):
                    count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return count


def close_browser_gracefully(name: str):
    handles = get_windows_by_name(name)
    if not handles:
        print(f"No browser window found for '{name}'")
        return
    tabs = count_browser_tabs(name)
    if tabs > 3:
        confirm = input(
            f"Browser has ~{tabs} open tabs. Close anyway? (yes/no): "
        ).strip().lower()
        if confirm != "yes":
            print("Cancelled")
            return
    WM_CLOSE = 0x0010
    user32.PostMessageW(handles[0], WM_CLOSE, 0, 0)
    print(f"Sent close signal to {name} (session will be saved by browser)")


# ──────────────────────────────────────────
#  RUNNING PROCESSES
# ──────────────────────────────────────────

def get_running_processes() -> dict:
    running = {}
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name'].lower().replace(".exe", "")
            running[name] = proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return running


def is_running(name: str) -> bool:
    return name.lower().replace(".exe", "") in get_running_processes()


def is_browser(name: str) -> bool:
    return any(b in name.lower() for b in BROWSERS)


# ──────────────────────────────────────────
#  OPEN / CLOSE
# ──────────────────────────────────────────

def open_app(app: dict):
    name = app["name"]
    if not os.path.exists(app["path"]):
        print(f"File not found: {app['path']}")
        print("Try 'reindex' to refresh")
        return
    if is_running(name):
        print(f"'{name}' is already running!")
        if input("Open another instance? (yes/no): ").strip().lower() != "yes":
            return
    try:
        subprocess.Popen(app["path"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Launched: {name}  ({app['size_kb']} KB)  →  {app['path']}")
    except PermissionError:
        print("Permission denied. Try running as administrator.")
    except Exception as e:
        print(f"Failed to launch '{name}': {e}")


def close_app(name: str):
    name_lower = name.lower().replace(".exe", "")
    running = get_running_processes()
    matches = {n: pid for n, pid in running.items() if name_lower in n}

    if not matches:
        print(f"'{name}' is not running")
        return

    if is_browser(name_lower):
        close_browser_gracefully(name_lower)
        return

    killed, failed = [], []

    for proc_name, pid in matches.items():
        try:
            proc = psutil.Process(pid)

            # Step 1: WM_CLOSE (like clicking X)
            handles = get_windows_by_name(proc_name)
            if handles:
                WM_CLOSE = 0x0010
                user32.PostMessageW(handles[0], WM_CLOSE, 0, 0)
            try:
                proc.wait(timeout=2)
                killed.append(proc_name)
                continue
            except psutil.TimeoutExpired:
                pass

            # Step 2: Alt+F4 (keyboard close)
            if handles:
                try:
                    send_alt_f4(handles[0])
                except Exception:
                    pass
            try:
                proc.wait(timeout=2)
                killed.append(proc_name)
                continue
            except psutil.TimeoutExpired:
                pass

            # Step 3: terminate() — SIGTERM
            proc.terminate()
            try:
                proc.wait(timeout=3)
                killed.append(proc_name)
                continue
            except psutil.TimeoutExpired:
                pass

            # Step 4: Last resort — ask user
            confirm = input(
                f"'{proc_name}' is not responding. Force close? (yes/no): "
            ).strip().lower()
            if confirm == "yes":
                proc.kill()
                killed.append(proc_name)
                print(f"  '{proc_name}' force closed")
            else:
                failed.append(proc_name)
                print(f"  '{proc_name}' skipped")

        except psutil.AccessDenied:
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                killed.append(proc_name)
            else:
                failed.append(proc_name)
        except psutil.NoSuchProcess:
            pass

    if killed:
        print(f"Closed: {', '.join(set(killed))}")
    if failed:
        print(f"Could not close: {', '.join(set(failed))}")


# ──────────────────────────────────────────
#  PICK APP
# ──────────────────────────────────────────

def pick_app(results: list) -> dict | None:
    if not results:
        print("No apps found")
        return None
    if len(results) == 1:
        return results[0]
    print(f"\nFound {len(results)} matches:")
    for i, app in enumerate(results, 1):
        status = " [RUNNING]" if is_running(app["name"]) else ""
        print(f"  {i}. {app['name']}{status}  ({app['size_kb']} KB)")
        print(f"     {app['path']}")
    try:
        choice = input("\nPick a number (or Enter to cancel): ").strip()
        if not choice:
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            return results[idx]
        print("Invalid choice")
    except ValueError:
        print("Invalid input")
    return None


# ──────────────────────────────────────────
#  CONSOLE
# ──────────────────────────────────────────

def show_help():
    print(f"""
============================================
          App Manager Commands
============================================
  search <name>      - Find application
  open <name>        - Open application
  close <name>       - Close application
  minimize <name>    - Minimize window
  maximize <name>    - Maximize window
  restore <name>     - Restore window size
  running <name>     - Check if app is running
  cache status       - Show cache info
  cache clean        - Remove dead entries from cache
  reindex            - Rebuild index (foreground)
  reindex bg         - Rebuild index (background)
  help               - Show this help
  exit               - Exit
============================================
Auto-update interval: every {AUTO_UPDATE_HOURS}h
App size filter: {MIN_APP_SIZE_KB} KB – {MAX_APP_SIZE_MB} MB
    """)


def show_cache_status(apps: list):
    meta = load_meta()
    last = meta.get("last_update", "never")
    print(f"\n=== Cache Status ===")
    print(f"File          : {CACHE_FILE}")
    print(f"Apps stored   : {len(apps)}")
    print(f"Last update   : {last} ({get_cache_age()})")
    print(f"Outdated      : {'Yes' if is_cache_outdated() else 'No'}")
    if CACHE_FILE.exists():
        size_kb = CACHE_FILE.stat().st_size / 1024
        print(f"Cache size    : {size_kb:.1f} KB")
