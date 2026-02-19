import screen_brightness_control as sbc


def get_brightness():
    """Get current screen brightness (0-100)"""
    brightness = sbc.get_brightness()
    # get_brightness() returns a list (for multiple monitors)
    return brightness[0]


def set_brightness(level: int):
    """Set screen brightness (0-100)"""
    if not 0 <= level <= 100:
        print("Error: Brightness level must be between 0 and 100")
        return
    sbc.set_brightness(level)
    print(f"Brightness set to {level}%")


def increase_brightness(amount: int = 10):
    """Increase brightness by given amount"""
    current = get_brightness()
    new_level = min(100, current + amount)
    set_brightness(new_level)


def decrease_brightness(amount: int = 10):
    """Decrease brightness by given amount"""
    current = get_brightness()
    new_level = max(0, current - amount)
    set_brightness(new_level)


def show_status():
    """Show current brightness"""
    print(f"Brightness: {get_brightness()}%")


def show_help():
    """Display available commands"""
    print("""
================================
  Brightness Control Commands
================================
  get            - Show current brightness
  set <0-100>    - Set brightness level
  up <amount>    - Increase brightness (default +10)
  down <amount>  - Decrease brightness (default -10)
  status         - Show brightness status
  help           - Show this help
  exit           - Exit program
================================
    """)


