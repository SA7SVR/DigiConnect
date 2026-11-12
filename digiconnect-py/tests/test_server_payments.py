"""Payments + licence model of the DigiConnect server (the HAM Digi system), run against the real PHP code:
IPN processing, automatic activation, EUR and SEK kept apart, default demo length in hours/days/months/years, per-installation actions, activation codes."""
import json, re, subprocess, time, urllib.parse, urllib.request, http.cookiejar
import pytest
from test_license import srv, lic, PERSON, _php_flags, shutil  # noqa: F401  (fixtures and helpers of the licence tests)

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


class Admin:
    """The panel as a browser uses it: sign in, read a page, press a button (with the page's CSRF token)."""
    def __init__(self, base):
        self.base = base + "admin/index.php"
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.open(self.base, urllib.parse.urlencode(dict(login="1", u="a", p="b")).encode()).read()

    def page(self, p, **q):
        return self.op.open(self.base + "?" + urllib.parse.urlencode(dict(p=p, **q))).read().decode()

    def post(self, p, a, **f):
        tok = re.search(r'name="csrf" value="([0-9a-f]+)"', self.page(p)).group(1)
        return self.op.open(self.base, urllib.parse.urlencode(dict(csrf=tok, p=p, a=a, **f), doseq=True).encode()).read().decode()


def ipn(srv, **p):
    """Hands a (PayPal-verified) IPN message to the server's processing function, like ipn.php does after PayPal says VERIFIED."""
    (srv.root / "t_ipn.php").write_text("<?php require __DIR__.'/lib.php'; $p=json_decode($argv[1],true); echo dc_ipn_process($p,'raw',dc_pay_settings());")
    r = subprocess.run(["php", *_php_flags(), str(srv.root / "t_ipn.php"), json.dumps(p)], capture_output=True, text=True, cwd=srv.root)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip()


def pay(txn, amount="10.00", cur="EUR", **extra):
    return dict(dict(txn_id=txn, payment_status="Completed", mc_gross=amount, mc_currency=cur, first_name="Nikos", last_name="P", payer_email="payer@example.org"), **extra)


def inst(srv, iid="inst-1"):
    l = lic(srv, iid); l.register(PERSON); return l


def test_donation_with_the_dc_number_activates_the_installation_and_keeps_a_code(srv):
    l = inst(srv)
    assert ipn(srv, **pay("T1", custom="DC-00001")) == "ok"
    row = srv.sql("SELECT * FROM dc_payments")[0]
    assert (row["install"], row["status"], row["amount"], row["currency"], row["matched_by"]) == ("inst-1", "Completed", 10.0, "EUR", "auto: DC custom")
    assert row["code"].startswith("HZD-")
    i = srv.sql("SELECT state, lic_by, lic_code, owner FROM dc_installs")[0]
    assert (i["state"], i["lic_code"], i["owner"]) == ("full", row["code"], "Nikos P") and i["lic_by"] == "payment T1"
    assert srv.sql("SELECT used, uses, kind FROM dc_codes WHERE code=?", row["code"])[0] == dict(used=1, uses=1, kind="full")
    assert l.verdict(l.check()).state == "full"
    assert any(e["kind"] == "pay_auto" for e in srv.sql("SELECT kind FROM dc_events"))


def test_payment_is_matched_by_registered_email_or_callsign_in_the_note(srv):
    inst(srv, "inst-1"); lic(srv, "inst-2").register(dict(PERSON, call="SM0ABC", mail="other@example.org"))
    ipn(srv, **pay("T1", payer_email="HELLAS@example.org"))                       # the registration e-mail, any case
    ipn(srv, **pay("T2", payer_email="stranger@example.org", memo="73 de sm0abc"))   # callsign in the note
    got = {r["txn"]: (r["install"], r["matched_by"]) for r in srv.sql("SELECT txn, install, matched_by FROM dc_payments")}
    assert got == {"T1": ("inst-1", "auto: email"), "T2": ("inst-2", "auto: callsign in note")}


def test_unknown_payer_waits_in_the_panel_and_can_be_assigned(srv):
    inst(srv); a = Admin(srv.base)
    ipn(srv, **pay("T9", "50.00", "SEK", payer_email="nobody@example.org"))
    assert srv.sql("SELECT install FROM dc_payments")[0]["install"] in (None, "")
    assert srv.sql("SELECT state FROM dc_installs")[0]["state"] == "demo"
    assert "pay_unmatched" in [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]
    html = a.page("payments"); assert 'value="DC-00012"' not in html and "T9" in html
    a.post("payments", "pay_assign", pid=str(srv.sql("SELECT id FROM dc_payments")[0]["id"]), to="DC-00001")
    assert srv.sql("SELECT state, lic_by FROM dc_installs")[0]["state"] == "full" and srv.sql("SELECT install FROM dc_payments")[0]["install"] == "inst-1"
    assert "no such" not in a.post("payments", "pay_assign", pid="1", to="DC-09999").lower()   # an unknown number is refused, not a crash


