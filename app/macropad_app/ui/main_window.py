"""The main window: side menu, pages over the background, Apply, tray icon,
and everything that runs in the background (pad link, updates, flashing)."""

import copy
import logging
import threading
import time

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
                               QPushButton, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

from .. import UPDATE_REPO, VERSION, config, flasher, paths, protocol, updater, winsys
from ..device import PadLink
from ..i18n import T, set_language
from . import dialogs, theme
from .background import Background
from .. import focus, picture
from ..actions import ActionRunner
from ..pcstats import PcStats
from ..stats import KeyStats
from .scenes import live
from .pages import (DisplayPage, GuidePage, HomePage, KeysPage, LanguagePage, LedsPage, SettingsPage, StatsPage,
                    UpdatePage)
from .widgets import StatusBox, ToggleSwitch, label

log = logging.getLogger("macropad.ui")

MENU = [("home", HomePage), ("keys", KeysPage), ("leds", LedsPage), ("language", LanguagePage),
        ("update", UpdatePage), ("guide", GuidePage), ("display", DisplayPage), ("stats", StatsPage),
        ("settings", SettingsPage)]


def app_icon() -> QIcon:
    p = paths.resource("icon.png")
    if p.exists():
        return QIcon(str(p))
    pm = QPixmap(64, 64)               # fallback: a little purple key pad
    pm.fill(Qt.transparent)
    g = QPainter(pm)
    g.setRenderHint(QPainter.Antialiasing)
    g.setBrush(QColor(theme.ACCENT))
    g.setPen(Qt.NoPen)
    g.drawRoundedRect(2, 2, 60, 60, 14, 14)
    g.setBrush(QColor("white"))
    for r in range(3):
        for c in range(3):
            g.drawRoundedRect(11 + c * 15, 11 + r * 15, 11, 11, 3, 3)
    g.end()
    return QIcon(pm)


class _Bridge(QObject):
    """Carries results from worker threads into the window's thread."""
    update_checked = Signal(object, str, bool)       # release or None, error, manual
    download_progress = Signal(float, object)
    download_done = Signal(object, str)               # path or None, error
    flash_progress = Signal(float, object)
    flash_stage = Signal(str)
    flash_done = Signal(bool, str)
    files_checked = Signal(object)                    # dict


