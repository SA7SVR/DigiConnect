"""Asking for a VoIP account, end to end: the program's page talks over real HTTP to the real PHP server (voip_request.php + the panel where the administrator approves)."""
import time
import pytest
from app.qt import QtWidgets as W
from app.store import Store
from app.context import Ctx
from app.engine import NullEngine
from app.ui.voippage import VoipPage
from app.voip import signup
from test_license import srv, shutil  # noqa: F401
from test_server_payments import Admin

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")

PERSON = dict(name="Nikos P", call="SV1ABC", want="2001", msg="Hello", lang="el")


@pytest.fixture()
def base(srv, monkeypatch):
    monkeypatch.setattr(signup, "BASE", srv.base)
    return srv


def owner(srv, opened=True, **kw):
    a = Admin(srv.base); a.post("voip", "voip_set", _tab="set", voip_on="1" if opened else "", voip_server=kw.get("server", "pbx.example.org"), voip_port="5061", voip_transport="tls", voip_domain=kw.get("domain", "")); return a


def wait(cond, page=None, secs=10):
    end = time.time() + secs
    while time.time() < end:
        W.QApplication.processEvents()
        if cond(): return True
        time.sleep(0.02)
    return cond()


def make(tmp_path):
    st = Store(tmp_path); st.settings.update(callsign="SV1ABC", op_name="Nikos P", install_id="inst-test-1"); ctx = Ctx(st, NullEngine()); pg = VoipPage(ctx); pg.show(); W.QApplication.processEvents(); return st, pg


def test_the_functions_follow_the_servers_answers(base):
    assert signup.is_open() is False
    with pytest.raises(signup.SignupError) as e: signup.submit(**PERSON)
    assert e.value.code == "closed"
    owner(base)
    assert signup.is_open() is True
    rid, tok = signup.submit(**PERSON)
    assert rid > 0 and len(tok) == 32
    assert signup.status(rid, tok)["status"] == "new"
    with pytest.raises(signup.SignupError) as e: signup.status(rid, "x" * 32)
    assert e.value.code == "unknown"
    with pytest.raises(signup.SignupError) as e: signup.submit(**PERSON)
    assert e.value.code == "pending" and "already waiting" in e.value.text


def test_an_unreachable_server_is_reported_as_a_network_problem_not_as_a_server_answer(monkeypatch):
    monkeypatch.setattr(signup, "BASE", "http://127.0.0.1:9/")
    with pytest.raises(signup.SignupError) as e: signup.status(1, "x")
    assert e.value.code == "" and e.value.text


def test_the_page_hides_the_check_button_until_a_request_is_waiting(tmp_path):
    st, pg = make(tmp_path)
    assert pg.req_btn.isVisible() and not pg.req_chk.isVisible()
    st.settings.update(voip_req_state="pending", voip_req_id=5, voip_req_token="t"); pg._req_refresh()
    assert not pg.req_btn.isVisible() and pg.req_chk.isVisible() and "waiting" in pg.req_lbl.text()


def submit_and_wait(pg, st):
    pg.acc.submit(**PERSON); assert wait(lambda: st.settings.get("voip_req_state") == "pending")
    return int(st.settings["voip_req_id"])


def check(pg, st, cond, silent=False):
    pg.acc.check(silent); assert wait(cond), pg.req_lbl.text()


def test_a_request_is_approved_and_the_account_fills_in_and_stays_linked_with_the_server(base, tmp_path):
    st, pg = make(tmp_path); a = owner(base, domain="pbx.example.org")
    rid = submit_and_wait(pg, st); assert len(st.settings["voip_req_token"]) == 32 and base.sql("SELECT inst FROM dc_voip_req")[0]["inst"] == "inst-test-1"
    pg._req_check(False); assert wait(lambda: "still waiting" in pg.req_lbl.text()), pg.req_lbl.text()
    a.post("voip", "voip_approve", _tab="set", rid=str(rid), ext="2001", pw="Secret-pass-1")
    pg._req_check(False)
    assert wait(lambda: st.settings.get("voip_req_state") == "linked"), st.settings.get("voip_req_state")
    assert pg.user.text() == "2001" and pg.pw.text() == "Secret-pass-1" and pg.server.text() == "pbx.example.org" and pg.port.text() == "5061" and pg.transport.currentText() == "TLS" and pg.domain.text() == "pbx.example.org"
    assert st.settings["voip_user"] == "2001" and st.settings["voip_pw"] == "Secret-pass-1" and st.settings["voip_transport"] == "tls"
    assert st.settings["voip_req_token"] and base.sql("SELECT pw FROM dc_voip_req")[0]["pw"] == "Secret-pass-1"      # the link stays, and the password stays on the server
    assert st.settings["voip_auto"] is True and st.settings["voip_remember"] is True                                  # it signs in by itself when the program starts
    assert "2001" in pg.req_lbl.text() and not pg.req_btn.isVisible() and pg.req_chk.isVisible()
    assert pg.user.isReadOnly() and pg.pw.isReadOnly() and not pg.transport.isEnabled()                              # the server decides these
    for w in (pg.server, pg.port, pg.user, pg.auth_user, pg.domain, pg.pw, pg.transport): assert w.property("locked") is True and w.toolTip() == "Set by the administrator"      # shown grey
    assert not pg.name.isReadOnly() and pg.name.property("locked") in (None, False) and pg.remember.isEnabled() and pg.auto.isEnabled()                                    # what the user may still change stays normal


