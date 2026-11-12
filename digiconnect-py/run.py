import sys
import bootstrap           # nothing from the app package may be imported before bootstrap.activate() has run


def main():
    ov = bootstrap.activate(bootstrap.BASE_VERSION)      # must happen before the rest of 'app' is imported
    try:
        _run(ov)
    except Exception:
        if ov:                                # the new code could not start: switch it off and start the shell's own code
            bootstrap.mark_bad(ov); bootstrap.started_ok(); bootstrap.relaunch(); return
        raise


def _run(ov):
    from app.qt import QtWidgets, QtCore
    from app.theme import qss
    from app.context import Ctx
    from app.store import Store
    from app.engine_client import EngineClient, find_engine
    from app.ui.main_window import MainWindow
    from app.updater import Updater
    from app.presence import Presence
    app = QtWidgets.QApplication(sys.argv); app.setApplicationName("DigiConnect"); app.setOrganizationName("HELLASZone")
    store = Store(); path = find_engine()
    ctx = Ctx(store, EngineClient(path, store) if path else None); app.setStyleSheet(qss(ctx.store.settings["text_size"]))
    w = MainWindow(ctx); w.updater = Updater(store); w.bind_updater(); w.presence = Presence(ctx, w.updater); w.show(); ctx.refresh_hosts(); ctx.refresh_asl()
    QtCore.QTimer.singleShot(15000, bootstrap.started_ok)      # up for 15 s: this start counts as good
    app.aboutToQuit.connect(bootstrap.started_ok)               # a normal exit is not a crash
    QtCore.QTimer.singleShot(6000, w.presence.start)            # tell the server this station is online (can be switched off in Settings)
    QtCore.QTimer.singleShot(4000, w.updater.start)             # first check shortly after the window is up
    code = app.exec()
    sys.exit(code)


if __name__ == "__main__":
    main()
