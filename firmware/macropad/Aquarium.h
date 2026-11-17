// Aquarium.h - a small animated aquarium for a 320 x 170 RGB565 frame buffer.
//
// Pure C++ (no Arduino calls), so the same code runs on the T-Display-S3
// and on a PC for previews. The sketch gives it a frame buffer, calls
// update() and render() every frame and then pushes the buffer to the screen.

#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>

// Arduino builds with -Os (small code). This file is the hot path, so build it for speed.
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC push_options
#pragma GCC optimize("O2")
#endif

namespace aq {

constexpr int W = 320;
constexpr int H = 170;
constexpr float PI_F = 3.14159265f;

// ---------------------------------------------------------------------------
//  Small helpers
// ---------------------------------------------------------------------------

struct Col {
  float r, g, b;
};

inline float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline float lerpf(float a, float b, float t) { return a + (b - a) * t; }
inline Col mix(Col a, Col b, float t) { return {lerpf(a.r, b.r, t), lerpf(a.g, b.g, t), lerpf(a.b, b.b, t)}; }
inline Col scale(Col c, float k) { return {c.r * k, c.g * k, c.b * k}; }

inline uint16_t pack(float r, float g, float b) {
  int ri = (int)clampf(r, 0, 255), gi = (int)clampf(g, 0, 255), bi = (int)clampf(b, 0, 255);
  return (uint16_t)(((ri & 0xF8) << 8) | ((gi & 0xFC) << 3) | (bi >> 3));
}
inline uint16_t pack(Col c) { return pack(c.r, c.g, c.b); }
inline Col unpack(uint16_t c) {
  int r = (c >> 8) & 0xF8, g = (c >> 3) & 0xFC, b = (c << 3) & 0xF8;
  return {(float)(r | (r >> 5)), (float)(g | (g >> 6)), (float)(b | (b >> 5))};
}

// Integer versions for the per-pixel work (much cheaper on the ESP32 than floats).
struct C8 {
  int r, g, b;  // 0..255
};
inline int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
// floor / ceil to int without a library call
inline int ifloor(float v) {
  int i = (int)v;
  return v < (float)i ? i - 1 : i;
}
inline int iceil(float v) {
  int i = (int)v;
  return v > (float)i ? i + 1 : i;
}
inline C8 toC8(Col c) { return {clampi((int)c.r, 0, 255), clampi((int)c.g, 0, 255), clampi((int)c.b, 0, 255)}; }
inline uint16_t pack8(int r, int g, int b) { return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)); }
inline uint16_t pack8(C8 c) { return pack8(c.r, c.g, c.b); }
// opacity 0..1 -> 0..256
inline int alpha256(float a) { return a <= 0 ? 0 : (a >= 1 ? 256 : (int)(a * 256.0f + 0.5f)); }
// mix colour c over pixel d with opacity a (0..256)
inline uint16_t blend565(uint16_t d, const C8 &c, int a) {
  int r = (d >> 8) & 0xF8, g = (d >> 3) & 0xFC, b = (d << 3) & 0xF8;
  r |= r >> 5;
  g |= g >> 6;
  b |= b >> 5;
  r += ((c.r - r) * a) >> 8;
  g += ((c.g - g) * a) >> 8;
  b += ((c.b - b) * a) >> 8;
  return pack8(r, g, b);
}

// Fast sine from a table: plenty for animation, much cheaper than sinf().
class SinTable {
 public:
  SinTable() {
    for (int i = 0; i < N; i++) t_[i] = sinf(i * 2 * PI_F / N);
  }
  float sin(float x) const { return t_[(int)(x * (N / (2 * PI_F))) & (N - 1)]; }
  float cos(float x) const { return sin(x + PI_F / 2); }

 private:
  static constexpr int N = 1024;
  float t_[N];
};

class Rng {
 public:
  explicit Rng(uint32_t seed = 1) : s_(seed ? seed : 1) {}
  uint32_t next() {
    s_ ^= s_ << 13;
    s_ ^= s_ >> 17;
    s_ ^= s_ << 5;
    return s_;
  }
  float uni() { return (next() >> 8) * (1.0f / 16777216.0f); }
  float range(float a, float b) { return a + (b - a) * uni(); }

 private:
  uint32_t s_;
};

// ---------------------------------------------------------------------------
//  Drawing into an RGB565 buffer, with transparency and soft edges
// ---------------------------------------------------------------------------

class Canvas {
 public:
  uint16_t *fb = nullptr;

  inline void put(int x, int y, Col c) {
    if ((unsigned)x < (unsigned)W && (unsigned)y < (unsigned)H) fb[y * W + x] = pack(c);
  }
  // a = opacity 0..256
  inline void blendI(int x, int y, const C8 &c, int a) {
    if ((unsigned)x >= (unsigned)W || (unsigned)y >= (unsigned)H || a <= 0) return;
    uint16_t &p = fb[y * W + x];
    p = a >= 256 ? pack8(c) : blend565(p, c, a);
  }
  // a = opacity 0..1
  inline void blend(int x, int y, Col c, float a) {
    if (a <= 0.004f) return;
    blendI(x, y, toC8(c), alpha256(a));
  }
  // brighten (light on the sand)
  static inline void addI(uint16_t &p, int amount) {
    int r = (p >> 8) & 0xF8, g = (p >> 3) & 0xFC, b = (p << 3) & 0xF8;
    r |= r >> 5;
    g |= g >> 6;
    b |= b >> 5;
    r += amount;
    g += amount;
    b += (amount * 7) >> 3;
    p = pack8(r > 255 ? 255 : r, g > 255 ? 255 : g, b > 255 ? 255 : b);
  }

  // Horizontal run from x = L to x = R (fractions give soft ends), fully opaque.
  void span(int y, float L, float R, const C8 &c) {
    if ((unsigned)y >= (unsigned)H || R <= L) return;
    uint16_t *row = fb + y * W;
    const uint16_t solid = pack8(c);
    int xa = ifloor(L), xb = iceil(R) - 1;
    if (xa == xb) {
      if ((unsigned)xa < (unsigned)W) row[xa] = blend565(row[xa], c, (int)((R - L) * 256));
      return;
    }
    if ((unsigned)xa < (unsigned)W) row[xa] = blend565(row[xa], c, (int)((xa + 1 - L) * 256));
    if ((unsigned)xb < (unsigned)W) row[xb] = blend565(row[xb], c, (int)((R - xb) * 256));
    int a = xa + 1 < 0 ? 0 : xa + 1, b = xb - 1 > W - 1 ? W - 1 : xb - 1;
    for (int x = a; x <= b; x++) row[x] = solid;
  }

  // Soft-edged disc. Each row is: soft left rim, solid middle, soft right rim.
  void fillCircle(float cx, float cy, float r, Col c, float a) {
    if (r <= 0 || a <= 0.004f) return;
    const C8 ci = toC8(c);
    const int ai = alpha256(a);
    const uint16_t solid = pack8(ci);
    const float ro = r + 0.5f, ri = r - 0.5f;
    const float ro2 = ro * ro, ri2 = ri > 0 ? ri * ri : -1.0f;
    int y0 = ifloor(cy - ro), y1 = iceil(cy + ro);
    if (y0 < 0) y0 = 0;
    if (y1 > H - 1) y1 = H - 1;
    for (int y = y0; y <= y1; y++) {
      const float dy = y + 0.5f - cy, dy2 = dy * dy;
      if (dy2 >= ro2) continue;
      const float ho = sqrtf(ro2 - dy2);
      int xa = ifloor(cx - ho - 0.5f), xb = iceil(cx + ho - 0.5f);
      if (xa < 0) xa = 0;
      if (xb > W - 1) xb = W - 1;
      int ia = xb + 1, ib = xb;  // solid part (empty unless the row crosses the inner disc)
      if (dy2 < ri2) {
        const float hi = sqrtf(ri2 - dy2);
        ia = iceil(cx - hi - 0.5f);
        ib = ifloor(cx + hi - 0.5f);
        if (ia < xa) ia = xa;
        if (ib > xb) ib = xb;
        if (ib < ia - 1) ib = ia - 1;
      }
      uint16_t *row = fb + y * W;
      for (int x = xa; x < ia && x <= xb; x++) rim(row[x], x + 0.5f - cx, dy2, ro, ro2, ci, ai);
      if (ai >= 256)
        for (int x = ia; x <= ib; x++) row[x] = solid;
      else
        for (int x = ia; x <= ib; x++) row[x] = blend565(row[x], ci, ai);
      for (int x = ib + 1 > xa ? ib + 1 : xa; x <= xb; x++) rim(row[x], x + 0.5f - cx, dy2, ro, ro2, ci, ai);
    }
  }
  static inline void rim(uint16_t &p, float dx, float dy2, float ro, float ro2, const C8 &c, int ai) {
    float d2 = dx * dx + dy2;
    if (d2 >= ro2) return;
    float cov = ro - sqrtf(d2);
    int aa = cov >= 1 ? ai : (int)(ai * cov);
    if (aa > 0) p = aa >= 256 ? pack8(c) : blend565(p, c, aa);
  }