class MainWindow(QMainWindow):
    def __init__(self, settings, start_hidden=False):
        super().__init__()
        self.settings = settings
        self.draft = settings.copy()
        set_language(self.draft["app_language"])
        self.bridge = _Bridge()
        self.link = PadLink(knob_app_volume=settings.data["knob_target"] == "app", player=settings.data["player"])
        self.link_status = "searching"
        self.pad_firmware = None          # None = not connected, "" = old firmware, else version
        self.now_playing = ("", "", "")
        self.media_available = True
        self.applying = False
        self.flashing = False
        self.apply_dialog = None
        self.latest = None
        self.update_text = ""
        self.update_busy = False
        self.repair_text = ""
        self.repair_needed = False
        self.repair_release = None
        self._cancel = threading.Event()
        self.stats = KeyStats(paths.stats_file())
        import os
        import sys
        self._own_exe = os.path.basename(sys.executable).lower()
        self.active_profile = None        # index of the profile for the program in front
        self.program = ""                 # that program
        self.locked = False
        self.mic_muted = None
        self.runner = ActionRunner(self.link, lambda: (self.settings.data, self.active_profile), self,
                                   on_app=self._app_action)
        self.focus = focus.FocusTimer(settings.data["display"]["options"]["timer"], self)
        self.pcstats = None               # started when first needed
        self.picture_pending = False      # a new own picture waits for Apply
        self._upload_dialog = None
        self._clock_sent = 0.0
        live.lang = 1 if settings.data["pad_language"] == "de" else 0
        live.timer = (self.focus.left, self.focus.total, 0, 0, False)
        live.set_picture(picture.load())
        try:
            self.bundle = flasher.load_bundle()
        except flasher.FlashError as e:
            log.info("No firmware bundle: %s", e)
            self.bundle = None

        self.setWindowTitle(T("app_title"))
        self.setWindowIcon(app_icon())
        self.resize(1160, 760)
        self.setMinimumSize(980, 640)
        self._build()
        self._make_tray()
        self._wire()
        self.link.start()
        self._sync_autostart()
        if updater.due_for_check(self.settings.data) and UPDATE_REPO:
            QTimer.singleShot(4000, lambda: self.check_updates(manual=False))
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._periodic)
        self._update_timer.start(60 * 60 * 1000)
        self._watch_timer = QTimer(self)          # program in front (profiles), lock screen
        self._watch_timer.timeout.connect(self._watch)
        self._watch_timer.start(500)
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self.stats.flush)
        self._stats_timer.start(30000)
        self._second = QTimer(self)               # PC stats and the clock for the widgets
        self._second.timeout.connect(self._each_second)
        self._second.start(1000)
        self.focus.changed.connect(self._focus_changed)
        self.focus.phase_ended.connect(self._focus_phase_ended)
        if not start_hidden:
            self.show()

    # ----- layout -------------------------------------------------------------
    def _build(self):
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.setCentralWidget(root)
        h.addWidget(self._build_sidebar())
        self.background = Background()
        self.background.set_style(self.draft["display"], self.draft["lights"]["colour"])
        h.addWidget(self.background, 1)
        content = QVBoxLayout(self.background)
        content.setContentsMargins(0, 18, 0, 18)
        content.setSpacing(6)
        title = QLabel("MACRO PAD")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        content.addWidget(title)
        self.stack = QStackedWidget()
        self.pages = {}
        for key, cls in MENU:
            page = cls(self)
            self.pages[key] = page
            self.stack.addWidget(page)
        content.addWidget(self.stack, 1)
        row = QHBoxLayout()
        row.addStretch()
        self.unsaved = label("", "Note", wrap=False)
        row.addWidget(self.unsaved)
        row.addSpacing(10)
        self.apply_btn = QPushButton(T("apply"))
        self.apply_btn.setObjectName("Apply")
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.clicked.connect(self.apply)
        row.addWidget(self.apply_btn)
        row.addStretch()
        content.addLayout(row)
        self._select("home")
        self.changed(refresh_pages=False)

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(250)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 18, 14, 16)
        v.setSpacing(4)
        self.menu_buttons = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, _ in MENU:
            icon = {"home": "\u2302  ", "settings": "\u2699  "}.get(key, "\u25B8  ")
            b = QPushButton(icon + T(f"menu_{key}").replace("&", "&&"))
            b.setObjectName("MenuItem")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._select(k))
            group.addButton(b)
            v.addWidget(b)
            self.menu_buttons[key] = b
        v.addStretch(1)
        line = QFrame()
        line.setObjectName("SideLine")
        v.addWidget(line)
        v.addSpacing(8)
        v.addWidget(label(T("pad_status"), "SmallLabel"))
        self.status_box = StatusBox()
        v.addWidget(self.status_box)
        v.addSpacing(10)
        row = QHBoxLayout()
        row.addWidget(label(T("autostart"), wrap=False))
        row.addStretch()
        self.autostart = ToggleSwitch(checked=self.settings.data["autostart"])
        self.autostart.toggled.connect(self._autostart_toggled)
        row.addWidget(self.autostart)
        v.addLayout(row)
        v.addSpacing(8)
        v.addWidget(label(T("version", v=VERSION), "Version"))
        return side

    def _select(self, key):
        idx = [k for k, _ in MENU].index(key)
        self.stack.setCurrentIndex(idx)
        self.menu_buttons[key].setChecked(True)
        self.pages[key].refresh()

    def _rebuild(self):
        """After a language change: build the whole window again with the new texts."""
        current = MENU[self.stack.currentIndex()][0]
        old = self.centralWidget()
        set_language(self.settings.data["app_language"])
        self.setWindowTitle(T("app_title"))
        self._build()
        old.deleteLater()
        self._select(current)
        self._show_status()
        self._update_tray_texts()

    # ----- tray ---------------------------------------------------------------
    def _make_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        self.act_open = QAction(T("tray_open"), self)
        self.act_quit = QAction(T("tray_quit"), self)
        self.act_open.triggered.connect(self.show_window)
        self.act_quit.triggered.connect(self.quit_app)
        menu.addAction(self.act_open)
        menu.addSeparator()
        menu.addAction(self.act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_window() if r in (QSystemTrayIcon.Trigger,
                                                                          QSystemTrayIcon.DoubleClick) else None)
        self.tray.setToolTip(T("app_title"))
        self.tray.show()
        self._tray_hint_shown = False

    def _update_tray_texts(self):
        if self.tray:
            self.act_open.setText(T("tray_open"))
            self.act_quit.setText(T("tray_quit"))

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        # closing the window keeps the app (and the pad's music info) running in the tray
        if self.tray is not None and not getattr(self, "_quitting", False):
            e.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self.tray.showMessage(T("app_title"), T("tray_running"), app_icon(), 4000)
                self._tray_hint_shown = True
            return
        self._shutdown()
        e.accept()

    def quit_app(self):
        if self.flashing:
            return                  # never quit in the middle of flashing
        self._quitting = True
        self._shutdown()
        QApplication.quit()

    def _shutdown(self):
        try:
            self.stats.flush()
        except Exception:
            pass
        try:
            self.link.stop()
        except Exception:
            pass
        if self.tray:
            self.tray.hide()

    # ----- pad link -----------------------------------------------------------
    def _wire(self):
        self.link.status_changed.connect(self._link_status)
        self.link.info_received.connect(self._pad_info)
        self.link.apply_finished.connect(self._apply_finished)
        self.link.pad_lights_changed.connect(self._pad_lights)
        self.link.now_playing.connect(self._now_playing)
        self.link.music_state.connect(self._music_state)
        self.link.music_level.connect(self._music_level)
        self.link.key_event.connect(self._key_event)
        self.link.mic_muted.connect(self._mic_changed)
        self.link.picture_progress.connect(self._picture_progress)
        self.link.picture_done.connect(self._picture_done)
        b = self.bridge
        b.update_checked.connect(self._update_checked)
        b.download_progress.connect(lambda f, s: self._progress and self._progress.set_progress(f, s))
        b.download_done.connect(self._download_done)
        b.flash_progress.connect(lambda f, s: self._progress and self._progress.set_progress(f, s))
        b.flash_stage.connect(lambda t: self._progress and self._progress.set_stage(t))
        b.flash_done.connect(self._flash_done)
        b.files_checked.connect(self._files_checked)
        self._progress = None

    def _link_status(self, status):
        self.link_status = status
        if status != "connected":
            self.pad_firmware = None
        self._show_status()
        self.pages["update"].refresh()

    def _show_status(self):
        status = "busy" if (self.applying or self.flashing) else self.link_status
        self.status_box.set_status(status, T({"connected": "st_connected", "searching": "st_searching",
                                              "busy": "st_busy", "disconnected": "st_disconnected"}[status]))

    # ----- keys, profiles, microphone, lock --------------------------------------
    def _key_event(self, key, down, layer2, app):
        if down:
            self.stats.count(key, layer2)
            self.background.poke()                    # the app's background reacts too
        self.runner.key_event(key, down, layer2, app)

    def _watch(self):
        program = winsys.foreground_program()
        own = program and program == getattr(self, "_own_exe", None)
        if program and not own and program != self.program:
            self.program = program
            profile = config.active_profile(self.settings.data, program)
            if profile != self.active_profile:
                self.active_profile = profile
                self._send_pad_state(overlay=True, lights=True, lock=False)
                page = self.pages.get("keys")
                if page is not None and page.isVisible():
                    page.refresh()
        locked = winsys.screen_locked() if self.settings.data["sleep"]["when_locked"] else False
        if locked != self.locked:
            self.locked = locked
            self._send_pad_state(overlay=False, lights=False, lock=True)

    # ----- widgets: PC stats, clock, focus timer, own picture ---------------------
    def _proto4(self):
        return self.link_status == "connected" and self._pad_proto() >= 4

    def _each_second(self):
        s = self.settings.data["display"]
        on_pad = self._proto4() and s["animation"] and s["background"] == "stats"
        page = self.pages.get("display")
        previews = page is not None and page.isVisible() and self.draft["display"]["animation"]
        in_app = self.background.mode == "native" and self.draft["display"]["background"] == "stats"
        if on_pad or previews or in_app:
            if self.pcstats is None:
                self.pcstats = PcStats()
            live.stats = self.pcstats.sample()
            if on_pad:
                self.link.send([protocol.stats_line(*live.stats)])
        now = time.monotonic()
        if self._proto4() and now - self._clock_sent > 600:      # keeps the pad's clock right
            self._clock_sent = now
            self.link.send([protocol.month_line(time.localtime().tm_mon, protocol.local_epoch())])

    def _app_action(self, name):
        if name == "timer":
            self.focus.toggle()
        elif name == "timer_skip":
            self.focus.skip()

    def _focus_changed(self):
        f = self.focus
        live.timer = (f.left, f.total, f.phase, f.round, f.paused)
        if self._proto4():
            self.link.send([protocol.timer_line(f.left, f.total, f.phase, f.round, f.paused)])

    def _focus_phase_ended(self, ended, new):
        if self.tray is not None:
            text = T("timer_break_now") if new in (focus.BREAK, focus.LONG_BREAK) else T("timer_focus_now")
            self.tray.showMessage(T("app_title"), text, app_icon(), 5000)

    def picture_changed(self):
        self.picture_pending = True
        self.changed()

    def _upload_picture_if_needed(self):
        pic = live.picture
        s = self.settings.data["display"]
        if pic is None or not self._proto4():
            return
        if self.picture_pending or (s["animation"] and s["background"] == "picture"):
            self.link.upload_picture(pic)

    def _picture_progress(self, done, total):
        if self._upload_dialog is None:
            self._upload_dialog = dialogs.ProgressDialog(self, T("pic_upload"))
            self._upload_dialog.set_stage(T("pic_upload_stage"))
            self._upload_dialog.cancel_requested.connect(self.link.cancel_picture)
            self._upload_dialog.open()
            self._upload_start = time.monotonic()
        frac = done / total if total else 0
        elapsed = time.monotonic() - self._upload_start
        self._upload_dialog.set_progress(frac, elapsed / frac - elapsed if frac > 0.05 else None)

    def _picture_done(self, ok, why):
        if ok:
            self.picture_pending = False
            self.changed()
        else:
            log.info("Picture not sent: %s", why)
        if self._upload_dialog is not None:
            self._upload_dialog.finish(T("pic_sent") if ok else T("pic_not_sent", why=why))
            self._upload_dialog = None
        elif not ok and why not in ("cancelled", "not connected"):
            dialogs.info(self, T("pic_not_sent", why=why))

    def _mic_changed(self, state):
        self.mic_muted = state
        self._send_pad_state(overlay=False, lights=True, lock=False)

    def _send_pad_state(self, overlay=True, lights=True, lock=True):
        """What the pad keeps only in memory: the profile, key lights, lock state."""
        if self.link_status != "connected" or self._pad_proto() < 3:
            return
        s = self.settings.data
        lines = []
        if overlay:
            lines += protocol.overlay_lines(s, self.active_profile)
        if lights:
            lines.append(protocol.CLEAR_HIGHLIGHTS)
            if self.mic_muted is not None:
                layout = s["profiles"][self.active_profile]["keys"] if self.active_profile is not None else s["keys"]
                for i, aid in enumerate(layout):
                    if aid == "app:mic_mute":
                        lines.append(protocol.highlight_line(i, "#FF0000" if self.mic_muted else "#00C853"))
        if lock:
            lines.append(protocol.locked_line(self.locked))
            if self._pad_proto() >= 4:
                f = self.focus
                lines.append(protocol.timer_line(f.left, f.total, f.phase, f.round, f.paused))
        if lines:
            self.link.send(lines)

    def _music_level(self, level):
        self.background.set_level(level)
        page = self.pages.get("display")
        if page is not None:
            page.set_level(level)

    def _pad_proto(self):
        """Settings protocol of the connected pad (1 = firmware 2.0)."""
        info = self.link.info
        return info.protocol if info is not None else 1

    def _pad_info(self, info):
        self.pad_firmware = info.firmware if info else ""
        if info is not None:
            if self.settings.data["pad_sync_pending"]:
                log.info("Sending settings that were changed while the pad was away")
                self.applying = True
                self._show_status()
                self.apply_btn.setText(T("applying"))
                self.link.apply(protocol.settings_lines(self.settings.data, self._pad_proto()))
            else:
                self._adopt_pad_lights(info.mode, info.brightness, info.colour)
            self._send_pad_state()
        self.pages["update"].refresh()
        self.pages["display"].refresh()
        if self.firmware_outdated:
            self.menu_buttons["update"].setText("▸  " + T("menu_update").replace("&", "&&") + "  ●")

    def _adopt_pad_lights(self, mode, brightness, colour):
        """Light mode / brightness / colour changed with the keys on the pad."""
        saved = self.settings.data["lights"]
        same_draft = self.draft["lights"] == saved
        trial = copy.deepcopy(self.settings.data)
        # take only values that make sense here (an odd answer is simply ignored)
        if config.mode_available(trial, mode):
            trial["lights"]["mode"] = mode
        if 10 <= brightness <= 100:
            trial["lights"]["brightness"] = brightness
        if 0 <= colour < config.COLOUR_COUNT:
            trial["lights"]["colour"] = colour
        trial = config.validate(trial)
        if trial["lights"] == saved:
            return
        self.settings.data["lights"] = trial["lights"]
        self.settings.save()
        if same_draft:
            self.draft["lights"] = copy.deepcopy(trial["lights"])
            self.pages["leds"].refresh()
        self.changed(refresh_pages=False)

    def _pad_lights(self, mode, brightness, colour):
        self._adopt_pad_lights(mode, brightness, colour)

    def _music_state(self, ok, why):
        self.media_available = ok
        if not ok:
            log.info("No music info: %s", why)
        self.pages["home"].refresh()

    def _now_playing(self, player, title, artist):
        self.now_playing = (player, title, artist)
        self.pages["home"].refresh()

    @property
    def firmware_outdated(self):
        if not self.bundle or self.link_status != "connected" or self.pad_firmware is None:
            return False
        return self.pad_firmware == "" or protocol.is_newer(self.bundle.version, self.pad_firmware)

    # ----- editing & apply ----------------------------------------------------
    @staticmethod
    def _user_part(data):
        """The settings the user edits on the pages (not the app's own bookkeeping)."""
        d = config.validate(data)
        for k in ("pad_sync_pending", "updates", "autostart"):
            d.pop(k, None)
        return d

    def changed(self, refresh_pages=False):
        if refresh_pages:
            for page in self.pages.values():
                page.refresh()
        dirty = self._user_part(self.draft) != self._user_part(self.settings.data) or getattr(
            self, "picture_pending", False)
        pending = self.settings.data["pad_sync_pending"]
        self.apply_btn.setEnabled((dirty or pending) and not self.applying and not self.flashing)
        self.unsaved.setText(T("unsaved_hint") if dirty else "")
        self.background.set_style(self.draft["display"], self.draft["lights"]["colour"])

    def apply(self):
        new = config.validate(self.draft)
        lang_changed = new["app_language"] != self.settings.data["app_language"]
        new["pad_sync_pending"] = True
        new["autostart"] = self.settings.data["autostart"]
        new["updates"] = self.settings.data["updates"]
        if not self.settings.replace(new):
            dialogs.info(self, T("err_save", path=self.settings.path))
            return
        self.draft = self.settings.copy()
        self.link.set_knob_target(new["knob_target"] == "app")
        if lang_changed:
            self._rebuild()
        if self.link_status == "connected" and self.pad_firmware:
            self.applying = True
            self._show_status()
            self.apply_btn.setText(T("applying"))
            self.apply_btn.setEnabled(False)
            self.apply_dialog = dialogs.ApplyDialog(self, seconds=2)
            self.apply_dialog.open()
            self.link.apply(protocol.settings_lines(self.settings.data, self._pad_proto()))
        elif self.link_status == "connected" and self.pad_firmware == "":
            dialogs.info(self, T("apply_old_fw"))
        else:
            dialogs.info(self, T("apply_offline"))
        self.changed()

    def _apply_finished(self, ok, detail):
        self.applying = False
        if ok:
            self.settings.data["pad_sync_pending"] = False
            self.settings.save()
            self.active_profile = config.active_profile(self.settings.data, self.program)
            self._send_pad_state()
            self.focus.set_minutes(self.settings.data["display"]["options"]["timer"])
            live.lang = 1 if self.settings.data["pad_language"] == "de" else 0
            self._upload_picture_if_needed()
        else:
            log.info("Apply failed: %s", detail)
        self.apply_btn.setText(T("apply"))
        self._show_status()
        self.changed()
        if self.apply_dialog is not None:
            self.apply_dialog.finish(ok, T("apply_done") if ok else T("apply_failed", why=detail))
            self.apply_dialog = None

    def _autostart_toggled(self, on):
        self.settings.data["autostart"] = on
        self.draft["autostart"] = on
        self.settings.save()
        winsys.set_autostart(on)

    def _sync_autostart(self):
        import sys
        if getattr(sys, "frozen", False) and self.settings.data["autostart"] != winsys.autostart_enabled():
            winsys.set_autostart(self.settings.data["autostart"])

    # ----- updates -----------------------------------------------------------
    def _periodic(self):
        if UPDATE_REPO and updater.due_for_check(self.settings.data):
            self.check_updates(manual=False)

    def check_updates(self, manual=True):
        if not UPDATE_REPO:
            self.update_text = T("upd_off")
            self.pages["update"].refresh()
            return
        if self.update_busy:
            return
        self.update_busy = True
        self.update_text = T("upd_checking")
        self.pages["update"].refresh()

        def work():
            try:
                rel = updater.latest_release(UPDATE_REPO)
                self.bridge.update_checked.emit(rel, "", manual)
            except Exception as e:
                self.bridge.update_checked.emit(None, str(e), manual)
        threading.Thread(target=work, daemon=True).start()

    def _update_checked(self, rel, error, manual):
        self.update_busy = False
        self.settings.data["updates"]["last_check"] = time.time()
        self.settings.save()
        if rel is None:
            self.update_text = T("upd_error", e=error)
        else:
            self.latest = rel
            if rel.newer:
                self.update_text = T("upd_avail", v=rel.version)
                self.menu_buttons["update"].setText("▸  " + T("menu_update").replace("&", "&&") + "  ●")
                if not manual and self.tray and rel.version != self.settings.data["updates"]["skip_version"]:
                    self.tray.showMessage(T("app_title"), T("upd_avail", v=rel.version), app_icon(), 6000)
            else:
                self.update_text = T("upd_none")
        self.pages["update"].refresh()

    def start_update(self, release=None):
        rel = release or self.latest
        if not rel or self._progress is not None:
            return
        self._cancel.clear()
        self._progress = dialogs.ProgressDialog(self, T("prog_download"))
        self._progress.set_stage(T("prog_download") + f"  (v{rel.version})")
        self._progress.cancel_requested.connect(self._cancel.set)
        self._progress.finished.connect(self._progress_closed)
        self._progress.open()
        start = time.monotonic()

        def progress(done, total):
            frac = done / total if total else 0.0
            elapsed = time.monotonic() - start
            left = elapsed / frac - elapsed if frac > 0.03 else None
            self.bridge.download_progress.emit(frac, left)

        def work():
            try:
                path = updater.download(rel, progress, self._cancel)
                self.bridge.download_done.emit(path, "")
            except updater.Cancelled:
                self.bridge.download_done.emit(None, T("cancelled"))
            except Exception as e:
                self.bridge.download_done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _progress_closed(self, *_):
        self._progress = None

    def _download_done(self, path, error):
        if self._progress is None:
            return
        if path is None:
            self._progress.finish(error if error == T("cancelled") else T("upd_error", e=error))
            return
        self._progress.finish(T("prog_install"))
        try:
            if updater.start_installer(path):
                QTimer.singleShot(1500, self.quit_app)
        except updater.UpdateError as e:
            self._progress.finish(T("upd_error", e=e))

    # ----- firmware ------------------------------------------------------------
    def flash_firmware(self):
        if not self.bundle or self.flashing or self._progress is not None:
            return
        if not dialogs.ask(self, T("fw_flash_q", v=self.bundle.version, s=self.bundle.estimate_seconds())):
            return
        self.flashing = True
        self._cancel.clear()
        self._show_status()
        self.changed()
        # the pad comes back with this firmware: send the settings to it afterwards
        self.settings.data["pad_sync_pending"] = True
        self.settings.save()
        self._progress = dialogs.ProgressDialog(self, T("prog_flash"), confirm_cancel=T("prog_cancel_q"))
        self._progress.cancel_requested.connect(self._cancel.set)
        self._progress.finished.connect(self._progress_closed)
        self._progress.open()
        bundle, link, bridge, cancel = self.bundle, self.link, self.bridge, self._cancel
        was_connected = self.link_status == "connected"

        def work():
            try:
                bridge.flash_stage.emit(T("prog_bootloader"))
                before = flasher.rom_ports()
                link.pause(enter_bootloader=was_connected)
                port = flasher.wait_for_rom_port(20, cancel, before=before)
                if cancel.is_set():
                    raise flasher.FlashError(T("cancelled"))
                if not port:
                    raise flasher.FlashError("the pad did not show up in update mode - unplug it, hold BOOT "
                                             "while plugging it back in, then try again")
                bridge.flash_stage.emit(T("prog_writing"))
                flasher.flash(bundle, port, lambda f, s: bridge.flash_progress.emit(f, s), cancel)
                bridge.flash_stage.emit(T("prog_reconnect"))
                flasher.wait_for_pad(25, cancel)
                bridge.flash_done.emit(True, T("flash_ok", v=bundle.version))
            except Exception as e:
                msg = str(e)
                bridge.flash_done.emit(False, T("cancelled") if msg == "cancelled" else T("flash_failed", e=msg))
            finally:
                link.resume()
        threading.Thread(target=work, daemon=True).start()

    def _flash_done(self, ok, text):
        self.flashing = False
        self._show_status()
        self.changed()
        if ok:
            self.menu_buttons["update"].setText("▸  " + T("menu_update").replace("&", "&&"))
        if self._progress is not None:
            self._progress.finish(text)
        self.pages["update"].refresh()

    # ----- settings page ----------------------------------------------------------
    def reset_settings(self):
        """Everything back to the defaults (in the draft: Apply keeps it). The app
        languages, autostart and update settings stay as they are."""
        fresh = config.defaults()
        for keep in ("app_language", "pad_language", "autostart", "updates", "pad_sync_pending"):
            fresh[keep] = copy.deepcopy(self.settings.data[keep])
        self.draft = fresh
        for page in self.pages.values():
            page.refresh()
        self.changed()

    def uninstall(self, delete_data):
        if self.flashing:
            return
        unins = winsys.find_uninstaller()
        if unins is None:
            dialogs.info(self, T("set_uninst_missing"))
            return
        if not dialogs.ask(self, T("set_uninst_q_data" if delete_data else "set_uninst_q")):
            return
        self.link.stop()
        winsys.set_autostart(False)
        if delete_data:
            winsys.delete_user_data()
        try:
            winsys.run_uninstaller(unins)
        except OSError as e:
            dialogs.info(self, T("set_uninst_failed", e=e))
            self.link.start()
            return
        self.quit_app()

    # ----- repair ---------------------------------------------------------------
    def check_files(self):
        self.repair_text = T("upd_checking")
        self.repair_needed = False
        self.pages["update"].refresh()

        def work():
            result = {"ok": 0, "bad": [], "against": "", "error": "", "release": None}
            try:
                manifest = None
                if UPDATE_REPO:
                    try:
                        rel = updater.latest_release(UPDATE_REPO)
                        result["release"] = rel
                        if rel.newer:
                            result["newer"] = True
                        manifest = (rel.version, rel.files)
                    except updater.UpdateError as e:
                        result["error"] = str(e)
                if manifest is None or result.get("newer"):
                    import json
                    local = paths.install_dir() / "manifest.json"
                    if local.exists() and not result.get("newer"):
                        data = json.loads(local.read_text("utf-8"))
                        manifest = (data.get("version", VERSION), data.get("files", {}))
                if manifest and not result.get("newer"):
                    result["against"] = manifest[0]
                    result["ok"], result["bad"] = updater.check_files(manifest[1])
            except Exception as e:
                result["error"] = str(e)
            self.bridge.files_checked.emit(result)
        threading.Thread(target=work, daemon=True).start()

    def _files_checked(self, r):
        self.repair_release = r.get("release")
        if r.get("newer"):
            self.repair_text = T("repair_newer")
            self.repair_needed = True
        elif r["against"]:
            if r["bad"]:
                shown = ", ".join(r["bad"][:5]) + (" ..." if len(r["bad"]) > 5 else "")
                self.repair_text = T("repair_bad", n=len(r["bad"])) + f"  ({shown})"
                self.repair_needed = bool(self.repair_release)
            else:
                self.repair_text = T("repair_ok", n=r["ok"]) + "  ·  " + T("repair_source", v=r["against"])
        else:
            self.repair_text = T("upd_error", e=r["error"] or T("upd_off"))
        self.pages["update"].refresh()

    def repair(self):
        if self.repair_release:
            self.start_update(self.repair_release)
