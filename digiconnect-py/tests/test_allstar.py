"""AllStarLink: node list parser/search, portal sign-in token (against a local mock of the AppAuth API), engine parameters,
and the connect sequence (address + token first, then the engine is told to connect)."""
import json, os, sys, pathlib, threading, time, http.server
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app.qt import QtWidgets as W, QtCore
from app import allstar, engine_client
from app import hostlists as H
from app.store import Store
from app.rules import Target, NETS
from app.engine_client import EngineClient
from app.servers import protocol_for


class Mock(http.server.BaseHTTPRequestHandler):
    seen: list = []
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Mock.seen.append(body)
        if body.get("password") == "limit": code, out = 429, {"status": False, "auth-token": None}
        elif body.get("password") == "good": code, out = 200, {"status": True, "auth-token": "a" * 64, "request-id": body.get("request-id")}
        else: code, out = 200, {"status": False, "auth-token": None}
        data = json.dumps(out).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


@pytest.fixture
def api():
    srv = http.server.HTTPServer(("127.0.0.1", 0), Mock); Mock.seen = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1/appauth/request"
    srv.shutdown()


def test_parse_and_search(tmp_path):
    nodes = allstar.parse_nodes("1999|WB6NIL|Allstar Hub|Los Angeles, CA\n2000|SM5ABC|Stockholm repeater|Sweden\nrubbish\n1999|DUP||\n# c\n55|short|x|y\n")
    assert [n["node"] for n in nodes] == ["1999", "2000"] and nodes[1]["call"] == "SM5ABC"
    assert [n["node"] for n in allstar.parse_nodes('[{"node": 3001, "callsign": "sa7svr", "description": "Jönköping", "location": "SE"}]')] == ["3001"]
    d = allstar.NodeDirectory(tmp_path); d._set(nodes, time.time())
    assert [n["node"] for n in d.search("stockholm")] == ["2000"] and [n["node"] for n in d.search("hub angeles")] == ["1999"] and len(d.search("")) == 2
    assert d.stale() is False and d.can_refresh() is False


def test_token_request(api, tmp_path):
    st = Store(tmp_path); cid = allstar.client_id(st)
    assert cid == allstar.client_id(st) and len(cid) == 36
    tok, err = allstar.request_token("SA7SVR", "good", cid, api); assert tok == "a" * 64 and not err
    sent = Mock.seen[-1]; assert sent["username"] == "SA7SVR" and sent["client-id"] == cid and sent["password"] == "good"
    tok, err = allstar.request_token("SA7SVR", "bad", cid, api); assert not tok and "did not accept" in err
    tok, err = allstar.request_token("SA7SVR", "limit", cid, api); assert not tok and "too many" in err
    assert allstar.request_token("SA7 SVR", "x", cid, api)[0] == "" and allstar.request_token("SA7SVR", "", cid, api)[0] == ""
    tok, err = allstar.request_token("SA7SVR", "good", cid, "http://127.0.0.1:9/none", timeout=2); assert not tok and "Cannot reach" in err


def test_names():
    assert allstar.caller_name("abc", "sa7svr") == "abc/SA7SVR" and allstar.dns_name("1999") == "1999.nodes.allstarlink.org"
    assert allstar.srv_name("1999") == "_iax._udp.1999.nodes.allstarlink.org" and "AllStar" in NETS
    assert protocol_for(Target("AllStar", "1999")) == "IAX"


def test_params(tmp_path):
    st = Store(tmp_path); eng = EngineClient("/nonexistent", st); t = Target("AllStar", "1999", "x")
    p, err = eng._params(t); assert p is None and "callsign" in err
    st.settings["callsign"] = "SA7SVR"
    p, err = eng._params(t); assert p is None and "password" in err
    eng.asl_password = "pw"
    p, err = eng._params(t); assert not err and (p["mode"], p["name"], p["iax_user"], p["iax_pass"], p["asl_user"], p["host"], p["port"]) == ("IAX", "1999", "allstar-public", "allstar", "SA7SVR", "1999.nodes.allstarlink.org", 4569)
    assert "pw" not in json.dumps(p)                                           # the portal password never goes to the engine
    st.settings["asl_user"] = "SM5ABC"; assert eng._params(t)[0]["asl_user"] == "SM5ABC"
    assert eng._params(Target("AllStar", "abc", "x"))[0] is None
    eng.servers.remember(t, "my.node.example:4570"); p, _ = eng._params(t); assert (p["host"], p["port"]) == ("my.node.example", 4570)


