"""EngineClient: runs the protocol engine (dcengine) as separate helper processes.

One helper process per link (network + destination). A link is shared by its roles: any number
of Listen receivers and the one Connect(TX). The helper lives while it has at least one role.
If the engine crashes, only that link is lost and the UI reports it; the UI never freezes."""
import json, os, sys
from pathlib import Path
from .qt import QtCore, Signal
from .engine import Engine
from .rules import Target
from .servers import Servers, protocol_for, split_dstar


def find_engine() -> str | None:
    exe = "dcengine.exe" if sys.platform.startswith("win") else "dcengine"
    cands = []
    if os.environ.get("DC_ENGINE"): cands.append(Path(os.environ["DC_ENGINE"]))
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    exed = Path(sys.executable).parent
    for d in (base, base / "engine", base / "bin", exed, exed / "engine", exed.parent / "Resources", exed.parent / "Resources" / "engine"):
        cands.append(d / exe)
        cands.append(d / "dcengine.app" / "Contents" / "MacOS" / "dcengine")   # macOS bundle
    for c in cands:
        if c.is_file(): return str(c)
    return None


def clean_engine_env():
    """Environment for the protocol engine: it has its own Qt, so variables that point to ANOTHER Qt (the Python UI's PySide6, a CI/SDK Qt)
    or to the PyInstaller bundle must not reach it - otherwise it can load the wrong libraries/plugins and stall (seen on macOS arm64)."""
    import sys
    env = QtCore.QProcessEnvironment.systemEnvironment()
    for k in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH", "QT_ROOT_DIR", "QT_DEBUG_PLUGINS",
              "DYLD_FRAMEWORK_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        env.remove(k)
    if getattr(sys, "frozen", False) and env.contains("LD_LIBRARY_PATH"):          # PyInstaller on Linux prepends its own folder
        orig = env.value("LD_LIBRARY_PATH_ORIG")
        env.insert("LD_LIBRARY_PATH", orig) if orig else env.remove("LD_LIBRARY_PATH")
    return env


class Link(QtCore.QObject):
    event = Signal(object, dict)          # (link, event)
    finished = Signal(object)

    def __init__(self, key, target: Target, path: str, parent=None):
        super().__init__(parent)
        self.key, self.target = key, target
        self.rx: set[int] = set()
        self.tx = False
        self.state = "connecting"
        self._buf = b""
        self._queue: list[bytes] = []           # commands sent before the process finished starting
        self._alive = True
        self._errn = 0
        self.proc = QtCore.QProcess(self)
        self.proc.setProgram(path)
        self.proc.setProcessEnvironment(clean_engine_env())
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.readyReadStandardError.connect(self._read_err)
        self.proc.started.connect(self._flush)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)
        self.proc.start()

    def _flush(self):
        for b in self._queue: self.proc.write(b)
        self._queue.clear()

    def _on_finished(self, code=0, status=None, *_):
        from . import diag
        diag.log(f"engine process {self.key if hasattr(self, 'key') else ''} ended: exit code {code}, {'crashed' if status == QtCore.QProcess.ExitStatus.CrashExit else 'normal exit'}, expected={not self._alive}")
        if self._alive: self.finished.emit(self)

    def _on_error(self, err):
        if self._alive and err == QtCore.QProcess.ProcessError.FailedToStart:
            self.event.emit(self, {"ev": "status", "state": "error", "msg": "The protocol engine could not be started"})

    def send(self, cmd: str, **kw):
        data = (json.dumps(dict(cmd=cmd, **kw)) + "\n").encode()
        st = self.proc.state()
        if st == QtCore.QProcess.ProcessState.Running: self.proc.write(data)
        elif st == QtCore.QProcess.ProcessState.Starting: self._queue.append(data)

    def _read(self):
        self._buf += bytes(self.proc.readAllStandardOutput())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if line.startswith(b"{"):
                try: self.event.emit(self, json.loads(line))
                except ValueError: pass

    def _read_err(self):
        """The engine's own diagnostics (stderr): into digiconnect.log; 'DCWARN:' lines are also shown to the user."""
        from . import diag
        for raw in bytes(self.proc.readAllStandardError()).decode("utf-8", "replace").splitlines():
            line = raw.strip()
            if not line: continue
            if self._errn < 400: diag.log("engine stderr: " + line); self._errn += 1
            if "DCWARN:" in line: self.event.emit(self, {"ev": "warn", "msg": line.split("DCWARN:", 1)[1].strip()})

    def close(self):
        self._alive = False            # we asked for this: no 'stopped unexpectedly' report
        self.send("quit")
        proc = self.proc
        def reap():
            try:
                if proc.state() != QtCore.QProcess.ProcessState.NotRunning: proc.kill(); proc.waitForFinished(1000)
            except RuntimeError:
                pass
        QtCore.QTimer.singleShot(2500, reap)