def linked(base, tmp_path, ext="2001", pw="Secret-pass-1"):
    st, pg = make(tmp_path); a = owner(base, domain="pbx.example.org"); rid = submit_and_wait(pg, st)
    a.post("voip", "voip_approve", _tab="set", rid=str(rid), ext=ext, pw=pw); pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "linked")
    return st, pg, a, rid


def test_a_new_password_from_the_owner_arrives_by_itself_and_a_signed_in_phone_signs_in_again(base, tmp_path, monkeypatch):
    st, pg, a, rid = linked(base, tmp_path); ph = pg.ph; calls = []
    ph.reg_state = "registered"; monkeypatch.setattr(ph, "sign_out", lambda *x, **k: calls.append("out")); monkeypatch.setattr(ph, "sign_in", lambda *x, **k: calls.append("in") or True)
    a.post("voip", "voip_pw", _tab="acc", rid=str(rid), ext="2001", pw="Lost-and-new-3")
    check(pg, st, lambda: st.settings["voip_pw"] == "Lost-and-new-3")
    assert pg.pw.text() == "Lost-and-new-3" and calls == ["out", "in"] and "updated" in pg.req_lbl.text()              # nobody typed anything
    a.post("voip", "voip_pw", _tab="acc", rid=str(rid), ext="2009", pw="Lost-and-new-3"); check(pg, st, lambda: st.settings["voip_user"] == "2009"); assert pg.user.text() == "2009"


def test_sign_in_first_asks_the_server_for_the_newest_details_and_still_works_when_the_server_cannot_be_reached(base, tmp_path, monkeypatch):
    st, pg, a, rid = linked(base, tmp_path); got = []
    a.post("voip", "voip_pw", _tab="acc", rid=str(rid), ext="2001", pw="Changed-pass-4")
    pg.acc.ensure_fresh(lambda: got.append(st.settings["voip_pw"])); assert wait(lambda: got) and got == ["Changed-pass-4"]      # the newest password was taken BEFORE signing in
    monkeypatch.setattr(signup, "BASE", "http://127.0.0.1:9/"); got.clear()
    pg.acc.ensure_fresh(lambda: got.append(st.settings["voip_pw"])); assert wait(lambda: got) and got == ["Changed-pass-4"]  # no server: the saved ones are used, sign-in is not stopped


def test_the_sign_in_button_takes_the_new_password_from_the_server_first(base, tmp_path, monkeypatch):
    st, pg, a, rid = linked(base, tmp_path); used = []
    monkeypatch.setattr(pg.ph, "sign_in", lambda password=None: used.append((password, dict(st.settings)["voip_pw"])) or True)
    a.post("voip", "voip_pw", _tab="acc", rid=str(rid), ext="2001", pw="Fresh-pass-5")
    pg.sign.click(); assert wait(lambda: used) and used == [("Fresh-pass-5", "Fresh-pass-5")]


