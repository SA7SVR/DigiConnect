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
    from app.license import License
    from app.ui.license_dialog import run_gate, Watcher
    updater = Updater(store)
    lic = License(store, updater.params)
    if not run_gate(lic, store, lang=store.settings.get("language", "")): sys.exit(0)          # first run: name, callsign, DMR ID, email; then the demo / licence rules
    w = MainWindow(ctx); w.license_watcher = Watcher(lic); w.bind_license(w.license_watcher); QtCore.QTimer.singleShot(60 * 1000, w.license_watcher.start); w.updater = updater; w.bind_updater(); w.presence = Presence(ctx, w.updater); w.show(); ctx.refresh_hosts(); ctx.refresh_asl()
    ctx._list_timer = QtCore.QTimer(ctx); ctx._list_timer.setInterval(30 * 60 * 1000); ctx._list_timer.timeout.connect(lambda: (ctx.refresh_hosts(), ctx.refresh_asl())); ctx._list_timer.start()   # lists stay current while the program runs
    QtCore.QTimer.singleShot(15000, bootstrap.started_ok)      # up for 15 s: this start counts as good
    app.aboutToQuit.connect(lambda: setattr(ctx, 'closing', True))
    app.aboutToQuit.connect(bootstrap.started_ok)               # a normal exit is not a crash
    QtCore.QTimer.singleShot(6000, w.presence.start)            # tell the server this station is online (can be switched off in Settings)
    QtCore.QTimer.singleShot(4000, w.updater.start)             # first check shortly after the window is up
    code = app.exec()
    sys.exit(code)


if __name__ == "__main__":
    main()