  void ring(float cx, float cy, float r, float th, Col c, float a) {
    const C8 ci = toC8(c);
    const int ai = alpha256(a);
    const float half = th * 0.5f + 0.5f;
    const float ro = r + half, ri = r - half;
    const float ro2 = ro * ro, ri2 = ri > 0 ? ri * ri : -1.0f;
    int x0 = ifloor(cx - ro), x1 = iceil(cx + ro);
    int y0 = ifloor(cy - ro), y1 = iceil(cy + ro);
    if (x0 < 0) x0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (y0 < 0) y0 = 0;
    if (y1 > H - 1) y1 = H - 1;
    for (int y = y0; y <= y1; y++) {
      float dy = y + 0.5f - cy, dy2 = dy * dy;
      uint16_t *row = fb + y * W;
      for (int x = x0; x <= x1; x++) {
        float dx = x + 0.5f - cx, d2 = dx * dx + dy2;
        if (d2 >= ro2 || d2 <= ri2) continue;
        float cov = half - fabsf(sqrtf(d2) - r);
        if (cov > 0) row[x] = blend565(row[x], ci, (int)(ai * (cov > 1 ? 1 : cov)));
      }
    }
  }

  // Ellipse; topOnly cuts it at the centre line (for domes like the chest lid)
  void fillEllipse(float cx, float cy, float rx, float ry, Col c, float a, bool topOnly = false) {
    const C8 ci = toC8(c);
    const int ai = alpha256(a);
    int x0 = ifloor(cx - rx - 1), x1 = iceil(cx + rx + 1);
    int y0 = ifloor(cy - ry - 1), y1 = topOnly ? ifloor(cy) : iceil(cy + ry + 1);
    if (x0 < 0) x0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (y0 < 0) y0 = 0;
    if (y1 > H - 1) y1 = H - 1;
    const float irx = 1.0f / rx, iry = 1.0f / ry;
    const float rmin = rx < ry ? rx : ry;
    const float lim = (1.0f + 0.5f / rmin) * (1.0f + 0.5f / rmin);
    for (int y = y0; y <= y1; y++) {
      float ny = (y + 0.5f - cy) * iry;
      uint16_t *row = fb + y * W;
      for (int x = x0; x <= x1; x++) {
        float nx = (x + 0.5f - cx) * irx;
        float d2 = nx * nx + ny * ny;
        if (d2 >= lim) continue;
        float cov = (1.0f - sqrtf(d2)) * rmin + 0.5f;
        if (cov <= 0) continue;
        int aa = cov >= 1 ? ai : (int)(ai * cov);
        if (aa > 0) row[x] = aa >= 256 ? pack8(ci) : blend565(row[x], ci, aa);
      }
    }
  }

  void fillRect(float x, float y, float w, float h, Col c, float a) {
    const C8 ci = toC8(c);
    const int ai = alpha256(a);
    if (ai <= 0) return;
    int x0 = ifloor(x), x1 = iceil(x + w), y0 = ifloor(y), y1 = iceil(y + h);
    if (x0 < 0) x0 = 0;
    if (x1 > W) x1 = W;
    if (y0 < 0) y0 = 0;
    if (y1 > H) y1 = H;
    for (int yy = y0; yy < y1; yy++) {
      uint16_t *row = fb + yy * W;
      for (int xx = x0; xx < x1; xx++) row[xx] = ai >= 256 ? pack8(ci) : blend565(row[xx], ci, ai);
    }
  }

  void fillTri(float x0, float y0, float x1, float y1, float x2, float y2, Col c, float a) {
    float minx = fminf(x0, fminf(x1, x2)), maxx = fmaxf(x0, fmaxf(x1, x2));
    float miny = fminf(y0, fminf(y1, y2)), maxy = fmaxf(y0, fmaxf(y1, y2));
    float area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (fabsf(area) < 0.01f) return;
    const C8 ci = toC8(c);
    const int ai = alpha256(a);
    float inv = 1.0f / area;
    int ya = ifloor(miny), yb = iceil(maxy), xa = ifloor(minx), xb = iceil(maxx);
    if (ya < 0) ya = 0;
    if (yb > H - 1) yb = H - 1;
    if (xa < 0) xa = 0;
    if (xb > W - 1) xb = W - 1;
    for (int y = ya; y <= yb; y++) {
      float py = y + 0.5f;
      uint16_t *row = fb + y * W;
      for (int x = xa; x <= xb; x++) {
        float px = x + 0.5f;
        float w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) * inv;
        float w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) * inv;
        float w2 = 1.0f - w0 - w1;
        if (w0 >= 0 && w1 >= 0 && w2 >= 0) row[x] = ai >= 256 ? pack8(ci) : blend565(row[x], ci, ai);
      }
    }
  }
};

// ---------------------------------------------------------------------------
//  Fish species
// ---------------------------------------------------------------------------

enum Pattern : uint8_t { P_CLOWN, P_BLUETANG, P_YELLOWTANG, P_NEON, P_ANGEL, P_GOLD };

struct Species {
  Pattern pattern;
  float len, hgt, speed;
  Col fin, tail;
  float finAlpha;
  float tailLen, tailSpread, tailFork;
  float dorsalH, dorsalStart, dorsalEnd, dorsalPeak;
  float analH, analStart, analEnd, analPeak;
};

static const Species SPECIES[] = {
    // pattern       len  hgt  speed  fin               tail               a     tLen  tSpr  fork  dH    dS     dE    dP    aH    aS     aE     aP
    {P_CLOWN, 30, 15, 22, {250, 115, 25}, {250, 115, 25}, 0.92f, 0.40f, 0.55f, 0.0f, 0.38f, -0.55f, 0.30f, 0.55f, 0.28f, -0.55f, -0.05f, 0.5f},
    {P_BLUETANG, 36, 21, 26, {30, 70, 190}, {255, 205, 35}, 0.95f, 0.42f, 0.75f, 0.35f, 0.24f, -0.80f, 0.60f, 0.6f, 0.22f, -0.75f, 0.20f, 0.5f},
    {P_YELLOWTANG, 30, 22, 21, {250, 205, 30}, {250, 205, 30}, 0.95f, 0.36f, 0.70f, 0.0f, 0.36f, -0.75f, 0.45f, 0.6f, 0.34f, -0.70f, 0.25f, 0.5f},
    {P_NEON, 13, 5.5f, 30, {230, 240, 255}, {230, 240, 255}, 0.30f, 0.48f, 0.80f, 0.5f, 0.40f, -0.25f, 0.05f, 0.5f, 0.32f, -0.45f, 0.00f, 0.5f},
    {P_ANGEL, 26, 22, 15, {200, 205, 215}, {200, 205, 215}, 0.65f, 0.50f, 0.90f, 0.0f, 1.20f, -0.55f, 0.25f, 0.18f, 1.15f, -0.60f, 0.15f, 0.18f},
    {P_GOLD, 28, 15, 19, {255, 150, 50}, {255, 150, 50}, 0.70f, 0.90f, 1.10f, 0.6f, 0.45f, -0.50f, 0.30f, 0.6f, 0.25f, -0.55f, -0.10f, 0.5f},
};

