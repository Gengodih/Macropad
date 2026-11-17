"""Tests for settings, keys, protocol, updater and flasher (no hardware needed).
Run:  python -m unittest discover -s tests -v"""

import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ["MACROPAD_HOME"] = tempfile.mkdtemp()

from macropad_app import config, flasher, keys, protocol, updater  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        d = config.defaults()
        self.assertEqual(config.validate(d), d)
        self.assertEqual(d["keys"], keys.DEFAULT_LAYOUT)

    def test_old_display_settings_move_over(self):
        d = config.validate({"display": {"background": "aquarium", "fish": False, "brightness": 7, "music": True}})
        self.assertTrue(d["display"]["animation"])
        self.assertEqual(d["display"]["background"], "aquarium")
        self.assertFalse(d["display"]["options"]["aquarium"]["fish"])
        self.assertEqual(d["display"]["options"]["fire"], {"beat": True, "fox": True})
        self.assertEqual(d["display"]["brightness"], 7)

    def test_display_options_checked(self):
        d = config.validate({"display": {"animation": True, "background": "volcano",
                                         "options": {"seasons": {"season": "monsoon"}, "fire": {"fox": False, "x": 1},
                                                     "rain": "wet"}}})
        self.assertEqual(d["display"]["background"], "aquarium")
        self.assertEqual(d["display"]["options"]["seasons"]["season"], "auto")
        self.assertEqual(d["display"]["options"]["fire"], {"beat": True, "fox": False})
        self.assertEqual(d["display"]["options"]["rain"], {"storm": True})
        d = config.validate({"display": {"background": "seasons", "options": {"seasons": {"season": "winter"}}}})
        self.assertEqual((d["display"]["background"], d["display"]["options"]["seasons"]["season"]), ("seasons", "winter"))

    def test_garbage_becomes_defaults(self):
        for junk in (None, 5, "x", [], {"keys": "no"}, {"lights": []}, {"display": {"brightness": "high"}}):
            self.assertEqual(config.validate(junk)["keys"], keys.DEFAULT_LAYOUT)

    def test_fields_are_checked_one_by_one(self):
        d = config.validate({"app_language": "fr", "pad_language": "de", "keys": ["key:F13"] * 14 + ["bogus"],
                             "lights": {"brightness": 500, "colour": -1, "mode": 3,
                                        "builtin_enabled": [True] * 6,
                                        "schemes": [{"name": "A|B", "effect": "nope", "colours": ["#zzzzzz", "#ABCDEF"]},
                                                    {"name": ""}, "junk"]},
                             "display": {"background": "plain", "fish": "yes", "brightness": 0, "music": False},
                             "updates": {"last_check": True}})
        self.assertEqual(d["app_language"], "en")
        self.assertEqual(d["pad_language"], "de")
        self.assertEqual(d["keys"][14], keys.DEFAULT_LAYOUT[14])
        self.assertEqual(d["lights"]["brightness"], 60)
        self.assertEqual(d["lights"]["colour"], 11)
        self.assertEqual(len(d["lights"]["schemes"]), 1)
        s = d["lights"]["schemes"][0]
        self.assertEqual(s["name"], "A/B")
        self.assertEqual(s["effect"], "static")
        self.assertEqual(s["colours"][:2], ["#000000", "#abcdef"])
        self.assertEqual(len(s["colours"]), 15)
        self.assertFalse(d["display"]["animation"])           # 1.2 "plain" = animation off
        self.assertEqual(d["display"]["background"], "aquarium")
        self.assertTrue(d["display"]["options"]["aquarium"]["fish"])   # "yes" is no bool
        self.assertEqual(d["display"]["brightness"], 16)
        self.assertFalse(d["display"]["music"])
        self.assertEqual(d["updates"]["last_check"], 0.0)

    def test_mode_must_exist(self):
        d = config.validate({"lights": {"mode": config.MODE_CUSTOM + 3, "schemes": []}})
        self.assertEqual(d["lights"]["mode"], 0)
        d = config.validate({"lights": {"mode": 0, "builtin_enabled": [False, True] + [True] * 4}})
        self.assertEqual(d["lights"]["mode"], 1)
        d = config.validate({"lights": {"mode": 0, "builtin_enabled": [False] * 6}})
        self.assertEqual(d["lights"]["mode"], config.MODE_OFF)

    def test_max_ten_schemes(self):
        many = [{"name": f"S{i}", "effect": "static", "colours": ["#ffffff"] * 15} for i in range(14)]
        self.assertEqual(len(config.validate({"lights": {"schemes": many}})["lights"]["schemes"]), 10)

    def test_save_load_and_broken_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            s = config.Settings(path)
            s.data["keys"][0] = "sc:copy"
            self.assertTrue(s.save())
            self.assertEqual(config.Settings(path).data["keys"][0], "sc:copy")
            path.write_text("{ not json", "utf-8")
            s2 = config.Settings(path)
            self.assertEqual(s2.data["keys"], keys.DEFAULT_LAYOUT)
            self.assertTrue(list(Path(tmp).glob("settings.broken-*.json")))


