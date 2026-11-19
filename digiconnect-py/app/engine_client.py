"""EngineClient: runs the protocol engine (dcengine) as separate helper processes.

One helper process per link (network + destination). A link is shared by its roles: any number
of Listen receivers and the one Connect(TX). The helper lives while it has at least one role.
If the engine crashes, only that link is lost and the UI reports it; the UI never freezes."""
import json, math, os, sys
from pathlib import Path
from .qt import QtCore, Signal
from .engine import Engine
from .rules import Target
from .servers import Servers, protocol_for, split_dstar


def find_engine() -> str | None:
    """The engine to run: an updated one (app/engine_update.py) when a good one is installed, else the one of the installer."""
    if not os.environ.get("DC_ENGINE"):
        from . import engine_update
        try: c = engine_update.current()
        except Exception: c = None
        if c: return c["path"]
    return builtin_engine()


def builtin_engine() -> str | None:
    """The engine that came with the installer."""
    exe = "dcengine.exe" if sys.platform.startswith("win") else "dcengine"
    cands = []
    if os.environ.get("DC_ENGINE"): cands.append(Path(os.environ["DC_ENGINE"]))
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    exed = Path(sys.executable).parent
    for d in (base, base / "engine", base / "engine" / "bin", base / "bin", exed, exed / "engine", exed / "engine" / "bin", exed.parent / "Resources", exed.parent / "Resources" / "engine"):   # Linux package: engine/bin/dcengine
        cands.append(d / exe)
        cands.append(d / "dcengine.app" / "Contents" / "MacOS" / "dcengine")   # macOS bundle
    for c in cands:
        if c.is_file(): return str(c)
    return None


def check_updated_engine(client) -> None:
    """At start-up, in the background: an engine that came from an update must still start (an antivirus or a damaged disk can spoil files later).
    If it does not, it is marked bad and the client uses the installer's engine again."""
    import threading
    def work():
        from . import engine_update, diag
        try:
            c = engine_update.current()
            if not c or os.path.normcase(os.path.abspath(client.path)) != os.path.normcase(os.path.abspath(c["path"])): return
            if engine_update.hello(c["path"]): return
        except Exception: return
        engine_update.mark_bad(c["version"]); back = builtin_engine()
        diag.log(f"start-up check: updated engine {c['version']} does not start, using the installer's engine ({back})")
        if back: client.path = back
    threading.Thread(target=work, daemon=True).start()


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
        self.rewind = False                     # BrandMeister Rewind login (the DMR ID is sent without ESSID)
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


def grid_center(loc) -> tuple[float, float] | None:
    """Centre of a Maidenhead locator (4, 6 or 8 characters) as (lat, lon); None when it is not a locator."""
    t = str(loc or "").strip().upper()
    if len(t) not in (4, 6, 8) or not (t[0:2].isalpha() and t[0] in "ABCDEFGHIJKLMNOPQR" and t[1] in "ABCDEFGHIJKLMNOPQR" and t[2:4].isdigit()): return None
    lon = (ord(t[0]) - 65) * 20 - 180 + int(t[2]) * 2; lat = (ord(t[1]) - 65) * 10 - 90 + int(t[3]); w, h = 2.0, 1.0
    if len(t) >= 6:
        if not (t[4:6].isalpha() and "A" <= t[4] <= "X" and "A" <= t[5] <= "X"): return None
        w, h = 2 / 24, 1 / 24; lon += (ord(t[4]) - 65) * w; lat += (ord(t[5]) - 65) * h
    if len(t) == 8:
        if not t[6:8].isdigit(): return None
        w, h = w / 10, h / 10; lon += int(t[6]) * w; lat += int(t[7]) * h
    return round(lat + h / 2, 6), round(lon + w / 2, 6)


# What the station tells a DMR master when it logs in (the Homebrew "RPTC" packet): position, frequency, text. Some masters (BrandMeister) refuse
# the login at this last step when they dislike these values, so a refusal (DMR_NAK_CONFIG) is retried at once with the next set; the set that
# was accepted is remembered. 0 = what a real hotspot sends (the position from the locator in Settings), 1 = another frequency, 2 = the plain old set.
DMR_CFG_LAST = 2


