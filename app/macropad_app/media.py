"""Music info for the pad (Windows only): the song, cover, volume and loudness
of Spotify or Deezer, read from Windows' media controls and mixer.

This is the former macropad_helper.py, now running inside the app. On other
systems (or if a library is missing) MEDIA_OK is False and the app still
works: it just tells the pad that no music app is there.
"""

import asyncio
import io
import json
import logging
import sys
import time
import unicodedata
from datetime import datetime, timezone

from . import paths

log = logging.getLogger("macropad.media")

MEDIA_OK = False
COVERS_OK = False
IMPORT_ERROR = ""
if sys.platform == "win32":
    try:
        # pycaw and winrt both use Windows COM: multi-threaded mode, set before
        # comtypes is first imported (this module is imported in the music thread)
        sys.coinit_flags = 0  # COINIT_MULTITHREADED
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioMeterInformation
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
        MEDIA_OK = True
        try:
            from PIL import Image
            from winrt.windows.storage.streams import Buffer, InputStreamOptions
            COVERS_OK = True
        except ImportError:
            COVERS_OK = False
    except Exception as e:  # missing library: the app keeps working without music info
        IMPORT_ERROR = f"{type(e).__name__}: {e}"
else:
    IMPORT_ERROR = "music info needs Windows"

VOL_STEP = 0.02             # 2 % per knob click; keep equal to VOL_STEP in the firmware
SEND_EVERY = 0.5            # seconds between updates to the pad (also its "app is running" signal)
LEVEL_EVERY = 0.04          # seconds between loudness updates (25 per second)
LEVEL_GAIN = 1.25           # raise if the "Music beat" lights look too calm
COVER = 120                 # album cover size in pixels; keep equal to COVER in the firmware

# Music apps it knows:
#   key: (name shown on the pad, text in the app's Windows media id, program file)
PLAYERS = {
    "spotify": ("Spotify", "spotify", "spotify.exe"),
    "deezer":  ("Deezer",  "deezer",  "deezer.exe"),
}

# --------------------------------------------------------------------------
# Text for the pad's screen (its font only has plain ASCII)
# --------------------------------------------------------------------------
_REPLACE = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
    "|": "/",  # '|' separates fields in the message
    "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
})


def to_ascii(text, limit):
    text = (text or "").translate(_REPLACE)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = " ".join(text.split())  # no newlines or double spaces
    return text[:limit]


# --------------------------------------------------------------------------
# One app's own volume in the Windows mixer
# --------------------------------------------------------------------------
class AppVolume:
    """Finds an app's audio session(s) in the Windows mixer and changes only those.
    Each entry is (volume control, loudness meter or None)."""

    def __init__(self, exe_name):
        self.exe = exe_name.lower()
        self._sessions = []
        self._looked_at = 0.0

    def _find(self):
        # Searching is a bit slow, so only look again every 3 s (or when nothing is found).
        if self._sessions and time.monotonic() - self._looked_at < 3:
            return self._sessions
        found = []
        for s in AudioUtilities.GetAllSessions():
            try:
                if s.Process and s.Process.name().lower() == self.exe:
                    try:
                        meter = s._ctl.QueryInterface(IAudioMeterInformation)
                    except Exception:
                        meter = None
                    found.append((s.SimpleAudioVolume, meter))
            except Exception:
                continue  # process ended while we looked
        self._sessions = found
        self._looked_at = time.monotonic()
        return found

    def get(self):
        """Returns (volume 0-100 or -1 if the app has made no sound yet, muted)."""
        try:
            for v, _ in self._find():
                return round(v.GetMasterVolume() * 100), bool(v.GetMute())
        except Exception:
            self._sessions = []  # app restarted: search again next time
        return -1, False

    def change(self, clicks):
        try:
            sessions = self._find()
            if not sessions:
                return
            level = min(1.0, max(0.0, sessions[0][0].GetMasterVolume() + clicks * VOL_STEP))
            for v, _ in sessions:
                v.SetMasterVolume(level, None)
                if clicks > 0 and v.GetMute():
                    v.SetMute(0, None)  # turning up also unmutes
            log.info("%s volume %d %%", self.exe, round(level * 100))
        except Exception as e:
            log.info("Could not change volume: %s", e)
            self._sessions = []

    def toggle_mute(self):
        try:
            sessions = self._find()
            if not sessions:
                return
            mute = not sessions[0][0].GetMute()
            for v, _ in sessions:
                v.SetMute(int(mute), None)
            log.info("%s %s", self.exe, "muted" if mute else "unmuted")
        except Exception as e:
            log.info("Could not mute: %s", e)
            self._sessions = []

    def peak(self):
        """Current loudness of the app, 0.0-1.0 (0 if unknown)."""
        try:
            values = [m.GetPeakValue() for _, m in self._find() if m is not None]
            return max(values) if values else 0.0
        except Exception:
            self._sessions = []
            return 0.0