class KeysTests(unittest.TestCase):
    def all_ids(self):
        ids = ["none", "lights", "fun2"]
        ids += [f"key:{n}" for n in keys.KEYS_BY_NAME]
        ids += [f"media:{n}" for n in keys.MEDIA]
        ids += [f"sc:{n}" for n in keys.SHORTCUTS]
        ids += [keys.combo_id(m, "K") for m in range(16)]
        return ids

    def test_every_action_resolves_in_both_languages(self):
        for aid in self.all_ids():
            for lang in ("en", "de"):
                a = keys.resolve(aid, lang)
                self.assertIn(a.type, (0, 1, 2, 3, 4))
                if a.type in (keys.T_KEY, keys.T_COLOUR):
                    self.assertLessEqual(a.code, 0xFF)
                self.assertTrue(keys.short_label(aid, lang))

    def test_unknown_ids(self):
        for bad in ("", "key:", "key:F99", "media:x", "sc:x", "combo:99:A", "combo:a:A", "combo:3:NOPE",
                    "lights:x", None, 5):
            self.assertFalse(keys.is_valid(bad), bad)

    def test_hid_codes(self):
        self.assertEqual(keys.KEYS_BY_NAME["F13"].code, 0x68)
        self.assertEqual(keys.KEYS_BY_NAME["F24"].code, 0x73)
        self.assertEqual(keys.KEYS_BY_NAME["A"].code, 0x04)
        self.assertEqual(keys.KEYS_BY_NAME["0"].code, 0x27)
        self.assertEqual(keys.KEYS_BY_NAME["1"].code, 0x1E)
        self.assertEqual(keys.KEYS_BY_NAME["F1"].code, 0x3A)
        self.assertEqual(keys.KEYS_BY_NAME["NUM0"].code, 0x62)
        self.assertEqual(keys.resolve("sc:snip"), keys.PadAction(0, 0x16, keys.WIN | keys.SHIFT, "Snipping Tool"))


