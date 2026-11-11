"""Session rules: Listen / Connect(TX) are separate; single vs multiple listening;
PTT hold/latch with fixed destination and time limit; card state; validators.
Pure Python (no Qt) so it is fully testable. Time is injected via tick(ms)."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

NETS = ("DMR", "D-Star", "EchoLink", "C4FM", "NXDN", "P25", "M17")
MAX_DMR = 4
WARN_SECONDS = 15


class ListenMode(Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class CardState(Enum):
    NEUTRAL = "neutral"
    GREEN = "green"
    PINK = "pink"
    AMBER = "amber"


@dataclass(frozen=True)
class Target:
    net: str            # one of NETS
    id: str             # TG / reflector+module / callsign / YSF id
    name: str = ""

    def key(self):
        return (self.net, self.id)

    def __eq__(self, o):
        return isinstance(o, Target) and self.key() == o.key()

    def __hash__(self):
        return hash(self.key())


@dataclass
class Receiver:
    handle: int
    target: Target
    muted: bool = False
    volume: float = 1.0
    reports_traffic: bool = False
    blocked: bool = False


@dataclass
class OpResult:
    ok: bool = True
    kind: str = "ok"            # ok | focused | replaced | refused
    handle: int = 0
    removed: list = field(default_factory=list)
    reason: str = ""


class SessionRules:
    def __init__(self):
        self.mode = ListenMode.SINGLE
        self.rx: list[Receiver] = []
        self.focus_handle = 0
        self._next = 1
        self.net_volume = {n: 1.0 for n in NETS}
        self.net_muted = {n: False for n in NETS}
        self.selected: Target | None = None
        self.tx_connected = False
        self.tx_target: Target | None = None
        self.ptt = False
        self.latched = False
        self.limit = 120
        self.remaining = 0
        self._acc = 0
        self.ducking = True

    # ---- listening --------------------------------------------------------
    def find(self, handle):
        return next((r for r in self.rx if r.handle == handle), None)

    def listen(self, t: Target) -> OpResult:
        for r in self.rx:
            if r.target == t:
                self.focus_handle = r.handle
                return OpResult(True, "focused", r.handle)
        o = OpResult()
        if self.mode is ListenMode.SINGLE:
            o.removed = [r.handle for r in self.rx]
            self.rx.clear()
            if o.removed:
                o.kind = "replaced"
        elif t.net != "DMR":
            keep = []
            for r in self.rx:
                if r.target.net == t.net:
                    o.removed.append(r.handle)
                else:
                    keep.append(r)
            self.rx = keep
            if o.removed:
                o.kind = "replaced"
        elif sum(1 for r in self.rx if r.target.net == "DMR") >= MAX_DMR:
            return OpResult(False, "refused", reason="dmr-capacity")
        r = Receiver(self._next, t)
        self._next += 1
        self.rx.append(r)
        self.focus_handle = o.handle = r.handle
        return o

    def stop_listening(self, handle) -> OpResult:
        r = self.find(handle)
        if not r:
            return OpResult(False, "refused", reason="unknown")
        self.rx.remove(r)
        if self.focus_handle == handle:
            self.focus_handle = self.rx[-1].handle if self.rx else 0
        return OpResult(True, "ok", handle, [handle])

    def set_mode(self, m: ListenMode) -> OpResult:
        if self.ptt:
            return OpResult(False, "refused", reason="tx-active")
        o = OpResult()
        if m is ListenMode.SINGLE and len(self.rx) > 1:
            keep = self.focus_handle if self.find(self.focus_handle) else self.rx[0].handle
            o.removed = [r.handle for r in self.rx if r.handle != keep]
            self.rx = [r for r in self.rx if r.handle == keep]
            self.focus_handle = keep
        self.mode = m
        return o

    def stop_all(self):
        self.rx.clear()
        self.focus_handle = 0
        self._end_ptt()
        self.tx_connected = False

    def effective_volume(self, r: Receiver) -> float:
        if r.muted or r.blocked or self.net_muted[r.target.net]:
            return 0.0
        v = self.net_volume[r.target.net] * r.volume
        if self.ptt and self.tx_target == r.target:
            return 0.0                       # no self-monitoring of the matching receiver
        if self.ptt and self.ducking:
            v *= 0.25
        return v

    # ---- transmit ---------------------------------------------------------
    def select(self, t: Target | None):
        self.selected = t

    def connect_tx(self, t: Target) -> OpResult:
        if self.ptt:
            return OpResult(False, "refused", reason="tx-active")
        self.tx_target, self.tx_connected = t, True
        return OpResult()

    def disconnect_tx(self):
        self._end_ptt()
        self.tx_connected = False

    @property
    def ptt_available(self) -> bool:
        return self.tx_connected and self.selected is not None and self.selected == self.tx_target

    def ptt_press(self, latch: bool) -> OpResult:
        if not self.ptt_available:
            return OpResult(False, "refused", reason="not-tx-ready")
        if self.ptt:
            if self.latched and latch:
                self._end_ptt()
            return OpResult()
        self.ptt, self.latched = True, latch
        self.remaining, self._acc = self.limit, 0
        return OpResult()

    def ptt_release(self):
        self._end_ptt()

    def _end_ptt(self):
        self.ptt = self.latched = False
        self.remaining = self._acc = 0

    def set_limit(self, s: int) -> bool:
        if self.ptt or s not in (60, 120, 180):
            return False
        self.limit = s
        return True

    @property
    def countdown_red(self) -> bool:
        return self.ptt and self.remaining <= WARN_SECONDS

    def tick(self, ms: int):
        if not self.ptt:
            return
        self._acc += ms
        while self._acc >= 1000 and self.remaining > 0:
            self._acc -= 1000
            self.remaining -= 1
        if self.remaining <= 0:
            self._end_ptt()

    def focus_lost(self):
        if self.ptt:
            self._end_ptt()

    # ---- presentation -----------------------------------------------------
    def card_state(self, r: Receiver) -> CardState:
        actual = r.reports_traffic and not r.muted and not r.blocked and not self.net_muted[r.target.net]
        if self.mode is ListenMode.MULTIPLE and actual:
            return CardState.AMBER
        return CardState.PINK

    def is_listening(self, t: Target) -> bool:
        return any(r.target == t for r in self.rx)


# ---- validators -----------------------------------------------------------
def valid_dmr_tg(s: str) -> bool:
    return s.isascii() and s.isdigit() and 1 <= int(s) <= 16777215 and len(s) <= 8


def valid_dtmf(s: str) -> bool:
    return 1 <= len(s) <= 32 and all(c in "0123456789ABCD*#" for c in s)


def valid_favorite_name(s: str) -> bool:
    return 1 <= len(s) <= 80          # Python str length counts code points


def valid_text_size(px: int) -> bool:
    return 11 <= px <= 20
