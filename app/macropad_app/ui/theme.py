"""Colours and the Qt style sheet (dark mode)."""

SIDEBAR = "#15151c"
SIDEBAR_LINE = "#2a2a36"
TEXT = "#f2f2f7"
DIM = "#a1a1b5"
FAINT = "#6b6b80"
ACCENT = "#8b5cf6"          # purple, like the pad's default light colour
ACCENT_DARK = "#6d28d9"
CARD = "rgba(18, 20, 32, 0.78)"
CARD_BORDER = "rgba(255, 255, 255, 0.10)"
GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"

STATUS_COLOURS = {"connected": GREEN, "searching": YELLOW, "busy": RED, "disconnected": RED}

QSS = f"""
* {{
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: #0e0f16; }}
QToolTip {{ background: #222232; color: {TEXT}; border: 1px solid {SIDEBAR_LINE}; padding: 4px; }}

#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {SIDEBAR_LINE}; }}
#SideHeader {{ font-size: 12pt; font-weight: 600; color: {DIM}; padding: 2px 6px; }}
QPushButton#MenuItem {{
    text-align: left; padding: 9px 14px; border: 1px solid transparent; border-radius: 10px;
    background: transparent; font-size: 11pt; color: {TEXT};
}}
QPushButton#MenuItem:hover {{ background: #20202b; }}
QPushButton#MenuItem:checked {{ border: 1px solid {ACCENT}; background: rgba(139, 92, 246, 0.16); }}
#SideLine {{ background: {SIDEBAR_LINE}; max-height: 1px; min-height: 1px; }}
#SmallLabel {{ color: {DIM}; font-size: 9pt; }}
#Version {{ color: {FAINT}; font-size: 9pt; }}

#Card {{ background: {CARD}; border: 1px solid {CARD_BORDER}; border-radius: 16px; }}
#PageTitle {{ font-size: 26pt; font-weight: 800; letter-spacing: 6px; color: white; }}
#CardTitle {{ font-size: 13pt; font-weight: 700; color: white; }}
#Hint {{ color: {DIM}; }}
#Note {{ color: {DIM}; font-size: 9pt; }}

QPushButton {{
    background: #26263a; border: 1px solid #34344a; border-radius: 9px; padding: 7px 14px;
}}
QPushButton:hover {{ background: #303048; }}
QPushButton:pressed {{ background: #1d1d2c; }}
QPushButton:disabled {{ color: {FAINT}; background: #1b1b27; border-color: #262634; }}
QPushButton#Primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; font-weight: 700; }}
QPushButton#Primary:hover {{ background: #9d74f8; }}
QPushButton#Primary:disabled {{ background: #3b3355; border-color: #3b3355; color: #9a93b5; }}
QPushButton#Apply {{
    background: {ACCENT}; border: 2px solid #b39afc; border-radius: 14px; padding: 10px 40px;
    font-size: 12pt; font-weight: 800;
}}
QPushButton#Apply:hover {{ background: #9d74f8; }}
QPushButton#Apply:disabled {{ background: rgba(40, 36, 60, 0.85); border-color: #3a3550; color: #8f89a8; }}
QPushButton#Danger {{ background: #3a1d24; border-color: #5a2a33; }}
QPushButton#Danger:hover {{ background: #4a232c; }}

QComboBox, QLineEdit, QSpinBox, QKeySequenceEdit {{
    background: #1c1c2a; border: 1px solid #34344a; border-radius: 8px; padding: 6px 10px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: #1c1c2a; border: 1px solid #34344a; selection-background-color: {ACCENT_DARK}; }}
QListWidget {{ background: rgba(20, 20, 32, 0.6); border: 1px solid #2c2c40; border-radius: 10px; padding: 4px; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 7px; }}
QListWidget::item:selected {{ background: {ACCENT_DARK}; color: white; }}
QListWidget::item:hover {{ background: #26263a; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 18px; height: 18px; }}
QCheckBox::indicator {{ border: 1px solid #4a4a64; border-radius: 5px; background: #1c1c2a; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: none; }}
QRadioButton::indicator {{ border: 1px solid #4a4a64; border-radius: 9px; background: #1c1c2a; }}
QRadioButton::indicator:checked {{
    border: 1px solid {ACCENT};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                stop:0 white, stop:0.32 white, stop:0.42 {ACCENT}, stop:1 {ACCENT});
}}
QSlider::groove:horizontal {{ height: 6px; background: #2a2a3c; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QProgressBar {{ background: #1c1c2a; border: 1px solid #34344a; border-radius: 8px; height: 14px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 7px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3a52; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: #1c1c2a; padding: 7px 14px; border-radius: 8px; margin: 2px; }}
QTabBar::tab:selected {{ background: {ACCENT_DARK}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
"""
