from services.system.system_info import *


def main():
    print("System Info started. Type 'help' for commands.")

    while True:
        try:
            user_input = input("\n> ").strip().lower()
            if not user_input:
                continue

            parts = user_input.split()
            command = parts[0]

            commands = {
                "os": get_os_info,
                "cpu": get_cpu_info,
                "ram": get_ram_info,
                "uptime": get_uptime,
                "disk": get_disk_info,
                "battery": get_battery_info,
                "network": get_network_info,
                "wifi": get_wifi_info,
                "speed": get_network_speed,
                "usb": get_usb_devices,
                "audio": get_audio_devices,
                "processes": get_top_processes,
                "security": get_security_info,
                "users": get_active_users,
                "display": get_display_info,
                "info": get_full_info,
                "help": show_help,
            }

            if command == "exit":
                print("Exiting...")
                break
            elif command in commands:
                commands[command]()
            else:
                print(f"Unknown command: '{command}'. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def start():
    print("System info")


if __name__ == "__main__":
    start()
