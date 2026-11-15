"""Listening to a group: the tile says Idle / Receiving audio with the callsign of the station that talks, 'Receive only' at the bottom,
and a side panel with the station details opens by itself. DMR sends only the DMR ID; the callsign comes from the RadioID database."""
import json
from app.store import Store
from app.rules import Target
from app.context import Ctx
from app.callbook import Callbook, parse
from app.ui.favorites import Favorites

ANSWER = json.dumps({"count": 1, "results": [dict(id=2021015, callsign="sy1bru", fname="George", surname="", city="Athens", state="", country="Greece", remarks="")]}).encode()


def make(tmp_path, answers=None):
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"; st.toggle_fav("DMR", "930", "PanHellenic Chat"); st.toggle_fav("DMR", "20208", "YSF202 Greece")
    ctx = Ctx(st); calls = []
    def fetch(url):
        calls.append(url)
        if answers is None: raise OSError("offline")
        return answers
    ctx.callbook = Callbook(tmp_path, fetch=fetch)
    return ctx, calls


def listen(ctx, tg, name):
    t = Target("DMR", tg, name); ctx.select(t); ctx.rules.listen(t); ctx.changed.emit()
    class L:                                                        # the engine link of this receiver
        target = t; rx = {ctx.rules.rx[-1].handle}
    return L()


def rx(state, srcid, **k): return dict(state=state, srcid=srcid, src="", callsign="SA7SVR", dst="930", **k)


def test_parse_radioid_answer():
    i = parse(ANSWER, 2021015)
    assert i["call"] == "SY1BRU" and i["name"] == "George" and i["country"] == "Greece" and i["city"] == "Athens"
    assert parse(b'{"count":0,"results":[]}', 5) is None and parse(b"not json") is None and parse(ANSWER, 999) is None


def test_callbook_keeps_answers_on_disk(tmp_path):
    cb = Callbook(tmp_path, fetch=lambda u: ANSWER); assert cb.lookup_now(2021015)["call"] == "SY1BRU"
    cb2 = Callbook(tmp_path, fetch=lambda u: (_ for _ in ()).throw(OSError("offline")))
    assert cb2.cached(2021015)["call"] == "SY1BRU" and not cb2.needs_fetch(2021015)          # asked once, then remembered
    off = Callbook(tmp_path / "x", fetch=lambda u: (_ for _ in ()).throw(OSError("offline"))); assert off.lookup_now(7) is None and off.cached(7) is None


def test_tile_shows_idle_then_callsign_then_receive_only(tmp_path):
    ctx, calls = make(tmp_path, ANSWER); fv = Favorites(ctx, lambda *a: None)
    card = next(c for c in fv.cards if c.fav["id"] == "930")
    assert "Activity unavailable" in card.act.text() and card.tx.text() == "Transmit disconnected" and not fv.side.isVisibleTo(fv)
    ln = listen(ctx, "930", "PanHellenic Chat")
    assert "Idle" in card.act.text() and card.tx.text() == "Receive only" and card.who.isHidden() and fv.side.isVisibleTo(fv)      # listening: the panel opens by itself
    ctx.callbook.mem[2021015] = dict(at=1e12, info=parse(ANSWER, 2021015))                                                     # the lookup has answered
    ctx._on_heard(ln, rx("new", 2021015)); fv.refresh_state()
    assert not card.who.isHidden() and card.who.text() == "SY1BRU" and "George" in card.who2.text() and "Greece" in card.who2.text()
    p = fv.side
    assert p.state.text() == "Traffic detected" and p.call.text() == "SY1BRU" and p.name.text() == "George" and "2021015" in p.rows.text() and "Greece" in p.rows.text() and "RadioID" in p.src.text()
    ctx._on_heard(ln, rx("end", 2021015)); fv.refresh_state()
    assert card.who.isHidden() and "Idle" in card.act.text() and p.state.text() == "Last station heard" and p.call.text() == "SY1BRU"      # the details stay after the transmission
    other = next(c for c in fv.cards if c.fav["id"] == "20208"); assert "Activity unavailable" in other.act.text() and other.tx.text() == "Transmit disconnected"
    ctx.stop_all(); fv.refresh_state(); assert not p.isVisibleTo(fv) and "Activity unavailable" in card.act.text()


def test_amber_tile_in_multiple_mode_says_receiving_audio(tmp_path):
    from app.rules import ListenMode
    ctx, _ = make(tmp_path, ANSWER); ctx.rules.set_mode(ListenMode.MULTIPLE); fv = Favorites(ctx, lambda *a: None)
    ln = listen(ctx, "930", "PanHellenic Chat"); ctx.callbook.mem[2021015] = dict(at=1e12, info=parse(ANSWER, 2021015))
    ctx._on_heard(ln, rx("streaming", 2021015)); fv.refresh_state(); card = next(c for c in fv.cards if c.fav["id"] == "930")
    assert "Receiving audio" in card.act.text() and card.who.text() == "SY1BRU"