def dmr_station_config(settings: dict, variant: int, version: str = "") -> dict:
    pos = grid_center(settings.get("locator"))
    loc = (settings.get("locator") or "").strip().upper()
    if variant >= 2 or pos is None: lat, lon, where = "0", "0", ""
    else: lat, lon, where = f"{pos[0]:.6f}", f"{pos[1]:.6f}", loc
    return dict(lat=lat, lon=lon, location=where, description="DigiConnect", url="https://hellaszone.com/digiconnect",
                freq="434000000" if variant == 1 else "438800000", swid="DigiConnect", pkgid="DigiConnect " + version if version else "DigiConnect")


# BrandMeister does not accept the Homebrew protocol from a program that has no radio: it answers the login and then refuses the station settings.
# Software clients (VoxDMR, ubDMR ...) use BrandMeister's own "Rewind" protocol (Open DMR Terminal Protocol) on UDP 54006, with the plain DMR ID
# (no ESSID) and the hotspot password. The engine falls back to the older port 54005 when 54006 does not answer. Setting dmr_protocol: auto | homebrew | rewind.
REWIND_PORT = 54006


def uses_rewind(settings: dict, host: str, hosts=None) -> bool:
    mode = str(settings.get("dmr_protocol") or "auto").lower()
    if mode in ("homebrew", "rewind"): return mode == "rewind"
    h = (host or "").strip().lower()
    if h.endswith(".brandmeister.network"): return True
    try: return bool(hosts is not None and hosts.is_brandmeister(h))
    except Exception: return False


def essid_for_engine(text) -> int:
    """The ESSID as people know it (Pi-Star / MMDVM / BrandMeister SelfCare): empty = none (the hotspot id is the DMR ID itself), otherwise the two
    digits are appended: DMR ID 2407219 + ESSID 22 = hotspot id 240721922, ESSID 00 = 240721900. The engine counts like DroidStar (0 = none, n = suffix n-1),
    so the suffix goes in as suffix+1. A wrong suffix means a hotspot id without the password the user set in SelfCare, and BrandMeister refuses it."""
    t = str(text if text is not None else "").strip()
    return min(int(t), 99) + 1 if t.isdigit() else 0


def hotspot_id(dmr_id, essid_text) -> int:
    """The id the master sees (shown to the user in the login log)."""
    e = essid_for_engine(essid_text); return int(dmr_id) * 100 + (e - 1) if e else int(dmr_id)


