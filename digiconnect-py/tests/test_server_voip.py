"""VoIP account requests, run against the real PHP code: the endpoint the program calls (voip_request.php) and the panel page where the owner approves.
Nothing is simulated: the requests are real HTTP calls to the PHP server, the answers are what it really returns."""
import json, re, urllib.parse, urllib.request, urllib.error
import pytest
from test_license import srv, shutil  # noqa: F401
from test_server_payments import Admin

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")

REQ = dict(action="submit", name="Nikos P", call="sv1abc", want="2001", msg="Hello", lang="el", consent="1", website="")


def call(srv, **f):
    rq = urllib.request.Request(srv.base + "voip_request.php", urllib.parse.urlencode(f).encode())
    try: return json.loads(urllib.request.urlopen(rq).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())


def open_requests(srv, a=None, **kw):
    a = a or Admin(srv.base)
    a.post("voip", "voip_set", voip_on="1", voip_server=kw.get("server", "sip.example.org"), voip_port=str(kw.get("port", 5060)), voip_transport=kw.get("transport", "udp"), voip_domain=kw.get("domain", ""))
    return a


def test_requests_are_refused_until_the_owner_opens_them(srv):
    assert call(srv, action="info") == {"ok": True, "open": False}
    assert call(srv, **REQ) == {"ok": False, "err": "closed"}
    assert srv.sql("SELECT COUNT(*) n FROM dc_voip_req")[0]["n"] == 0
    open_requests(srv)
    assert call(srv, action="info") == {"ok": True, "open": True}


def test_a_request_is_stored_with_a_secret_token_that_only_the_sender_knows(srv):
    open_requests(srv)
    r = call(srv, **REQ)
    assert r["ok"] and r["id"] > 0 and len(r["token"]) == 32
    row = srv.sql("SELECT * FROM dc_voip_req")[0]
    assert row["call"] == "SV1ABC" and "email" not in row and row["want"] == "2001" and row["status"] == "new"
    assert row["tok"] != r["token"] and len(row["tok"]) == 64                                  # only the hash of the token is kept
    assert call(srv, action="status", id=r["id"], token=r["token"]) == {"ok": True, "status": "new", "reason": ""}
    assert call(srv, action="status", id=r["id"], token="0" * 32) == {"ok": False, "err": "unknown"}
    assert call(srv, action="status", id=r["id"] + 5, token=r["token"]) == {"ok": False, "err": "unknown"}
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_req'")[0]["n"] == 1      # the owner is alerted


@pytest.mark.parametrize("bad,err", [(dict(name=""), "name"), (dict(call="hello world"), "call"), (dict(call=""), "call"), (dict(consent="0"), "consent")])
def test_a_bad_request_is_refused_and_stores_nothing(srv, bad, err):
    open_requests(srv)
    assert call(srv, **dict(REQ, **bad)) == {"ok": False, "err": err}
    assert srv.sql("SELECT COUNT(*) n FROM dc_voip_req")[0]["n"] == 0


def test_a_robot_that_fills_the_hidden_field_gets_an_answer_but_nothing_is_stored(srv):
    open_requests(srv)
    r = call(srv, **dict(REQ, website="http://spam.example"))
    assert r["ok"] and r["id"] == 0 and srv.sql("SELECT COUNT(*) n FROM dc_voip_req")[0]["n"] == 0


def test_one_open_request_per_callsign_and_a_limit_per_address(srv):
    open_requests(srv)
    assert call(srv, **REQ)["ok"]
    assert call(srv, **dict(REQ, name="Other"))["err"] == "pending"                              # same callsign
    for i in range(4): assert call(srv, **dict(REQ, call=f"SV1AB{chr(68 + i)}"))["ok"]
    assert call(srv, **dict(REQ, call="SV1ZZZ"))["err"] == "too_many"                           # the 6th from one address within 24 h


def test_the_owner_approves_the_program_gets_the_details_once_and_the_password_is_wiped(srv):
    a = open_requests(srv, server="sip.example.org", port=5061, transport="tls", domain="pbx.example.org")
    r = call(srv, **REQ)
    page = a.page("voip")
    assert "SV1ABC" in page and "Nikos P" in page and not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", page)
    rid = str(r["id"])
    a.post("voip", "voip_approve", rid=rid, ext="2001", pw="short")                              # too short: refused
    assert srv.sql("SELECT status FROM dc_voip_req")[0]["status"] == "new"
    a.post("voip", "voip_approve", rid=rid, ext="2001", pw="Secret-pass-1")
    s = call(srv, action="status", id=r["id"], token=r["token"])
    assert s == {"ok": True, "status": "approved", "delivered": False, "ext": "2001", "password": "Secret-pass-1", "server": "sip.example.org", "port": 5061, "transport": "tls", "domain": "pbx.example.org"}
    assert call(srv, action="ack", id=r["id"], token=r["token"]) == {"ok": True}
    again = call(srv, action="status", id=r["id"], token=r["token"])
    assert again["status"] == "approved" and again["delivered"] is True and again["password"] == "" and again["ext"] == "2001"
    assert srv.sql("SELECT pw FROM dc_voip_req")[0]["pw"] == ""                                  # the password is gone from the server
    assert "Secret-pass-1" not in a.page("voip") and "Secret-pass-1" not in a.page("activity")
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_ok'")[0]["n"] == 1
    assert call(srv, **dict(REQ, call="SV1ABC"))["ok"]                                          # nothing is pending any more: the same callsign may ask again


def test_a_rejected_request_says_so_and_never_carries_a_password(srv):
    a = open_requests(srv)
    r = call(srv, **REQ)
    a.post("voip", "voip_reject", rid=str(r["id"]), reason="No licence found")
    assert call(srv, action="status", id=r["id"], token=r["token"]) == {"ok": True, "status": "rejected", "reason": "No licence found"}


def test_deleting_a_request_makes_its_token_useless(srv):
    a = open_requests(srv)
    r = call(srv, **REQ)
    a.post("voip", "voip_del", rid=str(r["id"]))
    assert call(srv, action="status", id=r["id"], token=r["token"])["err"] == "unknown"


def test_the_panel_page_and_menu_render_without_php_errors(srv):
    a = Admin(srv.base)
    for p in ("voip", "dashboard", "activity"):
        html = a.page(p)
        assert "<aside>" in html and not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", html), p
    assert "?p=voip" in a.page("dashboard")
    open_requests(a=a, srv=srv); call(srv, **REQ)
    html = a.page("activity")
    assert "SV1ABC" in html and "VoIP" in html and not re.search(r"(Fatal error|Warning:|Notice:)", html)


def test_no_e_mail_is_asked_for_stored_or_sent(srv):
    a = open_requests(srv)
    call(srv, **dict(REQ, email="nikos@example.org"))                                            # even if a client sent one, it is ignored
    r = srv.sql("SELECT * FROM dc_voip_req")[0]
    assert "nikos@example.org" not in json.dumps(r) and "email" not in r
    html = a.page("voip")
    assert "mailto:" not in html and "nikos@example.org" not in html
    a.post("voip", "voip_approve", rid=str(r["id"]), ext="2001", pw="Secret-pass-1")
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='mail'")[0]["n"] == 0            # not even an attempt to send a mail
