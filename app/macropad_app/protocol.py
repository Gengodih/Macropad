"""Messages between the app and the pad (one text line each, see the firmware).

app -> pad (settings, take effect at once, "W" keeps them in the pad's flash):
    K|key|type|code|mods|label      G|lang      D|bg|fish|level|music
    LE|mask  LS|slot|effect|name|RRGGBB,...  LP|colour  LB|percent  LM|mode
    W   ?   !BOOT
pad -> app:
    I|version|protocol|lang|mode|light%|colour      A|W|accepted|rejected
    A|E|start of a message it did not understand     X|mode|light%|colour
plus the music messages of the helper (S, T, L, C / V, M, P, N, B, R).
"""

import unicodedata
from dataclasses import dataclass

from . import config, keys

PROTO_VERSION = 1

# German letters in the pad's screen font (code page 437)
_CP437 = {"ä": 0x84, "ö": 0x94, "ü": 0x81, "Ä": 0x8E, "Ö": 0x99,
          "Ü": 0x9A, "ß": 0xE1}
_ASCII_FIX = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                            "–": "-", "—": "-", "|": "/", "´": "'"})


def pad_text(text: str, limit: int) -> bytes:
    """Text for the pad's screen: ASCII plus the German letters it can show."""
    out = bytearray()
    for ch in (text or "").translate(_ASCII_FIX):
        if ch in _CP437:
            out.append(_CP437[ch])
        elif 32 <= ord(ch) < 127:
            out.append(ord(ch))
        else:
            out += unicodedata.normalize("NFKD", ch).encode("ascii", "ignore")
        if len(out) >= limit:
            break
    return bytes(out[:limit])


def _line(*parts) -> bytes:
    out = bytearray()
    for i, p in enumerate(parts):
        if i:
            out += b"|"
        out += p if isinstance(p, (bytes, bytearray)) else str(p).encode("ascii")
    return bytes(out) + b"\n"


def _pad_action(index, action_id, lang, names, proto):
    a = keys.resolve(action_id, lang, names)
    if proto < 3 and a.type in (keys.T_APP, keys.T_LAYER):
        # older firmware does not know app keys / layers: the default job instead
        a = keys.resolve(keys.DEFAULT_LAYOUT[index], lang)
    return a


def key_line(index: int, action_id: str, lang: str, names: dict | None = None, proto: int = 3,
             kind: str = "K") -> bytes:
    """K = the keys (saved), O = profile of the program in front (not saved)."""
    a = _pad_action(index, action_id, lang, names, proto)
    return _line(kind, index, a.type, a.code, a.mods, pad_text(a.label, 23))


def overlay_lines(settings: dict, profile_index) -> list[bytes]:
    """The keys a profile changes (O|...), after O|- which clears the last one."""
    lines = [b"O|-\n"]
    if profile_index is None or not 0 <= profile_index < len(settings["profiles"]):
        return lines
    lang, names = settings["pad_language"], config.action_names(settings)
    for i, aid in enumerate(settings["profiles"][profile_index]["keys"]):
        if aid != settings["keys"][i]:
            lines.append(key_line(i, aid, lang, names, kind="O"))
    return lines


def tap_line(action_id: str) -> bytes:
    """KS|type|code|mods - the pad types this key for the app (macros, tap/hold)."""
    a = keys.resolve(action_id)
    return _line("KS", a.type, a.code, a.mods)


def highlight_line(index: int, rgb: str | None) -> bytes:
    """H|key|RRGGBB = this key's light (from the app), None = back to normal."""
    return _line("H", index, rgb.lstrip("#").upper() if rgb else "-")


CLEAR_HIGHLIGHTS = b"H|-\n"


def locked_line(locked: bool) -> bytes:
    return _line("SL", int(bool(locked)))


def parse_press(line: str):
    """P|key|down|layer2|app -> (key, down, layer2, app) or None."""
    p = line.split("|")
    if len(p) != 5 or p[0] != "P":
        return None
    try:
        key, down, layer2, app = (int(x) for x in p[1:])
    except ValueError:
        return None
    if not 0 <= key < keys.KEY_COUNT:
        return None
    return key, bool(down), bool(layer2), bool(app)


def language_line(lang: str) -> bytes:
    return _line("G", 1 if lang == "de" else 0)


def background_options(name: str, options: dict) -> int:
    """The option bits of one background, as the pad's Backgrounds.h reads them."""
    o = options.get(name, {})
    if name == "seasons":
        return config.SEASONS.index(o.get("season", "auto")) << 1
    if name == "fire":
        return int(bool(o.get("beat"))) | int(bool(o.get("fox"))) << 1
    if name == "aquarium":
        return int(bool(o.get("fish", True)))
    if name == "clock":
        return int(bool(o.get("seconds", True))) | int(bool(o.get("h12"))) << 1
    if name in ("timer", "picture"):
        return 0
    first = next(iter(config.BACKGROUND_OPTIONS[name]))
    return int(bool(o.get(first)))


