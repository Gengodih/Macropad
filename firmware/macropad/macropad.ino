/*
  ESP32-S3 Macro Pad  -  firmware for the LilyGO T-Display-S3
  ------------------------------------------------------------
  15 keys (3 rows x 5) + 1 rotary encoder (with push) + the built-in 1.9" screen.

  USB acts as three things at once:
    - a keyboard       (F13-F23, Win+Shift+S)  -> Discord keybinds, screenshots
    - media keys       (prev / play-pause / next)  -> any music app
    - a serial port    -> talks to macropad_helper.py on the PC
                          (song info in; knob, play/next/prev out)

  Works with Spotify and Deezer: the PC helper tells the pad which app is
  playing; the screen shows the album cover, title, artist, song progress, a
  play/pause symbol and the PC volume as a row of bars. While the helper
  is not running, the screen shows an aquarium instead (needs PSRAM). Every
  key press drops some fish food; a dimmed screen makes it night.

  RGB: one SK6812MINI-E LED under each key (plus optional underglow LEDs).
  Lights (bottom right): tap = next light mode, hold + turn knob = LED
  brightness. Fun 2 (left of it): tap = F16, hold + turn knob = colour for
  "Key glow" and "One colour". Mode, colour and brightness are remembered
  after unplugging.

  Macro Pad app (Windows): keys, lights, screen and language can be set in the
  app. It sends them over USB and the pad keeps them in its flash memory, so
  they stay after unplugging and also work without the app. Firmware updates
  come through the app as well (Update & Repair).

  Start-up show (about 4 s): the tank on the screen fills with water, the
  fish swim in and a welcome appears, while the LEDs flash red, green, blue
  (a quick check that every LED works) and then rise blue with the water.
  Keys and knob work right away; only the light settings wait until the
  show is over.

  Arduino IDE  ->  Tools menu:
    Board ............ ESP32S3 Dev Module
    USB Mode ......... USB-OTG (TinyUSB)
    USB CDC On Boot .. Enabled
    Flash Size ....... 16MB (128Mb)
    PSRAM ............ OPI PSRAM
    Upload Mode ...... USB-OTG CDC (TinyUSB)

  Libraries (Library Manager): "GFX Library for Arduino" by Moon On Our Nation
                               "Adafruit NeoPixel" by Adafruit
  Board package (Boards Manager): "esp32" by Espressif Systems, version 3.x

  Wiring: the keys form a 3 x 5 matrix. Each key connects its row line to its
  column line through a diode (1N4148W); the diode's stripe (cathode) faces
  the column. The pad switches one column LOW at a time and reads the rows,
  about 1000 times a second. Encoder: A, B, push to the GPIOs below, encoder
  C (middle pin) and the other push pin to GND. No resistors needed (internal
  pull-ups are used).
*/

#include <Arduino.h>
#include "USB.h"
#include "USBHIDKeyboard.h"
#include "USBHIDConsumerControl.h"
#include <Arduino_GFX_Library.h>
#include "SafeLCD8.h"      // screen bus without the streaks (third file in this folder)
#include <Adafruit_NeoPixel.h>
#include <Preferences.h>
#include <esp_heap_caps.h>
#include "esp32-hal-tinyusb.h"   // usb_persist_restart(): reboot into flash mode for updates
#include <esp_partition.h>       // own picture: kept in the flash area after the app

// Firmware version, reported to the Macro Pad app (Update & Repair compares it).
const char FW_VERSION[] = "2.3.1";
const uint8_t PROTO_VERSION = 4;   // settings messages understood by this firmware (2: backgrounds, 3: app keys, 4: widgets)
#include "Aquarium.h"   // the aquarium scene (second file in this sketch folder)
#include "Backgrounds.h"   // the other animated backgrounds

#if ARDUINO_USB_MODE
#error "Set Tools > USB Mode to 'USB-OTG (TinyUSB)', otherwise the pad cannot act as a keyboard."
#endif

// ============================================================================
//  Settings you may want to change
// ============================================================================

// Pins on the T-Display-S3 headers.
// Left header: GPIO 1 2 3 10 11 12 13   Right header: GPIO 43 44 18 17 21 16
// Key matrix: 3 row lines (read, with pull-ups) and 5 column lines (driven).
const uint8_t ROWS = 3, COLS = 5, KEY_COUNT = ROWS * COLS;
const uint8_t PIN_ROW[ROWS] = {1, 2, 3};
const uint8_t PIN_COL[COLS] = {10, 11, 12, 13, 43};   // GPIO44 stays free
// Keys are numbered row by row, left to right (default layout, change it in the app):
//    0  1  2  3  4      F13   F14   F15   F16    F17
//    5  6  7  8  9      F18   F19   F20   F21    F22
//   10 11 12 13 14      Prev  Play  Next  Fun 2  Lights
const uint8_t PIN_ENC_A  = 18;
const uint8_t PIN_ENC_B  = 17;
const uint8_t PIN_ENC_SW = 21;
const uint8_t PIN_LED    = 16;     // RGB data, through the 3.3 V -> 5 V level shifter

// RGB lighting: SK6812MINI-E LEDs chained DOUT -> DIN.
// KEY_LED[k] = place of key k's LED in the chain (0 = first LED after the
// level shifter), keys numbered as above. Match this to how the chain runs
// on your PCB. A "snake" route (row 2 right to left) would be
// {0, 1, 2, 3, 4,  9, 8, 7, 6, 5,  10, 11, 12, 13, 14}.
const uint8_t KEY_LED[KEY_COUNT] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14};
const uint8_t UNDERGLOW_LEDS = 0;  // extra LEDs at the end of the chain (0 = none)
const uint8_t LED_COUNT = KEY_COUNT + UNDERGLOW_LEDS;
const uint8_t LED_MAX = 200;       // brightness limit per colour, 0-255
// Current limit for all LEDs together, so the pad stays within what a USB
// port gives (500 mA, minus about 150 mA for the board and screen).
// SK6812MINI-E: about 12 mA per colour at full power (datasheet).
const float LED_BUDGET_MA = 300.0f;
const float LED_MA_PER_COLOUR = 12.0f;
// Start-up show. The red/green/blue flash tests the LEDs: if one stays dark,
// so do all after it in the chain - the fault is at the first dark LED (or
// the solder joints just before it).
const bool STARTUP_ANIMATION = true;
// Welcome text during the start-up show:
//      Welcome, Max!
//    to your Macro Pad
//  handcrafted by Gengodih
const char OWNER_NAME[] = "";          // whose pad it is ("" = just "Welcome!"); the app can set it too
const char MAKER_NAME[] = "Gengodih";  // who built it ("" = leave that line out)
const uint32_t LED_FRAME_MS = 20;  // 50 light updates per second

// Screen orientation: 3 = USB-C on the right, 1 = USB-C on the left (turned 180 degrees)
const uint8_t SCREEN_ROTATION = 3;

const uint8_t PIN_BTN_BOOT = 0;    // onboard BOOT button  -> extra key (F24)
const uint8_t PIN_BTN_IO14 = 14;   // onboard second button -> screen brightness

// Encoder: most EC11 knobs make 4 signal steps per click. If one click moves
// the volume twice, set this to 2. If the knob turns the wrong way, set
// ENC_REVERSE to true (or swap the A and B wires).
const int  ENC_STEPS_PER_CLICK = 2;     // Alps EC11E15244G1: 15 pulses / 30 detents. Use 4 for 20/20 or 24/24 encoders
const bool ENC_REVERSE = false;

// Volume change per knob click in percent. Keep it equal to VOL_STEP in
// macropad_helper.py so the bar on the screen matches.
const int VOL_STEP = 2;

const uint32_t DEBOUNCE_MS     = 5;
const uint32_t HELPER_TIMEOUT  = 5000;  // nothing from the PC for this long = helper offline
const uint32_t TOAST_MS        = 900;   // how long a key name stays on screen
const bool AQUARIUM_WHEN_OFFLINE = true; // animated background (aquarium etc.) while no song is shown
const uint32_t AQUARIUM_FRAME_MS = 25;  // at most 40 aquarium frames per second

// HID usage codes (USB keyboard spec, page 0x07)
const uint8_t HID_F13 = 0x68, HID_F14 = 0x69, HID_F15 = 0x6A, HID_F16 = 0x6B,
              HID_F17 = 0x6C, HID_F18 = 0x6D, HID_F19 = 0x6E, HID_F20 = 0x6F,
              HID_F21 = 0x70, HID_F22 = 0x71, HID_F23 = 0x72, HID_F24 = 0x73, HID_S = 0x16;
// Modifier bits
const uint8_t MOD_CTRL = 0x01, MOD_SHIFT = 0x02, MOD_ALT = 0x04, MOD_WIN = 0x08;

enum ActionType : uint8_t { ACT_KEY, ACT_MEDIA, ACT_LIGHTS, ACT_COLOUR, ACT_NONE, ACT_APP, ACT_LAYER, ACT_TYPE_COUNT };

struct KeyAction {
  ActionType type;
  uint16_t code;      // HID usage (ACT_KEY / ACT_COLOUR) or consumer code (ACT_MEDIA)
  uint8_t mods;       // modifier bits (ACT_KEY / ACT_COLOUR)
  char label[24];     // shown on the screen when pressed
};
// ACT_LIGHTS = the light key: nothing is sent to the PC.
// ACT_COLOUR = tap sends its key (when you let go); hold + turn the knob picks the light colour.
// ACT_NONE   = does nothing.
// ACT_APP    = the app does it (macro, text, program, tap/hold ...): the pad only reports
//              the press. Without the app the key does its default job.
// ACT_LAYER  = while held, the other keys do their layer-2 job.

// Default for each key, in the key order shown above. The Macro Pad app can
// change every key; its choice is kept in flash (see loadSettings).
const KeyAction DEFAULT_ACTIONS[KEY_COUNT] = {
  // row 1
  {ACT_KEY,   HID_F13, 0, "F13"},
  {ACT_KEY,   HID_F14, 0, "F14"},
  {ACT_KEY,   HID_F15, 0, "F15"},
  {ACT_KEY,   HID_F16, 0, "F16"},
  {ACT_KEY,   HID_F17, 0, "F17"},
  // row 2
  {ACT_KEY,   HID_F18, 0, "F18"},
  {ACT_KEY,   HID_F19, 0, "F19"},
  {ACT_KEY,   HID_F20, 0, "F20"},
  {ACT_KEY,   HID_F21, 0, "F21"},
  {ACT_KEY,   HID_F22, 0, "F22"},
  // row 3
  {ACT_MEDIA, CONSUMER_CONTROL_SCAN_PREVIOUS, 0, "Previous"},
  {ACT_MEDIA, CONSUMER_CONTROL_PLAY_PAUSE, 0, "Play / Pause"},
  {ACT_MEDIA, CONSUMER_CONTROL_SCAN_NEXT, 0, "Next"},
  {ACT_COLOUR, HID_F23, 0, "Fun 2 (F23)"},
  {ACT_LIGHTS, 0, 0, "Lights"},
};
// What each key does right now (defaults, or what the app sent).
KeyAction actions[KEY_COUNT];
KeyAction actions2[KEY_COUNT];           // layer 2: while a layer key is held (saved too)
KeyAction overlay[KEY_COUNT];            // the profile of the program in front (from the app, not saved)
uint16_t overlayMask = 0;                // which keys the profile changes
const KeyAction NO_ACTION = {ACT_NONE, 0, 0, ""};
uint8_t layerHeld = 0;                   // layer keys held down right now
char ownerName[24] = "";                 // for the welcome ("" = OWNER_NAME)
const KeyAction ACTION_BOOT = {ACT_KEY, HID_F24, 0, "BOOT key (F24)"};

// ============================================================================
//  Hardware objects
// ============================================================================

USBHIDKeyboard Keyboard;
USBHIDConsumerControl ConsumerControl;

// T-Display-S3 screen: ST7789, 170x320, 8-bit parallel bus (fixed pins on the board)
const uint8_t PIN_LCD_POWER = 15;
const uint8_t PIN_LCD_BL    = 38;
Arduino_DataBus *bus = new SafeLCD8(
    7 /* DC */, 6 /* CS */, 8 /* WR */, 9 /* RD */,
    39, 40, 41, 42, 45, 46, 47, 48 /* D0-D7 */);
// Landscape, 320 x 170. Orientation: SCREEN_ROTATION at the top.
Arduino_GFX *panel = new Arduino_ST7789(
    bus, 5 /* RST */, SCREEN_ROTATION, true /* IPS */, 170, 320, 35, 0, 35, 0);

