"""The VoIP page: what it shows before and after signing in, the people list with the states the server reported, the keypad, saving the account, and Greek."""
import time
import pytest
from app.qt import QtWidgets as W
from app.store import Store
from app.context import Ctx
from app.engine import NullEngine
from app.ui.voippage import VoipPage
from app.voip import phone as P, ua as U
from app import i18n


def make(tmp_path, **settings):
    st = Store(tmp_path); st.settings.update(settings); ctx = Ctx(st, NullEngine()); pg = VoipPage(ctx); pg.show(); W.QApplication.processEvents(); return st, ctx, pg


def test_the_page_starts_signed_out_and_nothing_can_be_called(tmp_path):
    st, ctx, pg = make(tmp_path)
    assert pg.sign.text() == "Sign in" and pg.reg.text() == "Not signed in" and pg.status.text() == "Sign in to call" and not pg.call_btn.isEnabled()
    assert not pg.in_box.isVisible() and not pg.hang.isVisible() and pg.server.text() == "sip.foxhost.org" and pg.port.text() == "5060" and pg.transport.currentText() == "UDP"
    assert pg.pw.echoMode() == W.QLineEdit.EchoMode.Password
    pg._call(); assert pg.who.text() == "Sign in first, then enter a number"


def test_the_keypad_types_a_number_and_the_account_is_saved(tmp_path):
    st, ctx, pg = make(tmp_path)
    for k in "1002": pg.keys[k].click()
    assert pg.number.text() == "1002"
    pg.server.setText(" pbx.example.org "); pg.port.setText("abc"); pg.transport.setCurrentText("TLS"); pg.user.setText("1001"); pg.pw.setText("pw"); pg.remember.setChecked(False); pg.tlsv.setChecked(False)
    pg.save_account(); s = st.settings
    assert (s["voip_server"], s["voip_port"], s["voip_transport"], s["voip_user"], s["voip_pw"], s["voip_remember"], s["voip_tls_verify"]) == ("pbx.example.org", 5060, "tls", "1001", "", False, False)     # a bad port falls back to 5060; no password is stored unless asked
    pg.remember.setChecked(True); pg.save_account(); assert st.settings["voip_pw"] == "pw"
    assert Store(tmp_path).settings["voip_server"] == "pbx.example.org"                                         # it is on disk


def test_people_are_listed_with_what_the_server_reported(tmp_path):
    st, ctx, pg = make(tmp_path, voip_contacts=[dict(name="Takis", number="1002", callsign="SV1CDR"), dict(name="", number="1003", callsign=""), dict(name="Bad", number="", callsign="")])
    assert pg.people.count() == 2 and "Waiting for the server" in pg.people.item(0).text() and "Takis · SV1CDR" in pg.people.item(0).text() and "Add the people you call" not in pg.people_note.text()
    ctx.phone.dialog["1002"] = ("free", "no call"); ctx.phone.presence["1002"] = ("online", ""); ctx.phone.dialog["1003"] = ("busy", "on a call"); pg.refresh_people()
    assert pg.people.item(0).text().endswith("Available") and pg.people.item(1).text().endswith("On a call") and pg.people.item(1).text().startswith("1003")
    assert "Sign in to see who is available." in pg.people_note.text()
    i18n.set_language("el")
    try: pg.refresh_people(); assert pg.people.item(0).text().endswith("Διαθέσιμος") and pg.people.item(1).text().endswith("Σε κλήση")
    finally: i18n.set_language("en")


def test_adding_and_removing_people_updates_the_list_and_the_settings(tmp_path):
    st, ctx, pg = make(tmp_path)
    ctx.phone.set_contacts([dict(name="A", number=" 1001 ", callsign="x1"), dict(name="B", number="  ", callsign="")])
    pg.refresh_people(); assert pg.people.count() == 1 and st.settings["voip_contacts"] == [dict(name="A", number="1001", callsign="x1")]
    pg.people.setCurrentRow(0); pg._remove(); assert pg.people.count() == 0 and st.settings["voip_contacts"] == [] and "Add the people you call" in pg.people_note.text()


