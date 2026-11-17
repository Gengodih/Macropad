// Backgrounds.h - the screen backgrounds besides the aquarium:
// Synthwave, Lava lamp, Space, Campfire, Matrix, Rainy night and Seasons.
//
// Like Aquarium.h this is plain C++ (no Arduino calls), so the same code runs
// on the T-Display-S3 and on a PC for previews. It draws into the same
// 320 x 170 RGB565 frame buffer and reuses the aquarium's drawing helpers.
//
//   fx.begin(frame, scratch, seed)   scratch: a W*H*2 byte buffer (PSRAM) for
//                                    still layers and the fire's heat map
//   fx.select(kind, options)         which background, plus its option bits
//   fx.poke(label)                   a key was pressed (label = its name)
//   fx.update(dt, inputs)            move everything on by dt seconds
//   fx.render()                      draw the frame

#pragma once
#include "Aquarium.h"
#include <cstdio>
#include <cstring>

#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC push_options
#pragma GCC optimize("O2")
#endif

namespace bgx {

using aq::W;
using aq::H;
using aq::PI_F;
using aq::Col;
using aq::C8;
using aq::clampf;
using aq::clampi;
using aq::lerpf;
using aq::mix;
using aq::pack;
using aq::pack8;
using aq::toC8;

// Background numbers, the same as BgAnim in the sketch and in the app
enum Kind : uint8_t {
  AQUARIUM = 0, PLAIN = 1, SYNTHWAVE = 2, LAVA = 3, SPACE = 4, FIRE = 5, MATRIX = 6, RAIN = 7,
  SEASONS = 8, CLOCK = 9, STATS = 10, TIMER = 11, PICTURE = 12, KIND_COUNT = 13
};

// Option bits (from the app). Seasons keeps its season in bits 1-3:
// 0 = by the date, 1 = winter, 2 = spring, 3 = summer, 4 = autumn.
constexpr uint8_t OPT_A = 0x01;   // Synthwave: pulse with the music, Lava: light colour,
                                  // Space: rocket on key press, Fire: dance to the music,
                                  // Matrix: key names fall along, Rain: thunderstorm
constexpr uint8_t OPT_B = 0x02;   // Fire: a sleepy fox by the fire, Clock: 12-hour time
// Clock OPT_A: seconds bar, Stats OPT_A: history graph

struct Inputs {
  float level = 0;          // music loudness 0-1 (smoothed)
  uint16_t accentHue = 0;   // the light colour (Adafruit hue scale) for "Lava: light colour"
  uint8_t accentSat = 255;
  uint8_t month = 0;        // 1-12 from the PC, 0 = unknown
  uint32_t epoch = 0;       // local time in seconds since 1970 (from the PC), 0 = unknown
  uint8_t lang = 0;         // 0 English, 1 German
  float cpu = -1, ram = -1, gpu = -1, gpuTemp = -1;   // PC stats in %, degrees C; -1 = unknown
  float timerLeft = 0, timerTotal = 0;                // focus timer, seconds
  uint8_t timerPhase = 0;   // 0 off, 1 focus, 2 break, 3 long break
  uint8_t timerRound = 0;   // 1-4
  bool timerPaused = false;
};

// Date from days since 1970 (H. Hinnant's civil_from_days)
inline void civilFromDays(int32_t z, int &y, unsigned &m, unsigned &d) {
  z += 719468;
  const int32_t era = (z >= 0 ? z : z - 146096) / 146097;
  const unsigned doe = (unsigned)(z - era * 146097);
  const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  y = (int)yoe + era * 400;
  const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const unsigned mp = (5 * doy + 2) / 153;
  d = doy - (153 * mp + 2) / 5 + 1;
  m = mp < 10 ? mp + 3 : mp - 9;
  y += (m <= 2);
}

// Classic 5x7 font (Adafruit GFX), ASCII 32-126: 5 columns per character, bit 0 = top row
static const uint8_t FONT5x7[95 * 5] = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x5F, 0x00, 0x00, 0x00, 0x07, 0x00, 0x07, 0x00, 0x14, 0x7F, 0x14, 0x7F, 0x14,
  0x24, 0x2A, 0x7F, 0x2A, 0x12, 0x23, 0x13, 0x08, 0x64, 0x62, 0x36, 0x49, 0x56, 0x20, 0x50, 0x00, 0x08, 0x07, 0x03, 0x00,
  0x00, 0x1C, 0x22, 0x41, 0x00, 0x00, 0x41, 0x22, 0x1C, 0x00, 0x2A, 0x1C, 0x7F, 0x1C, 0x2A, 0x08, 0x08, 0x3E, 0x08, 0x08,
  0x00, 0x80, 0x70, 0x30, 0x00, 0x08, 0x08, 0x08, 0x08, 0x08, 0x00, 0x00, 0x60, 0x60, 0x00, 0x20, 0x10, 0x08, 0x04, 0x02,
  0x3E, 0x51, 0x49, 0x45, 0x3E, 0x00, 0x42, 0x7F, 0x40, 0x00, 0x72, 0x49, 0x49, 0x49, 0x46, 0x21, 0x41, 0x49, 0x4D, 0x33,
  0x18, 0x14, 0x12, 0x7F, 0x10, 0x27, 0x45, 0x45, 0x45, 0x39, 0x3C, 0x4A, 0x49, 0x49, 0x31, 0x41, 0x21, 0x11, 0x09, 0x07,
  0x36, 0x49, 0x49, 0x49, 0x36, 0x46, 0x49, 0x49, 0x29, 0x1E, 0x00, 0x00, 0x14, 0x00, 0x00, 0x00, 0x40, 0x34, 0x00, 0x00,
  0x00, 0x08, 0x14, 0x22, 0x41, 0x14, 0x14, 0x14, 0x14, 0x14, 0x00, 0x41, 0x22, 0x14, 0x08, 0x02, 0x01, 0x59, 0x09, 0x06,
  0x3E, 0x41, 0x5D, 0x59, 0x4E, 0x7C, 0x12, 0x11, 0x12, 0x7C, 0x7F, 0x49, 0x49, 0x49, 0x36, 0x3E, 0x41, 0x41, 0x41, 0x22,
  0x7F, 0x41, 0x41, 0x41, 0x3E, 0x7F, 0x49, 0x49, 0x49, 0x41, 0x7F, 0x09, 0x09, 0x09, 0x01, 0x3E, 0x41, 0x41, 0x51, 0x73,
  0x7F, 0x08, 0x08, 0x08, 0x7F, 0x00, 0x41, 0x7F, 0x41, 0x00, 0x20, 0x40, 0x41, 0x3F, 0x01, 0x7F, 0x08, 0x14, 0x22, 0x41,
  0x7F, 0x40, 0x40, 0x40, 0x40, 0x7F, 0x02, 0x1C, 0x02, 0x7F, 0x7F, 0x04, 0x08, 0x10, 0x7F, 0x3E, 0x41, 0x41, 0x41, 0x3E,
  0x7F, 0x09, 0x09, 0x09, 0x06, 0x3E, 0x41, 0x51, 0x21, 0x5E, 0x7F, 0x09, 0x19, 0x29, 0x46, 0x26, 0x49, 0x49, 0x49, 0x32,
  0x03, 0x01, 0x7F, 0x01, 0x03, 0x3F, 0x40, 0x40, 0x40, 0x3F, 0x1F, 0x20, 0x40, 0x20, 0x1F, 0x3F, 0x40, 0x38, 0x40, 0x3F,
  0x63, 0x14, 0x08, 0x14, 0x63, 0x03, 0x04, 0x78, 0x04, 0x03, 0x61, 0x59, 0x49, 0x4D, 0x43, 0x00, 0x7F, 0x41, 0x41, 0x41,
  0x02, 0x04, 0x08, 0x10, 0x20, 0x00, 0x41, 0x41, 0x41, 0x7F, 0x04, 0x02, 0x01, 0x02, 0x04, 0x40, 0x40, 0x40, 0x40, 0x40,
  0x00, 0x03, 0x07, 0x08, 0x00, 0x20, 0x54, 0x54, 0x78, 0x40, 0x7F, 0x28, 0x44, 0x44, 0x38, 0x38, 0x44, 0x44, 0x44, 0x28,
  0x38, 0x44, 0x44, 0x28, 0x7F, 0x38, 0x54, 0x54, 0x54, 0x18, 0x00, 0x08, 0x7E, 0x09, 0x02, 0x18, 0xA4, 0xA4, 0x9C, 0x78,
  0x7F, 0x08, 0x04, 0x04, 0x78, 0x00, 0x44, 0x7D, 0x40, 0x00, 0x20, 0x40, 0x40, 0x3D, 0x00, 0x7F, 0x10, 0x28, 0x44, 0x00,
  0x00, 0x41, 0x7F, 0x40, 0x00, 0x7C, 0x04, 0x78, 0x04, 0x78, 0x7C, 0x08, 0x04, 0x04, 0x78, 0x38, 0x44, 0x44, 0x44, 0x38,
  0xFC, 0x18, 0x24, 0x24, 0x18, 0x18, 0x24, 0x24, 0x18, 0xFC, 0x7C, 0x08, 0x04, 0x04, 0x08, 0x48, 0x54, 0x54, 0x54, 0x24,
  0x04, 0x04, 0x3F, 0x44, 0x24, 0x3C, 0x40, 0x40, 0x20, 0x7C, 0x1C, 0x20, 0x40, 0x20, 0x1C, 0x3C, 0x40, 0x30, 0x40, 0x3C,
  0x44, 0x28, 0x10, 0x28, 0x44, 0x4C, 0x90, 0x90, 0x90, 0x7C, 0x44, 0x64, 0x54, 0x4C, 0x44, 0x00, 0x08, 0x36, 0x41, 0x00,
  0x00, 0x00, 0x77, 0x00, 0x00, 0x00, 0x41, 0x36, 0x08, 0x00, 0x02, 0x01, 0x02, 0x04, 0x02,
};

