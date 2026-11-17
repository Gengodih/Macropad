"""Where the app keeps its files.

Personal data (settings, log, learned music apps) lives in the user's AppData
folder, never next to the program: an update replaces the program folder and
must not touch the user's settings.
"""

import os
import sys
from pathlib import Path


def user_dir() -> Path:
    """%APPDATA%\\MacroPad on Windows, ~/.config/MacroPad elsewhere (for testing)."""
    override = os.environ.get("MACROPAD_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "MacroPad"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "MacroPad"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base


def settings_file() -> Path:
    return user_dir() / "settings.json"


def log_file() -> Path:
    return user_dir() / "macropad.log"


def learned_file() -> Path:
    return user_dir() / "learned_apps.json"


def stats_file() -> Path:
    return user_dir() / "stats.json"


def downloads_dir() -> Path:
    d = user_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def install_dir() -> Path:
    """Folder of the running program (the .exe's folder when built)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource(*parts) -> Path:
    """A file shipped with the app (firmware, icon). In the built app PyInstaller
    puts them in _internal/resources (sys._MEIPASS/resources)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", install_dir()), "resources", *parts)
    return Path(__file__).resolve().parent.joinpath("resources", *parts)


def firmware_dir() -> Path:
    return resource("firmware")
