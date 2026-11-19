"""The VoIP phone against a small SIP registrar / proxy written for the test (UDP on the loopback address): sign in with digest, wrong password, calls both ways,
audio frames, keypad digits, reject, cancel, hang up, unknown number, sign out - and the Qt Phone object on top (signals, call list). The proxy is deliberately
strict about what it checks (digest response, Via handling) and knows nothing about our code except the digest function, which has its own RFC test."""
import socket, threading, time, secrets
import numpy as np, pytest
from app.voip import sipmsg as S, ua as U


def wait(cond, t=6.0):
    t0 = time.time()
    while time.time() - t0 < t:
        if cond(): return True
        time.sleep(0.02)
    return cond()


class FakePbx(threading.Thread):
    realm = "fakepbx"

    def __init__(self, users):
        super().__init__(daemon=True); self.users = users; self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.sock.bind(("127.0.0.1", 0)); self.sock.settimeout(0.1)
        self.port = self.sock.getsockname()[1]; self.regs = {}; self.invite_to = {}; self.log = []; self.stop_flag = False; self.nonces = set(); self.start()

    def stop(self): self.stop_flag = True; self.join(2); self.sock.close()

    def send(self, m, addr): self.sock.sendto(m.to_bytes(), addr)

    def reply(self, req, code, reason, addr, extra=()):
        r = S.Message(status=code, reason=reason)
        for h in ("via", "from", "call-id", "cseq"):
            for v in req.all(h): r.add(S.nice(h), v)
        to = req.get("to"); r.add("To", to if "tag=" in to or code == 100 else to + ";tag=" + S.new_tag())
        for k, v in extra: r.add(k, v)
        r.add("Content-Length", "0"); self.send(r, addr)

    def run(self):
        while not self.stop_flag:
            try: data, addr = self.sock.recvfrom(65535)
            except (socket.timeout, OSError): continue
            m = S.parse(data)
            if not m: continue
            self.log.append((m.method or m.status, m.get("cseq")))
            try: self.handle(m, addr)
            except Exception as ex: self.log.append(("ERROR", repr(ex)))

    def handle(self, m, addr):
        if not m.is_request:                                   # a response from a callee: take our Via off and send it on to the next Via
            vias = [i for i, (k, _) in enumerate(m.headers) if k == "Via"]; del m.headers[vias[0]]
            nxt = m.get("via"); host, _, port = nxt.split()[1].split(";")[0].partition(":"); self.send(m, (host, int(port or 5060))); return
        if m.method == "REGISTER": return self.register(m, addr)
        user = S.uri_parts(m.uri).get("user", "")
        parts = S.uri_parts(m.uri); target = (parts.get("host"), int(parts.get("port") or 5060))
        if m.method in ("BYE", "INFO", "UPDATE") and any(d == target for d, _ in self.regs.values()):          # in-dialog request: the Request-URI is the other side's registered contact
            self.forward(m, target, m.uri); return
        if m.method in ("ACK", "CANCEL") and m.call_id in self.invite_to:
            self.forward(m, self.invite_to[m.call_id], m.uri)
            if m.method == "CANCEL": self.reply(m, 200, "OK", addr)
            return
        if m.method == "INVITE":
            if user not in self.regs: self.reply(m, 404, "Not Found", addr); return
            self.reply(m, 100, "Trying", addr); dest, contact = self.regs[user]; self.invite_to[m.call_id] = dest; self.forward(m, dest, contact); return
        if m.method in ("OPTIONS", "SUBSCRIBE", "NOTIFY"): self.reply(m, 405 if m.method == "SUBSCRIBE" else 200, "Method Not Allowed" if m.method == "SUBSCRIBE" else "OK", addr); return
        self.reply(m, 501, "Not Implemented", addr)

    def forward(self, m, dest, ruri):
        m.uri = ruri; m.headers.insert(0, ("Via", f"SIP/2.0/UDP 127.0.0.1:{self.port};branch={S.new_branch()}")); self.send(m, dest)

    def register(self, m, addr):
        ext = S.uri_parts(m.get("to") and S.uri_of(m.get("to"))).get("user", ""); auth = m.get("authorization")
        if not auth:
            nonce = secrets.token_hex(8); self.nonces.add(nonce)
            self.reply(m, 401, "Unauthorized", addr, [("WWW-Authenticate", f'Digest realm="{self.realm}", nonce="{nonce}", algorithm=MD5, qop="auth"')]); return
        a = S.parse_challenge(auth)
        ch = {"realm": self.realm, "nonce": a.get("nonce", ""), "algorithm": "MD5", "qop": "auth"}
        want = S.digest_response(ch, ext, self.users.get(ext, "\0"), "REGISTER", a.get("uri", ""), nc=int(a.get("nc", "1"), 16), cnonce=a.get("cnonce", ""))
        ok = a.get("nonce") in self.nonces and ext in self.users and S.parse_challenge(want)["response"] == a.get("response") and a.get("username") == ext
        if not ok: self.reply(m, 403, "Forbidden", addr); return
        contact = S.uri_of(m.get("contact")); exp = m.get("expires") or "300"
        host, port = S.uri_parts(contact).get("host"), S.uri_parts(contact).get("port") or 5060
        if exp == "0": self.regs.pop(ext, None)
        else: self.regs[ext] = ((host, int(port)), contact)
        self.reply(m, 200, "OK", addr, [("Contact", m.get("contact")), ("Expires", exp)])


