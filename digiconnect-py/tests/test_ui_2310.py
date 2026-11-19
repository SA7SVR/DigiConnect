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


def test_donate_button_shows_the_amount_from_the_server(tmp_path):
    from app import license as L, i18n
    w = _win(tmp_path)
    mk = lambda **i: L.Verdict("ok", "demo", "7 days", "", "https://x.example", i)
    w._license_changed(mk(offer="donate", amount="5 €")); assert w.donate_btn.text() == "♥ Donate · 5 €" and not w.donate_btn.isHidden()
    w._license_changed(mk(offer="buy", amount="12 €")); assert w.donate_btn.text() == "♥ Buy a licence · 12 €"
    w._license_changed(mk(offer="donate", amount="")); assert w.donate_btn.text() == "♥ Donate"            # empty amount = as before
    w._license_changed(mk(offer="donate")); assert w.donate_btn.text() == "♥ Donate"
    w._license_changed(mk(offer="none", amount="5 €")); assert w.donate_btn.isHidden()
    assert L.with_amount("♥ Donate", {"amount": "5 & 6"}) == "♥ Donate · 5 && 6"                      # '&' would otherwise become a Qt shortcut
    i18n.set_language("Ελληνικά")
    try:
        w._license_changed(mk(offer="donate", amount="5 €")); assert w.donate_btn.text() == "♥ Δωρεά · 5 €"
        w._license_changed(mk(offer="buy", amount="5 €")); assert w.donate_btn.text() == "♥ Αγορά άδειας · 5 €"
    finally: i18n.set_language("English")


def test_when_the_demo_has_ended_the_window_says_what_to_do_to_continue(tmp_path):
    from app import license as L, i18n
    from app.ui.license_dialog import block_text
    mk = lambda msg, **i: L.Verdict("blocked", "locked", "", msg, "https://x.example", i)
    end = "Your demo period has ended. Contact SA7SVR to activate."
    t = block_text(mk(end + "\n\nThanks for trying it!", offer="donate", amount="5 €", no="DC-0042"))
    assert t.startswith("Your demo period has ended.") and "make a donation" in t and "DC-0042" in t and "Activation code" in t and t.endswith("Thanks for trying it!")
    assert "Contact SA7SVR to activate" not in t
    assert "buy a licence" in block_text(mk(end, offer="buy", no="DC-1"))
    n = block_text(mk(end, offer="none")); assert "donation" not in n and "contact the owner" in n
    assert "Your licence has ended." in block_text(mk("Your licence has ended. Contact SA7SVR."))
    assert block_text(mk("This installation needs activation. Contact SA7SVR.", offer="donate")) == "This installation needs activation. Contact SA7SVR."   # a lock by the owner: unchanged
    i18n.set_language("Ελληνικά")
    try:
        g = block_text(mk(end + "\n\nΕυχαριστώ!", offer="donate", no="DC-0042"))
        assert g.startswith("Η περίοδος demo έληξε.") and "κάνε μια δωρεά" in g and "DC-0042" in g and "Κωδικός ενεργοποίησης" in g and g.endswith("Ευχαριστώ!")
        assert "Your" not in g and "installation number" not in g
    finally: i18n.set_language("English")


def test_block_dialog_shows_that_text_and_the_amount(tmp_path):
    from app import license as L
    from app.ui.license_dialog import BlockDialog
    W.QApplication.instance() or W.QApplication([])
    v = L.Verdict("blocked", "locked", "", "Your demo period has ended. Contact SA7SVR to activate.", "https://x.example", dict(offer="donate", amount="5 €", no="DC-7"))
    d = BlockDialog(v, lambda: v)
    assert "make a donation" in d.msg.text() and d.donate.text() == "♥ Donate · 5 €" and not d.donate.isHidden()


def test_licence_window_shows_permanent_licence_number_code_and_owner(tmp_path):
    from app import license as L, i18n
    from app.ui.license_dialog import licence_line
    import time
    mk = lambda st="full", **i: L.Verdict("ok", st, "", "", "https://x.example", i)
    since = int(time.mktime((2026, 11, 18, 12, 0, 0, 0, 0, -1)))
    l = licence_line(mk(no="DC-00001", kind="full", exp=0, since=since))
    assert l == "Licence: Permanent · DC-00001 · since 2026-11-18", l
    assert licence_line(mk(no="DC-00001", kind="full", exp=since)).startswith("Licence: until 2026-11-18 · DC-00001")
    assert licence_line(mk(no="DC-00001", kind="free")) == "Licence: Free use · DC-00001"
    assert licence_line(mk("demo", no="DC-00001")) == "" and licence_line(None) == ""
    assert licence_line(mk(kind="full", exp=0)) == "Licence: Permanent"                          # an older server answer without number / date
    i18n.set_language("Ελληνικά")
    try: assert licence_line(mk(no="DC-00001", kind="full", exp=0, since=since)) == "Άδεια: Μόνιμη · DC-00001 · από 2026-11-18"
    finally: i18n.set_language("English")
