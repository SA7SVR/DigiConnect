"""Registration + demo/licence against the real PHP server code (php -S on localhost), and the offline rules."""
import os, shutil, socket, sqlite3, subprocess, sys, time, pathlib
import urllib.request
import pytest
from app import license as L

SERVER = pathlib.Path(__file__).resolve().parents[1] / "server" / "digiconnect"
pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _php_flags():
    """php.exe from a CI image can come without php.ini, so sqlite is not loaded: switch it on explicitly when `php -m` does not list it."""
    have = subprocess.run(["php", "-m"], capture_output=True, text=True).stdout.lower()
    return [] if "pdo_sqlite" in have else ["-d", "extension=pdo_sqlite", "-d", "extension=sqlite3"]


@pytest.fixture()
def srv(tmp_path):
    root = tmp_path / "dc"; shutil.copytree(SERVER, root, ignore=shutil.ignore_patterns("data", "pkg", "hosts"))
    (root / "data").mkdir(); (root / "pkg").mkdir(); (root / "hosts").mkdir()
    (root / "config.php").write_text("<?php return ['admin_user'=>'a','admin_pass'=>'b','demo_days'=>14,'gate'=>true];")
    port = free_port(); log = (tmp_path / "php.log").open("w+")
    p = subprocess.Popen(["php", *_php_flags(), "-S", f"127.0.0.1:{port}", "-t", str(root)], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
        except OSError: time.sleep(0.1)
    class S: pass
    s = S(); s.port, s.root, s.proc = port, root, p; s.base = f"http://127.0.0.1:{port}/"
    s.sql = lambda q, *a: _sql(root, q, a)
    try: urllib.request.urlopen(s.base + "manifest.php?id=probe&v=2.1.0")
    except Exception as ex:                                                    # say WHY the PHP server answers with an error (missing extension ...)
        log.flush(); log.seek(0); p.kill(); pytest.fail(f"php server probe failed: {ex}\n--- php output ---\n{log.read()[-3000:]}\n--- php -m ---\n{subprocess.run(['php', '-m'], capture_output=True, text=True).stdout[-1500:]}")
    s.sql("DELETE FROM dc_installs"); s.sql("DELETE FROM dc_events")                                   # the probe above is not part of any test
    yield s
    p.kill(); p.wait()


def _sql(root, q, args=()):
    c = sqlite3.connect(root / "data" / "digiconnect.db"); c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, args).fetchall()]; c.commit(); return r
    finally: c.close()


class FakeStore:
    def __init__(self): self.settings = {}
    def save_settings(self): pass


def lic(srv, iid="inst-1"):
    return L.License(FakeStore(), lambda: dict(id=iid, v="2.1.0", os="linux", arch="x64", shell="2.1.0"), base=srv.base)


PERSON = dict(name="Panagiotis", call="sa7svr", dmr_id="2400123", mail="Hellas@Example.org")


def test_validate():
    assert L.validate(PERSON) == []
    assert set(L.validate(dict(name="", call="123", dmr_id="12", mail="x"))) == {"name", "call", "dmr_id", "mail"}


def test_new_installation_must_register_then_gets_the_demo(srv):
    l = lic(srv)
    v = l.verdict(l.check()); assert v.kind == "register"
    m = l.register(PERSON); v = l.verdict(m)
    assert v.kind == "ok" and v.state == "demo" and v.left == "14 days left"
    row = srv.sql("SELECT call,name,mail,dmr_id,consent_at FROM dc_installs")[0]
    assert (row["call"], row["name"], row["mail"], row["dmr_id"]) == ("SA7SVR", "Panagiotis", "hellas@example.org", "2400123") and row["consent_at"]
    assert l.verdict(l.check()).kind == "ok"                                              # registered stays registered


def test_server_refuses_bad_or_unconsented_registration(srv):
    l = lic(srv)
    for bad, why in ((dict(PERSON, dmr_id="12"), "dmr_id"), (dict(PERSON, mail="nope"), "mail"), (dict(PERSON, call="12"), "call"), (dict(PERSON, name=" "), "name")):
        with pytest.raises(L.LicenseError, match=why): l.register(bad)
    import urllib.request, urllib.parse, json
    d = urllib.parse.urlencode(dict(id="x1", name="a", call="SA7SVR", dmr_id="2400123", mail="a@b.se")).encode()      # no consent
    assert json.loads(urllib.request.urlopen(srv.base + "register.php", d).read()) == {"ok": False, "err": "consent"}


def test_admin_lock_and_activate_are_followed(srv):
    l = lic(srv); l.register(PERSON)
    srv.sql("UPDATE dc_installs SET state='locked', note='Contact SA7SVR' WHERE id='inst-1'")
    v = l.verdict(l.check()); assert v.kind == "blocked" and "Contact SA7SVR" in v.msg
    srv.sql("UPDATE dc_installs SET state='full' WHERE id='inst-1'"); assert l.verdict(l.check()).state == "full"
    srv.sql("UPDATE dc_installs SET enabled=0, state='disabled' WHERE id='inst-1'"); assert l.verdict(l.check()).kind == "blocked"


def test_demo_expires(srv):
    l = lic(srv); l.register(PERSON)
    srv.sql("UPDATE dc_installs SET demo_until=? WHERE id='inst-1'", int(time.time()) - 5)
    v = l.verdict(l.check()); assert v.kind == "blocked" and "demo period has ended" in v.msg


def test_reinstall_with_same_callsign_and_email_keeps_the_state_but_other_email_gets_a_new_demo(srv):
    a = lic(srv, "inst-1"); a.register(PERSON)
    srv.sql("UPDATE dc_installs SET state='locked' WHERE id='inst-1'")
    b = lic(srv, "inst-2"); assert b.verdict(b.register(PERSON)).kind == "blocked"          # same person: the earlier state returns
    c = lic(srv, "inst-3"); assert c.verdict(c.register(dict(PERSON, mail="other@example.org"))).kind == "ok"


def test_gate_off_in_the_panel_makes_everything_full(srv):
    l = lic(srv); l.register(PERSON)
    srv.sql("INSERT INTO dc_kv(k,v) VALUES('gate','0')"); assert l.verdict(l.check()).state == "full"


def test_offline_rules_follow_the_server_setting(srv):
    l = lic(srv); l.register(PERSON)
    srv.proc.kill(); srv.proc.wait()                                                          # the server disappears
    now = time.time()
    assert l.verdict(None, "down", now).kind == "offline"                                     # default = require
    c = l.cache(); c.update(offline="grace", offline_days=7, ts=now - 3 * 86400); l.store.settings["lic"] = c
    assert l.verdict(None, "down", now).allowed
    c["ts"] = now - 8 * 86400; assert l.verdict(None, "down", now).kind == "offline"
    c.update(offline="allow", ts=now - 400 * 86400); assert l.verdict(None, "down", now).allowed
    c.update(state="locked", msg="Contact SA7SVR"); assert l.verdict(None, "down", now).kind == "blocked"     # a block already known stays


def test_first_start_without_server_cannot_register(srv):
    srv.proc.kill(); srv.proc.wait(); l = lic(srv)
    v = l.evaluate(); assert v.kind == "offline" and "first start" in v.msg


def test_panel_settings_reach_the_program(srv):
    l = lic(srv); l.register(PERSON)
    srv.sql("INSERT INTO dc_kv(k,v) VALUES('offline','grace'),('offline_days','3'),('donate_url','https://example.org/d')")
    l.check(); c = l.cache(); assert (c["offline"], c["offline_days"], c["donate"]) == ("grace", 3, "https://example.org/d")
