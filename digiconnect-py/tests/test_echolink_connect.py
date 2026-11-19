"""EchoLink connection in the application: who answered is shown (callsign and name as the STATION sent them), the Connected / Disconnected signals play only for
a REAL change of a real link, connecting also listens ("Stop listening" is ready at once), and the 30-second wait is translated."""
import threading, pytest
from app.qt import QtWidgets as W
from app.store import Store
from app.context import Ctx
from app.engine import NullEngine
from app.engine_client import EngineClient
from app.rules import Target
from app import signals, i18n


class Link:
    def __init__(self, target):
        self.key, self.target, self.rx, self.tx, self.state, self.sent = f"{target.net}:{target.id}", target, set(), False, "connecting", []; self.cfg_variant = ""
    def send(self, cmd, **kw): self.sent.append((cmd, kw))
    def close(self): pass


def make(tmp_path):
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"
    eng = EngineClient("/nonexistent", st); ctx = Ctx(st, eng)
    return st, eng, ctx


def add_link(eng, ctx, t, handle=1):
    ln = Link(t); eng.links[ln.key] = ln; ln.rx.add(handle)
    ctx.rules.select(t); ctx.rules.listen(t)
    return ln


def test_the_peer_the_station_reports_is_kept_and_shown(tmp_path):
    st, eng, ctx = make(tmp_path); t = Target("EchoLink", "SA7SVR-L", "x"); ln = add_link(eng, ctx, t)
    eng._on_event(ln, {"ev": "status", "state": "connected", "peer": "SA7SVR-L", "peername": "HELLAS Zone Net"})
    assert ctx.el_peers["SA7SVR-L"] == {"peer": "SA7SVR-L", "name": "HELLAS Zone Net"}
    eng._on_event(ln, {"ev": "peer", "peer": "SA7SVR-L", "peername": "Hellas"})                  # the station introduces itself differently later
    assert ctx.el_peers["SA7SVR-L"]["name"] == "Hellas"
    assert ctx.engine_connected("EchoLink", "SA7SVR-L") and not ctx.engine_connected("EchoLink", "OTHER")
    eng._on_event(ln, {"ev": "status", "state": "connected"})                                     # no peer in it: nothing is invented
    assert ctx.el_peers["SA7SVR-L"]["name"] == "Hellas"


def test_the_panel_says_connected_to_the_callsign_and_name_the_station_sent(tmp_path):
    from app.ui.workspace import Workspace
    st, eng, ctx = make(tmp_path); t = Target("EchoLink", "SA7SVR-L", "x"); ln = add_link(eng, ctx, t)
    ws = Workspace(ctx, "EchoLink", lambda *a: None); ws.show()
    eng._on_event(ln, {"ev": "status", "state": "connected", "peer": "SA7SVR-L", "peername": "HELLAS Zone Net"})
    W.QApplication.processEvents()
    head = ws.el_head.text()
    assert "SA7SVR-L" in head and "HELLAS Zone Net" in head and "Connected to" in head, head
    assert "has not sent a list" in head                                                         # connected, but the station sent no user list: said as it is
    eng._on_event(ln, {"ev": "nodetext", "text": "Welcome\nSM0ABC SV1XYZ"})
    W.QApplication.processEvents()
    assert "HELLAS Zone Net" in ws.el_head.text() and "connected" in ws.el_head.text()
    ws.close()


def test_the_signals_play_once_per_real_change_and_only_for_echolink(tmp_path, monkeypatch):
    played = []; monkeypatch.setattr(signals, "play", lambda name, speakers="", runner=None: played.append((name, speakers)) or True)
    st, eng, ctx = make(tmp_path); st.settings["speakers"] = "My speakers"
    t = Target("EchoLink", "SA7SVR-L", "x"); ln = add_link(eng, ctx, t)
    ctx.changed.emit(); assert played == []                                                      # nothing is connected yet: no sound
    eng._on_event(ln, {"ev": "status", "state": "connected", "peer": "SA7SVR-L"})
    assert played == [("connected", "My speakers")]
    ctx.changed.emit(); ctx.changed.emit(); assert played == [("connected", "My speakers")]      # the same connection does not play again
    eng._on_event(ln, {"ev": "status", "state": "timeout", "msg": "The station stopped answering"})
    assert played[-1][0] == "disconnected" and len(played) == 2
    other = Target("AllStar", "509830", "x"); ln2 = add_link(eng, ctx, other, 2)                  # an AllStarLink node says it in its own voice
    eng._on_event(ln2, {"ev": "status", "state": "connected"}); eng._on_event(ln2, {"ev": "status", "state": "disconnected"})
    dmr = Target("DMR", "91", "x"); ln3 = add_link(eng, ctx, dmr, 3)
    eng._on_event(ln3, {"ev": "status", "state": "connected"}); eng._on_event(ln3, {"ev": "status", "state": "disconnected"})
    assert len(played) == 2


