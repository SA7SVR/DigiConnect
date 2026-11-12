"""The 'I am online' message: real HTTP request to a local server, content checked."""
import json, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from app.store import Store
from app.context import Ctx
from app.rules import Target
from app.presence import Presence


def test_presence_sends_station_state(tmp_path):
    got = []
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            got.append(parse_qs(urlparse(self.path).query)); b = b'{"ok":true}'
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    (tmp_path / "data").mkdir(); st = Store(tmp_path / "data"); st.settings["callsign"] = "sa7svr"; st.settings["locator"] = "jo77"
    ctx = Ctx(st)
    class U:
        def params(self): return dict(id="abc123", v="2.0.3", os="linux", arch="x64", shell="2.0.0")
    p = Presence(ctx, U(), f"http://127.0.0.1:{srv.server_port}/ping.php")
    ctx.rules.listen(Target("DMR", "91", "Greece"))
    p.ping()
    for _ in range(100):
        if got: break
        time.sleep(0.05)
    srv.shutdown()
    assert got, "nothing was sent"
    q = {k: v[0] for k, v in got[0].items()}
    assert q["id"] == "abc123" and q["call"] == "SA7SVR" and q["grid"] == "JO77" and q["os"] == "linux" and q["rx"] == "DMR:91" and q["ptt"] == "0"
    time.sleep(0.2); assert p.last_ok


def test_presence_can_be_switched_off(tmp_path):
    (tmp_path / "data").mkdir(); st = Store(tmp_path / "data"); st.settings["share_presence"] = False
    ctx = Ctx(st)
    class U:
        def params(self): return dict(id="x", v="1", os="linux", arch="x64", shell="2")
    p = Presence(ctx, U(), "http://127.0.0.1:9/ping.php"); p.ping()
    assert p.sent == 0 and not p._busy
