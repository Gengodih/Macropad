// SafeLCD8.h - screen bus for the LilyGO T-Display-S3 (8-bit parallel, ESP32-S3)
//
// Based on Arduino_ESP32LCD8 from "GFX Library for Arduino" by moononournation
// (BSD licence), for the esp32 board package 3.x. The difference: the picture
// goes out through two transfer buffers, and a buffer is only filled again
// once the DMA has finished sending it. The library version refills its only
// buffer while it is still being sent; with a fast frame buffer that shows up
// as short horizontal streaks. Bonus: sending a frame takes less CPU time.
#pragma once
#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <esp_lcd_panel_io.h>

#if !defined(ESP_ARDUINO_VERSION_MAJOR) || ESP_ARDUINO_VERSION_MAJOR < 3
#error "Needs the esp32 board package version 3.x (Tools > Board > Boards Manager)"
#endif

class SafeLCD8 : public Arduino_DataBus {
 public:
  SafeLCD8(int8_t dc, int8_t cs, int8_t wr, int8_t rd,
           int8_t d0, int8_t d1, int8_t d2, int8_t d3, int8_t d4, int8_t d5, int8_t d6, int8_t d7)
      : _dc(dc), _cs(cs), _wr(wr), _rd(rd), _d{d0, d1, d2, d3, d4, d5, d6, d7} {}

  bool begin(int32_t speed = GFX_NOT_DEFINED, int8_t dataMode = GFX_NOT_DEFINED) override {
    (void)dataMode;
    uint32_t hz = (speed == GFX_NOT_DEFINED) ? 20000000UL : (uint32_t)speed;  // same as the library
    if (_cs != GFX_NOT_DEFINED) {
      pinMode(_cs, OUTPUT);
      digitalWrite(_cs, HIGH);
    }
    pinMode(_wr, OUTPUT);
    digitalWrite(_wr, HIGH);
    if (_rd != GFX_NOT_DEFINED) {
      pinMode(_rd, OUTPUT);
      digitalWrite(_rd, HIGH);
    }

    esp_lcd_i80_bus_config_t busConfig = {};
    busConfig.dc_gpio_num = _dc;
    busConfig.wr_gpio_num = _wr;
    busConfig.clk_src = LCD_CLK_SRC_PLL160M;
    for (int i = 0; i < 8; i++) busConfig.data_gpio_nums[i] = _d[i];
    busConfig.bus_width = 8;
    busConfig.max_transfer_bytes = BUF_BYTES;
    busConfig.dma_burst_size = 64;
    if (esp_lcd_new_i80_bus(&busConfig, &_i80) != ESP_OK) return false;

    esp_lcd_panel_io_i80_config_t ioConfig = {};
    ioConfig.cs_gpio_num = _cs;
    ioConfig.pclk_hz = hz;
    ioConfig.trans_queue_depth = 4;
    ioConfig.on_color_trans_done = onSent;  // counts finished transfers
    ioConfig.user_ctx = this;
    ioConfig.lcd_cmd_bits = 8;
    ioConfig.lcd_param_bits = 8;
    ioConfig.dc_levels.dc_idle_level = 0;
    ioConfig.dc_levels.dc_cmd_level = 0;
    ioConfig.dc_levels.dc_dummy_level = 0;
    ioConfig.dc_levels.dc_data_level = 1;
    if (esp_lcd_new_panel_io_i80(_i80, &ioConfig, &_io) != ESP_OK) return false;

    for (int i = 0; i < 2; i++) {
      _bufs[i] = (uint8_t *)esp_lcd_i80_alloc_draw_buffer(_io, BUF_BYTES, MALLOC_CAP_DMA);
      if (!_bufs[i]) return false;
      _ticket[i] = 0;
    }
    _cur = 0;
    _buffer = _bufs[0];
    _len = 0;
    _cmd = -1;
    _isColor = false;
    return true;
  }

  void beginWrite() override {
    _cmd = -1;
    _len = 0;
  }
  void endWrite() override { flushBuffer(); }

