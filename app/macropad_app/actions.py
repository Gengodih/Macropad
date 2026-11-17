"""What the app does for a key: macros, tap / hold / double tap and the
microphone switch. The pad reports presses of such keys (P|...|1); all other
keys the pad handles itself, also without the app."""

import logging
import queue
import threading
import time

from PySide6.QtCore import QObject, QTimer

from . import keys, protocol, winsys

log = logging.getLogger("macropad.actions")

HOLD_MS = 400        # held this long = "hold"
DOUBLE_MS = 260      # a second tap within this time = "double tap"


def action_for(settings, profile, key, layer2=False):
    """The action id of a key right now (the active profile or the normal layout)."""
    if profile is not None and 0 <= profile < len(settings["profiles"]):
        return settings["profiles"][profile]["keys"][key]
    return settings["keys"][key]


class _Multi:
    def __init__(self, parent):
        self.hold = QTimer(parent)
        self.hold.setSingleShot(True)
        self.double = QTimer(parent)
        self.double.setSingleShot(True)
        self.held_fired = False
        self.second = False
        self.entry = None


class ActionRunner(QObject):
    def __init__(self, link, current, parent=None, on_app=None):
        """current(): (saved settings, index of the active profile or None).
        on_app(name): app actions the window handles (focus timer)."""
        super().__init__(parent)
        self.link = link
        self.current = current
        self.on_app = on_app
        self._multi = {}
        self._steps = queue.Queue()
        self._worker = threading.Thread(target=self._work, name="macros", daemon=True)
        self._worker.start()

    # ----- from the pad -------------------------------------------------------
    def key_event(self, key, down, layer2, app):
        if not app:
            return
        try:
            settings, profile = self.current()
            aid = action_for(settings, profile, key, layer2)
            if aid.startswith("multi:"):
                entry = settings["multi"].get(keys.ref_id(aid))
                if entry:
                    self._multi_event((key, layer2), down, entry, settings)
            elif down:
                self.run(aid, settings)
        except Exception:
            log.exception("Key action failed")

    def run(self, aid, settings):
        if aid == "app:mic_mute":
            self.link.toggle_mic()
        elif aid.startswith("app:") and self.on_app:
            self.on_app(aid[4:])
        elif aid.startswith("macro:"):
            m = settings["macros"].get(keys.ref_id(aid))
            if m:
                self._steps.put(list(m["steps"]))
        elif keys.is_pad_action(aid):
            self.link.send([protocol.tap_line(aid)])

    # ----- tap / hold / double tap ------------------------------------------
    def _multi_event(self, slot, down, entry, settings):
        st = self._multi.get(slot)
        if st is None:
            st = self._multi[slot] = _Multi(self)
            st.hold.timeout.connect(lambda st=st: self._held(st))
            st.double.timeout.connect(lambda st=st: self._fire(st, "tap"))
        st.entry = (entry, settings)
        if down:
            if st.double.isActive():                # second tap in time: double tap
                st.double.stop()
                st.second = True
                self._fire(st, "double")
                return
            st.held_fired = False
            st.second = False
            if entry["hold"] != "none":
                st.hold.start(HOLD_MS)
            return
        # let go
        if st.second:
            st.second = False
            return
        st.hold.stop()
        if st.held_fired:
            return
        if entry["double"] != "none":
            st.double.start(DOUBLE_MS)              # wait: maybe a second tap comes
        else:
            self._fire(st, "tap")

    def _held(self, st):
        st.held_fired = True
        self._fire(st, "hold")

    def _fire(self, st, which):
        entry, settings = st.entry
        aid = entry.get(which, "none")
        if aid != "none":
            self.run(aid, settings)

    # ----- macros (one after another, in their own thread) --------------------
    def _work(self):
        while True:
            steps = self._steps.get()
            for st in steps:
                try:
                    t = st["type"]
                    if t == "keys":
                        self.link.send([protocol.tap_line(st["action"])])
                        time.sleep(0.06)              # the pad types it, then the next step
                    elif t == "text":
                        winsys.type_text(st["text"])
                        time.sleep(0.03)
                    elif t == "open":
                        winsys.open_target(st["target"])
                    elif t == "delay":
                        time.sleep(st["ms"] / 1000)
                except Exception:
                    log.exception("Macro step failed: %s", st)