class FakeLink(QtCore.QObject):
    event = QtCore.Signal(object, dict); finished = QtCore.Signal(object)
    def __init__(self, key, target, path, parent=None):
        super().__init__(parent); self.key, self.target, self.rx, self.tx, self.state, self.sent, self.closed = key, target, set(), False, "connecting", [], False
    def send(self, cmd, **kw): self.sent.append((cmd, kw))
    def close(self): self.closed = True


def pump(cond, timeout=5.0):
    app = W.QApplication.instance(); end = time.time() + timeout
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
        if cond(): return True
    return False


def test_connect_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_client, "Link", FakeLink)
    st = Store(tmp_path); st.settings.update(callsign="SA7SVR"); fake_exe = tmp_path / "dcengine"; fake_exe.write_text("x")
    eng = EngineClient(str(fake_exe), st); eng.asl_password = "pw"
    calls = []
    eng.token_fn = lambda u, pw, cid: (calls.append((u, pw, cid)) or ("TOK", ""))
    eng.dns_fn = lambda node, done: done("node1999.example.org", 4570)
    states = []; eng.status.connect(lambda ln, s, m: states.append((s, m)))
    assert eng.start_rx(1, Target("AllStar", "1999", "Hub")) == ""
    ln = eng.links["AllStar:1999"]
    assert pump(lambda: any(c == "connect" for c, _ in ln.sent))
    cmd, kw = [x for x in ln.sent if x[0] == "connect"][0]
    assert (kw["mode"], kw["host"], kw["port"], kw["iax_user"], kw["iax_pass"], kw["name"], kw["iax_name"]) == ("IAX", "node1999.example.org", 4570, "allstar-public", "allstar", "1999", "TOK/SA7SVR")
    assert calls[0][0] == "SA7SVR" and calls[0][1] == "pw" and "asl_user" not in kw
    # refusal: no engine start, the reason is reported, nothing is left behind
    states.clear(); eng.token_fn = lambda u, pw, cid: ("", "AllStarLink did not accept this callsign / password")
    eng.stop_rx(1); assert "AllStar:1999" not in eng.links
    eng.start_rx(2, Target("AllStar", "2000", "x")); ln2 = eng.links["AllStar:2000"]
    assert pump(lambda: ("error", "AllStarLink did not accept this callsign / password") in states)
    assert not any(c == "connect" for c, _ in ln2.sent) and "AllStar:2000" not in eng.links and ln2.closed
    # cancelled while the sign-in is running: the late answer must not start a connection
    gate = threading.Event()
    eng.token_fn = lambda u, pw, cid: (gate.wait(3) and ("TOK", ""))
    eng.start_rx(3, Target("AllStar", "3000", "x")); ln3 = eng.links["AllStar:3000"]; eng.stop_rx(3); gate.set()
    pump(lambda: False, 0.6); assert not any(c == "connect" for c, _ in ln3.sent)


def test_workspace_and_directory(tmp_path):
    from app.context import Ctx
    from app.ui.workspace import Workspace
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"; ctx = Ctx(st)
    ctx.asl_nodes._set(allstar.parse_nodes("1999|WB6NIL|Allstar Hub|Los Angeles\n2000|SM5ABC|Stockholm repeater|Sweden\n"), time.time())
    ws = Workspace(ctx, "AllStar", lambda *a: None); ws._hosts_loaded()
    assert ws.list.count() == 2 and "Stockholm" in ws.list.item(1).text()
    ws.search.setText("2000"); assert ws.list.count() == 1
    ws.search.setText("12345"); assert ws.list.count() == 1 and "12345" in ws.list.item(0).text()          # a typed node number can always be used
    ws.search.setText("")
    ws.asl_pw.setText("secret"); assert ctx.asl_password == "secret" and st.settings["asl_pw"] == "secret"          # entered once, kept
    assert Ctx(Store(tmp_path)).asl_password == "secret"                                                           # ...and still there after a restart
    ws.asl_rem.setChecked(False); assert st.settings["asl_pw"] == "" and ctx.asl_password == "secret" and Ctx(Store(tmp_path)).asl_password == ""    # not remembered: memory only
    ws.list.setCurrentRow(0); assert ctx.selected.net == "AllStar" and ctx.selected.id == "1999"
    assert ctx.servers.info(ctx.selected)[0]["host"] == "1999.nodes.allstarlink.org"