def test_unknown_id_shows_the_plain_id_and_is_honest(tmp_path):
    ctx, calls = make(tmp_path, None); fv = Favorites(ctx, lambda *a: None); ln = listen(ctx, "930", "PanHellenic Chat")
    ctx._on_heard(ln, rx("new", 2021107)); fv.refresh_state(); card = next(c for c in fv.cards if c.fav["id"] == "930")
    assert card.who.text() == "2021107" and fv.side.call.text() == "2021107" and "Nothing is invented" in fv.side.src.text()


def test_lookup_result_replaces_the_id_in_last_heard_and_tile(tmp_path):
    ctx, _ = make(tmp_path, ANSWER); fv = Favorites(ctx, lambda *a: None); ln = listen(ctx, "930", "PanHellenic Chat")
    ctx.callbook.fetch = lambda u: ANSWER; ctx._on_heard(ln, rx("new", 2021015)); assert ctx.last_heard[0]["src"] == "2021015"
    info = ctx.callbook.lookup_now(2021015); ctx._on_station(2021015, info); fv.refresh_state()
    assert ctx.last_heard[0]["src"] == "SY1BRU" and fv.side.call.text() == "SY1BRU"
    ctx._on_heard(ln, rx("streaming", 2021015)); assert len(ctx.last_heard) == 1           # the same transmission goes on: still one row


def test_new_qso_button_takes_the_heard_station(tmp_path):
    ctx, _ = make(tmp_path, ANSWER); got = []; fv = Favorites(ctx, lambda *a: got.append(dict(ctx.qso_prefill)))
    ln = listen(ctx, "930", "PanHellenic Chat"); ctx.callbook.mem[2021015] = dict(at=1e12, info=parse(ANSWER, 2021015)); ctx._on_heard(ln, rx("new", 2021015)); fv.refresh_state()
    fv.side.nq.click(); assert got and got[0]["callsign"] == "SY1BRU" and got[0]["name"] == "George" and got[0]["country"] == "Greece" and got[0]["dest"] == "930"


def test_received_audio_moves_the_station_bar_not_the_microphone(tmp_path):
    from app.ui.knob import MicKnob
    ctx, _ = make(tmp_path, ANSWER); fv = Favorites(ctx, lambda *a: None); ln = listen(ctx, "930", "PanHellenic Chat")
    ctx.engine.rx_level = lambda: 0.6; ctx.engine.mic_level = lambda: 0.6
    ctx.callbook.mem[2021015] = dict(at=1e12, info=parse(ANSWER, 2021015)); ctx._on_heard(ln, rx("new", 2021015)); fv.refresh_state(); fv._levels()
    card = next(c for c in fv.cards if c.fav["id"] == "930"); assert card.lvl.v == 0.6 and fv.side.lvl.v == 0.6      # the station that talks shows the level
    k = MicKnob(ctx, 62); k._poll(); assert k._level == 0                                                          # receiving: the microphone stays quiet
    ctx.rules.ptt = True; k._poll(); assert k._level == 0.6                                                        # I speak: it moves
    fv._levels(); assert card.lvl.v == 0                                                                           # and the listening bar rests while I transmit



def test_dtmf_keypad(tmp_path):
    from app.ui.dtmfpad import DtmfPad
    ctx, _ = make(tmp_path, ANSWER); sent = []
    class Eng:
        name = "fake"
        def send_dtmf(self, t, keys): sent.append((t.id, keys)); return ""
        def ptt(self, on): pass
        def rx_level(self): return 0.0
        def mic_level(self): return 0.0
    ctx.engine = Eng(); pad = DtmfPad(ctx)
    assert "Choose an EchoLink" in pad.hint.text() and not pad.send.isEnabled() and pad.disp.text().startswith("0-9")       # nothing connected yet
    for k in "1*2#": pad.keys[k].click()
    assert pad.seq == "1*2#" and pad.disp.text() == "1*2#" and not pad.send.isEnabled()                                       # keys work, but no connection to send to
    pad.back.click(); assert pad.seq == "1*2"; pad.clear.click(); assert pad.seq == "" and not pad.back.isEnabled()
    assert pad.ad.isHidden(); pad.ad_toggle.setChecked(True); assert not pad.ad.isHidden(); pad.keys["A"].click(); assert pad.seq == "A"; pad._set("")
    t = Target("AllStar", "1999", "Hub"); ctx.select(t); ctx.changed.emit(); assert "AllStar" in pad.hint.text()
    pad.keys["5"].click(); pad.keys["0"].click(); assert pad.send.isEnabled(); pad.send.click()
    assert sent == [("1999", "50")] and pad.seq == ""                                                                          # sent to the node, the display is empty again
    for _ in range(40): pad.press("1")
    assert len(pad.seq) == 32                                                                                                 # at most 32 keys
    from PySide6 import QtTest
    from app.qt import Qt
    pad._set(""); QtTest.QTest.keyClick(pad, Qt.Key.Key_9); QtTest.QTest.keyClick(pad, Qt.Key.Key_Backspace); assert pad.seq == ""
    ctx.rules.ptt = True; ctx.changed.emit(); assert pad.stop.isEnabled()