struct Fish {
  uint8_t sp;
  float x, y, vx;
  float dir, wantDir;       // facing: +1 right, -1 left, values between = turning
  float targetY, cruise;
  float decide, bubbleT;
  float phase, tailPhase;
  float z;                  // 0 = near, 1 = far (smaller, hazier, drawn first)
  float sizeK;
  bool school;              // neon tetras swim as a group
  float ox, oy;             // place inside the school
};

struct Bubble {
  float x, y, r, phase;
  bool alive;
};

struct Flake {
  float x, y, vy, phase, rest;
  Col c;
  bool alive, landed;
};

struct Plant {
  float x, base, step, w, phase, sway, lean;
  int n;
  Col c0, c1;
  bool front;
};

// ---------------------------------------------------------------------------
//  The aquarium
// ---------------------------------------------------------------------------

class Aquarium {
 public:
  // frame: the buffer shown on screen. bgDay/bgNight: W*H buffers for the still
  // background (bgNight may be null: night is then computed on the fly).
  // dayCache/nightCache (optional, W*H each, need bgNight): background plus
  // light rays, refreshed one slice per frame because the rays move slowly.
  // Saves a lot of time on every frame.
  void begin(uint16_t *frame, uint16_t *bgDay, uint16_t *bgNight, uint32_t seed,
             uint16_t *dayCache = nullptr, uint16_t *nightCache = nullptr) {
    frame_ = frame;
    bgDay_ = bgDay;
    bgNight_ = bgNight;
    cached_ = bgNight && dayCache && nightCache;
    dayCache_ = dayCache;
    nightCache_ = nightCache;
    slice_ = -1;
    rng_ = Rng(seed);
    sandMinY_ = H;
    for (int x = 0; x < W; x++) {
      sandTop_[x] = 147 + 2.5f * sinf(x * 0.043f + 0.5f) + 1.6f * sinf(x * 0.11f + 2.0f);
      sandTopI_[x] = (int16_t)sandTop_[x];
      if (sandTopI_[x] < sandMinY_) sandMinY_ = sandTopI_[x];
    }
    buildBackground();
    makePlants();
    makeFish();
  }

  void feed() {
    if (intro_) return;  // no food while the tank is still filling
    float cx = rng_.range(60, 260);
    int made = 0;
    for (auto &f : flakes_) {
      if (f.alive) continue;
      f.alive = true;
      f.landed = false;
      f.x = cx + rng_.range(-28, 28);
      f.y = rng_.range(2, 7);
      f.vy = rng_.range(9, 15);
      f.phase = rng_.range(0, 6.28f);
      f.rest = 0;
      static const Col FOOD[] = {{240, 120, 40}, {220, 60, 40}, {120, 170, 60}, {245, 190, 70}};
      f.c = FOOD[rng_.next() % 4];
      if (++made >= 9) break;
    }
  }

  void toggleNight() { night_ = !night_; }
  // false = an empty tank (water, plants, bubbles). The fish keep swimming
  // unseen, so they are where they should be when switched back on.
  bool showFish = true;
  bool isNight() const { return night_; }

  // ----- Start-up show: the dim, empty tank fills with water (light comes
  // with it), then the fish swim in from both sides.
  static constexpr float FILL_START = 0.5f, FILL_TIME = 1.2f, FISH_IN = 1.25f, INTRO_END = 2.3f;
  void startIntro() {
    intro_ = true;
    introT_ = 0;
    for (int i = 0; i < fishCount_; i++) {
      Fish &f = fish_[i];
      float a = halfLen(f);
      float side = f.school ? -1.0f : ((i % 2) ? -1.0f : 1.0f);  // -1 = waits on the left
      f.x = side < 0 ? -a : W + a;
      f.dir = f.wantDir = -side;  // facing into the tank
      f.vx = 0;
      if (!f.school) {
        f.cruise = SPECIES[f.sp].speed * 2.2f;  // brisk entrance, calms down at the next decision
        f.decide = rng_.range(1.6f, 2.6f);
      }
    }
    schoolX_ = -20;
    schoolDir_ = 1;
    schoolDecide_ = 4;
  }
  // seconds since power-on (the caller's clock, so the LEDs can follow along)
  void setIntroTime(float t) {
    introT_ = t;
    if (t >= INTRO_END) intro_ = false;
  }
  bool introRunning() const { return intro_; }
  // water level during the fill: 0 = empty, 1 = full
  float introFill() const {
    float p = clampf((introT_ - FILL_START) / FILL_TIME, 0, 1);
    return p * p * (3 - 2 * p);  // smooth start and stop
  }

  void update(float dt) {
    if (dt > 0.05f) dt = 0.05f;
    t_ += dt;
    if (t_ > 7200) t_ -= 7200;  // keep float precision when running for hours
    light_ += clampf((night_ ? 0.0f : 1.0f) - light_, -dt / 1.5f, dt / 1.5f);
    for (int y = 0; y < H; y++) waterRow_[y] = lit(waterColor(y));
    if (!intro_ || introT_ >= FISH_IN + 0.45f) updateSchool(dt);
    for (int i = 0; i < fishCount_; i++) {
      // start-up: big fish come in one after another, the little school together
      float release = FISH_IN + (fish_[i].school ? 0.45f : 0.18f * i);
      if (intro_ && introT_ < release) continue;
      updateFish(fish_[i], dt);
    }
    if (intro_) introBubbles(dt);
    updateBubbles(dt);
    updateFlakes(dt);
    updateChest(dt);
  }

  void render() {
    if (cached_) {
      refreshCaches();
      composeCaches();
    } else {
      drawBackground(0, H);
      drawRays(0, H, light_);
    }
    drawCaustics();
    for (int i = 0; i < plantCount_; i++)
      if (!plants_[i].front) drawPlant(plants_[i]);
    drawChest();
    // far fish first
    int order[MAX_FISH];
    for (int i = 0; i < fishCount_; i++) order[i] = i;
    for (int i = 1; i < fishCount_; i++)
      for (int j = i; j > 0 && fish_[order[j]].z > fish_[order[j - 1]].z; j--) {
        int tmp = order[j];
        order[j] = order[j - 1];
        order[j - 1] = tmp;
      }
    if (showFish)
      for (int i = 0; i < fishCount_; i++) drawFish(fish_[order[i]]);
    drawFlakes();
    drawBubbles();
    for (int i = 0; i < plantCount_; i++)
      if (plants_[i].front) drawPlant(plants_[i]);
    drawSurface();
    if (intro_) drawIntroWater();
  }

 private:
  static constexpr int MAX_FISH = 14, MAX_BUBBLES = 56, MAX_FLAKES = 24, MAX_PLANTS = 7;

  Canvas cv_;
  uint16_t *frame_ = nullptr, *bgDay_ = nullptr, *bgNight_ = nullptr;
  uint16_t *dayCache_ = nullptr, *nightCache_ = nullptr;
  bool cached_ = false;
  int slice_ = -1;
  Rng rng_;
  SinTable sn_;
  float t_ = 0, light_ = 1;
  bool intro_ = false;
  float introT_ = 0, introBubbleT_ = 0;
  bool night_ = false;
  float sandTop_[W];
  int16_t sandTopI_[W];
  int sandMinY_ = 0;
  Col waterRow_[H];

  Fish fish_[MAX_FISH];
  int fishCount_ = 0;
  Bubble bubbles_[MAX_BUBBLES] = {};
  Flake flakes_[MAX_FLAKES] = {};
  Plant plants_[MAX_PLANTS];
  int plantCount_ = 0;

  float airT_ = 0;
  float chestT_ = 4, chestOpen_ = 0;
  bool chestBurst_ = false;
  float schoolX_ = 160, schoolY_ = 70, schoolDir_ = 1, schoolTargetY_ = 70, schoolDecide_ = 3;

  static constexpr float CHEST_X = 238;
  static constexpr float STONE_X = 293;

