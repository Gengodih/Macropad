"""How often each key is pressed (for the Statistics page), per day, in
%APPDATA%\\MacroPad\\stats.json. Counted while the app runs."""

import datetime
import json
import logging
import os

from . import keys

log = logging.getLogger("macropad.stats")
KEEP_DAYS = 400


class KeyStats:
    def __init__(self, path):
        self.path = path
        self.days = {}          # "2026-11-17": {"1": [15 counts], "2": [15 counts]}
        self._dirty = False
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            for day, layers in (raw.get("days") or {}).items():
                ok = {}
                for layer in ("1", "2"):
                    v = layers.get(layer) if isinstance(layers, dict) else None
                    if isinstance(v, list) and len(v) == keys.KEY_COUNT and all(
                            isinstance(x, int) and x >= 0 for x in v):
                        ok[layer] = v
                if ok and len(day) == 10:
                    self.days[day] = ok
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning("Statistics file unreadable, starting again: %s", e)

    @staticmethod
    def today():
        return datetime.date.today().isoformat()

    def count(self, key, layer2=False):
        if not 0 <= key < keys.KEY_COUNT:
            return
        day = self.days.setdefault(self.today(), {})
        row = day.setdefault("2" if layer2 else "1", [0] * keys.KEY_COUNT)
        row[key] += 1
        self._dirty = True

    def totals(self, days=None, layer2=False):
        """Presses per key: today (days=1), the last n days, or all (None)."""
        layer = "2" if layer2 else "1"
        out = [0] * keys.KEY_COUNT
        first = None
        if days:
            first = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        for day, layers in self.days.items():
            if first and day < first:
                continue
            for i, n in enumerate(layers.get(layer, ())):
                out[i] += n
        return out

    def reset(self):
        self.days = {}
        self._dirty = True
        self.flush()

    def flush(self):
        if not self._dirty:
            return
        cutoff = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
        self.days = {d: v for d, v in self.days.items() if d >= cutoff}
        try:
            tmp = str(self.path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"days": self.days}, f)
            os.replace(tmp, self.path)
            self._dirty = False
        except OSError as e:
            log.warning("Could not save the statistics: %s", e)