def display_line(display: dict, proto: int = 3) -> bytes:
    """D|background|fish|brightness|music|options. Firmware with settings
    protocol 1 only knows the aquarium and "plain" (and five fields)."""
    name = display["background"]
    bg = config.PAD_BACKGROUND[name] if display["animation"] else config.PAD_PLAIN
    fish = int(bool(display["options"]["aquarium"]["fish"]))
    if display["animation"] and proto < config.MIN_PROTO.get(name, 2):
        bg = 0                                 # this pad does not know it yet: the aquarium
    if proto < 2:
        if bg not in (0, config.PAD_PLAIN):
            bg = 0
        return _line("D", bg, fish, display["brightness"], int(display["music"]))
    return _line("D", bg, fish, display["brightness"], int(display["music"]),
                 background_options(name, display["options"]))


def month_line(month: int, local_epoch: int | None = None) -> bytes:
    """Z|month[|local time] - the date for "Seasons" (protocol 2) and the clock (protocol 4)."""
    if local_epoch is None:
        return _line("Z", max(1, min(12, int(month))))
    return _line("Z", max(1, min(12, int(month))), int(local_epoch))


def local_epoch(t: float | None = None) -> int:
    """Seconds since 1970 in local time (what the pad's clock shows)."""
    import time
    t = time.time() if t is None else t
    lt = time.localtime(t)
    return int(t) + (lt.tm_gmtoff or 0)


def stats_line(cpu, ram, gpu, gpu_temp) -> bytes:
    """Q|cpu|ram|gpu|gpu temperature, whole numbers, -1 = unknown."""
    def v(x, hi):
        return -1 if x is None or x < 0 else max(0, min(hi, int(round(x))))
    return _line("Q", v(cpu, 100), v(ram, 100), v(gpu, 100), v(gpu_temp, 150))


def timer_line(left, total, phase, round_, paused) -> bytes:
    """U|seconds left|total|phase|round|paused - the focus timer (phase 0 = off)."""
    return _line("U", max(0, int(round(left))), max(0, int(round(total))), int(phase), int(round_), int(bool(paused)))


def scheme_line(slot: int, scheme: dict | None) -> bytes:
    if not scheme:
        return _line("LS", slot, 0, "", "")
    colours = ",".join(c.lstrip("#").upper() for c in scheme["colours"])
    return _line("LS", slot, config.EFFECTS.index(scheme["effect"]), pad_text(scheme["name"], 15), colours)


def light_lines(lights: dict) -> list[bytes]:
    mask = sum(1 << i for i, on in enumerate(lights["builtin_enabled"]) if on)
    lines = [_line("LE", mask)]
    for slot in range(config.MAX_SCHEMES):
        scheme = lights["schemes"][slot] if slot < len(lights["schemes"]) else None
        lines.append(scheme_line(slot, scheme))
    lines += [_line("LP", lights["colour"]), _line("LB", lights["brightness"]), _line("LM", lights["mode"])]
    return lines


def settings_lines(settings: dict, proto: int = 3) -> list[bytes]:
    """Every settings message for the pad, in a safe order (the light mode last,
    because it may point at a scheme sent just before). proto: the pad's
    settings protocol (from its I| answer)."""
    settings = config.validate(settings)
    lang = settings["pad_language"]
    names = config.action_names(settings)
    lines = [language_line(lang)]
    lines += [key_line(i, a, lang, names, proto) for i, a in enumerate(settings["keys"])]
    if proto >= 3:
        lines.append(_line("N", pad_text(settings["owner_name"], 20)))
        lines.append(_line("TO", settings["sleep"]["idle_minutes"]))
    lines.append(display_line(settings["display"], proto))
    lines += light_lines(settings["lights"])
    return lines


SAVE = b"W\n"
INFO_REQUEST = b"?\n"
BOOTLOADER = b"!BOOT\n"


@dataclass
class PadInfo:
    firmware: str
    protocol: int
    language: int
    mode: int
    brightness: int
    colour: int


def parse_info(line: str) -> PadInfo | None:
    p = line.split("|")
    if len(p) != 7 or p[0] != "I":
        return None
    try:
        nums = [int(x) for x in p[2:]]
    except ValueError:
        return None
    return PadInfo(p[1][:20], *nums)


def parse_ack(line: str):
    """'A|W|12|0' -> (12, 0); anything else -> None."""
    p = line.split("|")
    if len(p) == 4 and p[0] == "A" and p[1] == "W":
        try:
            return int(p[2]), int(p[3])
        except ValueError:
            return None
    return None


def parse_lights(line: str):
    """'X|3|60|11' -> (mode, brightness, colour): changed with the keys on the pad."""
    p = line.split("|")
    if len(p) == 4 and p[0] == "X":
        try:
            return int(p[1]), int(p[2]), int(p[3])
        except ValueError:
            return None
    return None


def version_tuple(v: str):
    """'2.0.10' -> (2, 0, 10); text parts count as 0, so it never raises."""
    out = []
    for part in str(v or "").lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


def is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)
