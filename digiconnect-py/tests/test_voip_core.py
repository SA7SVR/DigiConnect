"""VoIP phone, parts that need no network and no sound card: SIP messages and digest, SDP, G.711, RTP and the jitter buffer, resampling, presence,
who-is-available words, the rings, the Greek texts, and the phone page. Known values come from the RFCs / ITU tables, not from our own code."""
import hashlib, struct
import numpy as np, pytest
from app.voip import sipmsg as S, sdp, g711, rtp, ua as U
from app.voip.audio import Resampler, match_device
from app.voip.phone import combine, Cadence, RING_IN, RING_OUT, STATE_TEXT
from app.voip import texts
from app import i18n


# ---------------- SIP messages and digest
def test_digest_matches_the_rfc2617_example():
    ch = S.parse_challenge('Digest realm="testrealm@host.com", qop="auth,auth-int", nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", opaque="5ccc069c403ebaf9f0171e9517f40e41"')
    h = S.digest_response(ch, "Mufasa", "Circle Of Life", "GET", "/dir/index.html", nc=1, cnonce="0a4f113b")
    assert 'response="6629fae49393a05397450978507c4ef1"' in h and "qop=auth" in h and "nc=00000001" in h and 'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in h


def test_digest_without_qop_and_sha256_are_computed_by_the_rules():
    ch = {"realm": "r", "nonce": "n"}
    md = lambda s: hashlib.md5(s.encode()).hexdigest()
    want = md(f"{md('u:r:p')}:n:{md('REGISTER:sip:x')}")
    assert f'response="{want}"' in S.digest_response(ch, "u", "p", "REGISTER", "sip:x")
    ch = {"realm": "r", "nonce": "n", "qop": "auth", "algorithm": "SHA-256"}
    sh = lambda s: hashlib.sha256(s.encode()).hexdigest()
    want = sh(f"{sh('u:r:p')}:n:00000001:cc:auth:{sh('REGISTER:sip:x')}")
    assert f'response="{want}"' in S.digest_response(ch, "u", "p", "REGISTER", "sip:x", cnonce="cc") and S.supported(ch) and not S.supported({"realm": "r", "algorithm": "SHA-512-256x"})


def test_message_roundtrip_compact_headers_and_folding():
    raw = (b"INVITE sip:1002@example.org SIP/2.0\r\nv: SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK1\r\nf: \"Pit\" <sip:1001@example.org>;tag=a1\r\nt: <sip:1002@example.org>\r\n"
           b"i: abc@host\r\nCSeq: 7 INVITE\r\nm: <sip:1001@10.0.0.1:5060>\r\nSubject: one\r\n two\r\nl: 4\r\n\r\nbody")
    m = S.parse(raw)
    assert m.method == "INVITE" and m.uri == "sip:1002@example.org" and m.call_id == "abc@host" and m.cseq == (7, "INVITE") and m.tag("from") == "a1" and m.get("subject") == "one two"
    assert m.body == b"body" and S.display_name(m.get("from")) == "Pit" and S.uri_of(m.get("contact")) == "sip:1001@10.0.0.1:5060"
    again = S.parse(m.to_bytes()); assert again.call_id == "abc@host" and again.body == b"body" and again.get("content-length") == "4"
    assert S.parse(b"garbage") is None and S.parse(b"\r\n\r\n") is None
    r = S.parse(b"SIP/2.0 486 Busy Here\r\nCSeq: 1 INVITE\r\n\r\n"); assert (r.status, r.reason, r.is_request) == (486, "Busy Here", False)


def test_tcp_framing_waits_for_the_whole_message_and_skips_keepalives():
    msg = b"OPTIONS sip:x SIP/2.0\r\nContent-Length: 5\r\n\r\nhello"
    assert S.frame_length(msg) == len(msg) and S.frame_length(msg[:-1]) == 0 and S.frame_length(msg[:20]) == 0
    assert S.frame_length(b"\r\n\r\n" + msg) == -4 and S.frame_length(b"x" * 10) == 0


