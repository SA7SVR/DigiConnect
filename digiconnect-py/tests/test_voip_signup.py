"""Asking for a VoIP account, end to end: the program's page talks over real HTTP to the real PHP server (voip_request.php + the panel where the owner approves)."""
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
    a = Admin(srv.base); a.post("voip", "voip_set", voip_on="1" if opened else "", voip_server=kw.get("server", "pbx.example.org"), voip_port="5061", voip_transport="tls", voip_domain=kw.get("domain", "")); return a


def wait(cond, page=None, secs=10):
    end = time.time() + secs
    while time.time() < end:
        W.QApplication.processEvents()
        if cond(): return True
        time.sleep(0.02)
    return cond()


def make(tmp_path):
    st = Store(tmp_path); st.settings.update(callsign="SV1ABC", op_name="Nikos P"); ctx = Ctx(st, NullEngine()); pg = VoipPage(ctx); pg.show(); W.QApplication.processEvents(); return st, pg


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


def test_a_request_is_approved_and_the_account_fills_in_and_the_server_forgets_the_password(base, tmp_path):
    st, pg = make(tmp_path)
    a = owner(base, domain="pbx.example.org")
    # the same call the dialog makes when "Send the request" is pressed
    pg._run("submit", lambda: signup.submit(**PERSON))
    assert wait(lambda: st.settings.get("voip_req_state") == "pending") and st.settings["voip_req_id"] > 0 and len(st.settings["voip_req_token"]) == 32
    rid = base.sql("SELECT id FROM dc_voip_req")[0]["id"]
    pg._req_check(False); assert wait(lambda: "still waiting" in pg.req_lbl.text()), pg.req_lbl.text()
    a.post("voip", "voip_approve", rid=str(rid), ext="2001", pw="Secret-pass-1")
    pg._req_check(False)
    assert wait(lambda: st.settings.get("voip_req_state") == "done"), st.settings.get("voip_req_state")
    assert pg.user.text() == "2001" and pg.pw.text() == "Secret-pass-1" and pg.server.text() == "pbx.example.org" and pg.port.text() == "5061" and pg.transport.currentText() == "TLS" and pg.domain.text() == "pbx.example.org"
    assert st.settings["voip_user"] == "2001" and st.settings["voip_pw"] == "Secret-pass-1" and st.settings["voip_transport"] == "tls" and st.settings["voip_req_token"] == ""   # saved on this computer
    assert base.sql("SELECT pw FROM dc_voip_req")[0]["pw"] == ""                                  # and gone from the server
    assert "2001" in pg.req_lbl.text() and pg.req_btn.isVisible() and not pg.req_chk.isVisible()


def test_a_rejection_shows_the_reason_and_allows_a_new_request(base, tmp_path):
    st, pg = make(tmp_path); a = owner(base)
    pg._run("submit", lambda: signup.submit(**PERSON)); assert wait(lambda: st.settings.get("voip_req_state") == "pending")
    a.post("voip", "voip_reject", rid=str(base.sql("SELECT id FROM dc_voip_req")[0]["id"]), reason="No licence found")
    pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "rejected")
    assert "No licence found" in pg.req_lbl.text() and st.settings["voip_req_token"] == "" and pg.req_btn.isVisible() and pg.req_btn.text() == "Request an account again"
    assert pg.user.text() == ""                                                                    # nothing was filled in


def test_a_request_the_server_no_longer_knows_is_dropped(base, tmp_path):
    st, pg = make(tmp_path); owner(base)
    st.settings.update(voip_req_state="pending", voip_req_id=99, voip_req_token="a" * 32); pg._req_refresh()
    pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "")
    assert pg.req_btn.isVisible() and "does not know" in pg.req_lbl.text()


def test_a_network_error_keeps_the_request_so_it_can_be_checked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(signup, "BASE", "http://127.0.0.1:9/")
    st, pg = make(tmp_path); st.settings.update(voip_req_state="pending", voip_req_id=5, voip_req_token="t" * 32); pg._req_refresh()
    pg._req_check(False); assert wait(lambda: "cannot be reached" in pg.req_lbl.text())
    assert st.settings["voip_req_state"] == "pending" and st.settings["voip_req_token"] == "t" * 32 and pg.req_chk.isVisible()


def test_if_the_confirmation_fails_the_password_stays_saved_and_the_confirmation_is_repeated(base, tmp_path, monkeypatch):
    st, pg = make(tmp_path); a = owner(base)
    pg._run("submit", lambda: signup.submit(**PERSON)); assert wait(lambda: st.settings.get("voip_req_state") == "pending")
    a.post("voip", "voip_approve", rid=str(base.sql("SELECT id FROM dc_voip_req")[0]["id"]), ext="2002", pw="Another-pass-2")
    real = signup.ack; monkeypatch.setattr(signup, "ack", lambda *a, **k: (_ for _ in ()).throw(signup.SignupError("", "offline")))
    pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "ack" and "cannot be reached" in pg.req_lbl.text())
    assert st.settings["voip_pw"] == "Another-pass-2" and st.settings["voip_user"] == "2002" and base.sql("SELECT pw FROM dc_voip_req")[0]["pw"] == "Another-pass-2"   # not wiped before it is confirmed
    monkeypatch.setattr(signup, "ack", real)
    pg._req_check(False); assert wait(lambda: st.settings.get("voip_req_state") == "done")
    assert base.sql("SELECT pw FROM dc_voip_req")[0]["pw"] == ""


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