  // ----- colours and light ------------------------------------------------

  Col waterColor(int y) const {
    float t = (float)y / (H - 1);
    const Col top = {50, 150, 205}, mid = {20, 98, 162}, bot = {8, 48, 98};
    return t < 0.45f ? mix(top, mid, t / 0.45f) : mix(mid, bot, (t - 0.45f) / 0.55f);
  }
  static Col nightOf(Col c) { return {c.r * 0.30f, c.g * 0.38f, c.b * 0.56f + 6}; }
  Col lit(Col c) const { return light_ >= 0.999f ? c : mix(nightOf(c), c, light_); }

  // ----- background (drawn once into bgDay, converted for bgNight) ---------

  void buildBackground() {
    cv_.fb = bgDay_;
    // water
    for (int y = 0; y < H; y++) {
      uint16_t c = pack(waterColor(y));
      for (int x = 0; x < W; x++) bgDay_[y * W + x] = c;
    }
    // distant hills
    for (int x = 0; x < W; x++) {
      float top = 124 + 7 * sinf(x * 0.021f + 1.3f) + 4 * sinf(x * 0.057f);
      for (int y = (int)top; y < H; y++) {
        Col c = scale(waterColor(y), 0.72f);
        c.b += 6;
        cv_.blend(x, y, c, clampf(top + 1 - y + 1, 0, 1) < 1 ? 0.5f : 0.85f);
      }
    }
    // far plants (dark, static)
    for (int k = 0; k < 9; k++) {
      float bx = rng_.range(5, W - 5), hgt = rng_.range(18, 38), lean = rng_.range(-0.25f, 0.25f);
      float x = bx, y = 140;
      for (int i = 0; i < (int)hgt; i++) {
        float f = (float)i / hgt;
        x += lean * 0.6f + 0.35f * sinf(f * 5 + k);
        y -= 1;
        cv_.fillCircle(x, y, 1.6f * (1 - 0.6f * f), {20, 80, 70}, 0.55f);
      }
    }
    // sand
    for (int x = 0; x < W; x++) {
      int top = (int)sandTop_[x];
      for (int y = top; y < H; y++) {
        float t = (float)(y - top) / (H - top + 1);
        Col c = mix({228, 204, 152}, {178, 148, 102}, t);
        float n = rng_.range(-11, 11);
        c = {c.r + n, c.g + n, c.b + n * 0.8f};
        if (y == top) c = mix(c, waterColor(y), 0.35f);
        cv_.put(x, y, c);
      }
    }
    // rocks
    drawRock(46, 150, 31, 19, 1);
    drawRock(74, 152, 15, 9, 2);
    drawRock(172, 154, 17, 9, 3);
    drawRock(STONE_X, sandTop_[(int)STONE_X] + 2, 6, 4, 4);  // air stone
    // pebbles
    static const Col PEB[] = {{150, 140, 130}, {118, 100, 88}, {182, 172, 152}, {196, 122, 92}, {92, 92, 98}, {210, 205, 195}};
    for (int i = 0; i < 38; i++) {
      float x = rng_.range(2, W - 2);
      float y = rng_.range(sandTop_[(int)x] + 3, H - 1);
      float rx = rng_.range(1.2f, 2.7f), ry = rx * rng_.range(0.6f, 0.85f);
      Col c = PEB[rng_.next() % 6];
      cv_.fillEllipse(x + 0.6f, y + 0.8f, rx, ry, {90, 70, 50}, 0.35f);  // shadow
      cv_.fillEllipse(x, y, rx, ry, c, 1.0f);
      cv_.blend((int)(x - rx * 0.3f), (int)(y - ry * 0.4f), {255, 255, 255}, 0.45f);
    }
    if (bgNight_)
      for (int i = 0; i < W * H; i++) bgNight_[i] = pack(nightOf(unpack(bgDay_[i])));
    cv_.fb = frame_;
  }

  void drawRock(float cx, float cy, float rx, float ry, int seed) {
    Rng r(seed * 7919 + 13);
    const Col base = seed == 4 ? Col{120, 120, 125} : Col{112, 106, 100};
    for (int y = (int)(cy - ry - 1); y <= (int)(cy + ry * 0.55f); y++) {
      for (int x = (int)(cx - rx - 1); x <= (int)(cx + rx + 1); x++) {
        float nx = (x + 0.5f - cx) / rx, ny = (y + 0.5f - cy) / ry;
        float d = nx * nx + ny * ny;
        if (d > 1.0f) continue;
        float shade = clampf(0.72f + 0.42f * (-0.55f * nx - 0.85f * ny) - 0.18f * d, 0.35f, 1.25f);
        Col c = scale(base, shade);
        float n = r.range(-9, 9);
        c = {c.r + n, c.g + n, c.b + n};
        if (ny < -0.35f && seed != 4 && r.uni() < 0.35f) c = mix(c, {70, 130, 60}, 0.5f);  // moss
        float edge = clampf((1.0f - sqrtf(d)) * fminf(rx, ry) + 0.5f, 0, 1);
        cv_.blend(x, y, c, edge);
      }
    }
  }

  // Day picture (background + sun rays) and night picture (background + moon
  // ray). One slice of rows of each is redrawn per frame, so each slice is
  // fresh every 8 frames - the rays move far too slowly for anyone to notice.
  void refreshCaches() {
    const int SLICES = 8;
    int y0 = 0, y1 = H;  // first frame: everything
    if (slice_ >= 0) {
      y0 = slice_ * H / SLICES;
      y1 = (slice_ + 1) * H / SLICES;
    }
    slice_ = (slice_ + 1) % SLICES;
    const int i0 = y0 * W, n = (y1 - y0) * W;
    memcpy(dayCache_ + i0, bgDay_ + i0, n * 2);
    memcpy(nightCache_ + i0, bgNight_ + i0, n * 2);
    cv_.fb = dayCache_;
    drawRays(y0, y1, 1.0f);
    cv_.fb = nightCache_;
    drawRays(y0, y1, 0.0f);
    cv_.fb = frame_;
  }

  // the frame starts as the day picture, the night picture or a mix of both
  void composeCaches() {
    uint16_t *fb = cv_.fb;
    if (light_ >= 0.999f) {
      memcpy(fb, dayCache_, W * H * 2);
    } else if (light_ <= 0.001f) {
      memcpy(fb, nightCache_, W * H * 2);
    } else {
      const uint32_t k = (uint32_t)(light_ * 32 + 0.5f);  // 0..32
      for (int i = 0; i < W * H; i++) {
        uint32_t d = dayCache_[i], m = nightCache_[i];
        d = (d | (d << 16)) & 0x07E0F81F;
        m = (m | (m << 16)) & 0x07E0F81F;
        uint32_t r = ((((d - m) * k) >> 5) + m) & 0x07E0F81F;
        fb[i] = (uint16_t)((r >> 16) | r);
      }
    }
  }

  // rows y0..y1-1 of the still background, day or night or in between
  void drawBackground(int y0, int y1) {
    const int i0 = y0 * W, i1 = y1 * W;
    uint16_t *fb = cv_.fb;
    if (light_ >= 0.999f) {
      memcpy(fb + i0, bgDay_ + i0, (i1 - i0) * 2);
    } else if (bgNight_ && light_ <= 0.001f) {
      memcpy(fb + i0, bgNight_ + i0, (i1 - i0) * 2);
    } else if (bgNight_) {  // day <-> night fade
      const int k = alpha256(light_);
      for (int i = i0; i < i1; i++) {
        uint16_t d = bgDay_[i];
        int r = (d >> 8) & 0xF8, g = (d >> 3) & 0xFC, b = (d << 3) & 0xF8;
        C8 day = {r | (r >> 5), g | (g >> 6), b | (b >> 5)};
        fb[i] = blend565(bgNight_[i], day, k);
      }
    } else {  // no night buffer: darken on the fly
      const int k = alpha256(light_);
      for (int i = i0; i < i1; i++) {
        uint16_t d = bgDay_[i];
        int r = (d >> 8) & 0xF8, g = (d >> 3) & 0xFC, b = (d << 3) & 0xF8;
        r |= r >> 5;
        g |= g >> 6;
        b |= b >> 5;
        int nr = (r * 77) >> 8, ng = (g * 97) >> 8, nb = ((b * 143) >> 8) + 6;
        fb[i] = pack8(nr + (((r - nr) * k) >> 8), ng + (((g - ng) * k) >> 8), clampi(nb + (((b - nb) * k) >> 8), 0, 255));
      }
    }
  }

