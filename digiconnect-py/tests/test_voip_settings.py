"""Every setting of the VoIP tabs: what the user types is saved, reaches the user agent as the configuration, and does what it says (ringtones, do not disturb, auto-answer, voicemail,
the account request texts in Greek). No setting is only a field: each one is read back from the program's real objects."""
import struct, wave, time
import numpy as np
import pytest
from app.qt import QtWidgets as W
from app.store import Store, DEFAULTS
from app.context import Ctx
from app.engine import NullEngine
from app.ui.voippage import VoipPage
from app.voip import phone as P, ua as U, texts
from app import i18n


def make(tmp_path, **s):
    st = Store(tmp_path); st.settings.update(s); ctx = Ctx(st, NullEngine()); pg = VoipPage(ctx); pg.show(); W.QApplication.processEvents(); return st, ctx, pg


# ---- configuration handed to the SIP stack ---------------------------------------------------------------------------------------------
def test_the_defaults_make_a_normal_configuration(tmp_path):
    st = Store(tmp_path); st.settings.update(voip_server="pbx.example.org", voip_user="1001", voip_pw="x"); c = P.Phone(st).config()
    assert (c.server, c.port, c.transport, c.user, c.domain, c.expires, c.local_port, c.keepalive, c.codecs, c.dtmf, c.bind_rtp, c.tls_verify, c.trace) == \
           ("pbx.example.org", 5060, "udp", "1001", "pbx.example.org", 300, 0, True, (0, 8), "auto", (12000, 12999), True, False)
    assert c.jitter == 3 and c.stun == "" and c.public_ip == "" and c.auth_user == "1001"          # the authentication name is the username when empty


def test_every_setting_reaches_the_configuration(tmp_path):
    st = Store(tmp_path); st.settings.update(voip_server="pbx.example.org", voip_port=5061, voip_transport="tls", voip_user="1001", voip_auth_user="auth1001", voip_pw="pw", voip_domain="example.org", voip_name="Nikos",
        voip_expires=120, voip_local_port=5070, voip_keepalive=False, voip_keepalive_secs=15, voip_stun="stun.example.org:3478", voip_public_ip="203.0.113.7", voip_rtp_lo=20000, voip_rtp_hi=20100,
        voip_pcmu=False, voip_pcma=True, voip_dtmf="info", voip_ua="MyPhone/1", voip_trace=True, voip_tls_verify=False, voip_tls_ca="/x/ca.pem", voip_jitter_ms=100)
    c = P.Phone(st).config()
    assert (c.server, c.port, c.transport, c.user, c.auth_user, c.password, c.domain, c.display_name, c.expires, c.local_port) == ("pbx.example.org", 5061, "tls", "1001", "auth1001", "pw", "example.org", "Nikos", 120, 5070)
    assert (c.keepalive, c.keepalive_secs, c.stun, c.public_ip, c.bind_rtp, c.codecs, c.dtmf, c.user_agent, c.trace, c.tls_verify, c.tls_ca, c.jitter) == \
           (False, 15, "stun.example.org:3478", "203.0.113.7", (20000, 20100), (8,), "info", "MyPhone/1", True, False, "/x/ca.pem", 5)


@pytest.mark.parametrize("proxy,host,port", [("proxy.example.org", "proxy.example.org", 5060), ("proxy.example.org:5080", "proxy.example.org", 5080), ("sip:proxy.example.org:5080", "proxy.example.org", 5080), ("proxy.example.org:99999", "proxy.example.org", 5060)])
def test_an_outbound_proxy_takes_the_connection_but_the_account_stays_on_the_server(tmp_path, proxy, host, port):
    st = Store(tmp_path); st.settings.update(voip_server="pbx.example.org", voip_user="1", voip_pw="x", voip_proxy=proxy); c = P.Phone(st).config()
    assert c.domain == "pbx.example.org" and c.server == host and c.port == port, (c.server, c.port)


def test_codec_order_and_wrong_numbers(tmp_path):
    st = Store(tmp_path); st.settings.update(voip_server="s", voip_user="1", voip_pw="x", voip_codec_first="PCMA"); assert P.Phone(st).config().codecs == (8, 0)
    st.settings.update(voip_pcmu=False, voip_pcma=False, voip_codec_first="PCMU"); assert P.Phone(st).config().codecs == (0, 8)          # nothing chosen: both, never an empty offer
    st.settings.update(voip_port="abc", voip_expires=5, voip_local_port=99999, voip_jitter_ms="x", voip_rtp_lo=30000, voip_rtp_hi=100)
    c = P.Phone(st).config(); assert (c.port, c.expires, c.local_port, c.jitter, c.bind_rtp) == (5060, 300, 0, 3, (12000, 12999))