# --------------------------------------------------------------------------
# Album cover: Windows gives a small picture; the pad wants raw RGB565 pixels
# --------------------------------------------------------------------------
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def cover_pixels(picture_bytes):
    """JPEG/PNG -> COVER x COVER square, RGB565 little-endian bytes (as the ESP32
    stores them). A fine dither pattern hides the colour steps of RGB565."""
    img = Image.open(io.BytesIO(picture_bytes)).convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    img = img.resize((COVER, COVER), Image.LANCZOS)
    rgb = img.tobytes()
    out = bytearray(COVER * COVER * 2)
    i = o = 0
    for y in range(COVER):
        row = _BAYER[y & 3]
        for x in range(COVER):
            t = row[x & 3]
            r = min(255, rgb[i] + (t >> 1))
            g = min(255, rgb[i + 1] + (t >> 2))
            b = min(255, rgb[i + 2] + (t >> 1))
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out[o] = v & 0xFF
            out[o + 1] = v >> 8
            i += 3
            o += 2
    return bytes(out)


async def read_cover(props):
    """The current song's album cover as pad pixels, or b"" if there is none."""
    if not COVERS_OK or props is None:
        return b""
    try:
        ref = props.thumbnail
        if ref is None:
            return b""
        stream = await ref.open_read_async()
        size = int(stream.size)
        if size <= 0 or size > 8_000_000:
            return b""
        result = await stream.read_async(Buffer(size), size, InputStreamOptions.READ_AHEAD)
        return cover_pixels(bytes(result))
    except Exception as e:
        log.info("No album cover: %s", e)
        return b""


def song_time(session, playing):
    """(position, length) of the song in milliseconds; (0, 0) if the app does not say."""
    try:
        tl = session.get_timeline_properties()
        length = (tl.end_time - tl.start_time).total_seconds()
        if length <= 0:
            return 0, 0
        pos = (tl.position - tl.start_time).total_seconds()
        if playing and tl.last_updated_time is not None:
            # the app reports the position from time to time; add the time since then
            updated = tl.last_updated_time
            now = datetime.now(timezone.utc)
            if updated.tzinfo is None:
                now = now.replace(tzinfo=None)
            age = (now - updated).total_seconds()
            if 0 < age < 86400:
                pos += age
        pos = max(0.0, min(pos, length))
        return int(pos * 1000), int(length * 1000)
    except Exception:
        return 0, 0


class MicVolume:
    """The default microphone's mute switch (Windows), for "Microphone on/off"."""

    def __init__(self):
        self._ep = None
        self._looked_at = 0.0

    def _endpoint(self):
        if self._ep is None or time.monotonic() - self._looked_at > 5:
            self._looked_at = time.monotonic()
            try:
                dev = AudioUtilities.GetMicrophone()
                if dev is None:
                    self._ep = None
                elif hasattr(dev, "EndpointVolume"):     # newer pycaw
                    self._ep = dev.EndpointVolume
                else:
                    from comtypes import CLSCTX_ALL
                    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self._ep = iface.QueryInterface(IAudioEndpointVolume)
            except Exception as e:
                log.info("No microphone found: %s", e)
                self._ep = None
        return self._ep

    def muted(self):
        """True / False, or None if there is no microphone."""
        try:
            ep = self._endpoint()
            return None if ep is None else bool(ep.GetMute())
        except Exception:
            self._ep = None
            return None

    def toggle(self):
        try:
            ep = self._endpoint()
            if ep is not None:
                ep.SetMute(0 if ep.GetMute() else 1, None)
        except Exception as e:
            log.info("Could not switch the microphone: %s", e)
            self._ep = None


