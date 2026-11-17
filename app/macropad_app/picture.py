"""Own pictures for the pad's screen: any image or GIF -> RGB565 frames.
A still picture keeps the full 320 x 170 pixels; an animated GIF uses
160 x 85 per frame (shown twice as big) so up to 50 frames fit into the pad.
The converted picture is kept in %APPDATA%\\MacroPad\\picture.bin."""

import json
import logging
import struct
import zlib

from . import paths

log = logging.getLogger("macropad.picture")

MAX_FRAMES = 50
PAD_SPACE = 0x160000 - 16          # the pad's picture area minus the header


class Picture:
    def __init__(self, w, h, frames, delay_ms, data: bytes, name=""):
        self.w, self.h, self.frames, self.delay_ms, self.data, self.name = w, h, frames, delay_ms, data, name

    @property
    def crc(self) -> int:
        return zlib.crc32(self.data) & 0xFFFFFFFF


def convert(path, fit=False) -> Picture:
    """Image file -> Picture. Raises ValueError with a readable reason."""
    from PIL import Image, ImageOps, ImageSequence
    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(str(e)) from e
    frames = [f.copy() for f in ImageSequence.Iterator(img)] if getattr(img, "is_animated", False) else [img.copy()]
    durations = [max(20, int(f.info.get("duration", img.info.get("duration", 100)) or 100)) for f in frames]
    animated = len(frames) > 1
    if animated and len(frames) > MAX_FRAMES:          # keep every n-th frame, same total length
        step = len(frames) / MAX_FRAMES
        idx = [int(i * step) for i in range(MAX_FRAMES)]
        total = sum(durations)
        frames = [frames[i] for i in idx]
        durations = [max(20, total // MAX_FRAMES)] * MAX_FRAMES
    w, h = (160, 85) if animated else (320, 170)
    delay = int(sum(durations) / len(durations)) if animated else 100
    out = bytearray()
    for f in frames:
        f = f.convert("RGBA")
        bg = Image.new("RGBA", f.size, (0, 0, 0, 255))
        f = Image.alpha_composite(bg, f).convert("RGB")
        if fit:
            f = ImageOps.pad(f, (w, h), method=Image.LANCZOS, color=(0, 0, 0))
        else:
            f = ImageOps.fit(f, (w, h), method=Image.LANCZOS)
        out += rgb565(f)
    if len(out) > PAD_SPACE:
        raise ValueError("too big")
    name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    return Picture(w, h, len(frames), delay, bytes(out), name)


def rgb565(img) -> bytes:
    """PIL RGB image -> little-endian RGB565 bytes."""
    px = img.tobytes()
    out = bytearray(len(px) // 3 * 2)
    j = 0
    for i in range(0, len(px), 3):
        r, g, b = px[i], px[i + 1], px[i + 2]
        v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out[j] = v & 0xFF
        out[j + 1] = v >> 8
        j += 2
    return bytes(out)


def save(pic: Picture, source=""):
    d = paths.user_dir()
    with open(d / "picture.bin", "wb") as f:
        f.write(struct.pack("<4sHHHH", b"MPIC", pic.w, pic.h, pic.frames, pic.delay_ms))
        f.write(pic.data)
    with open(d / "picture.json", "w", encoding="utf-8") as f:
        json.dump({"name": pic.name, "source": str(source)}, f)


def load() -> Picture | None:
    d = paths.user_dir()
    try:
        raw = (d / "picture.bin").read_bytes()
        magic, w, h, frames, delay = struct.unpack("<4sHHHH", raw[:12])
        data = raw[12:]
        if magic != b"MPIC" or len(data) != w * h * frames * 2 or (w, h) not in ((320, 170), (160, 85)):
            return None
        name = ""
        try:
            name = json.loads((d / "picture.json").read_text("utf-8")).get("name", "")
        except Exception:
            pass
        return Picture(w, h, frames, delay, data, name)
    except FileNotFoundError:
        return None
    except Exception as e:
        log.warning("Stored picture unreadable: %s", e)
        return None


def source() -> str:
    """The file the picture was made from (to convert it again), '' if unknown / gone."""
    import os
    try:
        src = json.loads((paths.user_dir() / "picture.json").read_text("utf-8")).get("source", "")
        return src if src and os.path.exists(src) else ""
    except Exception:
        return ""


def remove():
    d = paths.user_dir()
    for n in ("picture.bin", "picture.json"):
        try:
            (d / n).unlink()
        except FileNotFoundError:
            pass