def test_one_blocked_account_cannot_sign_in_and_is_signed_out_with_the_owners_reason_until_it_is_lifted(base, tmp_path, monkeypatch):
    st, pg, a, rid = linked(base, tmp_path); ph = pg.ph; calls = []; pg.ctx.toast.connect(lambda m: calls.append(m))
    orig_out = ph.sign_out; ph.reg_state = "registered"; monkeypatch.setattr(ph, "sign_out", lambda *x, **k: calls.append("out"))
    a.post("voip", "voip_block", _tab="acc", rid=str(rid), hours="0", reason="Misuse of the net")
    check(pg, st, lambda: st.settings.get("voip_block") is True)
    assert "out" in calls and any("Misuse of the net" in str(c) for c in calls)                                       # signed out at once, and the user is told why
    assert "Misuse of the net" in ph.blocked() and "Misuse of the net" in pg.req_lbl.text()
    ph.reg_state = "unregistered"; monkeypatch.setattr(ph, "sign_out", orig_out); assert ph.sign_in("x") is False and "Misuse of the net" in ph.reg_text and ph.ua is None      # and cannot sign in
    a.post("voip", "voip_unblock", _tab="acc", rid=str(rid)); check(pg, st, lambda: st.settings.get("voip_block") is False)
    assert ph.blocked() == "" and "lifted" in pg.req_lbl.text()


def test_a_block_for_a_time_lifts_itself_and_the_global_switch_is_a_separate_thing(base, tmp_path):
    st, pg, a, rid = linked(base, tmp_path)
    a.post("voip", "voip_block", _tab="acc", rid=str(rid), hours="1", reason="Pause"); check(pg, st, lambda: st.settings.get("voip_block") is True)
    until = st.settings["voip_block_until"]; assert abs(until - (time.time() + 3600)) < 120 and pg.acc.blocked()[0]
    st.settings["voip_block_until"] = int(time.time()) - 1; assert not pg.acc.blocked()[0] and pg.ph.blocked() == ""     # the time has passed: no server answer is needed
    assert pg.ctx.policy.allows("VoIP")                                                                                  # the administrator's other switches were not touched


def test_blocked_text_is_in_greek(base, tmp_path):
    from app import i18n
    st, pg = make(tmp_path); st.settings.update(voip_block=True, voip_block_until=0, voip_block_reason="Λόγος")
    i18n.set_language("el")
    try: assert "αποκλειστεί" in pg.acc.block_text() and "Λόγος" in pg.acc.block_text()
    finally: i18n.set_language("en")


def test_a_program_that_lost_its_settings_gets_its_account_back_by_itself(base, tmp_path, monkeypatch):
    from app.voip import account
    st, pg, a, rid = linked(base, tmp_path)
    (tmp_path / "new").mkdir(); (tmp_path / "x").mkdir(); st2 = Store(tmp_path / "new"); st2.settings.update(callsign="SV1ABC", install_id="inst-test-1"); ctx2 = Ctx(st2, NullEngine())
    monkeypatch.setattr(account, "AUTO", True); done = []
    ctx2.voip_account.ensure_fresh(lambda: done.append(1)); assert wait(lambda: done)
    assert st2.settings["voip_req_state"] == "linked" and st2.settings["voip_user"] == "2001" and st2.settings["voip_pw"] == "Secret-pass-1"
    st3 = Store(tmp_path / "x"); st3.settings.update(callsign="SV1ABC", install_id="somebody-else"); ctx3 = Ctx(st3, NullEngine()); done.clear()
    ctx3.voip_account.ensure_fresh(lambda: done.append(1)); assert wait(lambda: done) and st3.settings.get("voip_req_state", "") == "" and not st3.settings.get("voip_user")   # another installation gets nothing