class MasterVolume:
    """The whole PC's volume: the Windows volume slider of the current output
    (speakers, headphones ...). Same get / change / toggle_mute as AppVolume."""

    def __init__(self):
        self._ep = None
        self._looked_at = 0.0

    def _endpoint(self):
        # look again every 3 s, so plugging in headphones is picked up
        if self._ep is None or time.monotonic() - self._looked_at > 3:
            self._looked_at = time.monotonic()
            try:
                dev = AudioUtilities.GetSpeakers()
                if hasattr(dev, "EndpointVolume"):       # newer pycaw
                    self._ep = dev.EndpointVolume
                else:                                    # older pycaw
                    from comtypes import CLSCTX_ALL
                    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self._ep = iface.QueryInterface(IAudioEndpointVolume)
            except Exception as e:
                log.info("No sound output found: %s", e)
                self._ep = None
        return self._ep

    def get(self):
        try:
            ep = self._endpoint()
            if ep is None:
                return -1, False
            return round(ep.GetMasterVolumeLevelScalar() * 100), bool(ep.GetMute())
        except Exception:
            self._ep = None
            return -1, False

    def change(self, clicks):
        try:
            ep = self._endpoint()
            if ep is None:
                return
            level = ep.GetMasterVolumeLevelScalar() + clicks * VOL_STEP
            level = min(1.0, max(0.0, round(level / VOL_STEP) * VOL_STEP))  # even steps, like the volume keys
            ep.SetMasterVolumeLevelScalar(level, None)
            if clicks > 0 and ep.GetMute():
                ep.SetMute(0, None)  # turning up also unmutes
            log.info("PC volume %d %%", round(level * 100))
        except Exception as e:
            log.info("Could not change the PC volume: %s", e)
            self._ep = None

    def toggle_mute(self):
        try:
            ep = self._endpoint()
            if ep is None:
                return
            mute = not ep.GetMute()
            ep.SetMute(int(mute), None)
            log.info("PC sound %s", "muted" if mute else "on")
        except Exception as e:
            log.info("Could not mute: %s", e)
            self._ep = None


def press_media_key(cmd):
    """Presses a Windows media key (like a keyboard's media keys would)."""
    vk = {"P": 0xB3, "N": 0xB0, "B": 0xB1}[cmd]   # VK_MEDIA_PLAY_PAUSE / NEXT_TRACK / PREV_TRACK
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 1, 0)       # KEYEVENTF_EXTENDEDKEY
        user32.keybd_event(vk, 0, 1 | 2, 0)   # ... | KEYEVENTF_KEYUP
    except Exception as e:
        log.info("Could not press the media key: %s", e)


def load_learned():
    try:
        return {k.lower(): v for k, v in json.loads(paths.learned_file().read_text("utf-8")).items()}
    except Exception:
        return {}


def save_learned(learned):
    try:
        paths.learned_file().write_text(json.dumps(learned, indent=2), "utf-8")
    except Exception as e:
        log.info("Could not save the learned music apps: %s", e)


# --------------------------------------------------------------------------
# The music app (from Windows' media controls, the same info as the volume flyout)
# --------------------------------------------------------------------------
class MusicApp:
    def __init__(self, manager, allowed, app_volume=False):
        self.manager = manager
        self.allowed = allowed               # player keys we may use, in order of preference
        self.key = allowed[0]                # last player seen
        self.seen = False
        self.session = None
        self.playing = False
        self.props = None                    # media info of the current song (for the cover)
        self.track = None                    # (app, title, artist): a change means a new song
        self.time_line = "T|0|0\n"            # song position and length
        self.last_error = ""
        self.learned = load_learned()        # media id -> player key
        self.volumes = {k: AppVolume(PLAYERS[k][2]) for k in allowed}
        self.master_volume = MasterVolume()
        self.app_volume = app_volume         # knob: the music app's volume (True) or the PC's

    @property
    def volume(self):
        """The music app's own entry in the mixer (also its loudness meter)."""
        return self.volumes[self.key]

    @property
    def control(self):
        """What the knob turns and the pad shows: the PC volume, or the app's."""
        return self.volumes[self.key] if self.app_volume else self.master_volume

    def _player_of(self, app_id):
        """Player key for a media id, or None if it is not one of our music apps."""
        for k in self.allowed:
            if PLAYERS[k][1] in app_id:
                return k
        k = self.learned.get(app_id)
        return k if k in self.allowed else None

    def _learn(self, candidates):
        """Newer Spotify versions tell Windows only a generic id such as
        "Chromium.ZVFT...". If exactly one unknown media session is active and
        exactly one of our music apps is making sound right now, they are the
        same app: remember that id (saved in the app's user folder)."""
        if len(candidates) != 1:
            return False
        loud = [k for k in self.allowed if self.volumes[k].peak() > 0.002]
        if len(loud) != 1:
            return False
        app_id = candidates[0]
        self.learned[app_id] = loud[0]
        save_learned(self.learned)
        log.info("Learned: %s shows up in Windows as '%s'", PLAYERS[loud[0]][0], app_id)
        return True

    def _find_session(self):
        """Picks our music app's media session; one that is playing wins."""
        best = None
        unknown_active = []
        sessions = list(self.manager.get_sessions())
        for s in sessions:
            app_id = (s.source_app_user_model_id or "").lower()
            info = s.get_playback_info()
            playing = info is not None and info.playback_status == PlaybackStatus.PLAYING
            k = self._player_of(app_id)
            if k is None:
                if playing:
                    unknown_active.append(app_id)
                continue
            if not playing and self.volumes[k].peak() > 0.01:
                playing = True   # the app says "paused" but we can hear it
            if best is None or (playing and not best[2]):
                best = (s, k, playing)
        if best is None:
            if not unknown_active:   # nothing says "playing": try the session Windows shows
                current = self.manager.get_current_session()
                if current is not None:
                    app_id = (current.source_app_user_model_id or "").lower()
                    if self._player_of(app_id) is None:
                        unknown_active.append(app_id)
            if self._learn(unknown_active):
                return self._find_session()
        if best:
            self.session, self.key, self.seen = best[0], best[1], True
        else:
            self.session = None
        return best

    async def status_line(self):
        title = artist = ""
        playing = False
        props = best = None
        pos = length = 0
        try:
            best = self._find_session()
            if best:
                session, _, playing = best
                try:
                    # Windows usually answers at once; never let a slow answer stop the updates
                    props = await asyncio.wait_for(session.try_get_media_properties_async(), 1.5)
                except asyncio.TimeoutError:
                    props = self.props   # keep showing the last song
                if props is not None:
                    title, artist = props.title or "", props.artist or ""
                pos, length = song_time(session, playing)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if msg != self.last_error:
                log.info("Could not read the music app's info: %s", msg)
                self.last_error = msg
        self.playing = playing
        self.props = props
        self.track = (self.key if best else "", title, artist) if title else None
        self.time_line = f"T|{pos}|{length}\n"
        vol, muted = self.control.get()
        name = PLAYERS[self.key][0] if self.seen else ""
        return (f"S|{name}|{int(playing)}|{vol}|{int(muted)}|"
                f"{to_ascii(title, 100)}|{to_ascii(artist, 80)}\n")

    async def command(self, cmd):
        """P = play/pause, N = next, B = back (previous). Goes straight to
        Spotify/Deezer; without them (or if they refuse) it presses the normal
        Windows media key, so the key always does something."""
        name = {"P": "play/pause", "N": "next", "B": "previous"}[cmd]
        try:
            session = self.session or (self._find_session() or (None,))[0]
            if session is not None:
                if cmd == "P":
                    ok = await session.try_toggle_play_pause_async()
                elif cmd == "N":
                    ok = await session.try_skip_next_async()
                else:
                    ok = await session.try_skip_previous_async()
                if ok is not False:
                    log.info("%s: %s", PLAYERS[self.key][0], name)
                    return
        except Exception as e:
            log.info("Could not control the app: %s", e)
            self.session = None
        press_media_key(cmd)
        log.info("Media key: %s", name)




