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
    ctx = Ctx(st); app.setStyleSheet(qss(14))
    from app import hostlists            # the DMR list comes only from a downloaded source list: use a sample of the Pi-Star TG list format
    ctx.hosts._set(hostlists.parse_tg("1;0;LOCAL;TG1\n2;0;CLUSTER;TG2\n8;0;REGIONAL;TG8\n9;0;LOCAL;TG9\n91;0;WORLD-WIDE;TG91\n92;0;EUROPE;TG92\n202;0;;TG202\n"), {"TG": "ok 7"}, __import__("time").time()); w = MainWindow(ctx); w.show(); app.processEvents()
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


def test_favorites_second_click_stops_listening(win):
    """First click on a favorite card starts listening, the second click on the same card stops it (and other cards stay)."""
    w, ctx, app = win; ctx.store.toggle_fav("C4FM", "00006", "A"); ctx.store.toggle_fav("DMR", "91", "B"); w.nav("favorites"); app.processEvents()
    a, b = w.favs.cards[0], w.favs.cards[1]; w.mixer.multi.click()
    a.clicked.emit(a.fav); b.clicked.emit(b.fav)
    assert ctx.rules.is_listening(Target("C4FM", "00006")) and ctx.rules.is_listening(Target("DMR", "91"))
    a.clicked.emit(a.fav)
    assert not ctx.rules.is_listening(Target("C4FM", "00006")) and ctx.rules.is_listening(Target("DMR", "91"))
    a.clicked.emit(a.fav); assert ctx.rules.is_listening(Target("C4FM", "00006"))         # third click starts it again


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
    w, ctx, app = win; ws = pick(w, "DMR", 4); app.processEvents()
    for b in (ws.tx.listen, ws.tx.connect):
        img = b.grab().toImage(); assert img.pixelColor(img.width() - 8, img.height() // 2).lightness() > 110, b.text()


def test_mute_button_shows_its_state(win):
    w, ctx, app = win; b = w.mixer.mutes["C4FM"]
    assert b.property("icon_name") == "speaker" and not ctx.rules.net_muted["C4FM"]
    b.click(); assert ctx.rules.net_muted["C4FM"] and b.property("icon_name") == "speaker_off"     # muted: crossed speaker
    b.click(); assert not ctx.rules.net_muted["C4FM"] and b.property("icon_name") == "speaker"
    w._mute_all(); assert all(x.property("icon_name") == "speaker_off" for x in w.mixer.mutes.values())   # F4 follows too
    w._mute_all(); assert all(x.property("icon_name") == "speaker" for x in w.mixer.mutes.values())


def test_toast_is_at_the_top_and_goes_away(win):
    w, ctx, app = win; t = w.toast
    ctx.toast.emit("Connected · GR-HELLAS Zone B · DX Zone"); app.processEvents()
    assert t.isVisible() and t.y() < 40 and t.y() + t.height() < 120            # top of the window, not over the bottom controls
    t.t.stop(); t._fade_out(); t.anim.setCurrentTime(t.anim.duration()); app.processEvents()   # jump to the end of the fade
    assert not t.isVisible()


def test_dmr_password_shows_where_it_is_kept(win):
    """Typing the BrandMeister password must give a visible answer: saved on this computer / kept only for this run / nothing entered."""
    w, ctx, app = win; ws = pick(w, "DMR", 4)
    assert "No password" in ws.dm_state.text()
    ws.dm_rem.setChecked(True); ws.dm_pw.setText("abc123")
    assert "saved on this computer" in ws.dm_state.text() and ctx.store.settings["dmr_pw"] == "abc123"
    ws.dm_rem.setChecked(False)
    assert "only until you close" in ws.dm_state.text() and ctx.store.settings["dmr_pw"] == "" and ctx.dmr_password == "abc123"


def test_mute_reaches_a_transmit_only_link(win):
    """Connect (TX) without Listen: the server's audio still plays, so the network's mute / volume must be sent to that link too."""
    w, ctx, app = win
    sent = []
    class L:
        key = "AllStar:1234"; target = Target("AllStar", "1234"); rx = set(); tx = True; state = "connected"
        def send(self, cmd, **kw): sent.append((cmd, kw))
    class E:
        name = "fake"; preview = False
        def tx_only_links(self): return [L()]
    ctx.engine = E(); ctx.engine.set_rx_volume = lambda *a: None
    ctx.rules.net_muted["AllStar"] = False; ctx._sync_audio(); assert sent[-1] == ("out_volume", {"out": 1.0}) or sent[-1][1]["out"] > 0
    ctx.rules.net_muted["AllStar"] = True; ctx._sync_audio()
    assert sent[-1] == ("out_volume", {"out": 0.0})
    n = len(sent); ctx._sync_audio(); assert len(sent) == n                    # nothing is resent while unchanged


def test_master_dialog_has_a_network_filter(win, monkeypatch):
    """Choose DMR server: pick BrandMeister / DMR+ / FreeDMR (networks named by the host list) and see only their masters."""
    import time
    from app import hostlists as H
    from app.qt import QtWidgets as W
    w, ctx, app = win; ws = pick(w, "DMR", 4)
    ctx.hosts._set(H.parse_dmr("BM_2022_Greece\t\t\t2022\t2022.master.brandmeister.network\t\tpassw0rd\t62031\n"
                               "DMR+_IPSC2-ANDALUCIA\t\t124734\t141.94.206.232\t\t\t\tPASSWORD\t55555\n"
                               "FreeDMR_Spain\t\t\t1\tfreedmr.example.org\t\tpassw0rd\t62031\n"), {"DMR": "ok 3"}, time.time())
    seen = {}
    def fake_exec(self):
        box = self.findChildren(W.QComboBox)[0]; lst = self.findChildren(W.QListWidget)[0]
        seen["networks"] = [box.itemText(i) for i in range(box.count())]
        i = box.findData("DMR+"); box.setCurrentIndex(i); seen["dmrplus"] = [lst.item(k).text() for k in range(lst.count())]
        return 0
    monkeypatch.setattr(W.QDialog, "exec", fake_exec)
    ws._choose_master()
    assert seen["networks"][0] == "All networks" and any(n.startswith("BrandMeister") for n in seen["networks"]) and any(n.startswith("FreeDMR") for n in seen["networks"])
    assert len(seen["dmrplus"]) == 1 and "ANDALUCIA" in seen["dmrplus"][0]


def test_allstar_page_lists_stations_connected_to_the_node(win):
    w, ctx, app = win; w.nav("net:AllStar"); ws = w.ws["AllStar"]
    t = Target("AllStar", "509830", "HELLAS Zone Net"); ctx.select(t)
    ws._asl_links_show(); assert "Connect to a node" in ws.asl_head.text()                  # not connected: nothing to show
    ctx.rules.listen(t)                                                                       # connected (listening) to the node
    ctx._asl_links_asked["509830"] = 1e18                                                     # no real network in the test
    ws._asl_links_show(); assert "509830" in ws.asl_head.text() and ws.asl_list.count() == 0
    ctx._on_asl_links("509830", dict(title="HELLAS Zone Server", keyed=True, error="", rows=[
        dict(node="63618", callsign="SV1GGF", owner="SV1GGF", location="Piraeus", site="SV1GGF NODE", mode="T", status="Active"),
        dict(node="63938", callsign="DL4LGV", owner="DL4LGV", location="JO42tk", site="DL4LGV", mode="T", status="Active")]))
    assert ws.asl_list.count() == 2 and "SV1GGF" in ws.asl_list.item(0).text() and "Piraeus" in ws.asl_list.item(0).text()
    assert "2" in ws.asl_head.text() and "transmitting" in ws.asl_head.text()


class _FakeLic:
    """Stands in for app.license.License (no network)."""
    def __init__(self, answers): self.answers = list(answers); self.sent = []; self.last = None
    def register(self, d, lang=""): self.sent.append(d); return dict(ok=True, state="demo", left="14 days left", registered=1, donate="https://example.org/d")
    def verdict(self, m): 
        from app import license as L
        return L.Verdict("ok", m["state"], m.get("left", ""), "", m.get("donate", ""))
    def evaluate(self):
        from app import license as L
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def test_registration_dialog_requires_all_fields_and_consent(win):
    from app.ui.license_dialog import RegistrationDialog
    w, ctx, app = win; lic = _FakeLic([])
    d = RegistrationDialog(lic, ctx.store)
    d._send(); assert "name" in d.err.text().lower() and not lic.sent
    d.name.setText("Panagiotis"); d.call.setText("sa7svr"); d.dmr.setText("12"); d._send(); assert "DMR ID" in d.err.text() and not lic.sent
    d.dmr.setText("2400123"); d.mail.setText("nope"); d._send(); assert "email" in d.err.text().lower() and not lic.sent
    d.mail.setText("a@b.se"); d._send(); assert "agree" in d.err.text().lower() and not lic.sent
    d.agree.setChecked(True); d._send()
    import time
    for _ in range(100):
        app.processEvents()
        if d.answer is not None: break
        time.sleep(0.02)
    assert lic.sent and lic.sent[0]["call"] == "sa7svr" and d.answer["state"] == "demo"
    s = ctx.store.settings; assert (s["callsign"], s["dmr_id"], s["op_name"], s["email"], s["registered"]) == ("SA7SVR", "2400123", "Panagiotis", "a@b.se", True)


def test_window_shows_demo_days_and_blocks_when_locked(win, monkeypatch):
    from app import license as L
    from app.qt import QtWidgets as W
    w, ctx, app = win
    w._license_changed(L.Verdict("ok", "demo", "12 days left", "", "https://example.org/d"))
    assert not w.demo_lbl.isHidden() and "12" in w.demo_lbl.text() and w.license_url == "https://example.org/d"
    w._license_changed(L.Verdict("ok", "full"));  assert w.demo_lbl.isHidden()
    shown = {}
    class D:
        def __init__(self, v, check, parent=None): shown["v"] = v; self.result_verdict = None
        def exec(self): return 0
    import app.ui.license_dialog as LD
    monkeypatch.setattr(LD, "BlockDialog", D); quits = []
    monkeypatch.setattr(W.QApplication, "quit", staticmethod(lambda: quits.append(1)))
    w.watcher = type("Wt", (), {"lic": _FakeLic([L.Verdict("blocked", "locked", "", "locked")])})()
    w._license_changed(L.Verdict("blocked", "locked", "", "This installation needs activation. Contact SA7SVR."))
    assert shown["v"].kind == "blocked" and quits == [1]                                  # the program asked, the person chose Quit


def test_run_gate_registers_then_continues_and_blocks_when_refused(win, monkeypatch):
    from app import license as L
    import app.ui.license_dialog as LD
    w, ctx, app = win
    seq = {"reg": 0, "block": 0}
    class R:
        def __init__(self, *a, **k): self.answer = dict(state="demo", left="14 days left", registered=1)
        def exec(self): seq["reg"] += 1; return 1
    class B:
        def __init__(self, v, check, parent=None): self.result_verdict = None
        def exec(self): seq["block"] += 1; return 0
    monkeypatch.setattr(LD, "RegistrationDialog", R); monkeypatch.setattr(LD, "BlockDialog", B)
    lic = _FakeLic([L.Verdict("register")]); lic.verdict = lambda m: L.Verdict("ok", m["state"], m.get("left", ""))
    assert LD.run_gate(lic, ctx.store) is True and seq == {"reg": 1, "block": 0}
    lic2 = _FakeLic([L.Verdict("blocked", "locked", "", "x")]); assert LD.run_gate(lic2, ctx.store) is False and seq["block"] == 1       # Quit
    lic3 = _FakeLic([L.Verdict("offline", msg="no server")]); assert LD.run_gate(lic3, ctx.store) is False


def test_microphone_meter_only_when_transmit_is_connected(win):
    """Listening only: no microphone knob / level bar. It appears when Connect (TX) is on and goes away again."""
    w, ctx, app = win; ws = pick(w, "DMR", 4)
    ws.tx.listen.click(); app.processEvents()
    assert ctx.rules.is_listening(ctx.selected) and ws.tx.knob.isHidden() and w.dock.knob.isHidden()
    ws.tx.connect.click(); app.processEvents()
    assert ctx.rules.tx_connected and not ws.tx.knob.isHidden() and not w.dock.knob.isHidden()
    ws.tx.connect.click(); app.processEvents()
    assert not ctx.rules.tx_connected and ws.tx.knob.isHidden() and w.dock.knob.isHidden()