// HSV (Adafruit hue scale 0-65535, sat/val 0-255) -> colour
inline Col hsv(uint16_t hue, uint8_t sat, uint8_t val) {
  float h = hue / 65536.0f * 6.0f;
  int i = (int)h;
  float f = h - i;
  float v = val, s = sat / 255.0f;
  float p = v * (1 - s), q = v * (1 - s * f), t = v * (1 - s * (1 - f));
  switch (i % 6) {
    case 0: return {v, t, p};
    case 1: return {q, v, p};
    case 2: return {p, v, t};
    case 3: return {p, q, v};
    case 4: return {t, p, v};
    default: return {v, p, q};
  }
}

class Effects {
 public:
  void begin(uint16_t *frame, uint16_t *scratch, uint32_t seed) {
    fb_ = frame;
    cv_.fb = frame;
    scratch_ = scratch;
    rng_ = aq::Rng(seed ? seed : 7);
    // random 5x7 glyphs for the Matrix rain (look like a strange alphabet)
    static const char SRC[] = "0123456789ABCDEFGHJKLMNPRSTUVXZ<>*+=:$#%&@";
    for (int g = 0; g < GLYPHS; g++) {
      const uint8_t *f = fontChar(SRC[rng_.next() % (sizeof(SRC) - 1)]);
      bool mirror = rng_.next() & 1;
      for (int c = 0; c < 5; c++) glyphs_[g][c] = mirror ? f[4 - c] : f[c];
    }
    kind_ = 255;
  }

  // Switches background (resets it) or just takes new options.
  void select(uint8_t kind, uint8_t opts) {
    if (kind >= KIND_COUNT) kind = SYNTHWAVE;
    uint8_t season = resolveSeason(opts);
    if (kind != kind_ || (kind == SEASONS && season != season_)) {
      kind_ = kind;
      opts_ = opts;
      season_ = season;
      t_ = 0;
      setup();
    }
    opts_ = opts;
  }
  uint8_t kind() const { return kind_; }

  void poke(const char *label) {
    switch (kind_) {
      case SPACE:
        if (opts_ & OPT_A) launchRocket();
        break;
      case FIRE:
        sparks(14);
        if (opts_ & OPT_B) foxWake_ = 5.0f;          // the fox looks up for a while
        break;
      case LAVA: lavaKick(); break;
      case MATRIX:
        if ((opts_ & OPT_A) && label && label[0]) matrixWord(label);
        break;
      case SEASONS: gust_ += 60; break;
      case SYNTHWAVE: kick_ = 1.0f; break;
      case CLOCK: case TIMER: pulse_ = 1.0f; break;
      case RAIN: drops(3); break;
      default: break;
    }
  }

  void update(float dt, const Inputs &in) {
    if (dt > 0.05f) dt = 0.05f;
    in_ = in;
    t_ += dt;
    if (t_ > 3600) t_ -= 3600;
    if (kind_ == SEASONS && resolveSeason(opts_) != season_) select(SEASONS, opts_);
    switch (kind_) {
      case SYNTHWAVE: updateSynth(dt); break;
      case LAVA: updateLava(dt); break;
      case SPACE: updateSpace(dt); break;
      case FIRE: updateFire(dt); break;
      case MATRIX: updateMatrix(dt); break;
      case RAIN: updateRain(dt); break;
      case SEASONS: updateSeasons(dt); break;
      case CLOCK: case STATS: case TIMER: case PICTURE: updateWidget(dt); break;
      default: break;
    }
  }

  // Own picture (from the app, in flash): w x h pixels per frame, 320x170 or 160x85
  void setPicture(const uint16_t *pixels, uint16_t w, uint16_t h, uint16_t frames, uint16_t delayMs) {
    pic_ = pixels;
    picW_ = w;
    picH_ = h;
    picFrames_ = frames ? frames : 1;
    picDelay_ = delayMs < 20 ? 100 : delayMs;
    picFrame_ = 0;
    picT_ = 0;
  }

  // While a focus timer runs: a small timer in the corner of any other background
  void drawTimerBadge(uint16_t *frame, const Inputs &in) {
    if (!in.timerPhase || kind_ == TIMER) return;
    aq::Canvas c;
    c.fb = frame;
    int left = (int)(in.timerLeft + 0.99f);
    if (left < 0) left = 0;
    char buf[8];
    snprintf(buf, sizeof(buf), "%02d:%02d", left / 60 % 100, left % 60);
    const float x = 226, y = 6, w = 88, h = 24;
    c.fillRect(x + 4, y, w - 8, h, {10, 10, 20}, 0.7f);
    c.fillCircle(x + 4, y + h / 2, h / 2, {10, 10, 20}, 0.7f);
    c.fillCircle(x + w - 4, y + h / 2, h / 2, {10, 10, 20}, 0.7f);
    Col dot = in.timerPaused ? Col{150, 150, 170} : (in.timerPhase == 1 ? Col{255, 90, 70} : Col{80, 220, 140});
    c.fillCircle(x + 10, y + h / 2, 5, dot, 1.0f);
    aq::Canvas keep = cv_;
    cv_ = c;
    text(buf, x + 22, y + 5, 2, {245, 245, 255}, 1.0f);
    cv_ = keep;
  }

  void render() {
    switch (kind_) {
      case SYNTHWAVE: renderSynth(); break;
      case LAVA: renderLava(); break;
      case SPACE: renderSpace(); break;
      case FIRE: renderFire(); break;
      case MATRIX: renderMatrix(); break;
      case RAIN: renderRain(); break;
      case SEASONS: renderSeasons(); break;
      case CLOCK: renderClock(); break;
      case STATS: renderStats(); break;
      case TIMER: renderTimer(); break;
      case PICTURE: renderPicture(); break;
      default:
        for (int i = 0; i < W * H; i++) fb_[i] = 0;
        break;
    }
  }

 private:
  static constexpr int GLYPHS = 40;
  uint16_t *fb_ = nullptr, *scratch_ = nullptr;
  aq::Canvas cv_;
  aq::Rng rng_{7};
  Inputs in_;
  uint8_t kind_ = 255, opts_ = 0, season_ = 0;
  float t_ = 0;
  uint8_t glyphs_[GLYPHS][5];

  float rnd(float a, float b) { return rng_.range(a, b); }
  // the still layer (sky, city ...) back into the frame
  void copyStill() {
    if (scratch_) memcpy(fb_, scratch_, W * H * 2);
    else for (int i = 0; i < W * H; i++) fb_[i] = 0;
  }
  // draw into the still layer instead of the frame
  void toStill(bool on) { cv_.fb = (on && scratch_) ? scratch_ : fb_; }
  void verticalGradient(int y0, int y1, Col top, Col bottom) {
    uint16_t *dst = cv_.fb;
    for (int y = y0; y < y1 && y < H; y++) {
      float k = y1 - 1 > y0 ? (float)(y - y0) / (y1 - 1 - y0) : 0;
      uint16_t c = pack(mix(top, bottom, k));
      for (int x = 0; x < W; x++) dst[y * W + x] = c;
    }
  }
  void line(float x0, float y0, float x1, float y1, Col c, float a) {
    float dx = x1 - x0, dy = y1 - y0;
    int n = (int)(fmaxf(fabsf(dx), fabsf(dy)) + 1);
    for (int i = 0; i <= n; i++) {
      float k = (float)i / n;
      cv_.blend((int)(x0 + dx * k), (int)(y0 + dy * k), c, a);
    }
  }
  void glyph(const uint8_t *cols, int x, int y, uint16_t colour) {
    for (int c = 0; c < 5; c++) {
      uint8_t bits = cols[c];
      for (int r = 0; r < 7; r++)
        if (bits & (1 << r)) {
          int px = x + c, py = y + r;
          if ((unsigned)px < (unsigned)W && (unsigned)py < (unsigned)H) fb_[py * W + px] = colour;
        }
    }
  }
  const uint8_t *fontChar(char ch) {
    if (ch >= 'a' && ch <= 'z') ch -= 32;
    if (ch < 32 || ch > 126) ch = '?';
    return &FONT5x7[(ch - 32) * 5];
  }

  void setup() {
    toStill(true);
    switch (kind_) {
      case SYNTHWAVE: setupSynth(); break;
      case LAVA: setupLava(); break;
      case SPACE: setupSpace(); break;
      case FIRE: setupFire(); break;
      case MATRIX: setupMatrix(); break;
      case RAIN: setupRain(); break;
      case SEASONS: setupSeasons(); break;
      default: break;
    }
    toStill(false);
  }

  uint8_t resolveSeason(uint8_t opts) const {
    uint8_t s = (opts >> 1) & 7;
    if (s >= 1 && s <= 4) return s - 1;            // 0 winter, 1 spring, 2 summer, 3 autumn
    uint8_t m = in_.month;
    if (m >= 3 && m <= 5) return 1;
    if (m >= 6 && m <= 8) return 2;
    if (m >= 9 && m <= 11) return 3;
    return 0;                                        // Dec-Feb, or date unknown
  }


  // =========================================================================
  //  Widgets: clock, PC stats, focus timer, own picture
  // =========================================================================
  const uint16_t *pic_ = nullptr;
  uint16_t picW_ = 0, picH_ = 0, picFrames_ = 1, picDelay_ = 100, picFrame_ = 0;
  float picT_ = 0, histT_ = 0;
  float cpuHist_[64], ramHist_[64];
  uint8_t histN_ = 0;

  // text in the 5x7 font, upper case, scaled
  void text(const char *s, float x, float y, int scale, Col c, float a) {
    for (; *s; s++, x += 6 * scale) {
      char ch = *s;
      if (ch >= 'a' && ch <= 'z') ch -= 32;
      if (ch < 32 || ch > 126) ch = '?';
      glyphBlend(ch, x, y, c, a, scale);
    }
  }
  static float textW(const char *s, int scale) { return strlen(s) * 6.0f * scale - scale; }
  void textC(const char *s, float cx, float y, int scale, Col c, float a) { text(s, cx - textW(s, scale) / 2, y, scale, c, a); }