def test_failure_words_carry_the_code_and_are_not_invented():
    assert U.fail_text(486, "Busy Here") == "Busy (486 Busy Here)" and U.fail_text(486) == "Busy (486)" and U.fail_text(486, "busy") == "Busy (486)"
    assert U.fail_text(401, "Unauthorized").startswith("Wrong username or password (401")
    assert U.fail_text(418, "I'm a teapot") == "Refused (418 I'm a teapot)" and U.fail_text(302, "x").startswith("Failed")


# ---------------- SDP
def test_sdp_offer_and_answer_are_read_back():
    body = sdp.build("192.0.2.5", 12345)
    r = sdp.parse(body)
    assert (r.ip, r.port, r.codecs, r.event_pt) == ("192.0.2.5", 12345, [0, 8], 101) and not r.on_hold and sdp.choose(r) == 0
    ans = sdp.parse(sdp.build("192.0.2.5", 12346, only=[8])); assert ans.codecs == [8] and sdp.choose(ans) == 8


def test_sdp_from_a_pbx_hold_and_no_common_codec():
    pbx = (b"v=0\r\no=- 1 1 IN IP4 198.51.100.7\r\ns=-\r\nc=IN IP4 198.51.100.7\r\nt=0 0\r\nm=audio 20000 RTP/AVP 9 8 0 101\r\n"
           b"a=rtpmap:9 G722/8000\r\na=rtpmap:8 PCMA/8000\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:101 telephone-event/8000\r\na=sendrecv\r\n")
    r = sdp.parse(pbx); assert r.ip == "198.51.100.7" and r.port == 20000 and sdp.choose(r) == 0 and r.event_pt == 101                   # G.722 is offered by the PBX but we use G.711
    only722 = sdp.parse(pbx.replace(b"9 8 0 101", b"9 101").replace(b"a=rtpmap:8 PCMA/8000\r\n", b"").replace(b"a=rtpmap:0 PCMU/8000\r\n", b""))
    assert only722.codecs == [] and sdp.choose(only722) == -1                                                                          # only G.722: no common codec, the call is refused honestly
    held = sdp.parse(pbx.replace(b"sendrecv", b"sendonly")); assert held.on_hold
    assert sdp.parse(pbx.replace(b"c=IN IP4 198.51.100.7", b"c=IN IP4 0.0.0.0")).on_hold


# ---------------- G.711
def test_g711_known_code_words():
    # ITU-T G.711: u-law 0xFF = 0, 0x7F = -0, 0x80 = +32124, 0x00 = -32124 ; A-law 0xD5 = +8, 0x55 = -8, 0xAA = +32256 (in 16-bit scale)
    d = g711.decode(bytes([0xFF, 0x7F, 0x80, 0x00]), 0); assert list(d) == [0, 0, 32124, -32124]
    a = g711.decode(bytes([0xD5, 0x55, 0xAA, 0x2A]), 8); assert list(a) == [8, -8, 32256, -32256]
    assert g711.ulaw_encode(np.array([0, 32124, -32124], np.int16)) == bytes([0xFF, 0x80, 0x00]) and g711.alaw_encode(np.array([8, -8], np.int16)) == bytes([0xD5, 0x55])


@pytest.mark.parametrize("pt", [0, 8])
def test_g711_roundtrip_error_is_small(pt):
    x = (np.sin(2 * np.pi * 440 * np.arange(8000) / 8000) * 12000).astype(np.int16)
    y = g711.decode(g711.encode(x, pt), pt).astype(np.int32)
    assert len(y) == len(x) and np.max(np.abs(y - x)) <= 400                                  # the quantising step at this level is at most 256


def test_g711_encode_decode_are_stable_for_every_code_word():
    for pt in (0, 8):
        every = bytes(range(256)); pcm = g711.decode(every, pt); back = g711.encode(pcm, pt)
        if pt == 8: assert back == every
        else: assert [i for i in range(256) if back[i] != every[i]] == [0x7F] and back[0x7F] == 0xFF               # u-law has two zeros (+0 and -0): -0 comes back as +0, everything else is exact


# ---------------- RTP
def test_rtp_packet_and_dtmf_event_layout():
    p = rtp.build_packet(0, 65535, 4294967200, 0xDEADBEEF, b"\x01\x02", marker=True)
    assert p[0] == 0x80 and p[1] == 0x80 and struct.unpack("!HII", p[2:12]) == (65535, 4294967200, 0xDEADBEEF)
    assert rtp.parse_packet(p) == (0, True, 65535, 4294967200, 0xDEADBEEF, b"\x01\x02")
    assert rtp.parse_packet(b"\x00" * 5) is None
    ev = rtp.dtmf_payload(5, True, 1280); assert ev == bytes([5, 0x80 | 10, 0x05, 0x00]) and rtp.parse_dtmf(ev) == (5, True, 1280)


