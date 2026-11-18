"""The whole window with the settings file of a real user (a chosen microphone and speakers, callsign, saved favourites, older settings
files), and every page of it opened. The other UI tests start with an empty profile, which is how a crash on the Microphone page
(settings['mic'] holds the device NAME) got through to a user's computer."""
import os, json, pathlib, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from app.qt import QtWidgets
from app.store import Store
from app.context import Ctx
from app.theme import qss
from app.ui.main_window import MainWindow, NETS

REAL = {"callsign": "SA7SVR", "locator": "JO77", "dmr_id": "2407219", "essid": "", "language": "English", "theme": "dark", "text_size": 14,
        "mic": "Microphone (Realtek High Definition Audio)", "speakers": "Speakers (Realtek High Definition Audio)", "mic_gain": 120,
        "op_name": "Hellas", "email": "x@example.org", "registered": True, "rec_path": "", "listen_mode": "multiple"}


def _open(settings, tmp):
    (pathlib.Path(tmp) / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    (pathlib.Path(tmp) / "favorites.json").write_text(json.dumps([{"net": "DMR", "id": "91", "name": "TG 91 World-wide"}]), encoding="utf-8")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    st = Store(pathlib.Path(tmp)); ctx = Ctx(st); app.setStyleSheet(qss(14))
    w = MainWindow(ctx); w.show(); app.processEvents()
    return w, ctx, app


def _every_page(w, app):
    keys = ["favorites", "log", "heard", "mic", "map", "rec", "mixer", "mixer", "newqso", "settings", "help"]   # "analysis" and "updates" open modal dialogs (exec) and would wait for a click + ["net:" + n for n in NETS]
    for k in keys:
        w.nav(k); app.processEvents()
    return keys


def test_every_page_opens_with_a_real_profile():
    w, ctx, app = _open(REAL, tempfile.mkdtemp())
    try:
        assert len(_every_page(w, app)) >= 11
        assert ctx.store.settings["mic"] == REAL["mic"] and ctx.store.settings["speakers"] == REAL["speakers"]
        w.nav("mic"); w.micp._save()                                  # saving the microphone page must not touch the device names
        assert ctx.store.settings["mic"] == REAL["mic"] and "mic_fx" in ctx.store.settings
        saved = json.loads((pathlib.Path(ctx.store.root) / "settings.json").read_text(encoding="utf-8"))
        assert saved["mic"] == REAL["mic"] and saved["speakers"] == REAL["speakers"]
    finally: w.close()


def test_old_settings_file_where_the_microphone_values_were_stored_under_mic():
    w, ctx, app = _open(dict(REAL, mic={"gain": 3, "bass": 1, "highpass": 0}), tempfile.mkdtemp())
    try:
        _every_page(w, app)
        assert w.micp.sliders["gain"].value() == 3 and "mic" not in ctx.store.settings
    finally: w.close()
