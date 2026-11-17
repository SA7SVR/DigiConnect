"""The online-stations list: grid squares become positions, networks are read from what a station listens to, bad answers are ignored."""
import json
from app import online, net


def test_grid_square_centre():
    assert online.grid_centre("JO89") == (17.0, 59.5)          # JO89 is central Sweden (Stockholm area)
    lon, lat = online.grid_centre("JO89ab")
    assert 16.0 < lon < 16.1 and 59.0 < lat < 59.1
    assert online.grid_centre("") is None and online.grid_centre("ZZ99") is None and online.grid_centre("JO") is None


def test_network_of_station():
    assert online.net_of("DMR:24015", "") == "DMR"
    assert online.net_of("", "D-Star:REF001 C") == "D-Star"
    assert online.net_of("", "") == "Program"


def test_fetch_keeps_public_fields_only(monkeypatch):
    body = {"ok": True, "t": 1, "stations": [{"call": "SA7SVR", "grid": "JO89", "rx": "DMR:24015", "tx": "", "ptt": 1, "id": 99, "email": "x@y"},
                                             {"call": ""}, "junk"]}
    monkeypatch.setattr(net, "get", lambda *a, **k: json.dumps(body).encode())
    rows = online.fetch("https://example.invalid/online.php")
    assert rows == [{"call": "SA7SVR", "grid": "JO89", "rx": "DMR:24015", "tx": "", "ptt": 1}]


def test_fetch_gives_nothing_on_a_bad_answer(monkeypatch):
    monkeypatch.setattr(net, "get", lambda *a, **k: b"<html>error</html>")
    assert online.fetch("https://example.invalid/online.php") == []
    monkeypatch.setattr(net, "get", lambda *a, **k: json.dumps({"ok": False}).encode())
    assert online.fetch("https://example.invalid/online.php") == []