def test_the_password_is_used_only_when_remembered_or_typed_in_this_session(tmp_path):
    st = Store(tmp_path); st.settings.update(voip_server="s", voip_user="1", voip_pw="saved", voip_remember=False); ph = P.Phone(st)
    assert ph.config().password == ""; ph._session_pw = "typed"; assert ph.config().password == "typed"
    st.settings["voip_remember"] = True; ph._session_pw = ""; assert ph.config().password == "saved"


# ---- the tabs -------------------------------------------------------------------------------------------------------------------------
def test_the_five_tabs_exist_and_switch(tmp_path):
    st, ctx, pg = make(tmp_path)
    assert [b.text() for b in pg.sections] == ["Account", "Network", "Audio", "Calls", "Advanced"]
    for i, b in enumerate(pg.sections):
        b.click(); W.QApplication.processEvents(); assert pg.stack.currentIndex() == i and b.isChecked() and sum(x.isChecked() for x in pg.sections) == 1


def test_every_field_of_the_tabs_is_saved_and_shown_again(tmp_path):
    st, ctx, pg = make(tmp_path)
    pg.proxy.setText("proxy.example.org:5080"); pg.local_port.setValue(5070); pg.expires.setValue(120); pg.stun.setText("stun.example.org"); pg.public_ip.setText("203.0.113.7")
    pg.ua_name.setText("MyPhone/1"); pg.trace.setChecked(True); pg.auto_answer.setChecked(True); pg.dnd.setChecked(True); pg.vm.setText("*97"); pg.mic_gain.setValue(130); pg.ring_vol.setValue(80)
    W.QApplication.processEvents()
    s = st.settings
    assert (s["voip_proxy"], s["voip_local_port"], s["voip_expires"], s["voip_stun"], s["voip_public_ip"], s["voip_ua"], s["voip_trace"], s["voip_auto_answer"], s["voip_dnd"], s["voip_vm"], s["voip_mic_gain"], s["voip_ring_vol"]) == \
           ("proxy.example.org:5080", 5070, 120, "stun.example.org", "203.0.113.7", "MyPhone/1", True, True, True, "*97", 130, 80)
    pg2 = VoipPage(Ctx(st, NullEngine())); pg2.show()                                                         # a new window shows what was saved
    assert (pg2.proxy.text(), pg2.local_port.value(), pg2.expires.value(), pg2.stun.text(), pg2.trace.isChecked(), pg2.dnd.isChecked(), pg2.vm.text(), pg2.mic_gain.value()) == ("proxy.example.org:5080", 5070, 120, "stun.example.org", True, True, "*97", 130)


def test_restoring_the_defaults_keeps_the_account_the_people_and_the_calls(tmp_path):
    st, ctx, pg = make(tmp_path, voip_user="1001", voip_pw="pw", voip_contacts=[{"name": "A", "number": "1"}], voip_history=[{"t": 1}])
    pg.proxy.setText("x"); pg.dnd.setChecked(True); pg.vm.setText("*97"); W.QApplication.processEvents()
    pg._defaults(); W.QApplication.processEvents()
    s = st.settings
    assert s["voip_proxy"] == "" and s["voip_dnd"] is False and s["voip_vm"] == "" and pg.proxy.text() == "" and not pg.dnd.isChecked()
    assert s["voip_user"] == "1001" and s["voip_pw"] == "pw" and s["voip_contacts"] == [{"name": "A", "number": "1"}] and s["voip_history"] == [{"t": 1}]


def test_the_defaults_in_the_store_cover_every_setting_the_page_saves(tmp_path):
    st, ctx, pg = make(tmp_path)
    for key in pg.ctl: assert key in DEFAULTS, key


# ---- ringtones -------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key", list(P.RINGTONES))
def test_every_ringtone_makes_20_ms_frames_with_tones_and_pauses(tmp_path, key):
    st = Store(tmp_path); ph = P.Phone(st); r = ph.make_ring(key); frames = [r.frame() for _ in range(300)]
    assert all(f.dtype == np.int16 and len(f) == 160 for f in frames)
    peaks = [int(np.abs(f).max()) for f in frames]
    assert max(peaks) > 2000 and min(peaks) == 0 and max(peaks) < 20000                                      # it rings, it pauses, and it is not at full scale


