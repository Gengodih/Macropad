"""The USB link to the pad, running in its own thread.

It finds the pad, keeps the music info flowing (media.py), sends settings when
the user presses Apply, and hands the port over to the flasher for updates.
Nothing here may ever stop the app: every error ends in "reconnect".
"""

import asyncio
import logging
import queue
import threading
import time
from dataclasses import dataclass, field

import serial
from serial.tools import list_ports

from PySide6.QtCore import QObject, Signal

from . import protocol

log = logging.getLogger("macropad.device")

ESPRESSIF_VID = 0x303A            # every ESP32-S3 reports this USB vendor id
# The chip's built-in flash mode (USB-Serial/JTAG) uses product id 0x1001 -
# and so does the Arduino TinyUSB firmware on the T-Display-S3. The two are
# told apart by talking to them: only the firmware answers "?".
ROM_BOOTLOADER_PID = 0x1001
SEARCH_GRACE = 10.0               # seconds of "searching" before it says "disconnected"
ACK_TIMEOUT = 3.0
KEEPALIVE = b"S||0|-1|0||\n"      # "app running, no music app" (when music info is off)

STATUS_CONNECTED = "connected"
STATUS_SEARCHING = "searching"
STATUS_BUSY = "busy"              # applying or updating: do not unplug
STATUS_DISCONNECTED = "disconnected"


def pad_ports():
    """Serial ports that belong to an ESP32-S3, the 'Macro Pad' one first."""
    found = []
    try:
        for p in list_ports.comports():
            if p.vid == ESPRESSIF_VID:
                text = " ".join(str(x) for x in (p.description, p.product, p.interface) if x).lower()
                found.append((0 if "macro" in text else 1, p.device, p.pid))
    except Exception as e:
        log.info("Could not list the COM ports: %s", e)
    return [(dev, pid) for _, dev, pid in sorted(found)]


def open_port(port, timeout=0):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200   # ignored by USB, but required
    ser.timeout = timeout
    ser.write_timeout = 3   # an album cover is about 29 kB
    ser.rts = False         # with RTS off the ESP32-S3 never reboots into flash mode
    ser.dtr = True          # tells the pad that a program is listening
    ser.open()
    return ser


@dataclass
class ApplyRequest:
    lines: list
    attempts: int = 0
    deadline: float = 0.0
    sent: int = 0


@dataclass
class _Control:
    """Requests from the window to the link thread."""
    kind: str
    payload: object = None
    done: threading.Event = field(default_factory=threading.Event)
    result: object = None


