from services.system.computer_status import *

def show_help():
    """Display available commands"""
    print("""
=============================
    Power Control Commands
=============================
  shutdown   - Shutdown the computer
  restart    - Restart the computer
  sleep      - Put computer to sleep
  lock       - Lock the screen
  cancel     - Cancel scheduled shutdown/restart
  help       - Show this help
  exit       - Exit program
=============================
    """)


def main():
    """Main console loop"""
    print("Power Control started. Type 'help' for commands.")

    while True:
        try:
            user_input = input("\n> ").strip().lower()

            if not user_input:
                continue

            command = user_input.split()[0]

            if command == "exit":
                print("Exiting...")
                break

            elif command == "help":
                show_help()

            elif command == "shutdown":
                shutdown()

            elif command == "restart":
                restart()

            elif command == "sleep":
                sleep()

            elif command == "lock":
                lock()

            elif command == "cancel":
                cancel_shutdown()

            else:
                print(f"Unknown command: '{command}'. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def start():
    print("Computer Status")


if __name__ == "__main__":
    start()
