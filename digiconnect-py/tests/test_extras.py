"""Extras: a mode (or a program feature) set to "Extra" stays closed until the installation has paid for it.
Real PHP server code: panel -> signed licence answer; PayPal notification -> automatic unlock; manual unlock; nothing else changes."""
import json, re, urllib.parse, urllib.request
import pytest
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_server_payments import Admin, ipn, pay, inst

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")
CARD = dict(offer="donate", amount="3 €", link="https://www.paypal.com/donate/?hosted_button_id=ALLSTAR", msg_el="Το AllStar είναι extra.", msg_en="AllStar is an extra.")


def answer(srv, iid="inst-1", v="2.3.12"):
    q = urllib.parse.urlencode(dict(id=iid, v=v, hw="a" * 32, n="0" * 32))
    return json.loads(json.loads(urllib.request.urlopen(srv.base + "manifest.php?" + q).read())["payload"])


def pol(srv, iid="inst-1"): return answer(srv, iid)["pol"]


def paid_mode(a, mode="AllStar", **card):
    a.post("modes", "extra_cfg", mode=mode, **dict(CARD, **card))
    a.post("modes", "mode_set", mode=mode, state="paid")


def full(srv, iid="inst-1"):
    """A licensed installation (the licence was paid earlier)."""
    l = inst(srv, iid); srv.sql("UPDATE dc_installs SET state='full', demo_until=0 WHERE id=?", iid); return l


def test_an_extra_is_closed_with_its_price_and_message_until_unlocked(srv):
    inst(srv); a = Admin(srv.base)
    assert pol(srv)["paid"] == {} and "AllStar" not in pol(srv)["off"]                       # nothing is an extra by default: everything works as before
    paid_mode(a)
    p = pol(srv); assert "AllStar" in p["off"] and "DMR" not in p["off"]
    c = p["paid"]["AllStar"]
    assert c == dict(offer="donate", amount="3 €", link=CARD["link"], msg="Το AllStar είναι extra.\nAllStar is an extra.")
    assert answer(srv)["extras"] == []


def test_without_its_own_link_the_general_donation_link_is_used(srv):
    inst(srv); a = Admin(srv.base); paid_mode(a, link="")
    k = pol(srv)["paid"]["AllStar"]["link"]
    assert k == "" or k.startswith("https://")                                              # the general link (the program has its own built-in one when the server has none), never anything but https


def test_manual_unlock_for_selected_installations_only_and_taking_it_back(srv):
    inst(srv, "inst-1"); inst(srv, "inst-2"); a = Admin(srv.base); paid_mode(a)
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_give", txset="-", testerset="-")
    assert "AllStar" not in pol(srv, "inst-1")["off"] and "AllStar" not in pol(srv, "inst-1")["paid"] and answer(srv, "inst-1")["extras"] == ["AllStar"]
    assert "AllStar" in pol(srv, "inst-2")["off"] and "AllStar" in pol(srv, "inst-2")["paid"]
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_take", txset="-", testerset="-")
    assert "AllStar" in pol(srv, "inst-1")["off"] and answer(srv, "inst-1")["extras"] == []


def test_what_was_unlocked_survives_every_change_of_the_general_setting(srv):
    inst(srv); a = Admin(srv.base); paid_mode(a)
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_give", txset="-", testerset="-")
    a.post("modes", "mode_set", mode="AllStar", state="off"); assert "AllStar" in pol(srv)["off"]           # closed for everybody
    a.post("modes", "mode_set", mode="AllStar", state="on"); assert "AllStar" not in pol(srv)["off"]        # free for everybody
    a.post("modes", "mode_set", mode="AllStar", state="paid"); assert "AllStar" not in pol(srv)["off"]      # an extra again: the one who paid still has it
    assert answer(srv)["extras"] == ["AllStar"]


def test_a_payment_with_the_number_and_the_name_unlocks_the_extra_and_not_a_new_licence(srv):
    full(srv); a = Admin(srv.base); paid_mode(a)
    code_before = srv.sql("SELECT lic_code FROM dc_installs")[0]["lic_code"]
    assert ipn(srv, **pay("X1", "3.00", item_name="DigiConnect AllStar", memo="DC-00001")) == "ok"
    row = srv.sql("SELECT * FROM dc_payments")[0]
    assert row["install"] == "inst-1" and row["matched_by"].startswith("auto: ") and row["note"] == "extra: AllStar" and not row["code"]
    assert "AllStar" not in pol(srv)["off"] and answer(srv)["extras"] == ["AllStar"]
    assert srv.sql("SELECT lic_code, state FROM dc_installs")[0] == dict(lic_code=code_before, state="full")      # no second licence code
    assert not srv.sql("SELECT * FROM dc_codes")                                                              # none created
    assert "pay_extra" in [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]