class PadLink(QObject):
    status_changed = Signal(str)
    info_received = Signal(object)            # protocol.PadInfo, or None for an old firmware
    apply_finished = Signal(bool, str)        # ok, details
    pad_lights_changed = Signal(int, int, int)
    now_playing = Signal(str, str, str)       # player, title, artist
    port_changed = Signal(str)
    music_state = Signal(bool, str)           # music info available?, reason if not
    music_level = Signal(float)               # loudness 0-1, about 25 a second while music plays

    def __init__(self, knob_app_volume=True, player="auto"):
        super().__init__()
        self._requests = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self._status = None
        self._paused = False
        self._knob_app_volume = knob_app_volume
        self._player = player
        self.port = ""
        self.info = None

    # ----- called from the window (any thread) -------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pad-link", daemon=True)
        self._thread.start()

    def stop(self, wait=2.0):
        self._stop.set()
        if self._thread:
            self._thread.join(wait)

    def apply(self, lines):
        """Send settings (list of protocol lines) and save them on the pad."""
        self._requests.put(_Control("apply", list(lines)))

    def set_knob_target(self, app_volume: bool):
        self._requests.put(_Control("knob", bool(app_volume)))

    def request_info(self):
        self._requests.put(_Control("info"))

    def pause(self, enter_bootloader=False, timeout=5.0) -> bool:
        """Close the port and keep it closed (for the flasher). With
        enter_bootloader the pad is first told to restart into flash mode.
        Returns True once the port is free."""
        c = _Control("pause", enter_bootloader)
        self._requests.put(c)
        return c.done.wait(timeout) and bool(c.result)

    def resume(self):
        self._requests.put(_Control("resume"))

    @property
    def status(self):
        return self._status

    # ----- link thread -------------------------------------------------------
    def _set_status(self, status):
        if status != self._status:
            self._status = status
            self.status_changed.emit(status)

    def _run(self):
        try:
            asyncio.run(self._main())
        except Exception:
            log.exception("Pad link stopped unexpectedly")

    async def _start_music(self):
        """MusicApp, or None if music info is not available here.
        media.py (pycaw, winrt) is only ever imported in this thread: both set up
        Windows COM for the thread that imports them, and the window's thread
        belongs to Qt."""
        try:
            from . import media
        except Exception as e:
            log.info("Music info off: %s", e)
            self.music_state.emit(False, str(e))
            return None
        if not media.MEDIA_OK:
            log.info("Music info off: %s", media.IMPORT_ERROR)
            self.music_state.emit(False, media.IMPORT_ERROR)
            return None
        for _ in range(3):
            try:
                manager = await asyncio.wait_for(media.MediaManager.request_async(), 5)
                allowed = list(media.PLAYERS) if self._player == "auto" else [self._player]
                music = media.MusicApp(manager, allowed, self._knob_app_volume)
                self.music_state.emit(True, "")
                return music
            except Exception as e:
                log.info("Windows media controls not ready (%s), trying again", e)
                await asyncio.sleep(3)
        self.music_state.emit(False, "Windows media controls did not answer")
        return None

    def _handle_controls(self, ser, music, pending):
        """Requests from the window. Returns 'pause' if the port must be freed."""
        while True:
            try:
                c = self._requests.get_nowait()
            except queue.Empty:
                return None
            if c.kind == "apply":
                if ser is None:
                    self.apply_finished.emit(False, "not connected")
                else:
                    pending.append(ApplyRequest(c.payload))
            elif c.kind == "knob":
                self._knob_app_volume = c.payload
                if music is not None:
                    music.app_volume = c.payload
            elif c.kind == "info":
                if ser is not None:
                    ser.write(protocol.INFO_REQUEST)
            elif c.kind == "pause":
                if ser is not None and c.payload:
                    # New firmware restarts on "!BOOT". Older firmware does not know it,
                    # but every Arduino TinyUSB sketch restarts into flash mode when
                    # the port is switched to 1200 baud (like the Arduino IDE does).
                    try:
                        ser.write(protocol.BOOTLOADER)
                        ser.flush()
                        time.sleep(0.3)
                        ser.dtr = False
                        ser.baudrate = 1200
                    except Exception as e:
                        log.info("Pad left for flash mode (%s)", e)
                self._paused = True
                self._pause_request = c
                return "pause"
            elif c.kind == "resume":
                self._paused = False

    async def _main(self):
        music = await self._start_music()
        lost_at = time.monotonic()
        self._pause_request = None
        while not self._stop.is_set():
            if self._paused:
                if self._pause_request is not None:
                    self._pause_request.result = True
                    self._pause_request.done.set()
                    self._pause_request = None
                self._set_status(STATUS_BUSY)
                self._handle_controls(None, music, [])
                await asyncio.sleep(0.2)
                lost_at = time.monotonic()
                continue
            if self._handle_controls(None, music, []) == "pause":
                continue
            ports = [dev for dev, pid in pad_ports()]
            if not ports:
                waited = time.monotonic() - lost_at
                self._set_status(STATUS_SEARCHING if waited < SEARCH_GRACE else STATUS_DISCONNECTED)
                await asyncio.sleep(1.0)
                continue
            port = ports[0]
            try:
                ser = open_port(port)
            except (serial.SerialException, OSError) as e:
                log.info("Cannot open %s (%s). Is another program using it?", port, e)
                self._set_status(STATUS_DISCONNECTED)
                await asyncio.sleep(2)
                continue
            self.port = port
            self.port_changed.emit(port)
            log.info("Connected to the pad on %s", port)
            try:
                await self._session(ser, music)
            except (serial.SerialException, OSError) as e:
                log.info("Pad disconnected (%s)", e)
            except Exception:
                log.exception("Unexpected error - reconnecting")
                await asyncio.sleep(1)
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
                self.port = ""
                self.port_changed.emit("")
                if music is not None:
                    self.now_playing.emit("", "", "")
            lost_at = time.monotonic()
            await asyncio.sleep(0.5)
        self._set_status(STATUS_DISCONNECTED)

    async def _session(self, ser, music):
        from . import media  # only for CoverSender / handle_message / timing constants
        covers = media.CoverSender() if music is not None else None
        pending = []                      # apply requests
        current = None                    # the one waiting for its "A|W"
        errors = []
        buffer = b""
        last_sent = last_level = 0.0
        last_track = None
        info_asked = time.monotonic()
        ser.write(protocol.INFO_REQUEST)
        got_info = False
        self._set_status(STATUS_CONNECTED)
        try:
            while not self._stop.is_set():
                if self._handle_controls(ser, music, pending) == "pause":
                    return
                data = ser.read(ser.in_waiting or 1)  # raises SerialException when unplugged
                send_now = False
                if data:
                    buffer += data
                    if len(buffer) > 65536:          # garbage without line ends: drop it
                        buffer = b""
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        msg = raw.decode("ascii", "ignore").strip()
                        if not msg:
                            continue
                        if msg.startswith("I|"):
                            info = protocol.parse_info(msg)
                            if info:
                                got_info = True
                                self.info = info
                                if info.protocol >= 2:   # the date, for the "Seasons" background
                                    ser.write(protocol.month_line(time.localtime().tm_mon))
                                self.info_received.emit(info)
                        elif msg.startswith("A|W|") and current is not None:
                            ack = protocol.parse_ack(msg)
                            ok = ack is not None and ack[1] == 0 and ack[0] == current.sent
                            detail = "" if ok else f"pad accepted {ack} of {current.sent}; {'; '.join(errors)}"
                            if not ok and current.attempts < 2:
                                log.info("Settings not fully accepted (%s), sending again", detail)
                                current.deadline = 0.0         # resend below
                            else:
                                self.apply_finished.emit(ok, detail)
                                current = None
                            errors = []
                        elif msg.startswith("A|E|"):
                            errors.append(msg[4:])
                            log.info("Pad did not understand: %s", msg[4:])
                        elif msg.startswith("X|"):
                            x = protocol.parse_lights(msg)
                            if x:
                                self.pad_lights_changed.emit(*x)
                        elif music is not None:
                            if msg == "R":
                                covers.resend()
                                continue
                            await media.handle_message(msg, music)
                            send_now = True
                        elif msg in ("P", "N", "B"):
                            pass                      # no music info: nothing to control

                now = time.monotonic()
                # an old firmware never answers "?": treat it as such after 2 s
                if not got_info and now - info_asked > 2.0:
                    got_info = True
                    self.info = None
                    self.info_received.emit(None)

                # settings: send, then wait for the pad's "saved"
                if current is None and pending:
                    current = pending.pop(0)
                    current.deadline = 0.0
                if current is not None and now >= current.deadline:
                    if current.attempts >= 2:
                        self.apply_finished.emit(False, "the pad did not answer")
                        current = None
                    else:
                        current.attempts += 1
                        errors = []
                        for line in current.lines:
                            ser.write(line)
                        ser.write(protocol.SAVE)
                        current.sent = len(current.lines)
                        current.deadline = now + ACK_TIMEOUT

                # music info (also the pad's sign that the app is running)
                if send_now or now - last_sent >= media.SEND_EVERY:
                    if music is not None:
                        line = await music.status_line()
                        ser.write(line.encode("ascii") + music.time_line.encode("ascii"))
                        covers.update(ser, music)
                        track = music.track
                        if track != last_track:
                            last_track = track
                            if track:
                                player = media.PLAYERS.get(track[0], (track[0],))[0]
                                self.now_playing.emit(player, track[1], track[2])
                            else:
                                self.now_playing.emit("", "", "")
                    else:
                        ser.write(KEEPALIVE)
                    last_sent = now
                if music is not None and music.playing and now - last_level >= media.LEVEL_EVERY:
                    level = round(min(1.0, music.volume.peak() * media.LEVEL_GAIN) * 100)
                    ser.write(f"L|{level}\n".encode("ascii"))
                    self.music_level.emit(level / 100.0)
                    last_level = now
                await asyncio.sleep(0.02)
        finally:
            if covers is not None:
                covers.stop()
            if current is not None:
                self.apply_finished.emit(False, "the pad was unplugged")
            for _ in pending:
                self.apply_finished.emit(False, "the pad was unplugged")