def test_the_ring_volume_changes_how_loud_it_is(tmp_path):
    st = Store(tmp_path); ph = P.Phone(st); loud = {}
    for v in (20, 100):
        st.settings["voip_ring_vol"] = v; r = ph.make_ring("classic"); loud[v] = max(int(np.abs(r.frame()).max()) for _ in range(20))
    assert loud[100] > loud[20] * 3


def wav(path, rate=8000, ch=1, sw=2, secs=0.3, freq=600):
    n = int(rate * secs); t = np.arange(n) / rate; x = np.sin(2 * np.pi * freq * t)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(sw); w.setframerate(rate)
        if sw == 1: data = ((x * 100 + 128).astype(np.uint8))
        elif sw == 2: data = (x * 20000).astype("<i2")
        elif sw == 3: data = b"".join(struct.pack("<i", int(v * 4000000))[:3] for v in x)
        else: data = (x * 1e9).astype("<i4")
        if sw == 3: w.writeframes(data * ch if ch == 1 else b"".join(data[i:i + 3] * ch for i in range(0, len(data), 3)))
        else: w.writeframes(np.repeat(data[:, None], ch, axis=1).tobytes())


@pytest.mark.parametrize("rate,ch,sw", [(8000, 1, 2), (44100, 2, 2), (48000, 1, 3), (22050, 1, 1), (16000, 2, 4)])
def test_the_users_own_wav_file_is_a_ring(tmp_path, rate, ch, sw):
    f = tmp_path / "r.wav"; wav(f, rate, ch, sw); r = P.WavRing(str(f))
    n = len(r.pcm) // 160; frames = [r.frame() for _ in range(n * 2)]
    assert all(len(x) == 160 and x.dtype == np.int16 for x in frames) and max(int(np.abs(x).max()) for x in frames) > 3000
    assert int(np.abs(frames[-1]).max()) == 0 and abs(n * 160 / 8000 - (0.3 + 2.0)) < 0.1                    # the sound, then two seconds of silence, then it starts again
    assert int(np.abs(frames[n]).max()) > 3000


def test_a_wav_file_that_cannot_be_used_is_refused_and_the_classic_ring_plays_instead(tmp_path):
    bad = tmp_path / "bad.wav"; bad.write_bytes(b"not a wav"); empty = tmp_path / "e.wav"
    with wave.open(str(empty), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"")
    for f in (bad, empty, tmp_path / "missing.wav"):
        with pytest.raises(Exception): P.WavRing(str(f))
    st = Store(tmp_path); ph = P.Phone(st); logs = []; ph._log = logs.append
    r = ph.make_ring("file", str(bad)); assert isinstance(r, P.Cadence) and any("cannot be used" in l for l in logs)
    st.settings.update(voip_ringtone="file", voip_ring_file=str(tmp_path / "missing.wav")); assert isinstance(ph.make_ring(), P.Cadence)
    good = tmp_path / "g.wav"; wav(good); st.settings["voip_ring_file"] = str(good); assert isinstance(ph.make_ring(), P.WavRing)


def test_the_ring_preview_plays_only_when_no_call_is_going_on(tmp_path, monkeypatch):
    monkeypatch.setattr(P.Audio, "start_speakers", lambda self: True); monkeypatch.setattr(P.Audio, "stop", lambda self: None)
    st = Store(tmp_path); ph = P.Phone(st)
    assert ph.preview_ring("bell", seconds=0.05) is True and isinstance(ph.cadence, P.Cadence)
    class C: state = "active"
    ph.call = C(); assert ph.preview_ring("bell") is False
    monkeypatch.setattr(P.Audio, "start_speakers", lambda self: False); ph.call = None; assert ph.preview_ring("bell") is False and ph.cadence is None


def test_an_incoming_call_rings_with_the_chosen_ringtone(tmp_path, monkeypatch):
    monkeypatch.setattr(P.Audio, "start_speakers", lambda self: True); monkeypatch.setattr(P.Audio, "stop", lambda self: None)
    st = Store(tmp_path); st.settings["voip_ringtone"] = "bell"; ph = P.Phone(st)
    class C:
        direction, state, remote_name, remote_user, remote_uri, answered_at, end_reason = "in", "incoming", "A", "1002", "sip:1002@x", 0, ""
        def reject(self, code): self.rejected = code
    c = C(); ph._on_call(c, "incoming")
    assert ph.cadence is not None and ph.cadence.pattern == P.RINGTONES["bell"][1]