def frame(v): return np.full(160, v, np.int16)


def test_jitter_buffer_orders_drops_duplicates_and_repeats_a_lost_frame():
    j = rtp.JitterBuffer(prefill=3)
    for s in (11, 10, 12, 12, 14): j.push(s, frame(s))                                        # out of order, a duplicate, and 13 missing
    got = [int(j.pull()[0]) for _ in range(5)]
    assert got == [10, 11, 12, 6, 14] and j.lost == 1 and j.received == 5                      # 13 is replaced by a faded copy of 12 (half the level), the duplicate is dropped
    assert not j.buf


def test_jitter_buffer_wraps_the_sequence_number_and_ignores_late_packets():
    j = rtp.JitterBuffer(prefill=2)
    for s in (65534, 65535, 0, 1): j.push(s, frame(s % 100 + 1))
    out = [int(j.pull()[0]) for _ in range(4)]
    assert out == [(65534 % 100) + 1, (65535 % 100) + 1, 1, 2]
    j.push(65534, frame(9)); assert j.late == 1


def test_jitter_buffer_plays_silence_while_waiting_and_after_the_stream_stops():
    j = rtp.JitterBuffer(prefill=3); assert not j.pull().any()
    j.push(1, frame(5)); assert not j.pull().any()                                            # still filling
    for s in (2, 3): j.push(s, frame(5))
    assert j.pull()[0] == 5
    for _ in range(40): j.pull()
    assert not j.pull().any() and j.underruns > 0


