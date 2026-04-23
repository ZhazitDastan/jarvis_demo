"""
ramdisk.py — копирует Vosk-модель на RAM-диск (ImDisk) для быстрой загрузки.

Требует установленного ImDisk Toolkit:
  https://sourceforge.net/projects/imdisk-toolkit/

Запускается при старте Jarvis до загрузки STT-моделей.
Если ImDisk не установлен или нет прав — тихо пропускает, используя обычный путь.
"""

import os
import shutil
import subprocess
import ctypes

_DRIVE = "R"


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _imdisk_available() -> bool:
    try:
        subprocess.run(["imdisk"], capture_output=True, timeout=3)
        return True
    except FileNotFoundError:
        return False


def _drive_exists(drive: str) -> bool:
    return os.path.isdir(f"{drive}:\\")


def _dir_size_mb(path: str) -> int:
    total = 0
    for dirpath, _, files in os.walk(path):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                pass
    return total // (1024 * 1024)


def _create_ramdisk(drive: str, size_mb: int) -> bool:
    try:
        subprocess.run(
            ["imdisk", "-a", "-s", f"{size_mb}M", "-m", f"{drive}:", "-o", "rem"],
            check=True, capture_output=True, timeout=15,
        )
        subprocess.run(
            ["format", f"{drive}:", "/fs:ntfs", "/q", "/y"],
            check=True, capture_output=True, timeout=20,
        )
        return True
    except Exception as e:
        print(f"  [!] imdisk ошибка: {e}")
        return False


def setup_vosk_ramdisk(vosk_src: str, drive: str = _DRIVE) -> str:
    """
    Копирует Vosk-модель на RAM-диск и возвращает путь к ней.
    Если RAM-диск недоступен — возвращает оригинальный путь без изменений.
    """
    if not os.path.exists(vosk_src):
        return vosk_src

    dst = os.path.join(f"{drive}:\\", "vosk-ru")

    # Модель уже лежит на RAM-диске с прошлого запуска
    if _drive_exists(drive) and os.path.exists(dst):
        print(f"  [RAM] Vosk — уже на RAM-диске {drive}:")
        return dst

    # Диска нет — пробуем создать
    if not _drive_exists(drive):
        if not _is_admin():
            print("  [~] RAM-диск: нужны права администратора — пропускаю")
            return vosk_src
        if not _imdisk_available():
            print("  [~] ImDisk не установлен — пропускаю RAM-диск")
            print("       Скачать: https://sourceforge.net/projects/imdisk-toolkit/")
            return vosk_src

        size_mb = _dir_size_mb(vosk_src) + 60  # +60 MB запас под NTFS-метаданные
        print(f"  [~] Создаю RAM-диск {drive}: ({size_mb} MB)...", end="", flush=True)
        if not _create_ramdisk(drive, size_mb):
            print(" ✗")
            return vosk_src
        print(" ✓")

    # Копируем модель на диск
    print(f"  [~] Копирую Vosk → {drive}:\\vosk-ru...", end="", flush=True)
    try:
        shutil.copytree(vosk_src, dst)
        print(" ✓")
        return dst
    except Exception as e:
        print(f" ✗ ({e})")
        return vosk_src