class EngineClient(QtCore.QObject, Engine):
    name = "dcengine"
    status = Signal(object, str, str)     # (link, state, message)
    heard = Signal(object, dict)          # (link, rx event)
    notice = Signal(str)                  # an engine warning for the user (e.g. the microphone delivers no sound)
    volume_refresh = Signal()             # a link just connected: re-send the receive volumes
    _tok_done = Signal(object, str, str)  # (callback, token, error) from the sign-in worker thread -> UI thread

    def __init__(self, path: str, store, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.path, self.store = path, store
        self.servers = Servers(store)
        self.links: dict[str, Link] = {}
        self._level = 0.0
        self._decay = QtCore.QTimer(self); self._decay.setInterval(100)
        self._decay.timeout.connect(lambda: setattr(self, "_level", self._level * 0.7)); self._decay.start()
        self.dmr_password = ""
        self.asl_password = ""                         # AllStarLink portal password (session only)
        self._tok_done.connect(lambda cb, tok, err: cb(tok, err))
        self.token_fn = None                           # tests replace these two; None = the real AllStarLink services
        self.dns_fn = None

    # ---- helpers ----------------------------------------------------------
    def _params(self, t: Target) -> tuple[dict | None, str]:
        s = self.store.settings
        proto = protocol_for(t)
        if not proto: return None, "EchoLink is under construction — coming soon."
        if proto == "IAX":
            from . import allstar
            if not allstar.valid_node(t.id): return None, "Enter a valid AllStarLink node number (digits only)."
        call = (s.get("callsign") or "").strip().upper()
        if not call: return None, "Enter your callsign first (Settings › Station)."
        ep = self.servers.resolve(t)
        if not ep: return None, "NEED_ENDPOINT"
        p = dict(mode=proto, host=ep["host"], port=ep["port"], callsign=call, name=t.id, vocoder="Software vocoder",
                 capture=s.get("mic") or "", playback=s.get("speakers") or "")
        if proto == "DMR":
            if not str(s.get("dmr_id") or "").strip().isdigit(): return None, "A DMR ID is required for DMR (Settings › Radio networks)."
            host = str(ep["host"]).lower(); pw = (self.dmr_password or "").strip()          # a pasted password often carries a trailing space/newline: the master would refuse it
            if not pw:
                if "brandmeister" in host:               # BrandMeister: personal hotspot password (SelfCare > Hotspot Security); the list only has a placeholder
                    return None, "BrandMeister needs your personal hotspot password: enter it in the Password field of the DMR server card (BrandMeister SelfCare › Hotspot Security), then connect again."
                hosts = getattr(self.servers, "hosts", None)
                pw = hosts.dmr_default_password(host) if hosts is not None else ""       # other masters: the password the host list gives, like Pi-Star
            p.update(dmrid=int(s["dmr_id"]), essid=int(s.get("essid") or 0) if str(s.get("essid") or "0").isdigit() else 0,
                     password=pw, tg=int(t.id) if t.id.isdigit() else 0, cc=int(s.get("cc") or 1), slot=int(s.get("slot") or 2))
        elif proto in ("REF", "XRF", "DCS", "M17"):
            ref, mod = split_dstar(t); p.update(name=ref, module=mod)
        elif proto == "IAX":
            user = (s.get("asl_user") or call).strip()
            if not allstar.valid_user(user): return None, "Enter your AllStarLink portal username on the AllStar page (your callsign)."
            if not self.asl_password: return None, "Enter your AllStarLink portal password on the AllStar page."
            p.update(name=t.id.strip(), iax_user=allstar.PUBLIC_USER, iax_pass=allstar.PUBLIC_SECRET, asl_user=user)
        elif proto == "NXDN":
            if not str(s.get("nxdn_id") or "").strip().isdigit(): return None, "An NXDN ID is required for NXDN (Settings › Radio networks)."
            p.update(nxdnid=int(s["nxdn_id"]), name=t.id.strip())
        elif proto == "P25":
            if not str(s.get("dmr_id") or "").strip().isdigit(): return None, "A radio ID is required for P25: enter your DMR ID (Settings › Radio networks)."
            p.update(dmrid=int(s["dmr_id"]), name=t.id.strip())
        return p, ""

    def _link(self, t: Target) -> tuple[Link | None, str]:
        key = f"{t.net}:{t.id}"
        if key in self.links: return self.links[key], ""
        params, err = self._params(t)
        if params is None: return None, err
        if not os.path.isfile(self.path): return None, "Protocol engine not found."
        ln = Link(key, t, self.path, self)
        ln.event.connect(self._on_event); ln.finished.connect(self._on_finished)
        self.links[key] = ln
        from . import diag; diag.log("connect " + key + " " + str({k: v for k, v in params.items() if k not in ("password", "iax_name")}))
        if params["mode"] == "IAX": self._prepare_allstar(ln, t, params)
        else: ln.send("connect", **params)
        return ln, ""

    # ---- AllStarLink: address from DNS + single-use token, both before the call --------------------------------
    def _prepare_allstar(self, ln: Link, t: Target, params: dict):
        from . import allstar
        node, user, pw = t.id.strip(), params.pop("asl_user"), self.asl_password
        res = {}
        def step():
            if "ep" not in res or "tok" not in res: return
            if self.links.get(ln.key) is not ln: return                  # cancelled meanwhile (Listen/Connect switched off)
            tok, err = res["tok"]
            if not tok:
                self.status.emit(ln, "error", err); ln.rx.clear(); ln.tx = False; self.links.pop(ln.key, None); ln.close(); return
            host, port = res["ep"]
            params.update(host=host, port=port, iax_name=allstar.caller_name(tok, user))
            ln.send("connect", **params)
        def got_ep(host, port): res["ep"] = (host, port); step()
        def got_tok(tok, err): res["tok"] = (tok, err); step()
        self.status.emit(ln, "connecting", "Signing in to AllStarLink…")
        user_ep = self.servers.user.get(self.servers.key(t))
        if user_ep: got_ep(user_ep["host"], int(user_ep["port"]))
        else: (self.dns_fn or allstar.srv_lookup)(node, got_ep)
        cid = allstar.client_id(self.store)
        def work():
            fn = self.token_fn or allstar.request_token
            try: tok, err = fn(user, pw, cid)
            except Exception as ex: tok, err = "", f"AllStarLink sign-in failed: {ex}"
            self._tok_done.emit(got_tok, tok, err)
        import threading; threading.Thread(target=work, daemon=True).start()

    def _release(self, ln: Link):
        if not ln.rx and not ln.tx and self.links.get(ln.key) is ln:
            del self.links[ln.key]; ln.close()

    # ---- Engine interface ---------------------------------------------------
    def start_rx(self, handle, target):
        ln, err = self._link(target)
        if ln is None: return err
        ln.rx.add(handle)
        return "" if ln.state != "connected" else "Connected"

    def stop_rx(self, handle):
        for ln in list(self.links.values()):
            if handle in ln.rx: ln.rx.discard(handle); self._release(ln)

    def connect_tx(self, target):
        self.disconnect_tx()
        ln, err = self._link(target)
        if ln is None: return err
        ln.tx = True
        return ""

    def disconnect_tx(self):
        for ln in list(self.links.values()):
            if ln.tx: ln.send("ptt", on=False); ln.tx = False; self._release(ln)

    def ptt(self, on):
        for ln in self.links.values():
            if ln.tx and ln.state == "connected": ln.send("ptt", on=bool(on))

    def send_dtmf(self, target, keys: str) -> str:
        """DTMF digits to the node of this target (AllStarLink uses them to control the node). Returns '' or the reason it was not sent."""
        ln = self.links.get(f"{target.net}:{target.id}")
        if ln is None or ln.state != "connected": return "DTMF can only be sent while the connection to that node is up."
        if protocol_for(target) != "IAX": return "DTMF is available for AllStarLink nodes."
        ln.send("dtmf", keys=keys); return ""

    def mic_gain(self) -> float:
        """Microphone level from the settings (percent; 100 = device level, above 100 = software gain)."""
        try: return max(0.0, min(4.0, float(self.store.settings.get("mic_gain", 100)) / 100.0))
        except (TypeError, ValueError): return 1.0

    def set_mic_gain(self, pct: float):
        self.store.settings["mic_gain"] = int(pct)
        for ln in self.links.values(): ln.send("volume", **{"in": self.mic_gain()})

    def mic_level(self): return min(1.0, self._level / 20000.0)

    def tx_only_links(self):
        """Connected links that only transmit (Connect TX, no Listen): they still receive audio from the server, so they need the volume/mute too."""
        return [ln for ln in self.links.values() if ln.tx and not ln.rx and ln.state == "connected"]

    def set_rx_volume(self, handle, vol: float):
        for ln in self.links.values():
            if handle in ln.rx: ln.send("out_volume", out=max(0.0, min(1.0, vol)))

    def shutdown(self):
        for ln in list(self.links.values()): ln.close()
        self.links.clear()

    # ---- events ---------------------------------------------------------------
    def _on_event(self, ln: Link, e: dict):
        ev = e.get("ev")
        if ev == "warn":
            self.notice.emit(e.get("msg", "")); return
        if ev == "log":
            from . import diag; diag.log(f"engine {ln.key}: {e.get('text', '')}"); return          # e.g. the steps of a DMR login (never the password)
        if ev in ("status", "error"):
            from . import diag; diag.log(f"engine {ln.key}: {ev} {e.get('state', '')} {e.get('msg', '')}")
        if ev == "status":
            ln.state = e.get("state", ln.state)
            if ln.state == "connected": self.__dict__.pop("_resend", None); ln.send("volume", **{"in": self.mic_gain()}); self.volume_refresh.emit()
            self.status.emit(ln, ln.state, e.get("msg", ""))
            if ln.state in ("error", "timeout", "disconnected"):
                ln.rx.clear(); ln.tx = False; self._release(ln)
        elif ev == "rx":
            self.heard.emit(ln, e)
        elif ev == "level":
            self._level = max(self._level, float(e.get("out", 0)))

    def _on_finished(self, ln: Link):
        if self.links.get(ln.key) is ln:
            self.status.emit(ln, "error", "The protocol engine stopped unexpectedly.")
            ln.rx.clear(); ln.tx = False; self.links.pop(ln.key, None)
