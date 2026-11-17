"""Dialogs: choosing a key's action, the "Changing" popup, update/flash progress."""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import keys
from ..i18n import T, language


def ask(parent, text, title="") -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title or T("app_title"))
    box.setText(text)
    yes = box.addButton(T("yes"), QMessageBox.YesRole)
    box.addButton(T("no"), QMessageBox.NoRole)
    box.exec()
    return box.clickedButton() is yes


def info(parent, text, title=""):
    box = QMessageBox(parent)
    box.setWindowTitle(title or T("app_title"))
    box.setText(text)
    box.addButton(T("ok"), QMessageBox.AcceptRole)
    box.exec()


def ask_text(parent, text, value="", limit=15):
    d = QDialog(parent)
    d.setWindowTitle(T("app_title"))
    lay = QVBoxLayout(d)
    lay.addWidget(QLabel(text))
    edit = QLineEdit(value)
    edit.setMaxLength(limit)
    lay.addWidget(edit)
    row = QHBoxLayout()
    row.addStretch()
    cancel = QPushButton(T("cancel"))
    ok = QPushButton(T("ok"))
    ok.setObjectName("Primary")
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    cancel.clicked.connect(d.reject)
    ok.clicked.connect(d.accept)
    edit.returnPressed.connect(d.accept)
    if d.exec() == QDialog.Accepted and edit.text().strip():
        return edit.text().strip()
    return None


# Qt key -> our key names (for "press the combination")
def _qt_key_name(key: int):
    from PySide6.QtCore import Qt as Q
    if Q.Key_A <= key <= Q.Key_Z:
        return chr(key)
    if Q.Key_0 <= key <= Q.Key_9:
        return chr(key)
    if Q.Key_F1 <= key <= Q.Key_F24:
        return f"F{key - Q.Key_F1 + 1}"
    table = {Q.Key_Return: "ENTER", Q.Key_Enter: "ENTER", Q.Key_Escape: "ESC", Q.Key_Backspace: "BACKSPACE",
             Q.Key_Tab: "TAB", Q.Key_Space: "SPACE", Q.Key_Insert: "INSERT", Q.Key_Delete: "DELETE",
             Q.Key_Up: "UP", Q.Key_Down: "DOWN", Q.Key_Left: "LEFT", Q.Key_Right: "RIGHT", Q.Key_Home: "HOME",
             Q.Key_End: "END", Q.Key_PageUp: "PAGEUP", Q.Key_PageDown: "PAGEDOWN", Q.Key_Print: "PRINTSCREEN",
             Q.Key_Pause: "PAUSE", Q.Key_Comma: "COMMA", Q.Key_Period: "PERIOD", Q.Key_Minus: "MINUS",
             Q.Key_Slash: "SLASH", Q.Key_Menu: "MENU", Q.Key_CapsLock: "CAPSLOCK"}
    return table.get(key)


class ComboRecorder(QLineEdit):
    """Click, then press a key combination: it shows up and fills the boxes."""
    recorded = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText(T("combo_record"))

    def keyPressEvent(self, e):
        name = _qt_key_name(e.key())
        if not name:
            return
        m = e.modifiers()
        mods = ((keys.CTRL if m & Qt.ControlModifier else 0) | (keys.SHIFT if m & Qt.ShiftModifier else 0) |
                (keys.ALT if m & Qt.AltModifier else 0) | (keys.WIN if m & Qt.MetaModifier else 0))
        self.setText(keys.label(keys.combo_id(mods, name), language()))
        self.recorded.emit(mods, name)


