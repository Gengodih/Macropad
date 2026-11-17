"""Everything a key on the pad can do, and how it is sent to the pad.

An action is stored in the settings as a short id string:

    none                    does nothing
    lights                  light key (tap = next light mode, hold + knob = brightness)
    fun2                    colour key (tap = F23, hold + knob = light colour)
    key:F13                 one keyboard key
    media:play_pause        a media key
    sc:copy                 a ready-made shortcut (Ctrl+C ...)
    combo:3:K               an own shortcut: modifier bits + key name (3 = Ctrl+Shift)

The pad gets (type, code, modifiers, label) for each key - see protocol.py.
"""

from dataclasses import dataclass

# Pad action types (ActionType in the firmware)
T_KEY, T_MEDIA, T_LIGHTS, T_COLOUR, T_NONE = 0, 1, 2, 3, 4

# Modifier bits (same as the firmware)
CTRL, SHIFT, ALT, WIN = 0x01, 0x02, 0x04, 0x08
MOD_NAMES = {"en": [(CTRL, "Ctrl"), (SHIFT, "Shift"), (ALT, "Alt"), (WIN, "Win")],
             "de": [(CTRL, "Strg"), (SHIFT, "Shift"), (ALT, "Alt"), (WIN, "Win")]}


@dataclass(frozen=True)
class KeyName:
    name: str        # id part, e.g. "F13", "A", "ENTER"
    code: int        # HID usage (keyboard page)
    en: str
    de: str


def _k(name, code, en=None, de=None):
    return KeyName(name, code, en or name, de or en or name)


# Keyboard keys, grouped as they are shown in the app
KEY_GROUPS = {
    "fkeys_high": [_k(f"F{n}", 0x68 + n - 13) for n in range(13, 25)],
    "fkeys": [_k(f"F{n}", 0x3A + n - 1) for n in range(1, 13)],
    "letters": [_k(chr(c), 0x04 + c - ord("A")) for c in range(ord("A"), ord("Z") + 1)],
    "digits": [_k(str(d), 0x1E + (d - 1 if d else 9)) for d in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)],
    "editing": [
        _k("ENTER", 0x28, "Enter", "Enter"), _k("ESC", 0x29, "Esc", "Esc"),
        _k("BACKSPACE", 0x2A, "Backspace", "Rücktaste"), _k("TAB", 0x2B, "Tab", "Tab"),
        _k("SPACE", 0x2C, "Space", "Leertaste"), _k("INSERT", 0x49, "Insert", "Einfg"),
        _k("DELETE", 0x4C, "Delete", "Entf"), _k("CAPSLOCK", 0x39, "Caps Lock", "Feststelltaste"),
        _k("MENU", 0x65, "Menu key", "Menütaste"),
    ],
    "navigation": [
        _k("UP", 0x52, "Arrow up", "Pfeil hoch"), _k("DOWN", 0x51, "Arrow down", "Pfeil runter"),
        _k("LEFT", 0x50, "Arrow left", "Pfeil links"), _k("RIGHT", 0x4F, "Arrow right", "Pfeil rechts"),
        _k("HOME", 0x4A, "Home", "Pos1"), _k("END", 0x4D, "End", "Ende"),
        _k("PAGEUP", 0x4B, "Page up", "Bild auf"), _k("PAGEDOWN", 0x4E, "Page down", "Bild ab"),
    ],
    "system": [
        _k("PRINTSCREEN", 0x46, "Print Screen", "Druck"), _k("SCROLLLOCK", 0x47, "Scroll Lock", "Rollen"),
        _k("PAUSE", 0x48, "Pause", "Pause"), _k("NUMLOCK", 0x53, "Num Lock", "Num"),
    ],
    "symbols": [
        _k("MINUS", 0x2D, "-", "ß"), _k("EQUAL", 0x2E, "=", "´"),
        _k("LBRACKET", 0x2F, "[", "Ü"), _k("RBRACKET", 0x30, "]", "+"),
        _k("BACKSLASH", 0x31, "\\", "#"), _k("SEMICOLON", 0x33, ";", "Ö"),
        _k("QUOTE", 0x34, "'", "Ä"), _k("GRAVE", 0x35, "`", "^"),
        _k("COMMA", 0x36, ","), _k("PERIOD", 0x37, "."), _k("SLASH", 0x38, "/", "-"),
    ],
    "numpad": [_k(f"NUM{d}", 0x62 if d == 0 else 0x59 + d - 1, f"Num {d}") for d in range(10)] + [
        _k("NUMDIV", 0x54, "Num /"), _k("NUMMUL", 0x55, "Num *"), _k("NUMSUB", 0x56, "Num -"),
        _k("NUMADD", 0x57, "Num +"), _k("NUMENTER", 0x58, "Num Enter"), _k("NUMDOT", 0x63, "Num ,"),
    ],
}
KEYS_BY_NAME = {k.name: k for group in KEY_GROUPS.values() for k in group}
KEYS_BY_CODE = {k.code: k for k in KEYS_BY_NAME.values()}