def test_the_same_notification_twice_pays_once_and_hamdigi_payments_are_left_alone(srv):
    inst(srv)
    ipn(srv, **pay("T1", custom="DC-00001")); ipn(srv, **pay("T1", custom="DC-00001"))
    assert len(srv.sql("SELECT * FROM dc_payments")) == 1 and len(srv.sql("SELECT * FROM dc_codes")) == 1
    assert ipn(srv, **pay("H1", custom="HD-00007")) == "hamdigi"                    # shared PayPal account: this one is HAM Digi's
    assert len(srv.sql("SELECT * FROM dc_payments")) == 1
    assert ipn(srv, **pay("B1", custom="HD-00007 DC-00001")) == "ok"                  # a message that names a DigiConnect installation stays ours


def test_minimum_amount_receiver_and_auto_off(srv):
    inst(srv)
    srv.sql("INSERT INTO dc_kv(k,v) VALUES('pay_min','20'),('pay_receiver','me@example.org')")
    assert ipn(srv, **pay("A", "10.00", custom="DC-00001", receiver_email="me@example.org")) == "ok"
    assert srv.sql("SELECT state FROM dc_installs")[0]["state"] == "demo"              # below the minimum: waits for you
    assert ipn(srv, **pay("B", "30.00", custom="DC-00001", receiver_email="someone@else.org")) == "receiver"   # not paid to you
    assert len(srv.sql("SELECT * FROM dc_payments")) == 1


def test_refund_is_recorded_but_does_not_take_the_licence_away(srv):
    inst(srv); ipn(srv, **pay("T1", custom="DC-00001"))
    ipn(srv, txn_id="R1", payment_status="Refunded", parent_txn_id="T1", mc_gross="-10.00", mc_currency="EUR")
    assert srv.sql("SELECT status FROM dc_payments")[0]["status"] == "Refunded"
    assert srv.sql("SELECT state FROM dc_installs")[0]["state"] == "full"
    assert "pay_refund" in [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]
    assert ipn(srv, txn_id="R2", payment_status="Refunded", parent_txn_id="HAMDIGI-TXN", mc_gross="-5", mc_currency="EUR") == "other"


def test_euro_and_krona_totals_are_never_added_together(srv):
    inst(srv); a = Admin(srv.base)
    ipn(srv, **pay("E1", "10.00", "EUR", custom="DC-00001")); ipn(srv, **pay("E2", "5.50", "EUR", payer_email="x@example.org"))
    ipn(srv, **pay("S1", "100.00", "SEK", payer_email="y@example.org")); ipn(srv, **pay("S2", "50.00", "SEK", payer_email="z@example.org"))
    a.post("payments", "pay_ignore", pid=str(srv.sql("SELECT id FROM dc_payments WHERE txn='S2'")[0]["id"]))     # set aside: not counted
    a.post("payments", "pay_add", amount="25", currency="sek", name="Swish man", email="", memo="Swish", to="")
    html = a.page("payments")
    assert "15.50 €" in html and "125.00 kr" in html                                   # EUR 10 + 5.50 ; SEK 100 + 25 (S2 ignored)
    assert "140.50" not in html and "115.50" not in html and "175.00" not in html         # no mixed sums
    assert "Ποιος πληρώνει" in html and "Swish man" in html
    assert "10.00 EUR" in a.page("installs")                                           # the installation shows what it has paid
    dash = a.page("dashboard"); assert "15.50 €" in dash and "125.00 kr" in dash


def test_default_demo_length_in_hours_days_months_years(srv):
    a = Admin(srv.base)
    for n, unit, secs, text in ((3, "h", 3 * 3600, "3 hours left"), (10, "d", 10 * 86400, "10 days left"), (1, "m", 28 * 86400, "days left"), (1, "y", 364 * 86400, "days left")):
        a.post("licenses", "lic_default", mode="demo", n=str(n), unit=unit, msg_el="", msg_en="", offer="donate", amount="", link="")
        l = lic(srv, f"i-{unit}"); l.register(PERSON | dict(mail=f"{unit}@example.org"))
        row = srv.sql("SELECT demo_until, lic_by FROM dc_installs WHERE id=?", f"i-{unit}")[0]
        assert row["lic_by"] == "default" and row["demo_until"] - time.time() >= secs - 60
        assert text in l.verdict(l.check()).left


