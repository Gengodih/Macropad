"""Compiles the firmware's settings parser (cut out of macropad.ino) together
with stubs on this PC and feeds it the exact lines the app sends.
Needs g++ (Linux/macOS). Run: python tests/native/run_native.py"""
import os, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
from macropad_app import config, protocol  # noqa: E402

ino = (ROOT / "firmware/macropad/macropad.ino").read_text("utf-8")

def cut(start, end):
    a = ino.index(start); b = ino.index(end, a)
    return ino[a:b]

parts = [
    cut("enum ActionType : uint8_t", "// What each key does right now"),
    "KeyAction actions[KEY_COUNT];\n",
    cut("// Lights\nenum LightMode", "// Colours for \"Key glow\""),
    cut("struct NamedColour", "// Screen settings (from the app)"),
    cut("// Screen settings (from the app)", "\n\n// Settings messages from the app"),
    "uint16_t cfgAccepted = 0, cfgRejected = 0;\n",
    cut("// Name of a light mode in the pad's language", "bool helperAlive(uint32_t now)"),
    cut("// Splits \"a|b|c\" in place.", "void sendInfo() {"),
    cut("bool applyKeyLine(char **f, int n) {", "// Everything the app can change, into flash"),
]
harness = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <cstdint>
#include <algorithm>
using std::min; using std::max;
#define CONSUMER_CONTROL_SCAN_PREVIOUS 0xB6
#define CONSUMER_CONTROL_PLAY_PAUSE 0xCD
#define CONSUMER_CONTROL_SCAN_NEXT 0xB5
const uint8_t KEY_COUNT = 15, ROWS = 3, COLS = 5;
const uint8_t HID_F13 = 0x68, HID_F14 = 0x69, HID_F15 = 0x6A, HID_F16 = 0x6B, HID_F17 = 0x6C, HID_F18 = 0x6D,
  HID_F19 = 0x6E, HID_F20 = 0x6F, HID_F21 = 0x70, HID_F22 = 0x71, HID_F23 = 0x72, HID_F24 = 0x73;
