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


def delete_user_data():
    """Removes %APPDATA%\\MacroPad (settings, log, downloads) and the app's
    registry key. The log file is closed first, Windows would refuse otherwise."""
    import logging
    import shutil
    from . import paths
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            h.close()
        finally:
            root.removeHandler(h)
    shutil.rmtree(paths.user_dir(), ignore_errors=True)
    if sys.platform == "win32":
        try:
            import winreg
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\MacroPad")
        except OSError:
            pass


def find_uninstaller():
    """The uninstaller Inno Setup put next to the app, or None (running from source)."""
    from . import paths
    found = sorted(paths.install_dir().glob("unins*.exe"))
    return found[-1] if found else None


def run_uninstaller(path):
    """Starts the uninstaller (it closes this app itself). Windows asks for admin
    rights if the app was installed for all users."""
    if sys.platform != "win32":
        raise OSError("uninstalling needs Windows")
    import ctypes
    rc = ctypes.windll.shell32.ShellExecuteW(None, "open", str(path), "/SILENT", None, 1)
    if rc <= 32:
        raise OSError(f"Windows error {rc}")


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
