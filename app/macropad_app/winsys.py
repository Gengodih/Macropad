"""Small Windows helpers: autostart and the app's own command line.
Everything is a quiet no-op on other systems (used for testing)."""

import logging
import os
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


# ---------------------------------------------------------------------------
#  For macros and profiles
# ---------------------------------------------------------------------------
def _user32():
    import ctypes
    return ctypes.WinDLL("user32", use_last_error=True)


def type_text(text: str) -> bool:
    """Types any text (also umlauts and emoji) into the window in front, like
    the keyboard would - independent of the keyboard layout."""
    if sys.platform != "win32" or not text:
        return False
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    KEYUP, UNICODE, VK_RETURN, VK_TAB = 0x0002, 0x0004, 0x0D, 0x09
    events = []
    for ch in text.replace("\r\n", "\n"):
        if ch in "\n\t":
            vk = VK_RETURN if ch == "\n" else VK_TAB
            for flags in (0, KEYUP):
                events.append(INPUT(type=1, ki=KEYBDINPUT(vk, 0, flags, 0, 0)))
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):            # emoji = two UTF-16 units
            unit = int.from_bytes(data[i:i + 2], "little")
            for flags in (UNICODE, UNICODE | KEYUP):
                events.append(INPUT(type=1, ki=KEYBDINPUT(0, unit, flags, 0, 0)))
    user32 = _user32()
    for i in range(0, len(events), 40):             # in small parts, so slow programs keep up
        part = events[i:i + 40]
        arr = (INPUT * len(part))(*part)
        user32.SendInput(len(part), arr, ctypes.sizeof(INPUT))
    return True


def _exe_of_window(hwnd) -> str:
    import ctypes
    from ctypes import wintypes
    user32 = _user32()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = kernel32.OpenProcess(0x1000, False, pid.value)     # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def foreground_program() -> str:
    """Exe name of the window in front, e.g. 'photoshop.exe' ('' if unknown)."""
    if sys.platform != "win32":
        return ""
    try:
        user32 = _user32()
        user32.GetForegroundWindow.restype = __import__("ctypes").c_void_p
        hwnd = user32.GetForegroundWindow()
        return _exe_of_window(hwnd) if hwnd else ""
    except Exception:
        return ""


def screen_locked() -> bool:
    """True while Windows shows the lock screen."""
    if sys.platform != "win32":
        return False
    try:
        if foreground_program() == "lockapp.exe":
            return True
        user32 = _user32()
        user32.OpenInputDesktop.restype = __import__("ctypes").c_void_p
        desk = user32.OpenInputDesktop(0, False, 0x0100)     # DESKTOP_SWITCHDESKTOP
        if not desk:
            return True                                       # the secure desktop is active
        user32.CloseDesktop(__import__("ctypes").c_void_p(desk))
        return False
    except Exception:
        return False


def running_programs() -> list[str]:
    """Exe names of the programs with a visible window (for choosing a profile's programs)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    user32 = _user32()
    found = set()
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        try:
            if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                exe = _exe_of_window(hwnd)
                if exe:
                    found.add(exe)
        except Exception:
            pass
        return True
    try:
        user32.EnumWindows(proto(cb), 0)
    except Exception:
        return []
    own = os.path.basename(sys.executable).lower()
    skip = {own, "explorer.exe", "textinputhost.exe", "applicationframehost.exe", "searchhost.exe",
            "shellexperiencehost.exe", "startmenuexperiencehost.exe", "lockapp.exe", "systemsettings.exe"}
    return sorted(found - skip)


def open_target(target: str) -> bool:
    """Opens a program, file, folder or web address."""
    import webbrowser
    target = (target or "").strip()
    if not target:
        return False
    try:
        low = target.lower()
        if low.startswith(("http://", "https://", "www.")):
            webbrowser.open(target if "://" in target else "https://" + target)
        elif sys.platform == "win32":
            os.startfile(target)                 # noqa: S606 - the user's own choice
        else:
            import subprocess
            subprocess.Popen(["xdg-open", target])
        return True
    except Exception as e:
        log.warning("Could not open %s: %s", target, e)
        return False
