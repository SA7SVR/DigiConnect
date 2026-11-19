"""The VoIP phone and the owner's server: the owner can close and open the phone remotely (the same Modes switches as the radio modes), and the stations list of the panel
shows who is signed in to the VoIP server (green) and who is not (red), as the programs themselves report it. Real PHP server, real program objects."""
import json, re, time, urllib.parse, urllib.request
import pytest
from app.qt import QtWidgets as W
from app.store import Store
from app.context import Ctx
from app.engine import NullEngine
from app.presence import Presence, activity
from app.policy import Policy
from app.ui.voippage import VoipPage
from app.ui.main_window import MainWindow
from app.voip import phone as P
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_server_payments import Admin
from test_modes import pol

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


def ping(srv, iid="inst-1", **q):
    q = dict(dict(id=iid, v="2.5.0", os="linux", call="SV1ABC"), **q)
    return json.loads(urllib.request.urlopen(srv.base + "ping.php?" + urllib.parse.urlencode(q)).read())


# ---- the owner closes / opens the phone ---------------------------------------------------------------------------------------------------
def test_the_panel_lists_voip_among_the_modes_and_closes_it_for_everyone_or_one_installation(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    assert "VoIP" in a.page("modes") and "VoIP" not in pol(srv)["off"]                       # open by default
    a.post("modes", "mode_set", mode="VoIP", state="off"); assert "VoIP" in pol(srv)["off"]
    a.post("modes", "mode_set", mode="VoIP", state="on"); assert "VoIP" not in pol(srv)["off"]
    a.post("modes", "mode_set", mode="VoIP", state="paid"); p = pol(srv); assert "VoIP" in p["off"] and "VoIP" in p["paid"]       # can be an extra too
    a.post("modes", "mode_set", mode="VoIP", state="on"); pol(srv, "inst-2")                       # a second installation exists
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["VoIP"]}, act="off", txset="-", testerset="-")             # only this installation
    assert "VoIP" in pol(srv)["off"] and "VoIP" not in pol(srv, "inst-2")["off"]


def test_a_closed_phone_stops_the_call_signs_out_and_says_why(tmp_path, monkeypatch):
    monkeypatch.setattr(P.Audio, "start_speakers", lambda self: True); monkeypatch.setattr(P.Audio, "stop", lambda self: None)
    st = Store(tmp_path); ctx = Ctx(st, NullEngine()); toasts = []; ctx.toast.connect(toasts.append)
    ended, signed = [], []
    class C:
        state = "active"; direction = "in"
        def hangup(self): ended.append(1)
    ctx.phone.call = C(); ctx.phone.reg_state = "registered"; ctx.phone.sign_out = lambda wait=1.5: signed.append(wait)
    assert ctx.apply_policy({"off": ["VoIP"], "note": "Κλειστό\nClosed"}) is True
    assert ended == [1] and signed == [0.0] and toasts and "Closed" in toasts[0]


def test_when_the_server_has_closed_the_phone_signing_in_is_refused_with_the_owners_message(tmp_path):
    st = Store(tmp_path); st.settings.update(voip_server="s", voip_user="1", voip_pw="x"); ctx = Ctx(st, NullEngine())
    ctx.apply_policy({"off": ["VoIP"], "note": "Closed for maintenance"})
    assert ctx.phone.sign_in() is False and ctx.phone.reg_state == "failed" and "Closed for maintenance" in ctx.phone.reg_text
    ctx.apply_policy({"off": []})                                                                    # opened again: a normal sign-in starts (no server here: it fails by itself, but it is tried)
    assert ctx.phone.blocked() == ""


def test_the_page_and_the_button_show_that_the_phone_is_closed_or_an_extra(tmp_path):
    st = Store(tmp_path); ctx = Ctx(st, NullEngine()); w = MainWindow(ctx); w.show(); w.nav("voip"); W.QApplication.processEvents()
    pg = w.voipp
    assert w.voip_btn.text() == "VoIP" and not pg.closed_note.isVisible() and pg.body.isEnabled()
    ctx.apply_policy({"off": ["VoIP"], "note": "Closed for maintenance"}); W.QApplication.processEvents()
    assert w.voip_btn.text() == "VoIP · closed" and pg.closed_note.isVisible() and "Closed for maintenance" in pg.closed_txt.text() and not pg.body.isEnabled() and not pg.closed_btn.isVisible()
    ctx.apply_policy({"off": ["VoIP"], "paid": {"VoIP": {"offer": "donate", "amount": "5 EUR", "link": "https://example.org/pay", "msg": ""}}}); W.QApplication.processEvents()
    assert w.voip_btn.text() == "VoIP · extra" and pg.closed_btn.isVisible() and "5" in pg.closed_btn.text() and "extra" in pg.closed_txt.text().lower()
    ctx.apply_policy({"off": []}); W.QApplication.processEvents()
    assert w.voip_btn.text() == "VoIP" and not pg.closed_note.isVisible() and pg.body.isEnabled()
    w.close()