async def handle_message(line, app):
    """Messages from the pad: 'V+2' / 'V-1' (knob), 'M' (knob press), 'P' / 'N' / 'B' (keys)."""
    if line.startswith("V"):
        try:
            app.control.change(int(line[1:]))
        except ValueError:
            pass
    elif line == "M":
        app.control.toggle_mute()
    elif line in ("P", "N", "B"):
        await app.command(line)


class CoverSender:
    """Sends the album cover when the song changes. Windows sometimes brings the
    new picture a moment after the new title, so it looks again after 0.8 s and
    3 s and only sends when the picture is really different. The picture is read
    in the background: the regular updates to the pad (its sign that the helper
    is running) must never wait for it."""

    def __init__(self):
        self.track = "not yet"   # forces a send right after connecting
        self.sent = None         # pixels last sent (None = nothing sent yet)
        self.checks = []         # times when to look at the picture
        self.retries = 0
        self.reading = None      # background job reading the picture
        self.reading_since = 0.0

    def stop(self):
        if self.reading and not self.reading.done():
            self.reading.cancel()
        self.reading = None

    def resend(self):
        if self.retries < 3:     # the pad lost something on the way
            self.retries += 1
            self.sent = None
            self.checks.append(time.monotonic())

    def update(self, ser, app):
        now = time.monotonic()
        if app.track != self.track:
            self.track = app.track
            self.retries = 0
            self.checks = [now, now + 0.8, now + 3.0]
            self.stop()          # a picture still being read belongs to the old song
        if self.reading is not None:
            if self.reading.done():
                try:
                    pixels = self.reading.result()
                except Exception:
                    pixels = b""
                self.reading = None
                self._send(ser, pixels)
            elif now - self.reading_since > 10:
                self.stop()      # Windows never answered: give up on this one
            return
        if not self.checks or now < self.checks[0]:
            return
        self.checks.pop(0)
        if app.track:
            self.reading = asyncio.ensure_future(read_cover(app.props))
            self.reading_since = now
        else:
            self._send(ser, b"")

    def _send(self, ser, pixels):
        if pixels == self.sent:
            return
        ser.write(f"C|{len(pixels)}|{sum(pixels) & 0xFFFFFFFF}\n".encode("ascii") + pixels)
        self.sent = pixels
        if pixels:
            log.info("Album cover sent")