# Media keys: (consumer code, English, German)
MEDIA = {
    "play_pause": (0xCD, "Play / Pause", "Play / Pause"),
    "next": (0xB5, "Next", "Weiter"),
    "prev": (0xB6, "Previous", "Zurück"),
    "stop": (0xB7, "Stop", "Stopp"),
    "mute": (0xE2, "Mute", "Stumm"),
    "vol_up": (0xE9, "Volume +", "Lauter"),
    "vol_down": (0xEA, "Volume -", "Leiser"),
    "calculator": (0x192, "Calculator", "Rechner"),
    "browser": (0x223, "Browser home", "Browser"),
}

# Ready-made shortcuts: (modifiers, key name, English, German)
SHORTCUTS = {
    "copy": (CTRL, "C", "Copy", "Kopieren"),
    "paste": (CTRL, "V", "Paste", "Einfügen"),
    "cut": (CTRL, "X", "Cut", "Ausschneiden"),
    "undo": (CTRL, "Z", "Undo", "Rückgängig"),
    "redo": (CTRL, "Y", "Redo", "Wiederholen"),
    "select_all": (CTRL, "A", "Select all", "Alles markieren"),
    "save": (CTRL, "S", "Save", "Speichern"),
    "find": (CTRL, "F", "Find", "Suchen"),
    "snip": (WIN | SHIFT, "S", "Snipping Tool", "Snipping Tool"),
    "clipboard": (WIN, "V", "Clipboard history", "Zwischenablage"),
    "emoji": (WIN, "PERIOD", "Emoji panel", "Emojis"),
    "task_manager": (CTRL | SHIFT, "ESC", "Task Manager", "Task-Manager"),
    "lock": (WIN, "L", "Lock PC", "PC sperren"),
    "desktop": (WIN, "D", "Show desktop", "Desktop anzeigen"),
    "explorer": (WIN, "E", "File Explorer", "Explorer"),
    "settings": (WIN, "I", "Windows settings", "Einstellungen"),
    "run": (WIN, "R", "Run", "Ausführen"),
    "close_window": (ALT, "F4", "Close window", "Fenster schließen"),
    "switch_window": (ALT, "TAB", "Switch window", "Fenster wechseln"),
    "new_tab": (CTRL, "T", "New tab", "Neuer Tab"),
    "close_tab": (CTRL, "W", "Close tab", "Tab schließen"),
    "reopen_tab": (CTRL | SHIFT, "T", "Reopen tab", "Tab wiederherstellen"),
    "desktop_next": (CTRL | WIN, "RIGHT", "Next desktop", "Nächster Desktop"),
    "desktop_prev": (CTRL | WIN, "LEFT", "Previous desktop", "Vorheriger Desktop"),
}

SPECIAL = {
    "none": ("Nothing", "Nichts"),
    "lights": ("Light key", "Licht-Taste"),
    "fun2": ("Fun 2 (colour key)", "Fun 2 (Farb-Taste)"),
}

# Default layout (key 0-14, row by row), as in the app design:
#   F13  F14  F15  F16  F17
#   F18  F19  F20  F21  F22
#   Prev Play Next Fun2 Lights
DEFAULT_LAYOUT = (
    ["key:F13", "key:F14", "key:F15", "key:F16", "key:F17",
     "key:F18", "key:F19", "key:F20", "key:F21", "key:F22",
     "media:prev", "media:play_pause", "media:next", "fun2", "lights"]
)
KEY_COUNT = 15
LIGHTS_KEY, FUN2_KEY = 14, 13          # these fall back to their job when the app is off
FUN2_TAP = "F23"


