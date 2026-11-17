"""Owner control of the modes: panel -> signed licence answer -> program (real PHP server code + the real window)."""
import json, time, urllib.parse, urllib.request
import pytest
from app.rules import Target
from app import license as L
from app.policy import Policy
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_server_payments import Admin
from test_ui_smoke import win, pick  # noqa: F401
from test_licence_ui import pump

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")
ALL = ["DMR", "D-Star", "C4FM", "NXDN", "P25", "M17", "AllStar", "EchoLink"]


def pol(srv, iid="inst-1", v="2.3.1"):
    q = urllib.parse.urlencode(dict(id=iid, v=v, hw="a" * 32, n="0" * 32))
    return json.loads(json.loads(urllib.request.urlopen(srv.base + "manifest.php?" + q).read())["payload"])["pol"]


def sel(a, ids, modes, act="-", txset="-", testerset="-"):
    return a.post("modes", "mode_inst", **{"ids[]": ids, "modes[]": modes}, act=act, txset=txset, testerset=testerset)


def test_default_everything_open_except_echolink_and_transmit_allowed(srv):
    lic(srv).register(PERSON); p = pol(srv)
    assert p["off"] == ["EchoLink"] and p["tx"] == 1 and p["old"] == 0


def test_panel_buttons_close_open_and_testers_only_for_everyone(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    a.post("modes", "mode_set", mode="NXDN", state="off"); assert "NXDN" in pol(srv)["off"]
    a.post("modes", "mode_set", mode="NXDN", state="on"); assert "NXDN" not in pol(srv)["off"]
    a.post("modes", "mode_set", mode="P25", state="beta"); assert "P25" in pol(srv)["off"]              # not a tester: closed
    srv.sql("UPDATE dc_installs SET tester=1"); assert "P25" not in pol(srv)["off"]                       # tester: open
    a.post("modes", "modes_all", state="off"); assert sorted(pol(srv)["off"]) == sorted(ALL)
    a.post("modes", "modes_all", state="on"); assert pol(srv)["off"] == []
    a.post("modes", "mode_set", mode="Bogus", state="off"); assert pol(srv)["off"] == []                    # unknown names change nothing


def test_selected_installations_only_and_back_to_general_setting(srv):
    for i in ("inst-1", "inst-2", "inst-3"): lic(srv, i).register(dict(PERSON, mail=f"{i}@example.org"))
    a = Admin(srv.base)
    a.post("modes", "mode_set", mode="DMR", state="off")                                                  # closed for everyone
    sel(a, ["inst-2"], ["DMR", "M17"], "on", "-", "-")
    assert "DMR" in pol(srv, "inst-1")["off"] and "DMR" not in pol(srv, "inst-2")["off"] and "DMR" in pol(srv, "inst-3")["off"]
    sel(a, ["inst-1", "inst-3"], ["P25"], "off", "0", "1")
    assert "P25" in pol(srv, "inst-1")["off"] and pol(srv, "inst-1")["tx"] == 0 and pol(srv, "inst-2")["tx"] == 1
    assert srv.sql("SELECT tester FROM dc_installs WHERE id='inst-3'")[0]["tester"] == 1
    sel(a, ["inst-2"], ["DMR"], "reset", "-", "-")
    assert "DMR" in pol(srv, "inst-2")["off"]                                                             # follows the general setting again
    sel(a, ["inst-1"], [], "-", "def", "-")
    assert pol(srv, "inst-1")["tx"] == 1
    assert "σε 2 εγκαταστάσεις" in sel(a, ["inst-1", "inst-3"], ["M17"], "off", "-", "-")
    out = sel(a, [], ["M17"], "off", "-", "-")
    assert "Διάλεξε τουλάχιστον μία εγκατάσταση" in out                                          # nothing ticked: a message, no change


def test_listen_only_and_minimum_version(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    a.post("modes", "modes_note", tx_all="0", min_version="2.4.0", modes_note_el="Κλειστό", modes_note_en="Closed", tx_note_el="", tx_note_en="", min_msg_el="", min_msg_en="")
    p = pol(srv, v="2.3.1"); assert p["tx"] == 0 and p["old"] == 1 and sorted(p["off"]) == sorted(ALL) and "2.4.0" in p["note"]
    p = pol(srv, v="2.4.0"); assert p["old"] == 0 and p["tx"] == 0 and p["note"].startswith("Κλειστό\nClosed")
    a.post("modes", "modes_note", tx_all="1", min_version="bad", modes_note_el="", modes_note_en="", tx_note_el="", tx_note_en="", min_msg_el="", min_msg_en="")
    p = pol(srv); assert p["tx"] == 1 and p["old"] == 0 and p["minv"] == ""


def test_panel_page_has_a_button_for_every_mode_and_changes_are_in_the_activity_log(srv):
    lic(srv).register(PERSON); a = Admin(srv.base); a.post("modes", "mode_set", mode="M17", state="off")
    page = a.page("modes")
    for m in ALL: assert m in page
    assert page.count('name="state" value="beta"') == len(ALL) and "mode_inst" in page and 'name="ids[]"' in page
    assert "M17" in a.page("activity")


def test_policy_is_signed_with_the_answer_so_it_cannot_be_edited_in_the_cache(srv):
    l = lic(srv); l.register(PERSON); Admin(srv.base).post("modes", "mode_set", mode="NXDN", state="off")
    d = l.check(); assert "NXDN" in d["pol"]["off"]
    c = l.store.settings["lic"]; c["payload"] = c["payload"].replace('"NXDN"', '"XXXX"')
    assert l.cache() == {}                                                                                  # an edited cache is not believed


def test_program_closes_the_mode_at_once_blocks_listen_connect_ptt_and_greys_the_tab(srv, win):
    w, ctx, app = win; l = lic(srv); l.register(PERSON)
    calls = []; ctx.engine.start_rx = lambda h, t: calls.append(("rx", t.net)) or "Connected"; ctx.engine.connect_tx = lambda t: calls.append(("tx", t.net)) or "Connected"
    ctx.engine.stop_rx = lambda h: calls.append(("stop", h)); ctx.engine.preview = True
    ws = pick(w, "DMR", 4); ws.tx.listen.click(); ws.tx.connect.click()
    assert ctx.rules.is_listening(ctx.selected) and ctx.rules.tx_connected and ("rx", "DMR") in calls
    Admin(srv.base).post("modes", "mode_set", mode="DMR", state="off")
    v = l.verdict(l.check()); w._license_changed(v)                                                         # what the hourly check does
    assert not ctx.rules.rx and not ctx.rules.tx_connected                                                  # stopped at once
    assert "DMR · " in w.tabs["DMR"].text() and w.tabs["DMR"].property("closed") is True and w.tabs["NXDN"].property("closed") in (False, None)
    n = len(calls); ws.tx.listen.click(); ws.tx.connect.click(); ws.tx.hold.click()
    assert len(calls) == n and not ctx.rules.rx and not ctx.rules.tx_connected                             # nothing starts again
    assert w.ws["DMR"].closed_note.isVisibleTo(w.ws["DMR"]) and not w.ws["DMR"]._sc.isEnabled()
    Admin(srv.base).post("modes", "mode_set", mode="DMR", state="on"); w._license_changed(l.verdict(l.check()))
    assert w.tabs["DMR"].property("closed") is False and w.ws["DMR"]._sc.isEnabled()
    ws.tx.listen.click(); assert ctx.rules.is_listening(ctx.selected)                                      # open again: works


def test_listen_only_stops_transmitting_and_refuses_new_ptt(srv, win):
    w, ctx, app = win
    ctx.engine.start_rx = lambda h, t: "Connected"; ctx.engine.connect_tx = lambda t: "Connected"; ctx.engine.preview = True; ctx.engine.ptt = lambda on: None; ctx.engine.disconnect_tx = lambda: None
    ws = pick(w, "DMR", 4); ws.tx.listen.click(); ws.tx.connect.click(); ws.tx.latch.click(); assert ctx.rules.ptt
    ctx.apply_policy(dict(off=[], tx=0, txnote="Μόνο ακρόαση\nListen only"))
    assert not ctx.rules.ptt and not ctx.rules.tx_connected and ctx.rules.is_listening(ctx.selected)         # listening goes on, transmitting stops
    ws.tx.connect.click(); assert not ctx.rules.tx_connected
    ctx.apply_policy(dict(off=[], tx=1)); ws.tx.connect.click(); assert ctx.rules.tx_connected


def test_the_last_policy_is_kept_offline(srv):
    l = lic(srv); l.register(PERSON); Admin(srv.base).post("modes", "mode_set", mode="M17", state="off"); l.check()
    srv.proc.kill(); srv.proc.wait()
    v = l.verdict(None, "down"); pl = Policy((v.info or {}).get("pol"))
    assert not pl.allows("M17") and pl.allows("DMR")


def test_message_language_pick():
    from app import i18n
    from app.policy import pick as pk
    i18n.set_language("English"); assert pk("Κλειστό\nClosed") == "Closed"
    i18n.set_language("Ελληνικά"); assert pk("Κλειστό\nClosed") == "Κλειστό"; i18n.set_language("English")


def ping(srv, iid="inst-1", v="2.3.1"):
    q = urllib.parse.urlencode(dict(id=iid, v=v, os="linux", arch="x64"))
    return json.loads(urllib.request.urlopen(srv.base + "ping.php?" + q).read())


def test_ping_carries_a_change_stamp_that_moves_only_when_something_changes(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    r0 = ping(srv)["rev"]; assert r0 and ping(srv)["rev"] == r0                                              # same state: same stamp
    a.post("modes", "mode_set", mode="NXDN", state="off"); r1 = ping(srv)["rev"]; assert r1 != r0            # a mode closed: new stamp
    a.post("modes", "mode_set", mode="NXDN", state="on"); assert ping(srv)["rev"] == r0                      # back to the same state: the old stamp
    a.post("modes", "modes_note", tx_all="0", min_version="", modes_note_el="Κείμενο", modes_note_en="Text"); assert ping(srv)["rev"] != r0


def test_presence_asks_for_the_full_answer_as_soon_as_the_stamp_changes(srv, tmp_path):
    from app.presence import Presence
    from app.store import Store
    from app.context import Ctx
    lic(srv).register(PERSON); (tmp_path / "d").mkdir(); ctx = Ctx(Store(tmp_path / "d"))
    class U:
        def params(self): return dict(id="inst-1", v="2.3.1", os="linux", arch="x64", shell="2.2.0")
    p = Presence(ctx, U(), srv.base + "ping.php"); hit = []; p.rev_changed.connect(lambda: hit.append(1))
    p._send(p.query()); assert p.rev and not hit                                                              # the first answer is only the baseline
    p._send(p.query()); assert not hit
    Admin(srv.base).post("modes", "mode_set", mode="P25", state="off")
    p._send(p.query()); assert hit == [1]                                                                       # change seen -> the program re-checks at once


def test_echolink_closed_by_the_owner_looks_closed(srv, win):
    w, ctx, app = win
    ctx.apply_policy(dict(off=["EchoLink"], note="Κλειστό\nClosed"))
    assert w.tabs["EchoLink"].text() == "EchoLink · " + __import__("app.i18n", fromlist=["tr"]).tr("closed") and w.tabs["EchoLink"].property("closed") is True
    assert w.ws["EchoLink"].closed_note.isVisibleTo(w.ws["EchoLink"])
    ctx.apply_policy(dict(off=[]))
    assert w.tabs["EchoLink"].text() == "EchoLink" and w.tabs["EchoLink"].property("closed") is False


def test_licence_window_says_when_the_servers_answer_was_not_accepted_and_which_modes_are_closed(srv):
    """If the owner's settings do not arrive (wrong/missing signature key) the person and the owner must be able to SEE it, not guess."""
    from app.ui.license_dialog import LicenceDialog, Watcher
    from test_license import lic as mk
    a = Admin(srv.base); a.post("modes", "mode_set", mode="DMR", state="off")
    good = mk(srv); good.evaluate(); d = LicenceDialog(Watcher(good)); t = d.status.text()
    assert "Server answer: ✓" in t and "Closed modes: DMR" in t and good.last_error == ""
    bad = L.License(good.store, good.params, base=srv.base, hw=good.hw, pubkeys=["AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="])
    bad.evaluate(); assert bad.last_error == "bad signature"
    t = LicenceDialog(Watcher(bad)).status.text(); assert "Server answer: ✗ bad signature" in t and "not applied" in t


def test_block_reaches_a_running_program_within_one_poll_even_with_show_online_off(srv, tmp_path, win):
    """The owner closes a mode in the panel: the program's own 5-second stamp poll sees it, fetches the signed answer and the mode is stopped at once - no restart, no ping needed."""
    from app.presence import LiveStamp
    w, ctx, app = win
    l = lic(srv); l.register(PERSON); l.evaluate()
    ctx.store.settings["share_presence"] = False                                                           # the ping is off: the block must still arrive
    class U:
        def params(self): return dict(id="inst-1", v="2.3.1", os="linux", arch="x64", shell="2.2.0")
    live = LiveStamp(U(), srv.base + "rev.php"); got = []
    live.rev_changed.connect(lambda: got.append(1)); live.rev_changed.connect(lambda: ctx.apply_policy((l.evaluate().info or {}).get("pol")))
    live._send(); assert live.last_ok and got == [1]                                                       # first stamp: one check at start
    live._send(); assert got == [1]                                                                         # nothing changed: nothing asked
    assert ctx.policy.allows("NXDN")
    Admin(srv.base).post("modes", "mode_set", mode="NXDN", state="off")
    live._send(); assert got == [1, 1]                                                                      # the very next poll sees it
    assert not ctx.policy.allows("NXDN") and ctx.policy.allows("DMR")                                        # applied live
    Admin(srv.base).post("modes", "mode_set", mode="NXDN", state="on")
    live._send(); assert ctx.policy.allows("NXDN")                                                          # and the unblock the same way


def test_rev_php_only_reads_it_creates_no_installation_and_shows_nobody_online(srv):
    r = json.loads(urllib.request.urlopen(srv.base + "rev.php?id=ghost-1").read()); assert r["ok"] is True and r["rev"] == ""
    assert srv.sql("SELECT id FROM dc_installs WHERE id='ghost-1'") == []


def test_essid_is_the_two_digit_suffix_like_pistar_and_selfcare():
    from app.engine_client import essid_for_engine, hotspot_id
    assert hotspot_id(2407219, "") == 2407219 and hotspot_id(2407219, None) == 2407219 and hotspot_id(2407219, "  ") == 2407219     # none: the DMR ID itself
    assert hotspot_id(2407219, "22") == 240721922 and hotspot_id(2407219, "00") == 240721900 and hotspot_id(2407219, "0") == 240721900
    assert hotspot_id(2407219, "01") == 240721901 and hotspot_id(2407219, "99") == 240721999 and hotspot_id(2407219, "x") == 2407219
    assert essid_for_engine("") == 0 and essid_for_engine("22") == 23                                       # the engine counts like DroidStar: suffix + 1
