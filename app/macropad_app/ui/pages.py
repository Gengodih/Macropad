"""The pages of the app (one per menu entry)."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QColorDialog, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton, QScrollArea,
                               QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget, QCheckBox)

from .. import MAKER, VERSION, config, keys, paths
from ..i18n import T, language
from . import dialogs, theme
from .scenes import OptionsPanel, PreviewTile
from .widgets import Card, KeyCap, KnobIcon, Swatch, ToggleSwitch, label


def palette_colour(i) -> QColor:
    """Screen colour of the pad's named light colours (same hues as the firmware)."""
    hues = [0, 4550, 6900, 10000, 15500, 21845, 27300, 32768, 37300, 42800, 46400, 51900, 55500, 59200, 62800, 0]
    if i == 15:
        return QColor("white")
    return QColor.fromHsvF(hues[i] / 65536.0, 1.0, 1.0)


COLOUR_NAMES = [("Red", "Rot"), ("Orange", "Orange"), ("Amber", "Bernstein"), ("Yellow", "Gelb"),
                ("Lime", "Limette"), ("Green", "Grün"), ("Mint", "Mint"), ("Cyan", "Cyan"),
                ("Sky blue", "Himmelblau"), ("Blue", "Blau"), ("Indigo", "Indigo"), ("Purple", "Lila"),
                ("Magenta", "Magenta"), ("Pink", "Pink"), ("Rose", "Rosa"), ("White", "Weiß")]


class Page(QWidget):
    """Base: a scrollable column of cards over the background."""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setAttribute(Qt.WA_TranslucentBackground)
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(28, 6, 28, 12)
        self.col.setSpacing(14)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.build()
        self.col.addStretch(1)
        self.refresh()

    @property
    def draft(self):
        return self.ctx.draft

    def build(self):
        pass

    def refresh(self):
        pass


# ---------------------------------------------------------------------------
class HomePage(Page):
    def build(self):
        card = Card()
        card.add(label(T("home_sub", maker=MAKER), "CardTitle"))
        card.add(label(T("home_hint"), "Hint"))
        self.col.addWidget(card)
        self.music = Card(T("now_playing"))
        self.song = self.music.add(label("", wrap=True))
        self.col.addWidget(self.music)

    def refresh(self):
        player, title, artist = self.ctx.now_playing
        if not self.ctx.media_available:
            self.song.setText(T("music_off"))
        elif title:
            self.song.setText(f"<b>{_esc(title)}</b><br><span style='color:{theme.DIM}'>{_esc(artist)}"
                              f"{'  ·  ' + _esc(player) if player else ''}</span>")
        else:
            self.song.setText(f"<span style='color:{theme.DIM}'>{T('nothing_playing')}</span>")