def test_default_free_and_locked_with_lock_message(srv):
    a = Admin(srv.base)
    a.post("licenses", "lic_default", mode="free", n="14", unit="d", msg_el="", msg_en="", offer="none", amount="", link="")
    f = lic(srv, "free-1"); v = f.verdict(f.register(PERSON)); assert v.kind == "ok" and v.state == "full" and v.left == ""
    a.post("licenses", "lic_default", mode="locked", n="14", unit="d", msg_el="Ευχαριστώ!", msg_en="Thanks!", offer="donate", amount="5 €", link="https://example.org/pay")
    k = lic(srv, "lock-1"); m = k.register(PERSON | dict(mail="k@example.org"), lang="en"); v = k.verdict(m)
    assert v.kind == "blocked" and "Thanks!" in v.msg and "activation" in v.msg
    assert (m["donate"], m["offer"], m["amount"]) == ("https://example.org/pay", "donate", "5 €")      # the button settings reach the program


def test_per_installation_actions_and_reset_to_default(srv):
    l = inst(srv); a = Admin(srv.base)
    row = lambda: srv.sql("SELECT state, demo_until, lic_by FROM dc_installs")[0]
    a.post("installs", "lic_one", id="inst-1", do="demo", n="2", unit="h"); r = row(); assert r["state"] == "demo" and 3500 < r["demo_until"] - time.time() <= 7200 + 5 and r["lic_by"] == "panel"
    assert "hours left" in l.verdict(l.check()).left
    a.post("installs", "lic_one", id="inst-1", do="extend", n="3", unit="d"); assert row()["demo_until"] - time.time() > 3 * 86400
    a.post("installs", "lic_one", id="inst-1", do="full_until", n="1", unit="m"); r = row(); assert r["state"] == "full" and r["demo_until"] > time.time() + 27 * 86400
    assert l.verdict(l.check()).state == "full"
    srv.sql("UPDATE dc_installs SET demo_until=?", int(time.time()) - 5)                  # a time-limited licence that ran out
    v = l.verdict(l.check()); assert v.kind == "blocked" and "licence has ended" in v.msg
    a.post("installs", "lic_one", id="inst-1", do="full", n="1", unit="d"); assert row()["demo_until"] == 0 and l.verdict(l.check()).state == "full"
    a.post("installs", "lic_one", id="inst-1", do="lock", n="1", unit="d"); assert l.verdict(l.check()).kind == "blocked"
    a.post("installs", "lic_one", id="inst-1", do="free", n="1", unit="d"); assert l.verdict(l.check()).state == "full"
    a.post("installs", "lic_one", id="inst-1", do="default", n="1", unit="d"); assert l.verdict(l.check()).state == "demo" and row()["lic_by"] == "default"
    a.post("installs", "lic_one", id="inst-1", do="full", n="1", unit="d")
    a.post("licenses", "lic_default", mode="locked", n="1", unit="d", msg_el="", msg_en="", offer="donate", amount="", link="")
    a.post("licenses", "lic_reset_all")                                                    # a licence set by hand is not reset
    assert row()["state"] == "full"


def test_activation_codes_like_hamdigi(srv):
    l = inst(srv); a = Admin(srv.base)
    new = lambda **f: re.findall(r"HZD-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}", a.post("licenses", "code_new", **dict(dict(kind="demo", n="6", unit="d", uses="1", valid_days="0", count="1", note=""), **f)))[0]
    redeem = lambda c, iid="inst-1": json.loads(urllib.request.urlopen(srv.base + "api.php", urllib.parse.urlencode(dict(action="redeem", id=iid, code=c)).encode()).read())
    c = new(kind="demo", n="2", unit="h"); r = redeem(c); assert r["ok"] and r["state"] == "demo" and r["left"] == "2 hours left"     # counted from the moment it is entered
    assert redeem(c)["ok"] and srv.sql("SELECT used FROM dc_codes WHERE code=?", c)[0]["used"] == 1      # the same installation again: not used up twice
    assert redeem(c, "inst-other") == {"ok": False, "err": "used"}                          # another computer: refused ...
    assert "code_reuse" in [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]       # ... and you are told
    c = new(kind="full", perm="1", n="1"); r = redeem(c); assert r["state"] == "full" and srv.sql("SELECT demo_until, lic_code FROM dc_installs")[0] == dict(demo_until=0, lic_code=c)
    c = new(kind="full", n="1", unit="y", uses="0"); assert redeem(c)["state"] == "full" and redeem(c)["ok"]              # 0 = unlimited computers
    assert srv.sql("SELECT demo_until FROM dc_installs")[0]["demo_until"] > time.time() + 360 * 86400
    c = new(kind="demo", n="1", unit="d", valid_days="1"); srv.sql("UPDATE dc_codes SET valid_until=? WHERE code=?", int(time.time()) - 5, c)
    assert redeem(c)["err"] == "expired" and redeem("NOPE-0000")["err"] == "bad_code"      # the code itself has expired / does not exist
    c = new(kind="demo"); redeem(c); a.post("licenses", "code_more", code=c)                 # "+1": one more computer may use a used-up code
    assert srv.sql("SELECT uses FROM dc_codes WHERE code=?", c)[0]["uses"] == 2 and redeem(c)["ok"]
    assert len(re.findall("HZD-", a.post("licenses", "code_new", kind="demo", n="1", unit="d", uses="1", valid_days="0", count="3", note="x"))) >= 3
    a.post("licenses", "code_del", code=c); assert not srv.sql("SELECT * FROM dc_codes WHERE code=?", c)