  void writeCommand(uint8_t c) override {
    flushBuffer();
    _cmd = c;
    _isColor = false;
  }
  void writeCommand16(uint16_t) override {}  // not used by this screen (same as the library)
  void writeCommandBytes(uint8_t *data, uint32_t len) override {
    flushBuffer();
    if (len) {
      _cmd = *data++;
      _isColor = false;
      len--;
    }
    while (len--) write(*data++);
  }

  void write(uint8_t d) override {
    _buffer[_len++] = d;
    if (_len >= BUF_BYTES) flushBuffer();
  }
  void write16(uint16_t d) override {
    _buffer[_len++] = d >> 8;
    _buffer[_len++] = d & 0xFF;
    if (_len >= BUF_BYTES - 1) flushBuffer();
  }
  void writeBytes(uint8_t *data, uint32_t len) override {
    while (len--) write(*data++);
  }

  // Pixels go out high byte first
  void writePixels(uint16_t *data, uint32_t len) override {
    _isColor = true;
    while (len) {
      uint32_t room = (BUF_BYTES - _len) / 2;
      uint32_t n = len < room ? len : room;
      uint8_t *p = _buffer + _len;
      for (uint32_t i = 0; i < n; i++) {
        uint16_t v = data[i];
        p[0] = v >> 8;
        p[1] = v & 0xFF;
        p += 2;
      }
      data += n;
      len -= n;
      _len += n * 2;
      if (_len >= BUF_BYTES - 1) flushBuffer();
    }
  }
  void writeRepeat(uint16_t c, uint32_t len) override {
    _isColor = true;
    while (len) {
      uint32_t room = (BUF_BYTES - _len) / 2;
      uint32_t n = len < room ? len : room;
      uint8_t *p = _buffer + _len;
      for (uint32_t i = 0; i < n; i++) {
        p[0] = c >> 8;
        p[1] = c & 0xFF;
        p += 2;
      }
      len -= n;
      _len += n * 2;
      if (_len >= BUF_BYTES - 1) flushBuffer();
    }
  }

 private:
  static constexpr uint32_t BUF_BYTES = 8192;  // per transfer (a multiple of 4, as the DMA wants)

  // Called by the LCD driver (in its interrupt) each time a pixel transfer is done
  static bool IRAM_ATTR onSent(esp_lcd_panel_io_handle_t, esp_lcd_panel_io_event_data_t *, void *ctx) {
    SafeLCD8 *self = (SafeLCD8 *)ctx;
    self->_sent = self->_sent + 1;
    return false;
  }

  // Wait until transfer number 'ticket' is done (with a time limit, so it can never hang)
  void waitSent(uint32_t ticket) {
    uint32_t start = micros();
    while ((int32_t)(_sent - ticket) < 0 && micros() - start < 50000) {
    }
  }

  void flushBuffer() {
    if (_cmd == 0x2C) _isColor = true;  // RAMWR: pixel data follows
    if (_cmd < 0 && _len == 0) return;
    if (_isColor && _len > 0) {
      // Start the DMA (it runs on its own) and carry on in the other buffer
      if (esp_lcd_panel_io_tx_color(_io, _cmd, _buffer, _len) == ESP_OK) _ticket[_cur] = ++_queued;
      _cur ^= 1;
      _buffer = _bufs[_cur];
      waitSent(_ticket[_cur]);  // that one may still be on its way out
    } else {
      // command (+ parameters): sent right away; the driver first lets any pixels finish
      esp_lcd_panel_io_tx_param(_io, _cmd, _buffer, _len);
    }
    _cmd = -1;
    _len = 0;
  }

  int8_t _dc, _cs, _wr, _rd;
  int8_t _d[8];
  esp_lcd_i80_bus_handle_t _i80 = nullptr;
  esp_lcd_panel_io_handle_t _io = nullptr;
  uint8_t *_bufs[2] = {nullptr, nullptr};
  uint32_t _ticket[2] = {0, 0};
  uint8_t *_buffer = nullptr;
  uint32_t _len = 0;
  int32_t _cmd = -1;
  bool _isColor = false;
  int _cur = 0;
  uint32_t _queued = 0;
  volatile uint32_t _sent = 0;
};
