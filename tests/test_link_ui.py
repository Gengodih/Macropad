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
                line, buf = buf.split(b"\n", 1)
                self.received.append(line)
                if not self.answer:
                    continue
                if line == b"?":
                    os.write(self.master, b"I|2.0.0|1|0|4|70|3\n")
                elif line == b"W":
                    self.saves += 1
                    os.write(self.master, f"A|W|{count}|{rejected}\n".encode())
                    count = rejected = 0
                elif line[:2] in (b"K|", b"G|", b"D|") or line[:3] in (b"LE|", b"LS|", b"LP|", b"LB|", b"LM|"):
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
        w.draft["display"]["background"] = "plain"
        w.changed()
        self.assertEqual(w.background.mode, "plain")         # live preview
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

    def test_language_switch_rebuilds(self):
        w = self.win
        w.draft["app_language"] = "de"
        w.changed()
        w.apply()
        self.assertEqual(w.apply_btn.text(), "Anwenden")
        self.assertEqual(w.windowTitle(), "Macro Pad")


if __name__ == "__main__":
    unittest.main()