class EngineClient(QtCore.QObject, Engine):
    name = "dcengine"
    status = Signal(object, str, str)     # (link, state, message)
    heard = Signal(object, dict)          # (link, rx event)
    nodetext = Signal(object, str)        # (link, text a station sent: greeting / who is connected)
    notice = Signal(str)                  # an engine warning for the user (e.g. the microphone delivers no sound)
    volume_refresh = Signal()             # a link just connected: re-send the receive volumes
    mic_wave = Signal(object, bool, float)  # (samples -1..1, gate open, limiter gain in dB) from the microphone while transmitting
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
    def cfg_variant(self) -> int:
        """The set of station values to log in with: the one that was accepted last time, else 0."""
        try: return max(0, min(int(self.store.settings.get("dmr_cfg_variant") or 0), DMR_CFG_LAST))
        except (TypeError, ValueError): return 0

    def _retry_dmr_config(self, ln: "Link") -> bool:
        """The master accepted the id and the password but refused the station values: log in again, at once, with the next set. The listening/transmit
        choices of the refused link move to the new one, so the user only sees that the connection took a moment longer."""
        v = ln.cfg_variant + 1
        if ln.target.net != "DMR" or v > DMR_CFG_LAST or self.links.get(ln.key) is not ln: return False
        rx, tx, key, target = set(ln.rx), ln.tx, ln.key, ln.target
        from . import diag; diag.log(f"engine {key}: the master refused the station values (set {ln.cfg_variant}); trying set {v}")
        self.links.pop(key, None); ln.rx.clear(); ln.tx = False; ln.superseded = True; ln.close()
        nl, err = self._link(target, v)
        if nl is None: return False
        nl.rx |= rx; nl.tx = tx
        return True

    def _params(self, t: Target, variant: int | None = None) -> tuple[dict | None, str]:
        s = self.store.settings
        proto = protocol_for(t)
        if not proto: return None, "This network is not available."
        if proto == "ELINK" and not self.servers.resolve(t): return None, "Sign in to EchoLink on the EchoLink page and pick a station from the list first."
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
                    return None, "BrandMeister needs your personal hotspot password: enter it in Settings › Radio networks, field Password (BrandMeister SelfCare › Hotspot Security), then connect again."
                hosts = getattr(self.servers, "hosts", None)
                pw = hosts.dmr_default_password(host) if hosts is not None else ""       # other masters: the password the host list gives, like Pi-Star
            p.update(dmrid=int(s["dmr_id"]), essid=essid_for_engine(s.get("essid")),
                     password=pw, tg=int(t.id) if t.id.isdigit() else 0, cc=int(s.get("cc") or 1), slot=int(s.get("slot") or 2))
            v = self.cfg_variant() if variant is None else variant; p.update(dmr_station_config(s, v, "")); p["_variant"] = v
            if uses_rewind(s, host, getattr(self.servers, "hosts", None)): p.update(rewind=True, rewind_port=REWIND_PORT)
        elif proto in ("REF", "XRF", "DCS", "M17"):
            ref, mod = split_dstar(t); p.update(name=ref, module=mod)
        elif proto == "IAX":
            user = (s.get("asl_user") or call).strip()
            if not allstar.valid_user(user): return None, "Enter your AllStarLink portal username on the AllStar page (your callsign)."
            if not self.asl_password: return None, "Enter your AllStarLink portal password on the AllStar page."
            p.update(name=t.id.strip(), iax_user=allstar.PUBLIC_USER, iax_pass=allstar.PUBLIC_SECRET, asl_user=user)
        elif proto == "ELINK":
            p.update(name=t.id.strip().upper(), el_name=str(s.get("op_name") or ""), el_loc=str(s.get("echolink_loc") or ""))
        elif proto == "NXDN":
            if not str(s.get("nxdn_id") or "").strip().isdigit(): return None, "An NXDN ID is required for NXDN (Settings › Radio networks)."
            p.update(nxdnid=int(s["nxdn_id"]), name=t.id.strip())
        elif proto == "P25":
            if not str(s.get("dmr_id") or "").strip().isdigit(): return None, "A radio ID is required for P25: enter your DMR ID (Settings › Radio networks)."
            p.update(dmrid=int(s["dmr_id"]), name=t.id.strip())
        return p, ""

    def _link(self, t: Target, variant: int | None = None) -> tuple[Link | None, str]:
        key = f"{t.net}:{t.id}"
        if key in self.links: return self.links[key], ""
        params, err = self._params(t, variant)
        if params is None: return None, err
        if not os.path.isfile(self.path): return None, "Protocol engine not found."
        ln = Link(key, t, self.path, self); ln.cfg_variant = params.pop("_variant", 0); ln.rewind = bool(params.get("rewind"))
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
        if protocol_for(target) not in ("IAX", "ELINK"): return "DTMF is available for AllStarLink nodes and EchoLink stations."
        ln.send("dtmf", keys=keys); return ""

    def set_record(self, on: bool, path: str = ""):
        """Recording of the received audio: starts or stops it in every running engine (and on the next connection)."""
        self.record_state = (bool(on), path)
        for ln in self.links.values(): ln.send("record", on=bool(on), path=path)

    def set_mic(self, settings: dict):
        """Microphone processing from the Microphone page: sent to every running engine now and on each new connection."""
        self.mic_settings = dict(settings)
        for ln in self.links.values(): ln.send("mic", settings=self.mic_settings)

    def mic_gain(self) -> float:
        """Microphone level from the settings (percent; 100 = device level, above 100 = software gain)."""
        try: return max(0.0, min(6.0, float(self.store.settings.get("mic_gain", 100)) / 100.0))
        except (TypeError, ValueError): return 1.0

    def set_mic_gain(self, pct: float):
        self.store.settings["mic_gain"] = int(pct)
        for ln in self.links.values(): ln.send("volume", **{"in": self.mic_gain()})

    def rx_level(self):
        """The engine reports one audio peak (0..32767): while nobody transmits it is the received audio, while I transmit it is my microphone.
        Shown on a dB scale like every audio meter (-50 dBFS = empty, 0 dBFS = full): ordinary speech peaks around -20 dBFS and so fills over half of the bar
        (a linear scale showed only 9-10 % for a normal voice)."""
        p = float(self._level)
        if p < 1: return 0.0
        return max(0.0, min(1.0, (20.0 * math.log10(p / 32768.0) + 50.0) / 50.0))
    def mic_level(self): return self.rx_level()

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
        if getattr(ln, "superseded", False): return                     # the link that was replaced by a retry: its last words are not news
        ev = e.get("ev")
        if ev == "warn":
            self.notice.emit(e.get("msg", "")); return
        if ev == "nodetext":
            self.nodetext.emit(ln, e.get("text", "")); return
        if ev == "log":
            from . import diag; diag.log(f"engine {ln.key}: {e.get('text', '')}"); return          # e.g. the steps of a DMR login (never the password)
        if ev in ("status", "error"):
            from . import diag; diag.log(f"engine {ln.key}: {ev} {e.get('state', '')} {e.get('msg', '')}")
        if ev == "status" and e.get("state") == "error" and e.get("msg") == "The protocol engine could not be started" and self._updated_engine_failed():
            ln.rx.clear(); ln.tx = False; self.links.pop(ln.key, None); ln.close(); self.status.emit(ln, "error", "The updated protocol engine could not start; the installer's engine is used now. Connect again."); return
        if ev == "status" and e.get("state") == "error" and e.get("msg") == "DMR_NAK_CONFIG" and self._retry_dmr_config(ln): return
        if ev == "status":
            ln.state = e.get("state", ln.state)
            if ln.state == "connected" and ln.target.net == "DMR" and self.cfg_variant() != ln.cfg_variant:
                self.store.settings["dmr_cfg_variant"] = ln.cfg_variant; self.store.save_settings()          # this set was accepted: start with it next time
            if ln.state == "connected":
                self.__dict__.pop("_resend", None); ln.send("volume", **{"in": self.mic_gain()}); ln.send("mic", settings=getattr(self, "mic_settings", {})); st = getattr(self, "record_state", (False, "")); ln.send("record", on=st[0], path=st[1]); self.volume_refresh.emit()
            self.status.emit(ln, ln.state, e.get("msg", ""))
            if ln.state in ("error", "timeout", "disconnected"):
                ln.rx.clear(); ln.tx = False; self._release(ln)
        elif ev == "rx":
            self.heard.emit(ln, e)
        elif ev == "level":
            self._level = max(self._level, float(e.get("out", 0)))
        elif ev == "wave":
            self.mic_wave.emit(list(e.get("s", [])), bool(e.get("gate", True)), float(e.get("lim", 0.0)))

    def _updated_engine_failed(self) -> bool:
        """The engine in use came from an update and could not be started: drop it for good and go back to the installer's engine. True when that was the case."""
        from . import engine_update, diag
        try: c = engine_update.current()
        except Exception: c = None
        if not c or os.path.normcase(os.path.abspath(self.path)) != os.path.normcase(os.path.abspath(c["path"])): return False
        engine_update.mark_bad(c["version"]); back = builtin_engine()
        diag.log(f"updated engine {c['version']} could not be started: marked bad, using the installer's engine ({back})")
        if back: self.path = back
        self.notice.emit("The updated protocol engine could not start, so DigiConnect went back to the one that came with the installer. Connect again.")
        return True

    def _on_finished(self, ln: Link):
        if self.links.get(ln.key) is ln:
            self.status.emit(ln, "error", "The protocol engine stopped unexpectedly. Licence › Send diagnostics to the owner shows why.")
            ln.rx.clear(); ln.tx = False; self.links.pop(ln.key, None)
