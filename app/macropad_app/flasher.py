"""Firmware updates: puts the pad into its built-in flash mode and writes the
firmware with esptool, with progress, time left and a cancel button.

The firmware ships with the app (resources/firmware):
    firmware.json   {"version": "2.0.0", "chip": "esp32s3",
                     "parts": [{"offset": "0x0", "file": "bootloader.bin", "sha256": "..."}, ...]}
Only bootloader, partition table, boot_app0 and the program are written, so
the pad's saved settings (its NVS area) stay as they are.
"""

import contextlib
import io
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from serial.tools import list_ports

from . import paths
from .device import ESPRESSIF_VID, ROM_BOOTLOADER_PID
from .updater import sha256_of

log = logging.getLogger("macropad.flash")

BAUD = 921600
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_WRITING = re.compile(r"Writing at 0x([0-9a-fA-F]+)")


class FlashError(Exception):
    pass


@dataclass
class Bundle:
    version: str
    parts: list          # [(offset int, Path, size)]

    @property
    def total(self):
        return sum(size for _, _, size in self.parts)

    def estimate_seconds(self) -> int:
        # restart + about 40 kB/s of compressed writing, plus reconnect
        return int(12 + self.total / 60000)


def load_bundle(folder: Path | None = None) -> Bundle:
    folder = Path(folder or paths.firmware_dir())
    try:
        meta = json.loads((folder / "firmware.json").read_text("utf-8"))
        parts = []
        for p in meta["parts"]:
            f = folder / p["file"]
            if f.resolve().parent != folder.resolve():
                raise FlashError("firmware.json points outside its folder")
            if sha256_of(f) != str(p["sha256"]).lower():
                raise FlashError(f"{p['file']} is damaged (checksum)")
            parts.append((int(str(p["offset"]), 0), f, f.stat().st_size))
        if not parts:
            raise FlashError("firmware.json lists no files")
        return Bundle(str(meta["version"]), parts)
    except FlashError:
        raise
    except FileNotFoundError as e:
        raise FlashError("no firmware in this app build") from e
    except (OSError, KeyError, ValueError, TypeError) as e:
        raise FlashError(f"firmware files unreadable ({e})") from e


def rom_ports():
    """Espressif serial ports with product id 0x1001 (flash mode - or the pad itself)."""
    try:
        return [p.device for p in list_ports.comports()
                if p.vid == ESPRESSIF_VID and p.pid == ROM_BOOTLOADER_PID]
    except Exception:
        return []


def wait_for_rom_port(timeout=20.0, cancel=None, before=()):
    """After "!BOOT" the pad leaves (its port vanishes) and comes back in flash
    mode as a new COM port. A pad that already hangs in flash mode is found at once."""
    end = time.monotonic() + timeout
    before = list(before)
    if before:
        gone_by = time.monotonic() + 6.0          # first wait until the old port is gone
        while time.monotonic() < gone_by and set(before) & set(rom_ports()):
            if cancel is not None and cancel.is_set():
                return None
            time.sleep(0.2)
    seen_since = {}
    while time.monotonic() < end:
        if cancel is not None and cancel.is_set():
            return None
        now = time.monotonic()
        ports = rom_ports()
        for p in ports:
            seen_since.setdefault(p, now)
        for p in list(seen_since):
            if p not in ports:
                del seen_since[p]
        stable = [p for p, t in seen_since.items() if now - t >= 0.8]   # Windows finished setting it up
        if stable:
            new = [p for p in stable if p not in before]
            return (new or stable)[0]
        time.sleep(0.2)
    return None


class _Capture(io.TextIOBase):
    """Collects esptool's output, turns its progress lines into a fraction and
    stops esptool (by raising) when the user cancels."""

    def __init__(self, parts, progress, cancel):
        self.parts = sorted(parts, key=lambda x: x[0])
        self.total = max(1, sum(size for _, _, size in self.parts))
        self.progress, self.cancel = progress, cancel
        self.tail = []
        self.start = time.monotonic()
        self.part = 0
        self._buf = ""

    def writable(self):
        return True

    def isatty(self):
        return False

    def write(self, text):
        if self.cancel is not None and self.cancel.is_set():
            raise FlashError("cancelled")
        self._buf += text
        while "\n" in self._buf or "\r" in self._buf:
            cut = min(i for i in (self._buf.find("\n"), self._buf.find("\r")) if i >= 0)
            line, self._buf = self._buf[:cut].strip(), self._buf[cut + 1:]
            if line:
                self._line(line)
        if len(self._buf) > 400:
            self._buf = self._buf[-200:]
        return len(text)

    def _line(self, line):
        self.tail = (self.tail + [line])[-15:]
        log.debug("esptool: %s", line)
        addr = _WRITING.search(line)
        if addr:
            a = int(addr.group(1), 16)
            for i, (offset, _, _) in enumerate(self.parts):
                if a >= offset:
                    self.part = i
        m = _PERCENT.search(line)
        if m and self.progress:
            pct = min(100.0, float(m.group(1)))
            done = sum(size for _, _, size in self.parts[:self.part]) + self.parts[self.part][2] * pct / 100
            frac = min(1.0, done / self.total)
            elapsed = time.monotonic() - self.start
            left = elapsed / frac - elapsed if frac > 0.05 else None
            self.progress(frac, left)

    def flush(self):
        pass


_esptool_lock = threading.Lock()


def flash(bundle: Bundle, port: str, progress=None, cancel=None) -> None:
    """Writes the bundle with esptool (inside this process, so it works in the
    built app without a console). progress(fraction 0-1, seconds_left or None)."""
    import esptool
    args = ["--chip", "esp32s3", "--port", port, "--baud", str(BAUD),
            "--before", "no-reset", "--after", "hard-reset", "write-flash", "-z"]
    for offset, f, _ in bundle.parts:
        args += [hex(offset), str(f)]
    log.info("Flashing on %s: %s", port, " ".join(args))
    cap = _Capture(bundle.parts, progress, cancel)
    with _esptool_lock, contextlib.redirect_stdout(cap), contextlib.redirect_stderr(cap):
        try:
            esptool.main(args)
        except FlashError:
            raise
        except SystemExit as e:
            if e.code not in (0, None):
                raise FlashError(_hint(cap.tail) or f"esptool stopped (code {e.code})") from None
        except Exception as e:   # esptool's FatalError and serial errors
            raise FlashError(str(e) or _hint(cap.tail) or type(e).__name__) from None
    log.info("esptool finished: %s", " | ".join(cap.tail[-3:]))
    if progress:
        progress(1.0, 0)


def _hint(tail):
    for t in reversed(tail):
        if "error" in t.lower() or "fail" in t.lower():
            return t
    return tail[-1] if tail else ""


def wait_for_pad(timeout=25.0, cancel=None) -> bool:
    """After flashing the pad restarts as a normal keyboard + serial port."""
    end = time.monotonic() + timeout
    time.sleep(1.5)                                 # the flash-mode port first has to go away
    while time.monotonic() < end:
        if cancel is not None and cancel.is_set():
            return False
        try:
            if any(p.vid == ESPRESSIF_VID for p in list_ports.comports()):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False
