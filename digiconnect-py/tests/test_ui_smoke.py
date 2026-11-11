"""Offscreen UI smoke tests: drive the real widgets and check the rules are enforced through the UI."""
import os, sys, pathlib, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app.qt import QtWidgets, QtCore, Qt
from app.store import Store
from app.context import Ctx
from app.theme import qss
from app.rules import Target, ListenMode
from app.ui.main_window import MainWindow


@pytest.fixture
def win():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    st = Store(pathlib.Path(tempfile.mkdtemp())); st.settings["callsign"] = "SA7SVR"
    ctx = Ctx(st); app.setStyleSheet(qss(14)); w = MainWindow(ctx); w.show(); app.processEvents()
    yield w, ctx, app
    w.close()


def pick(w, net, row):
    w.nav("net:" + net); ws = w.ws[net]; ws.list.setCurrentRow(row); return ws


def test_listen_connect_ptt_flow(win):
    w, ctx, app = win; ws = pick(w, "DMR", 4)                       # TG 91
    assert ctx.selected == Target("DMR", "91") and ws.tx.listen.isEnabled()
    assert not ws.tx.hold.isEnabled()                                # selecting enables Listen, never PTT
    ws.tx.listen.click(); assert ctx.rules.is_listening(ctx.selected) and not ws.tx.hold.isEnabled()
    ws.tx.connect.click(); assert ctx.rules.tx_connected and ws.tx.hold.isEnabled()
    ws.tx.latch.click(); assert ctx.rules.ptt and ctx.rules.latched and ws.tx.latch.text() == "Stop TX"
    assert not ws.tx.limit.isEnabled()                               # limit locked during TX
    ws.tx.latch.click(); assert not ctx.rules.ptt
    ws.tx.stopall.click(); assert not ctx.rules.rx and not ctx.rules.tx_connected


def test_mode_buttons_and_capacity(win):
    w, ctx, app = win; w.mixer.multi.click(); assert ctx.rules.mode is ListenMode.MULTIPLE
    ws = pick(w, "DMR", 0)
    for row in (0, 1, 2, 3):
        ws.list.setCurrentRow(row); ws.tx.listen.click()
    assert len(ctx.rules.rx) == 4
    ws.list.setCurrentRow(4); ws.tx.listen.click(); assert len(ctx.rules.rx) == 4      # fifth refused
    w.mixer.single.click(); assert len(ctx.rules.rx) == 1


def test_focus_loss_stops_tx(win):
    w, ctx, app = win; ws = pick(w, "DMR", 4); ws.tx.listen.click(); ws.tx.connect.click(); ws.tx.latch.click()
    assert ctx.rules.ptt; ctx.focus_lost(); assert not ctx.rules.ptt


def test_favorites_click_listens_and_amber(win):
    w, ctx, app = win; ctx.store.toggle_fav("C4FM", "00006", "GR-HELLAS Zone A"); w.nav("favorites"); app.processEvents()
    c = w.favs.cards[0]; c.clicked.emit(c.fav); assert ctx.rules.is_listening(Target("C4FM", "00006"))
    ctx.rules.rx[0].reports_traffic = True; ctx.changed.emit(); assert c.property("state") == "amber"   # multiple mode default
    w.mixer.single.click(); assert c.property("state") == "pink"


def test_qso_save_validation_export_import(win, tmp_path):
    w, ctx, app = win; q = w.qdrawer; w.open_qso()
    q.w["callsign"].setText("sv1abc"); q.w["grid"].setText("KM17"); q.w["dest"].setText("91"); q._save()
    rows = ctx.store.search_qso(); assert len(rows) == 1 and rows[0]["callsign"] == "SV1ABC"
    q.w["callsign"].setText("bad"); n = len(ctx.store.search_qso()); q._save(); assert len(ctx.store.search_qso()) == n   # invalid callsign refused
    adif = ctx.store.to_adif(rows, "SA7SVR"); a, s = ctx.store.import_adif(adif); assert (a, s) == (0, 1)               # duplicate skipped
    ctx.store.set_deleted([rows[0]["id"]], True); assert not ctx.store.search_qso() and len(ctx.store.search_qso(trash=True)) == 1
    csv = ctx.store.to_csv(rows); assert csv.splitlines()[0].startswith("callsign;start_utc") and "SV1ABC" in csv


def test_settings_save_and_text_size(win):
    w, ctx, app = win; w.open_settings(); d = w.settings; d.f["callsign"].setText("sa7svr"); d.size.setValue(16); d._save()
    assert ctx.store.settings["callsign"] == "SA7SVR" and ctx.store.settings["text_size"] == 16 and w.callsign.text() == "SA7SVR"


def test_listen_and_connect_buttons_are_visible(win):
    """Regression: a transparent-background stylesheet on the scroll area made these buttons dark-on-dark (text invisible)."""
    w, ctx, app = win; ws = pick(w, "C4FM", 0); app.processEvents()
    for b in (ws.tx.listen, ws.tx.connect):
        img = b.grab().toImage(); assert img.pixelColor(img.width() - 8, img.height() // 2).lightness() > 110, b.text()
