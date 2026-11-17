// bgfx.cpp - the pad's screen animations as a small library for the PC app,
// so the previews in the app show exactly what the pad will show.
// Built by tools/build_bgfx.py (bgfx.dll on Windows, bgfx.so elsewhere).

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <new>

#include "../firmware/macropad/Aquarium.h"
#include "../firmware/macropad/Backgrounds.h"

#ifdef _WIN32
#define BGFX_API extern "C" __declspec(dllexport)
#else
#define BGFX_API extern "C" __attribute__((visibility("default")))
#endif

namespace {
constexpr size_t PIXELS = (size_t)aq::W * aq::H;

struct Renderer {
  uint16_t frame[PIXELS];
  uint16_t scratch[PIXELS];
  uint16_t *tankBufs[4] = {nullptr, nullptr, nullptr, nullptr};
  aq::Aquarium *tank = nullptr;
  bgx::Effects fx;
  uint32_t seed = 1;
  uint8_t kind = bgx::SYNTHWAVE;
  uint8_t opts = 0;
  bgx::Inputs info;                 // time, PC stats, timer (bgfx_set_info)
  uint16_t *picture = nullptr;      // own copy of the picture (bgfx_set_picture)

  bool startTank() {
    if (tank) return true;
    for (auto &b : tankBufs) {
      b = static_cast<uint16_t *>(calloc(PIXELS, 2));
      if (!b) return false;
    }
    tank = new (std::nothrow) aq::Aquarium();
    if (!tank) return false;
    tank->begin(frame, tankBufs[0], tankBufs[1], seed, tankBufs[2], tankBufs[3]);
    return true;
  }
  ~Renderer() {
    delete tank;
    for (auto b : tankBufs) free(b);
    free(picture);
  }
};
}  // namespace

BGFX_API int bgfx_version() { return 2; }
BGFX_API int bgfx_width() { return aq::W; }
BGFX_API int bgfx_height() { return aq::H; }

BGFX_API void *bgfx_new(uint32_t seed) {
  Renderer *r = new (std::nothrow) Renderer();
  if (!r) return nullptr;
  memset(r->frame, 0, sizeof(r->frame));
  r->seed = seed ? seed : 1;
  r->fx.begin(r->frame, r->scratch, r->seed);
  return r;
}

BGFX_API void bgfx_free(void *h) { delete static_cast<Renderer *>(h); }

// kind: 0 aquarium, 1 plain, 2 synthwave ... 8 seasons (as on the pad)
// opts: the option bits (aquarium: bit 0 = fish)
BGFX_API void bgfx_select(void *h, int kind, int opts) {
  Renderer *r = static_cast<Renderer *>(h);
  if (!r) return;
  if (kind < 0 || kind >= bgx::KIND_COUNT) kind = bgx::SYNTHWAVE;
  r->kind = (uint8_t)kind;
  r->opts = (uint8_t)opts;
  if (kind == bgx::AQUARIUM) {
    if (r->startTank()) r->tank->showFish = opts & 1;
  } else {
    r->fx.select((uint8_t)kind, (uint8_t)opts);
  }
}

BGFX_API void bgfx_poke(void *h, const char *label) {
  Renderer *r = static_cast<Renderer *>(h);
  if (!r) return;
  if (r->kind == bgx::AQUARIUM) {
    if (r->tank) r->tank->feed();
  } else {
    r->fx.poke(label ? label : "");
  }
}

BGFX_API void bgfx_update(void *h, float dt, float level, int hue, int sat, int month) {
  Renderer *r = static_cast<Renderer *>(h);
  if (!r) return;
  if (r->kind == bgx::AQUARIUM) {
    if (r->tank) r->tank->update(dt);
    return;
  }
  bgx::Inputs in = r->info;
  in.level = level < 0 ? 0 : (level > 1 ? 1 : level);
  in.accentHue = (uint16_t)hue;
  in.accentSat = (uint8_t)sat;
  in.month = (uint8_t)(month >= 1 && month <= 12 ? month : 0);
  r->fx.update(dt, in);
}

// Time, PC stats and the focus timer for the widgets (-1 = unknown)
BGFX_API void bgfx_set_info(void *h, uint32_t epoch, int lang, float cpu, float ram, float gpu, float gpuTemp,
                            float timerLeft, float timerTotal, int timerPhase, int timerRound, int timerPaused) {
  Renderer *r = static_cast<Renderer *>(h);
  if (!r) return;
  bgx::Inputs &i = r->info;
  i.epoch = epoch;
  i.lang = lang == 1 ? 1 : 0;
  i.cpu = cpu; i.ram = ram; i.gpu = gpu; i.gpuTemp = gpuTemp;
  i.timerLeft = timerLeft; i.timerTotal = timerTotal;
  i.timerPhase = (uint8_t)(timerPhase >= 0 && timerPhase <= 3 ? timerPhase : 0);
  i.timerRound = (uint8_t)(timerRound >= 0 && timerRound <= 9 ? timerRound : 0);
  i.timerPaused = timerPaused != 0;
}

// The own picture: frames of w x h RGB565 pixels (320x170 or 160x85); null = none
BGFX_API int bgfx_set_picture(void *h, const uint16_t *pixels, int w, int hgt, int frames, int delayMs) {
  Renderer *r = static_cast<Renderer *>(h);
  if (!r) return 0;
  free(r->picture);
  r->picture = nullptr;
  r->fx.setPicture(nullptr, 0, 0, 0, 0);
  bool ok = pixels && frames > 0 && frames < 1000 && ((w == 320 && hgt == 170) || (w == 160 && hgt == 85));
  if (!ok) return 0;
  size_t n = (size_t)w * hgt * frames;
  r->picture = static_cast<uint16_t *>(malloc(n * 2));
  if (!r->picture) return 0;
  memcpy(r->picture, pixels, n * 2);
  r->fx.setPicture(r->picture, (uint16_t)w, (uint16_t)hgt, (uint16_t)frames, (uint16_t)delayMs);
  return 1;
}

// Draws the frame and copies it (RGB565, 320 x 170, little endian) to out.
BGFX_API void bgfx_render(void *h, uint16_t *out) {
  Renderer *r = static_cast<Renderer *>(h);
  if (!r || !out) return;
  if (r->kind == bgx::AQUARIUM) {
    if (r->tank) r->tank->render();
  } else {
    r->fx.render();
  }
  memcpy(out, r->frame, sizeof(r->frame));
}