def test_the_amount_alone_unlocks_when_it_belongs_to_exactly_one_extra(srv):
    full(srv); a = Admin(srv.base); paid_mode(a)
    ipn(srv, **pay("X2", "3.00", memo="DC-00001"))
    assert answer(srv)["extras"] == ["AllStar"]


def test_unclear_payments_for_a_licensed_installation_wait_for_the_owner(srv):
    full(srv); a = Admin(srv.base); paid_mode(a); paid_mode(a, "M17", amount="3 €", link="https://example.org/m17")
    ipn(srv, **pay("A1", "3.00", memo="DC-00001"))                                  # 3 € belongs to two extras
    ipn(srv, **pay("A2", "1.00", item_name="AllStar", memo="DC-00001"))              # the name is there, the amount is too small
    ipn(srv, **pay("A3", "25.00", memo="DC-00001"))                                  # an amount nobody asked for
    assert answer(srv)["extras"] == []
    assert [r["install"] for r in srv.sql("SELECT install FROM dc_payments ORDER BY id")] in ([None, None, None], ["", "", ""])
    assert srv.sql("SELECT COUNT(*) n FROM dc_codes")[0]["n"] == 0                  # and the licence was not issued again
    kinds = [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]; assert kinds.count("pay_unmatched") == 3
    # the owner assigns one of them in the panel: it unlocks the extra he chooses
    a.post("payments", "pay_assign", pid=str(srv.sql("SELECT id FROM dc_payments WHERE txn='A2'")[0]["id"]), to="DC-00001", what="x:AllStar")
    assert answer(srv)["extras"] == ["AllStar"] and srv.sql("SELECT note FROM dc_payments WHERE txn='A2'")[0]["note"] == "extra: AllStar"


def test_a_demo_user_paying_is_still_a_licence_payment(srv):
    inst(srv); a = Admin(srv.base); paid_mode(a)
    ipn(srv, **pay("L1", "3.00", memo="DC-00001 AllStar"))                           # not licensed yet: this is the licence
    assert srv.sql("SELECT state FROM dc_installs")[0]["state"] == "full" and answer(srv)["extras"] == []
    assert "AllStar" in pol(srv)["off"]


def test_without_any_extra_for_sale_payments_work_exactly_as_before(srv):
    full(srv)
    ipn(srv, **pay("N1", "10.00", custom="DC-00001"))
    assert srv.sql("SELECT code FROM dc_payments")[0]["code"].startswith("HZD-")


def test_the_extra_goes_with_the_licence_to_a_reinstall(srv):
    l = full(srv); a = Admin(srv.base); paid_mode(a)
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_give", txset="-", testerset="-")
    lic(srv, "inst-2", hw=l.hw).register(PERSON)                                     # same computer, new installation id
    assert srv.sql("SELECT state FROM dc_installs WHERE id='inst-2'")[0]["state"] == "full"
    assert answer(srv, "inst-2")["extras"] == ["AllStar"] and "AllStar" not in pol(srv, "inst-2")["off"]


def test_extra_settings_are_checked_and_the_panel_pages_render(srv):
    inst(srv); a = Admin(srv.base)
    a.post("modes", "extra_cfg", mode="AllStar", offer="buy", amount="3 €", link="http://insecure.example", msg_el="x", msg_en="y")
    assert "AllStar" not in pol(srv)["paid"]
    paid_mode(a, offer="buy", msg_el="γραμμή 1\nγραμμή 2")
    c = pol(srv)["paid"]["AllStar"]; assert c["offer"] == "buy" and "\n" not in c["msg"].split("\n")[0] and c["msg"].startswith("γραμμή 1 γραμμή 2")
    a.post("modes", "extra_cfg", mode="Bogus", offer="buy", amount="9 €")                  # an unknown name changes nothing
    a.post("modes", "mode_set", mode="Bogus", state="paid"); assert set(pol(srv)["paid"]) == {"AllStar"}
    ipn(srv, **pay("Z9", "50.00", "SEK", payer_email="nobody@example.org"))
    for p in ("modes", "payments", "activity", "installs", "dashboard"):
        html = a.page(p)
        assert "<aside>" in html and not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", html), p
    assert "Extra: AllStar" in a.page("payments") and "extra_give" in a.page("modes")
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_give", txset="-", testerset="-")
    assert "★" in a.page("modes")
    act = a.page("activity"); assert "ξεκλειδώθηκε σε" in act or "unlocked for" in act


# ---------------------------------------------------------------- the program side
from app.policy import Policy                                                       # noqa: E402
from test_ui_smoke import win  # noqa: E402,F401