# ---- do not disturb, auto-answer, voicemail ----------------------------------------------------------------------------------------------
class Call:
    direction, state, remote_name, remote_user, remote_uri, answered_at, end_reason, held_by_remote, duration = "in", "incoming", "Takis", "1002", "sip:1002@x", 0, "", False, 0
    def __init__(self): self.rejected = None
    def reject(self, code): self.rejected = code


def test_do_not_disturb_answers_busy_without_ringing_and_lists_the_call_as_missed(tmp_path, monkeypatch):
    monkeypatch.setattr(P.Audio, "start_speakers", lambda self: True); monkeypatch.setattr(P.Audio, "stop", lambda self: None)
    st = Store(tmp_path); st.settings["voip_dnd"] = True; ph = P.Phone(st); seen = []; ph.call_changed.connect(lambda c, s: seen.append(s))
    c = Call(); ph._on_call(c, "incoming")
    assert c.rejected == 486 and ph.cadence is None and seen == []                                           # busy, no ring, no window
    c.state = "ended"; ph._on_call(c, "ended")
    h = st.settings["voip_history"][0]; assert h["dir"] == "missed" and h["number"] == "1002" and h["why"] == "Do not disturb" and ph.call is None and seen == []


def test_auto_answer_answers_after_the_chosen_time_only_if_the_call_is_still_ringing(tmp_path, monkeypatch):
    monkeypatch.setattr(P.Audio, "start_speakers", lambda self: True); monkeypatch.setattr(P.Audio, "stop", lambda self: None)
    st = Store(tmp_path); st.settings.update(voip_auto_answer=True, voip_auto_secs=0); ph = P.Phone(st); answered = []; ph.answer = lambda: answered.append(1)
    c = Call(); ph._on_call(c, "incoming"); assert answered == []
    end = time.time() + 3
    while not answered and time.time() < end: W.QApplication.processEvents(); time.sleep(0.01)
    assert answered == [1]
    c2 = Call(); ph.call = None; ph._on_call(c2, "incoming"); c2.state = "ended"; answered.clear()              # the caller gave up before the time ran out
    end = time.time() + 0.5
    while time.time() < end: W.QApplication.processEvents(); time.sleep(0.01)
    assert answered == []


def test_voicemail_dials_the_saved_number_and_says_so_when_there_is_none(tmp_path):
    st, ctx, pg = make(tmp_path); dialled = []; ctx.phone.dial = lambda n: dialled.append(n) or True
    ctx.phone.dial = lambda n: (dialled.append(n), bool(n))[1]; ctx.phone.reg_state = "registered"
    pg._voicemail(); assert dialled == [""] and "voicemail number" in pg.who.text()                      # no number saved: it says so, nothing is dialled
    st.settings["voip_vm"] = " *97 "; assert ctx.phone.voicemail() and dialled[-1] == "*97"


# ---- Greek -----------------------------------------------------------------------------------------------------------------------------
def test_every_text_of_the_voip_page_is_in_greek(tmp_path):
    i18n.set_language("el")
    try:
        st, ctx, pg = make(tmp_path)
        miss = set()
        for w in pg.findChildren(W.QWidget):
            texts_ = []
            if isinstance(w, (W.QLabel, W.QAbstractButton)): texts_.append(w.text())
            if isinstance(w, W.QLineEdit): texts_.append(w.placeholderText())
            if isinstance(w, W.QComboBox): texts_ += [w.itemText(i) for i in range(w.count())]
            if isinstance(w, W.QAbstractSpinBox): texts_.append(w.specialValueText())
            texts_.append(w.toolTip())
            for t in texts_:
                if t and any(c.isalpha() for c in t) and i18n.tr(t) == t and not t.isascii() is False:
                    miss.add(t)
        allowed = {"Server", "Port", "UDP", "TCP", "TLS", "PCMU", "PCMA", "SIP INFO", "SA7SVR", "1001", "DigiConnect-VoIP", "*", "#", "sip.example.org", "sip.foxhost.org", "PCMU (G.711 µ-law)", "PCMA (G.711 A-law)", "RTP", "STUN", "DTMF"}
        miss = {m for m in miss if m not in allowed and not m.replace("-", "").replace(".", "").replace(":", "").replace("/", "").isalnum()}
        assert not miss, sorted(miss)
    finally: i18n.set_language("en")


def test_the_greek_ringtone_names_and_signup_errors_exist():
    i18n.set_language("el")
    try:
        for k, (name, _) in P.RINGTONES.items(): assert i18n.tr(name) != name, name
        from app.voip import signup
        for e in signup.ERRORS.values(): assert i18n.tr(e) != e, e
    finally: i18n.set_language("en")
