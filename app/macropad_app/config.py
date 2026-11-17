"""User settings: loaded from and saved to %APPDATA%\\MacroPad\\settings.json.

Anything missing, broken or out of range is replaced by its default, so a
damaged file (or one written by an older version) can never stop the app.
A file that cannot be read at all is kept as settings.broken-<time>.json.
"""

import copy
import json
import logging
import os
import re
import time
from pathlib import Path

from . import keys, paths

log = logging.getLogger("macropad.config")

LANGS = ("en", "de")
EFFECTS = ("static", "breathe", "glow")       # own light schemes (FX_* in the firmware)
BACKGROUNDS = ("aquarium", "plain")           # screen background (BG_* in the firmware)
KNOB_TARGETS = ("pc", "app")
MAX_SCHEMES = 10
BUILTIN_MODES = 6                             # Rainbow ... One colour (Off is mode 6)
MODE_OFF = 6
MODE_CUSTOM = 7                               # own scheme n = mode 7 + n
COLOUR_COUNT = 16
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_SCHEME_COLOURS = ["#7c3aed"] * keys.KEY_COUNT

DEFAULTS = {
    "schema": 1,
    "app_language": "en",
    "pad_language": "en",
    "keys": list(keys.DEFAULT_LAYOUT),
    "knob_target": "app",          # the app design: knob = music app's volume / mute
    "player": "auto",              # auto, spotify, deezer
    "lights": {
        "mode": 0,
        "brightness": 60,
        "colour": 11,
        "builtin_enabled": [True] * BUILTIN_MODES,
        "schemes": [],             # [{"name": str, "effect": str, "colours": ["#rrggbb" x 15]}]
    },
    "display": {
        "background": "aquarium",
        "fish": True,
        "brightness": 16,          # backlight level 1-16
        "music": True,             # show the music screen while a song plays
    },
    "autostart": True,
    "start_minimized": False,
    "pad_sync_pending": False,     # settings changed while the pad was not connected
    "updates": {
        "auto_check": True,
        "last_check": 0.0,
        "skip_version": "",
    },
}


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


def _pick(value, allowed, default):
    return value if value in allowed else default


def _int(value, lo, hi, default):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    value = int(value)
    return value if lo <= value <= hi else default


def _bool(value, default):
    return value if isinstance(value, bool) else default


def clean_text(text, limit) -> str:
    """Printable text without the '|' separator, at most `limit` characters."""
    if not isinstance(text, str):
        return ""
    text = "".join(ch for ch in text if ch.isprintable()).replace("|", "/").strip()
    return text[:limit]


def _scheme(raw):
    if not isinstance(raw, dict):
        return None
    name = clean_text(raw.get("name"), 15)
    if not name:
        return None
    colours = raw.get("colours")
    if not isinstance(colours, list):
        colours = []
    colours = [c.lower() if isinstance(c, str) and _HEX.match(c) else "#000000" for c in colours]
    colours = (colours + ["#000000"] * keys.KEY_COUNT)[:keys.KEY_COUNT]
    return {"name": name, "effect": _pick(raw.get("effect"), EFFECTS, "static"), "colours": colours}


def validate(raw) -> dict:
    """Any dict -> complete, valid settings (unknown keys are dropped)."""
    d = defaults()
    if not isinstance(raw, dict):
        return d
    d["app_language"] = _pick(raw.get("app_language"), LANGS, d["app_language"])
    d["pad_language"] = _pick(raw.get("pad_language"), LANGS, d["pad_language"])
    d["knob_target"] = _pick(raw.get("knob_target"), KNOB_TARGETS, d["knob_target"])
    d["player"] = _pick(raw.get("player"), ("auto", "spotify", "deezer"), d["player"])
    d["autostart"] = _bool(raw.get("autostart"), d["autostart"])
    d["start_minimized"] = _bool(raw.get("start_minimized"), d["start_minimized"])
    d["pad_sync_pending"] = _bool(raw.get("pad_sync_pending"), d["pad_sync_pending"])

    km = raw.get("keys")
    if isinstance(km, list) and len(km) == keys.KEY_COUNT:
        d["keys"] = [a if keys.is_valid(a) else keys.DEFAULT_LAYOUT[i] for i, a in enumerate(km)]

    li, dl = raw.get("lights"), d["lights"]
    if isinstance(li, dict):
        schemes = [s for s in (_scheme(x) for x in (li.get("schemes") or [])[:MAX_SCHEMES]) if s]
        dl["schemes"] = schemes
        be = li.get("builtin_enabled")
        if isinstance(be, list) and len(be) == BUILTIN_MODES and all(isinstance(x, bool) for x in be):
            dl["builtin_enabled"] = be
        dl["brightness"] = _int(li.get("brightness"), 10, 100, dl["brightness"])
        dl["colour"] = _int(li.get("colour"), 0, COLOUR_COUNT - 1, dl["colour"])
        dl["mode"] = _int(li.get("mode"), 0, MODE_CUSTOM + MAX_SCHEMES - 1, dl["mode"])
    if not mode_available(d, dl["mode"]):
        dl["mode"] = first_available_mode(d)

    di, dd = raw.get("display"), d["display"]
    if isinstance(di, dict):
        dd["background"] = _pick(di.get("background"), BACKGROUNDS, dd["background"])
        dd["fish"] = _bool(di.get("fish"), dd["fish"])
        dd["brightness"] = _int(di.get("brightness"), 1, 16, dd["brightness"])
        dd["music"] = _bool(di.get("music"), dd["music"])

    up, du = raw.get("updates"), d["updates"]
    if isinstance(up, dict):
        du["auto_check"] = _bool(up.get("auto_check"), du["auto_check"])
        lc = up.get("last_check")
        du["last_check"] = float(lc) if isinstance(lc, (int, float)) and not isinstance(lc, bool) else 0.0
        du["skip_version"] = clean_text(up.get("skip_version"), 20)
    return d


def mode_available(settings, mode) -> bool:
    li = settings["lights"]
    if mode == MODE_OFF:
        return True
    if 0 <= mode < BUILTIN_MODES:
        return li["builtin_enabled"][mode]
    n = mode - MODE_CUSTOM
    return 0 <= n < len(li["schemes"])


def first_available_mode(settings) -> int:
    for m in list(range(BUILTIN_MODES)) + [MODE_CUSTOM + i for i in range(len(settings["lights"]["schemes"]))]:
        if mode_available(settings, m):
            return m
    return MODE_OFF


def installer_language() -> str:
    """The language picked in the installer (first start only), English otherwise."""
    import sys
    if sys.platform != "win32":
        return "en"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\MacroPad") as k:
            value, _ = winreg.QueryValueEx(k, "Language")
            return "de" if str(value).lower().startswith("german") else "en"
    except OSError:
        return "en"


class Settings:
    """Holds the settings and saves them safely (write to a temp file, then swap)."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else paths.settings_file()
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            d = defaults()
            lang = installer_language()
            d["app_language"] = d["pad_language"] = lang
            return d
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except Exception as e:  # unreadable: keep a copy, start with defaults
            log.warning("Settings file unreadable (%s), starting with defaults", e)
            try:
                self.path.replace(self.path.with_name(f"settings.broken-{int(time.time())}.json"))
            except OSError:
                pass
            return defaults()
        return validate(raw)

    def save(self) -> bool:
        self.data = validate(self.data)
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError as e:
            log.error("Could not save settings: %s", e)
            return False

    def copy(self) -> dict:
        return copy.deepcopy(self.data)

    def replace(self, data: dict) -> bool:
        self.data = validate(data)
        return self.save()
