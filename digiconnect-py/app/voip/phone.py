"""The telephone for the program: the SIP user agent, the sound cards, the rings, the contacts and the call list, as one Qt object.
The user agent works on its own thread; everything it reports is passed on here as Qt signals, so the screens only ever run on the Qt thread."""
import threading, time
import numpy as np
from ..qt import QtCore
from . import ua as U
from .audio import Audio, FRAME

Signal = QtCore.Signal


class Cadence:
    """A ring made of tones and pauses: [(frequencies, milliseconds), ...] repeated. frame() gives the next 20 ms."""

    def __init__(self, pattern, amp: float = 0.25):
        self.pattern, self.amp = pattern, amp; self.i = 0; self.left = pattern[0][1] // 20; self.t = 0

    def frame(self) -> np.ndarray:
        freqs, _ = self.pattern[self.i]
        n = np.arange(FRAME) + self.t
        out = np.zeros(FRAME, np.float32)
        for f in freqs: out += np.sin(2 * np.pi * f * n / 8000.0).astype(np.float32)
        if freqs: out *= self.amp / len(freqs)
        self.t += FRAME; self.left -= 1
        if self.left <= 0:
            self.i = (self.i + 1) % len(self.pattern); self.left = max(1, self.pattern[self.i][1] // 20); self.t = 0
        return (out * 32767).astype(np.int16)


RING_IN = [((440, 480), 400), ((), 200), ((440, 480), 400), ((), 2000)]            # the ring of an incoming call
RING_OUT = [((425,), 1000), ((), 4000)]                                              # the tone you hear while the other side rings (when the server sends none)

STATE_TEXT = {"calling": "Calling…", "ringing": "Ringing…", "incoming": "Incoming call", "connecting": "Connecting…", "active": "In a call", "held": "On hold", "ended": "Ended"}


def combine(dialog, presence) -> tuple[str, str]:
    """One state for a person from the two answers of the server: ('available' | 'ringing' | 'busy' | 'offline' | 'free' | 'nonumber' | 'unknown', words).
    dialog / presence are (state, text) or None. Nothing is guessed: 'free' means only that the server reports no call and does not say whether the person is signed in."""
    ds, dt = dialog or ("", ""); ps, pt = presence or ("", "")
    for st, tx in ((ds, dt), (ps, pt)):
        if "No such number" in tx: return "nonumber", "No such number on the server"
    if ds == "busy": return "busy", "On a call"
    if ds == "ringing": return "ringing", "Ringing"
    if ps == "offline": return "offline", "Offline"
    if ps == "online": return "available", pt or "Available"
    if ds == "free": return "free", "No call (the server does not say if signed in)"
    return "unknown", (dt or pt or "Waiting for the server")


class Phone(QtCore.QObject):
    registration = Signal(str, str)                 # state (unregistered | registering | registered | failed), text
    call_changed = Signal(object, str)              # Call, state
    presence_changed = Signal(str)                  # extension whose state changed
    dtmf_in = Signal(object, str)
    history_changed = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent); self.store = store; self.ua: U.UserAgent | None = None; self.call: U.Call | None = None; self.audio: Audio | None = None
        self.cadence: Cadence | None = None; self.reg_state = "unregistered"; self.reg_text = ""; self.dialog: dict[str, tuple] = {}; self.presence: dict[str, tuple] = {}; self._lock = threading.Lock()
        self._evt = _Bridge(self); self._evt.sig.connect(self._on_event)

    # ---- settings
    def cfg(self, key, default=""): return self.store.settings.get("voip_" + key, default)

    def contacts(self) -> list[dict]:
        c = self.store.settings.get("voip_contacts")
        return [dict(x) for x in c if isinstance(x, dict) and x.get("number")] if isinstance(c, list) else []

    def set_contacts(self, items: list[dict]):
        self.store.settings["voip_contacts"] = [dict(name=x.get("name", ""), number=str(x["number"]).strip(), callsign=x.get("callsign", "")) for x in items if str(x.get("number", "")).strip()]
        self.store.save_settings()
        if self.ua and self.reg_state == "registered": self.watch()

    def config(self) -> U.Config:
        s = self.store.settings
        return U.Config(server=s.get("voip_server", ""), port=int(s.get("voip_port") or 5060), transport=s.get("voip_transport", "udp"), user=s.get("voip_user", ""), password=self._session_pw or (s.get("voip_pw", "") if s.get("voip_remember", True) else ""),
                        auth_user=s.get("voip_auth_user", ""), domain=s.get("voip_domain", ""), display_name=s.get("voip_name") or s.get("op_name") or "", tls_verify=bool(s.get("voip_tls_verify", True)))

    _session_pw = ""

    # ---- sign in / out
    def sign_in(self, password: str | None = None) -> bool:
        s = self.store.settings
        if password is not None: self._session_pw = password
        if not s.get("voip_server") or not s.get("voip_user"):
            self._set_reg("failed", "Enter the server and your username first"); return False
        cfg = self.config()
        if not cfg.password: self._set_reg("failed", "Enter your password"); return False
        self.sign_out(wait=0.0)
        self.ua = U.UserAgent(cfg, lambda n, **k: self._evt.sig.emit(n, k), self._log); self.ua.start(); self._set_reg("registering", ""); return True

    def sign_out(self, wait: float = 1.5):
        ua, self.ua = self.ua, None
        self._stop_audio()
        if ua: threading.Thread(target=ua.stop, args=(wait,), daemon=True).start() if wait == 0 else ua.stop(wait)
        self.call = None; self._set_reg("unregistered", "")

    def shutdown(self): self.sign_out(1.5)

    def _log(self, text: str):
        try:
            from .. import diag; diag.log("voip " + text)
        except Exception: pass

    def _set_reg(self, state: str, text: str):
        self.reg_state, self.reg_text = state, text; self.registration.emit(state, text)

    # ---- events from the user agent (arrive on its thread, handled on the Qt thread)
    def _on_event(self, name: str, kw: dict):
        if name == "registration":
            self._set_reg(kw["state"], kw["text"])
            if kw["state"] == "registered": self.watch()
        elif name == "call": self._on_call(kw["call"], kw["state"])
        elif name == "presence":
            tbl = self.dialog if kw["event"] == "dialog" else self.presence
            tbl[kw["ext"]] = (kw["state"], kw["text"]); self.presence_changed.emit(kw["ext"])
        elif name == "dtmf": self.dtmf_in.emit(kw["call"], kw["digit"])

    def watch(self):
        nums = [c["number"] for c in self.contacts()]
        if self.ua: self.ua.watch(nums, events=("dialog", "presence"))

    def name_of(self, number: str) -> str:
        for c in self.contacts():
            if c["number"] == number: return c.get("name") or c.get("callsign") or ""
        return ""

    def state_of(self, number: str) -> tuple[str, str]:
        return combine(self.dialog.get(number), self.presence.get(number))

    # ---- calls
    def dial(self, number: str) -> bool:
        number = (number or "").strip()
        if not number or not self.ua or self.reg_state != "registered": return False
        if self.call and self.call.state != "ended": return False
        self.call = self.ua.call(number); return True

    def answer(self):
        if self.call: self._stop_tone(); self.call.answer()

    def hangup(self):
        if self.call: self.call.hangup()

    def reject(self):
        if self.call: self.call.reject(603)

    def dtmf(self, digit: str):
        if self.call and self.call.state == "active": self.call.send_dtmf(digit)

    def set_muted(self, on: bool):
        if self.audio: self.audio.muted = bool(on)
        self._muted = bool(on)

    _muted = False

    def _on_call(self, call: U.Call, state: str):
        if self.call is None or self.call is not call:
            if state == "incoming": self.call = call
            elif call is not self.call: return
        if state == "incoming": self._start_tone(RING_IN)
        elif state == "ringing": self._start_tone(RING_OUT)
        elif state == "active": self._start_call_audio(call)
        elif state == "ended": self._stop_audio(); self._remember(call)
        self.call_changed.emit(call, state)

    # ---- sound
    def _mk_audio(self) -> Audio:
        s = self.store.settings
        a = Audio(self._mic_frame, self._speaker_frame, s.get("mic", ""), s.get("speakers", "")); a.muted = self._muted; return a

    def _mic_frame(self, pcm):
        c = self.call
        if c and c.media and c.state == "active": c.media.send_frame(pcm)

    def _speaker_frame(self):
        c = self.call
        if c and c.media and (c.state == "active" or c.media.jitter.received > 0): return c.media.jitter.pull()
        if self.cadence: return self.cadence.frame()
        return np.zeros(FRAME, np.int16)

    def _start_tone(self, pattern):
        self.cadence = Cadence(pattern)
        if self.audio is None: self.audio = self._mk_audio()
        if not self.audio.start_speakers(): self._log("no speakers for the ring: " + self.audio.error)

    def _stop_tone(self): self.cadence = None

    def _start_call_audio(self, call):
        self._stop_tone()
        if self.audio is None: self.audio = self._mk_audio()
        self.audio.muted = self._muted
        ok_s = self.audio.start_speakers(); ok_m = self.audio.start_mic()
        if not (ok_s and ok_m): self._log("audio problem: " + self.audio.error)

    def _stop_audio(self):
        self.cadence = None; a, self.audio = self.audio, None
        if a: a.stop()

    def audio_problem(self) -> str: return self.audio.error if self.audio else ""

    # ---- call list
    def _remember(self, call: U.Call):
        h = self.store.settings.get("voip_history"); h = list(h) if isinstance(h, list) else []
        kind = "placed" if call.direction == "out" else ("received" if call.answered_at else "missed")
        h.insert(0, dict(t=time.time(), dir=kind, number=call.remote_user or call.remote_uri, name=call.remote_name or self.name_of(call.remote_user), secs=int(max(0, time.time() - call.answered_at)) if call.answered_at else 0, why=call.end_reason))
        self.store.settings["voip_history"] = h[:50]; self.store.save_settings(); self.history_changed.emit()


class _Bridge(QtCore.QObject):
    sig = Signal(str, object)
