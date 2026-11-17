"""Start of the app: logging, error safety net, one copy only, then the window.

    MacroPad.exe              open the window
    MacroPad.exe --minimized  start in the tray (used by autostart)
    MacroPad.exe --esptool .. runs esptool (the app uses this to flash the pad)
"""

import logging
import logging.handlers
import sys
import traceback


def _run_esptool(args):
    import esptool
    try:
        esptool.main(args)
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:  # esptool reports its own errors; give a clear exit code
        print(f"A fatal error occurred: {e}", flush=True)
        return 2


def _selftest():
    """Starts everything once without showing it (used by the build to check the
    finished .exe). Exit code 0 = fine."""
    import os
    import tempfile
    os.environ["MACROPAD_HOME"] = tempfile.mkdtemp()
    try:
        import esptool  # noqa: F401  (must be inside the build)
        import threading
        from PySide6.QtWidgets import QApplication
        from . import flasher
        # the music libraries, imported the way the app does it: in their own thread
        state = {}

        def load_media():
            from . import media
            state["ok"], state["why"] = media.MEDIA_OK, media.IMPORT_ERROR
        t = threading.Thread(target=load_media)
        t.start()
        t.join(30)
        if sys.platform == "win32" and not state.get("ok"):
            raise RuntimeError(f"music libraries missing in the build: {state.get('why')}")
        from .config import Settings
        from .ui import theme
        from .ui.main_window import MENU, MainWindow
        app = QApplication(sys.argv[:1])
        app.setStyleSheet(theme.QSS)
        flasher.load_bundle()
        w = MainWindow(Settings(), start_hidden=True)
        for key, _ in MENU:
            w._select(key)
            app.processEvents()
        w.quit_app()
        return 0
    except Exception:
        traceback.print_exc()
        try:
            from . import paths
            paths.log_file().write_text(traceback.format_exc(), "utf-8")
        except Exception:
            pass
        return 1


def _setup_logging():
    from . import paths
    handlers = []
    try:
        handlers.append(logging.handlers.RotatingFileHandler(paths.log_file(), maxBytes=1_000_000,
                                                             backupCount=1, encoding="utf-8"))
    except OSError:
        pass
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s",
                        datefmt="%d.%m. %H:%M:%S", handlers=handlers or [logging.NullHandler()])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--esptool"]:
        return _run_esptool(argv[1:])
    if argv[:1] == ["--selftest"]:
        return _selftest()

    _setup_logging()
    log = logging.getLogger("macropad")

    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMessageBox

    from . import VERSION, paths
    from .config import Settings
    from .i18n import T
    from .ui import theme

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Macro Pad")
    app.setQuitOnLastWindowClosed(False)    # keeps running in the tray
    app.setStyleSheet(theme.QSS)

    # Only one copy: a second start just brings the first window to the front.
    import getpass
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    server_name = "MacroPadApp-" + "".join(ch for ch in user if ch.isalnum())[:40]
    sock = QLocalSocket()
    sock.connectToServer(server_name)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)

    # Safety net: an error anywhere is logged and shown, the app keeps running.
    shown = {"last": 0.0}

    def excepthook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("Unhandled error:\n%s", text)
        import time
        if time.time() - shown["last"] < 5:      # never a flood of message boxes
            return
        shown["last"] = time.time()
        try:
            box = QMessageBox()
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(T("err_title"))
            box.setText(T("err_body", log=str(paths.log_file()), e=f"{kind.__name__}: {value}"))
            box.exec()
        except Exception:
            pass
    sys.excepthook = excepthook

    log.info("Macro Pad app %s starting", VERSION)
    settings = Settings()
    from .ui.main_window import MainWindow
    hidden = "--minimized" in argv or settings.data.get("start_minimized", False)
    window = MainWindow(settings, start_hidden=hidden)

    def on_second_copy():
        c = server.nextPendingConnection()
        if c:
            c.readyRead.connect(lambda: window.show_window())
            QTimer.singleShot(50, window.show_window)
    server.newConnection.connect(on_second_copy)

    rc = app.exec()
    log.info("Macro Pad app closed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