def test_a_released_account_unlocks_for_a_while_and_the_owner_can_bring_the_user_back_with_one_press(base, tmp_path, monkeypatch):
    st, pg, a, rid = linked(base, tmp_path); ph = pg.ph
    assert pg.user.isReadOnly()
    a.post("voip", "voip_release", _tab="acc", rid=str(rid)); check(pg, st, lambda: st.settings.get("voip_released") is True)
    assert st.settings["voip_req_state"] == "linked" and st.settings["voip_req_token"]                                   # the link stays: the account is still his, only unlocked
    assert "another server for now" in pg.req_lbl.text() and st.settings["voip_user"] == "2001" and st.settings["voip_pw"] == "Secret-pass-1"   # what he had stays, so he is not left empty
    assert pg.req_chk.isVisible() and not pg.req_btn.isVisible() and all(not w.isReadOnly() and w.property("locked") is False for w in (pg.server, pg.port, pg.user, pg.auth_user, pg.domain, pg.pw)) and pg.transport.isEnabled()
    pg.server.setText("sip.somewhere-else.org"); pg.user.setText("7777"); pg.server.editingFinished.emit(); pg.user.editingFinished.emit()
    pg.acc.check(True); done = []; pg.acc.ensure_fresh(lambda: done.append(1)); assert wait(lambda: done)
    assert st.settings["voip_server"] == "sip.somewhere-else.org" and st.settings["voip_user"] == "7777"                  # nothing puts the administrator's details back while he is free
    assert not pg.acc.blocked()[0]
    # the administrator brings him back
    calls = []; ph.reg_state = "registered"; monkeypatch.setattr(ph, "sign_out", lambda *x, **k: calls.append("out")); monkeypatch.setattr(ph, "sign_in", lambda *x, **k: calls.append("in") or True)
    a.post("voip", "voip_restore", _tab="acc", rid=str(rid)); check(pg, st, lambda: st.settings.get("voip_released") is False)
    assert st.settings["voip_server"] == "pbx.example.org" and st.settings["voip_user"] == "2001" and st.settings["voip_pw"] == "Secret-pass-1"   # the administrator's details are back
    assert "put the account back" in pg.req_lbl.text() and pg.user.isReadOnly() and pg.user.property("locked") is True and not pg.transport.isEnabled()      # and locked again
    assert calls == ["out", "in"]                                                                                         # a phone that was signed in elsewhere signs in to the administrator's server
    assert base.sql("SELECT COUNT(*) n FROM dc_events WHERE kind IN ('voip_rel','voip_res')")[0]["n"] == 2
    from app import i18n
    i18n.set_language("el")
    try: assert "προσωρινά" in i18n.tr("The administrator has let you use another server for now: the fields are unlocked and the details saved here stay as they are.") and "επανέφερε" in i18n.tr("The administrator has put the account back: your details were replaced by the server's and locked.")
    finally: i18n.set_language("en")


def test_an_account_the_owner_deleted_unlocks_the_fields_and_the_saved_details_stay(base, tmp_path):
    st, pg, a, rid = linked(base, tmp_path)
    a.post("voip", "voip_del", _tab="acc", rid=str(rid)); check(pg, st, lambda: st.settings.get("voip_req_state") == "")
    assert "removed" in pg.req_lbl.text() and st.settings["voip_user"] == "2001" and pg.req_btn.isVisible() and not pg.user.isReadOnly() and st.settings["voip_released"] is False


def test_a_linked_program_has_no_way_to_point_the_account_somewhere_else(base, tmp_path):
    st, pg, a, rid = linked(base, tmp_path)
    assert not hasattr(pg, "unlink_btn") and not [b for b in pg.findChildren(W.QPushButton) if b.text() == "Use another account"]     # no button that unlocks the fields
    for w in (pg.server, pg.port, pg.user, pg.auth_user, pg.domain, pg.pw): w.setText("evil.example.org"); w.editingFinished.emit()   # even a forced edit does not stick:
    pg.acc.check(True); assert wait(lambda: st.settings["voip_server"] == "pbx.example.org"), st.settings["voip_server"]               # the next check puts the administrator's details back
    assert st.settings["voip_user"] == "2001" and st.settings["voip_pw"] == "Secret-pass-1" and pg.server.text() == "pbx.example.org"


def test_a_rejection_shows_the_reason_and_allows_a_new_request(base, tmp_path):
    st, pg = make(tmp_path); a = owner(base)
    submit_and_wait(pg, st)
    a.post("voip", "voip_reject", _tab="set", rid=str(base.sql("SELECT id FROM dc_voip_req")[0]["id"]), reason="No licence found")
    pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "rejected")
    assert "No licence found" in pg.req_lbl.text() and st.settings["voip_req_token"] == "" and pg.req_btn.isVisible() and pg.req_btn.text() == "Request an account again"
    assert pg.user.text() == ""                                                                    # nothing was filled in


def test_a_request_the_server_no_longer_knows_is_dropped(base, tmp_path):
    st, pg = make(tmp_path); owner(base)
    st.settings.update(voip_req_state="pending", voip_req_id=99, voip_req_token="a" * 32); pg._req_refresh()
    pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "")
    assert pg.req_btn.isVisible() and "no longer has this request" in pg.req_lbl.text()


def test_a_network_error_keeps_the_request_so_it_can_be_checked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(signup, "BASE", "http://127.0.0.1:9/")
    st, pg = make(tmp_path); st.settings.update(voip_req_state="pending", voip_req_id=5, voip_req_token="t" * 32); pg._req_refresh()
    pg._req_check(False); assert wait(lambda: "cannot be reached" in pg.req_lbl.text())
    assert st.settings["voip_req_state"] == "pending" and st.settings["voip_req_token"] == "t" * 32 and pg.req_chk.isVisible()


