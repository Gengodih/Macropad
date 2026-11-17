"""The pad's animated backgrounds inside the app: one running scene, and the
preview tiles of the catalog on the Display page."""

import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import bgfx, config, protocol
from .theme import ACCENT

_seed = random.Random()


class LiveInfo:
    """What the widget previews show: set by the main window."""

    def __init__(self):
        self.lang = 0
        self.stats = (None, None, None, None)      # cpu, ram, gpu, gpu temperature
        self.timer = (0.0, 25 * 60.0, 0, 0, False)  # left, total, phase, round, paused
        self.picture = None                         # picture.Picture or None
        self.picture_version = 0

    def set_picture(self, pic):
        self.picture = pic
        self.picture_version += 1


live = LiveInfo()


class Scene:
    """One background, run by the pad's own code. paint() draws it into any
    rectangle, filling it (the middle is kept, the edges cut off as needed)."""

    def __init__(self, name):
        self.name = name
        self.image = None
        self.level = 0.0
        self._level_at = 0.0
        self._r = None
        self._pic_version = -1
        if bgfx.available():
            try:
                self._r = bgfx.Renderer(_seed.getrandbits(32) or 1)
            except (RuntimeError, MemoryError):
                self._r = None
        self.configure(name, config.BACKGROUND_OPTIONS)

    @property
    def ok(self):
        return self._r is not None

    def configure(self, name, options):
        self.name = name
        if self._r:
            self._r.select(config.PAD_BACKGROUND[name], protocol.background_options(name, options))

    def set_level(self, level):
        self.level = max(0.0, min(1.0, level))
        self._level_at = time.monotonic()

    def poke(self, label="Macro"):
        if self._r:
            self._r.poke(label)

    def step(self, dt, colour=11):
        if not self._r:
            return
        if time.monotonic() - self._level_at > 0.3:   # no music data: silence
            self.level *= 0.85
        if self.name in config.WIDGETS:
            cpu, ram, gpu, temp = live.stats
            left, total, phase, round_, paused = live.timer
            self._r.set_info(protocol.local_epoch(), live.lang, -1 if cpu is None else cpu, -1 if ram is None else ram,
                             -1 if gpu is None else gpu, -1 if temp is None else temp, left, total, phase, round_, paused)
            if self.name == "picture" and self._pic_version != live.picture_version:
                self._pic_version = live.picture_version
                p = live.picture
                if p is None:
                    self._r.set_picture(None)
                else:
                    self._r.set_picture(p.data, p.w, p.h, p.frames, p.delay_ms)
        self._r.update(dt, self.level, colour, time.localtime().tm_mon)
        self.image = self._r.frame()

    def paint(self, p: QPainter, rect: QRectF):
        if self.image is None:
            p.fillRect(rect, QColor("#11121b"))
            return
        iw, ih = self.image.width(), self.image.height()
        scale = max(rect.width() / iw, rect.height() / ih)
        sw, sh = rect.width() / scale, rect.height() / scale
        src = QRectF((iw - sw) / 2, (ih - sh) / 2, sw, sh)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(rect, self.image, src)
        p.restore()

    def close(self):
        if self._r:
            self._r.close()
            self._r = None


class PreviewTile(QWidget):
    """A small live preview in the catalog. Click = choose it."""

    clicked = Signal(str)
    LABEL_H = 26

    def __init__(self, name, title, parent=None):
        super().__init__(parent)
        self.name = name
        self.title = title
        self.selected = False
        self._hover = False
        self.scene = Scene(name)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(110)
        self.setFixedHeight(self._height_for(150))
        self.setToolTip(title)

    def _height_for(self, w):
        return int((w - 4) * bgfx.H / bgfx.W) + 4 + self.LABEL_H

    def resizeEvent(self, e):
        h = self._height_for(self.width())
        if h != self.height():
            self.setFixedHeight(h)
        super().resizeEvent(e)

    def set_selected(self, on):
        if on != self.selected:
            self.selected = on
            self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.name)
        super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        img = QRectF(2, 2, w - 4, self.height() - self.LABEL_H - 4)
        path = QPainterPath()
        path.addRoundedRect(img, 10, 10)
        p.save()
        p.setClipPath(path)
        self.scene.paint(p, img)
        if not self.scene.ok:
            p.setPen(QColor("#8a8aa0"))
            p.drawText(img, Qt.AlignCenter, "-")
        p.restore()
        if self.selected:
            pen = QPen(QColor(ACCENT), 3)
        elif self._hover:
            pen = QPen(QColor(255, 255, 255, 140), 1.5)
        else:
            pen = QPen(QColor(255, 255, 255, 40), 1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(img, 10, 10)
        if self.selected:                       # a tick in the corner
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(QRectF(img.right() - 24, img.top() + 6, 18, 18))
            p.setPen(QPen(QColor("white"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            x, y = img.right() - 24, img.top() + 6
            p.drawPolyline([QPointF(x + 5, y + 9.5), QPointF(x + 8, y + 12.5), QPointF(x + 13.5, y + 6)])
        f = QFont(self.font())
        f.setBold(self.selected)
        p.setFont(f)
        p.setPen(QColor("white") if self.selected else QColor("#c9c9d6"))
        p.drawText(QRectF(0, self.height() - self.LABEL_H, w, self.LABEL_H), Qt.AlignCenter, self.title)


class OptionsPanel(QWidget):
    """The settings of the chosen background, right under its row of previews,
    with a small notch pointing up at the chosen tile."""

    NOTCH = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notch_x = 40
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, self.NOTCH + 0.5, self.width() - 1, self.height() - self.NOTCH - 1)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        notch = QPainterPath()
        x = max(24, min(self.width() - 24, self.notch_x))
        notch.moveTo(x - self.NOTCH, r.top() + 1)
        notch.lineTo(x, 0.5)
        notch.lineTo(x + self.NOTCH, r.top() + 1)
        notch.closeSubpath()
        path = path.united(notch)
        p.setPen(QPen(QColor(ACCENT), 1.2))
        p.setBrush(QColor(139, 92, 246, 34))
        p.drawPath(path)
