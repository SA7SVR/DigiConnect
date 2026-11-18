"""EchoLink: directory sign-in against a fake directory server, the station list per country, who is connected, the page, and the engine voice (fake station)."""
import os, socket, sys, threading, pathlib, subprocess, pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import echolink, countries
from app.engine_client import find_engine

LIST = (b"@@@\r\n4\r\n"
        b"SV1ABC-R\r\nAthens, Greece [ON 21:40]\r\n123456\r\n10.0.0.1\r\n"
        b"SM0XYZ\r\nStockholm [BUSY 21:41]\r\n234567\r\n10.0.0.2\r\n"
        b"*ECHOTEST*\r\nEcho test server\r\n9999\r\n10.0.0.3\r\n"
        b"W1AW-L\r\nNewington CT\r\n345678\r\n10.0.0.4\r\n")


class FakeDirectory:
    """TCP server that behaves like the directory in the way this module expects: 'l...' -> OK or Bad, 's' -> the list, then closes."""
    def __init__(self, password="secret"):
        self.pw, self.seen = password, []
        self.sock = socket.socket(); self.sock.bind(("127.0.0.1", 0)); self.sock.listen(5); self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            try: c, _ = self.sock.accept()
            except OSError: return
            data = c.recv(4096); self.seen.append(data)
            if data.startswith(b"l"):
                ok = (b"\xac\xac" + self.pw.encode() + b"\r") in data
                c.sendall(b"OK\r\n" if ok else b"Bad\r\n")
            elif data == b"s": c.sendall(LIST)
            c.close()


@pytest.fixture
def fake(monkeypatch):
    d = FakeDirectory(); monkeypatch.setattr(echolink, "PORT", d.port); yield d; d.sock.close()


def test_login_message_has_the_documented_shape():
    m = echolink.build_login("sv1abc", "pw", "Athens")
    assert m.startswith(b"lSV1ABC\xac\xacpw\rONLINE") and m.endswith(b"\rAthens\r") and b"(" in m


def test_sign_in_and_list(fake):
    r = echolink.sign_in("SV1ABC", "secret", "Athens", servers=["127.0.0.1"])
    assert r["ok"] and len(r["stations"]) == 4 and r["login_raw"] == "OK"
    assert [s["kind"] for s in r["stations"]] == ["repeater", "station", "conference", "link"]
    assert [s["status"] for s in r["stations"]][:2] == ["ON", "BUSY"]
    assert b"s" in fake.seen


def test_wrong_password_is_reported_as_the_directory_said_it(fake):
    r = echolink.sign_in("SV1ABC", "nope", servers=["127.0.0.1"])
    assert not r["ok"] and "Bad" in r["error"] and not r["stations"]


def test_directory_down_and_missing_fields():
    assert "Cannot reach" in echolink.sign_in("SV1ABC", "x", servers=["127.0.0.1"], exchange=lambda *a, **k: (_ for _ in ()).throw(ConnectionRefusedError()))["error"]
    assert "password" in echolink.sign_in("SV1ABC", "")["error"] and "callsign" in echolink.sign_in("", "x")["error"]


def test_stations_are_grouped_by_country():
    rows = echolink.directory_rows(echolink.parse_stations(LIST))
    by = {r["name"]: r["country"] for r in rows}
    assert by == {"SV1ABC-R": "Greece", "SM0XYZ": "Sweden", "*ECHOTEST*": "", "W1AW-L": "United States"}
    r = {x["name"]: x for x in rows}["SM0XYZ"]
    assert r["host"] == "10.0.0.2" and r["port"] == 5198 and r["proto"] == "ELINK" and "busy" in r["sub"] and "Node 234567" in r["sub"]


def test_who_is_connected_from_the_stations_own_messages():
    st = {}
    echolink.apply_text(st, "Welcome to *HELLAS*\rConference users:\rSM0ABC SV1XYZ DL1ABC\r")
    assert st["calls"] == ["SM0ABC", "SV1XYZ", "DL1ABC"]
    echolink.apply_text(st, "+OH2BH joined")
    echolink.apply_text(st, "SV1XYZ disconnected")
    assert st["calls"] == ["SM0ABC", "DL1ABC", "OH2BH"] and st["lines"][-1] == "SV1XYZ disconnected"


def test_callsign_countries():
    assert countries.of_callsign("SV1ABC-R") == "Greece" and countries.of_callsign("*CONF*") == "" and countries.of_callsign("DL1ABC") == "Germany"