def test_dtmf(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_client, "Link", FakeLink)
    from app.context import Ctx
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"; fake_exe = tmp_path / "dcengine"; fake_exe.write_text("x")
    eng = EngineClient(str(fake_exe), st); eng.asl_password = "pw"; eng.token_fn = lambda u, p, c: ("TOK", ""); eng.dns_fn = lambda n, d: d("h.example", 4569)
    ctx = Ctx(st, eng); ctx.set_asl_login("SA7SVR", "pw"); t = Target("AllStar", "1999", "Hub")
    assert not ctx.send_dtmf("*3")                                              # nothing selected / connected
    ctx.select(t); ctx.toggle_listen(); ln = eng.links["AllStar:1999"]
    assert not ctx.send_dtmf("*3")                                              # not connected yet: refused, nothing sent
    ln.state = "connected"
    assert not ctx.send_dtmf("12X") and not ctx.send_dtmf("")                   # invalid keys
    assert ctx.send_dtmf("*3a#") and ("dtmf", {"keys": "*3A#"}) in ln.sent


def test_favorite_tile_shows_listening_and_dmr_password_is_kept(tmp_path):
    from app.context import Ctx
    from app.ui.favorites import Favorites
    from app.ui.workspace import Workspace
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"; st.toggle_fav("C4FM", "00006", "Test reflector"); ctx = Ctx(st)
    fv = Favorites(ctx, lambda *a: None); card = fv.cards[0]
    assert card.badge.isHidden()                                           # not listening: no badge
    ctx.select(Target("C4FM", "00006", "Test reflector")); ctx.rules.listen(Target("C4FM", "00006", "Test reflector")); ctx.changed.emit()
    assert not card.badge.isHidden() and "Listening" in card.badge.text()   # listening: the tile says so
    ctx.rules.stop_listening(ctx.rules.rx[0].handle); ctx.changed.emit(); assert card.badge.isHidden()
    ws = Workspace(ctx, "DMR", lambda *a: None); ws.dm_pw.setText("bm-secret")
    assert ctx.dmr_password == "bm-secret" and Ctx(Store(tmp_path)).dmr_password == "bm-secret"      # entered once on the DMR page, kept
    ws.dm_rem.setChecked(False); assert Ctx(Store(tmp_path)).dmr_password == "" and ctx.dmr_password == "bm-secret"


def test_settings_follow_the_mode(tmp_path):
    from app.context import Ctx
    from app.ui.drawers import SettingsDrawer
    d = SettingsDrawer(Ctx(Store(tmp_path)))
    shown = lambda: {k for k, ws in d.grp.items() if all(not w.isHidden() for w in ws)}
    d.set_mode("DMR"); assert shown() == {"DMR"}
    for net in ("NXDN", "P25", "D-Star", "C4FM", "M17", "EchoLink", "AllStar"): d.set_mode(net); assert shown() == {net}
    d.set_mode(None); assert shown() == set(d.grp)                       # pages without a mode: every group, each with its heading
    assert "module" not in d.f and "radio_message" not in d.f             # settings that did nothing are gone
    d.set_mode("P25"); d.f["dmr_id"].setText("2401234"); assert d.grp["P25"][1].findChildren(W.QLineEdit)[0].text() == "2401234"


