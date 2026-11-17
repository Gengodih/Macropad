"""Renders every page offscreen to PNG files (for checking the design)."""
import os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["MACROPAD_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from macropad_app.config import Settings
from macropad_app.ui import theme
from macropad_app.i18n import set_language

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots"
lang = sys.argv[2] if len(sys.argv) > 2 else "de"
os.makedirs(out, exist_ok=True)
app = QApplication([])
app.setStyleSheet(theme.QSS)
s = Settings()
s.data["app_language"] = lang
s.data["lights"]["schemes"] = [{"name": "Ocean", "effect": "breathe", "colours": ["#0ea5e9", "#22d3ee", "#06b6d4", "#3b82f6", "#6366f1"] * 3}]
from macropad_app.ui.main_window import MainWindow, MENU
w = MainWindow(s, start_hidden=False)
w.link.stop()
w.resize(1180, 780)
w._link_status("connected"); w.pad_firmware = "2.0.0"; w._show_status()
w.now_playing = ("Spotify", "Bohemian Rhapsody", "Queen"); w.pages["home"].refresh()
def shoot():
    for i, (key, _) in enumerate(MENU):
        w._select(key)
        for _ in range(8):
            w.background._tick(); app.processEvents()
        w.grab().save(f"{out}/{i}_{key}.png")
    app.quit()
QTimer.singleShot(300, shoot)
app.exec()
print("saved to", out)
