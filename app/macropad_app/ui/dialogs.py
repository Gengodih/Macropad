"""Dialogs: choosing a key's action, the "Changing" popup, update/flash progress."""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from .. import config, keys
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
    """Choose what one key does: categories on the left, actions on the right.

    mode: "key" (normal key), "layer2" (no layer / light keys), "sub" (part of a
    tap/hold key: pad keys, macros, microphone), "keys_only" (a macro step).
    draft: the settings being edited (new macros / tap-hold keys are added to it)."""

    def __init__(self, parent, index, current, draft=None, mode="key", title=None):
        super().__init__(parent)
        self.setWindowTitle(title or T("pick_title", n=index + 1))
        self.resize(760, 500)
        self.result_id = current
        self.draft = draft
        self.mode = mode
        lang = language()
        names = config.action_names(draft) if draft else {}
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

        special = ("none", "lights", "fun2") if mode == "key" else ("none",)
        groups = []
        if mode != "keys_only":
            groups.append(("special", [(a, keys.label(a, lang)) for a in special]))
            more = []
            if mode == "key":
                more.append(("layer", keys.label("layer", lang)))
            more.append(("app:mic_mute", keys.label("app:mic_mute", lang)))
            if draft:
                for rid, m in draft["macros"].items():
                    more.append((f"macro:{rid}", "\u25B6  " + T("macro_item", name=m["name"])))
                if mode != "sub":
                    for rid, m in draft["multi"].items():
                        more.append((f"multi:{rid}", "\u25CE  " + T("multi_item", name=m["name"])))
                more += [("+macro", "\uFF0B  " + T("new_macro")), ("+open", "\uFF0B  " + T("new_open")),
                         ("+text", "\uFF0B  " + T("new_text"))]
                if mode != "sub":
                    more.append(("+multi", "\uFF0B  " + T("new_multi")))
            groups.append(("app", more))
        groups += [
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

    def accept(self):
        """The "+ new ..." entries open their editor first."""
        rid = self.result_id
        if isinstance(rid, str) and rid.startswith("+") and self.draft is not None:
            if rid == "+multi":
                d = MultiEditor(self, self.draft)
            else:
                d = MacroEditor(self, self.draft, preset=rid[1:])
            if not d.exec():
                return
            self.result_id = d.action_id
        super().accept()

    def _describe(self, aid):
        kind = str(aid).partition(":")[0]
        if kind in ("none", "lights", "fun2", "layer"):
            self.desc.setText(T(f"desc_{kind}"))
        elif kind in ("app", "macro", "multi") or str(aid).startswith("+"):
            key = {"app": "desc_mic", "macro": "desc_macro", "multi": "desc_multi"}.get(kind)
            self.desc.setText(T(key) if key else T("desc_" + str(aid)[1:]))
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


# ---------------------------------------------------------------------------
#  Macros, tap / hold keys, profiles
# ---------------------------------------------------------------------------
def _buttons(dialog, layout, ok_text=None):
    row = QHBoxLayout()
    row.addStretch()
    cancel = QPushButton(T("cancel"))
    ok = QPushButton(ok_text or T("ok"))
    ok.setObjectName("Primary")
    cancel.clicked.connect(dialog.reject)
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    layout.addLayout(row)
    return ok


def step_text(step) -> str:
    """One macro step as a line of text."""
    t = step["type"]
    if t == "keys":
        return "\u2328  " + keys.label(step["action"], language())
    if t == "text":
        text = step["text"].replace("\n", " \u21B5 ")
        return "\u270E  " + T("step_text", text=text[:60] + ("\u2026" if len(text) > 60 else ""))
    if t == "open":
        return "\u2197  " + T("step_open", target=step["target"])
    return "\u23F1  " + T("step_delay", ms=step["ms"])


class TextStepDialog(QDialog):
    def __init__(self, parent, text=""):
        super().__init__(parent)
        self.setWindowTitle(T("new_text"))
        self.resize(480, 300)
        lay = QVBoxLayout(self)
        hint = QLabel(T("text_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        self.edit = QPlainTextEdit(text)
        lay.addWidget(self.edit, 1)
        _buttons(self, lay)

    def value(self):
        return self.edit.toPlainText()[:2000]


class OpenStepDialog(QDialog):
    def __init__(self, parent, target=""):
        super().__init__(parent)
        self.setWindowTitle(T("new_open"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        hint = QLabel(T("open_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        row = QHBoxLayout()
        self.edit = QLineEdit(target)
        self.edit.setPlaceholderText("https://...  /  C:\\Programs\\...")
        row.addWidget(self.edit, 1)
        browse = QPushButton(T("browse"))
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        lay.addLayout(row)
        _buttons(self, lay)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, T("new_open"), "", T("open_filter"))
        if path:
            self.edit.setText(path.replace("/", "\\") if "\\" in path or ":" in path[:3] else path)

    def value(self):
        return self.edit.text().strip()[:500]


class MacroEditor(QDialog):
    """A macro: several steps one after another (keys, text, open, pause).
    preset: "macro" (empty), "open" or "text" (starts with that one step)."""

    def __init__(self, parent, draft, rid=None, preset="macro"):
        super().__init__(parent)
        self.draft = draft
        self.rid = rid
        self.action_id = None
        old = draft["macros"].get(rid) if rid else None
        self.steps = [dict(s) for s in old["steps"]] if old else []
        self.setWindowTitle(T("macro_title"))
        self.resize(620, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(T("macro_name")))
        self.name = QLineEdit(old["name"] if old else "")
        self.name.setMaxLength(23)
        lay.addWidget(self.name)
        hint = QLabel(T("macro_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self._edit())
        body.addWidget(self.list, 1)
        side = QVBoxLayout()
        for text, fn in ((T("add_keys"), self._add_keys), (T("add_text"), self._add_text),
                         (T("add_open"), self._add_open), (T("add_delay"), self._add_delay)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            side.addWidget(b)
        side.addSpacing(12)
        for text, fn in ((T("step_edit"), self._edit), (T("step_up"), lambda: self._move(-1)),
                         (T("step_down"), lambda: self._move(1)), (T("step_remove"), self._remove)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            side.addWidget(b)
        side.addStretch()
        body.addLayout(side)
        lay.addLayout(body, 1)
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel(T("delay_ms")))
        self.delay = QSpinBox()
        self.delay.setRange(10, 10000)
        self.delay.setSingleStep(50)
        self.delay.setValue(500)
        delay_row.addWidget(self.delay)
        delay_row.addStretch()
        lay.addLayout(delay_row)
        _buttons(self, lay, T("save"))
        if not old and preset == "open":
            self.name.setText(T("default_open_name"))
            if not self._add_open():
                self.name.setText("")
        elif not old and preset == "text":
            self.name.setText(T("default_text_name"))
            if not self._add_text():
                self.name.setText("")
        self._fill()

    def _fill(self, select=None):
        self.list.clear()
        for st in self.steps:
            self.list.addItem(step_text(st))
        if select is not None and 0 <= select < len(self.steps):
            self.list.setCurrentRow(select)

    def _insert(self, step):
        row = self.list.currentRow()
        pos = row + 1 if row >= 0 else len(self.steps)
        if len(self.steps) >= config.MAX_STEPS:
            info(self, T("macro_full", n=config.MAX_STEPS))
            return False
        self.steps.insert(pos, step)
        self._fill(pos)
        return True

    def _add_keys(self):
        d = ActionPicker(self, 0, "key:F13", mode="keys_only", title=T("add_keys"))
        if d.exec() and keys.is_pad_action(d.result_id):
            return self._insert({"type": "keys", "action": d.result_id})
        return False

    def _add_text(self):
        d = TextStepDialog(self)
        if d.exec() and d.value():
            return self._insert({"type": "text", "text": d.value()})
        return False

    def _add_open(self):
        d = OpenStepDialog(self)
        if d.exec() and d.value():
            return self._insert({"type": "open", "target": d.value()})
        return False

    def _add_delay(self):
        return self._insert({"type": "delay", "ms": self.delay.value()})

    def _edit(self):
        row = self.list.currentRow()
        if row < 0:
            return
        st = self.steps[row]
        if st["type"] == "keys":
            d = ActionPicker(self, 0, st["action"], mode="keys_only", title=T("add_keys"))
            if d.exec() and keys.is_pad_action(d.result_id):
                st["action"] = d.result_id
        elif st["type"] == "text":
            d = TextStepDialog(self, st["text"])
            if d.exec() and d.value():
                st["text"] = d.value()
        elif st["type"] == "open":
            d = OpenStepDialog(self, st["target"])
            if d.exec() and d.value():
                st["target"] = d.value()
        else:
            st["ms"] = self.delay.value()
        self._fill(row)

    def _move(self, delta):
        row = self.list.currentRow()
        new = row + delta
        if row < 0 or not 0 <= new < len(self.steps):
            return
        self.steps[row], self.steps[new] = self.steps[new], self.steps[row]
        self._fill(new)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            del self.steps[row]
            self._fill(min(row, len(self.steps) - 1))

    def accept(self):
        name = config.clean_text(self.name.text(), 23)
        if not name:
            info(self, T("macro_need_name"))
            return
        if not self.steps:
            info(self, T("macro_need_step"))
            return
        if self.rid is None:
            if len(self.draft["macros"]) >= config.MAX_MACROS:
                info(self, T("macros_full", n=config.MAX_MACROS))
                return
            self.rid = config.new_ref_id(self.draft, "macro")
        self.draft["macros"][self.rid] = {"name": name, "steps": self.steps}
        self.action_id = f"macro:{self.rid}"
        super().accept()


class MultiEditor(QDialog):
    """One key, up to three jobs: tap, hold, double tap."""

    def __init__(self, parent, draft, rid=None):
        super().__init__(parent)
        self.draft = draft
        self.rid = rid
        self.action_id = None
        old = draft["multi"].get(rid) if rid else None
        self.values = {k: (old[k] if old else ("sc:copy" if k == "tap" else "none")) for k in ("tap", "hold", "double")}
        if not old:
            self.values["hold"] = "sc:paste"
        self.setWindowTitle(T("multi_title"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(T("macro_name")))
        self.name = QLineEdit(old["name"] if old else T("default_multi_name"))
        self.name.setMaxLength(23)
        lay.addWidget(self.name)
        hint = QLabel(T("multi_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        grid = QGridLayout()
        self.buttons = {}
        for row, k in enumerate(("tap", "hold", "double")):
            grid.addWidget(QLabel(T(f"multi_{k}")), row, 0)
            b = QPushButton()
            b.clicked.connect(lambda _=False, k=k: self._pick(k))
            grid.addWidget(b, row, 1)
            self.buttons[k] = b
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        _buttons(self, lay, T("save"))
        self._show()

    def _show(self):
        names = config.action_names(self.draft)
        for k, b in self.buttons.items():
            b.setText(keys.label(self.values[k], language(), names))

    def _pick(self, k):
        d = ActionPicker(self, 0, self.values[k], draft=self.draft, mode="sub", title=T(f"multi_{k}"))
        if d.exec() and config.multi_action_ok(self.draft, d.result_id):
            self.values[k] = d.result_id
            self._show()

    def accept(self):
        name = config.clean_text(self.name.text(), 23)
        if not name:
            info(self, T("macro_need_name"))
            return
        if self.rid is None:
            if len(self.draft["multi"]) >= config.MAX_MACROS:
                info(self, T("macros_full", n=config.MAX_MACROS))
                return
            self.rid = config.new_ref_id(self.draft, "multi")
        self.draft["multi"][self.rid] = {"name": name, **self.values}
        self.action_id = f"multi:{self.rid}"
        super().accept()


class ProfileDialog(QDialog):
    """Name of a profile and the programs it is for."""

    def __init__(self, parent, profile=None, running=()):
        super().__init__(parent)
        self.setWindowTitle(T("profile_title"))
        self.resize(520, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(T("profile_name")))
        self.name = QLineEdit(profile["name"] if profile else "")
        self.name.setMaxLength(30)
        lay.addWidget(self.name)
        hint = QLabel(T("profile_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        self.list = QListWidget()
        chosen = list(profile["programs"]) if profile else []
        for exe in list(dict.fromkeys(chosen + list(running))):
            self._add_item(exe, exe in chosen)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.extra = QLineEdit()
        self.extra.setPlaceholderText(T("profile_add_ph"))
        self.extra.returnPressed.connect(self._add_typed)
        row.addWidget(self.extra, 1)
        add = QPushButton(T("profile_add"))
        add.clicked.connect(self._add_typed)
        row.addWidget(add)
        browse = QPushButton(T("browse"))
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        lay.addLayout(row)
        _buttons(self, lay, T("save"))

    def _add_item(self, exe, checked):
        for i in range(self.list.count()):
            if self.list.item(i).text() == exe:
                self.list.item(i).setCheckState(Qt.Checked if checked else self.list.item(i).checkState())
                return
        it = QListWidgetItem(exe)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list.addItem(it)

    def _add_typed(self):
        exe = config.clean_program(self.extra.text())
        if exe:
            self._add_item(exe, True)
            self.extra.clear()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, T("profile_add"), "", T("exe_filter"))
        exe = config.clean_program(path)
        if exe:
            self._add_item(exe, True)

    def accept(self):
        if not config.clean_text(self.name.text(), 30):
            info(self, T("profile_need_name"))
            return
        super().accept()

    def value(self):
        progs = [self.list.item(i).text() for i in range(self.list.count())
                 if self.list.item(i).checkState() == Qt.Checked]
        return config.clean_text(self.name.text(), 30), progs