def test_policy_knows_extras_their_message_and_only_https_links():
    from app import i18n
    P = lambda **k: Policy(dict(off=["AllStar", "EchoLink"], paid={"AllStar": dict(offer="donate", amount="3 €", link="https://pay.example/x", msg="Το AllStar είναι extra.\nAllStar is an extra.")}, **k))
    p = P(); assert p.paid_info("AllStar")["amount"] == "3 €" and p.paid_info("EchoLink") is None and p.paid_info("DMR") is None and not p.allows("AllStar")
    assert p.paid_link("AllStar") == "https://pay.example/x"
    assert Policy(dict(off=["AllStar"], paid={"AllStar": dict(link="http://insecure")})).paid_link("AllStar") == ""            # never a non-https address
    assert Policy(dict(off=[], paid={"AllStar": dict(amount="3 €")})).paid_info("AllStar") is None                           # open on this installation: nothing to pay
    r = p.reason("AllStar"); assert r.startswith("AllStar is an extra.") and "additional donation" in r and r.endswith("AllStar is an extra.")
    assert "buy it" in Policy(dict(off=["M17"], paid={"M17": dict(offer="buy")})).reason("M17")
    assert p.reason("EchoLink") == "This mode is not available yet."                                                       # a closed (not paid) mode keeps its old message
    assert P() == P() and P() != Policy(dict(off=["AllStar", "EchoLink"])) and len({P(), P()}) == 1
    assert Policy(dict(off=[], paid=[])).paid == {} and Policy(dict(off=[], paid="x")).paid == {} and Policy(None).paid == {}  # an empty / odd answer never breaks it
    i18n.set_language("Ελληνικά")
    try:
        g = P().reason("AllStar"); assert g.startswith("Το AllStar είναι extra. Για να ξεκλειδώσει") and g.endswith("Το AllStar είναι extra.") and "additional" not in g
    finally: i18n.set_language("English")


def test_the_program_shows_the_extra_with_its_price_opens_the_payment_and_opens_when_paid(srv, win, monkeypatch):
    w, ctx, app = win; l = lic(srv); l.register(PERSON); a = Admin(srv.base); paid_mode(a)
    w._license_changed(l.verdict(l.check()))
    ws = w.ws["AllStar"]; ws.refresh()
    assert "AllStar · extra" in w.tabs["AllStar"].text() and w.tabs["AllStar"].property("closed") is True
    assert ws.closed_note.isVisibleTo(ws) and ws.closed_btn.isVisibleTo(ws) and ws.closed_btn.text() == "♥ Donate · 3 €" and "AllStar is an extra." in ws.closed_txt.text()
    assert w.tabs["EchoLink"].text().endswith("closed") and not w.ws["EchoLink"].closed_btn.isVisibleTo(w.ws["EchoLink"])      # an ordinary closed mode: no button
    opened = []; import app.ui.license_dialog as D; monkeypatch.setattr(D, "open_donate", lambda url="": opened.append(url))
    ws.closed_btn.click(); assert opened == [CARD["link"]]
    w.nav("favorites"); ctx._closed("AllStar"); assert w.current == "net:AllStar"                                            # trying to use it takes the person to that page
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_give", txset="-", testerset="-")
    w._license_changed(l.verdict(l.check())); ws.refresh()                                                                  # the hourly check after the payment
    assert w.tabs["AllStar"].text() == "AllStar" and w.tabs["AllStar"].property("closed") is False and not ws.closed_btn.isVisibleTo(ws) and ws._sc.isEnabled()


def test_licence_window_lists_the_extras_the_person_has_and_the_ones_for_sale(srv, win):
    from app.ui.license_dialog import LicenceDialog
    w, ctx, app = win; l = lic(srv); l.register(PERSON); a = Admin(srv.base); paid_mode(a); paid_mode(a, "M17", amount="2 €", link="https://pay.example/m17")
    a.post("modes", "mode_inst", **{"ids[]": ["inst-1"], "modes[]": ["AllStar"]}, act="extra_give", txset="-", testerset="-")
    v = l.verdict(l.check())
    assert v.info["extras"] == ["AllStar"] and list(v.info["pol"]["paid"]) == ["M17"]
    import types; d = types.SimpleNamespace(lic=types.SimpleNamespace(last=v, hw="a" * 32), status=types.SimpleNamespace(setText=lambda t: setattr(d, "t", t)), donate=types.SimpleNamespace(setVisible=lambda b: None, setText=lambda t: None))
    LicenceDialog.render(d)
    assert "Extras: AllStar ✓, M17 (2 €)" in d.t, d.t