uint8_t lightMode = 0, lightPct = 60, lightColour = 11;
bool dirty = false; bool aquariumReady = false; uint8_t brightnessIdx = 0;
struct { bool showFish; } tank;
void setBacklight(uint8_t) {}
#define strlcpy my_strlcpy
static size_t my_strlcpy(char *d, const char *s, size_t n) { size_t l = strlen(s); if (n) { size_t c = l < n - 1 ? l : n - 1; memcpy(d, s, c); d[c] = 0; } return l; }
template<class T> T constrain(T v, T lo, T hi) { return v < lo ? lo : v > hi ? hi : v; }
@@PARTS@@
uint8_t backlightFor(uint8_t idx) { return idx == 0 ? screenLevel : 0; }
void applyDisplay() { dirty = true; }
@@APPLY@@
int main() {
  memcpy(actions, DEFAULT_ACTIONS, sizeof(actions));
  char line[400];
  while (fgets(line, sizeof line, stdin)) {
    size_t n = strlen(line); while (n && (line[n-1] == '\n' || line[n-1] == '\r')) line[--n] = 0;
    if (!n) continue;
    if (strcmp(line, "W") == 0) { printf("ACK %u %u\n", cfgAccepted, cfgRejected); cfgAccepted = cfgRejected = 0; continue; }
    if (applyConfigLine(line)) cfgAccepted++; else { cfgRejected++; printf("REJ %s\n", line); }
  }
  printf("LANG %u BG %u FISH %d LEVEL %u MUSIC %d OPT %u\n", padLang, bgAnim, showFish, screenLevel, showMusic, bgOptions);
  printf("LIGHT %u %u %u MASK %u\n", lightMode, lightPct, lightColour, builtinMask);
  for (int i = 0; i < KEY_COUNT; i++) printf("KEY %d %u %u %u %s\n", i, actions[i].type, actions[i].code, actions[i].mods, actions[i].label);
  for (int i = 0; i < MAX_SCHEMES; i++) if (schemes[i].used) printf("SCHEME %d %u %s %02X%02X%02X %02X%02X%02X\n", i, schemes[i].effect, schemes[i].name,
       schemes[i].rgb[0][0], schemes[i].rgb[0][1], schemes[i].rgb[0][2], schemes[i].rgb[14][0], schemes[i].rgb[14][1], schemes[i].rgb[14][2]);
  return 0;
}
'''
apply_fn = cut("// One settings message. Returns false", "// Everything the app can change, into flash")
body = "\n".join(p for p in parts if not p.startswith("bool applyKeyLine"))
key_and_scheme = cut("bool applyKeyLine(char **f, int n) {", "// One settings message. Returns false")
src = harness.replace("@@PARTS@@", body).replace("@@APPLY@@", key_and_scheme + apply_fn)
src = src.replace("const char *tr(Txt t)", "const char *tr_unused(Txt t)")

def build():
    d = Path(tempfile.mkdtemp())
    (d / "t.cpp").write_text(src, "utf-8")
    r = subprocess.run(["g++", "-std=c++17", "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-o", str(d / "t"), str(d / "t.cpp")],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[:4000]); sys.exit("compile failed")
    return d / "t"

def run(exe, data: bytes):
    return subprocess.run([str(exe)], input=data, capture_output=True).stdout.decode("latin-1")

exe = build()
fails = 0
def check(name, cond, info=""):
    global fails
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  -> {info}"))
    fails += not cond

# 1. default settings: every line accepted
s = config.defaults()
lines = protocol.settings_lines(s)
out = run(exe, b"".join(lines) + protocol.SAVE)
check("defaults accepted", f"ACK {len(lines)} 0" in out, out[:300])

# 2. everything changed, German, schemes, shortcuts
s = config.defaults()
s["pad_language"] = "de"
s["keys"][0] = "sc:snip"; s["keys"][1] = "combo:15:F24"; s["keys"][2] = "none"; s["keys"][3] = "media:vol_up"
s["keys"][13] = "key:A"; s["keys"][14] = "media:calculator"
s["display"]["animation"] = False
s["display"]["options"]["aquarium"]["fish"] = False
s["display"]["brightness"] = 5; s["display"]["music"] = False
s["lights"]["schemes"] = [{"name": "Ocean|Blue", "effect": "glow", "colours": ["#00aaff"] * 14 + ["#ff0000"]},
                          {"name": "FireÜ", "effect": "breathe", "colours": ["#ff5500"] * 15}]
s["lights"]["builtin_enabled"] = [False, True, True, False, True, True]
s["lights"]["mode"] = config.MODE_CUSTOM + 1
s["lights"]["brightness"] = 80; s["lights"]["colour"] = 3
lines = protocol.settings_lines(s)
out = run(exe, b"".join(lines) + protocol.SAVE)
check("full settings accepted", f"ACK {len(lines)} 0" in out, out[:600])
check("language + display", "LANG 1 BG 1 FISH 0 LEVEL 5 MUSIC 0" in out, out)
check("lights", f"LIGHT {config.MODE_CUSTOM + 1} 80 3 MASK 54" in out, out)
check("snip key", "KEY 0 0 22 10 Snipping Tool" in out, out)
check("own combo", "KEY 1 0 115 15 " in out, out)
check("none key", "KEY 2 4 0 0 " in out, out)
check("calculator 16-bit media code", "KEY 14 1 402 0 Rechner" in out, out)
check("scheme 0 (| replaced, colours)", "SCHEME 0 2 Ocean/Blue 00AAFF FF0000" in out, out)
check("scheme 1 with umlaut", "SCHEME 1 1 Fire\x9a FF5500 FF5500" in out, out)

# 2b. the new backgrounds and their options
for name, opts, want in (("fire", {"beat": True, "fox": True}, 3), ("fire", {"beat": False, "fox": True}, 2),
                         ("seasons", {"season": "autumn"}, 8), ("matrix", {"key_names": False}, 0),
                         ("lava", {"light_colour": True}, 1)):
    s = config.defaults()
    s["display"]["background"] = name
    s["display"]["options"][name] = opts
    lines = protocol.settings_lines(s)
    out = run(exe, b"".join(lines) + protocol.SAVE)
    check(f"background {name} {opts}", f"ACK {len(lines)} 0" in out and
          f"BG {config.PAD_BACKGROUND[name]} FISH 1 LEVEL 16 MUSIC 1 OPT {want}" in out, out[:300])
# an old pad (settings protocol 1) gets five fields and the aquarium instead
s = config.defaults()
s["display"]["background"] = "space"
line = protocol.display_line(s["display"], proto=1)
check("old pad gets 5 fields", line == b"D|0|1|16|1\n", line)
out = run(exe, line + protocol.SAVE)
check("5-field D still accepted", "ACK 1 0" in out and "BG 0 FISH 1" in out, out[:200])

# 3. broken / hostile lines are rejected, nothing crashes
bad = [b"K|15|0|1|0|x\n", b"K|0|9|1|0|x\n", b"K|0|0|300|0|x\n", b"K|0|0|1\n", b"K|-1|0|1|0|x\n",
       b"G|2\n", b"D|0|1|0|1\n", b"D|9|1|5|1\n", b"D|2|1|5|1|256\n", b"D|2|1|5|1|3|9\n", b"D|2|1|5\n", b"LM|99\n", b"LB|5\n", b"LB|abc\n", b"LP|16\n",
       b"LS|10|0|x|" + b",".join([b"FFFFFF"] * 15) + b"\n", b"LS|0|0|x|FFFFFF\n",
       b"LS|0|0|x|" + b",".join([b"GGGGGG"] * 15) + b"\n", b"LS|0|0|x|" + b",".join([b"FFFFFF"] * 16) + b"\n",
       b"LM|8\n", b"X\n", b"K|0|0|1|0|" + b"A" * 200 + b"\n"]
out = run(exe, b"".join(bad) + protocol.SAVE)
m = re.search(r"ACK (\d+) (\d+)", out)
check("hostile lines", m and m.group(1) == "1" and m.group(2) == str(len(bad) - 1), out[:800])
check("long label cut to 23", "KEY 0 0 1 0 " + "A" * 23 + "\n" in out, out[-900:])

# 4. deleting the active scheme falls back to an available mode
seq = b"".join([b"LE|63\n", protocol.scheme_line(0, {"name": "X", "effect": "static", "colours": ["#ffffff"] * 15}),
                b"LM|7\n", b"LS|0|0||\n"]) + protocol.SAVE
out = run(exe, seq)
check("delete active scheme", "ACK 4 0" in out and "LIGHT 0 " in out, out)

print("native firmware parser:", "all ok" if not fails else f"{fails} failed")
sys.exit(1 if fails else 0)
