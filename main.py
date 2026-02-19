import json
from services.app.indexer import build_index, background_reindex, auto_update_scheduler
from services.app.indexer import search_apps, pick_app, open_app, close_app
from services.app.indexer import window_action, is_running, clean_cache, deduplicate
from services.app.indexer import show_cache_status, SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE, CACHE_FILE

from services.system.volume import get_volume, set_volume, mute, unmute, toggle_mute, is_muted
from services.system.screen_brightness import get_brightness, set_brightness, increase_brightness, decrease_brightness
from services.system.computer_status import shutdown, restart, sleep, lock, cancel_shutdown
from services.system.system_info import (
    get_os_info, get_cpu_info, get_ram_info, get_uptime,
    get_disk_info, get_battery_info, get_network_info, get_wifi_info,
    get_network_speed, get_usb_devices, get_audio_devices, get_top_processes,
    get_security_info, get_active_users, get_display_info, get_full_info
)


def show_help():
    print("""
============================================
              Jarvis Commands
============================================
 VOLUME:    vol get/set <n>/mute/unmute/toggle/status
 BRIGHTNESS: br get/set <n>/up [n]/down [n]/status
 POWER:     shutdown/restart/sleep/lock/cancel
 INFO:      os/cpu/ram/uptime/disk/battery
            network/wifi/speed/usb/audio
            processes/security/users/display/info
 APPS:      open/close/search/running <name>
            minimize/maximize/restore <name>
            reindex / reindex bg
            cache status / cache clean
 OTHER:     help / exit
============================================
    """)


def handle_volume(arg: str):
    parts = arg.split(maxsplit=1)
    cmd = parts[0] if parts else ""
    val = parts[1] if len(parts) > 1 else ""

    if cmd == "get":
        mute_status = " (Muted)" if is_muted() else ""
        print(f"Current volume: {get_volume()}%{mute_status}")
    elif cmd == "set":
        try:               set_volume(int(val))
        except ValueError: print("Usage: vol set <0-100>")
    elif cmd == "mute":    mute()
    elif cmd == "unmute":  unmute()
    elif cmd == "toggle":  toggle_mute()
    elif cmd == "status":  
        print(f"Volume: {get_volume()}% | {'Muted' if is_muted() else 'Unmuted'}")
    else:
        print("Usage: vol get | set <n> | mute | unmute | toggle | status")


def handle_brightness(arg: str):
    parts = arg.split(maxsplit=1)
    cmd = parts[0] if parts else ""
    val = parts[1] if len(parts) > 1 else ""

    if cmd == "get":      print(f"Current brightness: {get_brightness()}%")
    elif cmd == "set":
        try:              set_brightness(int(val))
        except ValueError: print("Usage: br set <0-100>")
    elif cmd == "up":
        increase_brightness(int(val) if val.isdigit() else 10)
        print(f"Brightness: {get_brightness()}%")
    elif cmd == "down":
        decrease_brightness(int(val) if val.isdigit() else 10)
        print(f"Brightness: {get_brightness()}%")
    elif cmd == "status": print(f"Brightness: {get_brightness()}%")
    else:
        print("Usage: br get | set <n> | up [n] | down [n] | status")


def main():
    print("Initializing Jarvis...")
    app_list = build_index()
    auto_update_scheduler(app_list)
    print("Jarvis ready. Type 'help' for commands.\n")

    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue

            parts   = user_input.split(maxsplit=1)
            command = parts[0].lower()
            arg     = parts[1].strip() if len(parts) > 1 else ""

            # ── Volume ──
            if command == "vol":
                handle_volume(arg)

            # ── Brightness ──
            elif command == "br":
                handle_brightness(arg)

            # ── Power ──
            elif command == "shutdown": shutdown()
            elif command == "restart":  restart()
            elif command == "sleep":    sleep()
            elif command == "lock":     lock()
            elif command == "cancel":   cancel_shutdown()

            # ── System Info ──
            elif command == "os":        get_os_info()
            elif command == "cpu":       get_cpu_info()
            elif command == "ram":       get_ram_info()
            elif command == "uptime":    get_uptime()
            elif command == "disk":      get_disk_info()
            elif command == "battery":   get_battery_info()
            elif command == "network":   get_network_info()
            elif command == "wifi":      get_wifi_info()
            elif command == "speed":     get_network_speed()
            elif command == "usb":       get_usb_devices()
            elif command == "audio":     get_audio_devices()
            elif command == "processes": get_top_processes()
            elif command == "security":  get_security_info()
            elif command == "users":     get_active_users()
            elif command == "display":   get_display_info()
            elif command == "info":      get_full_info()

            # ── Apps ──
            elif command == "search":
                if not arg: print("Usage: search <name>"); continue
                results = search_apps(arg, app_list)
                if not results:
                    print(f"'{arg}' not found. Try 'reindex'.")
                else:
                    for a in results:
                        status = " [RUNNING]" if is_running(a["name"]) else ""
                        print(f"  • {a['name']}{status}  ({a['size_kb']} KB)")
                        print(f"    {a['path']}")

            elif command == "open":
                if not arg: print("Usage: open <name>"); continue
                results = search_apps(arg, app_list)
                if not results: print(f"'{arg}' not found. Try 'reindex'."); continue
                app = pick_app(results)
                if app: open_app(app)

            elif command == "close":
                if not arg: print("Usage: close <name>"); continue
                close_app(arg)

            elif command == "minimize":  window_action(arg, SW_MINIMIZE, "minimized")
            elif command == "maximize":  window_action(arg, SW_MAXIMIZE, "maximized")
            elif command == "restore":   window_action(arg, SW_RESTORE,  "restored")

            elif command == "running":
                if not arg: print("Usage: running <name>"); continue
                print(f"'{arg}' is {'RUNNING' if is_running(arg) else 'NOT running'}")

            elif command == "reindex":
                if arg == "bg":
                    background_reindex(app_list)
                else:
                    new = build_index(force=True)
                    app_list.clear()
                    app_list.extend(new)

            elif command == "cache":
                if arg == "status":
                    show_cache_status(app_list)
                elif arg == "clean":
                    cleaned, removed = clean_cache(app_list)
                    final = deduplicate(cleaned)
                    app_list.clear()
                    app_list.extend(final)
                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(final, f, ensure_ascii=False, indent=2)
                    print(f"Cleaned: removed {removed} dead entries, {len(final)} apps remain")
                else:
                    print("Usage: cache status | cache clean")

            # ── Other ──
            elif command == "help":  show_help()
            elif command == "exit":  print("Goodbye!"); break
            else:
                print(f"Unknown command: '{command}'. Type 'help'.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
