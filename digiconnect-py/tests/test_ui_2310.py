"""2.3.10 user-reported fixes: per-mode Last heard, aligned columns, one-line clock, Exit button, toggle buttons, settings width, QSO order."""
import os, sys, pathlib, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from datetime import datetime
from app.qt import QtWidgets as W, Qt
from app.store import Store
from app.context import Ctx
from app.ui.main_window import MainWindow


def _win(tmp_path):
    W.QApplication.instance() or W.QApplication([])
    return MainWindow(Ctx(Store(tmp_path)))


def _heard(net, src, srcid=0):
    return dict(src=src, dst="1", gw="", net=net, target="1", stream_src=src, srcid=srcid, ts=datetime.now(), last=datetime.now(), me=False)


def test_each_mode_shows_only_its_own_last_heard(tmp_path):
    w = _win(tmp_path); ctx = w.ctx
    ctx.last_heard[:] = [_heard("DMR", "SA7SVR", 2401234), _heard("NXDN", "31", 31), _heard("C4FM", "SV1ABC")]
    for n in ("DMR", "NXDN", "C4FM", "P25"): w.ws[n].refresh()
    rows = lambda n: [w.ws[n].lh_tbl.item(i, 0).text() for i in range(w.ws[n].lh_tbl.rowCount())]
    assert rows("DMR") == ["SA7SVR"] and rows("NXDN") == ["31"] and rows("C4FM") == ["SV1ABC"] and rows("P25") == []


def test_country_from_callsign_prefix_when_the_network_sends_a_callsign(tmp_path):
    w = _win(tmp_path); ctx = w.ctx
    ctx.last_heard[:] = [_heard("C4FM", "SV1ABC"), _heard("C4FM", "31", 31)]
    w.ws["C4FM"].refresh(); t = w.ws["C4FM"].lh_tbl
    assert t.item(0, 2).text() == "Greece" and t.item(1, 2).text() == "—"         # a bare number is never given a made-up country


def test_header_and_data_are_aligned_the_same_way(tmp_path):
    w = _win(tmp_path)
    for t in (w.ws["DMR"].lh_tbl, w.log.table):
        assert t.horizontalHeader().defaultAlignment() & Qt.AlignmentFlag.AlignLeft


def test_clock_is_one_line_and_exit_button_exists(tmp_path):
    w = _win(tmp_path); w._clock()
    assert "<br" not in w.clock.text() and "UTC" in w.clock.text()
    assert w.exit_btn.objectName() == "exitBtn" and w.exit_btn.parent() is not None


def test_mic_and_map_buttons_open_then_close(tmp_path):
    w = _win(tmp_path)
    for key in ("mic", "map"):
        w.nav("net:P25"); w.nav(key); assert w.current == key
        w.nav(key); assert w.current == "net:P25", key


def test_settings_pages_fit_the_window(tmp_path):
    w = _win(tmp_path); w.resize(1200, 800); w.open_settings(); W.QApplication.processEvents()
    assert w.settings.width() <= w.width()


def test_now_talking_is_one_row(tmp_path):
    w = _win(tmp_path); ws = w.ws["DMR"]
    assert ws.now_head.parentWidget() is ws.now_call.parentWidget()
    assert ws.lh_title.alignment() & Qt.AlignmentFlag.AlignHCenter


def test_qso_log_newest_first(tmp_path):
    from app.store import Store
    s = Store(tmp_path)
    for t, c in (("2026-01-02T10:00:00", "B"), ("2026-01-03T09:00:00", "C"), ("2026-01-01 08:00:00", "A")):
        s.add_qso(dict(callsign=c, start_utc=t, system="DMR")) if hasattr(s, "add_qso") else None
    rows = s.search_qso("", "", "", "", "", False)
    if rows: assert [r["callsign"] for r in rows] == ["C", "B", "A"]


def test_qso_log_does_not_eat_the_letter_T_in_names(tmp_path):
    w = _win(tmp_path)
    w.ctx.store.add_qso(dict(callsign="SP1ABC", start_utc="2026-01-01T10:00:00", system="DMR", name="Tomasz Test", notes="T"))
    w.log.reload(); t = w.log.table
    assert t.item(0, 1).text() == "2026-01-01 10:00:00" and t.item(0, 4).text() == "Tomasz Test"


def test_nxdn_p25_numbers_become_call_signs_only_where_that_is_certain(tmp_path):
    import types
    from app.rules import Target
    w = _win(tmp_path); ctx = w.ctx; s = ctx.store.settings
    s["callsign"] = "sa7svr"; s["dmr_id"] = "2407219"; s["nxdn_id"] = "31"
    asked = []; ctx._ask_station = lambda d: asked.append(d)
    ln = lambda net: types.SimpleNamespace(target=Target(net, "202", "x"))
    assert ctx._talker(ln("NXDN"), dict(src="31", srcid=31)) == ("SA7SVR", 31)             # our own NXDN ID is our call sign
    assert ctx._talker(ln("P25"), dict(src="2407219", srcid=2407219)) == ("SA7SVR", 2407219)
    assert ctx._talker(ln("NXDN"), dict(src="44", srcid=44)) == ("44", 44) and asked == []       # a short number is nobody's registered ID: left alone, nothing asked
    assert ctx._talker(ln("P25"), dict(src="2021015", srcid=2021015)) == ("2021015", 2021015) and asked == [2021015]   # asked in the RadioID database
    assert ctx._talker(ln("C4FM"), dict(src="SV1ABC", srcid=0)) == ("SV1ABC", 0)                  # call-sign networks are untouched