class FakeCall:
    def __init__(self, direction="in", state="incoming"): self.direction, self.state, self.remote_name, self.remote_user, self.remote_uri, self.held_by_remote, self.end_reason, self.answered_at, self.duration = direction, state, "Takis", "1002", "sip:1002@x", False, "", 0.0, 0.0


def test_an_incoming_call_shows_answer_and_decline_and_an_ended_call_says_why(tmp_path):
    st, ctx, pg = make(tmp_path)
    c = FakeCall(); ctx.phone.call = c; pg._on_call(c, "incoming")
    assert pg.in_box.isVisible() and pg.status.text() == "Incoming call" and pg.who.text() == "From Takis · 1002" and not pg.call_btn.isVisible()
    c.state = "ended"; c.end_reason = "Missed"; ctx.phone.call = c; pg._on_call(c, "ended")
    assert not pg.in_box.isVisible() and pg.status.text() == "Missed" and pg.who.text() == "Call ended" and pg.call_btn.isVisible()
    i18n.set_language("el")
    try: c.end_reason = "Busy (486 Busy Here)"; pg._on_call(c, "ended"); assert pg.status.text() == "Κατειλημμένο (486 Busy Here)" and pg.who.text() == "Η κλήση τελείωσε"
    finally: i18n.set_language("en")


def test_the_registration_line_follows_the_state(tmp_path):
    st, ctx, pg = make(tmp_path); set_ = ctx.phone._set_reg                                                   # the phone announces its state; the page only shows it
    set_("registering", ""); assert pg.sign.text() == "Sign out" and pg.reg.text().startswith("Signing in")
    set_("registered", "Registered as 1001@x"); assert pg.reg.property("tone") == "green" and pg.call_btn.isEnabled() and pg.status.text() == "No call" and "Registered as 1001@x" in pg.reg.text()
    set_("failed", "Wrong username or password (401 Unauthorized)"); assert pg.sign.text() == "Sign in" and pg.reg.property("tone") == "red" and "401" in pg.reg.text() and not pg.call_btn.isEnabled()
    i18n.set_language("el")
    try: set_("failed", "Wrong username or password (401 Unauthorized)"); assert "Λάθος όνομα χρήστη ή κωδικός (401" in pg.reg.text()
    finally: i18n.set_language("en")


def test_the_call_list_shows_direction_name_and_length(tmp_path):
    st, ctx, pg = make(tmp_path, voip_history=[dict(t=time.time(), dir="placed", number="1002", name="Takis", secs=75), dict(t=time.time(), dir="missed", number="1003", name="", secs=0)])
    pg.refresh_history(); a, b = pg.hist.item(0).text(), pg.hist.item(1).text()
    assert a.startswith("→") and "Takis" in a and "1002" in a and a.endswith("(1:15)") and "\n" in a and b.startswith("✕") and "1003" in b and "(" not in b.split("\n")[1]       # the length is in brackets, only when there was a conversation
    assert pg.hist.item(0).data(0x0100) == "1002"


def test_add_edit_remove_are_fixed_at_the_very_bottom_of_the_people_panel(tmp_path):
    st, ctx, pg = make(tmp_path)
    pg.resize(1280, 800); W.QApplication.processEvents()
    panel_bottom = pg.people.parentWidget().mapToGlobal(pg.people.parentWidget().rect().bottomLeft()).y()
    ys = [b.mapToGlobal(b.rect().bottomLeft()).y() for b in (pg.add, pg.edit, pg.rm)]
    assert len(set(ys)) == 1 and panel_bottom - ys[0] < 24, (ys, panel_bottom)                    # on one line, right at the bottom edge
    assert pg.add.y() > pg.hist.y() + pg.hist.height() - 2 and pg.add.y() > pg.people.y() + pg.people.height()   # below both lists
    assert abs(pg.add.width() - pg.edit.width()) <= 1 and abs(pg.edit.width() - pg.rm.width()) <= 1
    pg.resize(1280, 1000); W.QApplication.processEvents()                                         # a taller window: the buttons follow the bottom edge
    pb = pg.people.parentWidget().mapToGlobal(pg.people.parentWidget().rect().bottomLeft()).y()
    assert pb - pg.add.mapToGlobal(pg.add.rect().bottomLeft()).y() < 24
