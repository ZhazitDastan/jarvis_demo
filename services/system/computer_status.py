import os
import platform
import subprocess


def shutdown():
    """Shutdown the computer"""
    confirm = input("Are you sure you want to shutdown? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Shutdown cancelled")
        return
    print("Shutting down...")
    if platform.system() == "Windows":
        os.system("shutdown /s /t 5")
    else:
        os.system("shutdown -h now")


def restart():
    """Restart the computer"""
    confirm = input("Are you sure you want to restart? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Restart cancelled")
        return
    print("Restarting...")
    if platform.system() == "Windows":
        os.system("shutdown /r /t 5")
    else:
        os.system("reboot")


def sleep():
    """Put the computer to sleep"""
    print("Going to sleep...")
    if platform.system() == "Windows":
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    else:
        os.system("systemctl suspend")


def lock():
    """Lock the screen"""
    print("Locking screen...")
    if platform.system() == "Windows":
        subprocess.call("rundll32.exe user32.dll,LockWorkStation")
    else:
        os.system("gnome-screensaver-command -l")


def cancel_shutdown():
    """Cancel scheduled shutdown or restart"""
    if platform.system() == "Windows":
        os.system("shutdown /a")
        print("Shutdown/restart cancelled")
    else:
        os.system("shutdown -c")
        print("Shutdown/restart cancelled")