  // moving light patterns on the sand
  void drawCaustics() {
    if (light_ < 0.05f) return;
    const float k = 42 * light_;
    for (int y = sandMinY_ + 1; y < H; y++) {
      const float inner = t_ * 1.2f + sn_.sin(y * 0.35f + t_ * 0.8f) * 1.5f;
      const float b0 = -y * (1.7f * 0.09f) - t_ * 0.9f;
      uint16_t *row = cv_.fb + y * W;
      for (int x = 0; x < W; x++) {
        if (y <= sandTopI_[x]) continue;
        float v = sn_.sin(x * 0.11f + inner) + sn_.sin(x * 0.09f + b0);
        if (v > 1.15f) {
          int amount = (int)((v - 1.15f) * k + 0.5f);
          if (amount > 0) Canvas::addI(row[x], amount);
        }
      }
    }
  }

  // light: 1 = day (sun rays), 0 = night (moon ray), in between = some of both
  void drawRays(int y0, int y1, float light) {
    struct Ray {
      float x, wTop, wBot, phase;
    };
    static const Ray RAYS[] = {{30, 9, 28, 0}, {118, 14, 38, 1.7f}, {200, 8, 24, 3.1f}, {262, 12, 34, 4.4f}};
    const float slant = 0.42f;
    if (light > 0.02f) {
      for (const Ray &r : RAYS) {
        float a = light * 0.11f * (0.55f + 0.45f * sn_.sin(t_ * 0.5f + r.phase));
        float x0 = r.x + 8 * sn_.sin(t_ * 0.21f + r.phase);
        drawRay(x0, slant, r.wTop, r.wBot, {205, 238, 255}, a, y0, y1);
      }
    }
    if (light < 0.98f) drawRay(150 + 6 * sn_.sin(t_ * 0.15f), 0.18f, 10, 40, {150, 180, 255}, (1 - light) * 0.07f, y0, y1);
  }

  void drawRay(float x0, float slant, float wTop, float wBot, Col c, float a, int yFrom, int yTo) {
    const C8 ci = toC8(c);
    if (yTo > 150) yTo = 150;
    for (int y = yFrom; y < yTo; y++) {
      float t = (float)y / 150;
      float cx = x0 + slant * y, hw = lerpf(wTop, wBot, t) * 0.5f;
      float ay = a * (1 - 0.75f * t) * 256.0f;  // opacity in the middle of the beam
      float k = ay / hw;                         // ... fading to 0 at the edges
      int xa = (int)(cx - hw), xb = (int)(cx + hw);
      if (xa < 0) xa = 0;
      if (xb > W - 1) xb = W - 1;
      uint16_t *row = cv_.fb + y * W;
      for (int x = xa; x <= xb; x++) {
        int aa = (int)(ay - fabsf(x + 0.5f - cx) * k);
        if (aa > 0) row[x] = blend565(row[x], ci, aa);
      }
    }
  }

  void drawSurface() {
    const float a = 0.30f + 0.25f * light_;
    const C8 water = toC8(lit({175, 228, 250})), edge = toC8(lit({235, 250, 255}));
    const int aw = alpha256(a), ae = alpha256(a + 0.25f);
    for (int x = 0; x < W; x++) {
      float sy = 4 + 1.2f * sn_.sin(x * 0.06f + t_ * 1.8f) + 0.8f * sn_.sin(x * 0.15f - t_ * 1.1f);
      int iy = (int)sy;
      for (int y = 0; y < iy; y++) cv_.blendI(x, y, water, aw);
      cv_.blendI(x, iy, edge, ae);
    }
  }

  // ----- plants ---------------------------------------------------------------

  void makePlants() {
    const float xs[] = {14, 98, 140, 206, 268, 120, 306};
    const bool front[] = {false, false, false, false, false, true, true};
    for (int i = 0; i < MAX_PLANTS; i++) {
      Plant &p = plants_[i];
      p.x = xs[i];
      p.base = sandTop_[(int)p.x] + 2;
      p.front = front[i];
      p.n = (int)rng_.range(front[i] ? 34 : 42, front[i] ? 46 : 62);
      p.step = 2.0f;
      p.w = front[i] ? 3.0f : rng_.range(2.0f, 2.8f);
      p.phase = rng_.range(0, 6.28f);
      p.sway = rng_.range(0.35f, 0.6f);
      p.lean = rng_.range(-0.12f, 0.12f);
      p.c0 = front[i] ? Col{30, 110, 45} : Col{25, 95, 55};
      p.c1 = front[i] ? Col{110, 200, 80} : Col{80, 170, 90};
    }
    plantCount_ = MAX_PLANTS;
  }

  // A plant is a swaying centre line with a tapering width. The stem is filled
  // row by row (one span per row), leaves first so the stem covers their roots.
  static constexpr int MAX_SEG = 64;
  void drawPlant(const Plant &p) {
    float px[MAX_SEG], py[MAX_SEG], pr[MAX_SEG];
    C8 pc[MAX_SEG];
    const int n = p.n < MAX_SEG ? p.n : MAX_SEG;
    float x = p.x, y = p.base;
    for (int i = 0; i < n; i++) {
      float f = (float)i / p.n;
      float ang = -PI_F / 2 + p.lean + p.sway * f * sn_.sin(t_ * 0.8f + p.phase - i * 0.16f);
      x += sn_.cos(ang) * p.step;
      y += sn_.sin(ang) * p.step;
      Col c = lit(mix(p.c0, p.c1, f));
      px[i] = x;
      py[i] = y;
      pr[i] = p.w * (1 - 0.55f * f);
      pc[i] = toC8(c);
      if (i > 6 && i % 7 == 3) {  // leaves, alternating sides
        float side = (i / 7) % 2 ? 1.0f : -1.0f;
        float lx = x + side * (6.5f + 2 * f), ly = y - 5;
        cv_.fillTri(x, y + 1.5f, x, y - 2.5f, lx, ly, mix(c, {150, 220, 110}, 0.25f), 0.95f);
      }
    }
    // round ends
    cv_.fillCircle(px[0], py[0], pr[0], {(float)pc[0].r, (float)pc[0].g, (float)pc[0].b}, 1.0f);
    cv_.fillCircle(px[n - 1], py[n - 1], pr[n - 1], {(float)pc[n - 1].r, (float)pc[n - 1].g, (float)pc[n - 1].b}, 1.0f);
    // stem, row by row from the bottom up (y gets smaller along the plant)
    int j = 0;
    for (int row = ifloor(py[0] - 0.5f); row >= 0 && row + 0.5f >= py[n - 1]; row--) {
      const float yc = row + 0.5f;
      if (row >= H || yc > py[0]) continue;
      while (j < n - 2 && py[j + 1] > yc) j++;
      const float dy = py[j] - py[j + 1];
      const float t = dy > 0.001f ? (py[j] - yc) / dy : 0;
      const float s = dy > 0.001f ? (px[j + 1] - px[j]) / dy : 0;
      const float xc = px[j] + (px[j + 1] - px[j]) * t;
      const float hw = (pr[j] + (pr[j + 1] - pr[j]) * t) * sqrtf(1 + s * s);
      cv_.span(row, xc - hw, xc + hw, t < 0.5f ? pc[j] : pc[j + 1]);
    }
  }

  // ----- fish -----------------------------------------------------------------

  void makeFish() {
    const uint8_t big[] = {0, 0, 1, 2, 4, 5};
    const float zs[] = {0.1f, 0.6f, 0.2f, 0.45f, 0.75f, 0.3f};
    for (int i = 0; i < 6; i++) addFish(big[i], zs[i], false, 0, 0);
    const float off[][2] = {{0, 0}, {-11, -6}, {-12, 5}, {-23, -1}, {8, 7}, {-22, 9}, {7, -7}};
    for (auto &o : off) addFish(3, 0.4f, true, o[0], o[1]);
  }