def _esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
class KeysPage(Page):
    """Keys of the normal layout, of layer 2, or of a profile (for some programs)."""

    def build(self):
        self.view = "base"          # "base", "layer2" or a profile index (int)
        card = Card(T("keys_title"))
        card.add(label(T("keys_hint"), "Hint"))
        # profile row
        row = QHBoxLayout()
        row.addWidget(label(T("profile_label"), wrap=False))
        self.profile_box = QComboBox()
        self.profile_box.setMinimumWidth(220)
        self.profile_box.currentIndexChanged.connect(self._profile_chosen)
        row.addWidget(self.profile_box)
        self.new_profile = QPushButton(T("profile_new"))
        self.new_profile.clicked.connect(self._add_profile)
        self.edit_profile = QPushButton(T("profile_programs"))
        self.edit_profile.clicked.connect(self._edit_profile)
        self.del_profile = QPushButton(T("profile_delete"))
        self.del_profile.clicked.connect(self._delete_profile)
        for b in (self.new_profile, self.edit_profile, self.del_profile):
            row.addWidget(b)
        row.addStretch()
        card.layout_.addLayout(row)
        self.profile_info = card.add(label("", "Note"))
        # layer row (normal layout only)
        self.layer_row = QWidget()
        lr = QHBoxLayout(self.layer_row)
        lr.setContentsMargins(0, 0, 0, 0)
        self.layer1 = QRadioButton(T("layer_1"))
        self.layer2 = QRadioButton(T("layer_2"))
        group = QButtonGroup(self)
        group.addButton(self.layer1)
        group.addButton(self.layer2)
        self.layer2.toggled.connect(self._layer_chosen)
        lr.addWidget(self.layer1)
        lr.addWidget(self.layer2)
        lr.addStretch()
        card.add(self.layer_row)
        self.layer_note = card.add(label("", "Note"))

        grid = QGridLayout()
        grid.setSpacing(10)
        self.caps = []
        for i in range(keys.KEY_COUNT):
            cap = KeyCap(i)
            cap.clicked.connect(lambda _=False, i=i: self.pick(i))
            grid.addWidget(cap, i // 5, i % 5)
            self.caps.append(cap)
        holder = QWidget()
        holder.setLayout(grid)
        holder.setMaximumWidth(620)
        holder.setMinimumHeight(270)
        centre = QHBoxLayout()
        centre.addStretch()
        centre.addWidget(holder, 4)
        centre.addStretch()
        card.layout_.addLayout(centre)
        row = QHBoxLayout()
        self.fallback = label("", "Note")
        row.addWidget(self.fallback, 1)
        reset = QPushButton(T("keys_reset"))
        reset.clicked.connect(self.reset)
        row.addWidget(reset)
        card.layout_.addLayout(row)
        self.col.addWidget(card)

        # macros and tap / hold keys
        mc = Card(T("macros_title"))
        mc.add(label(T("macros_hint"), "Hint"))
        self.macro_list = QListWidget()
        self.macro_list.setMinimumHeight(120)
        self.macro_list.itemDoubleClicked.connect(lambda _: self._edit_macro())
        mc.add(self.macro_list)
        row = QHBoxLayout()
        for text, fn in ((T("new_macro"), self._new_macro), (T("new_multi"), self._new_multi),
                         (T("macro_edit"), self._edit_macro), (T("macro_delete"), self._delete_macro)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        mc.layout_.addLayout(row)
        self.col.addWidget(mc)

        knob = Card(T("knob"))
        row = QHBoxLayout()
        icon = KnobIcon()
        icon.setFixedSize(64, 64)
        row.addWidget(icon)
        texts = QVBoxLayout()
        texts.addWidget(label(T("knob_press")))
        texts.addWidget(label(T("knob_turn")))
        row.addLayout(texts, 1)
        self.pc = QRadioButton(T("knob_pc"))
        self.app = QRadioButton(T("knob_app"))
        group = QButtonGroup(self)
        group.addButton(self.pc)
        group.addButton(self.app)
        self.pc.toggled.connect(self._knob)
        row.addWidget(self.pc)
        row.addSpacing(10)
        row.addWidget(self.app)
        knob.layout_.addLayout(row)
        knob.add(label(T("knob_note"), "Note"))
        self.col.addWidget(knob)

    # ----- which layout is shown -----------------------------------------------
    def _layout(self):
        if self.view == "layer2":
            return self.draft["keys2"]
        if isinstance(self.view, int):
            return self.draft["profiles"][self.view]["keys"]
        return self.draft["keys"]

    def _profile_chosen(self, index):
        if index <= 0:
            self.view = "layer2" if self.layer2.isChecked() else "base"
        else:
            self.view = index - 1
        self.refresh()

    def _layer_chosen(self):
        if not isinstance(self.view, int):
            self.view = "layer2" if self.layer2.isChecked() else "base"
            self.refresh()

    def refresh(self):
        lang = language()
        d = self.draft
        if isinstance(self.view, int) and self.view >= len(d["profiles"]):
            self.view = "base"
        names = config.action_names(d)
        # profile box
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        self.profile_box.addItem(T("profile_default"))
        for p in d["profiles"]:
            self.profile_box.addItem(p["name"])
        self.profile_box.setCurrentIndex(self.view + 1 if isinstance(self.view, int) else 0)
        self.profile_box.blockSignals(False)
        is_profile = isinstance(self.view, int)
        self.edit_profile.setEnabled(is_profile)
        self.del_profile.setEnabled(is_profile)
        self.new_profile.setEnabled(len(d["profiles"]) < config.MAX_PROFILES)
        active = getattr(self.ctx, "active_profile", None)
        if is_profile:
            progs = ", ".join(d["profiles"][self.view]["programs"]) or T("profile_no_programs")
            self.profile_info.setText(T("profile_for", programs=progs))
        else:
            now = d["profiles"][active]["name"] if active is not None and active < len(d["profiles"]) else None
            self.profile_info.setText(T("profile_active", name=now) if now else T("profile_none_active"))
        self.layer_row.setVisible(not is_profile)
        for b in (self.layer1, self.layer2):
            b.blockSignals(True)
        self.layer2.setChecked(self.view == "layer2")
        self.layer1.setChecked(self.view != "layer2")
        for b in (self.layer1, self.layer2):
            b.blockSignals(False)
        has_layer_key = "layer" in d["keys"]
        self.layer_note.setVisible(not is_profile)
        self.layer_note.setText(T("layer_note") if has_layer_key else T("layer_need_key"))
        # keys
        layout = self._layout()
        notes = []
        for i, cap in enumerate(self.caps):
            aid = layout[i]
            sub = keys.shortcut_text(aid, lang) if aid.startswith("sc:") else ""
            if aid.startswith("media:") or aid in ("lights",):
                sub = keys.label(aid, lang)
            if aid.startswith(("macro:", "multi:", "app:")):
                sub = {"macro": T("sub_macro"), "multi": T("sub_multi"), "app": T("sub_app")}[aid.split(":")[0]]
            fallback = self.view == "base" and (
                (i == keys.LIGHTS_KEY and aid != "lights") or (i == keys.FUN2_KEY and aid != "fun2"))
            cap.set_content(keys.short_label(aid, lang, names), sub, badge=fallback)
            if fallback:
                notes.append(T("fallback_note", what=T("what_lights" if i == keys.LIGHTS_KEY else "what_fun2")))
        if any(a.startswith(("macro:", "multi:", "app:")) for a in layout):
            notes.append(T("app_keys_note"))
        self.fallback.setText("\u25CF " + "  ".join(dict.fromkeys(notes)) if notes else "")
        self.fallback.setStyleSheet(f"color: {theme.YELLOW};" if notes else "")
        # macros list
        self.macro_list.clear()
        for rid, m in d["macros"].items():
            it = QListWidgetItem("\u25B6  " + T("macro_item", name=m["name"]) + f"   ({len(m['steps'])})")
            it.setData(Qt.UserRole, f"macro:{rid}")
            self.macro_list.addItem(it)
        for rid, m in d["multi"].items():
            it = QListWidgetItem("\u25CE  " + T("multi_item", name=m["name"]))
            it.setData(Qt.UserRole, f"multi:{rid}")
            self.macro_list.addItem(it)
        on_app = d["knob_target"] == "app"
        self.pc.blockSignals(True)
        self.app.blockSignals(True)
        self.app.setChecked(on_app)
        self.pc.setChecked(not on_app)
        self.pc.blockSignals(False)
        self.app.blockSignals(False)

    def pick(self, i):
        layout = self._layout()
        mode = "layer2" if self.view == "layer2" else "key"
        d = dialogs.ActionPicker(self, i, layout[i], draft=self.draft, mode=mode)
        if d.exec() and config.action_ok(self.draft, d.result_id):
            if mode == "layer2" and d.result_id in ("layer", "lights", "fun2"):
                return
            layout[i] = d.result_id
            self.ctx.changed()
            self.refresh()

    def reset(self):
        if not dialogs.ask(self, T("keys_reset_q")):
            return
        layout = self._layout()
        if self.view == "layer2":
            fresh = ["none"] * keys.KEY_COUNT
        elif isinstance(self.view, int):
            fresh = list(self.draft["keys"])
        else:
            fresh = list(keys.DEFAULT_LAYOUT)
        layout[:] = fresh
        self.ctx.changed()
        self.refresh()

    # ----- profiles -------------------------------------------------------------
    def _add_profile(self):
        from .. import winsys
        d = dialogs.ProfileDialog(self, None, winsys.running_programs())
        if d.exec():
            name, progs = d.value()
            self.draft["profiles"].append({"name": name, "programs": progs, "keys": list(self.draft["keys"])})
            self.view = len(self.draft["profiles"]) - 1
            self.ctx.changed()
            self.refresh()

    def _edit_profile(self):
        if not isinstance(self.view, int):
            return
        from .. import winsys
        p = self.draft["profiles"][self.view]
        d = dialogs.ProfileDialog(self, p, winsys.running_programs())
        if d.exec():
            p["name"], p["programs"] = d.value()
            self.ctx.changed()
            self.refresh()

    def _delete_profile(self):
        if isinstance(self.view, int) and dialogs.ask(
                self, T("profile_delete_q", name=self.draft["profiles"][self.view]["name"])):
            del self.draft["profiles"][self.view]
            self.view = "base"
            self.ctx.changed()
            self.refresh()

    # ----- macros ---------------------------------------------------------------
    def _new_macro(self):
        if dialogs.MacroEditor(self, self.draft).exec():
            self.ctx.changed()
            self.refresh()

    def _new_multi(self):
        if dialogs.MultiEditor(self, self.draft).exec():
            self.ctx.changed()
            self.refresh()

    def _selected_ref(self):
        it = self.macro_list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _edit_macro(self):
        aid = self._selected_ref()
        if not aid:
            return
        kind, rid = aid.split(":", 1)
        d = dialogs.MacroEditor(self, self.draft, rid) if kind == "macro" else dialogs.MultiEditor(self, self.draft, rid)
        if d.exec():
            self.ctx.changed()
            self.refresh()

    def _delete_macro(self):
        aid = self._selected_ref()
        if not aid:
            return
        kind, rid = aid.split(":", 1)
        store = self.draft["macros" if kind == "macro" else "multi"]
        if not dialogs.ask(self, T("macro_delete_q", name=store[rid]["name"])):
            return
        del store[rid]
        # keys that used it: back to their default / nothing
        self.ctx.draft = config.validate(self.ctx.draft)
        self.ctx.changed(refresh_pages=True)

    def _knob(self):
        self.draft["knob_target"] = "pc" if self.pc.isChecked() else "app"
        self.ctx.changed()


# ---------------------------------------------------------------------------
class LedsPage(Page):
    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        # left: modes, brightness, colour
        left = Card(T("leds_modes"))
        left.add(label(T("leds_modes_hint"), "Note"))
        self.modes = QListWidget()
        self.modes.setMinimumHeight(250)
        self.modes.itemChanged.connect(self._mode_ticked)
        self.modes.currentItemChanged.connect(self._mode_selected)
        left.add(self.modes)
        left.add(label(T("leds_brightness")))
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(10, 100)
        self.bright.setSingleStep(10)
        self.bright.setPageStep(10)
        self.bright.valueChanged.connect(self._bright)
        self.bright_value = label("", "Hint", wrap=False)
        br = QHBoxLayout()
        br.addWidget(self.bright, 1)
        br.addWidget(self.bright_value)
        left.layout_.addLayout(br)
        left.add(label(T("leds_colour")))
        sw = QGridLayout()
        sw.setSpacing(6)
        self.swatches = []
        group = QButtonGroup(self)
        group.setExclusive(True)
        for i in range(config.COLOUR_COUNT):
            s = Swatch(palette_colour(i), COLOUR_NAMES[i][1 if language() == "de" else 0])
            group.addButton(s)
            s.clicked.connect(lambda _=False, i=i: self._colour(i))
            sw.addWidget(s, i // 8, i % 8)
            self.swatches.append(s)
        left.layout_.addLayout(sw)
        row.addWidget(left, 1)

        # right: own schemes
        self.right = Card("")
        self.schemes_title = label("", "CardTitle")
        self.right.add(self.schemes_title)
        self.scheme_list = QListWidget()
        self.scheme_list.setMaximumHeight(130)
        self.scheme_list.currentRowChanged.connect(self._scheme_selected)
        self.right.add(self.scheme_list)
        b = QHBoxLayout()
        self.new_btn = QPushButton(T("leds_new"))
        self.ren_btn = QPushButton(T("leds_rename"))
        self.del_btn = QPushButton(T("leds_delete"))
        self.del_btn.setObjectName("Danger")
        self.new_btn.clicked.connect(self._new)
        self.ren_btn.clicked.connect(self._rename)
        self.del_btn.clicked.connect(self._delete)
        for w in (self.new_btn, self.ren_btn, self.del_btn):
            b.addWidget(w)
        self.right.layout_.addLayout(b)
        er = QHBoxLayout()
        er.addWidget(label(T("leds_effect"), wrap=False))
        self.effect = QComboBox()
        for e in config.EFFECTS:
            self.effect.addItem(T(f"fx_{e}"), e)
        self.effect.currentIndexChanged.connect(self._effect)
        er.addWidget(self.effect, 1)
        self.right.layout_.addLayout(er)
        self.scheme_hint = self.right.add(label(T("leds_click_key"), "Note"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.caps = []
        for i in range(keys.KEY_COUNT):
            cap = KeyCap(i)
            cap.setMinimumSize(52, 46)
            cap.clicked.connect(lambda _=False, i=i: self._key_colour(i))
            grid.addWidget(cap, i // 5, i % 5)
            self.caps.append(cap)
        self.right.layout_.addLayout(grid)
        self.fill_btn = QPushButton(T("leds_fill"))
        self.fill_btn.clicked.connect(self._fill)
        self.right.add(self.fill_btn)
        row.addWidget(self.right, 1)
        holder = QWidget()
        holder.setLayout(row)
        self.col.addWidget(holder)
        self._current_scheme = 0

    @property
    def lights(self):
        return self.draft["lights"]

    def refresh(self):
        li = self.lights
        self.modes.blockSignals(True)
        self.modes.clear()
        entries = [(m, T(f"mode_{m}"), True) for m in range(config.BUILTIN_MODES)]
        entries += [(config.MODE_CUSTOM + i, s["name"], False) for i, s in enumerate(li["schemes"])]
        entries.append((config.MODE_OFF, T("mode_6"), False))
        for mode, name, tickable in entries:
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, mode)
            if tickable:
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if li["builtin_enabled"][mode] else Qt.Unchecked)
            self.modes.addItem(it)
            if mode == li["mode"]:
                self.modes.setCurrentItem(it)
        self.modes.blockSignals(False)
        self.bright.blockSignals(True)
        self.bright.setValue(li["brightness"])
        self.bright.blockSignals(False)
        self.bright_value.setText(f"{li['brightness']} %")
        for i, s in enumerate(self.swatches):
            s.setChecked(i == li["colour"])
        # schemes
        self.schemes_title.setText(T("leds_schemes", n=len(li["schemes"])))
        self.scheme_list.blockSignals(True)
        self.scheme_list.clear()
        for s in li["schemes"]:
            self.scheme_list.addItem(s["name"])
        self._current_scheme = min(self._current_scheme, len(li["schemes"]) - 1)
        if self._current_scheme >= 0:
            self.scheme_list.setCurrentRow(self._current_scheme)
        self.scheme_list.blockSignals(False)
        self._show_scheme()

    def _show_scheme(self):
        li = self.lights
        has = 0 <= self._current_scheme < len(li["schemes"])
        for w in (self.ren_btn, self.del_btn, self.effect, self.fill_btn):
            w.setEnabled(has)
        self.new_btn.setEnabled(len(li["schemes"]) < config.MAX_SCHEMES)
        self.scheme_hint.setText(T("leds_click_key") if has else T("leds_no_scheme"))
        for i, cap in enumerate(self.caps):
            cap.setEnabled(has)
            colour = li["schemes"][self._current_scheme]["colours"][i] if has else None
            cap.set_content("", "", colour or "#2a2a38")
        if has:
            self.effect.blockSignals(True)
            self.effect.setCurrentIndex(config.EFFECTS.index(li["schemes"][self._current_scheme]["effect"]))
            self.effect.blockSignals(False)

    # --- edits ---
    def _mode_ticked(self, item):
        mode = item.data(Qt.UserRole)
        if 0 <= mode < config.BUILTIN_MODES:
            self.lights["builtin_enabled"][mode] = item.checkState() == Qt.Checked
            if not config.mode_available(self.draft, self.lights["mode"]):
                self.lights["mode"] = config.first_available_mode(self.draft)
            self.ctx.changed()
            self.refresh()

    def _mode_selected(self, item, _prev):
        if item is None:
            return
        mode = item.data(Qt.UserRole)
        if 0 <= mode < config.BUILTIN_MODES and not self.lights["builtin_enabled"][mode]:
            self.lights["builtin_enabled"][mode] = True     # choosing a mode puts it in the rotation
        self.lights["mode"] = mode
        self.ctx.changed()
        self.refresh()

    def _bright(self, v):
        v = max(10, min(100, round(v / 10) * 10))
        self.lights["brightness"] = v
        self.bright_value.setText(f"{v} %")
        self.ctx.changed()

    def _colour(self, i):
        self.lights["colour"] = i
        self.ctx.changed()

    def _scheme_selected(self, row):
        self._current_scheme = row
        self._show_scheme()

    def _new(self):
        li = self.lights
        if len(li["schemes"]) >= config.MAX_SCHEMES:
            dialogs.info(self, T("leds_max"))
            return
        name = dialogs.ask_text(self, T("leds_name_q"), T("new_scheme_name", n=len(li["schemes"]) + 1))
        if not name:
            return
        li["schemes"].append({"name": config.clean_text(name, 15) or "Scheme",
                              "effect": "static", "colours": list(config.DEFAULT_SCHEME_COLOURS)})
        self._current_scheme = len(li["schemes"]) - 1
        self.ctx.changed()
        self.refresh()

    def _rename(self):
        s = self.lights["schemes"][self._current_scheme]
        name = dialogs.ask_text(self, T("leds_name_q"), s["name"])
        if name:
            s["name"] = config.clean_text(name, 15) or s["name"]
            self.ctx.changed()
            self.refresh()

    def _delete(self):
        li = self.lights
        s = li["schemes"][self._current_scheme]
        if not dialogs.ask(self, T("leds_delete_q", name=s["name"])):
            return
        removed_mode = config.MODE_CUSTOM + self._current_scheme
        del li["schemes"][self._current_scheme]
        if li["mode"] == removed_mode:
            li["mode"] = config.first_available_mode(self.draft)
        elif li["mode"] > removed_mode:
            li["mode"] -= 1                       # the schemes after it moved up one place
        self._current_scheme = max(0, self._current_scheme - 1)
        self.ctx.changed()
        self.refresh()

    def _effect(self):
        self.lights["schemes"][self._current_scheme]["effect"] = self.effect.currentData()
        self.ctx.changed()

    def _pick_colour(self, start):
        c = QColorDialog.getColor(QColor(start), self, T("leds_title"))
        return c.name().lower() if c.isValid() else None

    def _key_colour(self, i):
        s = self.lights["schemes"][self._current_scheme]
        c = self._pick_colour(s["colours"][i])
        if c:
            s["colours"][i] = c
            self.ctx.changed()
            self._show_scheme()

    def _fill(self):
        s = self.lights["schemes"][self._current_scheme]
        c = self._pick_colour(s["colours"][0])
        if c:
            s["colours"] = [c] * keys.KEY_COUNT
            self.ctx.changed()
            self._show_scheme()


# ---------------------------------------------------------------------------
class LanguagePage(Page):
    def build(self):
        card = Card(T("lang_title"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        self.app_lang = QComboBox()
        self.pad_lang = QComboBox()
        for box in (self.app_lang, self.pad_lang):
            box.addItem("English", "en")
            box.addItem("Deutsch", "de")
            box.setMinimumWidth(220)
        grid.addWidget(label(T("lang_app"), wrap=False), 0, 0)
        grid.addWidget(self.app_lang, 0, 1)
        grid.addWidget(label(T("lang_pad"), wrap=False), 1, 0)
        grid.addWidget(self.pad_lang, 1, 1)
        grid.setColumnStretch(2, 1)
        card.layout_.addLayout(grid)
        card.add(label(T("lang_note"), "Note"))
        self.col.addWidget(card)
        self.app_lang.currentIndexChanged.connect(self._changed)
        self.pad_lang.currentIndexChanged.connect(self._changed)

    def refresh(self):
        for box, key in ((self.app_lang, "app_language"), (self.pad_lang, "pad_language")):
            box.blockSignals(True)
            box.setCurrentIndex(max(0, box.findData(self.draft[key])))
            box.blockSignals(False)

    def _changed(self):
        self.draft["app_language"] = self.app_lang.currentData()
        self.draft["pad_language"] = self.pad_lang.currentData()
        self.ctx.changed()


# ---------------------------------------------------------------------------
class DisplayPage(Page):
    """Animated background on/off, a catalog of live previews (click = choose),
    the chosen background's options right under its row, then brightness/music."""

    COLUMNS = 4
    FPS = 15

    def build(self):
        card = Card(T("disp_bg"))
        r = QHBoxLayout()
        self.anim = ToggleSwitch()
        r.addWidget(self.anim)
        r.addWidget(label(T("disp_anim")), 1)
        card.layout_.addLayout(r)
        self.anim_off_note = card.add(label(T("disp_anim_off"), "Note"))

        self.catalog = QWidget()
        self.catalog.setAttribute(Qt.WA_TranslucentBackground)
        self.cat_layout = QVBoxLayout(self.catalog)
        self.cat_layout.setContentsMargins(0, 4, 0, 0)
        self.cat_layout.setSpacing(8)
        self.tiles = {}
        self.rows = []
        names = config.BACKGROUNDS
        for start in range(0, len(names), self.COLUMNS):
            if names[start] == config.WIDGETS[0]:
                head = label(T("disp_widgets"), "CardTitle")
                head.setContentsMargins(0, 8, 0, 0)
                self.cat_layout.addWidget(head)
            row = QWidget()
            row.setAttribute(Qt.WA_TranslucentBackground)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(10)
            for name in names[start:start + self.COLUMNS]:
                tile = PreviewTile(name, T("bg_" + name))
                tile.clicked.connect(self._tile_clicked)
                self.tiles[name] = tile
                h.addWidget(tile, 1)
            for _ in range(self.COLUMNS - len(names[start:start + self.COLUMNS])):
                h.addStretch(1)
            self.rows.append(row)
            self.cat_layout.addWidget(row)

        self.panel = OptionsPanel()
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(18, OptionsPanel.NOTCH + 12, 18, 14)
        pl.setSpacing(8)
        self.panel_title = QLabel()
        self.panel_title.setObjectName("CardTitle")
        self.panel_desc = label("", "Hint")
        pl.addWidget(self.panel_title)
        pl.addWidget(self.panel_desc)
        self.panel_opts = QVBoxLayout()
        self.panel_opts.setSpacing(8)
        pl.addLayout(self.panel_opts)
        self.panel_hint = label(T("disp_try"), "Note")
        pl.addWidget(self.panel_hint)
        self.fw_note = label(T("disp_needs_fw"), "Note")
        self.fw_note.setStyleSheet("color: #fbbf24;")
        pl.addWidget(self.fw_note)
        self._panel_for = None
        self._opt_widgets = {}
        card.add(self.catalog)
        self.col.addWidget(card)

        screen = Card(T("disp_screen"))
        r = QHBoxLayout()
        r.addWidget(label(T("owner_name"), wrap=False))
        self.owner = QLineEdit()
        self.owner.setMaxLength(20)
        self.owner.setPlaceholderText(T("owner_ph"))
        self.owner.textEdited.connect(self._owner)
        r.addWidget(self.owner, 1)
        screen.layout_.addLayout(r)
        r = QHBoxLayout()
        self.music = ToggleSwitch()
        r.addWidget(self.music)
        r.addWidget(label(T("disp_music")), 1)
        screen.layout_.addLayout(r)
        screen.add(label(T("disp_brightness")))
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(1, 16)
        self.bright_value = label("", "Hint", wrap=False)
        r = QHBoxLayout()
        r.addWidget(self.bright, 1)
        r.addWidget(self.bright_value)
        screen.layout_.addLayout(r)
        screen.add(label(T("disp_note"), "Note"))
        self.col.addWidget(screen)

        self.anim.toggled.connect(self._changed)
        self.music.toggled.connect(self._changed)
        self.bright.valueChanged.connect(self._changed)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ----- live previews ------------------------------------------------------
    def _animate(self):
        want = self.isVisible() and self.draft["display"]["animation"]
        if want and not self._timer.isActive():
            self._timer.start(int(1000 / self.FPS))
        elif not want and self._timer.isActive():
            self._timer.stop()

    def showEvent(self, e):
        super().showEvent(e)
        self._animate()

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        colour = self.draft["lights"]["colour"]
        for tile in self.tiles.values():
            tile.scene.step(1.0 / self.FPS, colour)
            tile.update()
        self._place_notch()

    def set_level(self, level):
        for tile in self.tiles.values():
            tile.scene.set_level(level)

    def _tile_clicked(self, name):
        d = self.draft["display"]
        if d["background"] == name:
            self.tiles[name].scene.poke()          # chosen already: show how it reacts to a key
            self.ctx.background.poke()
            return
        d["background"] = name
        self.ctx.changed()
        self.refresh()

    # ----- options of the chosen background ----------------------------------
    def _build_options(self, name):
        def drop(w):
            w.hide()                  # gone at once, deleted a moment later
            w.setParent(None)
            w.deleteLater()

        while self.panel_opts.count():
            item = self.panel_opts.takeAt(0)
            if item.widget():
                drop(item.widget())
            elif item.layout():
                lay = item.layout()
                while lay.count():
                    w = lay.takeAt(0).widget()
                    if w:
                        drop(w)
                lay.deleteLater()
        self._opt_widgets = {}
        self.panel_title.setText(T("bg_" + name))
        self.panel_desc.setText(T("bgd_" + name))
        if name == "picture":
            self._picture_row()
        for key, default in config.BACKGROUND_OPTIONS[name].items():
            if key in config.TIMER_LIMITS:
                r = QHBoxLayout()
                r.addWidget(label(T(f"opt_timer_{key}"), wrap=False))
                sb = QSpinBox()
                sb.setRange(*config.TIMER_LIMITS[key])
                sb.setSuffix(" min")
                sb.valueChanged.connect(self._option_changed)
                r.addWidget(sb)
                r.addStretch()
                self.panel_opts.addLayout(r)
                self._opt_widgets[key] = sb
                continue
            if key == "season":
                r = QHBoxLayout()
                r.setSpacing(14)
                group = QButtonGroup(self.panel)
                buttons = {}
                for season in config.SEASONS:
                    b = QRadioButton(T("season_" + season))
                    group.addButton(b)
                    buttons[season] = b
                    r.addWidget(b)
                    b.toggled.connect(self._option_changed)
                r.addStretch()
                self.panel_opts.addLayout(r)
                self._opt_widgets[key] = buttons
            else:
                r = QHBoxLayout()
                sw = ToggleSwitch()
                sw.toggled.connect(self._option_changed)
                r.addWidget(sw)
                r.addWidget(label(T(f"opt_{name}_{key}")), 1)
                self.panel_opts.addLayout(r)
                self._opt_widgets[key] = sw
        self._panel_for = name

    def _option_changed(self, *_):
        d = self.draft["display"]
        name = self._panel_for
        if not name:
            return
        opts = d["options"][name]
        refit = name == "picture" and opts.get("fit") != self._opt_widgets["fit"].isChecked()
        for key, w in self._opt_widgets.items():
            if key == "season":
                for season, b in w.items():
                    if b.isChecked():
                        opts[key] = season
            elif key in config.TIMER_LIMITS:
                opts[key] = w.value()
            else:
                opts[key] = w.isChecked()
        self.ctx.changed()
        if refit:
            self._convert_picture(None)
        self.refresh()

    # ----- own picture ------------------------------------------------------------
    def _picture_row(self):
        r = QHBoxLayout()
        choose = QPushButton(T("pic_choose"))
        choose.setObjectName("Primary")
        choose.clicked.connect(self._choose_picture)
        r.addWidget(choose)
        self.pic_remove = QPushButton(T("pic_remove"))
        self.pic_remove.clicked.connect(self._remove_picture)
        r.addWidget(self.pic_remove)
        self.pic_name = label("", "Hint", wrap=False)
        r.addWidget(self.pic_name, 1)
        self.panel_opts.addLayout(r)
        self._show_picture_name()

    def _show_picture_name(self):
        from ..ui.scenes import live
        p = live.picture
        if not hasattr(self, "pic_name"):
            return
        try:
            self.pic_name.setText(T("pic_current", name=p.name, n=p.frames) if p else T("pic_none"))
            self.pic_remove.setEnabled(p is not None)
        except RuntimeError:          # the row was rebuilt meanwhile
            pass

    def _choose_picture(self):
        path, _ = QFileDialog.getOpenFileName(self, T("pic_choose"), "", T("pic_filter"))
        if path:
            self._convert_picture(path)

    def _convert_picture(self, path):
        from .. import picture
        from ..ui.scenes import live
        if path is None:                        # "fit" changed: convert the last file again
            path = picture.source()
            if not path:
                return
        try:
            pic = picture.convert(path, fit=self.draft["display"]["options"]["picture"]["fit"])
        except ValueError as e:
            dialogs.info(self, T("pic_failed", why=str(e)))
            return
        picture.save(pic, source=path)
        live.set_picture(pic)
        self.ctx.picture_changed()
        self._show_picture_name()

    def _remove_picture(self):
        from .. import picture
        from ..ui.scenes import live
        picture.remove()
        live.set_picture(None)
        self.ctx.picture_changed()
        self._show_picture_name()

    def _place_panel(self, name):
        names = list(config.BACKGROUNDS)
        row = self.rows[names.index(name) // self.COLUMNS]
        self.cat_layout.removeWidget(self.panel)
        self.cat_layout.insertWidget(self.cat_layout.indexOf(row) + 1, self.panel)
        self.panel.show()
        self._place_notch()

    def _place_notch(self):
        tile = self.tiles.get(self.draft["display"]["background"])
        if tile is None or not self.panel.isVisible():
            return
        x = tile.mapTo(self.catalog, tile.rect().center()).x() - self.panel.x()
        if abs(x - self.panel.notch_x) > 0.5:
            self.panel.notch_x = x
            self.panel.update()

    # ----- settings -----------------------------------------------------------
    def refresh(self):
        d = self.draft["display"]
        name = d["background"]
        if self.owner.text() != self.draft["owner_name"]:
            self.owner.setText(self.draft["owner_name"])
        for w in (self.anim, self.music, self.bright):
            w.blockSignals(True)
        self.anim.setChecked(d["animation"])
        self.music.setChecked(d["music"])
        self.bright.setValue(d["brightness"])
        self.bright_value.setText(f"{round(d['brightness'] / 16 * 100)} %")
        for w in (self.anim, self.music, self.bright):
            w.blockSignals(False)
        self.catalog.setVisible(d["animation"])
        self.anim_off_note.setVisible(not d["animation"])
        for n, tile in self.tiles.items():
            tile.set_selected(n == name)
            tile.scene.configure(n, d["options"])
        if self._panel_for != name:
            self._build_options(name)
        for key, w in self._opt_widgets.items():
            value = d["options"][name][key]
            if key in config.TIMER_LIMITS:
                w.blockSignals(True)
                w.setValue(value)
                w.blockSignals(False)
                continue
            if key == "season":
                for season, b in w.items():
                    b.blockSignals(True)
                    b.setChecked(season == value)
                    b.blockSignals(False)
            else:
                w.blockSignals(True)
                w.setChecked(value)
                w.blockSignals(False)
        self.fw_note.setVisible(name != "aquarium" and bool(getattr(self.ctx, "firmware_outdated", False)))
        self._place_panel(name)
        self._animate()

    def _owner(self, text):
        self.draft["owner_name"] = config.clean_text(text, 20)
        self.ctx.changed()

    def _changed(self, *_):
        d = self.draft["display"]
        d["animation"] = self.anim.isChecked()
        d["music"] = self.music.isChecked()
        d["brightness"] = self.bright.value()
        self.ctx.changed()
        self.refresh()


# ---------------------------------------------------------------------------
class UpdatePage(Page):
    def build(self):
        app = Card(T("upd_app"))
        app.add(label(T("upd_installed", v=VERSION)))
        self.app_state = app.add(label("", "Hint"))
        r = QHBoxLayout()
        self.check_btn = QPushButton(T("upd_check"))
        self.check_btn.clicked.connect(lambda: self.ctx.check_updates(manual=True))
        self.update_btn = QPushButton(T("upd_now"))
        self.update_btn.setObjectName("Primary")
        self.update_btn.clicked.connect(self.ctx.start_update)
        r.addWidget(self.check_btn)
        r.addWidget(self.update_btn)
        r.addStretch()
        self.auto = ToggleSwitch()
        self.auto.toggled.connect(self._auto)
        r.addWidget(self.auto)
        r.addWidget(label(T("upd_auto"), wrap=False))
        app.layout_.addLayout(r)
        self.col.addWidget(app)

        fw = Card(T("upd_fw"))
        self.fw_pad = fw.add(label(""))
        self.fw_bundled = fw.add(label("", "Hint"))
        self.fw_state = fw.add(label("", "Note"))
        r = QHBoxLayout()
        self.flash_btn = QPushButton(T("fw_flash"))
        self.flash_btn.clicked.connect(self.ctx.flash_firmware)
        r.addWidget(self.flash_btn)
        r.addStretch()
        fw.layout_.addLayout(r)
        self.col.addWidget(fw)

        rep = Card(T("repair"))
        self.rep_state = rep.add(label("", "Hint"))
        r = QHBoxLayout()
        self.rep_check = QPushButton(T("repair_check"))
        self.rep_check.clicked.connect(self.ctx.check_files)
        self.rep_now = QPushButton(T("repair_now"))
        self.rep_now.setObjectName("Primary")
        self.rep_now.clicked.connect(self.ctx.repair)
        r.addWidget(self.rep_check)
        r.addWidget(self.rep_now)
        r.addStretch()
        rep.layout_.addLayout(r)
        rep.add(label(T("repair_pad"), "Note"))
        self.col.addWidget(rep)

    def refresh(self):
        c = self.ctx
        self.auto.blockSignals(True)
        self.auto.setChecked(c.settings.data["updates"]["auto_check"])
        self.auto.blockSignals(False)
        self.app_state.setText(c.update_text)
        self.update_btn.setVisible(bool(c.latest and c.latest.newer))
        self.check_btn.setEnabled(not c.update_busy)
        # firmware
        if c.link_status == "connected":
            v = c.pad_firmware or T("fw_old")
            self.fw_pad.setText(T("fw_pad", v=v))
        else:
            self.fw_pad.setText(T("fw_pad", v=T("fw_unknown")))
        if c.bundle:
            self.fw_bundled.setText(T("fw_bundled", v=c.bundle.version))
        else:
            self.fw_bundled.setText(T("fw_missing"))
        self.fw_state.setText(T("fw_newer_avail") if c.firmware_outdated else "")
        self.fw_state.setStyleSheet(f"color: {theme.YELLOW};" if c.firmware_outdated else "")
        self.flash_btn.setEnabled(bool(c.bundle))
        self.flash_btn.setObjectName("Primary" if c.firmware_outdated else "")
        self.flash_btn.style().unpolish(self.flash_btn)
        self.flash_btn.style().polish(self.flash_btn)
        # repair
        self.rep_state.setText(c.repair_text)
        self.rep_now.setVisible(c.repair_needed)
        for lab in (self.app_state, self.fw_state, self.rep_state):
            lab.setVisible(bool(lab.text()))

    def _auto(self, on):
        self.ctx.settings.data["updates"]["auto_check"] = on
        self.ctx.settings.save()


# ---------------------------------------------------------------------------
class SettingsPage(Page):
    def build(self):
        gen = Card(T("set_general"))
        r = QHBoxLayout()
        self.minimized = ToggleSwitch()
        self.minimized.toggled.connect(self._changed)
        r.addWidget(self.minimized)
        r.addWidget(label(T("set_minimized")), 1)
        gen.layout_.addLayout(r)
        r = QHBoxLayout()
        r.addWidget(label(T("set_player"), wrap=False))
        self.player = QComboBox()
        for key, text in (("auto", T("player_auto")), ("spotify", "Spotify"), ("deezer", "Deezer")):
            self.player.addItem(text, key)
        self.player.setMinimumWidth(260)
        self.player.currentIndexChanged.connect(self._changed)
        r.addWidget(self.player)
        r.addStretch()
        gen.layout_.addLayout(r)
        gen.add(label(T("set_player_note"), "Note"))
        where = gen.add(label(T("set_data_where", path=str(paths.user_dir())), "Note"))
        where.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.col.addWidget(gen)

        sleep = Card(T("sleep_title"))
        r = QHBoxLayout()
        self.when_locked = ToggleSwitch()
        self.when_locked.toggled.connect(self._changed)
        r.addWidget(self.when_locked)
        r.addWidget(label(T("sleep_locked")), 1)
        sleep.layout_.addLayout(r)
        r = QHBoxLayout()
        r.addWidget(label(T("sleep_idle"), wrap=False))
        self.idle = QComboBox()
        for m in config.IDLE_CHOICES:
            self.idle.addItem(T("sleep_never") if m == 0 else T("sleep_minutes", n=m), m)
        self.idle.currentIndexChanged.connect(self._changed)
        r.addWidget(self.idle)
        r.addStretch()
        sleep.layout_.addLayout(r)
        sleep.add(label(T("sleep_note"), "Note"))
        self.col.addWidget(sleep)

        backup = Card(T("backup_title"))
        backup.add(label(T("backup_text"), "Hint"))
        r = QHBoxLayout()
        b = QPushButton(T("backup_export"))
        b.clicked.connect(self._export)
        r.addWidget(b)
        b = QPushButton(T("backup_import"))
        b.clicked.connect(self._import)
        r.addWidget(b)
        r.addStretch()
        backup.layout_.addLayout(r)
        self.col.addWidget(backup)

        reset = Card(T("set_reset_t"))
        reset.add(label(T("set_reset_text"), "Hint"))
        b = QPushButton(T("set_reset"))
        b.clicked.connect(self._reset)
        r = QHBoxLayout()
        r.addWidget(b)
        r.addStretch()
        reset.layout_.addLayout(r)
        self.col.addWidget(reset)

        un = Card(T("set_uninst_t"))
        un.add(label(T("set_uninst_text"), "Hint"))
        self.delete_data = QCheckBox(T("set_uninst_data"))
        un.add(self.delete_data)
        b = QPushButton(T("set_uninst"))
        b.setObjectName("Danger")
        b.clicked.connect(lambda: self.ctx.uninstall(self.delete_data.isChecked()))
        r = QHBoxLayout()
        r.addWidget(b)
        r.addStretch()
        un.layout_.addLayout(r)
        self.col.addWidget(un)

    def refresh(self):
        widgets = (self.minimized, self.player, self.when_locked, self.idle)
        for w in widgets:
            w.blockSignals(True)
        self.minimized.setChecked(self.draft["start_minimized"])
        self.player.setCurrentIndex(max(0, self.player.findData(self.draft["player"])))
        self.when_locked.setChecked(self.draft["sleep"]["when_locked"])
        self.idle.setCurrentIndex(max(0, self.idle.findData(self.draft["sleep"]["idle_minutes"])))
        for w in widgets:
            w.blockSignals(False)

    def _changed(self, *_):
        self.draft["start_minimized"] = self.minimized.isChecked()
        self.draft["player"] = self.player.currentData()
        self.draft["sleep"]["when_locked"] = self.when_locked.isChecked()
        self.draft["sleep"]["idle_minutes"] = self.idle.currentData()
        self.ctx.changed()

    BACKUP_PARTS = ("keys", "keys2", "macros", "multi", "profiles", "lights", "display", "knob_target",
                    "pad_language", "owner_name", "sleep")

    def _export(self):
        import json
        path, _ = QFileDialog.getSaveFileName(self, T("backup_export"), "MacroPad-backup.json", "JSON (*.json)")
        if not path:
            return
        data = {"macropad_backup": 1, "app": VERSION}
        data.update({k: self.draft[k] for k in self.BACKUP_PARTS})
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            dialogs.info(self, T("backup_saved", path=path))
        except OSError as e:
            dialogs.info(self, T("backup_failed", error=str(e)))

    def _import(self):
        import copy
        import json
        path, _ = QFileDialog.getOpenFileName(self, T("backup_import"), "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("macropad_backup") != 1:
                raise ValueError(T("backup_not_ours"))
        except (OSError, ValueError) as e:
            dialogs.info(self, T("backup_failed", error=str(e)))
            return
        merged = copy.deepcopy(self.ctx.draft)
        merged.update({k: data[k] for k in self.BACKUP_PARTS if k in data})
        self.ctx.draft = config.validate(merged)
        self.ctx.changed(refresh_pages=True)
        dialogs.info(self, T("backup_loaded"))

    def _reset(self):
        if dialogs.ask(self, T("set_reset_q")):
            self.ctx.reset_settings()
            dialogs.info(self, T("set_reset_done"))


# ---------------------------------------------------------------------------
class StatsPage(Page):
    """Which keys are pressed how often, as a heat map of the pad."""

    RANGES = (("today", 1), ("week", 7), ("month", 30), ("all", None))

    def build(self):
        card = Card(T("stats_title"))
        card.add(label(T("stats_hint"), "Hint"))
        r = QHBoxLayout()
        self.range_box = QComboBox()
        for key, _ in self.RANGES:
            self.range_box.addItem(T(f"stats_{key}"))
        self.range_box.setCurrentIndex(1)
        self.range_box.currentIndexChanged.connect(self.refresh)
        r.addWidget(self.range_box)
        self.layer_box = QComboBox()
        self.layer_box.addItems([T("layer_1"), T("layer_2")])
        self.layer_box.currentIndexChanged.connect(self.refresh)
        r.addWidget(self.layer_box)
        r.addStretch()
        card.layout_.addLayout(r)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.caps = []
        for i in range(keys.KEY_COUNT):
            cap = KeyCap(i)
            grid.addWidget(cap, i // 5, i % 5)
            self.caps.append(cap)
        holder = QWidget()
        holder.setLayout(grid)
        holder.setMaximumWidth(620)
        holder.setMinimumHeight(270)
        centre = QHBoxLayout()
        centre.addStretch()
        centre.addWidget(holder, 4)
        centre.addStretch()
        card.layout_.addLayout(centre)
        self.summary = card.add(label("", "CardTitle"))
        self.detail = card.add(label("", "Hint"))
        r = QHBoxLayout()
        r.addStretch()
        b = QPushButton(T("stats_reset"))
        b.clicked.connect(self._reset)
        r.addWidget(b)
        card.layout_.addLayout(r)
        card.add(label(T("stats_note"), "Note"))
        self.col.addWidget(card)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    @staticmethod
    def heat(f):
        """0..1 -> dark blue-grey .. purple .. orange."""
        stops = [(0.0, (40, 42, 60)), (0.5, (139, 92, 246)), (1.0, (251, 146, 60))]
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if f <= b:
                k = (f - a) / (b - a)
                return QColor(*(int(x + (y - x) * k) for x, y in zip(ca, cb)))
        return QColor(*stops[-1][1])

    def refresh(self):
        stats = getattr(self.ctx, "stats", None)
        if stats is None:
            return
        days = self.RANGES[self.range_box.currentIndex()][1]
        layer2 = self.layer_box.currentIndex() == 1
        counts = stats.totals(days, layer2)
        layout = self.draft["keys2" if layer2 else "keys"]
        names = config.action_names(self.draft)
        top = max(counts) or 1
        lang = language()
        for i, cap in enumerate(self.caps):
            cap.set_content(keys.short_label(layout[i], lang, names), f"{counts[i]:,}".replace(",", "."),
                            colour=self.heat(counts[i] / top))
        total = sum(counts)
        self.summary.setText(T("stats_total", n=f"{total:,}".replace(",", ".")))
        if total:
            best = counts.index(max(counts))
            self.detail.setText(T("stats_best", what=keys.label(layout[best], lang, names), n=counts[best]))
        else:
            self.detail.setText(T("stats_empty"))

    def _reset(self):
        if dialogs.ask(self, T("stats_reset_q")):
            self.ctx.stats.reset()
            self.refresh()


# ---------------------------------------------------------------------------
class GuidePage(Page):
    def build(self):
        for key in ("switch", "cap", "tips"):
            card = Card(T(f"guide_{key}_t"))
            text = T(f"guide_{key}", log=str(paths.log_file()))
            lab = card.add(label(text))
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.col.addWidget(card)
        credit = Card(T("guide_credit_t"))
        credit.add(label(T("guide_credit", maker=MAKER)))
        self.col.addWidget(credit)
