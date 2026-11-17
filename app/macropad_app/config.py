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
# Animated screen backgrounds, in catalog order. PAD_BACKGROUND = their number
# on the pad (BG_* in the firmware); 1 there is "plain" = animation switched off.
BACKGROUNDS = ("aquarium", "synthwave", "lava", "space", "fire", "matrix", "rain", "seasons",
               "clock", "stats", "timer", "picture")
WIDGETS = ("clock", "stats", "timer", "picture")      # shown as their own group in the catalog
PAD_BACKGROUND = {"aquarium": 0, "synthwave": 2, "lava": 3, "space": 4, "fire": 5, "matrix": 6,
                  "rain": 7, "seasons": 8, "clock": 9, "stats": 10, "timer": 11, "picture": 12}
MIN_PROTO = {"clock": 4, "stats": 4, "timer": 4, "picture": 4}   # older pads show the aquarium instead
PAD_PLAIN = 1
SEASONS = ("auto", "winter", "spring", "summer", "autumn")
# The options of each background and their defaults (the same order as the
# option bits on the pad, see protocol.background_options)
BACKGROUND_OPTIONS = {
    "aquarium": {"fish": True},
    "synthwave": {"beat": True},
    "lava": {"light_colour": False},
    "space": {"rocket": True},
    "fire": {"beat": True, "fox": True},
    "matrix": {"key_names": True},
    "rain": {"storm": True},
    "seasons": {"season": "auto"},
    "clock": {"seconds": True, "h12": False},
    "stats": {"graph": True},
    "timer": {"focus": 25, "break": 5, "long": 15},   # minutes
    "picture": {"fit": False},                          # False = fill the screen (cut edges), True = whole picture
}
TIMER_LIMITS = {"focus": (1, 120), "break": (1, 60), "long": (1, 60)}
KNOB_TARGETS = ("pc", "app")
MAX_SCHEMES = 10
BUILTIN_MODES = 6                             # Rainbow ... One colour (Off is mode 6)
MODE_OFF = 6
MODE_CUSTOM = 7                               # own scheme n = mode 7 + n
COLOUR_COUNT = 16
MAX_MACROS = 30
MAX_STEPS = 40
MAX_PROFILES = 10
STEP_TYPES = ("keys", "text", "open", "delay")
IDLE_CHOICES = (0, 5, 10, 15, 30, 60)          # minutes without a key until the pad sleeps (0 = never)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_SCHEME_COLOURS = ["#7c3aed"] * keys.KEY_COUNT

