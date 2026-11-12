from datetime import datetime, timezone
from .qt import QtCore, Signal
from .rules import SessionRules, Target, ListenMode
from .store import Store
from .engine import NullEngine
from .hostlists import HostLists
import threading


# What the DMR master told us when it refused the login (the engine sends the code; the text says what to check)
DMR_REFUSALS = {
    "DMR_NAK_ID": "The DMR master did not accept your DMR ID. Check the DMR ID in Settings › Radio networks (your own ID from RadioID.net, digits only) and the ESSID (leave it empty if unsure).",
    "DMR_NAK_PASSWORD": "The DMR master refused the password. On BrandMeister use your hotspot password (SelfCare › Hotspot Security), not your login password.",
    "DMR_NO_HOST": "The DMR master's address could not be found (DNS). Check the internet connection and the master server in the DMR server card.",
    "DMR_NAK_CONFIG": "The DMR master refused the connection settings after the password was accepted.",
}


class Ctx(QtCore.QObject):
    changed = Signal()
    toast = Signal(str)
    hosts_changed = Signal()            # the worldwide server lists were (re)loaded
    _hosts_done = Signal(int, object)
    _asl_done = Signal(int, str)
    asl_links_changed = Signal()        # the list of stations connected to an AllStar node was updated
    _asl_links_done = Signal(str, object)

    def __init__(self, store: Store | None = None, engine=None):
        super().__init__()
        self.store = store or Store()
        self.engine = engine or NullEngine()
        self.hosts = HostLists.for_root(self.store.root)
        from .allstar import NodeDirectory
        self.asl_nodes = NodeDirectory.for_root(self.store.root)
        self.closing = False                  # set when the program quits: background threads then stop emitting Qt signals
        self._asl_busy = False
        self._asl_done.connect(self._on_asl_done)
        self.asl_links: dict[str, dict] = {}; self._asl_links_asked: dict[str, float] = {}
        self._asl_links_done.connect(self._on_asl_links)
        from .servers import Servers
        self.servers = getattr(self.engine, "servers", None) or Servers(self.store)      # one address book for the pages and the engine
        self._hosts_busy = False
        self._hosts_done.connect(self._on_hosts_done)
        self.rules = SessionRules()
        self.rules.limit = self.store.settings.get("max_ptt", 120)
        self.rules.ducking = bool(self.store.settings.get("duck", True))
        if self.store.settings.get("listen_mode") == "multiple":
            self.rules.mode = ListenMode.MULTIPLE
        self.last_net = "DMR"
        self.engine_msg = ""
        self._problem = ("", 0.0)                # the last refusal / failure, kept visible in the status line for a while
        self.last_heard: list[dict] = []        # newest first
        self.dmr_password = (self.store.settings.get("dmr_pw") or "") if self.store.settings.get("remember_pw", True) else ""      # saved on this computer only while "Remember" is ticked
        if hasattr(self.engine, "dmr_password"): self.engine.dmr_password = self.dmr_password
        self.asl_password = (self.store.settings.get("asl_pw") or "") if self.store.settings.get("asl_remember", True) else ""    # AllStarLink portal password: kept in the settings file only when "Remember" is ticked
        if hasattr(self.engine, "asl_password"): self.engine.asl_password = self.asl_password
        if hasattr(self.engine, "status"):
            self.engine.status.connect(self._on_status); self.engine.heard.connect(self._on_heard)
            self.engine.volume_refresh.connect(lambda: self.__dict__.pop("_vol_cache", None))
            if hasattr(self.engine, "notice"): self.engine.notice.connect(self.toast.emit)
        from . import diag; self.toast.connect(lambda m: diag.log("toast: " + m)); diag.log(f"engine={self.engine.name}")
        self._timer = QtCore.QTimer(self); self._timer.setInterval(250); self._timer.timeout.connect(self._tick)
        self._timer.start()

    @property
    def selected(self): return self.rules.selected

    # ---- worldwide server lists ---------------------------------------------
    def refresh_hosts(self, force=False):
        """Downloads the YSF / D-Star / DMR lists in the background (only when missing, older than 24 h, or forced)."""
        if self._hosts_busy or not (force or self.hosts.stale()): return
        self._hosts_busy = True
        if force: self.toast.emit("Downloading the worldwide server lists…")
        def work():
            try: n, problems = self.hosts.download()
            except Exception as ex: n, problems = 0, [str(ex)]
            if not self.closing: self._hosts_done.emit(n, problems)
        threading.Thread(target=work, daemon=True).start()

    def refresh_asl(self, force=False):
        """Downloads the AllStarLink node list in the background (when missing, older than 24 h, or forced - but never more often than every 15 minutes)."""
        if self._asl_busy or not (force or self.asl_nodes.stale()): return
        if not self.asl_nodes.can_refresh():
            if force: self.toast.emit("The AllStarLink node list is up to date (it is renewed at most every 15 minutes).")
            return
        self._asl_busy = True
        if force: self.toast.emit("Downloading the AllStarLink node list…")
        def work():
            try: n, problem = self.asl_nodes.download()
            except Exception as ex: n, problem = 0, str(ex)
            if not self.closing: self._asl_done.emit(n, problem)
        threading.Thread(target=work, daemon=True).start()

    def _on_asl_done(self, n, problem):
        self._asl_busy = False
        from . import diag; diag.log(f"AllStar nodes: {n}; problem={problem}")
        if problem: self.toast.emit(problem + (" — using the saved copy." if self.asl_nodes.nodes else ""))
        elif n: self.toast.emit(f"AllStarLink node list updated: {n} nodes")
        self.hosts_changed.emit()

    def _on_hosts_done(self, n, problems):
        self._hosts_busy = False
        from . import diag; diag.log(f"host lists: {n} entries; problems={problems}; status={self.hosts.status}")
        retry, self._retry = getattr(self, "_retry", None), None
        if problems:
            self.toast.emit(("Server lists: " + "; ".join(problems[:2]) + (" …" if len(problems) > 2 else "")) + (" — using the saved copy." if n else ""))
        elif n:
            self.toast.emit(f"Server lists updated: {self.hosts.summary()}")
        self.hosts_changed.emit()
        if retry and getattr(self, "_auto_dl", False):
            if n: retry()
            self._auto_dl = False

    def _sync_audio(self):
        """Push the effective receive volume (volume slider, mute, ducking, no self-monitoring) to the engine."""
        if not hasattr(self.engine, "set_rx_volume"): return
        cache = self.__dict__.setdefault("_vol_cache", {})
        live = set()
        for r in self.rules.rx:
            live.add(r.handle); v = round(self.rules.effective_volume(r), 3)
            if cache.get(r.handle) != v:
                cache[r.handle] = v; self.engine.set_rx_volume(r.handle, v)
        r = self.rules
        for ln in (self.engine.tx_only_links() if hasattr(self.engine, "tx_only_links") else []):
            # a link that was only connected for transmitting also plays what the server sends: mute / volume of its network must reach it too
            net = ln.target.net; key = ("tx", ln.key); live.add(key)
            v = 0.0 if r.net_muted[net] else r.net_volume[net]
            if r.ptt and r.tx_target == ln.target: v = 0.0               # no self-monitoring
            elif r.ptt and r.ducking: v *= 0.25
            v = round(v, 3)
            if cache.get(key) != v: cache[key] = v; ln.send("out_volume", out=max(0.0, min(1.0, v)))
        for h in list(cache):
            if h not in live: del cache[h]

    ASL_LINKS_EVERY = 15.0              # seconds between two questions per node (the stats server allows 30 per minute)

    def _asl_nodes_in_use(self) -> set[str]:
        r = self.rules; nodes = {x.target.id for x in r.rx if x.target.net == "AllStar"}
        if r.tx_connected and r.tx_target is not None and r.tx_target.net == "AllStar": nodes.add(r.tx_target.id)
        return nodes

    def poll_asl_links(self, now: float | None = None):
        """Who is connected to the AllStar node(s) we are connected to: asked from the stats server in a worker thread, every 15 s."""
        import time as _t
        now = _t.monotonic() if now is None else now
        for node in self._asl_nodes_in_use():
            if now - self._asl_links_asked.get(node, -1e9) < self.ASL_LINKS_EVERY: continue
            self._asl_links_asked[node] = now
            def work(node=node):
                from . import allstar
                res = allstar.fetch_links(node)
                if not self.closing: self._asl_links_done.emit(node, res)
            threading.Thread(target=work, daemon=True).start()

    def _on_asl_links(self, node, res):
        res["ts"] = __import__("time").time(); self.asl_links[node] = res
        from . import diag; diag.log(f"AllStar node {node}: {len(res.get('rows', []))} linked nodes" + (f" ({res['error']})" if res.get("error") else ""))
        self.asl_links_changed.emit()

    def _tick(self):
        self._sync_audio()
        self.poll_asl_links()
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

    def set_mic_gain(self, pct: int):
        self.store.settings["mic_gain"] = int(pct); self.store.save_settings()
        if hasattr(self.engine, "set_mic_gain"): self.engine.set_mic_gain(pct)

    def dtmf_target(self):
        """The AllStar node DTMF goes to: the selected node, else the Connect (TX) node."""
        t, r = self.selected, self.rules
        if t is not None and t.net == "AllStar": return t
        if r.tx_connected and r.tx_target is not None and r.tx_target.net == "AllStar": return r.tx_target
        return None

    def send_dtmf(self, keys: str, target=None) -> bool:
        from .rules import valid_dtmf
        keys = (keys or "").strip().upper(); target = target or self.dtmf_target()
        if target is None: self.toast.emit("DTMF is sent to the connected AllStarLink node. Select the node and connect first."); return False
        if not valid_dtmf(keys): self.toast.emit("DTMF accepts 1 to 32 characters from 0-9, A-D, * and #."); return False
        if not hasattr(self.engine, "send_dtmf"): self.toast.emit("No protocol engine connected (UI preview)"); return False
        err = self.engine.send_dtmf(target, keys)
        self.toast.emit(err or f"DTMF sent: {keys}")
        return not err

    def set_asl_login(self, user: str, pw: str, remember=None):
        """AllStarLink portal account, entered once. The password is saved on this computer (settings file) only while "Remember" is on."""
        s = self.store.settings
        if remember is None: remember = bool(s.get("asl_remember", True))
        user = (user or "").strip(); changed = False
        for k, v in (("asl_user", user), ("asl_remember", bool(remember)), ("asl_pw", pw if remember else "")):
            if s.get(k) != v: s[k] = v; changed = True
        if changed: self.store.save_settings()
        self.asl_password = pw
        if hasattr(self.engine, "asl_password"): self.engine.asl_password = pw

    def set_dmr_password(self, pw: str, remember=None):
        s = self.store.settings
        if remember is None: remember = bool(s.get("remember_pw", True))
        changed = False
        for k, v in (("remember_pw", bool(remember)), ("dmr_pw", pw if remember else "")):
            if s.get(k) != v: s[k] = v; changed = True
        if changed: self.store.save_settings()
        self.dmr_password = pw
        if hasattr(self.engine, "dmr_password"): self.engine.dmr_password = pw

    # ---- engine feedback ------------------------------------------------------
    def note_problem(self, text: str):
        import time; self._problem = (text, time.monotonic())

    def _reject_if_failed(self, t: Target, handle, rx: bool):
        """The engine refused synchronously (no callsign, no server address...): undo the rules state."""
        m = self.engine_msg
        if not m or m == "Connected" or getattr(self.engine, "preview", False): return
        if rx: self.rules.stop_listening(handle)
        else: self.rules.disconnect_tx()
        self.engine_msg = ""
        if m == "NEED_ENDPOINT": self._no_address(t, rx)
        else: self.note_problem(m); self.toast.emit(m)

    def _no_address(self, t: Target, rx: bool):
        """The entry is not in the downloaded worldwide list: never ask the user for host:port.
        Download the lists once and retry by itself; if it still is not there, say so."""
        if t.net == "DMR":
            self.note_problem("Choose a DMR master server in the list first (Master server), then press Listen.")
            self.toast.emit("Choose a DMR master server in the list first (Master server), then press Listen."); return
        if not self.hosts.entries and not self._hosts_busy and not getattr(self, "_auto_dl", False):
            self._auto_dl = True; self._retry = self.toggle_listen if rx else self.toggle_tx
            self.toast.emit("Downloading the worldwide server lists, then connecting…"); self.refresh_hosts(True); return
        self.toast.emit(f"{t.id} is not in the worldwide server list. Press Refresh in the directory to download the newest lists.")

    def _on_status(self, ln, state: str, msg: str):
        t = ln.target
        if state == "connected":
            self.engine_msg = ""; self.toast.emit(f"Connected · {t.name or t.id}")
        elif state in ("error", "timeout"):
            for h in list(ln.rx): self.rules.stop_listening(h)
            if ln.tx: self.rules.disconnect_tx()
            from .i18n import tr
            text = tr(DMR_REFUSALS.get(msg, msg or state))
            if t.net == "DMR" and "no answer" in (msg or "").lower():
                text += tr(" — DMR: check the master address, your DMR ID and your personal hotspot password (BrandMeister SelfCare › Hotspot Security).")
            self.note_problem(f"{t.name or t.id}: {text}"); self.toast.emit(f"{t.name or t.id}: {text}")
        self.changed.emit()

    def _on_heard(self, ln, e: dict):
        st = e.get("state")
        if st in ("new", "streaming"):
            for r in self.rules.rx:
                if r.handle in ln.rx: r.reports_traffic = True
            src = e.get("src") or e.get("callsign") or "?"
            dst = (e.get("dst", "") or "").strip()
            if not dst.strip("*"): dst = ""                      # YSF sends '**********' = 'everyone': show nothing instead of stars
            now = self.utc_now()
            cur = next((h for h in self.last_heard[:6] if h["net"] == ln.target.net and h["src"] == src), None)
            if cur is not None and (now - cur["last"]).total_seconds() < 4:
                cur["last"] = now                                  # same transmission goes on (the engine reports every frame) -> one row
                if dst and not cur["dst"]: cur["dst"] = dst
            else:
                from . import diag; diag.log(f"heard {src} -> {dst} via {e.get('gw', '')} on {ln.target.net}:{ln.target.id}")
                mine = (self.store.settings.get("callsign") or "").strip().upper()
                self.last_heard.insert(0, dict(src=src, dst=dst, gw=(e.get("gw", "") or "").strip(), net=ln.target.net, target=ln.target.id,
                                              stream_src=src, ts=now, last=now, me=bool(mine) and mine in src.upper().replace(" ", "").split("/")))
                del self.last_heard[60:]
        elif st in ("end", "lost"):
            for r in self.rules.rx:
                if r.handle in ln.rx: r.reports_traffic = False
        self.changed.emit()

    # ---- text helpers -----------------------------------------------------
    def status_text(self) -> str:
        import time
        text, at = self._problem
        if text and time.monotonic() - at < 25: return "⚠ " + text            # why the last Listen / Connect did not start
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
