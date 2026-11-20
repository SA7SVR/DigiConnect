"""VoIP account requests, run against the real PHP code: the endpoint the program calls (voip_request.php) and the panel page where the Admin approves.
Nothing is simulated: the requests are real HTTP calls to the PHP server, the answers are what it really returns."""
import json, re, time, urllib.parse, urllib.request, urllib.error
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
    a.post("voip", "voip_set", _tab="set", voip_on="1", voip_server=kw.get("server", "sip.example.org"), voip_port=str(kw.get("port", 5060)), voip_transport=kw.get("transport", "udp"), voip_domain=kw.get("domain", ""))
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
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_req'")[0]["n"] == 1      # the Admin is alerted


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


def approve(srv, a, r, ext="2001", pw="Secret-pass-1"):
    a.post("voip", "voip_approve", _tab="set", rid=str(r["id"]), ext=ext, pw=pw)


def test_the_owner_approves_and_the_program_gets_the_details_and_the_password_stays_with_the_account(srv):
    a = open_requests(srv, server="sip.example.org", port=5061, transport="tls", domain="pbx.example.org")
    r = call(srv, **REQ)
    page = a.page("voip", tab="req")
    assert "SV1ABC" in page and "Nikos P" in page and not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", page)
    rid = str(r["id"])
    a.post("voip", "voip_approve", _tab="set", rid=rid, ext="2001", pw="short")                              # too short: refused
    assert srv.sql("SELECT status FROM dc_voip_req")[0]["status"] == "new"
    approve(srv, a, r)
    want = {"ok": True, "status": "approved", "ext": "2001", "password": "Secret-pass-1", "server": "sip.example.org", "port": 5061, "transport": "tls", "domain": "pbx.example.org", "blocked": False, "block_until": 0, "block_reason": ""}
    assert call(srv, action="status", id=r["id"], token=r["token"]) == want
    assert call(srv, action="status", id=r["id"], token=r["token"]) == want                      # asked again (any time the program signs in): the same answer, nothing was wiped
    assert call(srv, action="ack", id=r["id"], token=r["token"]) == {"ok": False, "err": "action"}   # the old "erase after receiving" step is gone
    assert srv.sql("SELECT pw FROM dc_voip_req")[0]["pw"] == "Secret-pass-1" and srv.sql("SELECT delivered_t FROM dc_voip_req")[0]["delivered_t"]
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_ok'")[0]["n"] == 1
    for t in ("req", "acc", "set"): assert "Secret-pass-1" not in a.page("voip", tab=t) or t == "acc"   # the password is typed/seen only in the accounts tab where the Admin manages it
    assert "Secret-pass-1" not in a.page("activity")
    assert call(srv, **dict(REQ, call="SV1ABC"))["ok"]                                          # nothing is pending any more: the same callsign may ask again


def test_a_new_password_set_in_the_panel_reaches_the_program_by_itself(srv):
    a = open_requests(srv); r = call(srv, **REQ); approve(srv, a, r)
    a.post("voip", "voip_pw", _tab="set", rid=str(r["id"]), ext="2005", pw="Brand-new-pw-2")
    s = call(srv, action="status", id=r["id"], token=r["token"])
    assert s["password"] == "Brand-new-pw-2" and s["ext"] == "2005"
    a.post("voip", "voip_pw", _tab="set", rid=str(r["id"]), ext="2005", pw="abc")                           # too short: refused, the old one stays
    assert call(srv, action="status", id=r["id"], token=r["token"])["password"] == "Brand-new-pw-2"
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_pw'")[0]["n"] == 1


def test_one_account_can_be_blocked_for_a_time_or_until_lifted_without_closing_voip_for_everybody(srv):
    a = open_requests(srv); r = call(srv, **REQ); approve(srv, a, r); rid = str(r["id"])
    q = lambda: call(srv, action="status", id=r["id"], token=r["token"])
    assert q()["blocked"] is False
    a.post("voip", "voip_block", _tab="set", rid=rid, hours="0", reason="Misuse")                           # until lifted
    s = q(); assert s["blocked"] is True and s["block_reason"] == "Misuse" and s["block_until"] == 0 and s["password"] == "Secret-pass-1"
    a.post("voip", "voip_unblock", _tab="set", rid=rid); assert q()["blocked"] is False
    a.post("voip", "voip_block", _tab="set", rid=rid, hours="24", reason="Cool down")                       # for a day
    s = q(); assert s["blocked"] is True and abs(s["block_until"] - (time.time() + 86400)) < 120
    srv.sql("UPDATE dc_voip_req SET block_until=?", int(time.time()) - 5)                    # the time has passed: it lifts itself
    assert q()["blocked"] is False
    assert call(srv, action="info")["open"] is True                                             # the global switch was never touched


