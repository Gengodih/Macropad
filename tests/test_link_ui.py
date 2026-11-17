"""Tests for the USB link (with a pretend pad on a pseudo terminal) and the
window (rendered offscreen). Run:  python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["MACROPAD_HOME"] = tempfile.mkdtemp()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from macropad_app import config, device, keys, protocol  # noqa: E402

APP = QApplication.instance() or QApplication([])


class FakePad:
    """Answers like the firmware: '?' -> I-line, settings counted, 'W' -> A|W|n|0."""

    def __init__(self, answer=True, reject_prefix=None):
        import pty
        self.master, slave = pty.openpty()
        self.port = os.ttyname(slave)
        self._slave = slave
        self.answer = answer
        self.reject_prefix = reject_prefix
        self.received = []
        self.saves = 0
        self.stop = False
        self.proto = 1
        self.picture = bytearray()          # what an upload wrote
        self.picture_crc = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        buf = b""
        count = rejected = 0
        while not self.stop:
            try:
                data = os.read(self.master, 4096)
            except OSError:
                return
            buf += data
            while b"\n" in buf:
                line, rest = buf.split(b"\n", 1)
                if line.startswith(b"IC|"):              # picture part: raw bytes follow
                    off, n = (int(x) for x in line[3:].split(b"|"))
                    if len(rest) < n:
                        break                            # wait for the rest
                    self.picture[off:off + n] = rest[:n]
                    buf = rest[n:]
                    os.write(self.master, f"IK|{off}|1\n".encode())
                    continue
                buf = rest
                self.received.append(line)
                if not self.answer:
                    continue
                if line == b"IP":
                    os.write(self.master, f"IP|{self.picture_crc}|1\n".encode())
                elif line.startswith(b"IB|"):
                    self.picture = bytearray()
                    os.write(self.master, b"IR\n")
                elif line.startswith(b"IE|"):
                    import zlib
                    ok = int(line[3:]) == zlib.crc32(bytes(self.picture))
                    if ok:
                        self.picture_crc = int(line[3:])
                    os.write(self.master, b"IA|1\n" if ok else b"IA|0|crc\n")
                elif line == b"?":
                    os.write(self.master, f"I|2.0.0|{self.proto}|0|4|70|3\n".encode())
                elif line == b"W":
                    self.saves += 1
                    os.write(self.master, f"A|W|{count}|{rejected}\n".encode())
                    count = rejected = 0
                elif line[:2] in (b"K|", b"G|", b"D|", b"N|") or line[:3] in (
                        b"LE|", b"LS|", b"LP|", b"LB|", b"LM|", b"K2|", b"TO|"):
                    if self.reject_prefix and line.startswith(self.reject_prefix):
                        rejected += 1
                        os.write(self.master, b"A|E|" + line[:12] + b"\n")
                    else:
                        count += 1

    def close(self):
        self.stop = True
        for fd in (self.master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass


def wait_for(cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        APP.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@unittest.skipUnless(sys.platform.startswith("linux"), "needs a pseudo terminal")
class LinkTests(unittest.TestCase):
    def run_link(self, pad):
        link = device.PadLink()
        events = {"status": [], "info": [], "apply": [], "lights": []}
        link.status_changed.connect(lambda s: events["status"].append(s), Qt.DirectConnection)
        link.info_received.connect(lambda i: events["info"].append(i), Qt.DirectConnection)
        link.apply_finished.connect(lambda ok, d: events["apply"].append((ok, d)), Qt.DirectConnection)
        link.pad_lights_changed.connect(lambda *a: events["lights"].append(a), Qt.DirectConnection)
        patcher = mock.patch.object(device, "pad_ports", return_value=[(pad.port, 0x1001)])
        patcher.start()
        self.addCleanup(patcher.stop)
        link.start()
        self.addCleanup(link.stop)
        return link, events

    def test_connect_info_and_apply(self):
        pad = FakePad()
        self.addCleanup(pad.close)
        link, ev = self.run_link(pad)
        self.assertTrue(wait_for(lambda: ev["info"]), ev)
        self.assertEqual(ev["info"][0].firmware, "2.0.0")
        self.assertIn("connected", ev["status"])
        s = config.defaults()
        s["keys"][0] = "sc:copy"
        link.apply(protocol.settings_lines(s))
        self.assertTrue(wait_for(lambda: ev["apply"]), ev)
        self.assertEqual(ev["apply"][0], (True, ""))
        self.assertIn(b"K|0|0|6|1|Copy", pad.received)
        # keep-alive lines go out (the pad's "app is running" signal)
        self.assertTrue(wait_for(lambda: any(r.startswith(b"S|") for r in pad.received)))

    def test_rejected_settings_are_retried_then_reported(self):
        pad = FakePad(reject_prefix=b"LB|")
        self.addCleanup(pad.close)
        link, ev = self.run_link(pad)
        self.assertTrue(wait_for(lambda: ev["info"]))
        link.apply(protocol.settings_lines(config.defaults()))
        self.assertTrue(wait_for(lambda: ev["apply"], 10), ev)
        ok, detail = ev["apply"][0]
        self.assertFalse(ok)
        self.assertIn("LB|", detail)
        self.assertEqual(pad.saves, 2)                 # one retry

    def test_old_firmware_and_silent_pad(self):
        pad = FakePad(answer=False)
        self.addCleanup(pad.close)
        link, ev = self.run_link(pad)
        self.assertTrue(wait_for(lambda: ev["info"], 5))
        self.assertIsNone(ev["info"][0])               # old firmware: no answer to "?"
        link.apply([b"G|1\n"])
        self.assertTrue(wait_for(lambda: ev["apply"], 10))
        self.assertEqual(ev["apply"][0], (False, "the pad did not answer"))

    def test_pause_frees_the_port(self):
        pad = FakePad()
        self.addCleanup(pad.close)
        link, ev = self.run_link(pad)
        self.assertTrue(wait_for(lambda: ev["info"]))
        self.assertTrue(link.pause(enter_bootloader=True, timeout=5))
        self.assertIn(b"!BOOT", pad.received)
        self.assertEqual(link.status, "busy")
        link.resume()
        self.assertTrue(wait_for(lambda: link.status == "connected", 6))

    def test_unplug_is_survived(self):
        pad = FakePad()
        link, ev = self.run_link(pad)
        self.assertTrue(wait_for(lambda: ev["info"]))
        pad.close()                                    # "unplugged"
        with mock.patch.object(device, "pad_ports", return_value=[]):
            self.assertTrue(wait_for(lambda: link.status in ("searching", "disconnected"), 8), ev["status"])


class WindowTests(unittest.TestCase):
    def setUp(self):
        from macropad_app.ui import dialogs, main_window
        self.dialogs = dialogs
        p1 = mock.patch.object(dialogs, "info", lambda *a, **k: None)
        p2 = mock.patch.object(dialogs, "ask", lambda *a, **k: True)
        p3 = mock.patch.object(device.PadLink, "start", lambda self: None)
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)
        self.tmp = tempfile.mkdtemp()
        self.settings = config.Settings(Path(self.tmp) / "settings.json")
        self.win = main_window.MainWindow(self.settings, start_hidden=True)
        self.addCleanup(self.win.quit_app)

    def test_all_pages_render_in_both_languages(self):
        from macropad_app.ui.main_window import MENU
        for lang in ("en", "de"):
            self.win.settings.data["app_language"] = lang
            self.win._rebuild()
            for key, _ in MENU:
                self.win._select(key)
                APP.processEvents()
                self.assertFalse(self.win.grab().isNull())

    def test_edit_and_apply_offline_keeps_pending(self):
        w = self.win
        self.assertFalse(w.apply_btn.isEnabled())
        w.draft["keys"][2] = "sc:paste"
        w.changed()
        self.assertTrue(w.apply_btn.isEnabled())
        w.apply()
        self.assertEqual(self.settings.data["keys"][2], "sc:paste")
        self.assertTrue(self.settings.data["pad_sync_pending"])
        self.assertTrue(config.Settings(self.settings.path).data["pad_sync_pending"])

    def test_apply_connected_and_finish(self):
        w = self.win
        sent = []
        w.link.apply = lambda lines: sent.append(lines)
        w._link_status("connected")
        w._pad_info(protocol.PadInfo("2.0.0", 1, 0, 0, 60, 11))
        w.draft["display"]["animation"] = False
        w.changed()
        self.assertEqual(w.background.mode, "plain")         # live preview
        w.draft["display"]["animation"] = True
        w.draft["display"]["background"] = "fire"
        w.changed()
        self.assertEqual(w.background.mode, "native")
        w.draft["display"]["background"] = "aquarium"
        w.changed()
        self.assertEqual(w.background.mode, "aquarium")
        w.draft["display"]["animation"] = False
        w.changed()
        w.apply()
        self.assertTrue(sent)
        self.assertEqual(w.status_box.text(), "Don't disconnect")
        w._apply_finished(True, "")
        self.assertFalse(self.settings.data["pad_sync_pending"])
        self.assertEqual(w.status_box.text(), "Connected")
        self.assertFalse(w.apply_btn.isEnabled())

    def test_pending_settings_sent_when_pad_appears(self):
        w = self.win
        sent = []
        w.link.apply = lambda lines: sent.append(lines)
        self.settings.data["pad_sync_pending"] = True
        w._link_status("connected")
        w._pad_info(protocol.PadInfo("2.0.0", 1, 0, 0, 60, 11))
        self.assertEqual(len(sent), 1)

    def test_pad_light_changes_are_adopted(self):
        w = self.win
        w._link_status("connected")
        w._pad_info(protocol.PadInfo("2.0.0", 1, 0, 3, 90, 5))
        self.assertEqual((self.settings.data["lights"]["mode"], self.settings.data["lights"]["brightness"],
                          self.settings.data["lights"]["colour"]), (3, 90, 5))
        w._pad_lights(99, 500, 99)                           # nonsense from the pad is ignored
        self.assertEqual(self.settings.data["lights"]["mode"], 3)
        self.assertEqual(self.settings.data["lights"]["brightness"], 90)

    def test_old_firmware_marks_update(self):
        w = self.win
        w._link_status("connected")
        w._pad_info(None)
        self.assertTrue(w.firmware_outdated)
        self.assertIn("●", w.menu_buttons["update"].text())

    def test_led_page_scheme_lifecycle(self):
        w = self.win
        page = w.pages["leds"]
        with mock.patch.object(self.dialogs, "ask_text", return_value="Ocean"):
            for _ in range(11):
                page._new()
        self.assertEqual(len(w.draft["lights"]["schemes"]), 10)
        page._current_scheme = 2
        w.draft["lights"]["mode"] = config.MODE_CUSTOM + 5
        page._delete()
        self.assertEqual(w.draft["lights"]["mode"], config.MODE_CUSTOM + 4)   # moved up with its scheme
        page._current_scheme = 3
        w.draft["lights"]["mode"] = config.MODE_CUSTOM + 3
        page._delete()
        self.assertTrue(config.mode_available(w.draft, w.draft["lights"]["mode"]))
        self.assertEqual(config.validate(w.draft)["lights"]["schemes"], w.draft["lights"]["schemes"])

    def test_key_picker_returns_valid_actions(self):
        from macropad_app.ui.dialogs import ActionPicker
        d = ActionPicker(self.win, 0, "combo:3:K")
        self.assertEqual(d.result_id, "combo:3:K")
        d.mod_boxes[keys.WIN].setChecked(True)
        self.assertEqual(d.result_id, "combo:11:K")
        d.cats.setCurrentRow(2)
        lw = d.lists[2]
        d._picked(lw.item(0))
        self.assertTrue(keys.is_valid(d.result_id))
        d.reject()

    def test_settings_reset(self):
        w = self.win
        self.settings.data["app_language"] = "de"
        self.settings.data["keys"][0] = "sc:copy"
        w.draft = self.settings.copy()
        w.reset_settings()
        self.assertEqual(w.draft["keys"], keys.DEFAULT_LAYOUT)
        self.assertEqual(w.draft["app_language"], "de")
        self.assertTrue(w.apply_btn.isEnabled())
        w.draft["start_minimized"] = True
        w.changed()
        w.apply()
        self.assertTrue(config.Settings(self.settings.path).data["start_minimized"])

    def test_uninstall(self):
        from macropad_app import winsys
        w = self.win
        calls = []
        with mock.patch.object(winsys, "find_uninstaller", return_value=None):
            w.uninstall(True)                      # from source: only a message
        with mock.patch.object(winsys, "find_uninstaller", return_value=Path("C:/x/unins000.exe")), \
             mock.patch.object(winsys, "delete_user_data", lambda: calls.append("data")), \
             mock.patch.object(winsys, "set_autostart", lambda on: calls.append(("auto", on))), \
             mock.patch.object(winsys, "run_uninstaller", lambda p: calls.append(("run", p.name))), \
             mock.patch.object(w, "quit_app", lambda: calls.append("quit")):
            w.uninstall(True)
        self.assertEqual(calls, [("auto", False), "data", ("run", "unins000.exe"), "quit"])

    def test_delete_user_data(self):
        from macropad_app import paths, winsys
        import logging
        home = Path(tempfile.mkdtemp())
        with mock.patch.dict(os.environ, {"MACROPAD_HOME": str(home)}):
            (paths.user_dir() / "settings.json").write_text("{}")
            h = logging.FileHandler(paths.user_dir() / "macropad.log")
            logging.getLogger().addHandler(h)
            winsys.delete_user_data()
            self.assertFalse(home.exists())
            self.assertNotIn(h, logging.getLogger().handlers)

    def test_language_switch_rebuilds(self):
        w = self.win
        w.draft["app_language"] = "de"
        w.changed()
        w.apply()
        self.assertEqual(w.apply_btn.text(), "Anwenden")
        self.assertEqual(w.windowTitle(), "Macro Pad")


if __name__ == "__main__":
    unittest.main()


class ActionTests(unittest.TestCase):
    """Macros, tap / hold / double tap and profiles, with a fake link."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from macropad_app.actions import ActionRunner

        class Link:
            def __init__(self):
                self.sent, self.mic = [], 0

            def send(self, lines):
                self.sent += lines

            def toggle_mic(self):
                self.mic += 1
        self.link = Link()
        self.s = config.validate({
            "macros": {"m1": {"name": "M", "steps": [{"type": "keys", "action": "sc:copy"},
                                                     {"type": "delay", "ms": 10},
                                                     {"type": "keys", "action": "key:A"}]}},
            "multi": {"t1": {"name": "T", "tap": "key:B", "hold": "key:C", "double": "key:D"},
                      "t2": {"name": "T2", "tap": "key:E", "hold": "none", "double": "none"}},
            "keys": ["macro:m1", "multi:t1", "multi:t2", "app:mic_mute"] + ["none"] * 11,
            "profiles": [{"name": "P", "programs": ["game.exe"], "keys": ["key:G"] + ["none"] * 14}]})
        self.profile = None
        self.runner = ActionRunner(self.link, lambda: (self.s, self.profile))

    def wait(self, ms):
        from PySide6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def code(self, aid):
        return protocol.tap_line(aid)

    def test_macro_runs_its_steps_in_order(self):
        self.runner.key_event(0, True, False, True)
        self.runner.key_event(0, False, False, True)
        self.wait(300)
        self.assertEqual(self.link.sent, [self.code("sc:copy"), self.code("key:A")])

    @mock.patch("macropad_app.actions.DOUBLE_MS", 700)
    @mock.patch("macropad_app.actions.HOLD_MS", 500)
    def test_tap_hold_double(self):
        r = self.runner
        r.key_event(1, True, False, True); r.key_event(1, False, False, True)   # tap ...
        self.wait(1100)                                                      # ... no second tap
        self.assertEqual(self.link.sent, [self.code("key:B")])
        self.link.sent.clear()
        r.key_event(1, True, False, True); self.wait(900)                    # hold
        self.assertEqual(self.link.sent, [self.code("key:C")])
        r.key_event(1, False, False, True)
        self.assertEqual(self.link.sent, [self.code("key:C")])               # letting go adds nothing
        self.link.sent.clear()
        r.key_event(1, True, False, True); r.key_event(1, False, False, True)
        self.wait(80)
        r.key_event(1, True, False, True); r.key_event(1, False, False, True)  # double tap
        self.wait(1100)
        self.assertEqual(self.link.sent, [self.code("key:D")])

    def test_tap_without_double_is_instant(self):
        self.runner.key_event(2, True, False, True)
        self.runner.key_event(2, False, False, True)
        self.assertEqual(self.link.sent, [self.code("key:E")])

    def test_mic_profile_and_pad_keys(self):
        self.runner.key_event(3, True, False, True)
        self.assertEqual(self.link.mic, 1)
        self.runner.key_event(0, True, True, True)          # an old pad's layer-2 report: the normal key (macro)
        self.wait(300)
        self.assertEqual(self.link.sent[:2], [self.code("sc:copy"), self.code("key:A")])
        self.profile = 0
        self.runner.key_event(0, True, False, True)
        self.assertEqual(self.link.sent[-1], self.code("key:G"))
        n = len(self.link.sent)
        self.runner.key_event(5, True, False, False)        # not an app key: the pad did it
        self.assertEqual(len(self.link.sent), n)

    def test_overlay_and_stats(self):
        lines = protocol.overlay_lines(self.s, 0)
        self.assertEqual(lines[0], b"O|-\n")
        self.assertIn(b"O|0|0|10|0|G\n", lines)
        self.assertEqual(len(lines), 5)       # key 0 plus keys 1-3, which are "none" in the profile
        self.assertEqual(protocol.overlay_lines(self.s, None), [b"O|-\n"])
        from macropad_app.stats import KeyStats
        path = Path(tempfile.mkdtemp()) / "stats.json"
        st = KeyStats(path)
        for k in (0, 0, 4):
            st.count(k)
        st.count(1, layer2=True)
        st.flush()
        st2 = KeyStats(path)
        self.assertEqual(st2.totals(1)[:5], [2, 0, 0, 0, 1])
        self.assertEqual(st2.totals(None, layer2=True)[1], 1)
        path.write_text("{broken")
        self.assertEqual(KeyStats(path).totals(), [0] * 15)


