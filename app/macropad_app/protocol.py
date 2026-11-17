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


def key_line(index: int, action_id: str, lang: str) -> bytes:
    a = keys.resolve(action_id, lang)
    return _line("K", index, a.type, a.code, a.mods, pad_text(a.label, 23))


def language_line(lang: str) -> bytes:
    return _line("G", 1 if lang == "de" else 0)


def display_line(display: dict) -> bytes:
    return _line("D", config.BACKGROUNDS.index(display["background"]), int(display["fish"]),
                 display["brightness"], int(display["music"]))


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


def settings_lines(settings: dict) -> list[bytes]:
    """Every settings message for the pad, in a safe order (the light mode last,
    because it may point at a scheme sent just before)."""
    settings = config.validate(settings)
    lang = settings["pad_language"]
    lines = [language_line(lang)]
    lines += [key_line(i, a, lang) for i, a in enumerate(settings["keys"])]
    lines.append(display_line(settings["display"]))
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
