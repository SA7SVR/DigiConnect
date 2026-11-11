"""Language and theme switching actually change the visible UI (the earlier build ignored both)."""
import os, sys, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.qt import QtWidgets as W
from app.store import Store
from app.context import Ctx
from app import i18n, theme
from app.ui.main_window import MainWindow
from app.rules import NETS


def _win(tmp_path):
    app = W.QApplication.instance() or W.QApplication([])
    return app, MainWindow(Ctx(Store(tmp_path)))


def test_translate_functions():
    i18n.set_language("Ελληνικά")
    assert i18n.tr("Listen") == "Ακρόαση" and i18n.tr("Updated 12:00:00 UTC") == "Ενημερώθηκε 12:00:00 UTC"
    assert i18n.tr("Listening · 2 receivers") == "Ακρόαση · 2 δέκτες" and i18n.tr("Unknown text stays") == "Unknown text stays"
    i18n.set_language("English"); assert i18n.tr("Listen") == "Listen"


def test_language_switch_is_live(tmp_path):
    app, w = _win(tmp_path)
    try:
        assert w.tabs["favorites"].text().startswith("My favorites")
        w.ctx.store.settings["language"] = "Ελληνικά"; w.apply_settings()
        assert w.tabs["favorites"].text().startswith("Αγαπημένα") and w.dock.listen.text() == "Ακρόαση"
        assert w.h_nq.text() == "Νέο QSO" and "Ακρόαση" in w.ws["DMR"].tx.listen.text()
        w.ctx.store.settings["language"] = "English"; w.apply_settings()
        assert w.dock.listen.text() == "Listen" and w.tabs["favorites"].text().startswith("My favorites")
    finally: i18n.set_language("English")


def test_theme_switch_changes_palette_and_stylesheet(tmp_path):
    app, w = _win(tmp_path)
    try:
        dark_bg = theme.C["bg"]; assert dark_bg in app.styleSheet()
        w.toggle_theme(); assert theme.current == "light" and theme.C["bg"] != dark_bg and theme.C["bg"] in app.styleSheet()
        assert w.ctx.store.settings["theme"] == "light"
        w.toggle_theme(); assert theme.current == "dark"
    finally: theme.set_theme("dark")


def test_all_networks_have_pages_colours_and_mixer(tmp_path):
    app, w = _win(tmp_path)
    assert set(NETS) >= {"NXDN", "P25", "M17"} and set(w.ws) == set(NETS) and set(w.mixer.sliders) == set(NETS) and set(theme.NET_COLOR) >= set(NETS)
