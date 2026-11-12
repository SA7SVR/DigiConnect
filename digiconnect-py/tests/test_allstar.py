"""AllStarLink: node list parser/search, portal sign-in token (against a local mock of the AppAuth API), engine parameters,
and the connect sequence (address + token first, then the engine is told to connect)."""
import json, os, sys, pathlib, threading, time, http.server
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app.qt import QtWidgets as W, QtCore
from app import allstar, engine_client
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
    ws.asl_pw.setText("secret"); assert ctx.asl_password == "secret" and "secret" not in json.dumps(st.settings)
    ws.list.setCurrentRow(0); assert ctx.selected.net == "AllStar" and ctx.selected.id == "1999"
    assert ctx.servers.info(ctx.selected)[0]["host"] == "1999.nodes.allstarlink.org"