  // one seven-segment digit (0-9, or -1 = dash)
  void seg(float x, float y, float len, float t, bool horizontal, Col c, float a) {
    const float g = t * 0.18f, e = t / 2;
    if (horizontal) {
      cv_.fillRect(x + e + g, y, len - t - 2 * g, t, c, a);
      cv_.fillTri(x + g, y + e, x + e + g, y, x + e + g, y + t, c, a);
      cv_.fillTri(x + len - g, y + e, x + len - e - g, y, x + len - e - g, y + t, c, a);
    } else {
      cv_.fillRect(x, y + e + g, t, len - t - 2 * g, c, a);
      cv_.fillTri(x + e, y + g, x, y + e + g, x + t, y + e + g, c, a);
      cv_.fillTri(x + e, y + len - g, x, y + len - e - g, x + t, y + len - e - g, c, a);
    }
  }
  void digit7(int d, float x, float y, float w, float h, float t, Col on, float offA) {
    static const uint8_t SEGS[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};
    uint8_t m = d < 0 ? 0x40 : SEGS[d % 10];
    const float hh = (h - t) / 2;
    struct S { float x, y, len; bool hor; } S7[7] = {
        {x, y, w, true}, {x + w - t, y, hh + t, false}, {x + w - t, y + hh, hh + t, false},
        {x, y + 2 * hh, w, true}, {x, y + hh, hh + t, false}, {x, y, hh + t, false}, {x, y + hh, w, true}};
    for (int i = 0; i < 7; i++) {
      bool lit = m & (1 << i);
      if (!lit && offA <= 0) continue;
      seg(S7[i].x, S7[i].y, S7[i].len, t, S7[i].hor, on, lit ? 1.0f : offA);
    }
  }
  // an arc of round dots (angles in degrees, 0 = right, clockwise)
  void arc(float cx, float cy, float r, float th, float a0, float a1, Col c, float a) {
    float len = fabsf(a1 - a0) * PI_F / 180 * r;
    int n = (int)(len / (th * 0.35f)) + 2;
    for (int i = 0; i <= n; i++) {
      float ang = (a0 + (a1 - a0) * i / n) * PI_F / 180;
      cv_.fillCircle(cx + cosf(ang) * r, cy + sinf(ang) * r, th / 2, c, a);
    }
  }
  Col accent() const { return hsv(in_.accentHue, in_.accentSat > 200 ? 200 : in_.accentSat, 255); }

  void updateWidget(float dt) {
    pulse_ = fmaxf(0, pulse_ - dt * 2);
    if (kind_ == STATS && (histT_ -= dt) <= 0) {        // one history point a second
      histT_ = 1;
      if (histN_ == 64) {
        memmove(cpuHist_, cpuHist_ + 1, 63 * sizeof(float));
        memmove(ramHist_, ramHist_ + 1, 63 * sizeof(float));
        histN_ = 63;
      }
      cpuHist_[histN_] = in_.cpu;
      ramHist_[histN_] = in_.ram;
      histN_++;
    }
    if (kind_ == PICTURE && pic_ && picFrames_ > 1) {
      picT_ += dt * 1000;
      while (picT_ >= picDelay_) {
        picT_ -= picDelay_;
        picFrame_ = (picFrame_ + 1) % picFrames_;
      }
    }
  }
  void widgetBackground(Col top, Col bottom) {
    verticalGradient(0, H, top, bottom);
    // two slow, soft glows
    float x1 = 160 + 120 * sinf(t_ * 0.07f), y1 = 85 + 50 * sinf(t_ * 0.05f + 1);
    float x2 = 160 + 120 * sinf(t_ * 0.05f + 2.5f), y2 = 85 + 50 * cosf(t_ * 0.06f);
    Col a = accent();
    cv_.fillCircle(x1, y1, 90, a, 0.05f);
    cv_.fillCircle(x2, y2, 70, mix(a, {255, 255, 255}, 0.3f), 0.04f);
  }