def test_old_codes_with_long_unit_names_still_work(srv):
    inst(srv)
    srv.sql("INSERT INTO dc_codes(code,kind,dur,unit,uses,used,created) VALUES('OLD-CODE-0001','demo',3,'days',1,0,?)", int(time.time()))
    r = json.loads(urllib.request.urlopen(srv.base + "api.php", urllib.parse.urlencode(dict(action="redeem", id="inst-1", code="old-code-0001")).encode()).read())
    assert r["ok"] and r["state"] == "demo"


def test_panel_pages_open_without_errors(srv):
    inst(srv); a = Admin(srv.base); ipn(srv, **pay("T1", custom="DC-00001"))
    for p in ("dashboard", "installs", "licenses", "payments", "activity", "settings", "stats"):
        html = a.page(p); assert "Fatal error" not in html and "Warning:" not in html and "Notice:" not in html and "<footer>" in html, p
    assert "pay_auto" not in a.page("activity") and "Αυτόματη ενεργοποίηση" in a.page("activity")


def test_messages_like_hamdigi_are_offered_to_everyone_or_one_installation(srv):
    l = inst(srv); lic(srv, "inst-2").register(PERSON | dict(mail="b@example.org")); a = Admin(srv.base)
    a.post("messages", "msg_new", target="", days="30", title_el="Γεια", title_en="Hello", body_el="Νέα έκδοση", body_en="New version", link="https://example.org/x")
    a.post("messages", "msg_new", target="DC-00002", days="0", title_el="", title_en="", body_el="Μόνο για σένα", body_en="", link="javascript:alert(1)")
    a.post("messages", "msg_new", target="DC-09999", days="1", title_el="", title_en="", body_el="x", body_en="", link="")      # unknown installation: refused
    ask = lambda iid: json.loads(urllib.request.urlopen(srv.base + "manifest.php?" + urllib.parse.urlencode(dict(id=iid, v="2.2.0"))).read())["msgs"]
    m1 = ask("inst-1"); assert [m["en"] for m in m1] == ["New version"] and m1[0]["link"] == "https://example.org/x" and m1[0]["title_el"] == "Γεια"
    m2 = ask("inst-2"); assert sorted(m["el"] for m in m2) == ["Μόνο για σένα", "Νέα έκδοση"] and [m["link"] for m in m2 if m["el"] == "Μόνο για σένα"] == [""]
    a.post("messages", "msg_off", mid=str(srv.sql("SELECT id FROM dc_messages WHERE body_en='New version'")[0]["id"])); assert [m["el"] for m in ask("inst-1")] == []
    a.post("messages", "msg_del", mid=str(srv.sql("SELECT id FROM dc_messages WHERE body_en=''")[0]["id"])); assert ask("inst-2") == []
    assert len(srv.sql("SELECT * FROM dc_messages")) == 1


def test_public_site_describes_the_licence_system_in_every_language(srv):
    for lang, word in (("el", "Δοκιμαστική περίοδος"), ("en", "Demo, licence and Donate"), ("sv", "Demoperiod"), ("it", "Periodo di prova")):
        html = urllib.request.urlopen(srv.base + f"index.php?lang={lang}").read().decode()
        assert word in html and 'id="licence"' in html and "NXDN" in html and "AllStarLink" in html and "privacy.php" in html and "Fatal error" not in html, lang