def test_trying_to_use_the_closed_phone_from_the_extra_signal_opens_the_phone_page(tmp_path):
    st = Store(tmp_path); ctx = Ctx(st, NullEngine()); w = MainWindow(ctx); w.show(); W.QApplication.processEvents()
    ctx.extra_needed.emit("VoIP"); W.QApplication.processEvents()
    assert w.current == "voip"; w.close()


# ---- who is signed in to the VoIP server ---------------------------------------------------------------------------------------------------
def test_the_program_reports_whether_its_phone_is_signed_in(tmp_path):
    st = Store(tmp_path); st.settings["voip_user"] = "2001"; ctx = Ctx(st, NullEngine())
    a = activity(ctx); assert a["voip"] == 0 and "vx" not in a
    ctx.phone.reg_state = "registered"; a = activity(ctx); assert a["voip"] == 1 and a["vx"] == "2001"
    ctx.phone.reg_state = "failed"; assert activity(ctx)["voip"] == 0


def test_the_server_stores_what_the_program_reports_and_never_guesses(srv):
    lic(srv).register(PERSON)
    assert srv.sql("SELECT voip, voip_ext FROM dc_installs")[0] == {"voip": None, "voip_ext": None}      # registered, but nothing reported yet
    assert ping(srv, voip=1, vx="2001")["ok"]
    assert srv.sql("SELECT voip, voip_ext FROM dc_installs")[0] == {"voip": 1, "voip_ext": "2001"}
    ping(srv, voip=0, vx="2001"); assert srv.sql("SELECT voip, voip_ext FROM dc_installs")[0] == {"voip": 0, "voip_ext": ""}        # the extension is not kept when signed out
    ping(srv); assert srv.sql("SELECT voip FROM dc_installs")[0]["voip"] is None                              # an older program that says nothing: unknown
    ping(srv, voip=1, vx="<b>20;01</b>"); assert srv.sql("SELECT voip_ext FROM dc_installs")[0]["voip_ext"] == "b2001b"


def test_the_stations_list_shows_green_for_signed_in_and_red_for_not(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    ping(srv, "inst-1", voip=1, vx="2001"); ping(srv, "inst-2", voip=0, call="SV2XYZ"); ping(srv, "inst-3", call="SV3OLD")
    html = a.page("dashboard")
    green = re.findall(r'<div class="vp on"><i></i>☎ VoIP online · 2001</div>', html); red = re.findall(r'<div class="vp off"><i></i>☎ VoIP offline</div>', html)
    assert len(green) >= 1 and len(red) >= 1, html[html.find('class="rail"'):][:1500]
    assert html.count('class="vp ') == len(re.findall(r'class="vp (?:on|off)"', html))                          # the old program (SV3OLD) has no badge at all
    assert "1 VoIP" in html                                                                                    # the count in the header of the list
    assert not re.search(r"(Fatal error|Warning:|Notice:|Deprecated:|Uncaught)", html)


def test_a_station_that_went_offline_is_red_even_if_its_last_report_was_signed_in(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    ping(srv, "inst-1", voip=1, vx="2001"); srv.sql("UPDATE dc_installs SET last_ping=?, last_seen=?", int(time.time()) - 3600, int(time.time()) - 3600)
    html = a.page("dashboard"); assert '<div class="vp off"><i></i>☎ VoIP offline</div>' in html and 'VoIP online' not in html


def test_presence_query_carries_the_voip_state(tmp_path):
    st = Store(tmp_path); st.settings["voip_user"] = "2001"; ctx = Ctx(st, NullEngine())
    class U:
        def params(self): return dict(id="abc", v="2.5.0", os="linux", arch="x64")
    p = Presence(ctx, U(), "http://127.0.0.1:9/ping.php")
    assert p.query()["voip"] == 0
    ctx.phone.reg_state = "registered"; q = p.query(); assert q["voip"] == 1 and q["vx"] == "2001"
