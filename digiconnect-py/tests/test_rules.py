import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.rules import *

T = lambda n, i: Target(n, i, i)


def test_single_replaces_across_networks():
    s = SessionRules()
    assert s.listen(T("DMR", "91")).kind == "ok"
    o = s.listen(T("D-Star", "REF001C"))
    assert o.kind == "replaced" and len(o.removed) == 1 and len(s.rx) == 1


def test_multiple_capacity_and_replace():
    s = SessionRules(); s.set_mode(ListenMode.MULTIPLE)
    for tg in ("91", "2", "240", "2401"):
        assert s.listen(T("DMR", tg)).ok
    assert not s.listen(T("DMR", "9")).ok and len(s.rx) == 4
    for n, i in (("D-Star", "REF001C"), ("C4FM", "00006"), ("EchoLink", "SM7XYZ")):
        assert s.listen(T(n, i)).ok
    assert len(s.rx) == 7
    assert s.listen(T("D-Star", "XRF012A")).kind == "replaced" and len(s.rx) == 7
    assert s.listen(T("DMR", "91")).kind == "focused" and len(s.rx) == 7


def test_back_to_single_keeps_focus():
    s = SessionRules(); s.set_mode(ListenMode.MULTIPLE)
    s.listen(T("DMR", "91")); h = s.listen(T("DMR", "2")).handle; s.listen(T("D-Star", "REF001C"))
    s.focus_handle = h
    o = s.set_mode(ListenMode.SINGLE)
    assert [r.handle for r in s.rx] == [h] and len(o.removed) == 2


def test_listen_is_not_tx():
    s = SessionRules(); t = T("DMR", "91"); s.select(t); s.listen(t)
    assert not s.ptt_available and not s.ptt_press(False).ok
    s.connect_tx(t); assert s.ptt_available
    s.select(T("DMR", "2")); assert not s.ptt_available
    s.select(t); assert s.ptt_press(False).ok and s.ptt and not s.latched
    s.ptt_release(); assert not s.ptt and s.tx_connected and len(s.rx) == 1


def test_latch_limit_countdown():
    s = SessionRules(); t = T("DMR", "91"); s.select(t); s.connect_tx(t)
    assert s.set_limit(60) and not s.set_limit(90)
    s.ptt_press(True); assert s.latched and s.remaining == 60 and not s.set_limit(180)
    s.tick(44000); assert s.remaining == 16 and not s.countdown_red
    s.tick(1000); assert s.remaining == 15 and s.countdown_red
    s.tick(15000); assert not s.ptt


def test_fixed_destination_and_stop_conditions():
    s = SessionRules(); t = T("DMR", "91"); s.select(t); s.connect_tx(t); s.ptt_press(True)
    assert not s.connect_tx(T("DMR", "2")).ok and s.tx_target == t
    assert not s.set_mode(ListenMode.MULTIPLE).ok
    s.focus_lost(); assert not s.ptt
    s.ptt_press(False); s.stop_all(); assert not s.ptt and not s.tx_connected and not s.rx


def test_latch_twice_stops():
    s = SessionRules(); t = T("DMR", "91"); s.select(t); s.connect_tx(t)
    s.ptt_press(True); s.ptt_press(True); assert not s.ptt


def test_ducking_and_self_monitor():
    s = SessionRules(); s.set_mode(ListenMode.MULTIPLE)
    a, b = T("DMR", "91"), T("DMR", "2")
    ha, hb = s.listen(a).handle, s.listen(b).handle; s.select(a); s.connect_tx(a)
    assert s.effective_volume(s.find(hb)) == 1
    s.ptt_press(False)
    assert s.effective_volume(s.find(ha)) == 0 and s.effective_volume(s.find(hb)) < 1
    s.ducking = False; assert s.effective_volume(s.find(hb)) == 1
    s.net_muted["DMR"] = True; assert s.effective_volume(s.find(hb)) == 0


def test_card_amber_only_multiple_real_traffic():
    s = SessionRules(); h = s.listen(T("DMR", "91")).handle
    s.find(h).reports_traffic = True; assert s.card_state(s.find(h)) is CardState.PINK
    s.set_mode(ListenMode.MULTIPLE); assert s.card_state(s.find(h)) is CardState.AMBER
    s.find(h).muted = True; assert s.card_state(s.find(h)) is CardState.PINK


def test_validators():
    assert valid_dmr_tg("91") and valid_dmr_tg("16777215")
    assert not any(valid_dmr_tg(x) for x in ("0", "16777216", "-5", "9a", ""))
    assert valid_dtmf("*123#AD") and not valid_dtmf("") and not valid_dtmf("12E") and not valid_dtmf("1" * 33)
    assert valid_favorite_name("Ελλάδα") and not valid_favorite_name("") and valid_favorite_name("x" * 80) and not valid_favorite_name("x" * 81)
    assert valid_text_size(11) and valid_text_size(20) and not valid_text_size(21)