@dataclass(frozen=True)
class PadAction:
    type: int
    code: int
    mods: int
    label: str


def mods_text(mods: int, lang: str = "en") -> str:
    return "+".join(name for bit, name in MOD_NAMES.get(lang, MOD_NAMES["en"]) if mods & bit)


def combo_id(mods: int, key_name: str) -> str:
    return f"combo:{int(mods)}:{key_name}"


def is_valid(action_id) -> bool:
    try:
        resolve(action_id)
        return True
    except (ValueError, TypeError, KeyError):
        return False


def label(action_id: str, lang: str = "en") -> str:
    """Name of an action for the app and the pad's screen."""
    de = lang == "de"
    kind, _, rest = str(action_id).partition(":")
    if kind in SPECIAL and not rest:
        return SPECIAL[kind][1 if de else 0]
    if kind == "key":
        k = KEYS_BY_NAME[rest]
        return k.de if de else k.en
    if kind == "media":
        return MEDIA[rest][2 if de else 1]
    if kind == "sc":
        return SHORTCUTS[rest][3 if de else 2]
    if kind == "combo":
        mods, key = _parse_combo(rest)
        k = KEYS_BY_NAME[key]
        name = k.de if de else k.en
        prefix = mods_text(mods, lang)
        return f"{prefix}+{name}" if prefix else name
    raise ValueError(f"unknown action {action_id!r}")


def shortcut_text(action_id: str, lang: str = "en") -> str:
    """The keys behind an action, e.g. 'Ctrl+C' (empty if it is not a key combination)."""
    kind, _, rest = str(action_id).partition(":")
    if kind == "sc":
        mods, key, *_ = SHORTCUTS[rest]
        k = KEYS_BY_NAME[key]
        return f"{mods_text(mods, lang)}+{k.de if lang == 'de' else k.en}"
    if kind == "fun2":
        return FUN2_TAP
    return ""


def _parse_combo(rest: str):
    mods_s, _, key = rest.partition(":")
    mods = int(mods_s)
    if not 0 <= mods <= 0x0F or key not in KEYS_BY_NAME:
        raise ValueError(f"bad combo {rest!r}")
    return mods, key


def resolve(action_id: str, lang: str = "en") -> PadAction:
    """Action id -> what the pad needs. Raises ValueError for unknown ids."""
    if not isinstance(action_id, str):
        raise TypeError("action id must be text")
    kind, _, rest = action_id.partition(":")
    text = label(action_id, lang)
    if kind == "none" and not rest:
        return PadAction(T_NONE, 0, 0, "")
    if kind == "lights" and not rest:
        return PadAction(T_LIGHTS, 0, 0, text)
    if kind == "fun2" and not rest:
        return PadAction(T_COLOUR, KEYS_BY_NAME[FUN2_TAP].code, 0, f"Fun 2 ({FUN2_TAP})")
    if kind == "key":
        return PadAction(T_KEY, KEYS_BY_NAME[rest].code, 0, text)
    if kind == "media":
        return PadAction(T_MEDIA, MEDIA[rest][0], 0, text)
    if kind == "sc":
        mods, key, *_ = SHORTCUTS[rest]
        return PadAction(T_KEY, KEYS_BY_NAME[key].code, mods, text)
    if kind == "combo":
        mods, key = _parse_combo(rest)
        return PadAction(T_KEY, KEYS_BY_NAME[key].code, mods, text)
    raise ValueError(f"unknown action {action_id!r}")


def short_label(action_id: str, lang: str = "en") -> str:
    """Very short text for the key buttons in the app (fits on a key cap)."""
    kind, _, rest = str(action_id).partition(":")
    if kind == "none":
        return "—"
    if kind == "lights":
        return "\U0001F4A1"
    if kind == "fun2":
        return "Fun 2"
    if kind == "media":
        return {"play_pause": "⏯", "next": "⏭", "prev": "⏮", "stop": "⏹",
                "mute": "\U0001F507", "vol_up": "\U0001F50A", "vol_down": "\U0001F509"}.get(rest, label(action_id, lang))
    return label(action_id, lang)