def test_dmr_password_rules(tmp_path):
    """BrandMeister without the user's personal hotspot password is refused with an explanation (the list only holds a placeholder);
    other masters use the password column of the host list, like Pi-Star; the user's own password always wins."""
    from app import hostlists as H
    from app.store import Store
    from app.engine_client import EngineClient
    from app.rules import Target
    st = Store(tmp_path); st.settings.update(callsign="SA7SVR", dmr_id="2407219")
    eng = EngineClient("/nonexistent", st)
    eng.servers.hosts._set(H.parse_dmr("BM_2402_Sweden\t\t\t2402\t2402.master.brandmeister.network\t\tpassw0rd\t62031\n"
                                       "FreeDMR_Greece\t\t\t2021\t185.243.214.85\t\t\t\tpassw0rd\t62031\n"
                                       "DMR+_X\t\t124734\t141.94.206.232\t\t\t\tPASSWORD\t55555\n"), {}, 1.0)
    t = Target("DMR", "202")
    st.settings.update(dmr_server="2402.master.brandmeister.network", dmr_port=62031)
    p, err = eng._params(t); assert p is None and "personal hotspot password" in err
    eng.dmr_password = "mine"; p, err = eng._params(t); assert p and p["password"] == "mine"
    eng.dmr_password = ""; st.settings.update(dmr_server="185.243.214.85")
    p, err = eng._params(t); assert p and p["password"] == "passw0rd"
    st.settings.update(dmr_server="141.94.206.232", dmr_port=55555)
    p, err = eng._params(t); assert p and p["password"] == "PASSWORD" and p["port"] == 55555


def test_grid_center_and_station_sets():
    from app.engine_client import grid_center, dmr_station_config
    assert grid_center("JO87") == (57.5, 17.0) and grid_center("jo87ab") == pytest.approx((57.0625, 16.041667), abs=1e-5)
    assert grid_center("") is None and grid_center("XX") is None and grid_center("ZZ99") is None and grid_center("JO87ZZ") is None and grid_center("JO8") is None
    s = {"locator": "JO87AB"}
    a, b, c = dmr_station_config(s, 0), dmr_station_config(s, 1), dmr_station_config(s, 2)
    assert a["lat"] != "0" and a["location"] == "JO87AB" and a["freq"] == "438800000" and b["freq"] == "434000000" and b["lat"] == a["lat"]
    assert (c["lat"], c["lon"], c["location"]) == ("0", "0", "")                                                  # the plain old set
    assert dmr_station_config({}, 0)["lat"] == "0"                                                                  # no locator entered: nothing invented


def test_dmr_master_refusing_the_station_values_is_retried_with_the_next_set_and_the_accepted_one_is_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_client, "Link", FakeLink)
    st = Store(tmp_path); st.settings.update(callsign="SA7SVR", dmr_id="2407219", locator="JO87AB", dmr_server="bm.example", dmr_port=62031)
    exe = tmp_path / "dcengine"; exe.write_text("x"); eng = EngineClient(str(exe), st); eng.dmr_password = "pw"
    states = []; eng.status.connect(lambda ln, s, m: states.append((s, m)))
    t = Target("DMR", "202", "x"); assert eng.start_rx(1, t) == ""
    first = eng.links["DMR:202"]
    first.event.emit(first, {"ev": "status", "state": "error", "msg": "DMR_NAK_CONFIG"})                         # the master refused the values (set 0)
    second = eng.links["DMR:202"]; assert second is not first and first.closed and second.rx == {1}               # same listening choice, new login
    assert pump(lambda: any(c == "connect" for c, _ in second.sent))
    kw = [x for x in second.sent if x[0] == "connect"][0][1]; assert kw["freq"] == "434000000" and kw["lat"] != "0" and "_variant" not in kw
    assert ("error", "DMR_NAK_CONFIG") not in states                                                             # the user is not told about the first refusal
    first.event.emit(first, {"ev": "status", "state": "disconnected"}); assert eng.links["DMR:202"] is second     # late words of the replaced link are ignored
    second.event.emit(second, {"ev": "status", "state": "connected"})                                           # accepted: remembered
    assert st.settings["dmr_cfg_variant"] == 1
    eng.stop_rx(1); eng.start_rx(2, t); third = eng.links["DMR:202"]
    assert pump(lambda: any(c == "connect" for c, _ in third.sent)) and [x for x in third.sent if x[0] == "connect"][0][1]["freq"] == "434000000"   # next time it starts with the set that worked
    # every set refused: after the last one the refusal is reported, once
    st.settings["dmr_cfg_variant"] = 0; eng.stop_rx(2); states.clear(); eng.start_rx(3, t)
    for want in (1, 2):
        ln = eng.links["DMR:202"]; ln.event.emit(ln, {"ev": "status", "state": "error", "msg": "DMR_NAK_CONFIG"}); assert states == []
    ln = eng.links["DMR:202"]; ln.event.emit(ln, {"ev": "status", "state": "error", "msg": "DMR_NAK_CONFIG"}); assert ("error", "DMR_NAK_CONFIG") in states