def test_a_failed_connection_makes_no_connected_sound(tmp_path, monkeypatch):
    played = []; monkeypatch.setattr(signals, "play", lambda name, speakers="", runner=None: played.append(name) or True)
    st, eng, ctx = make(tmp_path); t = Target("EchoLink", "SA7SVR-L", "x"); ln = add_link(eng, ctx, t)
    eng._on_event(ln, {"ev": "status", "state": "error", "msg": "The EchoLink station did not answer within 30 seconds - it may be offline or busy, or a firewall blocks UDP 5198/5199"})
    assert played == []                                                                          # it never connected: no Connected and no Disconnected signal


def test_the_user_can_turn_the_signals_off(tmp_path, monkeypatch):
    played = []; monkeypatch.setattr(signals, "play", lambda name, speakers="", runner=None: played.append(name) or True)
    st, eng, ctx = make(tmp_path); st.settings["sound_signals"] = False
    t = Target("EchoLink", "SA7SVR-L", "x"); ln = add_link(eng, ctx, t)
    eng._on_event(ln, {"ev": "status", "state": "connected"}); eng._on_event(ln, {"ev": "status", "state": "disconnected"})
    assert played == []


def test_play_sends_the_tone_to_the_engine_on_the_chosen_speakers():
    got = []; done = threading.Event()
    def runner(cmd, want, timeout): got.append((cmd, want)); done.set()
    assert signals.play("connected", "My speakers", runner=runner) and done.wait(3)
    assert got == [({"cmd": "test_spk", "device": "My speakers", "tone": "connected"}, "test_spk")]
    assert signals.play("nonsense", "x", runner=runner) is False                                  # only the two known signals exist
    assert signals.NETWORKS == ("EchoLink",) and signals.NAMES == ("connected", "disconnected")


class StubEngine(NullEngine):
    def __init__(self): self.calls = []
    def start_rx(self, handle, target): self.calls.append(("rx", target.net, target.id)); return ""
    def connect_tx(self, target): self.calls.append(("tx", target.net, target.id)); return ""


@pytest.mark.parametrize("net,listens", [("EchoLink", True), ("AllStar", True), ("DMR", False), ("C4FM", False)])
def test_connecting_a_call_also_listens_so_stop_listening_is_ready(tmp_path, net, listens):
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"; eng = StubEngine(); ctx = Ctx(st, eng)
    t = Target(net, "SA7SVR-L" if net == "EchoLink" else "509830", "x"); ctx.select(t)
    ctx.toggle_tx()
    assert ctx.rules.tx_connected and ctx.rules.is_listening(t) is listens, (net, eng.calls)
    assert ("tx", net, t.id) in eng.calls and (("rx", net, t.id) in eng.calls) is listens
    ctx.toggle_tx(); assert not ctx.rules.tx_connected                                          # Disconnect still ends the transmit link as before
    ctx.toggle_listen(); ctx.toggle_listen()                                                    # Listen / Stop listening keep working on their own


def test_the_30_second_message_and_the_new_texts_are_translated():
    i18n.set_language("el")
    try:
        for msg in ("The EchoLink station did not answer within 30 seconds - it may be offline or busy, or a firewall blocks UDP 5198/5199",
                    "Play a sound when a station connects or disconnects", "Connected to {}", "the station has not sent a list of connected stations"):
            assert i18n.tr(msg) != msg, msg
    finally:
        i18n.set_language("en")


def test_the_sound_option_is_in_the_audio_block_and_is_saved(tmp_path, monkeypatch):
    from app.ui import audioblock
    from app import audio_devices as AD
    monkeypatch.setattr(AD, "list_devices", lambda force=False: ([], [], ""))
    st = Store(tmp_path); ctx = Ctx(st, NullEngine())
    b = audioblock.AudioBlock(ctx)
    assert b.sig.isChecked() and st.settings.get("sound_signals", True) is True
    b.sig.setChecked(False); assert st.settings["sound_signals"] is False
    b.sig.setChecked(True); assert st.settings["sound_signals"] is True


def test_the_voip_button_is_reserved_and_switched_off(tmp_path):
    from app.ui.main_window import MainWindow
    st = Store(tmp_path); ctx = Ctx(st, NullEngine()); w = MainWindow(ctx)
    assert not w.voip_btn.isEnabled() and w.voip_btn.text() == "VoIP"                       # nothing is shown or connected: it is only reserved for a later version
    assert "VoIP" not in w.tabs and "Not available in this version" in w.voip_btn.toolTip()
    i18n.set_language("el")
    try: assert i18n.tr(w.voip_btn.toolTip()) != w.voip_btn.toolTip()
    finally: i18n.set_language("English")