class ProtocolTests(unittest.TestCase):
    def test_pad_text(self):
        self.assertEqual(protocol.pad_text("Zurück", 23), b"Zur\x81ck")
        self.assertEqual(protocol.pad_text("a|b–c é", 23), b"a/b-c e")
        self.assertEqual(protocol.pad_text("x" * 50, 23), b"x" * 23)
        self.assertEqual(protocol.pad_text("\U0001F600ok", 23), b"ok")

    def test_lines_are_short_and_clean(self):
        s = config.defaults()
        s["lights"]["schemes"] = [{"name": "N" * 15, "effect": "glow", "colours": ["#123456"] * 15}] * 10
        for line in protocol.settings_lines(s):
            self.assertTrue(line.endswith(b"\n"))
            self.assertEqual(line.count(b"\n"), 1)
            self.assertLess(len(line), 299)      # the pad's line buffer

    def test_parsers(self):
        self.assertEqual(protocol.parse_info("I|2.0.0|1|1|7|60|11"), protocol.PadInfo("2.0.0", 1, 1, 7, 60, 11))
        self.assertIsNone(protocol.parse_info("I|2.0.0|x|1|7|60|11"))
        self.assertIsNone(protocol.parse_info("I|2.0.0"))
        self.assertEqual(protocol.parse_ack("A|W|31|0"), (31, 0))
        self.assertIsNone(protocol.parse_ack("A|E|K|1"))
        self.assertEqual(protocol.parse_lights("X|3|50|2"), (3, 50, 2))
        self.assertIsNone(protocol.parse_lights("X|3|50"))

    def test_versions(self):
        self.assertTrue(protocol.is_newer("1.10.0", "1.9.9"))
        self.assertTrue(protocol.is_newer("v2.0", "1.99.99"))
        self.assertFalse(protocol.is_newer("1.1.0", "1.1.0"))
        self.assertFalse(protocol.is_newer("garbage", "1.0.0"))
        self.assertEqual(protocol.version_tuple(None), (0, 0, 0))


class _Server:
    """A tiny local web server standing in for GitHub."""

    def __init__(self, files):
        self.files = files
        files_ref = files

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = files_ref.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.setup_bytes = os.urandom(300_000)
        self.digest = hashlib.sha256(self.setup_bytes).hexdigest()
        self.srv = _Server({"/setup.exe": self.setup_bytes})
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"

    def tearDown(self):
        self.srv.close()

    def release(self, digest=None):
        return updater.Release("9.9.9", setup_name="MacroPad-Setup-9.9.9.exe", setup_url=self.srv.url + "/setup.exe",
                               setup_size=len(self.setup_bytes), setup_sha256=digest or self.digest)

    def test_download_ok_and_cached(self):
        calls = []
        path = updater.download(self.release(), lambda d, t: calls.append((d, t)))
        self.assertEqual(path.read_bytes(), self.setup_bytes)
        self.assertEqual(calls[-1][0], len(self.setup_bytes))
        again = updater.download(self.release())        # already there: no second download
        self.assertEqual(again, path)
        path.unlink()

    def test_damaged_download_is_refused(self):
        with self.assertRaises(updater.UpdateError):
            updater.download(self.release(digest="0" * 64))
        self.assertFalse(list(Path(os.environ["MACROPAD_HOME"], "downloads").glob("*.part")))

    def test_cancel(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(updater.Cancelled):
            updater.download(self.release(), cancel=ev)

    def test_release_parsing(self):
        manifest = {"version": "99.2.0", "firmware": "2.0.1",
                    "setup": {"name": "MacroPad-Setup-1.2.0.exe", "sha256": "AB" * 32, "size": 10},
                    "files": {"MacroPad.exe": "cd" * 32}}
        gh = {"body": "notes", "assets": [{"name": "manifest.json", "browser_download_url": "M"},
                                           {"name": "MacroPad-Setup-1.2.0.exe", "browser_download_url": "S", "size": 10}]}
        with mock.patch.object(updater, "_get_json", side_effect=lambda url, timeout=15: manifest if url == "M" else gh):
            rel = updater.latest_release("me/repo")
        self.assertEqual((rel.version, rel.firmware, rel.setup_url, rel.setup_sha256), ("99.2.0", "2.0.1", "S", "ab" * 32))
        self.assertEqual(rel.notes_by_lang, {})
        manifest["notes"] = {"en": ["New thing"], "de": ["Neues Ding"], "xx": ["ignored"]}
        with mock.patch.object(updater, "_get_json", side_effect=lambda url, timeout=15: manifest if url == "M" else gh):
            rel = updater.latest_release("me/repo")
        self.assertEqual(rel.notes_by_lang, {"en": ["New thing"], "de": ["Neues Ding"]})
        self.assertTrue(rel.newer)
        with mock.patch.object(updater, "_get_json", return_value={"assets": []}):
            with self.assertRaises(updater.UpdateError):
                updater.latest_release("me/repo")
        with self.assertRaises(updater.UpdateError):
            updater.latest_release("")

    def test_release_manifest_has_notes(self):
        import json
        import subprocess
        d = Path(tempfile.mkdtemp())
        (d / "dist").mkdir()
        (d / "dist" / "manifest.json").write_text(json.dumps({"version": "1.6.0", "firmware": "2.3.0", "files": {}}))
        (d / "setup.exe").write_bytes(b"x")
        root = Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable, str(root / "tools" / "make_manifest.py"), "release", str(d / "dist"),
                        str(d / "setup.exe"), str(d / "out.json")], check=True, capture_output=True)
        data = json.loads((d / "out.json").read_text("utf-8"))
        self.assertTrue(data["notes"]["en"] and data["notes"]["de"])
        self.assertIn("- ", (d / "release-notes.md").read_text("utf-8"))

    def test_check_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "a.txt").write_text("hello")
            (base / "sub").mkdir()
            (base / "sub" / "b.txt").write_text("world")
            files = {"a.txt": hashlib.sha256(b"hello").hexdigest(),
                     "sub/b.txt": hashlib.sha256(b"WORLD").hexdigest(),     # changed
                     "missing.dll": "00" * 32,
                     "../outside.txt": "00" * 32}                          # ignored
            ok, bad = updater.check_files(files, base)
            self.assertEqual(ok, 1)
            self.assertEqual(sorted(bad), ["missing.dll", "sub/b.txt"])


