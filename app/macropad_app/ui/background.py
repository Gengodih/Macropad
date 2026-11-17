"""The animated background of the content area - the same choice as the pad's
screen: an aquarium (with or without fish) or a plain dark background."""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import QWidget

FPS = 24


class _Fish:
    def __init__(self, rnd, w, h, small=False):
        self.small = small
        self.len = rnd.uniform(16, 22) if small else rnd.uniform(38, 66)
        self.speed = rnd.uniform(30, 48) if small else rnd.uniform(18, 40)
        self.dir = rnd.choice((-1, 1))
        self.x = rnd.uniform(0, w)
        self.y = rnd.uniform(h * 0.15, h * 0.7)
        self.base_y = self.y
        self.phase = rnd.uniform(0, 6.28)
        self.z = rnd.uniform(0.0, 1.0)
        palettes = [("#ff8a3d", "#ffd27a"), ("#3dd6ff", "#c3f4ff"), ("#ffd23d", "#fff2b0"),
                    ("#ff5d7a", "#ffc0cb"), ("#8b5cf6", "#d9c9ff"), ("#5eead4", "#e6fffb")]
        self.body, self.belly = palettes[rnd.randrange(len(palettes))]
        if small:
            self.body, self.belly = "#2dd4ff", "#ff3d6e"   # neon tetra


class _Bubble:
    def __init__(self, rnd, w, h, start_low=True):
        self.x = rnd.uniform(0, w)
        self.y = rnd.uniform(h * 0.75, h) if start_low else rnd.uniform(0, h)
        self.r = rnd.uniform(2, 6)
        self.speed = rnd.uniform(25, 55)
        self.phase = rnd.uniform(0, 6.28)


