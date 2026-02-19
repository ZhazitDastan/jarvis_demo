from services.system.volume import *


def main():
    """Main console loop"""
    print("Volume Control started. Type 'help' for commands.")

    while True:
        try:
            user_input = input("\n> ").strip().lower()

            if not user_input:
                continue

            parts = user_input.split()
            command = parts[0]

            if command == "exit":
                print("Exiting...")
                break

            elif command == "help":
                show_help()

            elif command == "get":
                mute_status = " (Muted)" if is_muted() else ""
                print(f"Current volume: {get_volume()}%")

            elif command == "set":
                if len(parts) < 2:
                    print("Usage: set <0-100>")
                else:
                    try:
                        level = int(parts[1])
                        set_volume(level)
                    except ValueError:
                        print("Error: Please enter a valid number (0-100)")

            elif command == "mute":
                mute()

            elif command == "unmute":
                unmute()

            elif command == "toggle":
                toggle_mute()

            elif command == "status":
                show_status()

            else:
                print(f"Unknown command: '{command}'. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def start():
    print("volume")


if __name__ == "__main__":
    start()