# ---------------- resampling and device names
@pytest.mark.parametrize("src,dst", [(8000, 48000), (48000, 8000), (8000, 44100), (44100, 8000), (16000, 8000)])
def test_resampler_keeps_the_tone_and_does_not_depend_on_block_size(src, dst):
    t = np.arange(src) / src; x = (np.sin(2 * np.pi * 500 * t) * 10000).astype(np.int16)
    whole = Resampler(src, dst).process(x)
    assert 0 <= dst - len(whole) <= 2 * dst // src + 3                                         # the last output samples need the next input sample, which has not come yet
    r = Resampler(src, dst); parts = []
    i = 0; sizes = [160, 137, 441, 1, 960, 313]; k = 0
    while i < len(x): n = sizes[k % len(sizes)]; parts.append(r.process(x[i:i + n])); i += n; k += 1
    cut = np.concatenate(parts); m = min(len(cut), len(whole))
    assert np.max(np.abs(cut[:m] - whole[:m])) < 1e-2
    seg = whole[len(whole) // 4: -len(whole) // 4].astype(float); sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); f = np.argmax(sp) * dst / len(seg)
    assert abs(f - 500) < 5 and 8000 < np.max(np.abs(seg)) < 11000


DEVS = [dict(name="Microsoft Sound Mapper - Input", max_input_channels=2, max_output_channels=0), dict(name="Microphone (USB Audio Device)", max_input_channels=1, max_output_channels=0),
        dict(name="Speakers (Realtek High Definition Audio)", max_input_channels=0, max_output_channels=2), dict(name="Headset Earphone (USB Audio Device)", max_input_channels=0, max_output_channels=2)]


def test_device_names_from_settings_are_matched_loosely_and_by_direction():
    assert match_device("Microphone (USB Audio Device)", DEVS, True) == 1 and match_device("Speakers (Realtek High Definition Audio)", DEVS, False) == 2
    assert match_device("Speakers (Realtek(R) Audio)", DEVS, False) == 2 and match_device("Headset Earphone", DEVS, False) == 3
    assert match_device("Microphone (USB Audio Device)", DEVS, False) is None and match_device("", DEVS, True) is None and match_device("Default", DEVS, False) is None
    assert match_device("Totally unknown card", DEVS, False) is None


# ---------------- presence and the words about a person
def dlg(*states, direction="receiver"):
    ds = "".join(f'<dialog id="{i}"><state>{s}</state></dialog>' for i, s in enumerate(states))
    return f'<?xml version="1.0"?><dialog-info xmlns="urn:ietf:params:xml:ns:dialog-info" version="1" state="full" entity="sip:1002@x">{ds}</dialog-info>'


def test_dialog_and_pidf_notifications_are_read_as_the_standards_say():
    assert U.parse_presence(dlg(), "dialog")[0] == "free" and U.parse_presence(dlg("terminated"), "dialog")[0] == "free"
    assert U.parse_presence(dlg("early"), "dialog")[0] == "ringing" and U.parse_presence(dlg("confirmed"), "dialog")[0] == "busy"
    assert U.parse_presence(dlg("terminated", "confirmed"), "dialog")[0] == "busy" and U.parse_presence("", "dialog")[0] == "unknown"
    pidf = lambda b, n="": f'<presence xmlns="urn:ietf:params:xml:ns:pidf"><tuple id="a"><status><basic>{b}</basic></status>{n}</tuple></presence>'
    assert U.parse_presence(pidf("open"), "presence", "application/pidf+xml")[0] == "online" and U.parse_presence(pidf("closed"), "presence", "application/pidf+xml")[0] == "offline"
    assert U.parse_presence(pidf("open", "<note>Ready</note>"), "presence", "application/pidf+xml") == ("online", "Ready")
    assert U.parse_presence("hello", "presence")[0] == "unknown"


def test_a_person_is_only_called_available_when_the_server_said_so():
    assert combine(None, None)[0] == "unknown"
    assert combine(("free", "no call"), None)[0] == "free"                                        # no call is NOT "available": the server did not say the person is signed in
    assert combine(("free", "no call"), ("online", ""))[0] == "available" and combine(("free", ""), ("offline", ""))[0] == "offline"
    assert combine(("busy", "on a call"), ("online", ""))[0] == "busy" and combine(("ringing", ""), None)[0] == "ringing"
    assert combine(("unknown", "404 Not Found"), None)[0] == "unknown" and combine(("unknown", "No such number (404)"), None)[0] == "nonumber"


# ---------------- rings
def test_the_rings_have_the_right_tones_and_rhythm():
    c = Cadence(RING_IN); f = [c.frame() for _ in range(3000 // 20)]
    on = [bool(np.abs(x).max() > 1000) for x in f]
    assert on[0] and on[19] and not on[20] and not on[29] and on[30] and on[49] and not on[50] and not on[149]          # 0.4 on, 0.2 off, 0.4 on, 2.0 off
    seg = np.concatenate(f[:19]).astype(float); sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); fr = np.fft.rfftfreq(len(seg), 1 / 8000)
    peaks = sorted(fr[np.argsort(sp)[-2:]]); assert 430 < peaks[0] < 450 and 470 < peaks[1] < 490
    assert Cadence(RING_OUT).frame().dtype == np.int16 and len(Cadence(RING_OUT).frame()) == 160


# ---------------- Greek
def test_every_state_and_failure_text_has_a_greek_translation():
    i18n.set_language("el")
    try:
        every = list(U.FAIL_TEXT.values()) + list(STATE_TEXT.values()) + ["Refused", "Failed", "Hung up", "Missed call", "Declined", "Cancelled", "The other side hung up", "Offline", "Available", "On a call", "Ringing",
                                                                      "No such number on the server", "Not signed in to the server", "Enter your password", "Incoming call from {}"]
        assert [s for s in every if i18n.tr(s) == s] == []
        assert texts.reason("Busy (486 Busy Here)") == "Κατειλημμένο (486 Busy Here)"
        assert texts.reason("Wrong username or password (401) - not trying again; check the username and password and press Sign in").startswith("Λάθος όνομα χρήστη ή κωδικός (401) - δεν ξαναδοκιμάζω")
        assert i18n.tr("Registered as 1001@sip.foxhost.org") == "Καταχωρήθηκε ως 1001@sip.foxhost.org"
        assert i18n.tr("Cannot reach the server sip.x:5060 (timed out)") == "Δεν βρίσκω τον server sip.x:5060 (timed out)"
    finally: i18n.set_language("en")
    assert texts.reason("Busy (486 Busy Here)") == "Busy (486 Busy Here)"