class Background(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.mode = "aquarium"
        self.fish_on = True
        self._rnd = random.Random(7)
        self._t = 0.0
        self._static = None
        self._fish = []
        self._bubbles = []
        self._plants = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ----- settings ---------------------------------------------------------
    def set_style(self, mode, fish):
        self.mode = mode if mode in ("aquarium", "plain") else "aquarium"
        self.fish_on = bool(fish)
        self._static = None
        self._update_timer()
        self.update()

    def _update_timer(self):
        want = self.mode == "aquarium" and self.isVisible()
        if want and not self._timer.isActive():
            self._timer.start(int(1000 / FPS))
        elif not want and self._timer.isActive():
            self._timer.stop()

    def showEvent(self, e):
        self._update_timer()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def resizeEvent(self, e):
        self._static = None
        self._populate()
        super().resizeEvent(e)

    # ----- scene ------------------------------------------------------------
    def _populate(self):
        w, h = max(1, self.width()), max(1, self.height())
        rnd = self._rnd
        self._fish = [_Fish(rnd, w, h) for _ in range(7)]
        school_y = h * 0.42
        for i in range(9):
            f = _Fish(rnd, w, h, small=True)
            f.dir = 1
            f.x = w * 0.2 + (i % 5) * 26
            f.base_y = school_y + (i // 5) * 18 + rnd.uniform(-5, 5)
            f.speed = 42
            self._fish.append(f)
        self._fish.sort(key=lambda f: -f.z)
        self._bubbles = [_Bubble(rnd, w, h, start_low=False) for _ in range(26)]
        self._plants = []
        for i in range(9):
            x = rnd.uniform(0.02, 0.98) * w
            blades = []
            for _ in range(rnd.randint(3, 6)):
                blades.append((rnd.uniform(-14, 14), rnd.uniform(h * 0.16, h * 0.38), rnd.uniform(0, 6.28),
                               rnd.choice(("#1f8a4c", "#2fae5f", "#167a44", "#3cc46d"))))
            self._plants.append((x, blades))

    def _sand_y(self, x, h):
        return h * 0.86 + 6 * math.sin(x * 0.012 + 0.5) + 4 * math.sin(x * 0.031 + 2.0)

    def _build_static(self):
        w, h = max(1, self.width()), max(1, self.height())
        pm = QPixmap(w, h)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        if self.mode == "plain":
            g = QLinearGradient(0, 0, w * 0.4, h)
            g.setColorAt(0, QColor("#171927"))
            g.setColorAt(1, QColor("#0b0c13"))
            p.fillRect(0, 0, w, h, g)
            glow = QRadialGradient(QPointF(w * 0.75, h * 0.15), w * 0.6)
            glow.setColorAt(0, QColor(139, 92, 246, 46))
            glow.setColorAt(1, QColor(139, 92, 246, 0))
            p.fillRect(0, 0, w, h, glow)
            p.end()
            return pm
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor("#2a8fb8"))
        g.setColorAt(0.35, QColor("#13628f"))
        g.setColorAt(0.8, QColor("#0b3557"))
        g.setColorAt(1.0, QColor("#08243b"))
        p.fillRect(0, 0, w, h, g)
        # sand
        path = QPainterPath(QPointF(0, h))
        for x in range(0, w + 8, 8):
            path.lineTo(x, self._sand_y(x, h))
        path.lineTo(w, h)
        path.closeSubpath()
        sg = QLinearGradient(0, h * 0.82, 0, h)
        sg.setColorAt(0, QColor("#c9a86a"))
        sg.setColorAt(1, QColor("#8a6a3a"))
        p.fillPath(path, sg)
        rnd = random.Random(3)
        for _ in range(int(w / 6)):   # pebbles
            x = rnd.uniform(0, w)
            y = rnd.uniform(self._sand_y(x, h) + 4, h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(rnd.choice(("#a88a55", "#d6bc86", "#7d6238", "#b89b66"))))
            p.drawEllipse(QPointF(x, y), rnd.uniform(1, 3), rnd.uniform(1, 2))
        for rx, ry, rw, rh in ((0.12, 0.86, 70, 44), (0.8, 0.87, 90, 52), (0.86, 0.85, 50, 34), (0.45, 0.9, 40, 22)):
            cx = rx * w
            rg = QRadialGradient(QPointF(cx - rw * 0.2, h * ry - rh * 0.3), rw)
            rg.setColorAt(0, QColor("#6f7b86"))
            rg.setColorAt(1, QColor("#323a44"))
            p.setBrush(rg)
            p.drawEllipse(QPointF(cx, h * ry), rw / 2, rh / 2)
        p.end()
        return pm

    # ----- animation --------------------------------------------------------
    def _tick(self):
        dt = 1.0 / FPS
        self._t += dt
        w, h = self.width(), self.height()
        for f in self._fish:
            f.x += f.dir * f.speed * dt
            margin = f.len * 1.5
            if not f.small and (f.x > w + margin or f.x < -margin):
                f.dir = -f.dir
                f.base_y = self._rnd.uniform(h * 0.15, h * 0.7)
            if f.small and f.x > w + 40:
                f.x = -40 - self._rnd.uniform(0, 160)
            f.y = f.base_y + math.sin(self._t * 0.9 + f.phase) * (4 if f.small else 9)
        for b in self._bubbles:
            b.y -= b.speed * dt
            if b.y < -10:
                b.y = h + self._rnd.uniform(0, 60)
                b.x = self._rnd.uniform(0, w)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if self._static is None or self._static.size() != self.size():
            self._static = self._build_static()
        p.drawPixmap(0, 0, self._static)
        if self.mode != "aquarium":
            return
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = self._t
        # light rays from the surface
        p.setPen(Qt.NoPen)
        for i, (x0, width) in enumerate(((0.15, 90), (0.38, 60), (0.62, 110), (0.85, 70))):
            sway = math.sin(t * 0.25 + i) * 30
            path = QPainterPath(QPointF(x0 * w + sway, 0))
            path.lineTo(x0 * w + sway + width, 0)
            path.lineTo(x0 * w + sway * 2.2 + width * 2.2 + 80, h * 0.85)
            path.lineTo(x0 * w + sway * 2.2 + 60, h * 0.85)
            path.closeSubpath()
            g = QLinearGradient(0, 0, 0, h * 0.85)
            a = int(30 + 14 * math.sin(t * 0.6 + i * 1.7))
            g.setColorAt(0, QColor(255, 255, 255, a))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(path, g)
        # plants
        for x, blades in self._plants:
            base = self._sand_y(x, h) + 6
            for off, length, ph, col in blades:
                sway = math.sin(t * 1.1 + ph) * 12
                path = QPainterPath(QPointF(x + off - 4, base))
                path.quadTo(QPointF(x + off - 6 + sway * 0.5, base - length * 0.5),
                            QPointF(x + off + sway, base - length))
                path.quadTo(QPointF(x + off + 4 + sway * 0.5, base - length * 0.5), QPointF(x + off + 4, base))
                p.setBrush(QColor(col))
                p.drawPath(path)
        # fish
        if self.fish_on:
            for f in self._fish:
                self._draw_fish(p, f)
        # bubbles
        for b in self._bubbles:
            x = b.x + math.sin(t * 2 + b.phase) * 3
            p.setPen(QPen(QColor(255, 255, 255, 150), 1.2))
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawEllipse(QPointF(x, b.y), b.r, b.r)
        # surface shimmer and a soft dark edge so the text stays readable
        top = QLinearGradient(0, 0, 0, 40)
        top.setColorAt(0, QColor(255, 255, 255, 50))
        top.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(0, 0, w, 40, top)
        p.fillRect(0, 0, w, h, QColor(5, 10, 20, 70))

    def _draw_fish(self, p, f):
        L = f.len * (0.75 + 0.25 * (1 - f.z))
        H = L * (0.42 if not f.small else 0.3)
        p.save()
        p.translate(f.x, f.y)
        if f.dir < 0:
            p.scale(-1, 1)
        wag = math.sin(self._t * (9 if f.small else 6) + f.phase) * H * 0.25
        alpha = int(255 - 90 * f.z)
        body = QColor(f.body)
        body.setAlpha(alpha)
        belly = QColor(f.belly)
        belly.setAlpha(alpha)
        # tail
        tail = QPainterPath(QPointF(-L * 0.42, 0))
        tail.lineTo(-L * 0.72, -H * 0.55 + wag)
        tail.quadTo(QPointF(-L * 0.62, wag), QPointF(-L * 0.72, H * 0.55 + wag))
        tail.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(body.darker(115))
        p.drawPath(tail)
        # body with a lighter belly
        g = QLinearGradient(0, -H / 2, 0, H / 2)
        g.setColorAt(0, body.darker(110))
        g.setColorAt(0.55, body)
        g.setColorAt(1, belly)
        p.setBrush(QBrush(g))
        p.drawEllipse(QRectF(-L / 2, -H / 2, L, H))
        # fin
        fin = QPainterPath(QPointF(-L * 0.05, -H * 0.42))
        fin.quadTo(QPointF(-L * 0.12, -H * 0.85), QPointF(-L * 0.3, -H * 0.4))
        p.setBrush(body.darker(125))
        p.drawPath(fin)
        # eye
        p.setBrush(QColor(255, 255, 255, alpha))
        p.drawEllipse(QPointF(L * 0.3, -H * 0.08), H * 0.13, H * 0.13)
        p.setBrush(QColor(10, 10, 20, alpha))
        p.drawEllipse(QPointF(L * 0.32, -H * 0.08), H * 0.07, H * 0.07)
        p.restore()
