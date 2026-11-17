# PyInstaller recipe for MacroPad.exe (one folder, no console window).
# Build:  pyinstaller --noconfirm macropad.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = (["psutil", "pynvml"] + collect_submodules("esptool") + collect_submodules("esp_pylib")
          + collect_submodules("winrt") + collect_submodules("pycaw") + collect_submodules("comtypes")
          + ["serial.tools.list_ports_windows"])
datas = [("app/macropad_app/resources", "resources")]
datas += collect_data_files("esptool")          # flasher stubs for the ESP32-S3
datas += collect_data_files("esp_pylib")

a = Analysis(
    ["app/run_app.py"],
    pathex=["app"],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtPositioning"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MacroPad",
    icon="app/macropad_app/resources/icon.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MacroPad")
