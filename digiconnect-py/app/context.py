from datetime import datetime, timezone
from .qt import QtCore, Signal
from .rules import SessionRules, Target, ListenMode
from .store import Store
from .engine import NullEngine


class Ctx(QtCore.QObject):
    changed = Signal()
    toast = Signal(str)
    need_endpoint = Signal(object)      # Target whose server address is unknown

    def __init__(self, store: Store | None = None, engine=None):
        super().__init__()
        self.store = store or Store()
        self.engine = engine or NullEngine()
        self.rules = SessionRules()
        self.rules.limit = self.store.settings.get("max_ptt", 120)
        self.rules.ducking = bool(self.store.settings.get("duck", True))
        if self.store.settings.get("listen_mode") == "multiple":
            self.rules.mode = ListenMode.MULTIPLE
        self.last_net = "DMR"
        self.engine_msg = ""
        self.last_heard: list[dict] = []        # newest first
        self.dmr_password = ""                   # session only, never written to disk
        if hasattr(self.engine, "status"):
            self.engine.status.connect(self._on_status); self.engine.heard.connect(self._on_heard)
            self.engine.volume_refresh.connect(lambda: self.__dict__.pop("_vol_cache", None))
        self._timer = QtCore.QTimer(self); self._timer.setInterval(250); self._timer.timeout.connect(self._tick)
        self._timer.start()

    @property
    def selected(self): return self.rules.selected

    def _sync_audio(self):
        """Push the effective receive volume (volume slider, mute, ducking, no self-monitoring) to the engine."""
        if not hasattr(self.engine, "set_rx_volume"): return
        cache = self.__dict__.setdefault("_vol_cache", {})
        live = set()
        for r in self.rules.rx:
            live.add(r.handle); v = round(self.rules.effective_volume(r), 3)
            if cache.get(r.handle) != v:
                cache[r.handle] = v; self.engine.set_rx_volume(r.handle, v)
        for h in list(cache):
            if h not in live: del cache[h]

    def _tick(self):
        self._sync_audio()
        if self.rules.ptt:
            self.rules.tick(250)
            if not self.rules.ptt:
                self.engine.ptt(False); self.toast.emit("TX ended: time limit reached")
            self.changed.emit()

    # ---- actions ----------------------------------------------------------
    def select(self, t: Target | None):
        self.rules.select(t); self.changed.emit()

    def toggle_listen(self):
        t = self.selected
        if not t: return
        if self.rules.is_listening(t):
            r = next(r for r in self.rules.rx if r.target == t)
            self.rules.stop_listening(r.handle); self.engine.stop_rx(r.handle)
        else:
            o = self.rules.listen(t)
            if not o.ok:
                self.toast.emit("Maximum of 4 DMR receivers reached. Stop one before adding another."); return
            for h in o.removed: self.engine.stop_rx(h)
            self.engine_msg = self.engine.start_rx(o.handle, t) or ""
            self._reject_if_failed(t, o.handle, rx=True)
        self.changed.emit()

    def toggle_tx(self):
        t = self.selected
        if not t: return
        if self.rules.tx_connected:
            self.rules.disconnect_tx(); self.engine.disconnect_tx(); self.engine.ptt(False)
        else:
            o = self.rules.connect_tx(t)
            if o.ok:
                self.engine_msg = self.engine.connect_tx(t) or ""
                self._reject_if_failed(t, None, rx=False)
        self.changed.emit()

    def ptt_down(self, latch=False):
        if self.rules.ptt and self.rules.latched and latch:
            self.rules.ptt_press(True); self.engine.ptt(False)
        elif self.rules.ptt_press(latch).ok:
            self.engine.ptt(True)
        self.changed.emit()

    def ptt_up(self):
        if self.rules.ptt and not self.rules.latched:
            self.rules.ptt_release(); self.engine.ptt(False); self.changed.emit()

    def stop_all(self):
        for r in list(self.rules.rx): self.engine.stop_rx(r.handle)
        self.engine.ptt(False); self.engine.disconnect_tx()
        self.rules.stop_all(); self.changed.emit()

    def set_mode(self, m: ListenMode):
        o = self.rules.set_mode(m)
        if not o.ok:
            self.toast.emit("Listening mode cannot be changed during transmission."); self.changed.emit(); return
        for h in o.removed: self.engine.stop_rx(h)
        self.store.settings["listen_mode"] = m.value; self.store.save_settings(); self.changed.emit()

    def set_limit(self, s: int):
        if self.rules.set_limit(s): self.changed.emit()

    def focus_lost(self):
        if self.rules.ptt:
            self.rules.focus_lost(); self.engine.ptt(False); self.toast.emit("TX stopped: window lost focus"); self.changed.emit()

    def retry_pending(self):
        fn, self._retry = getattr(self, "_retry", None), None
        if fn: fn()

    def set_dmr_password(self, pw: str):
        self.dmr_password = pw
        if hasattr(self.engine, "dmr_password"): self.engine.dmr_password = pw

    # ---- engine feedback ------------------------------------------------------
    def _reject_if_failed(self, t: Target, handle, rx: bool):
        """The engine refused synchronously (no callsign, no server address...): undo the rules state."""
        m = self.engine_msg
        if not m or m == "Connected" or getattr(self.engine, "preview", False): return
        if rx: self.rules.stop_listening(handle)
        else: self.rules.disconnect_tx()
        self.engine_msg = ""
        if m == "NEED_ENDPOINT":
            self._retry = self.toggle_listen if rx else self.toggle_tx
            self.need_endpoint.emit(t)
        else: self.toast.emit(m)

    def _on_status(self, ln, state: str, msg: str):
        t = ln.target
        if state == "connected":
            self.engine_msg = ""; self.toast.emit(f"Connected · {t.name or t.id}")
        elif state in ("error", "timeout"):
            for h in list(ln.rx): self.rules.stop_listening(h)
            if ln.tx: self.rules.disconnect_tx()
            self.toast.emit(f"{t.name or t.id}: {msg or state}")
        self.changed.emit()

    def _on_heard(self, ln, e: dict):
        st = e.get("state")
        if st in ("new", "streaming"):
            for r in self.rules.rx:
                if r.handle in ln.rx: r.reports_traffic = True
            src = e.get("src") or e.get("callsign") or "?"
            if st == "new" or not self.last_heard or self.last_heard[0].get("stream_src") != src:
                self.last_heard.insert(0, dict(src=src, dst=e.get("dst", ""), gw=e.get("gw", ""), net=ln.target.net, target=ln.target.id,
                                              stream_src=src, ts=self.utc_now()))
                del self.last_heard[30:]
        elif st in ("end", "lost"):
            for r in self.rules.rx:
                if r.handle in ln.rx: r.reports_traffic = False
        self.changed.emit()

    # ---- text helpers -----------------------------------------------------
    def status_text(self) -> str:
        r = self.rules
        if not r.rx: return "Listening stopped"
        n = len(r.rx)
        base = f"Listening · {n} receiver{'s' if n > 1 else ''}"
        return base + (f" · {self.engine_msg}" if self.engine_msg else "")

    def tx_text(self) -> str:
        r = self.rules
        if not r.tx_connected: return "Transmit disconnected"
        return "Transmitting" if r.ptt else f"Transmit ready · {r.tx_target.name or r.tx_target.id}"

    def tx_target_text(self) -> str:
        t = self.rules.tx_target if self.rules.tx_connected else None
        return f"TX · {t.net} · {t.id}" if t else "No TX destination"

    @staticmethod
    def utc_now(): return datetime.now(timezone.utc)
