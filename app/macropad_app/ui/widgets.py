"""Small custom widgets: switch, status box, cards, key caps, colour swatches."""

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme


class ToggleSwitch(QAbstractButton):
    """A sliding on/off switch (for Autostart and the display options)."""

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(46, 26)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def get_knob(self):
        return self._pos

    def set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, get_knob, set_knob)

    def setChecked(self, on):  # noqa: N802 (Qt name)
        super().setChecked(on)
        self._pos = 1.0 if on else 0.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off, on = QColor("#3a3a50"), QColor(theme.ACCENT)
        c = QColor(int(off.red() + (on.red() - off.red()) * self._pos),
                   int(off.green() + (on.green() - off.green()) * self._pos),
                   int(off.blue() + (on.blue() - off.blue()) * self._pos))
        if not self.isEnabled():
            c = QColor("#2a2a38")
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class StatusBox(QLabel):
    """The small coloured box with the pad's status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(30)
        self.set_status("searching", "")

    def set_status(self, status, text):
        colour = theme.STATUS_COLOURS.get(status, theme.RED)
        fg = "#1a1400" if status == "searching" else "white"
        self.setText(text)
        self.setStyleSheet(f"background: {colour}; color: {fg}; border-radius: 8px; padding: 5px 10px;"
                           f" font-weight: 700;")


class Card(QFrame):
    """See-through panel that sits on the background animation."""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(20, 16, 20, 18)
        self.layout_.setSpacing(10)
        if title:
            t = QLabel(title)
            t.setObjectName("CardTitle")
            self.layout_.addWidget(t)

    def add(self, w, stretch=0):
        self.layout_.addWidget(w, stretch)
        return w


def label(text, name=None, wrap=True):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class KeyCap(QAbstractButton):
    """One key of the pad: a rounded key cap with a short label (and a colour
    stripe for the light schemes)."""

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.text_ = ""
        self.sub = ""
        self.colour = None
        self.badge = False
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(78, 70)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def sizeHint(self):
        return QSize(96, 84)

    def set_content(self, text, sub="", colour=None, badge=False):
        self.text_, self.sub, self.colour, self.badge = text, sub, colour, badge
        self.setToolTip(f"{text}\n{sub}".strip())
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(3, 3, self.width() - 6, self.height() - 6)
        hover = self.underMouse()
        base = QColor(self.colour) if self.colour else QColor("#262636")
        if self.colour:
            base = base.darker(115)
        # key body with a lighter top face, like a real key cap
        p.setPen(QPen(QColor(theme.ACCENT) if (self.selected or hover) else QColor("#3d3d55"), 2 if self.selected else 1))
        p.setBrush(base.darker(140))
        p.drawRoundedRect(r, 12, 12)
        top = r.adjusted(5, 4, -5, -9)
        p.setPen(Qt.NoPen)
        p.setBrush(base.lighter(125 if hover else 110))
        p.drawRoundedRect(top, 9, 9)
        light = QColor(self.colour).lightness() > 150 if self.colour else False
        p.setPen(QColor("#111") if light else QColor("white"))
        f = QFont(self.font())
        size = 15 if len(self.text_) <= 3 else 11 if len(self.text_) <= 8 else 9
        f.setPointSize(size)
        f.setBold(True)
        p.setFont(f)
        text_rect = top.adjusted(4, 2, -4, -14 if self.sub else -2)
        p.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_)
        if self.sub:
            f.setPointSize(7)
            f.setBold(False)
            p.setFont(f)
            p.setPen(QColor("#333") if light else QColor(theme.DIM))
            p.drawText(top.adjusted(2, 0, -2, -3), Qt.AlignHCenter | Qt.AlignBottom, self.sub)
        if self.badge:   # works only while the app runs
            p.setBrush(QColor(theme.YELLOW))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(r.right() - 14, r.top() + 4, 9, 9))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class Swatch(QAbstractButton):
    """A round colour button."""

    def __init__(self, colour, tip="", parent=None, size=26):
        super().__init__(parent)
        self.colour = QColor(colour)
        self.setCheckable(True)
        self.setToolTip(tip)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(QPen(QColor("white"), 2.5) if self.isChecked() else QPen(QColor("#00000000"), 0))
        p.setBrush(self.colour)
        p.drawEllipse(r)


class KnobIcon(QWidget):
    """A drawn rotary knob for the key mapping page."""

    def sizeHint(self):
        return QSize(64, 64)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = min(self.width(), self.height()) - 6
        r = QRectF((self.width() - s) / 2, (self.height() - s) / 2, s, s)
        p.setPen(QPen(QColor("#4a4a64"), 2))
        p.setBrush(QColor("#2a2a3c"))
        p.drawEllipse(r)
        p.setBrush(QColor("#3a3a52"))
        p.drawEllipse(r.adjusted(s * 0.12, s * 0.12, -s * 0.12, -s * 0.12))
        p.setPen(QPen(QColor(theme.ACCENT), 3, Qt.SolidLine, Qt.RoundCap))
        c = r.center()
        p.drawLine(c.x(), c.y() - s * 0.08, c.x(), r.top() + s * 0.2)