class ActionPicker(QDialog):
    """Choose what one key does: categories on the left, actions on the right."""

    def __init__(self, parent, index, current):
        super().__init__(parent)
        self.setWindowTitle(T("pick_title", n=index + 1))
        self.resize(720, 480)
        self.result_id = current
        lang = language()
        lay = QVBoxLayout(self)
        body = QHBoxLayout()
        lay.addLayout(body, 1)
        self.cats = QListWidget()
        self.cats.setFixedWidth(200)
        body.addWidget(self.cats)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        self.desc = QLabel()
        self.desc.setObjectName("Hint")
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)

        groups = [("special", [(a, keys.label(a, lang)) for a in ("none", "lights", "fun2")]),
                  ("fkeys_high", [(f"key:{k.name}", k.name) for k in keys.KEY_GROUPS["fkeys_high"]]),
                  ("media", [(f"media:{n}", keys.label(f"media:{n}", lang)) for n in keys.MEDIA]),
                  ("shortcuts", [(f"sc:{n}", f"{keys.label('sc:' + n, lang)}   ({keys.shortcut_text('sc:' + n, lang)})")
                                 for n in keys.SHORTCUTS])]
        for g in ("fkeys", "letters", "digits", "editing", "navigation", "system", "symbols", "numpad"):
            groups.append((g, [(f"key:{k.name}", k.de if lang == "de" else k.en) for k in keys.KEY_GROUPS[g]]))

        self.lists = []
        select_cat = 0
        for ci, (cat, items) in enumerate(groups):
            self.cats.addItem(T(f"cat_{cat}"))
            lw = QListWidget()
            for aid, text in items:
                it = QListWidgetItem(text)
                it.setData(Qt.UserRole, aid)
                lw.addItem(it)
                if aid == current:
                    lw.setCurrentItem(it)
                    select_cat = ci
            lw.itemClicked.connect(self._picked)
            lw.itemDoubleClicked.connect(lambda _: self.accept())
            self.stack.addWidget(lw)
            self.lists.append(lw)

        # own shortcut
        self.cats.addItem(T("cat_combo"))
        combo = QWidget()
        cl = QVBoxLayout(combo)
        hint = QLabel(T("combo_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        cl.addWidget(hint)
        self.recorder = ComboRecorder()
        cl.addWidget(self.recorder)
        grid = QGridLayout()
        self.mod_boxes = {}
        for i, (bit, name) in enumerate(keys.MOD_NAMES[lang]):
            cb = QCheckBox(name)
            cb.toggled.connect(self._combo_changed)
            grid.addWidget(cb, 0, i)
            self.mod_boxes[bit] = cb
        cl.addLayout(grid)
        row = QHBoxLayout()
        row.addWidget(QLabel(T("combo_key")))
        self.key_box = QComboBox()
        for k in keys.KEYS_BY_NAME.values():
            self.key_box.addItem(k.de if lang == "de" else k.en, k.name)
        self.key_box.currentIndexChanged.connect(self._combo_changed)
        row.addWidget(self.key_box, 1)
        cl.addLayout(row)
        cl.addStretch()
        self.recorder.recorded.connect(self._recorded)
        self.stack.addWidget(combo)
        self.combo_index = len(groups)
        if str(current).startswith("combo:"):
            select_cat = self.combo_index
            mods, _, name = current[6:].partition(":")
            self._recorded(int(mods), name)

        self.cats.currentRowChanged.connect(self._cat_changed)
        self.cats.setCurrentRow(select_cat)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(T("cancel"))
        ok = QPushButton(T("ok"))
        ok.setObjectName("Primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)
        self._describe(current)

    def _cat_changed(self, row):
        self.stack.setCurrentIndex(row)
        if row == self.combo_index:
            self._combo_changed()

    def _picked(self, item):
        self.result_id = item.data(Qt.UserRole)
        self._describe(self.result_id)

    def _recorded(self, mods, name):
        for bit, cb in self.mod_boxes.items():
            cb.blockSignals(True)
            cb.setChecked(bool(mods & bit))
            cb.blockSignals(False)
        i = self.key_box.findData(name)
        if i >= 0:
            self.key_box.blockSignals(True)
            self.key_box.setCurrentIndex(i)
            self.key_box.blockSignals(False)
        self._combo_changed()

    def _combo_changed(self, *_):
        mods = sum(bit for bit, cb in self.mod_boxes.items() if cb.isChecked())
        name = self.key_box.currentData()
        if name:
            self.result_id = keys.combo_id(mods, name)
            self.recorder.setText(keys.label(self.result_id, language()))
            self._describe(self.result_id)

    def _describe(self, aid):
        kind = str(aid).partition(":")[0]
        if kind in ("none", "lights", "fun2"):
            self.desc.setText(T(f"desc_{kind}"))
        else:
            try:
                extra = keys.shortcut_text(aid, language())
                self.desc.setText(keys.label(aid, language()) + (f"  =  {extra}" if extra else ""))
            except Exception:
                self.desc.setText("")


class ApplyDialog(QDialog):
    """'Changing': how long it takes and that the pad must stay plugged in."""

    def __init__(self, parent, seconds=2):
        super().__init__(parent)
        self.setWindowTitle(T("apply_title"))
        self.setModal(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        self.text = QLabel(T("apply_wait", s=seconds))
        self.text.setWordWrap(True)
        lay.addWidget(self.text)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        self.button = QPushButton(T("close"))
        self.button.setEnabled(False)
        self.button.clicked.connect(self.accept)
        lay.addWidget(self.button, 0, Qt.AlignRight)
        self._start = time.monotonic()
        self._expected = max(1.0, seconds)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self._finished = False

    def _tick(self):
        if self._finished:
            return
        frac = (time.monotonic() - self._start) / self._expected
        self.bar.setValue(int(95 * (1 - 1 / (1 + 2 * frac))))   # creeps towards 95 %

    def finish(self, ok, text):
        self._finished = True
        self._timer.stop()
        self.bar.setValue(100 if ok else self.bar.value())
        self.text.setText(text)
        self.button.setEnabled(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.show()
        if ok:
            QTimer.singleShot(1400, self.accept)

    def reject(self):     # Esc / close only once it is done
        if self._finished:
            super().reject()


def fmt_duration(seconds):
    if seconds is None:
        return "..."
    seconds = max(0, int(round(seconds)))
    return T("sec", n=seconds) if seconds < 90 else T("min", n=round(seconds / 60))


class ProgressDialog(QDialog):
    """Progress with time left and a Cancel button (download and flashing)."""
    cancel_requested = Signal()

    def __init__(self, parent, title, confirm_cancel=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.confirm_cancel = confirm_cancel
        lay = QVBoxLayout(self)
        head = QLabel(title)
        head.setObjectName("CardTitle")
        lay.addWidget(head)
        self.stage = QLabel(T("prog_starting"))
        self.stage.setWordWrap(True)
        lay.addWidget(self.stage)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        self.left = QLabel("")
        self.left.setObjectName("Hint")
        lay.addWidget(self.left)
        warn = QLabel(T("prog_no_unplug"))
        warn.setObjectName("Note")
        lay.addWidget(warn)
        row = QHBoxLayout()
        row.addStretch()
        self.cancel = QPushButton(T("cancel"))
        self.cancel.setObjectName("Danger")
        self.cancel.clicked.connect(self._cancel)
        row.addWidget(self.cancel)
        lay.addLayout(row)
        self.done_ = False

    def set_stage(self, text):
        self.stage.setText(text)

    def set_progress(self, frac, seconds_left):
        self.bar.setValue(int(max(0.0, min(1.0, frac)) * 1000))
        self.left.setText(T("prog_left", t=fmt_duration(seconds_left)) if seconds_left is not None else "")

    def _cancel(self):
        if self.done_:
            self.accept()
            return
        if self.confirm_cancel and not ask(self, self.confirm_cancel):
            return
        self.cancel.setEnabled(False)
        self.cancel_requested.emit()

    def finish(self, text):
        self.done_ = True
        self.stage.setText(text)
        self.left.setText("")
        self.cancel.setEnabled(True)
        self.cancel.setText(T("close"))
        self.cancel.setObjectName("")
        self.cancel.style().unpolish(self.cancel)
        self.cancel.style().polish(self.cancel)

    def reject(self):     # Esc behaves like the Cancel button
        self._cancel()