def test_brandmeister_uses_rewind_other_masters_keep_homebrew_and_the_dmr_id_is_sent_plain(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_client, "Link", FakeLink)
    st = Store(tmp_path); st.settings.update(callsign="SA7SVR", dmr_id="2407219", essid="22", locator="JO87AB", dmr_server="185.4.134.95", dmr_port=62031)
    exe = tmp_path / "dcengine"; exe.write_text("x"); eng = EngineClient(str(exe), st); eng.dmr_password = "pw"
    class Hosts:                                              # what the downloaded lists say
        entries = [dict(proto="DMR", host="185.4.134.95", port=62031, name="BrandMeister 2022", src="api"), dict(proto="DMR", host="dmrplus.example", port=55555, name="DMR+_X")]
        def is_brandmeister(self, h): return H.HostLists.is_brandmeister(self, h)
        def dmr_default_password(self, h): return "passw0rd"
    eng.servers.hosts = Hosts()
    t = Target("DMR", "202", "x"); assert eng.start_rx(1, t) == ""; ln = eng.links["DMR:202"]
    assert pump(lambda: any(c == "connect" for c, _ in ln.sent)); kw = [x for x in ln.sent if x[0] == "connect"][0][1]
    assert kw["rewind"] is True and kw["rewind_port"] == 54006 and kw["dmrid"] == 2407219 and ln.rewind                  # the engine drops the ESSID itself: BrandMeister wants the plain ID
    eng.stop_rx(1)
    st.settings.update(dmr_server="dmrplus.example", dmr_port=55555)
    assert eng.start_rx(2, t) == ""; ln = eng.links["DMR:202"]
    assert pump(lambda: any(c == "connect" for c, _ in ln.sent)); kw = [x for x in ln.sent if x[0] == "connect"][0][1]
    assert "rewind" not in kw and not ln.rewind                                                                              # DMR+ and the rest stay on Homebrew
    assert engine_client.uses_rewind({"dmr_protocol": "rewind"}, "x.example") and not engine_client.uses_rewind({"dmr_protocol": "homebrew"}, "2022.master.brandmeister.network")
    assert engine_client.uses_rewind({}, "2022.master.brandmeister.network") and not engine_client.uses_rewind({}, "46.59.68.211")


def test_every_brandmeister_master_is_listed_once_with_its_ip_and_a_saved_pistar_host_becomes_that_entry(tmp_path):
    hl = H.HostLists(tmp_path)
    hl.entries = (H.parse_dmr("BM_2022_Greece\t\t\t2022\t2022.master.brandmeister.network\t\tpassw0rd\t62031\n"
                              "BM_2402_Sweden\t\t\t2402\t2402.master.brandmeister.network\t\tpassw0rd\t62031\n")
                  + H.parse_bm_api('[{"id":2022,"country":"GR","address":"185.4.134.95"}]'))
    hl._reindex() if hasattr(hl, "_reindex") else None
    names = [e["name"] for e in hl.dmr_masters()]
    assert names == ["BM_2402_Sweden", "BrandMeister 2022"]                    # Greece once (the API entry, with the IP); Sweden is not in the API list, so Pi-Star's stays
    e = hl.bm_api_twin("2022.master.brandmeister.network"); assert e and e["host"] == "185.4.134.95" and e["port"] == 62031 and e["name"] == "BrandMeister 2022"
    assert hl.bm_api_twin("185.4.134.95") is None and hl.bm_api_twin("2402.master.brandmeister.network") is None
    assert hl.is_brandmeister("185.4.134.95") and hl.is_brandmeister("2402.master.brandmeister.network") and not hl.is_brandmeister("46.59.68.211")