  void addFish(uint8_t sp, float z, bool school, float ox, float oy) {
    if (fishCount_ >= MAX_FISH) return;
    Fish &f = fish_[fishCount_++];
    f.sp = sp;
    f.z = z;
    f.sizeK = (1.0f - 0.35f * z) * rng_.range(0.9f, 1.1f);
    f.x = school ? schoolX_ + ox : rng_.range(40, W - 40);
    f.y = school ? schoolY_ + oy : rng_.range(30, 120);
    f.dir = f.wantDir = rng_.uni() < 0.5f ? -1.0f : 1.0f;
    f.cruise = SPECIES[sp].speed * rng_.range(0.7f, 1.2f);
    f.vx = f.dir * f.cruise;
    f.targetY = f.y;
    f.decide = rng_.range(1, 5);
    f.bubbleT = rng_.range(4, 14);
    f.phase = rng_.range(0, 6.28f);
    f.tailPhase = rng_.range(0, 6.28f);
    f.school = school;
    f.ox = ox;
    f.oy = oy;
  }

  float halfLen(const Fish &f) const { return SPECIES[f.sp].len * 0.5f * f.sizeK; }
  float halfHgt(const Fish &f) const { return SPECIES[f.sp].hgt * 0.5f * f.sizeK; }

  Flake *nearestFlake(float x, float y, float maxD) {
    Flake *best = nullptr;
    float bd = maxD * maxD;
    for (auto &fl : flakes_) {
      if (!fl.alive) continue;
      float d = (fl.x - x) * (fl.x - x) + (fl.y - y) * (fl.y - y) * 2;
      if (d < bd) {
        bd = d;
        best = &fl;
      }
    }
    return best;
  }

  void updateSchool(float dt) {
    schoolDecide_ -= dt;
    if (schoolDecide_ <= 0) {
      schoolDecide_ = rng_.range(3, 7);
      schoolTargetY_ = rng_.range(30, 115);
      if (rng_.uni() < 0.2f) schoolDir_ = -schoolDir_;
    }
    if (schoolX_ > W - 50 && schoolDir_ > 0) schoolDir_ = -1;
    if (schoolX_ < 50 && schoolDir_ < 0) schoolDir_ = 1;
    schoolX_ += schoolDir_ * 24 * dt;
    schoolY_ += (schoolTargetY_ - schoolY_) * fminf(1, dt * 0.6f);
  }

  void updateFish(Fish &f, float dt) {
    const Species &s = SPECIES[f.sp];
    float a = halfLen(f), b = halfHgt(f);
    float speed = f.cruise * (1 - 0.3f * f.z);
    Flake *food = nearestFlake(f.x, f.y, 220);
    float sgn = f.dir >= 0 ? 1.0f : -1.0f;

    float yMax = 138 - b * 1.4f;
    if (food) {
      f.wantDir = food->x > f.x ? 1.0f : -1.0f;
      f.targetY = food->y;
      yMax = food->y;  // may dive down to the sand for food lying there
      speed = s.speed * 1.9f;
      float nx = f.x + sgn * a * 0.95f;
      if (fabsf(nx - food->x) < 3 + b * 0.4f && fabsf(f.y - food->y) < 2.5f + b) food->alive = false;
    } else if (f.school) {
      float tx = schoolX_ + f.ox * schoolDir_, ty = schoolY_ + f.oy;
      f.wantDir = schoolDir_;
      f.targetY = ty;
      speed = 24 + clampf((tx - f.x) * schoolDir_, -12, 18);
      if ((tx - f.x) * schoolDir_ < -25) f.wantDir = -schoolDir_;  // overshot: come back
    } else {
      f.decide -= dt;
      if (f.decide <= 0) {
        f.decide = rng_.range(2.5f, 7);
        f.targetY = rng_.range(16 + b * 1.6f, 136 - b * 1.6f);
        f.cruise = s.speed * rng_.range(0.6f, 1.3f);
        if (rng_.uni() < 0.22f) f.wantDir = -f.wantDir;
      }
      float margin = a * 0.9f + 6;
      if (f.x > W - margin && f.wantDir > 0) f.wantDir = -1;
      if (f.x < margin && f.wantDir < 0) f.wantDir = 1;
    }

    f.dir += clampf(f.wantDir - f.dir, -dt * 3.2f, dt * 3.2f);
    float facing = f.dir >= 0 ? 1.0f : -1.0f;
    float vTarget = facing * speed * clampf(fabsf(f.dir), 0.15f, 1.0f);
    f.vx += (vTarget - f.vx) * fminf(1, dt * 2.2f);
    f.x += f.vx * dt;
    f.x = clampf(f.x, -a, W + a);
    f.targetY = clampf(f.targetY, 14 + b * 1.4f, fmaxf(yMax, 14 + b * 1.4f));
    f.y += (f.targetY - f.y) * fminf(1, dt * (food ? 2.0f : 0.8f));
    f.tailPhase += dt * (5 + fabsf(f.vx) * 0.32f);

    f.bubbleT -= dt;
    if (f.bubbleT <= 0) {
      f.bubbleT = rng_.range(6, 16);
      if (!f.school) spawnBubble(f.x + facing * a, f.y - b * 0.1f, rng_.range(0.9f, 1.4f));
    }
  }

  // Everything about one pixel column of a fish that does not change from row to row.
  // Worked out once per column, so the per-pixel loop stays cheap.
  struct FishCol {
    float u;                 // position along the body: +1 nose, -1 tail root
    float ext;               // nothing is drawn where |v| >= ext (quick skip)
    bool tail;
    float st, tailHalf, notch, tailA;  // tail fin
    Col tailC;
    float hb, fhUp, fhDn;    // back and belly fins
    float hu, invHu;         // body half-height (hu <= 0: no body in this column)
    float shineX, finX;      // highlight and side fin, horizontal part
    float band, eyeU;        // blue tang stripe, yellow tang spot
    Col base;                // body colour where the pattern only depends on u
  };
  static constexpr int MAX_COLS = 128;
  FishCol cols_[MAX_COLS];

  void columnPattern(const Species &s, FishCol &k) const {
    const float u = k.u;
    k.band = 99;
    k.eyeU = 99;
    switch (s.pattern) {
      case P_CLOWN: {
        const float cs[3] = {0.42f, -0.12f, -0.70f}, ws[3] = {0.08f, 0.10f, 0.07f};
        k.base = {252, 112, 22};
        for (int i = 0; i < 3; i++) {
          float d = fabsf(u - cs[i]);
          if (d < ws[i]) {
            k.base = {250, 250, 250};
            break;
          }
          if (d < ws[i] + 0.045f) {
            k.base = {25, 18, 22};
            break;
          }
        }
        break;
      }
      case P_BLUETANG:
        k.base = {32, 92, 220};
        if (u > -0.75f && u < 0.55f) k.band = -0.18f + 0.35f * sn_.sin((u + 0.25f) * 3.3f);
        break;
      case P_YELLOWTANG:
        k.base = {255, 214, 38};
        k.eyeU = (u + 0.84f) * (u + 0.84f);
        break;
      case P_ANGEL: {
        const float cs[3] = {0.38f, -0.12f, -0.60f}, ws[3] = {0.07f, 0.09f, 0.06f};
        k.base = {206, 211, 218};
        for (int i = 0; i < 3; i++)
          if (fabsf(u - cs[i]) < ws[i]) k.base = {48, 48, 58};
        break;
      }
      case P_NEON:
      case P_GOLD:
      default:
        k.base = {255, 142, 28};
        break;
    }
  }