  void renderClock() {
    widgetBackground({10, 8, 26}, {28, 10, 46});
    const bool de = in_.lang == 1;
    Col on = mix(accent(), {255, 255, 255}, 0.25f + 0.3f * pulse_);
    if (!in_.epoch) {
      for (int i = 0; i < 4; i++) digit7(-1, 31 + i * 64 + (i >= 2 ? 16 : 0), 24, 50, 86, 10, on, 0.06f);
      textC(de ? "VERBINDE DIE APP" : "CONNECT THE APP", 160, 138, 2, {200, 200, 220}, 0.8f);
      return;
    }
    uint32_t e = in_.epoch;
    int32_t days = (int32_t)(e / 86400);
    uint32_t sod = e % 86400;
    int hour = sod / 3600, minute = sod / 60 % 60, second = sod % 60;
    bool h12 = opts_ & OPT_B;
    int shown = h12 ? (hour % 12 == 0 ? 12 : hour % 12) : hour;
    float x = 31, y = 24;
    int dd[4] = {shown / 10, shown % 10, minute / 10, minute % 10};
    for (int i = 0; i < 4; i++) {
      if (i == 0 && h12 && dd[0] == 0) {
        x += 64;
        continue;                                  // no leading zero for 12-hour time
      }
      digit7(dd[i], x, y, 50, 86, 10, on, 0.06f);
      x += 64;
      if (i == 1) {                                // blinking colon
        float a = second % 2 ? 0.25f : 1.0f;
        cv_.fillRect(x - 6, y + 22, 9, 9, on, a);
        cv_.fillRect(x - 6, y + 56, 9, 9, on, a);
        x += 16;
      }
    }
    if (h12) text(hour < 12 ? "AM" : "PM", 290, 26, 1, on, 0.9f);
    if (opts_ & OPT_A) {                           // seconds bar
      cv_.fillRect(60, 122, 200, 3, {255, 255, 255}, 0.12f);
      cv_.fillRect(60, 122, 200 * (second + 1) / 60.0f, 3, on, 0.9f);
    }
    int y_;
    unsigned m, d;
    civilFromDays(days, y_, m, d);
    int wd = (int)((days + 3) % 7);                // 0 = Monday
    static const char *WD_EN[7] = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"};
    static const char *WD_DE[7] = {"MO", "DI", "MI", "DO", "FR", "SA", "SO"};
    static const char *MO_EN[12] = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"};
    static const char *MO_DE[12] = {"JAN", "FEB", "MRZ", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"};
    char buf[24];
    if (de) snprintf(buf, sizeof(buf), "%s %u. %s", WD_DE[wd], d, MO_DE[(m - 1) % 12]);
    else snprintf(buf, sizeof(buf), "%s %u %s", WD_EN[wd], d, MO_EN[(m - 1) % 12]);
    textC(buf, 160, 136, 2, {220, 220, 240}, 0.95f);
  }

  void gauge(float cx, float cy, float value, float maxv, const char *labelText, const char *unit) {
    const float r = 28, th = 7;
    arc(cx, cy, r, th, 135, 405, {255, 255, 255}, 0.10f);
    char buf[8];
    if (value < 0) {
      textC("--", cx, cy - 7, 2, {160, 160, 180}, 0.8f);
    } else {
      float f = clampf(value / maxv, 0, 1);
      Col c = f < 0.6f ? mix({80, 220, 140}, {250, 210, 80}, f / 0.6f) : mix({250, 210, 80}, {255, 80, 80}, (f - 0.6f) / 0.4f);
      if (f > 0.005f) arc(cx, cy, r, th, 135, 135 + 270 * f, c, 1.0f);
      snprintf(buf, sizeof(buf), "%d%s", (int)(value + 0.5f), unit);
      textC(buf, cx, cy - 7, 2, {245, 245, 255}, 1.0f);
    }
    textC(labelText, cx, cy + 26, 1, {200, 200, 220}, 0.9f);
  }
  void renderStats() {
    widgetBackground({8, 14, 26}, {14, 24, 40});
    const float y = 44;
    gauge(43, y, in_.cpu, 100, "CPU", "%");
    gauge(121, y, in_.ram, 100, "RAM", "%");
    gauge(199, y, in_.gpu, 100, "GPU", "%");
    gauge(277, y, in_.gpuTemp, 100, in_.lang ? "GPU TEMP" : "GPU TEMP", "C");
    if (!(opts_ & OPT_A)) {
      if (in_.cpu < 0) textC(in_.lang ? "VERBINDE DIE APP" : "CONNECT THE APP", 160, 130, 2, {200, 200, 220}, 0.8f);
      return;
    }
    // history: the last minute of CPU (accent) and RAM (white)
    const float gx = 16, gy = 98, gw = 288, gh = 60;
    cv_.fillRect(gx, gy, gw, gh, {0, 0, 0}, 0.25f);
    for (int k = 1; k < 4; k++) cv_.fillRect(gx, gy + gh * k / 4, gw, 1, {255, 255, 255}, 0.06f);
    Col a = accent();
    for (int series = 0; series < 2; series++) {
      const float *h = series ? ramHist_ : cpuHist_;
      Col c = series ? Col{230, 230, 245} : a;
      for (int i = 1; i < histN_; i++) {
        if (h[i - 1] < 0 || h[i] < 0) continue;
        float x0 = gx + gw - (histN_ - i) * gw / 63.0f, x1 = x0 + gw / 63.0f;
        float y0 = gy + gh - h[i - 1] / 100 * gh, y1 = gy + gh - h[i] / 100 * gh;
        line(x0, y0, x1, y1, c, series ? 0.6f : 1.0f);
        if (!series)
          for (float yy = fmaxf(y0, y1); yy < gy + gh; yy += 1) cv_.blend((int)x1, (int)yy, c, 0.12f);
      }
    }
    text("CPU", gx + 4, gy + 3, 1, a, 0.9f);
    text("RAM", gx + 28, gy + 3, 1, {230, 230, 245}, 0.7f);
  }

  void renderTimer() {
    const bool de = in_.lang == 1;
    const uint8_t ph = in_.timerPhase;
    Col top, bottom, ring;
    if (ph == 1) { top = {50, 12, 18}; bottom = {24, 6, 12}; ring = {255, 96, 72}; }
    else if (ph >= 2) { top = {8, 40, 32}; bottom = {4, 18, 16}; ring = {80, 220, 150}; }
    else { top = {16, 16, 30}; bottom = {10, 10, 20}; ring = accent(); }
    if (in_.timerPaused) ring = mix(ring, {150, 150, 170}, 0.6f);
    widgetBackground(top, bottom);
    const float cx = 78, cy = 85, r = 58, th = 10;
    arc(cx, cy, r, th, 0, 360, {255, 255, 255}, 0.08f);
    float frac = (ph && in_.timerTotal > 0) ? clampf(in_.timerLeft / in_.timerTotal, 0, 1) : 1.0f;
    if (frac > 0.002f) arc(cx, cy, r, th, -90, -90 + 360 * frac, ring, 1.0f);
    cv_.fillCircle(cx, cy, 34 + 3 * pulse_, ring, 0.10f + 0.10f * (in_.timerPaused ? 0 : 0.5f + 0.5f * sinf(t_ * 2)));
    int left = ph ? (int)(in_.timerLeft + 0.99f) : (int)(in_.timerTotal + 0.5f);
    if (left < 0) left = 0;
    int mm = left / 60 % 100, ss = left % 60;
    Col on = mix(ring, {255, 255, 255}, 0.35f);
    float x = 168, y = 50;
    int dd[4] = {mm / 10, mm % 10, ss / 10, ss % 10};
    for (int i = 0; i < 4; i++) {
      digit7(dd[i], x, y, 26, 50, 7, on, 0.06f);
      x += 33;
      if (i == 1) {
        cv_.fillRect(x - 4, y + 13, 6, 6, on, 1.0f);
        cv_.fillRect(x - 4, y + 31, 6, 6, on, 1.0f);
        x += 9;
      }
    }
    const char *lab;
    if (in_.timerPaused) lab = de ? "ANGEHALTEN" : "PAUSED";
    else if (ph == 1) lab = de ? "FOKUS" : "FOCUS";
    else if (ph == 2) lab = de ? "PAUSE" : "BREAK";
    else if (ph == 3) lab = de ? "LANGE PAUSE" : "LONG BREAK";
    else lab = de ? "BEREIT" : "READY";
    textC(lab, 240, 24, 2, {240, 240, 250}, 0.95f);
    if (ph) {
      for (int i = 0; i < 4; i++) {
        float dx = 210 + i * 20;
        bool done = i < in_.timerRound - (ph == 1 ? 1 : 0);
        cv_.fillCircle(dx, 128, 5, done || (i == in_.timerRound - 1 && ph == 1) ? ring : Col{255, 255, 255},
                       done ? 1.0f : (i == in_.timerRound - 1 && ph == 1 ? 0.5f : 0.15f));
      }
    } else {
      textC(de ? "TIMER-TASTE DRUECKEN" : "PRESS YOUR TIMER KEY", 240, 124, 1, {200, 200, 220}, 0.8f);
    }
  }

  void renderPicture() {
    if (!pic_) {
      verticalGradient(0, H, {16, 16, 28}, {8, 8, 16});
      textC(in_.lang ? "NOCH KEIN BILD" : "NO PICTURE YET", 160, 70, 2, {220, 220, 235}, 0.9f);
      textC(in_.lang ? "IN DER APP AUSWAEHLEN" : "CHOOSE ONE IN THE APP", 160, 96, 1, {170, 170, 190}, 0.8f);
      return;
    }
    const uint16_t *f = pic_ + (size_t)picFrame_ * picW_ * picH_;
    if (picW_ == W && picH_ == H) {
      memcpy(fb_, f, W * H * 2);
    } else {                                       // half size: every pixel twice
      for (int y = 0; y < H; y++) {
        const uint16_t *src = f + (size_t)(y * picH_ / H) * picW_;
        uint16_t *dst = fb_ + y * W;
        for (int x = 0; x < W; x++) dst[x] = src[x * picW_ / W];
      }
    }
  }

  // =========================================================================
  //  Synthwave: retro sun, mountains and a neon grid running towards you
  // =========================================================================
  static constexpr int HORIZON = 104;
  float gridPhase_ = 0, sunPhase_ = 0, kick_ = 0, pulse_ = 0;
  int16_t mtnFar_[W], mtnNear_[W];

  void setupSynth() {
    verticalGradient(0, 60, {14, 4, 40}, {60, 12, 98});
    verticalGradient(60, HORIZON, {60, 12, 98}, {250, 70, 140});
    verticalGradient(HORIZON, H, {40, 0, 60}, {8, 0, 22});
    for (int i = 0; i < 70; i++) {                   // stars in the upper sky
      int x = (int)rnd(0, W), y = (int)rnd(0, 55);
      float b = rnd(110, 255);
      cv_.blend(x, y, {b, b, b * 0.9f + 20}, 1.0f);
    }
    float a = rnd(0, 6), b = rnd(0, 6);
    for (int x = 0; x < W; x++) {
      float far = 86 - 10 * sinf(x * 0.021f + a) - 6 * sinf(x * 0.057f + b) - 3 * sinf(x * 0.13f);
      float near = 97 - 7 * fabsf(sinf(x * 0.017f + b)) - 4 * sinf(x * 0.071f + a);
      mtnFar_[x] = (int16_t)far;
      mtnNear_[x] = (int16_t)near;
    }
  }
  void updateSynth(float dt) {
    float beat = (opts_ & OPT_A) ? in_.level : 0.0f;
    pulse_ += (beat - pulse_) * (beat > pulse_ ? 0.5f : 0.08f);
    kick_ = fmaxf(0, kick_ - dt * 2.5f);
    gridPhase_ += dt * (0.9f + 1.4f * pulse_ + 1.5f * kick_);
    if (gridPhase_ >= 1) gridPhase_ -= 1;
    sunPhase_ += dt * 6;
    if (sunPhase_ >= 9) sunPhase_ -= 9;
  }
  void renderSynth() {
    copyStill();
    // sun with stripes that drift down
    const float cx = 160, cy = 74, r = 44;
    for (int y = (int)(cy - r); y < HORIZON; y++) {
      float dy = y + 0.5f - cy;
      if (fabsf(dy) >= r) continue;
      float k = (y - (cy - r)) / (2 * r);
      float startStripes = cy - r * 0.15f;
      if (y > startStripes) {
        float depth = (y - startStripes) / (cy + r - startStripes);
        float gap = 1.0f + 4.5f * depth;
        if (fmodf(y - sunPhase_ + 90, 9.0f) < gap) continue;
      }
      float half = sqrtf(r * r - dy * dy);
      cv_.span(y, cx - half, cx + half, toC8(mix({255, 230, 90}, {255, 50, 150}, k)));
    }
    // mountains: far ridge, near ridge with a neon edge
    for (int x = 0; x < W; x++) {
      uint16_t far = pack8(70, 18, 110), near = pack8(26, 4, 52);
      for (int y = mtnFar_[x]; y < HORIZON; y++) fb_[y * W + x] = far;
      for (int y = mtnNear_[x]; y < HORIZON; y++) fb_[y * W + x] = near;
      cv_.blend(x, mtnNear_[x], {255, 60, 220}, 0.8f);
    }
    // the floor grid
    float glow = 0.45f + 0.55f * fmaxf(pulse_, kick_);
    Col gridCol = mix({255, 40, 200}, {120, 240, 255}, pulse_ * 0.5f);
    for (int n = 0; n < 14; n++) {                   // horizontal lines, closer = lower
      float z = n + 1 - gridPhase_;
      float y = HORIZON + 66.0f / z;
      if (y >= H) continue;
      float fade = clampf((y - HORIZON) / 30.0f, 0.15f, 1.0f);
      int yi = (int)y;
      for (int x = 0; x < W; x++) cv_.blend(x, yi, gridCol, glow * fade);
    }
    for (int i = -12; i <= 12; i++) {                // lines from the vanishing point
      float xb = 160 + i * 34.0f;
      for (int y = HORIZON + 1; y < H; y++) {
        float k = (float)(y - HORIZON) / (H - 1 - HORIZON);
        cv_.blend((int)(160 + (xb - 160) * k), y, gridCol, glow * (0.25f + 0.75f * k));
      }
    }
    for (int x = 0; x < W; x++) cv_.blend(x, HORIZON, {255, 120, 230}, 0.9f);
  }

  // =========================================================================
  //  Lava lamp: soft blobs rising and sinking, melting into each other
  // =========================================================================
  static constexpr int LW = W / 2, LH = H / 2, BLOBS = 6;
  struct Blob {
    float x, y, r, speed, phase, wob, boost;
  } blobs_[BLOBS];

  void setupLava() {
    for (int i = 0; i < BLOBS; i++) {
      Blob &b = blobs_[i];
      b.x = 22 + (LW - 44) * (i + 0.5f) / BLOBS + rnd(-8, 8);
      b.r = rnd(5.5f, 9.5f);
      b.speed = rnd(0.035f, 0.08f);
      b.phase = rnd(0, 6.28f);
      b.wob = rnd(0, 6.28f);
      b.boost = 0;
      b.y = LH / 2;
    }
  }
  void lavaKick() {
    Blob &b = blobs_[rng_.next() % BLOBS];
    b.boost = 1.0f;
  }
  void updateLava(float dt) {
    for (auto &b : blobs_) {
      b.phase += dt * b.speed * 2 * PI_F * (1 + 2.5f * b.boost);
      b.boost = fmaxf(0, b.boost - dt * 0.5f);
      // up and down the whole lamp, slowest at the ends (like warm wax)
      b.y = LH * 0.5f + (LH * 0.5f - 4) * sinf(b.phase);
      b.x += sinf(t_ * 0.25f + b.wob) * dt * 2.5f;
      b.x = clampf(b.x, 14, LW - 14);
    }
  }
  void renderLava() {
    Col a, b;
    if (opts_ & OPT_A) {
      a = hsv(in_.accentHue, in_.accentSat, 255);
      b = hsv((uint16_t)(in_.accentHue + 5000), in_.accentSat, 230);
    } else {
      a = {255, 60, 170};
      b = {255, 150, 50};
    }
    const Col liquidTop = {30, 6, 58}, liquidBottom = {66, 10, 76};
    for (int y = 0; y < LH; y++) {
      Col liquid = mix(liquidTop, liquidBottom, (float)y / LH);
      Col blobCol = mix(a, b, (float)y / LH);
      for (int x = 0; x < LW; x++) {
        float f = 0;
        for (const auto &bl : blobs_) {
          float dx = x - bl.x, dy = (y - bl.y) * 1.2f;
          float d2 = dx * dx + dy * dy;
          float r2 = bl.r * bl.r;
          if (d2 < r2 * 9) {                       // smooth bump, zero beyond 3 radii
            float k = 1 - d2 / (r2 * 9);
            f += k * k * k;
          }
        }
        Col c;
        if (f < 0.12f) c = liquid;
        else if (f < 0.30f) c = mix(liquid, blobCol, (f - 0.12f) / 0.18f * 0.35f);   // glow round the wax
        else if (f < 0.38f) c = mix(mix(liquid, blobCol, 0.35f), blobCol, (f - 0.30f) / 0.08f);   // soft edge
        else {
          float in = clampf((f - 0.38f) * 1.6f, 0, 1);
          c = mix(blobCol, {255, 240, 215}, in * 0.35f);
        }
        // the round glass: darker towards both sides
        float side = fabsf(x - LW * 0.5f) / (LW * 0.5f);
        float shade = 1.0f - 0.45f * side * side;
        uint16_t p = pack(c.r * shade, c.g * shade, c.b * shade);
        uint16_t *row = fb_ + (y * 2) * W + x * 2;
        row[0] = row[1] = row[W] = row[W + 1] = p;
      }
    }
  }

  // =========================================================================
  //  Space: stars drifting by, shooting stars, a ringed planet, rockets
  // =========================================================================
  static constexpr int STARS = 100, ROCKETS = 3;
  struct Star {
    float x, y, speed, bright, tw;
    uint8_t layer;
  } stars_[STARS];
  struct Rocket {
    float x, y, vy, life;
    bool alive;
  } rockets_[ROCKETS];
  float shootT_ = 3, shootX_ = 0, shootY_ = 0, shootLife_ = 0;

  void setupSpace() {
    struct Cloud { float x, y, r; Col c; } clouds[6];
    for (int i = 0; i < 6; i++)
      clouds[i] = {rnd(20, 300), rnd(20, 150), rnd(35, 70), (i % 2) ? Col{110, 30, 150} : Col{20, 80, 140}};
    const float px = 252, py = 46, pr = 19, ra = pr * 2.0f, rb = pr * 0.5f;
    for (int y = 0; y < H; y++)
      for (int x = 0; x < W; x++) {
        Col c = mix({4, 4, 18}, {10, 6, 30}, (float)y / H);
        for (const auto &cl : clouds) {            // faint nebula clouds
          float dx = (x - cl.x) / cl.r, dy = (y - cl.y) / (cl.r * 0.6f);
          float d = dx * dx + dy * dy;
          if (d < 1) c = mix(c, cl.c, 0.22f * (1 - d) * (1 - d));
        }
        float dx = x + 0.5f - px, dy = y + 0.5f - py;
        float e = (dx * dx) / (ra * ra) + (dy * dy) / (rb * rb);
        bool ring = e > 0.55f && e < 1.0f;
        bool planet = dx * dx + dy * dy < pr * pr;
        if (planet && !(ring && dy > 0)) {          // the ring hides the planet only in front
          float lx = (dx + dy) / (pr * 1.4f);       // light from the upper left
          float band = 0.5f + 0.5f * sinf(dy * 0.55f);
          Col base = mix({200, 120, 70}, {245, 195, 130}, band);
          c = mix(base, {40, 18, 20}, clampf(lx * 0.8f + 0.25f, 0, 0.85f));
        } else if (ring) {
          float k = (e - 0.55f) / 0.45f;
          c = mix(c, mix({240, 215, 170}, {170, 130, 100}, k), 0.75f);
        }
        cv_.fb[y * W + x] = pack(c);
      }
    for (int i = 0; i < STARS; i++) {
      Star &s = stars_[i];
      s.layer = i < 45 ? 0 : (i < 80 ? 1 : 2);
      s.x = rnd(0, W);
      s.y = rnd(0, H);
      s.speed = s.layer == 0 ? 3 : (s.layer == 1 ? 9 : 20);
      s.bright = s.layer == 0 ? rnd(70, 140) : (s.layer == 1 ? rnd(130, 200) : rnd(190, 255));
      s.tw = rnd(0, 6.28f);
    }
    for (auto &r : rockets_) r.alive = false;
    shootT_ = rnd(2, 6);
    shootLife_ = 0;
  }
  void launchRocket() {
    for (auto &r : rockets_)
      if (!r.alive) {
        r.alive = true;
        r.x = -20;
        r.y = rnd(25, 145);
        r.vy = rnd(-8, 8);
        r.life = 0;
        return;
      }
  }
  void updateSpace(float dt) {
    for (auto &s : stars_) {
      s.x -= s.speed * dt;
      if (s.x < 0) {
        s.x += W;
        s.y = rnd(0, H);
      }
    }
    for (auto &r : rockets_)
      if (r.alive) {
        r.life += dt;
        r.x += 130 * dt;
        r.y += r.vy * dt + sinf(r.life * 5) * 0.3f;
        if (r.x > W + 30) r.alive = false;
      }
    if (shootLife_ > 0) {
      shootLife_ -= dt;
      shootX_ += 260 * dt;
      shootY_ += 120 * dt;
    } else if ((shootT_ -= dt) <= 0) {
      shootLife_ = 0.7f;
      shootX_ = rnd(20, 200);
      shootY_ = rnd(5, 50);
      shootT_ = rnd(4, 10);
    }
  }
  void renderSpace() {
    copyStill();
    for (const auto &s : stars_) {
      float b = s.bright * (0.75f + 0.25f * sinf(t_ * 2.3f + s.tw));
      int x = (int)s.x, y = (int)s.y;
      Col c = {b, b, fminf(255, b * 1.08f)};
      cv_.blend(x, y, c, 1.0f);
      if (s.layer == 2) {
        cv_.blend(x + 1, y, c, 0.45f);
        cv_.blend(x - 1, y, c, 0.45f);
        cv_.blend(x, y + 1, c, 0.45f);
        cv_.blend(x, y - 1, c, 0.45f);
      }
    }
    if (shootLife_ > 0) {
      float a = clampf(shootLife_ / 0.7f, 0, 1);
      for (int k = 0; k < 26; k++)
        cv_.blend((int)(shootX_ - k * 2.0f), (int)(shootY_ - k * 0.92f), {255, 255, 230}, a * (1 - k / 26.0f));
    }
    for (const auto &r : rockets_)
      if (r.alive) drawRocket(r.x, r.y, r.life);
  }
  void drawRocket(float x, float y, float life) {
    float f = 0.7f + 0.3f * sinf(life * 40);
    cv_.fillEllipse(x - 13, y, 8 * f, 3.2f, {255, 140, 30}, 0.9f);       // flame
    cv_.fillEllipse(x - 11, y, 4 * f, 1.8f, {255, 240, 120}, 1.0f);
    cv_.fillTri(x - 6, y - 4, x - 10, y - 8, x - 2, y - 4, {220, 40, 60}, 1.0f);   // fins
    cv_.fillTri(x - 6, y + 4, x - 10, y + 8, x - 2, y + 4, {220, 40, 60}, 1.0f);
    cv_.fillEllipse(x, y, 9, 4.2f, {235, 235, 245}, 1.0f);                // body
    cv_.fillTri(x + 7, y - 3.5f, x + 14, y, x + 7, y + 3.5f, {220, 40, 60}, 1.0f);  // nose
    cv_.fillCircle(x + 2, y, 1.8f, {80, 170, 255}, 1.0f);                 // window
  }

  // =========================================================================
  //  Campfire: the classic pixel fire, with sparks
  // =========================================================================
  static constexpr int FW = W / 2, FH = H / 2, SPARKS = 40, FIRE_LEVELS = 37;
  uint16_t firePal_[FIRE_LEVELS];
  struct Spark {
    float x, y, vx, vy, life;
  } sparks_[SPARKS];
  float fireAcc_ = 0, sparkT_ = 0;
  float fireCx_ = 160, fireHalf_ = 80;              // centre (screen pixels), half width (heat cells)
  float foxWake_ = 0, foxUp_ = 0, zzzT_ = 1;          // seconds left awake, head 0 = down .. 1 = up
  struct Zzz {
    float x, y, life;
  } zzz_[4];

  uint8_t *heat() { return reinterpret_cast<uint8_t *>(scratch_); }
  void setupFire() {
    static const uint8_t P[FIRE_LEVELS][3] = {
        {7, 7, 7},      {31, 7, 7},     {47, 15, 7},    {71, 15, 7},    {87, 23, 7},    {103, 31, 7},
        {119, 31, 7},   {143, 39, 7},   {159, 47, 7},   {175, 63, 7},   {191, 71, 7},   {199, 71, 7},
        {223, 79, 7},   {223, 87, 7},   {223, 87, 7},   {215, 95, 7},   {215, 95, 7},   {215, 103, 15},
        {207, 111, 15}, {207, 119, 15}, {207, 127, 15}, {207, 135, 23}, {199, 135, 23}, {199, 143, 23},
        {199, 151, 31}, {191, 159, 31}, {191, 159, 31}, {191, 167, 39}, {191, 167, 39}, {191, 175, 47},
        {183, 175, 47}, {183, 183, 47}, {183, 183, 55}, {207, 207, 111}, {223, 223, 159}, {239, 239, 199},
        {255, 255, 255}};
    for (int i = 0; i < FIRE_LEVELS; i++) firePal_[i] = pack8(P[i][0], P[i][1], P[i][2]);
    if (!scratch_) return;
    memset(heat(), 0, FW * FH);
    for (auto &s : sparks_) s.life = 0;
    for (auto &z : zzz_) z.life = 0;
    foxWake_ = foxUp_ = 0;
    fireGeometry();
    for (int i = 0; i < 70; i++) stepFire();         // starts already burning
  }
  // with the fox the fire is smaller and moves left, so he fits next to it
  void fireGeometry() {
    bool fox = opts_ & OPT_B;
    fireCx_ = fox ? 125 : 160;
    fireHalf_ = fox ? 48 : 80;
  }
  void sparks(int n) {
    for (auto &s : sparks_) {
      if (n <= 0) break;
      if (s.life > 0) continue;
      s.x = rnd(fireCx_ - 50, fireCx_ + 50);
      s.y = rnd(140, 160);
      s.vx = rnd(-25, 25);
      s.vy = rnd(-110, -60);
      s.life = rnd(0.8f, 1.6f);
      n--;
    }
  }
  void updateFire(float dt) {
    fireGeometry();
    if (opts_ & OPT_B) updateFox(dt);
    for (auto &s : sparks_)
      if (s.life > 0) {
        s.life -= dt;
        s.x += s.vx * dt + sinf(t_ * 6 + s.y * 0.1f) * 0.4f;
        s.y += s.vy * dt;
        s.vy += 18 * dt;
      }
    if ((sparkT_ -= dt) <= 0) {                     // a few embers all the time
      sparks(1);
      sparkT_ = rnd(0.15f, 0.5f);
    }
    if (!scratch_) return;
    fireAcc_ += dt;
    while (fireAcc_ >= 1.0f / 30) {                 // the fire itself moves at 30 steps a second
      fireAcc_ -= 1.0f / 30;
      stepFire();
    }
  }
  void stepFire() {
    uint8_t *h = heat();
    // the glowing bed of the fire: a mound in the middle
    float beat = (opts_ & OPT_A) ? in_.level : 0.6f;
    for (int x = 0; x < FW; x++) {
      float d = fabsf(x - fireCx_ / 2) / fireHalf_;
      float bed = (1 - d * d * 1.3f) * (26 + 10 * beat + 3 * sinf(t_ * 3 + x * 0.3f));
      h[(FH - 1) * FW + x] = (uint8_t)clampi((int)bed, 0, FIRE_LEVELS - 1);
    }
    for (int y = 1; y < FH; y++)
      for (int x = 0; x < FW; x++) {
        uint8_t v = h[y * FW + x];
        if (v == 0) {
          h[(y - 1) * FW + x] = 0;
          continue;
        }
        uint32_t r = rng_.next();
        int dx = x + (int)(r % 3) - 1;               // drifts left or right evenly
        if (dx < 0) dx = 0;
        if (dx >= FW) dx = FW - 1;
        int nv = v - (int)((r >> 8) & 1);
        h[(y - 1) * FW + dx] = (uint8_t)(nv < 0 ? 0 : nv);
      }
  }
  void renderFire() {
    if (scratch_) {
      const uint8_t *h = heat();
      for (int y = 0; y < FH; y++) {
        uint16_t *row = fb_ + (y * 2) * W;
        for (int x = 0; x < FW; x++) {
          uint16_t p = firePal_[h[y * FW + x]];
          row[x * 2] = row[x * 2 + 1] = row[W + x * 2] = row[W + x * 2 + 1] = p;
        }
      }
    } else {
      for (int i = 0; i < W * H; i++) fb_[i] = firePal_[0];
    }
    // logs under the fire
    const float lx = fireCx_, lw = fireHalf_ / 80.0f;
    cv_.fillEllipse(lx - 30 * lw, 164, 46 * lw, 7, {70, 38, 20}, 1.0f);
    cv_.fillEllipse(lx + 30 * lw, 165, 46 * lw, 7, {85, 46, 24}, 1.0f);
    cv_.fillEllipse(lx, 163, 30 * lw, 5, {60, 30, 16}, 1.0f);
    if (opts_ & OPT_B) drawFox();
    for (const auto &s : sparks_)
      if (s.life > 0) {
        float a = clampf(s.life, 0, 1);
        Col c = mix({255, 80, 20}, {255, 230, 120}, a);
        cv_.blend((int)s.x, (int)s.y, c, a);
        cv_.blend((int)s.x + 1, (int)s.y, c, a * 0.5f);
      }
  }

  // --- the sleepy fox: curled up right of the fire, looks up when a key is pressed
  void updateFox(float dt) {
    foxWake_ = fmaxf(0, foxWake_ - dt);
    float target = foxWake_ > 0 ? 1.0f : 0.0f;
    foxUp_ += (target - foxUp_) * fminf(1.0f, dt * (target > foxUp_ ? 6.0f : 1.2f));
    for (auto &z : zzz_)
      if (z.life > 0) {
        z.life -= foxUp_ > 0.3f ? 1.0f : dt;        // he woke up: the z's vanish
        z.life -= dt;
        z.y -= 9 * dt;
        z.x += sinf(z.life * 3) * 4 * dt + 3 * dt;
      }
    if (foxUp_ < 0.1f && (zzzT_ -= dt) <= 0) {    // asleep: little z's float up
      for (auto &z : zzz_)
        if (z.life <= 0) {
          z.x = 240;
          z.y = 136;
          z.life = 2.4f;
          break;
        }
      zzzT_ = 1.3f;
    }
  }
  void glyphBlend(char ch, float x, float y, Col c, float a, int scale) {
    const uint8_t *g = &FONT5x7[(ch - 32) * 5];
    for (int col = 0; col < 5; col++)
      for (int r = 0; r < 7; r++)
        if (g[col] & (1 << r))
          for (int sy = 0; sy < scale; sy++)
            for (int sx = 0; sx < scale; sx++) cv_.blend((int)x + col * scale + sx, (int)y + r * scale + sy, c, a);
  }
  void drawFox() {
    const float up = foxUp_;
    const float breath = sinf(t_ * 1.7f) * (1 - up);
    const float flick = 0.86f + 0.14f * sinf(t_ * 9) * sinf(t_ * 3.7f);   // firelight
    auto lit = [&](Col c) { return Col{c.r * flick, c.g * flick, c.b * flick}; };
    const Col fur = lit({226, 116, 46}), furDark = lit({150, 64, 28}), furLight = lit({240, 150, 70});
    const Col cream = lit({248, 230, 200}), dark = {38, 20, 16};
    const float X = 262, G = 166;                   // where he lies: centre, ground
    auto E = [&](float x, float y, float rx, float ry, Col c, float a) { cv_.fillEllipse(X + x, G + y, rx, ry, c, a); };
    auto T = [&](float x0, float y0, float x1, float y1, float x2, float y2, Col c, float a) {
      cv_.fillTri(X + x0, G + y0, X + x1, G + y1, X + x2, G + y2, c, a);
    };

    E(0, 0, 44, 4, {0, 0, 0}, 0.4f);                                  // shadow
    E(1, -13, 31, 14 + breath * 0.8f, furDark, 1.0f);                  // body
    E(-1, -14, 29, 12.5f + breath * 0.8f, fur, 1.0f);
    E(-4, -20, 18, 4, furLight, 0.5f);                                 // firelight on the back
    E(17, -12, 11, 10, fur, 1.0f);                                     // hind leg
    E(15, -15, 6, 4, furLight, 0.45f);

    // head: lies on the tail, lifts and looks at the fire when he is awake
    const float hx = -27 - 3 * up, hy = -13 - 15 * up;
    if (up > 0.03f) E((hx - 14) / 2, (hy - 16) / 2, 9, 5 + 6 * up, fur, 1.0f);   // neck
    const float lean = 3 * (1 - up);                // ears lie back while he sleeps
    T(hx - 7, hy - 5, hx - 1, hy - 6, hx - 6 + lean, hy - 16 + lean * 0.6f, fur, 1.0f);   // ears
    T(hx - 5.5f, hy - 6, hx - 2.5f, hy - 6, hx - 5 + lean, hy - 12.5f + lean * 0.6f, dark, 0.7f);
    T(hx + 1, hy - 6, hx + 8, hy - 4, hx + 5 + lean, hy - 15 + lean * 0.6f, furDark, 1.0f);
    E(hx, hy, 11, 9, fur, 1.0f);
    E(hx + 1, hy - 4, 7, 3, furLight, 0.5f);
    T(hx - 6, hy - 3, hx - 6, hy + 5, hx - 20, hy + 2, fur, 1.0f);   // snout
    T(hx - 6, hy + 1.5f, hx - 6, hy + 5.5f, hx - 18, hy + 3, cream, 1.0f);
    E(hx - 2, hy + 4.5f, 5.5f, 3, cream, 1.0f);                      // cheek
    cv_.fillCircle(X + hx - 19.5f, G + hy + 1.8f, 2, dark, 1.0f);    // nose
    if (up > 0.5f) {                                 // eyes open, the fire glints in them
      cv_.fillCircle(X + hx - 5, G + hy - 2, 1.9f, dark, 1.0f);
      cv_.blend((int)(X + hx - 6), (int)(G + hy - 3), {255, 225, 160}, 1.0f);
    } else {                                         // eyes shut: a small curve
      const int ex = (int)(X + hx - 7), ey = (int)(G + hy - 2);
      cv_.blend(ex, ey, dark, 1.0f);
      cv_.blend(ex + 1, ey + 1, dark, 1.0f);
      cv_.blend(ex + 2, ey + 1, dark, 1.0f);
      cv_.blend(ex + 3, ey + 1, dark, 1.0f);
      cv_.blend(ex + 4, ey, dark, 1.0f);
    }

    // the big bushy tail wraps round the front; it wags a little when he is awake
    const float wag = up * sinf(t_ * 7) * 3;
    E(4, -5, 30, 7, furDark, 1.0f);
    E(3, -6, 29, 6, fur, 1.0f);
    E(-21 + wag * 0.4f, -6 + wag * 0.15f, 13, 6.5f, fur, 1.0f);
    E(-32 + wag, -6 + wag * 0.3f, 6.5f, 4.5f, cream, 1.0f);           // white tip
    if (up < 0.4f) T(hx - 3, hy + 6, hx + 6, hy + 6, hx + 1, hy + 9, cream, 0.9f);   // paw under the chin

    for (const auto &z : zzz_)
      if (z.life > 0) {
        float a = fminf(1.0f, z.life / 0.8f) * fminf(1.0f, (2.4f - z.life) / 0.3f);
        glyphBlend('z', z.x, z.y, {230, 225, 255}, a * 0.9f, z.life < 1.4f ? 2 : 1);
      }
  }

  // =========================================================================
  //  Matrix: falling code; pressed keys fall along as words
  // =========================================================================
  static constexpr int MCOLS = W / 6, MROWS = H / 8;       // 53 x 21 cells of 6 x 8 pixels
  struct Column {
    float head, speed, wait;
    uint8_t trail;
    char word[24];
    uint8_t wordLen, wordPos;
    int16_t lastRow;
  } cols_[MCOLS];
  uint8_t cells_[MCOLS * MROWS];                           // < 100: strange glyph, >= 100: letter (ch - 32 + 100)

  void setupMatrix() {
    for (int c = 0; c < MCOLS; c++) {
      cols_[c] = Column{};
      respawn(cols_[c], true);
      for (int r = 0; r < MROWS; r++) cells_[c * MROWS + r] = (uint8_t)(rng_.next() % GLYPHS);
    }
  }
  void respawn(Column &col, bool anywhere) {
    col.speed = rnd(5, 16);
    col.trail = (uint8_t)rnd(6, 17);
    col.head = anywhere ? rnd(-MROWS, MROWS) : rnd(-8, -1);
    col.wait = anywhere ? 0 : rnd(0, 2.5f);
    col.wordLen = col.wordPos = 0;
    col.lastRow = -100;
  }
  void matrixWord(const char *label) {
    int best = (int)(rng_.next() % MCOLS);
    for (int tries = 0; tries < 12; tries++) {       // prefer a column that is waiting at the top
      int c = (int)(rng_.next() % MCOLS);
      if (cols_[c].head < 0 || cols_[c].head - cols_[c].trail > MROWS) {
        best = c;
        break;
      }
    }
    Column &col = cols_[best];
    respawn(col, false);
    col.wait = 0;
    col.head = -1;
    col.speed = 9;
    col.trail = 20;
    size_t n = 0;
    for (const char *p = label; *p && n < sizeof(col.word) - 1; p++) {
      uint8_t ch = (uint8_t)*p;
      switch (ch) {                                  // German letters on the pad are CP437
        case 0x84: case 0x8E: ch = 'A'; break;
        case 0x94: case 0x99: ch = 'O'; break;
        case 0x81: case 0x9A: ch = 'U'; break;
        case 0xE1: ch = 'S'; break;
        default: if (ch < 32 || ch > 126) ch = '?';
      }
      col.word[n++] = (char)ch;
    }
    col.word[n] = 0;
    col.wordLen = (uint8_t)n;
  }
  void updateMatrix(float dt) {
    for (int c = 0; c < MCOLS; c++) {
      Column &col = cols_[c];
      if (col.wait > 0) {
        col.wait -= dt;
        continue;
      }
      col.head += col.speed * dt;
      int row = (int)col.head;
      while (col.lastRow < row) {                    // a new cell reached: give it a character
        col.lastRow = col.lastRow < -1 ? row : col.lastRow + 1;
        if (col.lastRow >= 0 && col.lastRow < MROWS) {
          uint8_t v;
          if (col.wordPos < col.wordLen) v = (uint8_t)(col.word[col.wordPos++] - 32 + 100);
          else v = (uint8_t)(rng_.next() % GLYPHS);
          cells_[c * MROWS + col.lastRow] = v;
        }
      }
      if (col.head - col.trail > MROWS) respawn(col, false);
    }
    for (int i = 0; i < 18; i++) {                   // the code keeps changing a little
      int k = (int)(rng_.next() % (MCOLS * MROWS));
      if (cells_[k] < 100) cells_[k] = (uint8_t)(rng_.next() % GLYPHS);
    }
  }
  void renderMatrix() {
    for (int i = 0; i < W * H; i++) fb_[i] = 0;
    for (int c = 0; c < MCOLS; c++) {
      const Column &col = cols_[c];
      if (col.wait > 0) continue;
      int head = (int)col.head;
      for (int k = 0; k <= col.trail; k++) {
        int r = head - k;
        if (r < 0 || r >= MROWS) continue;
        uint8_t v = cells_[c * MROWS + r];
        bool letter = v >= 100;
        float b = 1.0f - (float)k / (col.trail + 1);
        uint16_t colour;
        if (k == 0) colour = pack8(210, 255, 215);
        else if (letter) colour = pack(255 * b, 230 * b, 90 * b);       // words glow golden
        else colour = pack(0, 40 + 215 * b, 20 + 60 * b);
        const uint8_t *g = letter ? fontChar((char)(v - 100 + 32)) : glyphs_[v % GLYPHS];
        glyph(g, c * 6, r * 8, colour);
      }
    }
  }

  // =========================================================================
  //  Rainy night: a city skyline, rain, drops on the glass, lightning
  // =========================================================================
  static constexpr int RAIN_N = 90, DROPS = 16, WINDOWS = 360;
  struct RainDrop {
    float x, y, speed, len, a;
  } rain_[RAIN_N];
  struct GlassDrop {
    float x, y, r, slide, wait;
  } glass_[DROPS];
  struct Window {
    int16_t x, y;
    uint8_t lit;
  } windows_[WINDOWS];
  int windowCount_ = 0;
  float flash_ = 0, boltT_ = 6, windowT_ = 1;
  float boltX_[12], boltY_[12];

  void drawWindow(const Window &w) {
    Col c = w.lit == 1 ? Col{255, 200, 110} : (w.lit == 2 ? Col{180, 210, 255} : Col{22, 24, 40});
    cv_.fillRect(w.x, w.y, 3, 4, c, 1.0f);
  }
  void setupRain() {
    verticalGradient(0, H, {10, 12, 30}, {48, 40, 70});
    cv_.fillCircle(60, 32, 12, {200, 205, 220}, 0.18f);   // the moon behind clouds
    cv_.fillCircle(60, 32, 9, {220, 225, 235}, 0.35f);
    for (int i = 0; i < 14; i++)
      cv_.fillEllipse(rnd(0, W), rnd(10, 60), rnd(30, 70), rnd(6, 12), {40, 42, 66}, 0.35f);
    windowCount_ = 0;
    int x = 0;
    while (x < W) {                                  // buildings with rows of windows
      int w = (int)rnd(16, 42), h = (int)rnd(45, 125);
      int top = H - h;
      Col body = mix({10, 12, 26}, {22, 22, 40}, rnd(0, 1));
      cv_.fillRect(x, top, w, h, body, 1.0f);
      if (rng_.next() % 3 == 0) cv_.fillRect(x + w / 2 - 1, top - 8, 2, 8, body, 1.0f);   // antenna
      for (int wy = top + 5; wy < H - 6; wy += 7)
        for (int wx = x + 3; wx < x + w - 4; wx += 6) {
          if (windowCount_ >= WINDOWS) break;
          Window &win = windows_[windowCount_++];
          win.x = (int16_t)wx;
          win.y = (int16_t)wy;
          uint32_t r = rng_.next() % 10;
          win.lit = r < 3 ? 1 : (r < 4 ? 2 : 0);
          drawWindow(win);
        }
      x += w + (int)rnd(0, 4);
    }
    for (auto &d : rain_) {
      d.x = rnd(0, W + 40);
      d.y = rnd(-H, H);
      d.speed = rnd(210, 330);
      d.len = rnd(5, 12);
      d.a = rnd(0.25f, 0.6f);
    }
    for (auto &g : glass_) newGlassDrop(g, true);
    flash_ = 0;
    boltT_ = rnd(5, 12);
  }
  void newGlassDrop(GlassDrop &g, bool anywhere) {
    g.x = rnd(5, W - 5);
    g.y = anywhere ? rnd(5, H - 5) : rnd(-5, H * 0.6f);
    g.r = rnd(1.5f, 3.6f);
    g.slide = 0;
    g.wait = rnd(0.5f, 6);
  }
  void drops(int n) {
    for (int i = 0; i < n; i++) newGlassDrop(glass_[rng_.next() % DROPS], true);
  }
  void updateRain(float dt) {
    for (auto &d : rain_) {
      d.y += d.speed * dt;
      d.x -= d.speed * 0.22f * dt;
      if (d.y > H) {
        d.y = rnd(-30, -5);
        d.x = rnd(0, W + 40);
      }
    }
    for (auto &g : glass_) {
      if (g.wait > 0) g.wait -= dt;
      else {
        g.slide += dt * 18 * g.r;
        g.y += dt * (25 + 30 * g.r);
        if (g.y > H + 5) newGlassDrop(g, false);
      }
    }
    if ((windowT_ -= dt) <= 0 && windowCount_ > 0) {   // someone switches a light on or off
      Window &w = windows_[rng_.next() % windowCount_];
      w.lit = w.lit ? 0 : (rng_.next() % 4 == 0 ? 2 : 1);
      toStill(true);
      drawWindow(w);
      toStill(false);
      windowT_ = rnd(0.4f, 1.8f);
    }
    if (flash_ > 0) flash_ -= dt;
    if ((opts_ & OPT_A) && (boltT_ -= dt) <= 0) {
      flash_ = 0.35f;
      float x = rnd(40, 280), y = 0;
      for (int i = 0; i < 12; i++) {
        boltX_[i] = x;
        boltY_[i] = y;
        x += rnd(-12, 12);
        y += rnd(5, 9);
      }
      boltT_ = rnd(7, 18);
    }
  }
  void renderRain() {
    copyStill();
    if (flash_ > 0) {
      int amount = (int)(flash_ / 0.35f * 120);
      if (flash_ > 0.2f && flash_ < 0.26f) amount /= 3;    // the flicker of a real flash
      for (int i = 0; i < W * H; i++) aq::Canvas::addI(fb_[i], amount);
      for (int i = 0; i < 11; i++) {
        line(boltX_[i], boltY_[i], boltX_[i + 1], boltY_[i + 1], {240, 240, 255}, 1.0f);
        line(boltX_[i] + 1, boltY_[i], boltX_[i + 1] + 1, boltY_[i + 1], {180, 190, 255}, 0.6f);
      }
    }
    for (const auto &d : rain_) line(d.x, d.y, d.x + d.len * 0.22f, d.y - d.len, {170, 180, 210}, d.a);
    for (const auto &g : glass_) {
      cv_.fillCircle(g.x, g.y, g.r + 0.6f, {20, 22, 40}, 0.45f);
      cv_.fillCircle(g.x, g.y, g.r, {120, 130, 160}, 0.55f);
      cv_.fillCircle(g.x - g.r * 0.35f, g.y - g.r * 0.35f, g.r * 0.35f, {240, 245, 255}, 0.8f);
    }
  }

  // =========================================================================
  //  Seasons: snow, cherry blossoms, fireflies, autumn leaves
  // =========================================================================
  static constexpr int PARTS = 70;
  struct Part {
    float x, y, vx, vy, size, phase, spin;
    uint8_t tint;
  } parts_[PARTS];
  float gust_ = 0;

  void tree(float x, float ground, float h, Col trunk, Col leaves, int season) {
    cv_.fillRect(x - 2, ground - h * 0.45f, 4, h * 0.45f, trunk, 1.0f);
    if (season == 0) {                               // snowy pine
      for (int k = 0; k < 3; k++) {
        float y0 = ground - h * (0.25f + 0.25f * k), w = h * (0.42f - 0.1f * k);
        cv_.fillTri(x - w, y0, x + w, y0, x, y0 - h * 0.38f, {20, 60, 50}, 1.0f);
        cv_.fillTri(x - w * 0.45f, y0 - h * 0.2f, x + w * 0.45f, y0 - h * 0.2f, x, y0 - h * 0.38f, {235, 240, 250}, 0.9f);
      }
      return;
    }
    for (int k = 0; k < 5; k++)
      cv_.fillCircle(x + rnd(-h * 0.22f, h * 0.22f), ground - h * 0.6f + rnd(-h * 0.15f, h * 0.15f), h * rnd(0.18f, 0.26f),
                     mix(leaves, {255, 255, 255}, rnd(0, 0.15f)), 1.0f);
  }
  void hills(float base, float amp, float freq, float phase, Col c) {
    for (int x = 0; x < W; x++) {
      int top = (int)(base - amp * sinf(x * freq + phase) - amp * 0.4f * sinf(x * freq * 2.7f + phase * 1.3f));
      uint16_t p = pack(c);
      for (int y = top < 0 ? 0 : top; y < H; y++) cv_.fb[y * W + x] = p;
    }
  }
  void setupSeasons() {
    const int s = season_;
    if (s == 0) {                                    // winter evening
      verticalGradient(0, H, {40, 56, 96}, {170, 180, 205});
      hills(120, 10, 0.02f, 1, {200, 210, 230});
      for (int i = 0; i < 6; i++) tree(rnd(10, 310), rnd(122, 140), rnd(35, 55), {50, 35, 30}, {}, 0);
      cv_.fillRect(205, 112, 34, 22, {90, 50, 40}, 1.0f);             // cabin
      cv_.fillTri(200, 113, 244, 113, 222, 96, {240, 244, 250}, 1.0f);
      cv_.fillRect(213, 119, 7, 7, {255, 200, 100}, 1.0f);
      hills(150, 6, 0.03f, 4, {235, 240, 250});
    } else if (s == 1) {                             // spring
      verticalGradient(0, H, {110, 170, 240}, {200, 230, 250});
      for (int i = 0; i < 5; i++) {
        float x = rnd(0, W), y = rnd(15, 55);
        for (int k = 0; k < 4; k++) cv_.fillCircle(x + k * 9, y + (k % 2) * 3, 8 + (k % 2) * 3, {255, 255, 255}, 0.85f);
      }
      hills(125, 12, 0.018f, 2, {110, 190, 90});
      for (int i = 0; i < 5; i++) tree(rnd(15, 305), rnd(128, 145), rnd(40, 60), {100, 70, 50}, {255, 170, 200}, 1);
      hills(152, 6, 0.03f, 5, {80, 170, 70});
    } else if (s == 2) {                             // summer evening
      verticalGradient(0, 90, {40, 30, 90}, {250, 140, 90});
      verticalGradient(90, H, {250, 140, 90}, {60, 40, 70});
      cv_.fillCircle(240, 96, 18, {255, 220, 140}, 0.9f);
      hills(118, 10, 0.02f, 3, {30, 50, 40});
      for (int i = 0; i < 4; i++) tree(rnd(15, 305), rnd(122, 140), rnd(40, 60), {20, 25, 20}, {25, 45, 30}, 2);
      hills(145, 8, 0.035f, 1, {15, 30, 22});
    } else {                                         // autumn
      verticalGradient(0, H, {250, 190, 120}, {255, 225, 170});
      hills(122, 12, 0.02f, 4, {170, 110, 60});
      for (int i = 0; i < 6; i++) {
        Col leaves = (i % 3 == 0) ? Col{230, 90, 40} : ((i % 3 == 1) ? Col{240, 160, 40} : Col{200, 60, 40});
        tree(rnd(10, 310), rnd(125, 145), rnd(40, 60), {90, 55, 35}, leaves, 3);
      }
      hills(150, 6, 0.03f, 2, {140, 85, 45});
    }
    for (auto &p : parts_) newPart(p, true);
    gust_ = 0;
  }
  void newPart(Part &p, bool anywhere) {
    p.x = rnd(-20, W + 20);
    p.y = anywhere ? rnd(-10, H) : rnd(-20, -4);
    p.phase = rnd(0, 6.28f);
    p.spin = rnd(1, 3);
    p.tint = (uint8_t)(rng_.next() % 4);
    switch (season_) {
      case 0: p.size = rnd(0.8f, 2.4f); p.vy = 12 + 10 * p.size; p.vx = rnd(-6, 6); break;
      case 1: p.size = rnd(1.2f, 2.2f); p.vy = rnd(14, 26); p.vx = rnd(8, 22); break;
      case 2: p.size = rnd(1.0f, 1.8f); p.vy = rnd(-6, 6); p.vx = rnd(-8, 8);
              p.y = anywhere ? rnd(60, H - 10) : rnd(60, H - 10); break;
      default: p.size = rnd(2.0f, 3.5f); p.vy = rnd(18, 32); p.vx = rnd(-6, 10); break;
    }
  }
  void updateSeasons(float dt) {
    gust_ = fmaxf(0, gust_ - dt * 40);
    for (auto &p : parts_) {
      p.phase += dt * p.spin;
      if (season_ == 2) {                            // fireflies wander and blink
        p.x += (p.vx + sinf(p.phase * 0.7f) * 6 + gust_ * 0.5f) * dt;
        p.y += (p.vy + cosf(p.phase * 0.9f) * 5) * dt;
        if (p.y < 50 || p.y > H - 5) p.vy = -p.vy;
        if (p.x < -10) p.x = W + 5;
        if (p.x > W + 10) p.x = -5;
        continue;
      }
      p.x += (p.vx + sinf(p.phase) * 10 + gust_) * dt;
      p.y += p.vy * dt;
      if (p.y > H + 6 || p.x > W + 30) newPart(p, false);
    }
  }
  void renderSeasons() {
    copyStill();
    for (const auto &p : parts_) {
      switch (season_) {
        case 0:
          cv_.fillCircle(p.x, p.y, p.size, {255, 255, 255}, 0.9f);
          break;
        case 1:
          cv_.fillEllipse(p.x, p.y, p.size * (1.0f + 0.5f * sinf(p.phase)), p.size * 0.7f,
                          p.tint % 2 ? Col{255, 190, 215} : Col{255, 225, 235}, 0.95f);
          break;
        case 2: {
          float glow = 0.5f + 0.5f * sinf(p.phase * 2.2f);
          cv_.fillCircle(p.x, p.y, p.size * 3, {220, 255, 120}, 0.12f * glow);
          cv_.fillCircle(p.x, p.y, p.size, {240, 255, 160}, 0.4f + 0.6f * glow);
          break;
        }
        default: {
          static const Col LEAF[4] = {{220, 80, 30}, {240, 160, 40}, {190, 50, 30}, {150, 90, 40}};
          float s = p.size, c = cosf(p.phase), sn = sinf(p.phase);
          float ax = c * s, ay = sn * s, bx = -sn * s * 0.5f, by = c * s * 0.5f;
          cv_.fillTri(p.x - ax, p.y - ay, p.x + bx, p.y + by, p.x + ax, p.y + ay, LEAF[p.tint], 1.0f);
          cv_.fillTri(p.x - ax, p.y - ay, p.x - bx, p.y - by, p.x + ax, p.y + ay, LEAF[p.tint], 1.0f);
          break;
        }
      }
    }
  }
};

}  // namespace bgx

#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC pop_options
#endif
