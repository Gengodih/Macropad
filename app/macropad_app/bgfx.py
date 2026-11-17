"""The pad's screen animations for the app (the library built from
native/bgfx.cpp, which uses the pad's own Aquarium.h and Backgrounds.h).

If the library is missing or cannot be loaded, available() is False and the
app simply shows still backgrounds instead - nothing else depends on it.
"""

import ctypes
import logging
import sys

from PySide6.QtGui import QImage

from . import paths

log = logging.getLogger("macropad.bgfx")

W, H = 320, 170
# The pad's light colours as (hue, saturation) on the Adafruit scale, for
# "Lava lamp: use the light colour" (COLOURS in the firmware)
LIGHT_HUES = [(0, 255), (4550, 255), (6900, 255), (10000, 255), (15500, 255), (21845, 255), (27300, 255), (32768, 255), (37300, 255), (42800, 255), (46400, 255), (51900, 255), (55500, 255), (59200, 255), (62800, 255), (0, 0)]

_lib = None
_tried = False


def _load():
    global _lib, _tried
    if _tried:
        return _lib
    _tried = True
    path = paths.resource("bgfx.dll" if sys.platform == "win32" else "bgfx.so")
    try:
        lib = ctypes.CDLL(str(path))
        lib.bgfx_version.restype = ctypes.c_int
        if lib.bgfx_version() != 1 or lib.bgfx_width() != W or lib.bgfx_height() != H:
            raise OSError("unexpected library version")
        lib.bgfx_new.restype = ctypes.c_void_p
        lib.bgfx_new.argtypes = [ctypes.c_uint32]
        lib.bgfx_free.argtypes = [ctypes.c_void_p]
        lib.bgfx_select.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        lib.bgfx_poke.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.bgfx_update.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.bgfx_render.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _lib = lib
    except (OSError, AttributeError) as e:
        log.warning("Animated backgrounds not available (%s): %s", path, e)
    return _lib


def available() -> bool:
    return _load() is not None


class Renderer:
    """One running background, exactly as the pad draws it (320 x 170)."""

    def __init__(self, seed=1):
        self._lib = _load()
        if self._lib is None:
            raise RuntimeError("background library not available")
        self._h = self._lib.bgfx_new(seed & 0xFFFFFFFF)
        if not self._h:
            raise MemoryError("background renderer")
        self._buf = (ctypes.c_uint16 * (W * H))()

    def select(self, kind: int, options: int):
        self._lib.bgfx_select(self._h, int(kind), int(options) & 0xFF)

    def poke(self, label: str = ""):
        self._lib.bgfx_poke(self._h, label.encode("ascii", "replace")[:23])

    def update(self, dt: float, level: float = 0.0, colour: int = 11, month: int = 0):
        hue, sat = LIGHT_HUES[colour] if 0 <= colour < len(LIGHT_HUES) else LIGHT_HUES[11]
        self._lib.bgfx_update(self._h, float(dt), float(level), hue, sat, int(month))

    def frame(self) -> QImage:
        self._lib.bgfx_render(self._h, self._buf)
        return QImage(bytes(self._buf), W, H, W * 2, QImage.Format.Format_RGB16).copy()

    def close(self):
        if self._h:
            self._lib.bgfx_free(self._h)
            self._h = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
