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
    "DMR_NO_REWIND": "BrandMeister did not answer on its terminal ports (UDP 54006 and 54005). Check the internet connection, that the network or firewall lets UDP out, and your DMR ID.",
}


class Ctx(QtCore.QObject):
    changed = Signal()
    toast = Signal(str)
    hosts_changed = Signal()            # the worldwide server lists were (re)loaded
    _hosts_done = Signal(int, object)
    _asl_done = Signal(int, str)
    dmr_server_changed = Signal()       # a DMR server was picked: the DMR page and Settings > Radio networks show the same server and port
    policy_changed = Signal()           # the owner's server opened/closed a mode or switched transmitting
    asl_links_changed = Signal()        # the list of stations connected to an AllStar node was updated
    _asl_links_done = Signal(str, object)
    el_changed = Signal()               # EchoLink: signed in / out, the station list arrived, or a station sent text (who is connected)
    _el_done = Signal(object)
    _station_done = Signal(int, object)   # a callbook lookup (DMR ID -> callsign) finished

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
        self.el_stations: list[dict] = []; self.el_status = ""; self.el_signed_in = False; self.el_busy = False; self.el_last = 0.0; self.el_result: dict = {}
        self.el_nodes: dict[str, dict] = {}          # call sign of the station we are connected to -> {lines, calls}: what it told us (who is connected)
        self._el_done.connect(self._on_el_done)
        self._asl_links_done.connect(self._on_asl_links)
        from .servers import Servers
        self.servers = getattr(self.engine, "servers", None) or Servers(self.store)      # one address book for the pages and the engine
        self._hosts_busy = False
        self._hosts_done.connect(self._on_hosts_done)
        from .policy import Policy
        self.policy = Policy()                # what the server allows (modes, transmit); the licence check updates it
        self.policy.user_off = set(store.settings.get("modes_off", []) or [])
        self.rules = SessionRules()
        self.rules.limit = self.store.settings.get("max_ptt", 120)
        self.rules.ducking = bool(self.store.settings.get("duck", True))
        if self.store.settings.get("listen_mode") == "multiple":
            self.rules.mode = ListenMode.MULTIPLE
        self.last_net = "DMR"
        self.engine_msg = ""
        self._problem = ("", 0.0)                # the last refusal / failure, kept visible in the status line for a while
        self.last_heard: list[dict] = []        # newest first
        from .callbook import Callbook
        self.callbook = Callbook(self.store.root)   # DMR ID -> callsign, name, country (RadioID), remembered on this computer
        self.talking: dict[tuple, dict] = {}    # (network, target id) -> the station that is talking there right now
        self._station_done.connect(self._on_station)
        self.qso_prefill = None                 # set by the station panel's New QSO button, read once by the QSO drawer
        self.dmr_password = (self.store.settings.get("dmr_pw") or "") if self.store.settings.get("remember_pw", True) else ""      # saved on this computer only while "Remember" is ticked
        if hasattr(self.engine, "dmr_password"): self.engine.dmr_password = self.dmr_password
        self.asl_password = (self.store.settings.get("asl_pw") or "") if self.store.settings.get("asl_remember", True) else ""    # AllStarLink portal password: kept in the settings file only when "Remember" is ticked
        if hasattr(self.engine, "asl_password"): self.engine.asl_password = self.asl_password
        self.el_password = (self.store.settings.get("el_pw") or "") if self.store.settings.get("el_remember", True) else ""
        if hasattr(self.engine, "nodetext"): self.engine.nodetext.connect(self._on_nodetext)
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
        self._bm_server_to_api()
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
        self._el_keepalive()
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
            if not self.policy.allows(t.net): self._closed(t.net); return
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
            if not self.policy.allows(t.net): self._closed(t.net); return
            if not self.policy.tx: self._no_tx(); return
            o = self.rules.connect_tx(t)
            if o.ok:
                self.engine_msg = self.engine.connect_tx(t) or ""
                self._reject_if_failed(t, None, rx=False)
        self.changed.emit()

    def ptt_down(self, latch=False):
        if not self.policy.tx: self._no_tx(); return
        if self.rules.ptt and self.rules.latched and latch:
            self.rules.ptt_press(True); self.engine.ptt(False)
        elif self.rules.ptt_press(latch).ok:
            self.engine.ptt(True)
        self.changed.emit()

    def stop_tx(self):
        """Ends a transmission at once (also a latched one), without stopping the listening."""
        if self.rules.ptt: self.rules._end_ptt(); self.engine.ptt(False); self.changed.emit()

    def dtmf_peer(self):
        """Where the DTMF keypad sends: an AllStar node, else the connected EchoLink peer; None = nothing to send to yet."""
        t = self.dtmf_target()
        if t is not None: return t
        r = self.rules
        return r.tx_target if r.tx_connected and r.tx_target is not None and r.tx_target.net == "EchoLink" else None

    def ptt_up(self):
        if self.rules.ptt and not self.rules.latched:
            self.rules.ptt_release(); self.engine.ptt(False); self.changed.emit()

    def stop_all(self):
        for r in list(self.rules.rx): self.engine.stop_rx(r.handle)
        self.engine.ptt(False); self.engine.disconnect_tx()
        self.rules.stop_all(); self.talking.clear(); self.changed.emit()

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
        keys = (keys or "").strip().upper(); target = target or self.dtmf_peer()
        if target is None: self.toast.emit("DTMF is sent to the connected AllStarLink node or EchoLink station. Select it and connect first (EchoLink: with Connect (TX) on)."); return False
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

    # ---- EchoLink: directory sign-in, station list, staying online ------------------------------------------------
    def set_el_login(self, call: str, pw: str, remember=None):
        s = self.store.settings
        if remember is None: remember = bool(s.get("el_remember", True))
        call = (call or "").strip().upper(); changed = False
        for k, v in (("echolink_call", call), ("el_remember", bool(remember)), ("el_pw", pw if remember else "")):
            if s.get(k) != v: s[k] = v; changed = True
        if changed: self.store.save_settings()
        self.el_password = pw

    def el_sign_in(self, state: str = "ONLINE", want_list: bool = True, silent: bool = False):
        """Signs in to the EchoLink directory and (when wanted) loads the station list, in a worker thread. The result is kept as it came (Test connection shows it)."""
        if self.el_busy: return
        s = self.store.settings; call = s.get("echolink_call") or s.get("callsign") or ""
        self.el_busy = True
        if not silent: self.el_status = "Signing in to EchoLink …"; self.el_changed.emit()
        loc = str(s.get("echolink_loc") or "")
        def work():
            from . import echolink
            try: res = echolink.sign_in(call, self.el_password, loc, state, want_list)
            except Exception as ex: res = dict(ok=False, error=f"EchoLink sign-in failed ({ex}).", server="", login_raw="", list_raw="", stations=[])
            res["state"] = state; res["silent"] = silent
            if not self.closing: self._el_done.emit(res)
        threading.Thread(target=work, daemon=True).start()

    def _on_el_done(self, res):
        from . import diag, echolink
        self.el_busy = False; self.el_result = res; self.el_last = __import__("time").monotonic()
        diag.log(f"EchoLink {res.get('state')}: ok={res.get('ok')} server={res.get('server')} stations={len(res.get('stations', []))} login={res.get('login_raw', '')[:60]!r} error={res.get('error')}")
        if res.get("state") == "OFFLINE": return
        if res.get("ok"):
            self.el_signed_in = True
            if res.get("stations"):
                self.el_stations = echolink.directory_rows(res["stations"])
                self.servers.el_hosts = {e["id"].upper(): {"host": e["host"], "port": e["port"]} for e in self.el_stations}
            self.el_status = f"Signed in to EchoLink · {len(self.el_stations)} stations"
            if not res.get("silent"): self.toast.emit(self.el_status)
        else:
            if not res.get("silent") or not self.el_signed_in: self.el_signed_in = False
            self.el_status = res.get("error") or "EchoLink sign-in failed."
            if not res.get("silent"): self.toast.emit(self.el_status)
        self.el_changed.emit(); self.hosts_changed.emit()

    def el_info(self, call: str) -> dict | None:
        """The directory row of an EchoLink station (place, node number, kind, status, country), or None."""
        c = (call or "").strip().upper()
        return next((e for e in self.el_stations if e["id"].upper() == c), None)

    def el_refresh(self):
        """Refresh on the EchoLink page: sign in again and reload the station list (or tell what is missing)."""
        if not self.el_password: self.toast.emit("Enter your EchoLink password first."); return
        self.el_sign_in()

    def el_go_offline(self):
        """Tells the directory we are leaving (the station list of others then shows us as offline). Quick, best effort."""
        if not self.el_signed_in: return
        from . import echolink
        try: echolink.sign_in(self.store.settings.get("echolink_call") or self.store.settings.get("callsign") or "", self.el_password, "", "OFFLINE", False)
        except Exception: pass
        self.el_signed_in = False

    def _el_in_use(self) -> bool:
        r = self.rules
        return any(x.target.net == "EchoLink" for x in r.rx) or (r.tx_connected and r.tx_target is not None and r.tx_target.net == "EchoLink")

    def _el_keepalive(self):
        """A station we call checks in the directory that the caller is online: say 'online' every 5 minutes while signed in (and connected to a station)."""
        import time as _t
        from . import echolink
        if self.el_signed_in and not self.el_busy and _t.monotonic() - self.el_last > echolink.STAY_ONLINE_EVERY and self._el_in_use():
            self.el_sign_in("BUSY" if self.rules.ptt else "ONLINE", want_list=False, silent=True)

    def _on_nodetext(self, ln, text: str):
        if ln.target.net != "EchoLink": return
        from . import echolink
        node = ln.target.id.upper(); st = echolink.apply_text(self.el_nodes.setdefault(node, {}), text)
        st["calls"] = [c for c in st["calls"] if c != node]                  # the station itself is not "connected to" itself
        self.el_changed.emit()

    def _bm_server_to_api(self):
        """A BrandMeister master chosen earlier from Pi-Star's list ('2022.master.brandmeister.network') becomes the same master from BrandMeister's own list
        (name 'BrandMeister 2022', its IP), so Settings and the DMR card show it the way every BrandMeister master is shown. Same server, same port."""
        try:
            e = self.hosts.bm_api_twin(str(self.store.settings.get("dmr_server") or ""))
            if e and int(self.store.settings.get("dmr_port") or 0) == int(e["port"]): self.set_dmr_server(e)
        except Exception: pass

    def set_dmr_server(self, m: dict):
        """A server picked from the downloaded list (or typed in the picker's Manual entry): Server and Port of the DMR settings are set to it."""
        s = self.store.settings; host, port = str(m["host"]), int(m["port"])
        name = "Manual entry" if m.get("src") == "manual" else (m.get("name") or host).replace("_", " ")
        s["dmr_server"], s["dmr_port"] = host, port; s["dmr_server_pick"] = {"host": host, "port": port, "name": name}
        self.store.save_settings(); self.toast.emit(f"DMR server: {name} ({host}:{port})")
        self.dmr_server_changed.emit(); self.changed.emit()

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
    def _closed(self, net: str):
        m = self.policy.reason(net); self.note_problem(m); self.toast.emit(m); self.changed.emit()

    def _no_tx(self):
        m = self.policy.tx_reason(); self.note_problem(m); self.toast.emit(m); self.changed.emit()

    def toggle_record(self) -> str:
        """Start or stop recording what is played to the person. Returns the file being written, or '' when stopped."""
        from .recording import recordings_dir
        from datetime import datetime
        if getattr(self, "recording", ""):
            self.engine.set_record(False); self.recording = ""
            self.toast.emit("Recording stopped."); self.changed.emit(); return ""
        path = str(recordings_dir(self.store) / f"DigiConnect_{datetime.now():%Y%m%d_%H%M%S}.wav")
        self.engine.set_record(True, path); self.recording = path
        self.toast.emit("Recording started: " + path); self.changed.emit(); return path

    def set_mode_enabled(self, net: str, on: bool):
        """The person switches a mode on or off from the network tabs. A mode that is off is stopped at once and cannot be started."""
        off = set(self.store.settings.get("modes_off", []) or []); (off.discard if on else off.add)(net)
        self.store.settings["modes_off"] = sorted(off); self.store.save_settings()
        self.policy.user_off = off
        for r in list(self.rules.rx):
            if not self.policy.allows(r.target.net): self.rules.stop_listening(r.handle); self.engine.stop_rx(r.handle)
        t = self.rules.tx_target
        if self.rules.tx_connected and t is not None and not self.policy.allows(t.net):
            self.rules.disconnect_tx(); self.engine.ptt(False); self.engine.disconnect_tx()
        self.policy_changed.emit(); self.changed.emit()

    def apply_policy(self, pol) -> bool:
        """The server's modes/transmit policy (from the signed licence answer). Whatever is now closed is stopped at once. Returns True when it changed."""
        from .policy import Policy
        new = Policy(pol)
        if new == self.policy: return False
        old, self.policy = self.policy, new
        msg = ""
        for r in list(self.rules.rx):
            if not new.allows(r.target.net): self.rules.stop_listening(r.handle); self.engine.stop_rx(r.handle); msg = new.reason()
        t = self.rules.tx_target
        if self.rules.tx_connected and t is not None and (not new.allows(t.net) or not new.tx):
            self.rules.disconnect_tx(); self.engine.ptt(False); self.engine.disconnect_tx(); msg = msg or (new.reason() if not new.allows(t.net) else new.tx_reason())
        if msg: self.note_problem(msg); self.toast.emit(msg)
        self.policy_changed.emit(); self.changed.emit(); return True

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
            if t.net == "DMR" and msg in DMR_REFUSALS and msg not in ("DMR_NO_HOST", "DMR_NO_REWIND"):
                try:
                    from .engine_client import hotspot_id
                    if getattr(ln, "rewind", False): text += " " + tr("DMR ID sent:") + f" {int(self.store.settings.get('dmr_id'))}"          # BrandMeister terminal login: the plain ID, no ESSID
                    else: text += " " + tr("Hotspot ID sent:") + f" {hotspot_id(self.store.settings.get('dmr_id'), self.store.settings.get('essid'))}"     # compare with My devices in SelfCare
                except Exception: pass
            if t.net == "DMR" and "no answer" in (msg or "").lower():
                text += tr(" — DMR: check the master address, your DMR ID and your personal hotspot password (BrandMeister SelfCare › Hotspot Security).")
            self.note_problem(f"{t.name or t.id}: {text}"); self.toast.emit(f"{t.name or t.id}: {text}")
        self.changed.emit()

    def _on_heard(self, ln, e: dict):
        st = e.get("state"); key = (ln.target.net, ln.target.id)
        if st in ("new", "streaming"):
            for r in self.rules.rx:
                if r.handle in ln.rx: r.reports_traffic = True
            src, srcid = self._talker(ln, e)
            dst = (e.get("dst", "") or "").strip()
            if not dst.strip("*"): dst = ""                      # YSF sends '**********' = 'everyone': show nothing instead of stars
            now = self.utc_now()
            tk = self.talking.get(key)
            if tk is None or tk.get("stream_src") != src: self.talking[key] = dict(src=src, stream_src=src, srcid=srcid, since=now)
            cur = next((h for h in self.last_heard[:6] if h["net"] == ln.target.net and h["stream_src"] == src), None)
            if cur is not None and (now - cur["last"]).total_seconds() < 4:
                cur["last"] = now                                  # same transmission goes on (the engine reports every frame) -> one row
                if dst and not cur["dst"]: cur["dst"] = dst
            else:
                from . import diag; diag.log(f"heard {src} -> {dst} via {e.get('gw', '')} on {ln.target.net}:{ln.target.id}")
                mine = (self.store.settings.get("callsign") or "").strip().upper()
                self.last_heard.insert(0, dict(src=src, dst=dst, gw=(e.get("gw", "") or "").strip(), net=ln.target.net, target=ln.target.id,
                                              stream_src=src, srcid=srcid, ts=now, last=now, me=bool(mine) and mine in src.upper().replace(" ", "").split("/")))
                del self.last_heard[60:]
        elif st in ("end", "lost"):
            for r in self.rules.rx:
                if r.handle in ln.rx: r.reports_traffic = False
            self.talking.pop(key, None)
        self.changed.emit()

    # ---- who is talking: DMR gives only the DMR ID, the callbook turns it into a callsign ----------------
    def _talker(self, ln, e: dict):
        """(text shown, DMR ID or 0). Other modes send the callsign themselves; DMR sends only the ID (the engine's 'callsign' field is OUR own)."""
        srcid = int(e.get("srcid") or 0)
        src = (e.get("src") or "").strip()
        net = ln.target.net
        if net in ("NXDN", "P25") and srcid and (not src or src.isdigit()):
            # NXDN / P25 send only a number. Our own number is our own call sign; a number of 7+ digits is looked up in the RadioID database, which
            # issues the same registered IDs (a short number, such as 31, is not a registered ID and is left as it is: nothing is guessed)
            s = self.store.settings; own = str(s.get("nxdn_id" if net == "NXDN" else "dmr_id") or "").strip()
            if own.isdigit() and int(own) == srcid and (s.get("callsign") or "").strip(): return s["callsign"].strip().upper(), srcid
            if srcid >= 1000000:
                info = self.callbook.cached(srcid)
                if info is None: self._ask_station(srcid)
                return (info["call"] if info else (src or str(srcid))), srcid
        if net == "DMR" and srcid:
            info = self.callbook.cached(srcid)
            if info is None: self._ask_station(srcid)
            return (info["call"] if info else (src or str(srcid))), srcid
        if not src and srcid: return str(srcid), srcid
        return (src or e.get("callsign") or "?"), srcid

    def _ask_station(self, did: int):
        if self.callbook.needs_fetch(did):
            self.callbook.ask(did, lambda d, info: (not self.closing) and self._station_done.emit(d, info))

    def _on_station(self, did: int, info):
        """The callbook answered: the ID on the cards / in Last heard becomes the callsign."""
        if not info: self.changed.emit(); return
        for h in self.last_heard:
            if h.get("srcid") == did and h["src"] == str(did):
                h["src"] = info["call"]; h["stream_src"] = info["call"]
                mine = (self.store.settings.get("callsign") or "").strip().upper(); h["me"] = bool(mine) and mine in info["call"].upper().split("/")
        for t in self.talking.values():
            if t.get("srcid") == did: t["src"] = info["call"]; t["stream_src"] = info["call"]
        self.changed.emit()

    def station_info(self, did: int) -> dict | None:
        """What the callbook knows about a DMR ID (None: unknown / not answered yet)."""
        return self.callbook.cached(did) if did else None

    def talker(self, t: Target) -> dict | None:
        """The station talking on this target right now: dict(src, srcid, name, country...) or None."""
        tk = self.talking.get((t.net, t.id))
        if not tk: return None
        out = dict(tk); info = self.station_info(tk.get("srcid") or 0)
        if info: out.update(name=info["name"], country=info["country"], city=info["city"], state=info["state"])
        return out

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
