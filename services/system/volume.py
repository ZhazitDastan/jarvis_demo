from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL


def get_volume_interface():
    """Helper: get volume interface"""
    devices = AudioUtilities.GetSpeakers()
    interface = devices._dev.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
    )
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume():
    """Get current system volume (0-100)"""
    volume = get_volume_interface()
    return round(volume.GetMasterVolumeLevelScalar() * 100)


def is_muted():
    """Check if audio is currently muted"""
    return bool(get_volume_interface().GetMute())


def set_volume(level: int):
    """Set system volume (0-100)"""
    if not 0 <= level <= 100:
        print("Error: Volume level must be between 0 and 100")
        return
    get_volume_interface().SetMasterVolumeLevelScalar(level / 100, None)
    print(f"Volume set to {level}%")


def mute():
    """Mute system audio"""
    if is_muted():
        print("Audio is already muted")
        return
    get_volume_interface().SetMute(1, None)
    print("Audio muted")


def unmute():
    """Unmute system audio"""
    if not is_muted():
        print("Audio is already unmuted")
        return
    get_volume_interface().SetMute(0, None)
    print("Audio unmuted")


def toggle_mute():
    """Toggle mute/unmute"""
    volume = get_volume_interface()
    muted = volume.GetMute()
    volume.SetMute(not muted, None)
    print(f"Audio {'muted' if not muted else 'unmuted'}")


def show_status():
    """Show current volume and mute status"""
    mute_status = "Muted" if is_muted() else "Unmuted"
    print(f"Volume: {get_volume()}% | Status: {mute_status}")


def show_help():
    """Display available commands"""
    print("""
=============================
   Volume Control Commands
=============================
  get          - Show current volume
  set <0-100>  - Set volume level
  mute         - Mute audio
  unmute       - Unmute audio
  toggle       - Toggle mute/unmute
  status       - Show volume + mute status
  help         - Show this help
  exit         - Exit program
=============================
    """)



