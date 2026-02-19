from services.app.indexer import *


def main():
    apps = build_index()
    auto_update_scheduler(apps)  # start background auto-updater
    print("\nApp Manager ready. Type 'help' for commands.")

    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if command == "exit":
                print("Exiting...")
                break

            elif command == "help":
                show_help()

            elif command == "reindex":
                if arg == "bg":
                    background_reindex(apps)
                else:
                    new = build_index(force=True)
                    apps.clear()
                    apps.extend(new)

            elif command == "cache":
                if arg == "status":
                    show_cache_status(apps)
                elif arg == "clean":
                    cleaned, removed = clean_cache(apps)
                    final = deduplicate(cleaned)
                    apps.clear()
                    apps.extend(final)
                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(final, f, ensure_ascii=False, indent=2)
                    print(f"Cache cleaned: removed {removed} dead entries, {len(final)} apps remain")
                else:
                    print("Usage: cache status | cache clean")

            elif command == "search":
                if not arg:
                    print("Usage: search <name>")
                    continue
                results = search_apps(arg, apps)
                if not results:
                    print(f"'{arg}' not found. Try 'reindex'.")
                else:
                    print(f"\nResults for '{arg}' ({len(results)} found):")
                    for app in results:
                        status = " [RUNNING]" if is_running(app["name"]) else ""
                        print(f"  • {app['name']}{status}  ({app['size_kb']} KB)")
                        print(f"    {app['path']}")

            elif command == "open":
                if not arg:
                    print("Usage: open <name>")
                    continue
                results = search_apps(arg, apps)
                if not results:
                    print(f"'{arg}' not found. Try 'reindex'.")
                    continue
                app = pick_app(results)
                if app:
                    open_app(app)

            elif command == "close":
                if not arg:
                    print("Usage: close <name>")
                    continue
                close_app(arg)

            elif command == "minimize":
                window_action(arg, SW_MINIMIZE, "minimized")

            elif command == "maximize":
                window_action(arg, SW_MAXIMIZE, "maximized")

            elif command == "restore":
                window_action(arg, SW_RESTORE, "restored")

            elif command == "running":
                if not arg:
                    print("Usage: running <name>")
                    continue
                status = "RUNNING" if is_running(arg) else "NOT running"
                print(f"'{arg}' is {status}")

            else:
                print(f"Unknown command: '{command}'. Type 'help'.")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def start():
    print("APP indexer")


if __name__ == "__main__":
    start()
