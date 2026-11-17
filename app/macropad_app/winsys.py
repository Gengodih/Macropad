"""Small Windows helpers: autostart and the app's own command line.
Everything is a quiet no-op on other systems (used for testing)."""

import logging
import sys

log = logging.getLogger("macropad.win")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "MacroPad"


def app_command(minimized=True) -> str:
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = f'"{pyw}" -m macropad_app'
    return cmd + (" --minimized" if minimized else "")


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE)
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> bool:
    """Start with Windows (current user only, no admin rights needed)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, app_command(True))
            else:
                try:
                    winreg.DeleteValue(k, VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        log.info("Could not change autostart: %s", e)
        return False