class WidgetTests(unittest.TestCase):
    """Focus timer, picture conversion and upload, widget messages."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, ms):
        from PySide6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def test_focus_timer_cycle(self):
        from macropad_app import focus
        t = focus.FocusTimer({"focus": 1, "break": 1, "long": 2})
        ended = []
        t.phase_ended.connect(lambda a, b: ended.append((a, b)))
        self.assertEqual((t.phase, t.left), (focus.OFF, 60))
        t.toggle()
        self.assertEqual((t.phase, t.round, t.paused), (focus.FOCUS, 1, False))
        t.toggle()                                   # pause
        left = t.left
        self.wait(1100)
        self.assertAlmostEqual(t.left, left, delta=0.01)
        t.toggle()                                   # go on
        for r in range(1, 5):
            self.assertEqual(t.phase, focus.FOCUS)
            t.skip()
            self.assertEqual(t.phase, focus.LONG_BREAK if r == 4 else focus.BREAK)
            t.skip()
        self.assertEqual((t.phase, t.round), (focus.FOCUS, 1))
        self.assertEqual(len(ended), 8)
        t.toggle()
        t.skip()                                     # paused + skip = stop
        self.assertEqual(t.phase, focus.OFF)

    def test_picture_convert(self):
        from PIL import Image
        from macropad_app import picture
        d = Path(tempfile.mkdtemp())
        still = d / "a.png"
        Image.new("RGB", (640, 200), (255, 0, 0)).save(still)
        pic = picture.convert(still)
        self.assertEqual((pic.w, pic.h, pic.frames, len(pic.data)), (320, 170, 1, 320 * 170 * 2))
        self.assertEqual(pic.data[:2], bytes([0x00, 0xF8]))       # pure red in RGB565
        fitted = picture.convert(still, fit=True)
        self.assertEqual(fitted.data[:2], b"\x00\x00")          # black edge above the picture
        with self.assertRaises(ValueError):
            picture.convert(d / "missing.png")

    @unittest.skipUnless(sys.platform.startswith("linux"), "needs a pseudo terminal")
    def test_picture_upload(self):
        from PIL import Image
        from macropad_app import picture
        d = Path(tempfile.mkdtemp())
        still = d / "a.png"
        Image.new("RGB", (640, 200), (255, 0, 0)).save(still)
        pic = picture.convert(still)
        pad = FakePad()
        pad.proto = 4
        link = device.PadLink()
        got = []
        link.picture_done.connect(lambda ok, why: got.append((ok, why)), Qt.DirectConnection)
        with mock.patch.object(device, "pad_ports", return_value=[(pad.port, 0x1001)]):
            link.start()
            for _ in range(60):
                self.wait(100)
                if link.info is not None:
                    break
            link.upload_picture(pic)
            for _ in range(100):
                self.wait(100)
                if got:
                    break
            self.assertEqual(got, [(True, "")])
            self.assertEqual(bytes(pad.picture), pic.data)
            link.upload_picture(pic)                  # same picture again: nothing sent
            for _ in range(50):
                self.wait(100)
                if len(got) == 2:
                    break
            self.assertEqual(got[1], (True, "same"))
            self.assertTrue(any(l.startswith(b"Z|") and l.count(b"|") == 2 for l in pad.received))
        link.stop()
        pad.close()

    def test_widget_lines(self):
        d = config.validate({"display": {"background": "clock", "options": {"clock": {"seconds": False, "h12": True}}}})
        self.assertEqual(protocol.display_line(d["display"], 4), b"D|9|1|16|1|2\n")
        self.assertEqual(protocol.display_line(d["display"], 3), b"D|0|1|16|1|2\n")   # older pad: aquarium
        self.assertEqual(protocol.stats_line(12.6, 140, None, -5), b"Q|13|100|-1|-1\n")
        self.assertEqual(protocol.timer_line(-3, 60, 2, 3, True), b"U|0|60|2|3|1\n")