@pytest.fixture
def pbx():
    p = FakePbx({"1001": "secret1", "1002": "secret2"}); yield p; p.stop()


def agent(pbx, user, pw=None, **kw):
    ev, logs = [], []
    cfg = U.Config(server="127.0.0.1", port=pbx.port, user=user, password=pw if pw is not None else {"1001": "secret1", "1002": "secret2"}.get(user, "x"), domain="127.0.0.1", bind_rtp=(14000, 14999), **kw)
    a = U.UserAgent(cfg, lambda n, **k: ev.append((n, k)), logs.append); a.ev, a.logs = ev, logs; a.start(); return a


def test_sign_in_with_digest_and_sign_out(pbx):
    a = agent(pbx, "1001")
    try:
        assert wait(lambda: a.reg_state == "registered") and a.reg_text == "Registered as 1001@127.0.0.1" and "1001" in pbx.regs
        assert [m for m in pbx.log if m[0] == "REGISTER"][:2] == [("REGISTER", "1 REGISTER"), ("REGISTER", "2 REGISTER")]       # one challenge, one answer
    finally: a.stop(2.0)
    assert wait(lambda: "1001" not in pbx.regs)                                                                          # leaving tells the server (Expires: 0)
    assert not [e for e in pbx.log if e[0] == "ERROR"], pbx.log


def test_a_wrong_password_is_reported_once_and_never_repeated(pbx):
    a = agent(pbx, "1001", pw="wrong")
    try:
        assert wait(lambda: a.reg_state == "failed") and a.reg_text.startswith("Wrong username or password") or a.reg_text.startswith("The server refused")
        n = len([m for m in pbx.log if m[0] == "REGISTER"]); time.sleep(1.5)
        assert len([m for m in pbx.log if m[0] == "REGISTER"]) == n and n == 2 and "1001" not in pbx.regs                    # a PBX with fail2ban would ban a client that keeps trying
    finally: a.stop(1.0)


def test_nobody_is_listening_on_the_server_port(pbx):
    port = pbx.port; pbx.stop(); ev = []
    cfg = U.Config(server="127.0.0.1", port=port, user="1001", password="x", domain="127.0.0.1"); a = U.UserAgent(cfg, lambda n, **k: ev.append((n, k)), lambda t: None); a.start()
    try: assert wait(lambda: a.reg_state in ("failed",) or any(e[0] == "registration" and e[1]["state"] == "failed" for e in ev), 12)
    finally: a.stop(0.5)


@pytest.fixture
def pair(pbx):
    a, b = agent(pbx, "1001"), agent(pbx, "1002"); inc = []
    b.on_event = lambda n, **k: (b.ev.append((n, k)), inc.append(k["call"]) if n == "call" and k["state"] == "incoming" else None)
    assert wait(lambda: a.reg_state == "registered" and b.reg_state == "registered")
    yield a, b, inc
    a.stop(1.0); b.stop(1.0)


def tone(f): return (np.sin(2 * np.pi * f * np.arange(8000) / 8000) * 8000).astype(np.int16)


def peak(chunks):
    seg = np.concatenate(chunks)[-6400:].astype(float); sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); return round(np.argmax(sp) * 8000 / len(seg))


def test_a_call_with_sound_both_ways_keypad_and_hang_up(pair):
    a, b, inc = pair; digits = []
    a.on_event = lambda n, **k: (a.ev.append((n, k)), digits.append(k["digit"]) if n == "dtmf" else None)
    c = a.call("1002")
    assert wait(lambda: inc) and inc[0].remote_user == "1001" and wait(lambda: c.state == "ringing")
    ic = inc[0]; ic.answer()
    assert wait(lambda: c.state == "active" and ic.state == "active")
    t1, t2 = tone(600), tone(900); g1, g2 = [], []
    for i in range(110):
        k = (i * 160) % 8000; c.media.send_frame(t1[k:k + 160]); ic.media.send_frame(t2[k:k + 160]); time.sleep(0.02); g1.append(ic.media.jitter.pull()); g2.append(c.media.jitter.pull())
    assert abs(peak(g1) - 600) < 10 and abs(peak(g2) - 900) < 10                                                         # each side hears the other's tone, not its own
    ic.send_dtmf("5"); ic.send_dtmf("#")
    assert wait(lambda: digits == ["5", "#"], 4), digits
    c.hangup()
    assert wait(lambda: ic.state == "ended" and c.state == "ended") and ic.end_reason == "The other side hung up" and c.end_reason == "Hung up"
    assert not [e for e in b.ev if e[0] == "call" and e[1]["state"] == "ended"][1:]                                      # one end, not two