DEFAULTS = {
    "schema": 1,
    "app_language": "en",
    "pad_language": "en",
    "keys": list(keys.DEFAULT_LAYOUT),
    "keys2": ["none"] * keys.KEY_COUNT,   # layer 2 (while a "layer" key is held)
    # own macros: id -> {"name": str, "steps": [{"type": "keys", "action": id} |
    #   {"type": "text", "text": str} | {"type": "open", "target": str} | {"type": "delay", "ms": int}]}
    "macros": {},
    # tap / hold / double-tap keys: id -> {"name": str, "tap": id, "hold": id, "double": id}
    "multi": {},
    # profiles: the keys change by themselves while one of these programs is in front
    "profiles": [],                # [{"name": str, "programs": ["photoshop.exe"], "keys": [15 ids]}]
    "owner_name": "",              # for the pad's welcome
    "sleep": {"when_locked": True, "idle_minutes": 0},
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
        "animation": True,         # animated background on/off (off = the plain screen)
        "background": "aquarium",
        "options": copy.deepcopy(BACKGROUND_OPTIONS),
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


def clean_program(name) -> str:
    """'C:\\Apps\\Photoshop.EXE' or 'photoshop' -> 'photoshop.exe'."""
    if not isinstance(name, str):
        return ""
    name = name.replace("/", "\\").rsplit("\\", 1)[-1].strip().lower()
    if name and "." not in name:
        name += ".exe"
    return name if re.match(r"^[\w .()+\-]{1,80}$", name) else ""


def action_ok(settings, aid) -> bool:
    """Valid action that also exists (a macro or tap/hold key must be in the settings)."""
    if not keys.is_valid(aid):
        return False
    if keys.is_ref(aid):
        kind, rid = aid.split(":", 1)
        return rid in settings.get("macros" if kind == "macro" else "multi", {})
    return True


def action_names(settings) -> dict:
    """{action id: name} for the macros and tap/hold keys (for labels)."""
    names = {f"macro:{rid}": m["name"] for rid, m in settings.get("macros", {}).items()}
    names.update({f"multi:{rid}": m["name"] for rid, m in settings.get("multi", {}).items()})
    return names


def new_ref_id(settings, kind) -> str:
    used = settings.get("macros" if kind == "macro" else "multi", {})
    n = 1
    while f"{kind[0]}{n}" in used:
        n += 1
    return f"{kind[0]}{n}"


def _macro(rid, raw):
    if not keys.valid_ref_id(rid) or not isinstance(raw, dict):
        return None
    name = clean_text(raw.get("name"), 23)
    steps = []
    for st in (raw.get("steps") if isinstance(raw.get("steps"), list) else [])[:MAX_STEPS]:
        if not isinstance(st, dict):
            continue
        t = st.get("type")
        if t == "keys" and keys.is_pad_action(st.get("action")):
            steps.append({"type": "keys", "action": st["action"]})
        elif t == "text" and isinstance(st.get("text"), str) and st["text"]:
            steps.append({"type": "text", "text": st["text"][:2000]})
        elif t == "open" and isinstance(st.get("target"), str) and st["target"].strip():
            steps.append({"type": "open", "target": st["target"].strip()[:500]})
        elif t == "delay":
            steps.append({"type": "delay", "ms": _int(st.get("ms"), 10, 10000, 500)})
    return {"name": name, "steps": steps} if name else None


def multi_action_ok(settings, aid) -> bool:
    """What a tap / hold / double tap may do: a pad key, a macro, the microphone or nothing."""
    return aid == "none" or keys.is_pad_action(aid) or aid.startswith("app:") or (
        aid.startswith("macro:") and action_ok(settings, aid))


def _multi(rid, raw, settings):
    if not keys.valid_ref_id(rid) or not isinstance(raw, dict):
        return None
    name = clean_text(raw.get("name"), 23)
    out = {"name": name}
    for k in ("tap", "hold", "double"):
        a = raw.get(k, "none")
        out[k] = a if isinstance(a, str) and multi_action_ok(settings, a) else "none"
    return out if name else None


def active_profile(settings, program: str):
    """Index of the profile for this program (lower-case exe name), or None."""
    for i, p in enumerate(settings.get("profiles", [])):
        if program and program in p["programs"]:
            return i
    return None


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

    # macros and tap/hold keys first: the key lists may point at them
    macros = raw.get("macros") if isinstance(raw.get("macros"), dict) else {}
    for rid, m in list(macros.items())[:MAX_MACROS]:
        m = _macro(rid, m)
        if m:
            d["macros"][rid] = m
    multi = raw.get("multi") if isinstance(raw.get("multi"), dict) else {}
    for rid, m in list(multi.items())[:MAX_MACROS]:
        m = _multi(rid, m, d)
        if m:
            d["multi"][rid] = m

    def layout(value, fallback, allow_layer=True):
        if not (isinstance(value, list) and len(value) == keys.KEY_COUNT):
            return list(fallback)
        return [a if action_ok(d, a) and (allow_layer or a not in ("layer", "lights", "fun2")) else fallback[i]
                for i, a in enumerate(value)]

    d["keys"] = layout(raw.get("keys"), keys.DEFAULT_LAYOUT)
    d["keys2"] = layout(raw.get("keys2"), d["keys2"], allow_layer=False)
    profiles = raw.get("profiles") if isinstance(raw.get("profiles"), list) else []
    for p in profiles[:MAX_PROFILES]:
        if not isinstance(p, dict):
            continue
        name = clean_text(p.get("name"), 30)
        progs = p.get("programs") if isinstance(p.get("programs"), list) else []
        progs = list(dict.fromkeys(x for x in (clean_program(x) for x in progs[:20]) if x))
        if name:
            d["profiles"].append({"name": name, "programs": progs, "keys": layout(p.get("keys"), d["keys"])})
    d["owner_name"] = clean_text(raw.get("owner_name"), 20)
    sl, ds = raw.get("sleep"), d["sleep"]
    if isinstance(sl, dict):
        ds["when_locked"] = _bool(sl.get("when_locked"), ds["when_locked"])
        ds["idle_minutes"] = _pick(sl.get("idle_minutes"), IDLE_CHOICES, ds["idle_minutes"])

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
        bg = di.get("background")
        if "animation" not in di and bg == "plain":       # settings from 1.2 and older
            dd["animation"] = False
        dd["animation"] = _bool(di.get("animation"), dd["animation"])
        dd["background"] = _pick(bg, BACKGROUNDS, dd["background"])
        opts = di.get("options") if isinstance(di.get("options"), dict) else {}
        if "fish" in di and "options" not in di:          # 1.2 and older: fish lived here
            opts = {"aquarium": {"fish": di.get("fish")}}
        for name, defaults_ in BACKGROUND_OPTIONS.items():
            given = opts.get(name) if isinstance(opts.get(name), dict) else {}
            for key, default in defaults_.items():
                if key == "season":
                    dd["options"][name][key] = _pick(given.get(key), SEASONS, default)
                elif key in TIMER_LIMITS:
                    dd["options"][name][key] = _int(given.get(key), *TIMER_LIMITS[key], default)
                else:
                    dd["options"][name][key] = _bool(given.get(key), default)
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