class FlasherTests(unittest.TestCase):
    def test_bundle_in_app(self):
        b = flasher.load_bundle()
        self.assertEqual([hex(o) for o, _, _ in b.parts], ["0x0", "0x8000", "0xe000", "0x10000"])
        self.assertGreater(b.estimate_seconds(), 10)

    def test_damaged_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = flasher.load_bundle().parts
            d = Path(tmp)
            meta = {"version": "1", "parts": []}
            for off, f, _ in src:
                (d / f.name).write_bytes(f.read_bytes())
                meta["parts"].append({"offset": hex(off), "file": f.name,
                                      "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
            (d / "firmware.json").write_text(json.dumps(meta))
            flasher.load_bundle(d)
            (d / "app.bin").write_bytes(b"broken")
            with self.assertRaises(flasher.FlashError):
                flasher.load_bundle(d)
            meta["parts"][0]["file"] = "../evil.bin"
            (d / "firmware.json").write_text(json.dumps(meta))
            with self.assertRaises(flasher.FlashError):
                flasher.load_bundle(d)
        with self.assertRaises(flasher.FlashError):
            flasher.load_bundle(Path(tempfile.mkdtemp()))

    def fake_esptool(self, fail=False):
        def main(args):
            offsets = [int(a, 16) for a in args if a.startswith("0x")]
            for off in offsets:
                for pct in (25, 50, 75, 100):
                    print(f"Writing at {off + pct * 10:#010x} ━━━   {pct:.1f}% 1kB/4kB [0s] ")
            if fail:
                print("A fatal error occurred: Failed to connect to ESP32-S3: No serial data received.")
                raise SystemExit(2)
            print("Hard resetting via RTS pin...")
        return main

    def test_flash_progress(self):
        b = flasher.load_bundle()
        seen = []
        with mock.patch("esptool.main", self.fake_esptool()):
            flasher.flash(b, "COM9", lambda f, s: seen.append(f))
        self.assertAlmostEqual(seen[-1], 1.0)
        self.assertEqual(seen, sorted(seen))            # never goes backwards
        self.assertGreater(len(seen), 10)

    def test_flash_error_message(self):
        with mock.patch("esptool.main", self.fake_esptool(fail=True)):
            with self.assertRaises(flasher.FlashError) as cm:
                flasher.flash(flasher.load_bundle(), "COM9")
        self.assertIn("Failed to connect", str(cm.exception))

    def test_flash_cancel(self):
        ev = threading.Event()
        ev.set()
        with mock.patch("esptool.main", self.fake_esptool()):
            with self.assertRaises(flasher.FlashError) as cm:
                flasher.flash(flasher.load_bundle(), "COM9", cancel=ev)
        self.assertEqual(str(cm.exception), "cancelled")

    def test_wait_for_rom_port(self):
        seq = iter([["COM7"], ["COM7"], [], [], ["COM9"], ["COM9"], ["COM9"], ["COM9"], ["COM9"], ["COM9"]] + [["COM9"]] * 50)
        with mock.patch.object(flasher, "rom_ports", side_effect=lambda: next(seq)), \
             mock.patch.object(flasher.time, "sleep", lambda s: None):
            t = [0.0]

            def mono():
                t[0] += 0.3
                return t[0]
            with mock.patch.object(flasher.time, "monotonic", mono):
                self.assertEqual(flasher.wait_for_rom_port(20, before=["COM7"]), "COM9")


if __name__ == "__main__":
    unittest.main()


class RendererTests(unittest.TestCase):
    """The pad's animations through the app's library (skipped if it is not built)."""

    def setUp(self):
        from macropad_app import bgfx
        if not bgfx.available():
            self.skipTest("bgfx library not built (python tools/build_bgfx.py)")
        self.bgfx = bgfx

    def test_every_background_draws(self):
        from macropad_app import protocol
        for name in config.BACKGROUNDS:
            for options in (config.BACKGROUND_OPTIONS, {name: {k: (not v if isinstance(v, bool) else "winter")
                                                               for k, v in config.BACKGROUND_OPTIONS[name].items()}}):
                r = self.bgfx.Renderer(3)
                r.select(config.PAD_BACKGROUND[name], protocol.background_options(name, options))
                for i in range(40):
                    if i in (5, 20):
                        r.poke(["Copy", "Pläy/Ü", "x" * 80][i % 3])
                    r.update(1 / 30, (i % 10) / 10, i % 16, 1 + i % 12)
                img = r.frame()
                self.assertEqual((img.width(), img.height()), (320, 170))
                colours = {img.pixel(x, y) for x in range(0, 320, 16) for y in range(0, 170, 10)}
                self.assertGreater(len(colours), 3, name)
                r.close()

    def test_odd_input_is_harmless(self):
        r = self.bgfx.Renderer(0)
        for kind, opts in ((-5, 0), (99, 255), (1, 0), (8, 255)):
            r.select(kind, opts)
            r.update(10.0, 5.0, 99, 77)
            r.poke("")
            r.frame()
        r.close()
        r.close()


class HeardVolumeTests(unittest.TestCase):
    """Music app mode: the pad shows Windows volume x the app's mixer level."""

    def setUp(self):
        from macropad_app import media

        class App:
            exe = "spotify.exe"

            def __init__(self):
                self.lv, self.muted = 1.0, False

            def level(self):
                return self.lv

            def get(self):
                return round(self.lv * 100), self.muted

            def set_level(self, level, unmute=False):
                self.lv = level

            def change(self, clicks):
                self.lv = min(1.0, max(0.0, self.lv + clicks * media.VOL_STEP))

        class Master:
            def __init__(self):
                self.m = 0.4

            def scalar(self):
                return self.m

            def get(self):
                return round(self.m * 100), False
        self.app, self.master = App(), Master()
        self.v = media.HeardVolume(self.app, self.master)

    def test_shows_what_you_hear(self):
        self.assertEqual(self.v.get(), (40, False))         # Windows 40 %, Spotify slider 100 %
        self.v.change(-5)                                   # knob: 5 clicks down = 10 % less heard
        self.assertEqual(self.v.get(), (30, False))
        self.assertAlmostEqual(self.app.lv, 0.75)
        self.v.change(50)                                   # never louder than the Windows volume
        self.assertEqual(self.v.get(), (40, False))
        self.assertAlmostEqual(self.app.lv, 1.0)
        self.master.m = 0.0                                 # Windows at 0: plain steps on the app
        self.v.change(-1)
        self.assertAlmostEqual(self.app.lv, 0.98)
        self.app.level = lambda: None                       # app not playing yet
        self.assertEqual(self.v.get(), (-1, False))