def test_reject_cancel_and_unknown_number(pair):
    a, b, inc = pair
    c = a.call("1002"); assert wait(lambda: inc); inc[0].reject(603)
    assert wait(lambda: c.state == "ended") and c.end_reason.startswith("Declined")
    inc.clear(); c = a.call("1002"); assert wait(lambda: inc and c.state == "ringing"); c.hangup()
    assert wait(lambda: c.state == "ended" and inc[0].state == "ended") and c.end_reason == "Cancelled" and inc[0].end_reason in ("Missed", "Missed call", "Cancelled")
    c = a.call("999"); assert wait(lambda: c.state == "ended") and c.end_reason.startswith("No such number (404")
    c = a.call("1002"); assert wait(lambda: len(inc) == 2)                                                              # a new call still works after all of that
    inc[-1].answer(); assert wait(lambda: c.state == "active"); c.hangup(); assert wait(lambda: c.state == "ended")


def test_a_call_cannot_start_before_signing_in(pbx):
    a = agent(pbx, "1001", pw="wrong")
    try:
        assert wait(lambda: a.reg_state == "failed"); c = a.call("1002")
        assert wait(lambda: c.state == "ended") and c.end_reason == "Not signed in to the server"
    finally: a.stop(0.5)


# ---------------- the Qt Phone on top of it
class FakeAudio:
    def __init__(self, on_mic, get_speaker, mic="", spk=""): self.get_speaker, self.muted, self.mic_level, self.spk_level, self.mic_used, self.spk_used, self.error = get_speaker, False, 0.0, 0.0, "Fake mic", "Fake speakers", ""; self.started = []
    def start_speakers(self): self.started.append("spk"); return True
    def start_mic(self): self.started.append("mic"); return True
    def stop(self): self.started.append("stop")


def spin(cond, t=6.0):
    from app.qt import QtWidgets as W
    t0 = time.time()
    while time.time() - t0 < t:
        W.QApplication.processEvents()
        if cond(): return True
        time.sleep(0.01)
    return cond()


def test_the_phone_object_signs_in_rings_answers_remembers_and_signs_out(pbx, tmp_path, monkeypatch):
    from app.store import Store
    from app.voip import phone as P
    monkeypatch.setattr(P, "Audio", FakeAudio)
    st = Store(tmp_path); st.settings.update(voip_server="127.0.0.1", voip_port=pbx.port, voip_user="1001", voip_remember=True, voip_name="Pit")
    ph = P.Phone(st); regs, calls = [], []
    ph.registration.connect(lambda s, t: regs.append(s)); ph.call_changed.connect(lambda c, s: calls.append(s))
    assert ph.sign_in("secret1") is True
    other = agent(pbx, "1002"); inc = []
    other.on_event = lambda n, **k: (other.ev.append((n, k)), inc.append(k["call"]) if n == "call" and k["state"] == "incoming" else None)
    try:
        assert spin(lambda: ph.reg_state == "registered") and "registering" in regs and regs[-1] == "registered" and wait(lambda: other.reg_state == "registered")
        assert ph.dial("1002") and spin(lambda: inc and "ringing" in calls)
        assert ph.cadence is not None and ph.audio.started == ["spk"]                                                    # the ring-back tone plays while the other side rings
        inc[0].answer(); assert spin(lambda: ph.call.state == "active") and ph.cadence is None and ph.audio.started[:3] == ["spk", "spk", "mic"]
        ph.set_muted(True); assert ph.audio.muted
        ph.hangup(); assert spin(lambda: calls[-1] == "ended") and ph.audio is None
        h = st.settings["voip_history"]; assert len(h) == 1 and h[0]["dir"] == "placed" and h[0]["number"] == "1002" and h[0]["secs"] >= 0
        # an incoming call that nobody answers is a missed call in the list
        c2 = other.call("1001"); assert spin(lambda: ph.call is not None and ph.call.state == "incoming") and ph.cadence is not None
        c2.hangup(); assert spin(lambda: ph.call.state == "ended"); h = st.settings["voip_history"]
        assert h[0]["dir"] == "missed" and h[0]["number"] == "1002" and len(h) == 2
        assert ph.state_of("1002")[0] in ("unknown", "free", "available")                                                  # this proxy sends no notifications: nothing is invented
    finally:
        ph.sign_out(1.0); other.stop(1.0)
    assert ph.reg_state == "unregistered" and wait(lambda: "1001" not in pbx.regs)


def test_the_phone_does_not_sign_in_without_server_user_or_password(tmp_path):
    from app.store import Store
    from app.voip import phone as P
    st = Store(tmp_path); ph = P.Phone(st); st.settings.update(voip_server="", voip_user="")
    assert ph.sign_in("x") is False and ph.reg_state == "failed" and ph.reg_text == "Enter the server and your username first"
    st.settings.update(voip_server="127.0.0.1", voip_user="1001", voip_remember=False); assert ph.sign_in("") is False and ph.reg_text == "Enter your password"
    assert ph.dial("1002") is False