def test_page_lists_by_country_and_shows_who_is_connected(tmp_path, fake):
    from app.qt import QtWidgets as W
    from app.store import Store
    from app.context import Ctx
    from app.rules import Target
    from app.ui.main_window import MainWindow
    app = W.QApplication.instance() or W.QApplication([])
    ctx = Ctx(Store(tmp_path)); ctx.store.settings.update(callsign="SV1ABC"); w = MainWindow(ctx); ws = w.ws["EchoLink"]
    ctx._on_el_done(echolink.sign_in("SV1ABC", "secret", servers=["127.0.0.1"]) | dict(state="ONLINE", silent=False))
    assert ctx.el_signed_in and len(ctx.el_stations) == 4 and ctx.servers.resolve(Target("EchoLink", "SM0XYZ")) == {"host": "10.0.0.2", "port": 5198}
    names = [ws.country.itemText(i) for i in range(ws.country.count())]
    assert {"Greece", "Sweden", "United States"} <= set(names) and ws.country.currentText() == "Greece"      # opens on the user's own country
    assert [e["name"] for e in ws.visible_entries()] == ["SV1ABC-R"]
    ws.country.setCurrentText("Sweden"); assert [e["name"] for e in ws.visible_entries()] == ["SM0XYZ"]
    # connected to a station: its message lists who is there
    t = Target("EchoLink", "SM0XYZ", "SM0XYZ"); ctx.select(t); ctx.rules.listen(t) if hasattr(ctx.rules, "listen") else None
    ctx.el_nodes["SM0XYZ"] = {}; echolink.apply_text(ctx.el_nodes["SM0XYZ"], "Users: SM0ABC SV1XYZ")
    ctx._el_in_use = lambda: True; ws._el_nodes_show()
    assert ws.el_list.count() == 2 and "SM0ABC" in ws.el_list.item(0).text()
    assert ws.el_list.item(1).text().startswith("SV1XYZ") and "Greece" in ws.el_list.item(1).text()


ENGINE = find_engine()


@pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
def test_engine_voice_against_fake_station():
    script = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_elink.py"
    r = subprocess.run([sys.executable, str(script), ENGINE], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


REAL = (b"@@@\n6\n"
        b" \nEchoLink Server v2.6.160\n0\n212.99.197.2\n"                      # a message of the directory: blank call sign, text in the description
        b"SV1ABC-R\nAthens, Greece [ON] 21:40\n123456\n10.0.0.1\n"
        b".\nfiller\n0\n0.0.0.0\n"                                           # filler record: skipped, not counted
        b"SM0XYZ\nStockholm [BUSY] 21:41\n234567\n10.0.0.2\n"
        b"*ECHOTEST*\nEcho test server\n9999\n10.0.0.3\n"
        b"W1AW-L\nNewington CT\n345678\n10.0.0.4\n"
        b"SA7SVR-L\nJonkoping [ON] 08:10\n456789\n10.0.0.5\n"
        b"+++")


def test_list_is_read_the_way_svxlink_reads_it_messages_are_not_stations():
    st, msgs = echolink.parse_list(REAL)
    assert [s["call"] for s in st] == ["SV1ABC-R", "SM0XYZ", "*ECHOTEST*", "W1AW-L", "SA7SVR-L"]
    assert msgs == ["EchoLink Server v2.6.160"]                                       # the 'station' 212.99.197.2 / EchoLink Server v2.6.160 was this
    assert st[0]["place"] == "Athens, Greece" and st[0]["status"] == "ON" and st[0]["at"] == "21:40" and st[0]["node"] == "123456"
    assert st[1]["status"] == "BUSY" and st[2]["kind"] == "conference" and st[3]["kind"] == "link" and st[0]["kind"] == "repeater"
    assert echolink.parse_list(b"garbage") == ([], [])


def test_incorrect_password_is_reported_from_the_list_message():
    bad = b"@@@\n1\n \nINCORRECT PASSWORD\n0\n0.0.0.0\n+++"
    class Ex:
        def __call__(self, host, payload, *a, **k): return b"OK" if payload.startswith(b"l") else bad
    r = echolink.sign_in("SA7SVR-L", "x", "", servers=["h"], exchange=Ex())
    assert not r["ok"] and "INCORRECT PASSWORD" in r["error"]


def test_login_uses_the_same_state_words_as_svxlink():
    import time
    t = time.struct_time((2026, 11, 18, 14, 5, 0, 2, 322, 0))
    assert echolink.build_login("sa7svr-l", "pw", "x", "ONLINE", t) == b"lSA7SVR-L\xac\xacpw\rONLINE3.38(14:05)\rx\r"
    assert echolink.build_login("sa7svr-l", "pw", "x", "BUSY", t).split(b"\r")[1] == b"BUSY3.40(14:05)"
    assert echolink.build_login("sa7svr-l", "pw", "x", "OFFLINE", t).split(b"\r")[1] == b"OFF-V3.40"