def test_a_program_that_lost_its_token_gets_its_account_back_by_installation_and_callsign(srv):
    a = open_requests(srv); r = call(srv, **dict(REQ, inst="inst-77")); approve(srv, a, r)
    n = call(srv, action="recover", inst="inst-77", call="SV1ABC")
    assert n["ok"] and n["id"] == r["id"] and n["token"] != r["token"]
    assert call(srv, action="status", id=n["id"], token=n["token"])["password"] == "Secret-pass-1"
    assert call(srv, action="status", id=r["id"], token=r["token"]) == {"ok": False, "err": "unknown"}   # the old token no longer works
    assert call(srv, action="recover", inst="other-install", call="SV1ABC") == {"ok": False, "err": "unknown"}   # another installation cannot take the account
    assert call(srv, action="recover", inst="inst-77", call="SV9ZZZ") == {"ok": False, "err": "unknown"}


def test_the_panel_has_tabs_and_the_accounts_tab_lists_who_has_an_account(srv):
    a = open_requests(srv); r = call(srv, **dict(REQ, inst="inst-1")); r2 = call(srv, **dict(REQ, call="SM0XYZ", name="Anna S"))
    assert "SM0XYZ" in a.page("voip", tab="req") and "tab=acc" in a.page("voip") and "tab=set" in a.page("voip")
    approve(srv, a, r)
    acc = a.page("voip", tab="acc")
    assert "SV1ABC" in acc and "Nikos P" in acc and "2001" in acc and "SM0XYZ" not in acc          # only those who got an account
    assert "SM0XYZ" in a.page("voip", tab="req") and "SV1ABC" not in a.page("voip", tab="req")      # open requests only
    a.post("voip", "voip_block", _tab="set", rid=str(r["id"]), hours="0", reason="x"); assert "μέχρι να άρεις" in a.page("voip", tab="acc") or "until lifted" in a.page("voip", tab="acc")
    assert not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", a.page("voip", tab="acc") + a.page("voip", tab="set"))


def test_the_accounts_tab_tells_online_from_active_but_not_signed_in_from_offline(srv):
    a = open_requests(srv); r = call(srv, **dict(REQ, inst="inst-1")); approve(srv, a, r)
    now = int(time.time())
    srv.sql("INSERT OR REPLACE INTO dc_installs(id,first_seen,last_seen,last_ping,voip,voip_ext) VALUES('inst-1',?,?,?,1,'2001')", now, now, now)
    assert "VoIP online" in a.page("voip", tab="acc")
    srv.sql("UPDATE dc_installs SET voip=0"); acc = a.page("voip", tab="acc"); assert "αδρανής" in acc or "idle" in acc
    srv.sql("UPDATE dc_installs SET last_ping=?", now - 3600); assert "offline" in a.page("voip", tab="acc")
    srv.sql("UPDATE dc_installs SET voip=NULL"); assert "VoIP online" not in a.page("voip", tab="acc")     # an older program reports nothing: nothing is invented


def test_voip_accounts_and_settings_are_in_the_backup_and_come_back_with_a_restore(srv):
    a = open_requests(srv, server="sip.example.org"); r = call(srv, **REQ); approve(srv, a, r)
    a.post("voip", "voip_block", _tab="set", rid=str(r["id"]), hours="0", reason="Misuse")
    a.post("backups", "backup_now"); good = sorted((srv.root / "data" / "backups").glob("digiconnect-*-manual-*.sqlite"))[-1].name
    a.post("voip", "voip_del", _tab="set", rid=str(r["id"])); srv.sql("UPDATE dc_kv SET v='0' WHERE k='voip_on'")
    assert not srv.sql("SELECT 1 FROM dc_voip_req")
    a.post("backups", "backup_restore", file=good, confirm="RESTORE")
    row = srv.sql("SELECT * FROM dc_voip_req")[0]
    assert row["call"] == "SV1ABC" and row["pw"] == "Secret-pass-1" and row["ext"] == "2001" and row["blocked"] == 1 and row["block_reason"] == "Misuse"
    assert srv.sql("SELECT v FROM dc_kv WHERE k='voip_on'")[0]["v"] == "1" and srv.sql("SELECT v FROM dc_kv WHERE k='voip_server'")[0]["v"] == "sip.example.org"
    assert call(srv, action="status", id=r["id"], token=r["token"])["status"] == "approved"             # the program's token still works after a restore


def test_a_rejected_request_says_so_and_never_carries_a_password(srv):
    a = open_requests(srv)
    r = call(srv, **REQ)
    a.post("voip", "voip_reject", _tab="set", rid=str(r["id"]), reason="No licence found")
    assert call(srv, action="status", id=r["id"], token=r["token"]) == {"ok": True, "status": "rejected", "reason": "No licence found"}


