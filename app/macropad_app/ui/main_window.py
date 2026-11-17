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
from .pages import DisplayPage, GuidePage, HomePage, KeysPage, LanguagePage, LedsPage, UpdatePage
from .widgets import StatusBox, ToggleSwitch, label

log = logging.getLogger("macropad.ui")

MENU = [("home", HomePage), ("keys", KeysPage), ("leds", LedsPage), ("language", LanguagePage),
        ("update", UpdatePage), ("guide", GuidePage), ("display", DisplayPage)]


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
        d = self.draft["display"]
        self.background.set_style(d["background"], d["fish"])
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
            b = QPushButton(("▸  " if key != "home" else "⌂  ") + T(f"menu_{key}").replace("&", "&&"))
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

    def _pad_info(self, info):
        self.pad_firmware = info.firmware if info else ""
        if info is not None:
            if self.settings.data["pad_sync_pending"]:
                log.info("Sending settings that were changed while the pad was away")
                self.applying = True
                self._show_status()
                self.apply_btn.setText(T("applying"))
                self.link.apply(protocol.settings_lines(self.settings.data))
            else:
                self._adopt_pad_lights(info.mode, info.brightness, info.colour)
        self.pages["update"].refresh()
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
        for k in ("pad_sync_pending", "updates", "autostart", "start_minimized"):
            d.pop(k, None)
        return d

    def changed(self, refresh_pages=False):
        dirty = self._user_part(self.draft) != self._user_part(self.settings.data)
        pending = self.settings.data["pad_sync_pending"]
        self.apply_btn.setEnabled((dirty or pending) and not self.applying and not self.flashing)
        self.unsaved.setText(T("unsaved_hint") if dirty else "")
        d = self.draft["display"]
        if (self.background.mode, self.background.fish_on) != (d["background"], d["fish"]):
            self.background.set_style(d["background"], d["fish"])

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
            self.link.apply(protocol.settings_lines(self.settings.data))
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