def test_the_request_dialog_checks_the_form_before_anything_is_sent(tmp_path, monkeypatch):
    st, pg = make(tmp_path); sent = []
    monkeypatch.setattr(signup, "submit", lambda **f: sent.append(f) or (1, "t" * 32))
    from app.qt import QtCore
    def drive():
        f = pg._req_form; d = f["dialog"]; send = [b for b in d.findChildren(W.QPushButton) if b.text() == "Send the request"][0]
        assert f["name"].text() == "Nikos P" and f["call"].text() == "SV1ABC" and "email" not in f      # prefilled from the program
        send.click(); assert sent == [] and "agree" in f["err"].text()                               # no consent: nothing leaves the computer
        f["consent"].setChecked(True); f["name"].setText(""); send.click(); assert sent == [] and "name" in f["err"].text()
        f["name"].setText("Nikos P"); send.click()
        assert wait(lambda: len(sent) == 1) and sent[0]["call"] == "SV1ABC" and sent[0]["name"] == "Nikos P"
        assert wait(lambda: st.settings.get("voip_req_state") == "pending"); W.QApplication.processEvents()
    QtCore.QTimer.singleShot(300, drive); pg._req_dialog()
    assert st.settings["voip_req_id"] == 1 and st.settings["voip_req_token"] == "t" * 32


def test_the_button_under_sign_in_opens_the_request_window(tmp_path):
    from app.qt import QtCore
    st, pg = make(tmp_path); opened = []
    pg.sections[0].click(); W.QApplication.processEvents()
    assert pg.req_btn.isVisible() and pg.req_btn.text() == "I don't have an account: request one" and pg.req_btn.y() > pg.sign.y()      # on the Account tab, just under Sign in
    def look():
        f = pg._req_form; opened.append((f["dialog"].isVisible(), f["dialog"].windowTitle(), f["want"].placeholderText())); f["dialog"].reject()
    QtCore.QTimer.singleShot(300, look); pg.req_btn.click()
    assert opened == [(True, "Request a VoIP account", "optional")]


def test_the_user_is_told_when_the_owner_has_made_the_account_and_sees_a_green_ready_line(base, tmp_path, monkeypatch):
    st, pg = make(tmp_path); a = owner(base, domain="pbx.example.org"); toasts = []; pg.ctx.toast.connect(toasts.append)
    assert not pg.acc_state.isVisible()                                                                                 # nothing asked yet: no line
    rid = submit_and_wait(pg, st); assert wait(lambda: pg.acc_state.isVisible())
    assert pg.acc_state.property("accstate") == "amber" and "waiting" in pg.acc_state.text() and not toasts            # waiting: amber, no notice yet
    a.post("voip", "voip_approve", _tab="set", rid=str(rid), ext="2001", pw="Secret-pass-1"); pg._req_check(False)
    assert wait(lambda: st.settings.get("voip_req_state") == "linked")
    assert pg.acc_state.property("accstate") == "green" and "ready for use" in pg.acc_state.text() and "2001" in pg.acc_state.text()            # green: ready
    assert toasts.count("Your VoIP account is ready for use: extension 2001.") == 1                                       # told once, with the extension
    pg._req_check(True); wait(lambda: False, secs=0.5); assert toasts.count("Your VoIP account is ready for use: extension 2001.") == 1       # the next checks do not repeat it
    a.post("voip", "voip_block", _tab="acc", rid=str(rid), hours="0", reason="Misuse"); ph = pg.ph; monkeypatch.setattr(ph, "sign_out", lambda *x, **k: None)
    pg._req_check(True); assert wait(lambda: pg.acc_state.property("accstate") == "red") and "blocked" in pg.acc_state.text()            # blocked: red
    a.post("voip", "voip_unblock", _tab="acc", rid=str(rid)); pg._req_check(True); assert wait(lambda: pg.acc_state.property("accstate") == "green")
    a.post("voip", "voip_release", _tab="acc", rid=str(rid)); pg._req_check(True); assert wait(lambda: pg.acc_state.property("accstate") == "muted")      # let go: grey
    from app import i18n
    i18n.set_language("el")
    try: assert i18n.tr("Your VoIP account is ready for use: extension 2001.") == "Ο λογαριασμός VoIP σου είναι έτοιμος για χρήση: εσωτερικό 2001." and i18n.tr("Your account is ready for use") == "Ο λογαριασμός σου είναι έτοιμος για χρήση"
    finally: i18n.set_language("en")