  Col bodyPattern(const Species &s, const FishCol &k, float vn, bool &glow) const {
    glow = false;
    switch (s.pattern) {
      case P_BLUETANG:
        if (vn < 0.45f && fabsf(vn - k.band) < 0.2f) return {12, 16, 45};
        return k.base;
      case P_YELLOWTANG:
        if (k.eyeU + vn * vn * 0.02f < 0.004f) return {250, 250, 245};
        return k.base;
      case P_NEON:
        if (fabsf(vn) < 0.30f && k.u > -0.85f && k.u < 0.75f) {
          glow = true;
          return {35, 225, 255};
        }
        if (vn > 0.30f && k.u < 0.12f) return {228, 36, 48};
        if (vn < 0) return {125, 138, 150};
        return {218, 222, 228};
      default:
        return k.base;
    }
  }

  static float bodyHalf(float u) {
    if (u <= -1.0f || u >= 1.0f) return 0;
    float h = sqrtf(1 - u * u);
    if (u > 0) h *= 1 - 0.22f * u * u;
    if (u < -0.5f) h *= 1 - 0.76f * (-u - 0.5f);
    return h;
  }

  static float finProfile(float u, float s, float e, float peak) {
    if (u < s || u > e) return 0;
    float t = (u - s) / (e - s);
    return t < peak ? t / peak : (1 - t) / (1 - peak);
  }

  void drawFish(const Fish &f) {
    const Species &s = SPECIES[f.sp];
    const float a = halfLen(f), b = halfHgt(f);
    const float sgn = f.dir >= 0 ? 1.0f : -1.0f;
    const float ad = fmaxf(fabsf(f.dir), 0.12f);
    const float ax = a * ad;  // half-length on screen (short while turning)
    const float fy = f.y + 1.3f * sn_.sin(t_ * 1.6f + f.phase);
    const float wag = 0.32f * sn_.sin(f.tailPhase);
    const float flap = 0.75f + 0.25f * sn_.sin(t_ * 9 + f.phase);
    const float haze = f.z * 0.38f;
    const float reach = 1.0f + s.tailLen;
    const float vExt = 1.0f + fmaxf(fmaxf(s.dorsalH, s.analH), s.tailSpread);
    int x0 = ifloor(f.x - ax * reach - 2), x1 = iceil(f.x + ax * reach + 2);
    int y0 = ifloor(fy - b * vExt - 2), y1 = iceil(fy + b * vExt + 2);
    if (x0 < 0) x0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (x1 - x0 + 1 > MAX_COLS) x1 = x0 + MAX_COLS - 1;
    if (y0 < 0) y0 = 0;
    if (y1 > H - 1) y1 = H - 1;

    const Col finC = lit(s.fin), tailC = lit(s.tail);
    const Col finUp = scale(finC, 0.9f), finDn = scale(finC, 0.85f);
    const float invAx = sgn / ax, invB = 1.0f / b, edge = 0.5f * invB;
    const float invTail = 1.0f / s.tailLen, flapK = 1.0f / (0.17f * flap);
    const float tailEnd = -0.82f - s.tailLen;

    // 1) per column
    for (int px = x0; px <= x1; px++) {
      FishCol &k = cols_[px - x0];
      const float u = (px + 0.5f - f.x) * invAx;
      k.u = u;
      k.tail = u < -0.82f && u > tailEnd;
      float ext = 0;
      if (k.tail) {
        k.st = (-0.82f - u) * invTail;
        k.tailHalf = 0.16f + k.st * s.tailSpread;
        k.notch = (s.tailFork > 0 && k.st > 1 - s.tailFork) ? (k.st - (1 - s.tailFork)) / s.tailFork * k.tailHalf * 0.85f : -1;
        k.tailA = s.finAlpha * (1 - 0.3f * k.st);
        k.tailC = scale(tailC, 0.85f + 0.15f * (1 - k.st));
        ext = fabsf(wag * k.st) + k.tailHalf + edge;
      } else {
        k.hb = bodyHalf(clampf(u, -0.99f, 0.99f));
        k.fhUp = s.dorsalH * finProfile(u, s.dorsalStart, s.dorsalEnd, s.dorsalPeak);
        k.fhDn = s.analH * finProfile(u, s.analStart, s.analEnd, s.analPeak);
        float fh = fmaxf(k.fhUp, k.fhDn);
        if (fh > 0) ext = k.hb + fh + edge;
      }
      k.hu = bodyHalf(u);
      if (k.hu > 0) {
        ext = fmaxf(ext, k.hu + edge);
        k.invHu = 1.0f / fmaxf(k.hu, 0.05f);
        float hx = (u - 0.32f) * (1.0f / 0.22f);
        k.shineX = 1 - hx * hx;
        float pu = (u - 0.16f) * flapK;
        k.finX = pu * pu;
        columnPattern(s, k);
      }
      k.ext = ext;
    }

    // 2) per pixel: fins and tail first, so the body covers their roots without seams
    const Col belly = {255, 248, 232}, shineC = {255, 255, 255};
    for (int py = y0; py <= y1; py++) {
      const float v = (py + 0.5f - fy) * invB;
      const float av = fabsf(v);
      const bool up = v < 0;
      const Col water = waterRow_[py];
      const C8 finRow = toC8(haze > 0 ? mix(up ? finUp : finDn, water, haze) : (up ? finUp : finDn));
      uint16_t *row = cv_.fb + py * W;
      for (int px = x0; px <= x1; px++) {
        const FishCol &k = cols_[px - x0];
        if (av >= k.ext) continue;
        uint16_t &p = row[px];

        if (k.tail) {
          float vv = fabsf(v - wag * k.st);
          float cov = clampf(fminf(k.tailHalf - vv, k.notch < 0 ? 9.0f : vv - k.notch) * b + 0.5f, 0, 1);
          if (cov > 0) {
            Col c = haze > 0 ? mix(k.tailC, water, haze) : k.tailC;
            int aa = alpha256(cov * k.tailA);
            if (aa > 0) p = aa >= 256 ? pack(c) : blend565(p, toC8(c), aa);
          }
        } else {
          float fh = up ? k.fhUp : k.fhDn;
          float d = av - k.hb;
          if (fh > 0 && d > -0.15f) {
            float cov = clampf((fh - d) * b + 0.5f, 0, 1);
            int aa = alpha256(cov * s.finAlpha);
            if (aa > 0) p = aa >= 256 ? pack8(finRow) : blend565(p, finRow, aa);
          }
        }

        // body
        if (k.hu <= 0) continue;
        float inside = (k.hu - av) * b;
        float cov = inside + 0.5f;
        if (cov <= 0) continue;
        float vn = v * k.invHu;
        bool glow;
        Col c = bodyPattern(s, k, vn, glow);
        float kk = 1 - 0.30f * clampf(-vn, 0, 1);                       // darker back
        kk *= 1 - 0.28f * clampf(1 - inside * (1.0f / 1.7f), 0, 1);     // darker outline
        c = scale(c, kk);
        if (vn > 0.2f && s.pattern != P_NEON) c = mix(c, belly, 0.4375f * (vn - 0.2f));  // pale belly
        if (k.shineX > 0) {
          float hv = (vn + 0.55f) * (1.0f / 0.3f);
          float hl = k.shineX - hv * hv;
          if (hl > 0) c = mix(c, shineC, 0.35f * hl);  // shine
        }
        float pv = (vn - 0.22f) * (1.0f / 0.24f);
        if (k.finX + pv * pv < 1) c = mix(c, s.fin, 0.45f);  // flapping side fin
        c = glow ? mix(c, lit(c), 0.25f) : lit(c);         // neon stripe keeps glowing at night
        if (haze > 0) c = mix(c, water, haze);
        int aa = alpha256(cov);
        p = aa >= 256 ? pack(c) : blend565(p, toC8(c), aa);
      }
    }
    // eye
    if (fabsf(f.dir) > 0.3f) {
      float ex = f.x + sgn * 0.6f * ax, ey = fy - 0.22f * b;
      float re = fmaxf(1.1f, b * 0.25f);
      Col white = lit({245, 245, 240});
      if (haze > 0) white = mix(white, waterRow_[(int)clampf(ey, 0, H - 1)], haze);
      cv_.fillCircle(ex, ey, re, white, 1.0f);
      cv_.fillCircle(ex + sgn * re * 0.25f, ey, re * 0.6f, {10, 10, 15}, 1.0f);
      if (re > 1.6f) cv_.blend((int)(ex + sgn * re * 0.1f), (int)(ey - re * 0.35f), {255, 255, 255}, 0.9f);
    }
  }

