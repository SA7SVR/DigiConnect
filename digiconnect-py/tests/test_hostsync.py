"""Host lists from RefCheck.Radio through our server: token only on the server, one request per list per hour, official data kept as it is,
a bad or shrunken answer never replaces the last good copy (real PHP code; the RefCheck site is a small local stand-in)."""
import shutil, subprocess, threading, http.server, pathlib
import pytest
from test_license import srv, _php_flags, SERVER, free_port  # noqa: F401
from test_server_payments import Admin

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")
TOKEN = "b" * 40
HEAD = "#\n# YSFHosts.txt\n#\n# Reflector data provided by DVRef - https://dvref.com/aup/\n#\n"
import json as _j
JSON = _j.dumps({"_refcheck_metadata": {"filename": "YSFHosts.json"}, "reflectors": [{"designator": "00006", "name": "HELLAS Zone A", "ipv4": "46.59.68.211", "port": 42000}]}, indent=2)
GOOD = HEAD + "".join(f"{i:05d};GR-TEST{i};Test {i};10.0.0.{i % 250};42000;{i % 99:03d};\n" for i in range(6, 56))


@pytest.fixture()
def rc(srv):
    seen = []; state = {"body": GOOD, "code": 200, "json": JSON}
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            seen.append((self.path, self.headers.get("Authorization")))
            if self.headers.get("Authorization") != "Token " + TOKEN: self.send_response(401); self.end_headers(); return
            self.send_response(state["code"]); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write((state["json"] if "/json/" in self.path else state["body"]).encode())
    port = free_port(); web = http.server.HTTPServer(("127.0.0.1", port), H); threading.Thread(target=web.serve_forever, daemon=True).start()
    for f in (SERVER / "hosts").glob("*.php"): shutil.copy(f, srv.root / "hosts" / f.name)
    (srv.root / "config.php").write_text(f"<?php return ['admin_user'=>'a','admin_pass'=>'b','demo_days'=>14,'gate'=>true,'refcheck_base'=>'http://127.0.0.1:{port}/'];")
    srv.seen, srv.state = seen, state
    def run():
        r = subprocess.run(["php", *_php_flags(), str(srv.root / "hosts" / "refresh.php"), "YSFHosts"], capture_output=True, text=True, timeout=120)
        return r.stdout + r.stderr
    srv.run = run
    def run_json():
        r = subprocess.run(["php", *_php_flags(), str(srv.root / "hosts" / "refresh.php"), "YSFHosts.json"], capture_output=True, text=True, timeout=120); return r.stdout + r.stderr
    srv.run_json = run_json
    srv.pub = lambda: (srv.root / "hosts" / "pub" / "YSFHosts.txt")
    srv.data = lambda: (srv.root / "data" / "hosts" / "YSFHosts.txt")
    yield srv
    web.shutdown()


def stored(s):
    p = s.pub() if s.pub().is_file() else s.data(); return p.read_text()


def test_token_is_entered_in_the_panel_and_checked(rc):
    a = Admin(rc.base)
    assert "not set" in a.page("servers") or "δεν έχει μπει" in a.page("servers")
    a.post("servers", "set_refcheck", refcheck_token="bad token!")
    assert rc.sql("SELECT v FROM dc_kv WHERE k='refcheck_token'") == []
    a.post("servers", "set_refcheck", refcheck_token=TOKEN)
    assert rc.sql("SELECT v FROM dc_kv WHERE k='refcheck_token'")[0]["v"] == TOKEN
    assert TOKEN not in a.page("servers")                                  # only the last 4 characters are shown


def test_list_comes_from_refcheck_unchanged_with_its_header_and_only_once_an_hour(rc):
    Admin(rc.base).post("servers", "set_refcheck", refcheck_token=TOKEN)
    out = rc.run(); assert "OK" in out, out
    txt = stored(rc)
    assert HEAD in txt and "00006;GR-TEST6;Test 6;10.0.0.6;42000;006;" in txt          # the official header and every line exactly as sent
    assert rc.seen == [("/ysf/", "Token " + TOKEN)]
    rc.run(); rc.run()
    assert len(rc.seen) == 1                                                 # the copy is kept for the hour: no second request


def test_a_broken_or_shrunken_answer_never_replaces_the_good_copy_and_no_other_mirror_is_used(rc):
    a = Admin(rc.base); a.post("servers", "set_refcheck", refcheck_token=TOKEN); rc.run(); good = stored(rc)
    rc.sql("DELETE FROM dc_kv WHERE k LIKE 'refcheck_try_%'")                # pretend an hour has passed
    rc.state["body"] = HEAD + "00006;GR-TEST6;Test 6;10.0.0.6;42000;006;\n00007;GR-X;X;10.0.0.7;42000;001;\n00008;GR-Y;Y;10.0.0.8;42000;001;\n"
    out = rc.run(); assert "FAIL" in out and "shrank" in out, out
    assert stored(rc) == good
    rc.sql("DELETE FROM dc_kv WHERE k LIKE 'refcheck_try_%'")
    rc.state["body"] = "<html>Too many requests</html>"
    out = rc.run(); assert "FAIL" in out, out
    assert stored(rc) == good and len(rc.seen) == 3                          # nothing else was asked


def test_json_list_is_stored_exactly_as_sent_and_can_be_downloaded_by_hand(rc):
    import urllib.request
    Admin(rc.base).post("servers", "set_refcheck", refcheck_token=TOKEN)
    out = rc.run_json(); assert "OK" in out, out
    got = urllib.request.urlopen(rc.base + "hosts/get.php?f=YSFHosts.json")
    assert got.headers["Content-Type"].startswith("application/json") and got.read().decode() == JSON      # no comment lines, nothing added
    assert rc.seen[-1] == ("/json/ysf/", "Token " + TOKEN)


def test_txt_list_can_be_downloaded_by_hand_and_appears_in_the_panel(rc):
    import urllib.request
    a = Admin(rc.base); a.post("servers", "set_refcheck", refcheck_token=TOKEN); rc.run()
    assert urllib.request.urlopen(rc.base + "hosts/get.php?f=YSFHosts.txt").read().decode().count("GR-TEST") == 50
    assert "YSFHosts.txt" in a.page("servers") and "YSFHosts.json" in a.page("servers")
