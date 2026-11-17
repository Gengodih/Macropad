"""The focus timer (Pomodoro): focus -> break, four rounds, then a long break.
Started and paused with the "Focus timer" keys; shown on the pad's screen."""

import time

from PySide6.QtCore import QObject, QTimer, Signal

OFF, FOCUS, BREAK, LONG_BREAK = 0, 1, 2, 3
ROUNDS = 4


class FocusTimer(QObject):
    changed = Signal()                 # every second while it runs, and on every change
    phase_ended = Signal(int, int)     # the phase that ended, the one that starts

    def __init__(self, minutes=None, parent=None):
        super().__init__(parent)
        self.minutes = dict(minutes or {"focus": 25, "break": 5, "long": 15})
        self.phase = OFF
        self.round = 0
        self.paused = False
        self.total = self.minutes["focus"] * 60
        self._end = 0.0                # time.monotonic() when the phase ends (while running)
        self._left = float(self.total)  # while paused / off
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._step)

    # ----- state -----------------------------------------------------------------
    @property
    def left(self) -> float:
        if self.phase == OFF or self.paused:
            return self._left
        return max(0.0, self._end - time.monotonic())

    def set_minutes(self, minutes):
        self.minutes = dict(minutes)
        if self.phase == OFF:
            self.total = self.minutes["focus"] * 60
            self._left = float(self.total)
            self.changed.emit()

    def _start_phase(self, phase):
        self.phase = phase
        key = {FOCUS: "focus", BREAK: "break", LONG_BREAK: "long"}[phase]
        self.total = self.minutes[key] * 60
        self._end = time.monotonic() + self.total
        self.paused = False
        self._tick.start(1000)

    # ----- keys ------------------------------------------------------------------
    def toggle(self):
        """Start, pause or go on."""
        if self.phase == OFF:
            self.round = 1
            self._start_phase(FOCUS)
        elif self.paused:
            self._end = time.monotonic() + self._left
            self.paused = False
            self._tick.start(1000)
        else:
            self._left = self.left
            self.paused = True
            self._tick.stop()
        self.changed.emit()

    def skip(self):
        """Next phase; while paused or off: stop and reset."""
        if self.phase == OFF or self.paused:
            self.stop()
            return
        self._next()

    def stop(self):
        self.phase = OFF
        self.round = 0
        self.paused = False
        self._tick.stop()
        self.total = self.minutes["focus"] * 60
        self._left = float(self.total)
        self.changed.emit()

    def _next(self):
        ended = self.phase
        if ended == FOCUS:
            new = LONG_BREAK if self.round >= ROUNDS else BREAK
        else:
            self.round = 1 if ended == LONG_BREAK else self.round + 1
            new = FOCUS
        self._start_phase(new)
        self.phase_ended.emit(ended, new)
        self.changed.emit()

    def _step(self):
        if self.phase != OFF and not self.paused and self.left <= 0:
            self._next()
        else:
            self.changed.emit()