  // ----- bubbles, food, chest ------------------------------------------------

  void spawnBubble(float x, float y, float r) {
    for (auto &b : bubbles_) {
      if (b.alive) continue;
      b = {x, y, r, rng_.range(0, 6.28f), true};
      return;
    }
  }

  void updateBubbles(float dt) {
    airT_ -= dt;
    if (airT_ <= 0) {
      airT_ = rng_.range(0.10f, 0.32f);
      spawnBubble(STONE_X + rng_.range(-2, 2), sandTop_[(int)STONE_X] - 2, rng_.range(1.0f, 2.4f));
    }
    for (auto &b : bubbles_) {
      if (!b.alive) continue;
      b.y -= (16 + b.r * 9) * dt;
      b.x += sn_.sin(t_ * 3.2f + b.phase) * 9 * dt;
      b.r += 0.12f * dt;
      if (b.y < 5) b.alive = false;
    }
  }

  // bubbles stirred up by the inflowing water
  void introBubbles(float dt) {
    float fill = introFill();
    if (fill <= 0 || fill >= 1) return;
    introBubbleT_ -= dt;
    while (introBubbleT_ <= 0) {
      introBubbleT_ += 0.018f;
      float level = H - fill * H;
      float x = rng_.range(6, W - 6);
      float y = rng_.range(fmaxf(level + 6, 10), sandTop_[(int)x] - 2);
      spawnBubble(x, y, rng_.range(0.8f, 2.2f));
    }
  }

  // Above the rising water: the tank still dry and unlit (quarter brightness),
  // with a bright, wavy waterline.
  void drawIntroWater() {
    float fill = introFill();
    if (fill >= 1) return;
    const float level = (H + 8) - fill * (H + 16);  // from just below the bottom to just above the top
    const C8 foam = {225, 242, 255};
    uint16_t *fb = cv_.fb;
    const float waves = 1 - 0.6f * fill;  // calmer as it fills up
    for (int x = 0; x < W; x++) {
      float sy = level + waves * (2.2f * sn_.sin(x * 0.045f + t_ * 3.1f) + 1.3f * sn_.sin(x * 0.12f - t_ * 2.3f));
      int iy = ifloor(sy);
      int top = iy < H ? iy : H;
      for (int y = 0; y < top; y++) {
        uint16_t &p = fb[y * W + x];
        p = (p >> 2) & 0x39E7;  // quarter brightness
      }
      if (iy >= 0 && iy < H) {  // the row the waterline crosses
        uint16_t &p = fb[iy * W + x];
        float above = sy - iy;
        uint16_t dim = (p >> 2) & 0x39E7;
        int r = (dim >> 8) & 0xF8, g = (dim >> 3) & 0xFC, b = (dim << 3) & 0xF8;
        p = blend565(p, {r, g, b}, (int)(above * 256));
        p = blend565(p, foam, 150);
      }
      if (iy + 1 >= 0 && iy + 1 < H) fb[(iy + 1) * W + x] = blend565(fb[(iy + 1) * W + x], foam, 60);
    }
  }

  void drawBubbles() {
    Col rim = lit({215, 238, 255}), fill = lit({190, 225, 250});
    for (auto &b : bubbles_) {
      if (!b.alive) continue;
      cv_.fillCircle(b.x, b.y, b.r, fill, 0.18f);
      cv_.ring(b.x, b.y, b.r, 0.8f, rim, 0.75f);
      cv_.blend((int)(b.x - b.r * 0.35f), (int)(b.y - b.r * 0.4f), {255, 255, 255}, 0.85f);
    }
  }

  void updateFlakes(float dt) {
    for (auto &f : flakes_) {
      if (!f.alive) continue;
      if (f.landed) {
        f.rest += dt;
        if (f.rest > 10) f.alive = false;
        continue;
      }
      f.y += f.vy * dt;
      f.x += sn_.sin(t_ * 2.3f + f.phase) * 6 * dt;
      int xi = (int)clampf(f.x, 0, W - 1);
      if (f.y >= sandTop_[xi] - 1) {
        f.y = sandTop_[xi] - 1;
        f.landed = true;
      }
    }
  }

  void drawFlakes() {
    for (auto &f : flakes_) {
      if (!f.alive) continue;
      Col c = lit(f.c);
      cv_.fillRect(f.x - 1, f.y - 1, 2, 2, c, 1.0f);
      cv_.blend((int)f.x, (int)f.y - 1, scale(c, 1.25f), 0.7f);
    }
  }

  void updateChest(float dt) {
    const float period = 12;
    chestT_ += dt;
    if (chestT_ > period * 100) chestT_ -= period * 100;
    float c = fmodf(chestT_, period);
    float target = 0;
    if (c > 9.0f && c < 9.6f) target = (c - 9.0f) / 0.6f;
    else if (c >= 9.6f && c < 11.0f) target = 1;
    else if (c >= 11.0f && c < 11.8f) target = 1 - (c - 11.0f) / 0.8f;
    chestOpen_ = target;
    if (c >= 9.6f && c < 11.0f) {
      if (!chestBurst_) {
        chestBurst_ = true;
        for (int i = 0; i < 11; i++)
          spawnBubble(CHEST_X + rng_.range(-9, 9), sandTop_[(int)CHEST_X] - 14 - rng_.range(0, 8), rng_.range(1.0f, 2.6f));
      }
    } else {
      chestBurst_ = false;
    }
  }

  void drawChest() {
    float bx = CHEST_X - 15, bw = 30, bh = 13;
    float by = sandTop_[(int)CHEST_X] + 3 - bh;  // top of the box
    float open = chestOpen_;
    Col wood = lit({122, 72, 36}), woodD = lit({86, 48, 22}), gold = lit({230, 185, 60}), goldD = lit({170, 130, 40});
    // shadow on the sand
    cv_.fillEllipse(CHEST_X + 2, by + bh, 18, 3, {60, 45, 30}, 0.35f);
    // inside + treasure
    float lift = 7 * open;
    if (open > 0.02f) {
      cv_.fillRect(bx + 1, by - lift, bw - 2, lift + 1, lit({40, 22, 10}), 1);
      for (int i = 0; i < 6; i++) cv_.fillCircle(bx + 5 + i * 4, by - 1 - (i % 2), 2.2f, gold, open);
      cv_.fillCircle(CHEST_X, by - lift * 0.5f, 18, lit({255, 220, 90}), 0.20f * open);
    }
    // box
    cv_.fillRect(bx, by, bw, bh, wood, 1);
    for (float yy = by + 4; yy < by + bh; yy += 4) cv_.fillRect(bx, yy, bw, 1, woodD, 0.6f);
    cv_.fillRect(bx + 5, by, 3, bh, goldD, 1);
    cv_.fillRect(bx + bw - 8, by, 3, bh, goldD, 1);
    cv_.fillRect(bx, by, bw, 1.5f, gold, 1);
    // lid (dome), lifted while open
    float ly = by - lift;
    cv_.fillEllipse(CHEST_X, ly, bw * 0.5f, 7 * (1 - 0.35f * open), wood, 1, true);
    cv_.fillRect(bx, ly - 1, bw, 2, gold, 1);
    cv_.fillRect(bx + 5, ly - 6 * (1 - 0.35f * open), 3, 6 * (1 - 0.35f * open), goldD, 0.9f);
    cv_.fillRect(bx + bw - 8, ly - 6 * (1 - 0.35f * open), 3, 6 * (1 - 0.35f * open), goldD, 0.9f);
    // lock
    cv_.fillRect(CHEST_X - 2, by + 1, 4, 5, gold, 1);
    cv_.put((int)CHEST_X, (int)by + 3, lit({60, 40, 10}));
  }
};

}  // namespace aq

#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC pop_options
#endif
