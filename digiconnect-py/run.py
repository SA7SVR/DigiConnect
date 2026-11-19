import os, sys
import bootstrap           # nothing from the app package may be imported before bootstrap.activate() has run


def main():
    ov = bootstrap.activate(bootstrap.BASE_VERSION)      # must happen before the rest of 'app' is imported
    if os.environ.get("DC_SELFTEST"): _selftest(os.environ["DC_SELFTEST"]); return
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
    from app.engine_client import EngineClient, find_engine, check_updated_engine
    from app.ui.main_window import MainWindow
    from app.updater import Updater
    from app.presence import Presence, LiveStamp
    app = QtWidgets.QApplication(sys.argv); app.setApplicationName("DigiConnect"); app.setOrganizationName("HELLASZone")
    store = Store(); path = find_engine()
    client = EngineClient(path, store) if path else None
    if client: check_updated_engine(client)          # an updated engine must still start; if not, the installer's engine is used again
    ctx = Ctx(store, client); app.setStyleSheet(qss(ctx.store.settings["text_size"]))
    from app.license import License
    from app.ui.license_dialog import run_gate, Watcher
    updater = Updater(store)
    lic = License(store, updater.params)
    if not run_gate(lic, store, lang=store.settings.get("language", "")): sys.exit(0)          # first run: name, callsign, DMR ID, email; then the demo / licence rules
    w = MainWindow(ctx); w.license_watcher = Watcher(lic); w.bind_license(w.license_watcher); QtCore.QTimer.singleShot(60 * 1000, w.license_watcher.start); w.updater = updater; w.bind_updater(); w.presence = Presence(ctx, w.updater); w.presence.rev_changed.connect(w.license_watcher.check); w.live = LiveStamp(w.updater); w.live.rev_changed.connect(w.license_watcher.check); w.show(); ctx.refresh_hosts(); ctx.refresh_asl()
    ctx._list_timer = QtCore.QTimer(ctx); ctx._list_timer.setInterval(30 * 60 * 1000); ctx._list_timer.timeout.connect(lambda: (ctx.refresh_hosts(), ctx.refresh_asl())); ctx._list_timer.start()   # lists stay current while the program runs
    QtCore.QTimer.singleShot(15000, bootstrap.started_ok)      # up for 15 s: this start counts as good
    app.aboutToQuit.connect(ctx.el_go_offline)                  # EchoLink: leave the directory cleanly (does nothing when not signed in)
    app.aboutToQuit.connect(lambda: setattr(ctx, 'closing', True))
    app.aboutToQuit.connect(bootstrap.started_ok)               # a normal exit is not a crash
    QtCore.QTimer.singleShot(3000, w.live.start)                # the owner's block / unblock reaches the program within seconds (independent of 'show me online')
    QtCore.QTimer.singleShot(6000, w.presence.start)            # tell the server this station is online (can be switched off in Settings)
    QtCore.QTimer.singleShot(4000, w.updater.start)             # first check shortly after the window is up
    code = app.exec()
    sys.exit(code)


def _selftest(status):
    """Start the BUILT program like a user's computer does (empty profile), open every page, write the result to the file 'status', exit.
    CI runs this on the packaged program (not on the source tree): a file that is missing from the package fails here, not on a user's PC."""
    import os, tempfile, traceback, pathlib
    try:
        from app.qt import QtWidgets
        from app.theme import qss
        from app.context import Ctx
        from app.store import Store
        from app.engine_client import find_engine
        from app.ui.main_window import MainWindow, NETS
        app = QtWidgets.QApplication(sys.argv)
        ctx = Ctx(Store(pathlib.Path(tempfile.mkdtemp()))); app.setStyleSheet(qss(14))
        w = MainWindow(ctx); w.show(); app.processEvents()
        for k in ["favorites", "log", "heard", "mic", "map", "rec", "newqso", "settings", "help"] + ["net:" + n for n in NETS]:
            w.nav(k); app.processEvents()
        res = "OK engine=" + str(find_engine())
    except BaseException:
        res = "FAILED\n" + traceback.format_exc()
    pathlib.Path(status).write_text(res, encoding="utf-8")
    os._exit(0 if res.startswith("OK") else 1)          # no normal Qt shutdown: it can crash on exit and hide the result


if __name__ == "__main__":
    main()