def test_deleting_a_request_makes_its_token_useless(srv):
    a = open_requests(srv)
    r = call(srv, **REQ)
    a.post("voip", "voip_del", _tab="set", rid=str(r["id"]))
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
    html = a.page("voip", tab="req") + a.page("voip", tab="acc")
    assert "mailto:" not in html and "nikos@example.org" not in html
    a.post("voip", "voip_approve", _tab="set", rid=str(r["id"]), ext="2001", pw="Secret-pass-1")
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='mail'")[0]["n"] == 0            # not even an attempt to send a mail


def test_both_lists_have_a_search_box_and_scroll_inside_themselves(srv):
    a = open_requests(srv); r = call(srv, **dict(REQ, inst="inst-1")); call(srv, **dict(REQ, call="SM0XYZ", name="Άννα S")); approve(srv, a, r)
    acc = a.page("voip", tab="acc"); req = a.page("voip", tab="req")
    for html, who in ((acc, "sv1abc"), (req, "sm0xyz")):
        assert 'id="vqs"' in html and 'oninput="vqfind(this)"' in html and 'id="vqlist"' in html and "overflow-y:auto" in html
        assert f'data-q="' in html and who in html.lower()                                         # what the search looks at: callsign, name, extension, status ...
    assert "<small id=\"vqcnt\">1 / 1</small>" in acc and "<small id=\"vqcnt\">1 / 1</small>" in req
    assert 'id="vqs"' not in a.page("voip", tab="set")                                           # the settings tab has no list


def test_a_person_who_asks_again_from_another_computer_is_offered_the_same_details_and_gets_them_back(srv):
    a = open_requests(srv); r = call(srv, **dict(REQ, inst="old-pc")); approve(srv, a, r)                          # the first computer
    r2 = call(srv, **dict(REQ, inst="new-pc"))                                                                    # a new computer: it has another installation id, the automatic recovery cannot know it
    assert call(srv, action="recover", inst="new-pc", call="SV1ABC") == {"ok": False, "err": "unknown"}          # an unverified callsign never gets a password by itself
    req = a.page("voip", tab="req")
    assert 'value="Secret-pass-1"' in req and 'value="2001"' in req and ("same details offered" in req or "προτείνονται τα ίδια στοιχεία" in req)     # one press on Approve gives the same details
    a.post("voip", "voip_approve", _tab="set", rid=str(r2["id"]), ext="2001", pw="Secret-pass-1")
    s = call(srv, action="status", id=r2["id"], token=r2["token"])
    assert s["status"] == "approved" and s["ext"] == "2001" and s["password"] == "Secret-pass-1"
    assert srv.sql("SELECT COUNT(*) n FROM dc_voip_req WHERE call='SV1ABC' AND status='approved'")[0]["n"] == 1   # the old computer's record is replaced, not duplicated
    assert call(srv, action="status", id=r["id"], token=r["token"]) == {"ok": False, "err": "unknown"}           # and only the new computer holds the account now


def test_release_keeps_the_account_and_restore_brings_it_back_even_when_it_is_blocked(srv):
    a = open_requests(srv); r = call(srv, **REQ); approve(srv, a, r); rid = str(r["id"]); q = lambda: call(srv, action="status", id=r["id"], token=r["token"])
    a.post("voip", "voip_block", _tab="acc", rid=rid, hours="0", reason="x")
    acc = a.page("voip", tab="acc"); assert 'value="voip_release"' in acc and 'value="voip_restore"' not in acc          # not hidden behind the block
    a.post("voip", "voip_release", _tab="acc", rid=rid)
    assert srv.sql("SELECT released, ext, pw FROM dc_voip_req")[0] == {"released": 1, "ext": "2001", "pw": "Secret-pass-1"}   # the account is still here, with its password
    assert q() == {"ok": True, "status": "approved", "released": True}                                                    # a free user is sent nothing: no password, no server, no block
    acc = a.page("voip", tab="acc"); assert 'value="voip_restore"' in acc and ("ξεκλείδωτος" in acc or "ελεύθερος" in acc or "released" in acc)
    assert "SV1ABC" in a.page("activity") and srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_rel'")[0]["n"] == 1
    a.post("voip", "voip_restore", _tab="acc", rid=rid)
    s2 = q(); assert s2["password"] == "Secret-pass-1" and s2["ext"] == "2001" and "released" not in s2 and s2["blocked"] is True   # everything is back, also the block that was set before
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='voip_res'")[0]["n"] == 1
    a.post("voip", "voip_release", _tab="acc", rid="99999"); assert srv.sql("SELECT released FROM dc_voip_req")[0]["released"] == 0   # an unknown account is ignored