// Draw into a frame buffer first, then push it in one go: no flicker.
// The buffer sits in the chip's own fast memory (falls back to PSRAM).
class FastCanvas : public Arduino_Canvas {
 public:
  FastCanvas(int16_t w, int16_t h, Arduino_G *output) : Arduino_Canvas(w, h, output) {}
  bool begin(int32_t speed = GFX_NOT_DEFINED) override {
    if (!_framebuffer)
      _framebuffer = (uint16_t *)heap_caps_malloc(_width * _height * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    return Arduino_Canvas::begin(speed);
  }
};
FastCanvas *gfx = new FastCanvas(320, 170, panel);

// SK6812MINI-E LEDs use GRB colour order, like WS2812 "NeoPixels".
Adafruit_NeoPixel strip(LED_COUNT, PIN_LED, NEO_GRB + NEO_KHZ800);
Preferences prefs;   // remembers light mode and brightness in flash

// Screen colour from red, green, blue (0-255). A macro on purpose: the Arduino
// IDE puts its own function declarations above the first function in the file,
// and they must come after the types below.
#define rgb(r, g, b) ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))
const uint16_t C_BG      = rgb(0, 0, 0);
const uint16_t C_TEXT    = rgb(255, 255, 255);
const uint16_t C_DIM     = rgb(150, 150, 150);
const uint16_t C_FAINT   = rgb(45, 45, 45);
const uint16_t C_GREEN   = rgb(30, 215, 96);    // Spotify green
const uint16_t C_DEEZER  = rgb(162, 56, 255);   // Deezer purple
const uint16_t C_BLURPLE = rgb(88, 101, 242);   // Discord colour
const uint16_t C_RED     = rgb(235, 70, 70);

// ============================================================================
//  State
// ============================================================================

struct Button {
  uint8_t pin;       // only for the encoder push and the onboard buttons
  bool stable;       // debounced: true = pressed
  bool raw;
  uint32_t changedAt;
};
Button keys[KEY_COUNT];
bool matrixRaw[KEY_COUNT];   // latest matrix scan, true = pressed
// What each key was doing when it went down. Its release uses the same action,
// even if the app changed the key (or went offline) while it was held.
KeyAction held[KEY_COUNT];
bool heldLayer2[KEY_COUNT];   // the press came from layer 2
// Key lights the app sets (e.g. red while the microphone is muted)
uint16_t highlightMask = 0;
uint8_t highlightRGB[KEY_COUNT][3];
// Sleep: screen and lights off while the PC is locked / asleep, or after a while without a key
uint8_t idleMinutes = 0;                 // 0 = never (from the app)
uint32_t lastActivity = 0;
bool pcLocked = false;                   // from the app
volatile bool padAsleep = false;
Button encButton, bootButton, io14Button;

// Encoder, decoded in an interrupt so no click is lost while the screen redraws
portMUX_TYPE encMux = portMUX_INITIALIZER_UNLOCKED;
volatile int32_t encRaw = 0;
volatile uint8_t encState = 0;
static const int8_t DRAM_ATTR ENC_TABLE[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

struct NowPlaying {
  char player[16] = "";  // "Spotify", "Deezer" ... as sent by the helper
  bool playing = false;
  int volume = -1;     // 0-100, -1 = the app has no entry in the Windows mixer yet
  bool muted = false;
  char title[128] = "";
  char artist[96] = "";
  uint32_t posMs = 0;  // song position when posAt was received
  uint32_t durMs = 0;  // song length, 0 = the app does not say
  uint32_t posAt = 0;  // millis() when posMs arrived
} np;

// Album cover from the helper, COVER x COVER pixels. Two buffers in PSRAM: one
// is shown, the next one is received into the other (no half-finished covers).
const int16_t COVER = 120;               // keep equal to COVER in macropad_helper.py
uint16_t *coverPix[2] = {nullptr, nullptr};
int coverShown = 0;
bool coverValid = false;                 // false: show a music note instead
size_t coverExpect = 0, coverGot = 0;    // bytes of the cover still coming in
bool coverSkip = false;                  // wrong size or no memory: read and drop
uint32_t coverSum = 0, coverWantSum = 0, coverLastByte = 0;

uint32_t lastHelperMsg = 0;   // millis() of the last message from the PC
bool helperWasAlive = false;
uint32_t lastKnobAt = 0;
uint32_t toastUntil = 0;
char toastText[32] = "";
uint16_t toastBg = rgb(88, 101, 242);   // Discord colour
uint16_t toastFg = 0xFFFF;
portMUX_TYPE toastMux = portMUX_INITIALIZER_UNLOCKED;  // toast is also read by the aquarium task
int mediaKeyDown = -1;        // index of the key holding a media key, -1 = none
bool dirty = true;            // screen needs a redraw
bool wasAnimating = false;
uint32_t lastFrame = 0;

// Onboard IO14 button: bright (screenLevel) -> dim -> off
const uint8_t BRIGHT_STEPS = 3, BRIGHT_DIM = 1, BRIGHT_OFF = 2;
volatile uint8_t brightnessIdx = 0;   // also read by the aquarium task

char rxLine[300];
size_t rxLen = 0;

// Aquarium (drawn by its own task on the second CPU core, so keys, knob and
// lights keep running at full speed). Only one side draws at a time: screenLock.
aq::Aquarium tank;
bool aquariumReady = false;              // PSRAM buffers were found at power-on
volatile bool aquariumWanted = false;    // set by loop(): helper is off
volatile uint8_t aquariumFeeds = 0;      // counts key presses -> fish food / pokes the other backgrounds
bgx::Effects effects;                    // the other animated backgrounds (same task, same buffers)
bool effectsReady = false;
char pokeLabel[24] = "";                 // name of the last pressed key (Matrix shows it)
portMUX_TYPE pokeMux = portMUX_INITIALIZER_UNLOCKED;
uint32_t introStart = 0, introLength = 0; // start-up show, millis()
SemaphoreHandle_t screenLock = nullptr;

// Lights
enum LightMode : uint8_t {
  L_RAINBOW, L_GRADIENT, L_MUSIC_COLOR, L_MUSIC_BEAT, L_KEY_GLOW, L_SOLID, L_OFF, L_COUNT};
const uint8_t L_BUILTIN_ON = 6;          // modes 0-5 can be left out of the Lights-key rotation
// Own light schemes from the app ("custom"): one colour per key plus an effect.
// They follow the built-in modes: mode L_CUSTOM + slot.
const uint8_t MAX_SCHEMES = 10;
const uint8_t L_CUSTOM = L_COUNT;
const uint8_t MODE_COUNT = L_COUNT + MAX_SCHEMES;
enum SchemeEffect : uint8_t { FX_STATIC, FX_BREATHE, FX_GLOW, FX_COUNT };
struct LightScheme {
  uint8_t used;                 // 0 = empty slot
  uint8_t effect;               // SchemeEffect
  char name[16];
  uint8_t rgb[KEY_COUNT][3];
};
LightScheme schemes[MAX_SCHEMES];
uint8_t builtinMask = 0x3F;     // bit n set = built-in mode n is in the rotation

// ----------------------------------------------------------------------------
// Texts on the pad's screen, English and German (the app picks one). The
// built-in font has the German letters at these codes (code page 437):
// \x84 = ae-umlaut, \x94 = oe-umlaut, \x81 = ue-umlaut, \xE1 = sharp s.
// The start-up welcome always stays English.
// ----------------------------------------------------------------------------
enum Txt : uint8_t {
  T_LIGHTS_FMT, T_COLOUR_FMT, T_LIGHT_LEVEL_FMT, T_MUTED, T_SOUND_ON, T_WIN_VOL_UP, T_WIN_VOL_DOWN,
  T_WIN_MUTE, T_MUSIC, T_OFFLINE, T_KEYS_NORMAL, T_KNOB_WIN, T_OFFLINE_LONG, T_CONNECTED,
  T_SAVED, T_UPDATE, T_PICTURE, T_COUNT};
const char *const TEXT_EN[T_COUNT] = {
  "Lights: %s", "Colour: %s", "Light brightness %d%%", "Sound muted", "Sound on",
  "Windows volume +", "Windows volume -", "Windows mute", "Music", "PC app offline",
  "Keys work normally.", "Knob = Windows volume", "PC app offline - keys work normally",
  "PC app connected", "Settings saved", "Update mode...", "Receiving picture..."};
const char *const TEXT_DE[T_COUNT] = {
  "Licht: %s", "Farbe: %s", "Lichthelligkeit %d%%", "Ton aus", "Ton an",
  "Lautst\x84rke +", "Lautst\x84rke -", "Ton aus (Windows)", "Musik", "PC-App offline",
  "Tasten funktionieren.", "Knopf = Lautst\x84rke", "PC-App offline - Tasten funktionieren",
  "PC-App verbunden", "Gespeichert", "Update-Modus...", "Bild kommt an..."};
const char *const LIGHT_NAMES_EN[L_COUNT] = {
  "Rainbow wave", "Gradient", "Music colour", "Music beat", "Key glow", "One colour", "Lights off"};
const char *const LIGHT_NAMES_DE[L_COUNT] = {
  "Regenbogen", "Farbverlauf", "Musikfarbe", "Musik-Beat", "Tasten-Gl\x81hen", "Eine Farbe", "Licht aus"};
uint8_t padLang = 0;             // 0 = English, 1 = German

// Colours for "Key glow" and "One colour" (hold Fun 2 + turn the knob, or set in the app).
// Hues use the Adafruit scale (0-65535) and are nudged so they still look
// right after gamma correction.
struct NamedColour { const char *en; const char *de; uint16_t hue; uint8_t sat; };
const NamedColour COLOURS[] = {
  {"Red", "Rot", 0, 255},            {"Orange", "Orange", 4550, 255},
  {"Amber", "Bernstein", 6900, 255}, {"Yellow", "Gelb", 10000, 255},
  {"Lime", "Limette", 15500, 255},   {"Green", "Gr\x81n", 21845, 255},
  {"Mint", "Mint", 27300, 255},      {"Cyan", "Cyan", 32768, 255},
  {"Sky blue", "Himmelblau", 37300, 255}, {"Blue", "Blau", 42800, 255},
  {"Indigo", "Indigo", 46400, 255},  {"Purple", "Lila", 51900, 255},
  {"Magenta", "Magenta", 55500, 255}, {"Pink", "Pink", 59200, 255},
  {"Rose", "Rosa", 62800, 255},      {"White", "Wei\xE1", 0, 0},
};
const uint8_t COLOUR_COUNT = sizeof(COLOURS) / sizeof(COLOURS[0]);

// Screen settings (from the app)
// The same numbers as bgx::Kind and the app. BG_PLAIN = no animation (the normal screen).
enum BgAnim : uint8_t {
  BG_AQUARIUM, BG_PLAIN, BG_SYNTHWAVE, BG_LAVA, BG_SPACE, BG_FIRE, BG_MATRIX, BG_RAIN, BG_SEASONS,
  BG_CLOCK, BG_STATS, BG_TIMER, BG_PICTURE, BG_COUNT};
uint8_t bgAnim = BG_AQUARIUM;    // background while no music screen is shown
bool showFish = true;            // fish in the aquarium
uint8_t bgOptions = 0x01;        // option bits of the other backgrounds (see Backgrounds.h)
uint8_t padMonth = 0;            // 1-12 from the PC (for "Seasons"), kept in flash
// Widgets: time, PC stats and the focus timer come from the app
uint32_t clockBase = 0, clockAt = 0;     // local time (s since 1970) at millis() clockAt; 0 = unknown
float pcCpu = -1, pcRam = -1, pcGpu = -1, pcGpuTemp = -1;
uint32_t statsAt = 0;
float timerLeft = 0, timerTotal = 0;
uint8_t timerPhase = 0, timerRound = 0;
bool timerPaused = false;
uint32_t timerAt = 0;
// Own picture in the "spiffs" flash area: 16-byte header, then RGB565 frames
struct PicHeader {
  uint32_t magic;                        // 'MPIC' once complete
  uint16_t w, h, frames, delayMs;
  uint32_t crc;                          // CRC-32 of the pixel data
};
const uint32_t PIC_MAGIC = 0x4349504D;
const esp_partition_t *picPart = nullptr;
const void *picMap = nullptr;
esp_partition_mmap_handle_t picMapHandle = 0;
PicHeader picHeader = {};
uint32_t picExpect = 0, picGot = 0, picOffset = 0;  // a part of an upload being received
uint32_t picLastByte = 0;
uint8_t *picBuf = nullptr;
uint8_t screenLevel = 16;        // backlight when "bright", 1-16
bool showMusic = true;           // music screen (cover, title, volume) while music plays

// Settings messages from the app since the last "W" (save)
uint16_t cfgAccepted = 0, cfgRejected = 0;

uint8_t lightColour = 11;          // index into COLOURS, starts at Purple
bool colourKeyHeld = false;        // Fun 2 is down
bool colourKnobUsed = false;       // knob was turned while holding it
uint8_t lightMode = L_RAINBOW;
uint8_t lightPct = 60;          // 10-100 % of LED_MAX
bool lightKeyHeld = false;      // light key is down
bool lightKnobUsed = false;     // knob was turned while holding it
uint32_t keyPressedAt[KEY_COUNT] = {0}; // for the "Key glow" mode
float audioTarget = 0;          // latest music level from the helper, 0-1
float audioLevel = 0;           // smoothed level used for the lights
uint32_t lastLevelAt = 0;
bool lightsNeedSave = false;
uint32_t lightsChangedAt = 0;

// ============================================================================
//  Helpers
// ============================================================================

// Milliseconds from t to now. Signed on purpose: a time stamped a moment
// *after* 'now' was read (by a message that just came in) gives a small
// negative number here, not a huge positive one that looks like "long ago".
int32_t msSince(uint32_t now, uint32_t t) {
  return (int32_t)(now - t);
}

const char *tr(Txt t) {
  return (padLang == 1 ? TEXT_DE : TEXT_EN)[t];
}

const char *colourName(uint8_t i) {
  return padLang == 1 ? COLOURS[i].de : COLOURS[i].en;
}

// Backlight chip level (0-16) for brightness step 0 (bright), 1 (dim), 2 (off)
uint8_t backlightFor(uint8_t idx) {
  if (padAsleep) return 0;                 // asleep: screen dark
  if (idx == 0) return screenLevel;
  if (idx == BRIGHT_DIM) return max(1, screenLevel / 4);
  return 0;
}

// Name of a light mode in the pad's language (own schemes: the name from the app)
const char *modeName(uint8_t mode) {
  if (mode >= L_CUSTOM && mode < MODE_COUNT) return schemes[mode - L_CUSTOM].name;
  if (mode >= L_COUNT) mode = L_OFF;
  return (padLang == 1 ? LIGHT_NAMES_DE : LIGHT_NAMES_EN)[mode];
}

// Can the Lights key / the app pick this mode right now?
bool modeAvailable(uint8_t mode) {
  if (mode == L_OFF) return true;                       // "off" is always there
  if (mode < L_BUILTIN_ON) return builtinMask & (1 << mode);
  if (mode >= L_CUSTOM && mode < MODE_COUNT) return schemes[mode - L_CUSTOM].used;
  return false;
}

// First mode that can be used (after a scheme was deleted or modes were switched off)
uint8_t firstAvailableMode() {
  for (uint8_t m = 0; m < L_BUILTIN_ON; m++)
    if (modeAvailable(m)) return m;
  for (uint8_t m = L_CUSTOM; m < MODE_COUNT; m++)
    if (modeAvailable(m)) return m;
  return L_OFF;
}

// Lights key: built-in modes, then the own schemes, then "off", then around again
uint8_t nextLightMode(uint8_t mode) {
  static const uint8_t ORDER_LEN = MODE_COUNT;
  uint8_t order[ORDER_LEN], n = 0;
  for (uint8_t m = 0; m < L_BUILTIN_ON; m++) order[n++] = m;
  for (uint8_t m = L_CUSTOM; m < MODE_COUNT; m++) order[n++] = m;
  order[n++] = L_OFF;
  uint8_t at = 0;
  for (uint8_t i = 0; i < n; i++)
    if (order[i] == mode) at = i;
  for (uint8_t step = 1; step <= n; step++) {
    uint8_t m = order[(at + step) % n];
    if (modeAvailable(m)) return m;
  }
  return L_OFF;
}

bool helperAlive(uint32_t now) {
  if (lastHelperMsg != 0 && msSince(now, lastHelperMsg) >= (int32_t)HELPER_TIMEOUT) lastHelperMsg = 0;  // gone
  return lastHelperMsg != 0;
}

// True while the start-up show runs (light settings are locked meanwhile).
bool introActive(uint32_t now) {
  return now - introStart < introLength;
}

const char *playerName() {
  return np.player[0] ? np.player : "Music";
}

uint16_t playerColor() {
  if (strcasecmp(np.player, "Deezer") == 0) return C_DEEZER;
  if (strcasecmp(np.player, "Spotify") == 0) return C_GREEN;
  return C_TEXT;
}

// With the helper running, Play / Next / Prev go straight to the music app
// (so a browser video cannot steal them). Returns the message, or nullptr.
const char *helperMediaCommand(uint16_t code) {
  switch (code) {
    case CONSUMER_CONTROL_PLAY_PAUSE:    return "P\n";
    case CONSUMER_CONTROL_SCAN_NEXT:     return "N\n";
    case CONSUMER_CONTROL_SCAN_PREVIOUS: return "B\n";
    default:                             return nullptr;
  }
}

void setToast(const char *text, uint16_t bg, uint16_t fg) {
  portENTER_CRITICAL(&toastMux);
  strlcpy(toastText, text, sizeof(toastText));
  toastUntil = millis() + TOAST_MS;
  toastBg = bg;
  toastFg = fg;
  portEXIT_CRITICAL(&toastMux);
  dirty = true;
}

void showToast(const char *text) {
  setToast(text, C_BLURPLE, C_TEXT);
}

// The chosen light colour as a screen colour (for the toast swatch).
uint16_t colourSwatch(uint8_t &luma) {
  uint32_t c = Adafruit_NeoPixel::ColorHSV(COLOURS[lightColour].hue, COLOURS[lightColour].sat, 255);
  uint8_t r = (c >> 16) & 0xFF, g = (c >> 8) & 0xFF, b = c & 0xFF;
  luma = (uint8_t)(0.3f * r + 0.59f * g + 0.11f * b);
  return rgb(r, g, b);
}

// Toast shown on the chosen colour, with dark text on light colours.
void showColourToast(const char *text) {
  uint8_t luma;
  uint16_t bg = colourSwatch(luma);
  setToast(text, bg, luma > 150 ? C_BG : C_TEXT);
}

// Save light settings 2 s after the last change (spares the flash).
void markLightsChanged() {
  lightsChangedAt = millis();
  lightsNeedSave = true;
}

void initButton(Button &b, uint8_t pin) {
  b.pin = pin;
  pinMode(pin, INPUT_PULLUP);
  b.raw = b.stable = (digitalRead(pin) == LOW);
  b.changedAt = 0;
}

// Feed a fresh reading (true = pressed). Returns true when the debounced state changed.
bool updateDebounced(Button &b, bool r, uint32_t now) {
  if (r != b.raw) {
    b.raw = r;
    b.changedAt = now;
  }
  if (r != b.stable && now - b.changedAt >= DEBOUNCE_MS) {
    b.stable = r;
    return true;
  }
  return false;
}

// For a button on its own pin (pressed = LOW).
bool updateButton(Button &b, uint32_t now) {
  return updateDebounced(b, digitalRead(b.pin) == LOW, now);
}

// Key matrix: rows are inputs with pull-ups, columns are outputs that idle HIGH.
void initMatrix() {
  for (uint8_t r = 0; r < ROWS; r++) pinMode(PIN_ROW[r], INPUT_PULLUP);
  for (uint8_t c = 0; c < COLS; c++) {
    pinMode(PIN_COL[c], OUTPUT);
    digitalWrite(PIN_COL[c], HIGH);
  }
}

// Pull one column LOW at a time; a pressed key in that column pulls its row
// LOW through its diode. The diodes stop any "ghost" keys when several keys
// are held. Takes about 50 microseconds for all 15 keys.
void scanMatrix() {
  for (uint8_t c = 0; c < COLS; c++) {
    digitalWrite(PIN_COL[c], LOW);
    delayMicroseconds(10);                  // let the lines settle
    for (uint8_t r = 0; r < ROWS; r++)
      matrixRaw[r * COLS + c] = (digitalRead(PIN_ROW[r]) == LOW);
    digitalWrite(PIN_COL[c], HIGH);
  }
}

void IRAM_ATTR encoderISR() {
  uint8_t s = (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  portENTER_CRITICAL_ISR(&encMux);
  encState = ((encState << 2) | s) & 0x0F;
  encRaw += ENC_TABLE[encState];
  portEXIT_CRITICAL_ISR(&encMux);
}

// Whole clicks turned since the last call (positive = clockwise).
int32_t takeEncoderClicks() {
  portENTER_CRITICAL(&encMux);
  int32_t clicks = encRaw / ENC_STEPS_PER_CLICK;
  encRaw -= clicks * ENC_STEPS_PER_CLICK;
  portEXIT_CRITICAL(&encMux);
  return ENC_REVERSE ? -clicks : clicks;
}

// Send one keyboard report holding every key-type button that is down right now,
// so several keys can be held together (for example as push-to-talk).
void sendKeyboardState() {
  KeyReport report = {};
  uint8_t n = 0;
  for (int i = 0; i < KEY_COUNT; i++) {
    if (keys[i].stable && held[i].type == ACT_KEY) {
      report.modifiers |= held[i].mods;
      if (n < 6 && held[i].code) report.keys[n++] = (uint8_t)held[i].code;
    }
  }
  if (bootButton.stable) {
    report.modifiers |= ACTION_BOOT.mods;
    if (n < 6) report.keys[n++] = (uint8_t)ACTION_BOOT.code;
  }
  Keyboard.sendReport(&report);
}

// The Lights and Fun 2 keys can get other jobs in the app, but only while the
// app is running: without it they are the light keys again, so the lights can
// always be changed on the pad.
// Keys the app does itself (ACT_APP) do their default job while it is off.
// A profile (overlay) only counts while the app runs.
const KeyAction &actionFor(int i, bool alive, bool layer2 = false) {
  if (layer2) {
    const KeyAction &a = actions2[i];
    return (a.type == ACT_APP && !alive) ? NO_ACTION : a;
  }
  ActionType d = DEFAULT_ACTIONS[i].type;
  if (!alive && (d == ACT_LIGHTS || d == ACT_COLOUR)) return DEFAULT_ACTIONS[i];
  if (alive && (overlayMask & (1u << i))) return overlay[i];
  if (!alive && actions[i].type == ACT_APP) return DEFAULT_ACTIONS[i];
  return actions[i];
}

// The app asked the pad to type a key (part of a macro / tap-hold): press and let go
void tapForApp(uint8_t type, uint16_t code, uint8_t mods) {
  if (type == ACT_MEDIA) {
    ConsumerControl.press(code);
    delay(10);
    ConsumerControl.release();
    return;
  }
  KeyReport r = {};
  r.modifiers = mods;
  r.keys[0] = (uint8_t)code;
  Keyboard.sendReport(&r);
  delay(10);
  sendKeyboardState();
}

// The T-Display-S3 backlight chip is set by counting pulses on its pin
// (16 levels), not by PWM. Same method as LilyGO's factory example.
void setBacklight(uint8_t value) {
  static uint8_t level = 0;
  const uint8_t steps = 16;
  if (value == 0) {
    digitalWrite(PIN_LCD_BL, LOW);
    delay(3);
    level = 0;
    return;
  }
  if (level == 0) {
    digitalWrite(PIN_LCD_BL, HIGH);
    level = steps;
    delayMicroseconds(30);
  }
  int from = steps - level;
  int to = steps - value;
  int pulses = (steps + to - from) % steps;
  for (int i = 0; i < pulses; i++) {
    digitalWrite(PIN_LCD_BL, LOW);
    digitalWrite(PIN_LCD_BL, HIGH);
  }
  level = value;
}

void tapMedia(uint16_t code) {
  ConsumerControl.press(code);
  delay(5);
  ConsumerControl.release();
}

// ============================================================================
//  Input handling
// ============================================================================

// A key was pressed: the background task feeds the fish or pokes its animation
void notePress(const char *label) {
  taskENTER_CRITICAL(&pokeMux);
  strlcpy(pokeLabel, label ? label : "", sizeof(pokeLabel));
  taskEXIT_CRITICAL(&pokeMux);
  aquariumFeeds = aquariumFeeds + 1;
}

void handleKeys(uint32_t now) {
  bool keyboardChanged = false;
  bool alive = helperAlive(now);

  scanMatrix();
  for (int i = 0; i < KEY_COUNT; i++) {
    if (!updateDebounced(keys[i], matrixRaw[i], now)) continue;
    if (keys[i].stable) {
      bool l2 = layerHeld > 0 && actions[i].type != ACT_LAYER;
      held[i] = actionFor(i, alive, l2);  // remember what this press does
      heldLayer2[i] = l2;
      keyPressedAt[i] = now;
      lastActivity = now;
      pcLocked = false;                   // someone is here
      notePress(held[i].label);           // fish food / the animated background reacts
    }
    const KeyAction &a = held[i];
    // the app counts presses (statistics) and does the ACT_APP keys
    if (alive) Serial.printf("P|%d|%d|%d|%d\n", i, keys[i].stable ? 1 : 0, heldLayer2[i] ? 1 : 0, a.type == ACT_APP ? 1 : 0);

    if (a.type == ACT_NONE) continue;
    if (a.type == ACT_APP) {
      if (keys[i].stable && a.label[0]) showToast(a.label);
      continue;
    }
    if (a.type == ACT_LAYER) {
      if (keys[i].stable) {
        layerHeld++;
        if (a.label[0]) showToast(a.label);
      } else if (layerHeld) {
        layerHeld--;
      }
      continue;
    }

    if (a.type == ACT_LIGHTS) {
      // Tap = next light mode. Hold + turn the knob = brightness (see handleKnob).
      if (keys[i].stable) {
        lightKeyHeld = true;
        lightKnobUsed = introActive(now);   // during the start-up show: no mode change
      } else {
        lightKeyHeld = false;
        if (!lightKnobUsed) {
          lightMode = nextLightMode(lightMode);
          char msg[40];
          snprintf(msg, sizeof(msg), tr(T_LIGHTS_FMT), modeName(lightMode));
          showToast(msg);
          markLightsChanged();
        }
      }
      continue;
    }

    if (a.type == ACT_COLOUR) {
      // Tap = send its key when let go. Hold + turn the knob = light colour (see handleKnob).
      if (keys[i].stable) {
        colourKeyHeld = true;
        colourKnobUsed = false;
      } else {
        colourKeyHeld = false;
        if (!colourKnobUsed) {
          if (a.code || a.mods) {
            KeyReport tap = {};
            tap.modifiers = a.mods;
            tap.keys[0] = (uint8_t)a.code;
            Keyboard.sendReport(&tap);
            delay(10);
            sendKeyboardState();            // release it, keep any other held keys
          }
          showToast(a.label);
        }
      }
      continue;
    }

    if (a.type == ACT_KEY) {
      keyboardChanged = true;
    } else if (keys[i].stable) {          // media key pressed
      const char *cmd = alive ? helperMediaCommand(a.code) : nullptr;
      if (cmd) {
        Serial.print(cmd);                // the app controls the music app directly
      } else {
        if (mediaKeyDown >= 0) ConsumerControl.release();
        ConsumerControl.press(a.code);    // no app: normal media key
        mediaKeyDown = i;
      }
    } else if (mediaKeyDown == i) {       // media key released
      ConsumerControl.release();
      mediaKeyDown = -1;
    }
    if (keys[i].stable && a.label[0]) showToast(a.label);
  }

  if (updateButton(bootButton, now)) {
    keyboardChanged = true;
    if (bootButton.stable) {
      showToast(ACTION_BOOT.label);
      notePress(ACTION_BOOT.label);
    }
  }
  if (keyboardChanged) sendKeyboardState();

  // Onboard button: cycle screen brightness bright -> dim -> off
  if (updateButton(io14Button, now) && io14Button.stable) {
    lastActivity = now;
    pcLocked = false;
    brightnessIdx = (brightnessIdx + 1) % BRIGHT_STEPS;
    setBacklight(backlightFor(brightnessIdx));
  }
}

void handleKnob(uint32_t now) {
  bool alive = helperAlive(now);

  int32_t clicks = takeEncoderClicks();
  if (clicks != 0) lastActivity = now;
  // Light settings are locked during the start-up show: turns are then swallowed.
  if (clicks != 0 && colourKeyHeld) {
    // Fun 2 held: the knob picks the colour for "Key glow" and "One colour"
    colourKnobUsed = true;
    if (!introActive(now)) {
      int c = ((int)lightColour + clicks) % COLOUR_COUNT;   // colour wheel, wraps around
      if (c < 0) c += COLOUR_COUNT;
      lightColour = c;
      char msg[40];
      snprintf(msg, sizeof(msg), tr(T_COLOUR_FMT), colourName(lightColour));
      showColourToast(msg);
      markLightsChanged();
    }
    clicks = 0;
  }
  if (clicks != 0 && lightKeyHeld) {
    // Lights key held: the knob sets LED brightness
    lightKnobUsed = true;
    if (!introActive(now)) {
      lightPct = constrain((int)lightPct + clicks * 10, 10, 100);
      char msg[40];
      snprintf(msg, sizeof(msg), tr(T_LIGHT_LEVEL_FMT), lightPct);
      showToast(msg);
      markLightsChanged();
    }
    clicks = 0;
  }
  if (clicks != 0) {
    lastKnobAt = now;
    dirty = true;
    if (alive) {
      // PC volume (or the music app's, see --app-volume), applied by the PC helper
      Serial.printf("V%+ld\n", (long)clicks);
      if (np.volume >= 0) {
        np.volume = constrain(np.volume + clicks * VOL_STEP, 0, 100);
        if (clicks > 0) np.muted = false;
      }
    } else {
      // No helper: plain Windows volume keys
      uint16_t code = clicks > 0 ? CONSUMER_CONTROL_VOLUME_INCREMENT : CONSUMER_CONTROL_VOLUME_DECREMENT;
      for (int32_t i = 0; i < abs(clicks); i++) tapMedia(code);
      showToast(tr(clicks > 0 ? T_WIN_VOL_UP : T_WIN_VOL_DOWN));
    }
  }

  if (updateButton(encButton, now) && encButton.stable) {
    if (lightKeyHeld || colourKeyHeld) {
      // Knob press while adjusting the lights: ignored (no accidental mute)
    } else if (alive) {
      Serial.print("M\n");
      np.muted = !np.muted;
      lastKnobAt = now;                   // the next helper update may still say the old state
      showToast(tr(np.muted ? T_MUTED : T_SOUND_ON));
    } else {
      tapMedia(CONSUMER_CONTROL_MUTE);
      showToast(tr(T_WIN_MUTE));
    }
  }
}

// Message from the helper:  S|player|playing|volume|muted|title|artist
void parseHelperLine(char *line) {
  const int FIELDS = 7;
  if (line[0] != 'S' || line[1] != '|') return;
  char *fields[FIELDS] = {nullptr};
  int n = 0;
  char *p = line;
  while (n < FIELDS) {
    fields[n++] = p;
    if (n == FIELDS) break;            // last field (artist) keeps any remaining text
    char *bar = strchr(p, '|');
    if (!bar) break;
    *bar = '\0';
    p = bar + 1;
  }
  if (n < FIELDS) return;

  uint32_t now = millis();
  const char *player = fields[1];
  bool playing = atoi(fields[2]) != 0;
  int volume = constrain(atoi(fields[3]), -1, 100);
  bool muted = atoi(fields[4]) != 0;
  const char *title = fields[5];
  const char *artist = fields[6];

  if (playing != np.playing || strcmp(player, np.player) != 0 ||
      strcmp(title, np.title) != 0 || strcmp(artist, np.artist) != 0)
    dirty = true;
  strlcpy(np.player, player, sizeof(np.player));
  np.playing = playing;
  strlcpy(np.title, title, sizeof(np.title));
  strlcpy(np.artist, artist, sizeof(np.artist));

  // Right after a knob turn, trust the local value so the bar does not jump back.
  if (msSince(now, lastKnobAt) > 400) {
    if (volume != np.volume || muted != np.muted) dirty = true;
    np.volume = volume;
    np.muted = muted;
  }
  lastHelperMsg = now;
}

// Message from the helper:  L|level   (music loudness 0-100, about 25 per second)
void parseLevelLine(const char *line) {
  if (line[0] != 'L' || line[1] != '|') return;
  audioTarget = constrain(atoi(line + 2), 0, 100) / 100.0f;
  lastLevelAt = millis();
}

// Message from the helper:  T|position_ms|length_ms   (song progress)
void parseTimeLine(const char *line) {
  if (line[0] != 'T' || line[1] != '|') return;
  char *end = nullptr;
  np.posMs = strtoul(line + 2, &end, 10);
  np.durMs = (end && *end == '|') ? strtoul(end + 1, nullptr, 10) : 0;
  np.posAt = millis();
}

// Message from the helper:  C|bytes|checksum   followed by exactly that many
// raw bytes: the album cover (COVER x COVER pixels, RGB565). C|0|0 = no cover.
void parseCoverLine(const char *line) {
  if (line[0] != 'C' || line[1] != '|') return;
  char *end = nullptr;
  size_t bytes = strtoul(line + 2, &end, 10);
  coverWantSum = (end && *end == '|') ? strtoul(end + 1, nullptr, 10) : 0;
  if (bytes == 0) {
    if (coverValid) dirty = true;
    coverValid = false;
    return;
  }
  if (bytes > 200000) return;   // garbled line: not a real cover
  coverExpect = bytes;
  coverGot = 0;
  coverSum = 0;
  coverLastByte = millis();
  coverSkip = bytes != (size_t)COVER * COVER * 2 || !coverPix[0] || !coverPix[1];
}

void finishCover() {
  coverExpect = 0;
  if (coverSkip) return;
  if (coverSum == coverWantSum) {
    coverShown ^= 1;   // show the new one; the old buffer takes the next cover
    coverValid = true;
    dirty = true;
  } else {
    Serial.print("R\n");   // something got lost on the way: ask for it again
  }
}

// ============================================================================
//  Settings from the Macro Pad app
// ============================================================================
// Each message takes effect at once; "W" then keeps them all in flash.
//   ?                              -> I|version|protocol|language|light mode|light %|colour
//   K|key|type|code|mods|label     one key (key 0-14, type = ActionType)
//   G|language                     0 English, 1 German
//   D|background|fish|level|music  0 aquarium / 1 plain, fish 0/1, backlight 1-16, music screen 0/1
//   LM|mode  LB|percent  LP|colour  LE|mask   light mode, brightness, colour, built-in modes in the rotation
//   LS|slot|effect|name|RRGGBB,RRGGBB,...    own light scheme (slot 0-9, 15 colours); empty name = delete
//   W                              save -> A|W|accepted|rejected
//   !BOOT                          restart into flash mode (firmware update from the app)

// Splits "a|b|c" in place. The last field keeps any further '|'. Returns the field count.
int splitFields(char *line, char **fields, int maxFields) {
  int n = 0;
  char *p = line;
  while (n < maxFields) {
    fields[n++] = p;
    if (n == maxFields) break;
    char *bar = strchr(p, '|');
    if (!bar) break;
    *bar = '\0';
    p = bar + 1;
  }
  return n;
}

// Whole number in [lo, hi]; false if the text is not one.
bool parseInt(const char *text, long lo, long hi, long &out) {
  if (!text || !*text) return false;
  char *end = nullptr;
  long v = strtol(text, &end, 10);
  if (*end != '\0' || v < lo || v > hi) return false;
  out = v;
  return true;
}

// Printable ASCII only (plus the German letters of the screen font), so a
// broken message can never put odd bytes on the screen.
void copyLabel(char *dst, size_t size, const char *src) {
  size_t n = 0;
  for (; *src && n + 1 < size; src++) {
    uint8_t c = (uint8_t)*src;
    if ((c >= 32 && c < 127) || c == 0x84 || c == 0x94 || c == 0x81 || c == 0x8E ||
        c == 0x99 || c == 0x9A || c == 0xE1)
      dst[n++] = (char)c;
  }
  dst[n] = '\0';
}

bool parseHexColour(const char *t, uint8_t *rgb) {
  for (int i = 0; i < 6; i++)
    if (!isxdigit((unsigned char)t[i])) return false;
  char part[3] = {0, 0, 0};
  for (int i = 0; i < 3; i++) {
    part[0] = t[i * 2];
    part[1] = t[i * 2 + 1];
    rgb[i] = (uint8_t)strtoul(part, nullptr, 16);
  }
  return true;
}

void sendInfo() {
  Serial.printf("I|%s|%u|%u|%u|%u|%u\n", FW_VERSION, PROTO_VERSION, padLang, lightMode, lightPct, lightColour);
}

void applyDisplay() {
  if (aquariumReady) tank.showFish = showFish;
  setBacklight(backlightFor(brightnessIdx));
  dirty = true;
}

// K|key|type|code|mods|label (layer 1), K2|... (layer 2), O|... (profile, not saved)
bool applyKeyLine(char **f, int n, KeyAction *into = actions, uint16_t *mask = nullptr) {
  long key, type, code, mods;
  if (n != 6 || !parseInt(f[1], 0, KEY_COUNT - 1, key) || !parseInt(f[2], 0, ACT_TYPE_COUNT - 1, type) ||
      !parseInt(f[3], 0, 0xFFFF, code) || !parseInt(f[4], 0, 0xFF, mods))
    return false;
  if ((type == ACT_KEY || type == ACT_COLOUR) && code > 0xFF) return false;   // keyboard codes are one byte
  if (into == actions2 && (type == ACT_LAYER || type == ACT_LIGHTS || type == ACT_COLOUR)) return false;
  KeyAction a;
  a.type = (ActionType)type;
  a.code = (uint16_t)code;
  a.mods = (uint8_t)mods;
  copyLabel(a.label, sizeof(a.label), f[5]);
  into[key] = a;
  if (mask) *mask |= (uint16_t)(1u << key);
  return true;
}

bool applySchemeLine(char **f, int n) {
  long slot, effect;
  if (n != 5 || !parseInt(f[1], 0, MAX_SCHEMES - 1, slot) || !parseInt(f[2], 0, FX_COUNT - 1, effect))
    return false;
  LightScheme &sc = schemes[slot];
  if (f[3][0] == '\0') {                 // empty name: delete the scheme
    memset(&sc, 0, sizeof(sc));
    if (!modeAvailable(lightMode)) lightMode = firstAvailableMode();
    return true;
  }
  LightScheme next = {};
  next.used = 1;
  next.effect = (uint8_t)effect;
  copyLabel(next.name, sizeof(next.name), f[3]);
  const char *p = f[4];
  for (int k = 0; k < KEY_COUNT; k++) {
    if (!parseHexColour(p, next.rgb[k])) return false;
    p += 6;
    if (k < KEY_COUNT - 1) {
      if (*p != ',') return false;
      p++;
    }
  }
  if (*p != '\0') return false;
  sc = next;
  return true;
}

// One settings message. Returns false if it is not one (or is broken).
bool applyConfigLine(char *line) {
  char *f[8];
  long v;
  if (line[0] == 'K' && line[1] == '|') {
    return applyKeyLine(f, splitFields(line, f, 6));
  }
  if (line[0] == 'K' && line[1] == '2' && line[2] == '|') {
    return applyKeyLine(f, splitFields(line, f, 6), actions2);
  }
  if (line[0] == 'N' && line[1] == '|') {       // N|owner name for the welcome
    copyLabel(ownerName, sizeof(ownerName), line + 2);
    return true;
  }
  if (line[0] == 'T' && line[1] == 'O' && line[2] == '|') {   // TO|minutes without a key until sleep
    if (!parseInt(line + 3, 0, 240, v)) return false;
    idleMinutes = (uint8_t)v;
    return true;
  }
  if (line[0] == 'G' && line[1] == '|') {
    if (!parseInt(line + 2, 0, 1, v)) return false;
    padLang = (uint8_t)v;
    dirty = true;
    return true;
  }
  if (line[0] == 'D' && line[1] == '|') {
    // D|background|fish|brightness|music[|options]
    long bg, fish, level, music, opts = bgOptions;
    int n = splitFields(line, f, 6);
    if ((n != 5 && n != 6) || !parseInt(f[1], 0, BG_COUNT - 1, bg) || !parseInt(f[2], 0, 1, fish) ||
        !parseInt(f[3], 1, 16, level) || !parseInt(f[4], 0, 1, music) || (n == 6 && !parseInt(f[5], 0, 0xFF, opts)))
      return false;
    bgAnim = (uint8_t)bg;
    showFish = fish;
    screenLevel = (uint8_t)level;
    showMusic = music;
    bgOptions = (uint8_t)opts;
    applyDisplay();
    return true;
  }
  if (line[0] == 'L' && line[1] && line[2] == '|') {
    switch (line[1]) {
      case 'M':
        if (!parseInt(line + 3, 0, MODE_COUNT - 1, v) || !modeAvailable((uint8_t)v)) return false;
        lightMode = (uint8_t)v;
        return true;
      case 'B':
        if (!parseInt(line + 3, 10, 100, v)) return false;
        lightPct = (uint8_t)v;
        return true;
      case 'P':
        if (!parseInt(line + 3, 0, COLOUR_COUNT - 1, v)) return false;
        lightColour = (uint8_t)v;
        return true;
      case 'E':
        if (!parseInt(line + 3, 0, (1 << L_BUILTIN_ON) - 1, v)) return false;
        builtinMask = (uint8_t)v;
        if (!modeAvailable(lightMode)) lightMode = firstAvailableMode();
        return true;
      case 'S':
        return applySchemeLine(f, splitFields(line, f, 5));
    }
  }
  return false;
}

// Everything the app can change, into flash (and loaded again at power-on).
void saveSettings() {
  prefs.putBytes("keys", actions, sizeof(actions));
  prefs.putBytes("keys2", actions2, sizeof(actions2));
  prefs.putString("owner", ownerName);
  prefs.putUChar("idle", idleMinutes);
  prefs.putBytes("schemes", schemes, sizeof(schemes));
  prefs.putUChar("bmask", builtinMask);
  prefs.putUChar("lang", padLang);
  prefs.putUChar("bg", bgAnim);
  prefs.putBool("fish", showFish);
  prefs.putUChar("bgopt", bgOptions);
  prefs.putUChar("scr", screenLevel);
  prefs.putBool("music", showMusic);
  prefs.putUChar("mode", lightMode);
  prefs.putUChar("level", lightPct);
  prefs.putUChar("colour", lightColour);
  lightsNeedSave = false;
}

void loadSettings() {
  memcpy(actions, DEFAULT_ACTIONS, sizeof(actions));
  memset(schemes, 0, sizeof(schemes));
  if (prefs.getBytesLength("keys") == sizeof(actions)) {
    KeyAction stored[KEY_COUNT];
    prefs.getBytes("keys", stored, sizeof(stored));
    for (int i = 0; i < KEY_COUNT; i++) {
      stored[i].label[sizeof(stored[i].label) - 1] = '\0';
      if (stored[i].type < ACT_TYPE_COUNT) actions[i] = stored[i];   // anything odd: keep the default
    }
  }
  for (auto &a : actions2) a = NO_ACTION;
  if (prefs.getBytesLength("keys2") == sizeof(actions2)) {
    KeyAction stored[KEY_COUNT];
    prefs.getBytes("keys2", stored, sizeof(stored));
    for (int i = 0; i < KEY_COUNT; i++) {
      stored[i].label[sizeof(stored[i].label) - 1] = '\0';
      if (stored[i].type < ACT_TYPE_COUNT && stored[i].type != ACT_LAYER) actions2[i] = stored[i];
    }
  }
  prefs.getString("owner", ownerName, sizeof(ownerName));
  idleMinutes = prefs.getUChar("idle", 0);
  if (idleMinutes > 240) idleMinutes = 0;
  if (prefs.getBytesLength("schemes") == sizeof(schemes)) {
    prefs.getBytes("schemes", schemes, sizeof(schemes));
    for (auto &sc : schemes) {
      sc.name[sizeof(sc.name) - 1] = '\0';
      if (sc.effect >= FX_COUNT || (sc.used && !sc.name[0])) memset(&sc, 0, sizeof(sc));
    }
  }
  builtinMask = prefs.getUChar("bmask", 0x3F) & 0x3F;
  padLang = prefs.getUChar("lang", 0) > 1 ? 0 : prefs.getUChar("lang", 0);
  bgAnim = prefs.getUChar("bg", BG_AQUARIUM);
  if (bgAnim >= BG_COUNT) bgAnim = BG_AQUARIUM;
  showFish = prefs.getBool("fish", true);
  bgOptions = prefs.getUChar("bgopt", 0x01);
  padMonth = prefs.getUChar("month", 0);
  if (padMonth > 12) padMonth = 0;
  screenLevel = constrain(prefs.getUChar("scr", 16), 1, 16);
  showMusic = prefs.getBool("music", true);
  lightMode = prefs.getUChar("mode", L_RAINBOW);
  if (lightMode >= MODE_COUNT || !modeAvailable(lightMode)) lightMode = firstAvailableMode();
  lightPct = constrain(prefs.getUChar("level", 60), 10, 100);
  lightColour = prefs.getUChar("colour", 11);
  if (lightColour >= COLOUR_COUNT) lightColour = 11;
}

// A line that is not a music message: app settings, info request, update mode.
// ---------------------------------------------------------------------------
//  Own picture: stored in the flash area after the app (kept by firmware updates)
// ---------------------------------------------------------------------------
uint32_t crc32Update(uint32_t crc, const uint8_t *p, size_t n) {
  crc = ~crc;
  while (n--) {
    crc ^= *p++;
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320UL & (0 - (crc & 1)));
  }
  return ~crc;
}

// The screen task must not read the picture while it changes
void unmapPicture() {
  bool locked = screenLock && xSemaphoreTake(screenLock, pdMS_TO_TICKS(500)) == pdTRUE;
  effects.setPicture(nullptr, 0, 0, 0, 0);
  if (picMap) {
    esp_partition_munmap(picMapHandle);
    picMap = nullptr;
  }
  if (locked) xSemaphoreGive(screenLock);
}

// Shows the stored picture (if there is a complete one)
void loadPicture() {
  if (!picPart) picPart = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, nullptr);
  unmapPicture();
  memset(&picHeader, 0, sizeof(picHeader));
  if (!picPart || esp_partition_read(picPart, 0, &picHeader, sizeof(picHeader)) != ESP_OK) return;
  size_t bytes = (size_t)picHeader.w * picHeader.h * picHeader.frames * 2;
  bool sizeOk = (picHeader.w == 320 && picHeader.h == 170) || (picHeader.w == 160 && picHeader.h == 85);
  if (picHeader.magic != PIC_MAGIC || !sizeOk || !picHeader.frames || bytes + 16 > picPart->size) {
    picHeader.magic = 0;
    return;
  }
  if (esp_partition_mmap(picPart, 0, bytes + 16, ESP_PARTITION_MMAP_DATA, &picMap, &picMapHandle) != ESP_OK) {
    picMap = nullptr;
    return;
  }
  if (effectsReady) {
    bool locked = screenLock && xSemaphoreTake(screenLock, pdMS_TO_TICKS(500)) == pdTRUE;
    effects.setPicture((const uint16_t *)((const uint8_t *)picMap + 16), picHeader.w, picHeader.h, picHeader.frames,
                       picHeader.delayMs);
    if (locked) xSemaphoreGive(screenLock);
  }
}

// IP = which picture is stored, IB|w|h|frames|delay|bytes = start (erases the area),
// IC|offset|length + raw bytes = one part, IE|crc = done, IX = delete
void handlePictureLine(char *line) {
  char *f[8];
  int n = splitFields(line, f, 7);
  if (line[1] == 'P') {
    Serial.printf("IP|%lu|%u\n", picHeader.magic == PIC_MAGIC ? (unsigned long)picHeader.crc : 0UL, picHeader.frames);
    return;
  }
  if (!picPart) {
    Serial.print("IA|0|no space\n");
    return;
  }
  if (line[1] == 'X') {
    unmapPicture();
    esp_partition_erase_range(picPart, 0, 4096);
    picHeader.magic = 0;
    Serial.print("IA|1\n");
    return;
  }
  if (line[1] == 'B') {
    long w, h, frames, delayMs, bytes;
    if (n != 6 || !parseInt(f[1], 160, 320, w) || !parseInt(f[2], 85, 170, h) || !parseInt(f[3], 1, 999, frames) ||
        !parseInt(f[4], 20, 10000, delayMs) || !parseInt(f[5], 1, 0x7FFFFFFF, bytes) ||
        bytes != w * h * frames * 2 || (size_t)bytes + 16 > picPart->size) {
      Serial.print("IA|0|bad size\n");
      return;
    }
    setToast(tr(T_PICTURE), C_DEEZER, C_TEXT);
    unmapPicture();
    size_t erase = ((size_t)bytes + 16 + 4095) & ~(size_t)4095;
    if (esp_partition_erase_range(picPart, 0, erase) != ESP_OK) {
      Serial.print("IA|0|erase\n");
      return;
    }
    picHeader = {0, (uint16_t)w, (uint16_t)h, (uint16_t)frames, (uint16_t)delayMs, 0};
    if (!picBuf) picBuf = (uint8_t *)malloc(4096);
    Serial.print("IR\n");
    return;
  }
  if (line[1] == 'C') {
    long off, len;
    if (n != 3 || !parseInt(f[1], 0, 0x7FFFFFFF, off) || !parseInt(f[2], 1, 4096, len) || !picBuf) {
      Serial.print("IA|0|bad part\n");
      return;
    }
    picOffset = (uint32_t)off;
    picExpect = (uint32_t)len;
    picGot = 0;
    picLastByte = millis();
    return;                                // the raw bytes follow (readSerial)
  }
  if (line[1] == 'E') {
    unsigned long want = n == 2 ? strtoul(f[1], nullptr, 10) : 0;
    size_t bytes = (size_t)picHeader.w * picHeader.h * picHeader.frames * 2;
    uint32_t crc = 0;
    uint8_t buf[512];
    for (size_t pos = 0; pos < bytes; pos += sizeof(buf)) {
      size_t k = min(sizeof(buf), bytes - pos);
      esp_partition_read(picPart, 16 + pos, buf, k);
      crc = crc32Update(crc, buf, k);
    }
    if (crc != want || !bytes) {
      Serial.print("IA|0|crc\n");
      return;
    }
    picHeader.magic = PIC_MAGIC;
    picHeader.crc = crc;
    esp_partition_write(picPart, 0, &picHeader, sizeof(picHeader));
    loadPicture();
    Serial.print("IA|1\n");
  }
}

// raw bytes of one picture part, written to flash when complete
void receivePictureBytes(size_t &budget) {
  size_t n = min((size_t)Serial.available(), min((size_t)(picExpect - picGot), budget));
  n = Serial.read(picBuf + picGot, n);
  picGot += n;
  if (n) picLastByte = millis();
  budget -= n;
  if (picGot >= picExpect) {
    bool ok = esp_partition_write(picPart, 16 + picOffset, picBuf, picExpect) == ESP_OK;
    Serial.printf("IK|%lu|%d\n", (unsigned long)picOffset, ok ? 1 : 0);
    picExpect = 0;
  }
}

void handleAppLine(char *line) {
  if (strcmp(line, "?") == 0) {
    sendInfo();
  } else if (strcmp(line, "W") == 0) {
    saveSettings();
    Serial.printf("A|W|%u|%u\n", cfgAccepted, cfgRejected);
    cfgAccepted = cfgRejected = 0;
  } else if (strcmp(line, "!BOOT") == 0) {
    // Firmware update: the app flashes the pad from its ROM bootloader, which
    // shows up as a new COM port. Settings in flash are kept.
    setToast(tr(T_UPDATE), C_RED, C_TEXT);
    strip.clear();
    strip.show();
    Serial.flush();
    delay(200);
    usb_persist_restart(RESTART_BOOTLOADER);
  } else if (line[0] == 'O' && line[1] == '|') {
    // O|key|type|code|mods|label: the profile of the program in front; O|- = none
    if (strcmp(line, "O|-") == 0) {
      overlayMask = 0;
    } else {
      char *f[7];
      applyKeyLine(f, splitFields(line, f, 6), overlay, &overlayMask);
    }
  } else if (line[0] == 'K' && line[1] == 'S' && line[2] == '|') {
    // KS|type|code|mods: type this key for the app (macros, tap/hold)
    char *f[5];
    long type, code, mods;
    if (splitFields(line, f, 4) == 4 && parseInt(f[1], 0, ACT_MEDIA, type) && parseInt(f[2], 0, 0xFFFF, code) &&
        parseInt(f[3], 0, 0xFF, mods) && (type == ACT_MEDIA || code <= 0xFF))
      tapForApp((uint8_t)type, (uint16_t)code, (uint8_t)mods);
  } else if (line[0] == 'H' && line[1] == '|') {
    // H|key|RRGGBB = this key's light, H|key|- = back to normal, H|- = all back
    char *f[4];
    long key;
    int n = splitFields(line, f, 3);
    if (n == 2 && strcmp(f[1], "-") == 0) {
      highlightMask = 0;
    } else if (n == 3 && parseInt(f[1], 0, KEY_COUNT - 1, key)) {
      if (strcmp(f[2], "-") == 0) highlightMask &= ~(uint16_t)(1u << key);
      else if (parseHexColour(f[2], highlightRGB[key])) highlightMask |= (uint16_t)(1u << key);
    }
  } else if (line[0] == 'S' && line[1] == 'L' && line[2] == '|') {
    pcLocked = line[3] == '1';              // SL|1 = the PC is locked, SL|0 = back
    if (!pcLocked) lastActivity = millis();
  } else if (line[0] == 'Z' && line[1] == '|') {
    // Z|month[|local time in s since 1970] from the app (Seasons background, clock)
    long m;
    char *f[4];
    int n = splitFields(line, f, 3);
    if (n >= 2 && parseInt(f[1], 1, 12, m) && m != padMonth) {
      padMonth = (uint8_t)m;
      prefs.putUChar("month", padMonth);
    }
    if (n == 3) {
      unsigned long t = strtoul(f[2], nullptr, 10);
      if (t > 1600000000UL) {
        clockBase = (uint32_t)t;
        clockAt = millis();
      }
    }
  } else if (line[0] == 'Q' && line[1] == '|') {
    // Q|cpu|ram|gpu|gpu temperature (-1 = unknown)
    char *f[6];
    long v[4];
    if (splitFields(line, f, 5) == 5 && parseInt(f[1], -1, 100, v[0]) && parseInt(f[2], -1, 100, v[1]) &&
        parseInt(f[3], -1, 100, v[2]) && parseInt(f[4], -1, 150, v[3])) {
      pcCpu = v[0]; pcRam = v[1]; pcGpu = v[2]; pcGpuTemp = v[3];
      statsAt = millis();
    }
  } else if (line[0] == 'U' && line[1] == '|') {
    // U|seconds left|total|phase|round|paused: the focus timer (phase 0 = off)
    char *f[7];
    long v[5];
    if (splitFields(line, f, 6) == 6 && parseInt(f[1], 0, 86400, v[0]) && parseInt(f[2], 0, 86400, v[1]) &&
        parseInt(f[3], 0, 3, v[2]) && parseInt(f[4], 0, 9, v[3]) && parseInt(f[5], 0, 1, v[4])) {
      timerLeft = v[0]; timerTotal = v[1]; timerPhase = v[2]; timerRound = v[3]; timerPaused = v[4];
      timerAt = millis();
    }
  } else if (line[0] == 'I' && line[1] && (line[2] == '|' || line[2] == '\0') && strchr("BCEPX", line[1])) {
    handlePictureLine(line);
  } else if (applyConfigLine(line)) {
    cfgAccepted++;
  } else if (line[0] && line[0] != 'S') {
    cfgRejected++;
    Serial.printf("A|E|%.12s\n", line);   // tells the app which message was not understood
  }
}

void readSerial() {
  uint32_t now = millis();
  if (coverExpect && now - coverLastByte > 1500) coverExpect = 0;  // transfer stuck: give up
  if (picExpect && now - picLastByte > 2000) picExpect = 0;
  size_t budget = 8192;   // per loop pass, so keys stay quick while a cover comes in
  if (Serial.available() && lastHelperMsg != 0) lastHelperMsg = now;  // anything from the helper: still there
  while (budget && Serial.available()) {
    if (picExpect) {
      receivePictureBytes(budget);
      continue;
    }
    if (coverExpect) {
      // raw cover bytes
      size_t n = min((size_t)Serial.available(), min(coverExpect - coverGot, budget));
      uint8_t drop[256];
      uint8_t *dst = coverSkip ? drop : (uint8_t *)coverPix[coverShown ^ 1] + coverGot;
      if (coverSkip && n > sizeof(drop)) n = sizeof(drop);
      n = Serial.read(dst, n);
      if (n == 0) break;
      for (size_t i = 0; i < n; i++) coverSum += dst[i];
      coverGot += n;
      budget -= n;
      coverLastByte = now;
      if (coverGot >= coverExpect) finishCover();
      continue;
    }
    char c = (char)Serial.read();
    budget--;
    if (c == '\r') continue;
    if (c == '\n') {
      rxLine[rxLen] = '\0';
      if (rxLine[0] == 'L' && rxLine[1] == '|') parseLevelLine(rxLine);
      else if (rxLine[0] == 'T' && rxLine[1] == '|') parseTimeLine(rxLine);
      else if (rxLine[0] == 'C' && rxLine[1] == '|') parseCoverLine(rxLine);
      else if (rxLine[0] == 'S' && rxLine[1] == '|') parseHelperLine(rxLine);
      else handleAppLine(rxLine);
      rxLen = 0;
    } else if (rxLen < sizeof(rxLine) - 1) {
      rxLine[rxLen++] = c;
    }
  }
}

// ============================================================================
//  Screen  (320 x 170 landscape)
// ============================================================================

// Built-in font: each character is 6 * size pixels wide, 8 * size tall.
void printFitted(const char *text, int16_t x, int16_t y, uint8_t size, uint16_t color, int maxChars) {
  gfx->setTextSize(size);
  gfx->setTextColor(color);
  gfx->setCursor(x, y);
  if ((int)strlen(text) <= maxChars) {
    gfx->print(text);
  } else {
    char buf[64];
    int keep = min(maxChars - 3, (int)sizeof(buf) - 4);
    memcpy(buf, text, keep);
    strcpy(buf + keep, "...");
    gfx->print(buf);
  }
}

// Music screen layout: cover on the left, everything else in a column on the right
const int16_t COVER_X = 12, COVER_Y = 25;
const int16_t COL_X = 144, COL_W = 166;

// One line of text in the right column; scrolls sideways when it is too long.
// Returns true while scrolling (needs animation). Drawn before the cover,
// which then hides anything that slid too far left.
bool drawScrollText(const char *text, int16_t y, uint8_t size, uint16_t color, uint32_t now) {
  const int16_t X = COL_X, W = COL_W;
  const int16_t charW = 6 * size, h = 8 * size;
  gfx->setTextSize(size);
  gfx->setTextColor(color);
  int32_t textW = (int32_t)strlen(text) * charW;
  if (textW <= W) {
    gfx->setCursor(X, y);
    gfx->print(text);
    return false;
  }
  const int32_t gap = 40, pause = 60;              // pause: about 2 s at the start
  int32_t period = textW + gap;
  int32_t t = (now / 30) % (period + pause);       // about 33 pixels per second
  int32_t offset = t < pause ? 0 : t - pause;
  gfx->setCursor(X - offset, y);
  gfx->print(text);
  gfx->setCursor(X - offset + period, y);          // the start comes round again
  gfx->print(text);
  gfx->fillRect(0, y, X, h, C_BG);                 // left of the column (the cover comes on top)
  gfx->fillRect(X + W, y, 320 - X - W, h, C_BG);   // right margin
  return true;
}

// Album cover with rounded corners, or a music note when there is none
void drawCover() {
  const int16_t R = 8;
  if (coverValid && coverPix[coverShown]) {
    gfx->draw16bitRGBBitmap(COVER_X, COVER_Y, coverPix[coverShown], COVER, COVER);
    for (int16_t dy = 0; dy < R; dy++)
      for (int16_t dx = 0; dx < R; dx++) {
        float ex = R - dx - 0.5f, ey = R - dy - 0.5f;
        if (ex * ex + ey * ey <= R * R) continue;      // inside the rounding: keep
        int16_t l = COVER_X + dx, r = COVER_X + COVER - 1 - dx;
        int16_t t = COVER_Y + dy, b = COVER_Y + COVER - 1 - dy;
        gfx->drawPixel(l, t, C_BG);
        gfx->drawPixel(r, t, C_BG);
        gfx->drawPixel(l, b, C_BG);
        gfx->drawPixel(r, b, C_BG);
      }
    return;
  }
  gfx->fillRoundRect(COVER_X, COVER_Y, COVER, COVER, R, C_FAINT);
  uint16_t c = np.player[0] ? playerColor() : C_DIM;   // two beamed notes
  int16_t cx = COVER_X + COVER / 2, cy = COVER_Y + COVER / 2;
  gfx->fillEllipse(cx - 18, cy + 20, 11, 8, c);
  gfx->fillEllipse(cx + 16, cy + 14, 11, 8, c);
  gfx->fillRect(cx - 11, cy - 22, 5, 42, c);
  gfx->fillRect(cx + 23, cy - 28, 5, 42, c);
  gfx->fillTriangle(cx - 11, cy - 22, cx + 28, cy - 28, cx + 28, cy - 19, c);
  gfx->fillTriangle(cx - 11, cy - 22, cx + 28, cy - 19, cx - 11, cy - 13, c);
}

// Thin line with a dot at the current position of the song
void drawProgress(uint32_t now) {
  const int16_t Y = 88;
  gfx->fillRoundRect(COL_X, Y, COL_W, 3, 1, C_FAINT);
  if (np.durMs == 0 || !np.title[0]) return;           // app does not tell the length
  uint32_t pos = np.posMs + (np.playing ? max<int32_t>(msSince(now, np.posAt), 0) : 0);
  if (pos > np.durMs) pos = np.durMs;
  int16_t w = (int64_t)COL_W * pos / np.durMs;
  gfx->fillRoundRect(COL_X, Y, max<int16_t>(w, 3), 3, 1, C_TEXT);
  gfx->fillCircle(COL_X + w, Y + 1, 5, C_TEXT);
}

// Round button in the middle: pause sign while playing, play triangle when paused
void drawPlayButton() {
  const int16_t CX = COL_X + COL_W / 2, CY = 116;
  gfx->fillCircle(CX, CY, 14, C_TEXT);
  if (np.playing) {
    gfx->fillRect(CX - 6, CY - 7, 4, 15, C_BG);
    gfx->fillRect(CX + 2, CY - 7, 4, 15, C_BG);
  } else {
    gfx->fillTriangle(CX - 4, CY - 8, CX - 4, CY + 8, CX + 8, CY, C_BG);
  }
}

// The volume (PC, or the app's) as a row of bars shaped like a sound wave: the coloured
// part is the volume. While music plays, the bars move with it.
bool drawVolumeWave(uint32_t now) {
  const int BARS = 23;
  const int16_t X = COL_X, YC = 147, HMAX = 24, STEP = 6, BW = 3;
  static const uint8_t SHAPE[BARS] = {30, 50, 35, 65, 85, 55, 100, 75, 45, 90, 70, 40,
                                      80, 95, 60, 35, 70, 85, 50, 65, 40, 55, 30};
  static float level = 0;
  bool moving = np.playing && msSince(now, lastLevelAt) < 400;   // the helper sends levels while music plays
  float target = moving ? audioTarget : 0;
  level += (target - level) * (target > level ? 0.5f : 0.15f);

  int lit = np.volume < 0 ? 0 : (np.volume * BARS + 50) / 100;
  uint16_t on = np.muted ? C_DIM : playerColor();
  for (int i = 0; i < BARS; i++) {
    float k = moving ? (0.35f + 0.65f * level) * (0.8f + 0.2f * sinf(now * 0.009f + i * 1.7f)) : 0.55f;
    int16_t h = max(3, (int)(HMAX * SHAPE[i] / 100.0f * k + 0.5f));
    gfx->fillRoundRect(X + i * STEP, YC - h / 2, BW, h, 1, i < lit ? on : C_FAINT);
  }
  if (now - lastKnobAt < 1500)   // just turned: frame it
    gfx->drawRoundRect(X - 4, YC - HMAX / 2 - 4, BARS * STEP + 3, HMAX + 8, 4, C_TEXT);

  gfx->setTextSize(1);
  gfx->setTextColor(np.muted ? C_RED : C_TEXT);
  gfx->setCursor(X + BARS * STEP + 4, YC - 4);
  if (np.volume < 0)  gfx->print("--");
  else if (np.muted)  gfx->print("MUTE");
  else                gfx->printf("%d%%", np.volume);
  return moving || level > 0.01f;
}

// Key name etc. at the bottom of the screen. Returns true while it is shown.
bool drawToast(uint32_t now) {
  char text[sizeof(toastText)];
  uint32_t until;
  uint16_t bg, fg;
  portENTER_CRITICAL(&toastMux);
  memcpy(text, toastText, sizeof(text));
  until = toastUntil;
  bg = toastBg;
  fg = toastFg;
  portEXIT_CRITICAL(&toastMux);
  if ((int32_t)(until - now) <= 0) return false;
  gfx->fillRoundRect(10, 140, 300, 26, 6, bg);
  int16_t w = strlen(text) * 12;
  printFitted(text, 160 - w / 2, 145, 2, fg, 24);
  return true;
}

// Is there a song to show? (music screen switched on in the app, and the app
// reports a song). Otherwise the pad shows its background.
bool musicScreenWanted(uint32_t now) {
  return showMusic && helperAlive(now) && np.title[0];
}

// Returns true if something on screen is moving.
bool drawScreen(uint32_t now) {
  bool alive = helperAlive(now);
  bool animating = false;

  gfx->fillScreen(C_BG);
  gfx->setTextWrap(false);

  if (musicScreenWanted(now)) {
    char header[16];
    strlcpy(header, np.player[0] ? np.player : tr(T_MUSIC), sizeof(header));
    for (char *c = header; *c; c++) *c = toupper(*c);
    printFitted(header, COL_X, 24, 1, playerColor(), 27);
    animating |= drawScrollText(np.title, 36, 2, C_TEXT, now);
    animating |= drawScrollText(np.artist, 58, 2, C_DIM, now);
    if (np.playing && np.durMs) animating = true;      // progress dot moves
    drawCover();
    drawProgress(now);
    drawPlayButton();
    animating |= drawVolumeWave(now);
  } else if (alive) {
    // App running, no song (or music screen off), plain background chosen
    printFitted("MACRO PAD", 10, 8, 2, C_DIM, 20);
    printFitted(tr(T_CONNECTED), 10, 42, 2, C_TEXT, 25);
  } else {
    printFitted("MACRO PAD", 10, 8, 2, C_DIM, 20);
    printFitted(tr(T_OFFLINE), 10, 42, 2, C_TEXT, 25);
    printFitted(tr(T_KEYS_NORMAL), 10, 72, 2, C_DIM, 25);
    printFitted(tr(T_KNOB_WIN), 10, 96, 2, C_DIM, 25);
  }

  if (drawToast(now)) animating = true;
  if (now - lastKnobAt < 1500) animating = true;   // keeps the knob highlight timed
  return animating;
}

// Sleep while the PC is locked / asleep, or after idleMinutes without a key
void updateSleep(uint32_t now) {
  bool idle = idleMinutes && msSince(now, lastActivity) > (int32_t)(idleMinutes * 60000UL);
  // USB asleep = the PC is off or asleep but still powers the port. Asked every time
  // (not from events: after a restart of the PC there is no "resume", just a new start).
  // A key press shows the screen for a minute even then.
  bool usbAsleep = tud_suspended() && msSince(now, lastActivity) > 60000;
  bool sleep = !introActive(now) && (usbAsleep || (pcLocked && helperAlive(now)) || idle);
  if (sleep == padAsleep) return;
  padAsleep = sleep;
  setBacklight(sleep ? 0 : backlightFor(brightnessIdx));
  dirty = true;
}

void updateScreen(uint32_t now) {
  if (padAsleep) {                        // screen dark: nothing to draw
    aquariumWanted = false;
    return;
  }
  bool alive = helperAlive(now);
  static bool musicWas = false;
  bool music = musicScreenWanted(now);
  if (alive != helperWasAlive || music != musicWas) {
    helperWasAlive = alive;
    musicWas = music;
    dirty = true;
  }
  // Helper off (or start-up show): the aquarium task has the screen.
  // Ours is redrawn once it is back.
  // Aquarium: during the start-up show, and whenever no song is shown (app off,
  // nothing playing, or the music screen switched off) - if chosen in the app.
  bool animated = bgAnim == BG_AQUARIUM || (bgAnim != BG_PLAIN && effectsReady);
  aquariumWanted = aquariumReady &&
                   (introActive(now) || (AQUARIUM_WHEN_OFFLINE && animated && !musicScreenWanted(now)));
  if (aquariumWanted) {
    dirty = true;
    return;
  }
  // Redraw on change, 25 fps while something moves, plus one last frame after.
  if (dirty || ((wasAnimating) && now - lastFrame >= 40)) {
    // the aquarium may still be finishing its last frame: then try again next time
    if (screenLock && xSemaphoreTake(screenLock, 0) != pdTRUE) return;
    wasAnimating = drawScreen(now);
    gfx->flush();
    if (screenLock) xSemaphoreGive(screenLock);
    lastFrame = now;
    dirty = false;
  }
}

// ============================================================================
//  Aquarium  (while the PC helper is off)
// ============================================================================

// Small see-through box with a line of text (built-in font, size 1)
void aquariumLabel(const char *text, int16_t y) {
  int16_t w = strlen(text) * 6 + 12, h = 14;
  int16_t x = (320 - w) / 2;
  uint16_t *fb = gfx->getFramebuffer();
  for (int16_t yy = y; yy < y + h; yy++)
    for (int16_t xx = x; xx < x + w; xx++) {
      uint16_t &p = fb[yy * 320 + xx];
      p = (p >> 1) & 0x7BEF;  // half brightness
    }
  printFitted(text, x + 6, y + 3, 1, C_TEXT, 50);
}

// One centred line of the welcome. It fades in from the water colour (the
// built-in font cannot be see-through) and has a soft shadow. Returns the y below it.
int16_t greetLine(const char *text, uint8_t size, int16_t y, uint8_t r, uint8_t g, uint8_t b, float a) {
  int maxChars = 300 / (6 * size);
  if ((int)strlen(text) > maxChars && size > 1) {   // too long: one size smaller
    size--;
    maxChars = 300 / (6 * size);
  }
  int16_t w = min((int)strlen(text), maxChars) * 6 * size;
  int16_t x = (320 - w) / 2;
  const float wr = 28, wg = 100, wb = 160;          // water colour behind the text
  uint16_t shadow = rgb((int)(wr - 22 * a), (int)(wg - 80 * a), (int)(wb - 115 * a));
  uint16_t col = rgb((int)(wr + (r - wr) * a), (int)(wg + (g - wg) * a), (int)(wb + (b - wb) * a));
  int16_t s = size >= 3 ? 2 : 1;
  printFitted(text, x + s, y + s, size, shadow, maxChars);
  printFitted(text, x, y, size, col, maxChars);
  return y + 8 * size;
}

// The welcome on the water during the start-up show, fading in and out
void drawGreeting(float t) {
  const float IN = 1.5f, OUT = 4.2f;
  if (t <= IN || t >= OUT) return;
  float a = min(1.0f, (t - IN) / 0.3f) * min(1.0f, (OUT - t) / 0.4f);
  char first[48], third[48] = "";
  const char *owner = ownerName[0] ? ownerName : OWNER_NAME;
  if (owner[0]) snprintf(first, sizeof(first), "Welcome, %s!", owner);
  else strlcpy(first, "Welcome!", sizeof(first));
  if (MAKER_NAME[0]) snprintf(third, sizeof(third), "handcrafted by %s", MAKER_NAME);
  int16_t y = third[0] ? 40 : 51;
  y = greetLine(first, 3, y, 255, 255, 255, a) + 8;
  y = greetLine("to your Macro Pad", 2, y, 230, 244, 255, a) + 10;
  if (third[0]) greetLine(third, 2, y, 150, 220, 255, a);
}

// What the animated backgrounds and widgets need to know right now
bgx::Inputs effectInputs() {
  bgx::Inputs in;
  uint32_t now = millis();
  in.level = audioLevel;
  in.accentHue = COLOURS[lightColour].hue;
  in.accentSat = COLOURS[lightColour].sat;
  in.month = padMonth;
  in.lang = padLang;
  if (clockBase) in.epoch = clockBase + (now - clockAt) / 1000;
  if (statsAt && now - statsAt < 5000) {      // no fresh numbers: shown as unknown
    in.cpu = pcCpu; in.ram = pcRam; in.gpu = pcGpu; in.gpuTemp = pcGpuTemp;
  }
  bool alive = helperAlive(now);
  if (timerPhase && alive) {
    float left = timerLeft - (timerPaused ? 0 : (now - timerAt) / 1000.0f);
    in.timerLeft = left < 0 ? 0 : left;
    in.timerTotal = timerTotal;
    in.timerPhase = timerPhase;
    in.timerRound = timerRound;
    in.timerPaused = timerPaused;
  } else if (!timerPhase) {
    in.timerTotal = timerTotal;
  }
  return in;
}

void aquariumTask(void *) {
  uint32_t last = millis(), shownSince = 0;
  uint8_t feedsSeen = aquariumFeeds;
  bool wasShowing = false;
  for (;;) {
    uint32_t start = millis();
    float dt = (start - last) / 1000.0f;
    last = start;
    // Not wanted, or screen switched off: nothing to draw
    if (!aquariumWanted || brightnessIdx == BRIGHT_OFF) {
      wasShowing = false;
      feedsSeen = aquariumFeeds;   // presses meanwhile are not food
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    if (!wasShowing) shownSince = start;
    wasShowing = true;

    xSemaphoreTake(screenLock, portMAX_DELAY);
    if (aquariumWanted) {
      uint8_t feeds = aquariumFeeds;
      bool pressed = feeds != feedsSeen;
      feedsSeen = feeds;
      uint8_t bg = bgAnim;
      bool other = effectsReady && bg != BG_AQUARIUM && bg != BG_PLAIN && !introActive(millis());
      if (other) {
        // one of the other backgrounds
        effects.select(bg, bgOptions);
        if (pressed) {
          char label[sizeof(pokeLabel)];
          taskENTER_CRITICAL(&pokeMux);
          memcpy(label, pokeLabel, sizeof(label));
          taskEXIT_CRITICAL(&pokeMux);
          label[sizeof(label) - 1] = '\0';
          effects.poke(label);
        }
        bgx::Inputs in = effectInputs();
        effects.update(dt, in);
        effects.render();
        effects.drawTimerBadge(gfx->getFramebuffer(), in);
      } else {
        if (pressed) tank.feed();
        bool night = brightnessIdx == BRIGHT_DIM;   // dimmed screen = night in the aquarium
        if (night != tank.isNight()) tank.toggleNight();
        if (tank.introRunning()) tank.setIntroTime((millis() - introStart) / 1000.0f);
        tank.update(dt);
        tank.render();
        if (effectsReady && timerPhase) effects.drawTimerBadge(gfx->getFramebuffer(), effectInputs());
      }
      uint32_t now = millis();
      bool intro = introActive(now);
      if (intro) {
        drawGreeting((now - introStart) / 1000.0f);
        shownSince = now;                  // the "offline" note comes after the show
      }
      if (!drawToast(now) && !intro && now - shownSince < 5000 && !helperAlive(now))
        aquariumLabel(tr(T_OFFLINE_LONG), 150);
      gfx->flush();
    }
    xSemaphoreGive(screenLock);

    uint32_t used = millis() - start;
    vTaskDelay(pdMS_TO_TICKS(used < AQUARIUM_FRAME_MS ? AQUARIUM_FRAME_MS - used : 1));
  }
}

// Background buffers in PSRAM, then the task on core 0 (loop() runs on core 1)
void startAquarium() {
  if (!(AQUARIUM_WHEN_OFFLINE || STARTUP_ANIMATION) || !psramFound()) return;
  const size_t bytes = 320 * 170 * 2;
  uint16_t *bufs[4];
  for (int i = 0; i < 4; i++) {
    bufs[i] = (uint16_t *)ps_malloc(bytes);
    if (!bufs[i]) return;   // not enough memory: keep the normal "helper offline" screen
  }
  tank.begin(gfx->getFramebuffer(), bufs[0], bufs[1], esp_random(), bufs[2], bufs[3]);
  tank.showFish = showFish;
  // one more buffer for the other backgrounds (their still picture / the fire's heat)
  uint16_t *still = (uint16_t *)ps_malloc(bytes);
  if (still) {
    effects.begin(gfx->getFramebuffer(), still, esp_random());
    effectsReady = true;
    loadPicture();
  }
  if (STARTUP_ANIMATION) tank.startIntro();
  screenLock = xSemaphoreCreateMutex();
  if (!screenLock) return;
  aquariumReady = true;
  xTaskCreatePinnedToCore(aquariumTask, "aquarium", 6144, nullptr, 1, nullptr, 0);
}

// ============================================================================
//  RGB lights
// ============================================================================

// Adafruit hue scale: 0-65535 = once around the colour wheel.
const uint16_t HUE_GREEN  = 21845;   // 120 degrees
const uint16_t HUE_PURPLE = 53000;   // about 290 degrees: still reads as purple after gamma

// Colour with brightness 0-1, scaled by the user brightness and LED_MAX,
// gamma-corrected so dim levels look smooth.
uint32_t ledColor(uint16_t hue, uint8_t sat, float v) {
  v = constrain(v, 0.0f, 1.0f);
  uint8_t val = (uint8_t)(v * LED_MAX * lightPct / 100.0f);
  return Adafruit_NeoPixel::gamma32(Adafruit_NeoPixel::ColorHSV(hue, sat, val));
}

// An exact colour (own schemes), with the same brightness and gamma handling.
uint32_t ledRGB(const uint8_t *rgb, float v) {
  v = constrain(v, 0.0f, 1.0f) * (LED_MAX * lightPct / 100.0f) / 255.0f;
  return Adafruit_NeoPixel::gamma32(Adafruit_NeoPixel::Color(rgb[0] * v, rgb[1] * v, rgb[2] * v));
}

// Green on the left to purple on the right, like the photo. Each column has
// one colour, so all three rows of a column match.
uint16_t gradientHue(float x) {
  float t = constrain(x, 0.0f, 1.0f);
  return HUE_GREEN + (uint16_t)(t * (HUE_PURPLE - HUE_GREEN));
}

uint16_t playerHue() {
  if (strcasecmp(np.player, "Deezer") == 0) return 53500;    // Deezer purple
  if (strcasecmp(np.player, "Spotify") == 0) return 25000;   // Spotify green
  return 32768;                                              // cyan
}

// x: 0 = left .. 1 = right, y: 0 = top .. 1 = bottom, key: 0-14 (-1 = underglow)
uint32_t lightColor(float x, float y, int key, uint32_t now) {
  if (lightMode >= L_CUSTOM && lightMode < MODE_COUNT) {
    // Own scheme from the app: each key its colour; underglow takes the bottom-row key below it
    const LightScheme &sc = schemes[lightMode - L_CUSTOM];
    int k = key >= 0 ? key : (ROWS - 1) * COLS + (int)(x * (COLS - 1) + 0.5f);
    float v = 1.0f;
    if (sc.effect == FX_BREATHE) {
      v = 0.35f + 0.65f * (0.5f + 0.5f * sinf(now * 2.0f * PI / 3000.0f));
    } else if (sc.effect == FX_GLOW && key >= 0) {
      const float base = 0.3f;
      v = base;
      if (keyPressedAt[key] != 0 && now - keyPressedAt[key] < 800)
        v = base + (1.0f - base) * (1.0f - (now - keyPressedAt[key]) / 800.0f);
    }
    return ledRGB(sc.rgb[k], v);
  }
  switch (lightMode) {
    case L_RAINBOW: {
      // Colours run from left to right and drift across the pad.
      uint16_t hue = (uint16_t)(now * 12) + (uint16_t)(x * 26000);
      return ledColor(hue, 255, 1.0f);
    }
    case L_GRADIENT:
      return ledColor(gradientHue(x), 255, 1.0f);

    case L_MUSIC_COLOR: {
      // The app's colour, slowly breathing while music plays.
      float v = 0.4f;
      if (helperAlive(now) && np.playing) v = 0.45f + 0.55f * (0.5f + 0.5f * sinf(now * 2.0f * PI / 3000.0f));
      return ledColor(playerHue(), 255, v);
    }
    case L_MUSIC_BEAT: {
      // Gradient colours; each column is a small level meter, the bottom row lights first.
      if (!helperAlive(now)) return ledColor(gradientHue(x), 255, 0.3f);
      float up = 1.0f - y;                               // 0 = bottom row, 1 = top row
      float lit = key >= 0 ? constrain(audioLevel * 3.0f - up * 2.0f, 0.0f, 1.0f) : audioLevel;
      return ledColor(gradientHue(x), 255, 0.3f + 0.7f * lit);
    }
    case L_KEY_GLOW: {
      // Chosen colour: underglow steady, keys dim; a pressed key flares up and fades back.
      const NamedColour &c = COLOURS[lightColour];
      if (key < 0) return ledColor(c.hue, c.sat, 1.0f);
      const float base = 0.35f;
      if (keyPressedAt[key] != 0) {
        uint32_t age = now - keyPressedAt[key];
        if (age < 800) {
          float f = 1.0f - age / 800.0f;
          return ledColor(c.hue, c.sat, base + (1.0f - base) * f);
        }
      }
      return ledColor(c.hue, c.sat, base);
    }
    case L_SOLID: {
      // All keys and the underglow in the chosen colour.
      const NamedColour &c = COLOURS[lightColour];
      return ledColor(c.hue, c.sat, 1.0f);
    }
    default:
      return 0;   // L_OFF
  }
}

// Send a frame to the LEDs, dimmed as a whole if it would draw more than
// LED_BUDGET_MA (only white or very bright frames at high brightness).
void showLimited(const uint32_t *frame) {
  uint32_t sum = 0;
  for (int i = 0; i < LED_COUNT; i++)
    sum += ((frame[i] >> 16) & 0xFF) + ((frame[i] >> 8) & 0xFF) + (frame[i] & 0xFF);
  float mA = sum / 255.0f * LED_MA_PER_COLOUR;
  float scale = mA > LED_BUDGET_MA ? LED_BUDGET_MA / mA : 1.0f;
  for (int i = 0; i < LED_COUNT; i++) {
    uint8_t r = ((frame[i] >> 16) & 0xFF) * scale;
    uint8_t g = ((frame[i] >> 8) & 0xFF) * scale;
    uint8_t b = (frame[i] & 0xFF) * scale;
    strip.setPixelColor(i, r, g, b);
  }
  strip.show();
}

// Mix two LED colours, m = 0..1
uint32_t mixColor(uint32_t a, uint32_t b, float m) {
  m = constrain(m, 0.0f, 1.0f);
  int ar = (a >> 16) & 0xFF, ag = (a >> 8) & 0xFF, ab = a & 0xFF;
  int br = (b >> 16) & 0xFF, bg = (b >> 8) & 0xFF, bb = b & 0xFF;
  return Adafruit_NeoPixel::Color(ar + (br - ar) * m, ag + (bg - ag) * m, ab + (bb - ab) * m);
}

// LEDs during the start-up show, t = seconds since power-on:
// red, green, blue flash -> blue water rising with the screen -> light mode
uint32_t introColor(float x, float y, int key, float t, uint32_t now) {
  const float FLASH = 0.18f;
  if (t < 3 * FLASH) {
    int step = (int)(t / FLASH);
    const uint16_t hues[3] = {0, 21845, 43690};
    return ledColor(hues[step], 255, sinf((t - step * FLASH) / FLASH * PI));  // soft pulse
  }
  const float fillStart = aq::Aquarium::FILL_START, fillTime = aq::Aquarium::FILL_TIME;
  float p = constrain((t - fillStart) / fillTime, 0.0f, 1.0f);
  p = p * p * (3 - 2 * p);                                   // same easing as the screen
  float h = key >= 0 ? 1.0f / 6 + (1.0f - y) * 2.0f / 3 : 0.0f;  // row height: bottom 1/6 .. top 5/6
  float lit = constrain((p - h) / 0.18f + 0.5f, 0.0f, 1.0f);
  float shimmer = 0.85f + 0.15f * sinf(now * 0.008f + x * 5.0f + y * 3.0f);
  uint32_t water = ledColor(34000, 255, lit * shimmer);
  float m = (t - (fillStart + fillTime)) / 0.5f;             // then over into the light mode
  return m <= 0 ? water : mixColor(water, lightColor(x, y, key, now), m);
}

void updateLights(uint32_t now) {
  static uint32_t lastLedFrame = 0;
  if (now - lastLedFrame < LED_FRAME_MS) return;
  lastLedFrame = now;

  // Music level: quick rise, slow fall; no data for 300 ms counts as silence.
  float target = msSince(now, lastLevelAt) < 300 ? audioTarget : 0.0f;
  audioLevel += (target - audioLevel) * (target > audioLevel ? 0.6f : 0.12f);

  bool intro = introActive(now);
  float t = (now - introStart) / 1000.0f;
  uint32_t frame[LED_COUNT];
  for (int k = 0; k < KEY_COUNT; k++) {
    float x = (float)(k % COLS) / (COLS - 1), y = (float)(k / COLS) / (ROWS - 1);
    frame[KEY_LED[k]] = intro ? introColor(x, y, k, t, now) : lightColor(x, y, k, now);
  }
  for (int u = 0; u < UNDERGLOW_LEDS; u++) {
    float x = UNDERGLOW_LEDS > 1 ? (float)u / (UNDERGLOW_LEDS - 1) : 0.5f;
    frame[KEY_COUNT + u] = intro ? introColor(x, 1.0f, -1, t, now) : lightColor(x, 1.0f, -1, now);
  }
  if (highlightMask && !intro && helperAlive(now)) {   // key lights from the app, always visible
    float k = LED_MAX / 255.0f * max((int)lightPct, 40) / 100.0f;
    for (int i = 0; i < KEY_COUNT; i++)
      if (highlightMask & (1u << i))
        frame[KEY_LED[i]] = Adafruit_NeoPixel::Color(highlightRGB[i][0] * k, highlightRGB[i][1] * k, highlightRGB[i][2] * k);
  }
  if (padAsleep)
    for (int i = 0; i < LED_COUNT; i++) frame[i] = 0;
  showLimited(frame);

  if (lightsNeedSave && msSince(now, lightsChangedAt) > 2000) {
    prefs.putUChar("mode", lightMode);
    prefs.putUChar("level", lightPct);
    prefs.putUChar("colour", lightColour);
    lightsNeedSave = false;
    // changed on the pad itself: tell the app, so its LED page shows the same
    if (helperAlive(now)) Serial.printf("X|%u|%u|%u\n", lightMode, lightPct, lightColour);
  }
}

// ============================================================================
//  Arduino entry points
// ============================================================================

void setup() {
  // USB first, so Windows sees the keyboard as early as possible
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);        // never block when no PC program is listening
  Keyboard.begin();
  ConsumerControl.begin();
  USB.productName("ESP32 Macro Pad");
  USB.manufacturerName("DIY");
  USB.begin();

  initMatrix();
  scanMatrix();
  for (int i = 0; i < KEY_COUNT; i++) {
    keys[i].pin = 0;
    keys[i].raw = keys[i].stable = matrixRaw[i];
    keys[i].changedAt = 0;
  }
  initButton(encButton, PIN_ENC_SW);
  initButton(bootButton, PIN_BTN_BOOT);
  initButton(io14Button, PIN_BTN_IO14);

  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  encState = (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encoderISR, CHANGE);

  // Screen
  pinMode(PIN_LCD_POWER, OUTPUT);
  digitalWrite(PIN_LCD_POWER, HIGH);
  if (!gfx->begin()) {
    // Not enough memory for the frame buffer: check Tools > PSRAM = OPI PSRAM
    while (true) delay(1000);
  }
  pinMode(PIN_LCD_BL, OUTPUT);
  setBacklight(backlightFor(brightnessIdx));
  gfx->fillScreen(C_BG);
  gfx->flush();

  // Album covers: room for a whole cover in the USB receive buffer (so nothing
  // is lost while the pad is busy) and two cover pictures in PSRAM
  Serial.setRxBufferSize(32768);
  if (psramFound()) {
    coverPix[0] = (uint16_t *)ps_malloc(COVER * COVER * 2);
    coverPix[1] = (uint16_t *)ps_malloc(COVER * COVER * 2);
  }

  // Keys, lights, screen and language as last set (defaults on a new pad)
  prefs.begin("macropad", false);
  loadSettings();
  setBacklight(backlightFor(brightnessIdx));
  strip.begin();
  strip.clear();
  strip.show();
  startAquarium();
  // start-up show: runs alongside everything else from here on
  introStart = millis();
  introLength = STARTUP_ANIMATION ? 4300 : 0;
}

void loop() {
  readSerial();                 // first, so every time stamp it sets is older than 'now'
  uint32_t now = millis();
  if (introLength && now - introStart >= introLength) introLength = 0;  // start-up show over, for good
  handleKeys(now);
  handleKnob(now);
  updateSleep(now);
  updateScreen(now);
  updateLights(now);
  delay(1);
}
