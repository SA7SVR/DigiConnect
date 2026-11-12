"""The licence windows of the program (activation code, messages, 'Licence' button) against the real PHP server."""
import threading, time
import pytest
from app.qt import QtWidgets, QtCore
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_ui_smoke import win  # noqa: F401
from app import license as L
from app.ui import license_dialog as LD

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


def pump(app, cond, secs=8):
    t = time.time()
    while time.time() - t < secs:
        app.processEvents()
        if cond(): return True
        time.sleep(0.02)
    return False


def code(srv, c, **kw):
    cols = dict(code=c, kind="full", dur=0, unit="d", uses=1, used=0, created=1, valid_until=0); cols.update(kw)
    srv.sql(f"INSERT INTO dc_codes({','.join(cols)}) VALUES({','.join('?'*len(cols))})", *cols.values())


def test_activation_dialog_good_bad_and_used_codes(srv, win):
    w, ctx, app = win; l = lic(srv); l.register(PERSON)
    code(srv, "GOOD-1"); code(srv, "OLD-1", valid_until=5)
    d = LD.ActivationDialog(l)
    d.code.setText("NOPE"); d.ok.click(); assert pump(app, lambda: "not valid" in d.err.text() or "δεν είναι" in d.err.text())
    d.code.setText("OLD-1"); d.ok.click(); assert pump(app, lambda: "expired" in d.err.text() or "λήξει" in d.err.text())
    d.code.setText("GOOD-1"); d.ok.click(); assert pump(app, lambda: d.answer is not None)
    assert d.answer["state"] == "full" and l.verdict(d.answer).state == "full"
    row = srv.sql("SELECT state, lic_code FROM dc_installs WHERE id='inst-1'")[0]; assert (row["state"], row["lic_code"]) == ("full", "GOOD-1")
    other = lic(srv, "inst-2"); other.register(dict(PERSON, mail="x@example.org"))
    d2 = LD.ActivationDialog(other); d2.code.setText("GOOD-1"); d2.ok.click()
    assert pump(app, lambda: "already been used" in d2.err.text() or "ήδη χρησιμοποιηθεί" in d2.err.text()) and d2.answer is None     # one-computer code


def test_message_to_owner_reaches_the_inbox_and_the_reply_comes_back(srv, win):
    w, ctx, app = win; l = lic(srv); l.register(PERSON)
    d = LD.MessageDialog(l); d.subject.setText("Hello"); d.body.setPlainText("Please help"); d.send.click()
    assert pump(app, lambda: "Sent" in d.msg.text() or "Στάλθηκε" in d.msg.text())
    row = srv.sql("SELECT install, call, subject, body, src FROM dc_inbox")[0]
    assert (row["install"], row["subject"], row["body"], row["src"]) == ("inst-1", "Hello", "Please help", "app") and row["call"] == "SA7SVR"
    srv.sql("UPDATE dc_inbox SET reply='We are on it', reply_t=?, status='answered'", int(time.time()))
    assert l.replies()[0]["reply"] == "We are on it"
    d2 = LD.MessageDialog(l); d2.send.click(); assert "first" in d2.msg.text() or "πρώτα" in d2.msg.text()                 # empty message is not sent


def test_unread_badge_and_licence_dialog_list(srv, win):
    w, ctx, app = win; l = lic(srv); l.register(PERSON)
    srv.sql("INSERT INTO dc_messages(t,scope,target,title,body,active,title_en,title_el,body_en,body_el) VALUES(?,?,?,?,?,1,?,?,?,?)",
            int(time.time()), "all", "", "T", "B", "Welcome", "Καλώς ήρθες", "Hello there", "Γεια σου")
    wt = LD.Watcher(l); w.bind_license(wt); l.check()
    wt.reply_ids = []; l.reply_ids = []
    assert wt.unread() == 1
    wt._arrived(l.verdict(l.check()))
    assert pump(app, lambda: "1" in w.lic_btn.text())
    dlg = LD.LicenceDialog(wt)
    assert pump(app, lambda: dlg.list.count() >= 1 and dlg.list.item(0) is not None and ("Hello there" in dlg.list.item(0).text() or "Γεια σου" in dlg.list.item(0).text()))
    assert "DC-" in dlg.status.text() and l.hw[:8] in dlg.status.text()
    assert wt.unread() == 0 and "1" not in w.lic_btn.text().replace("Licence", "")


def test_block_dialog_has_code_and_contact_buttons_and_other_pc_message(srv, win):
    w, ctx, app = win; l = lic(srv); l.register(PERSON)
    srv.sql("UPDATE dc_installs SET state='full', demo_until=0, lic_by='admin' WHERE id='inst-1'")
    l.check()
    clone = L.License(l.store.__class__(), l.params, base=srv.base, hw="c" * 32, pubkeys=[srv.pub]); clone.store.settings = {}
    v = clone.verdict(clone.check())
    assert v.kind == "blocked" and "another computer" in v.msg and v.info.get("other_pc") == 1
    d = LD.BlockDialog(v, clone.evaluate)
    assert not d.code.isHidden() and not d.contact.isHidden() and d.code.text() and d.contact.text()
    off = LD.BlockDialog(L.Verdict("offline", msg="no server"), clone.evaluate)
    assert off.code.isHidden() and off.contact.isHidden()                      # without a connection neither can work


def test_bottom_licence_card_shows_number_licence_callsign_and_computer(srv, win):
    w, ctx, app = win; l = lic(srv); l.register(PERSON)
    w._license_changed(l.verdict(l.check()))
    assert w.chip_no.text().startswith("DC-") and "Demo" in w.chip_lic.text() and w.chip_lic.property("tone") == "amber"
    assert w.chip_call.text() == "SA7SVR" and len(w.chip_pc.text()) == 8
    srv.sql("UPDATE dc_installs SET state='full', demo_until=0, lic_by='admin' WHERE id='inst-1'")
    w._license_changed(l.verdict(l.check()))
    assert "Licensed" in w.chip_lic.text() and w.chip_lic.property("tone") == "green"
