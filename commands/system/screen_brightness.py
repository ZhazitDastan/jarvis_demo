from services.system.screen_brightness import *


def main():
    """Main console loop"""
    print("Brightness Control started. Type 'help' for commands.")

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
                print(f"Current brightness: {get_brightness()}%")

            elif command == "set":
                if len(parts) < 2:
                    print("Usage: set <0-100>")
                else:
                    try:
                        level = int(parts[1])
                        set_brightness(level)
                    except ValueError:
                        print("Error: Please enter a valid number (0-100)")

            elif command == "up":
                amount = int(parts[1]) if len(parts) > 1 else 10
                increase_brightness(amount)
                print(f"Brightness: {get_brightness()}%")

            elif command == "down":
                amount = int(parts[1]) if len(parts) > 1 else 10
                decrease_brightness(amount)
                print(f"Brightness: {get_brightness()}%")

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
    print("Screen brightness")


if __name__ == "__main__":
    start()
