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
        self.proc = QtCore.QProcess(self)
        self.proc.setProgram(path)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.started.connect(self._flush)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)
        self.proc.start()

    def _flush(self):
        for b in self._queue: self.proc.write(b)
        self._queue.clear()

    def _on_finished(self, *_):
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

    def __init__(self, path: str, store, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.path, self.store = path, store
        self.servers = Servers(store)
        self.links: dict[str, Link] = {}
        self._level = 0.0
        self._decay = QtCore.QTimer(self); self._decay.setInterval(100)
        self._decay.timeout.connect(lambda: setattr(self, "_level", self._level * 0.7)); self._decay.start()
        self.dmr_password = ""

    # ---- helpers ----------------------------------------------------------
    def _params(self, t: Target) -> tuple[dict | None, str]:
        s = self.store.settings
        proto = protocol_for(t)
        if not proto: return None, "EchoLink is not available in this build yet."
        call = (s.get("callsign") or "").strip().upper()
        if not call: return None, "Enter your callsign first (Settings › Station)."
        ep = self.servers.resolve(t)
        if not ep: return None, "NEED_ENDPOINT"
        p = dict(mode=proto, host=ep["host"], port=ep["port"], callsign=call, name=t.id, vocoder="Software vocoder")
        if proto == "DMR":
            if not str(s.get("dmr_id") or "").strip().isdigit(): return None, "A DMR ID is required for DMR (Settings › Radio networks)."
            p.update(dmrid=int(s["dmr_id"]), essid=int(s.get("essid") or 0) if str(s.get("essid") or "0").isdigit() else 0,
                     password=self.dmr_password, tg=int(t.id) if t.id.isdigit() else 0, cc=int(s.get("cc") or 1), slot=int(s.get("slot") or 2))
        elif proto in ("REF", "XRF", "DCS"):
            ref, mod = split_dstar(t); p.update(name=ref, module=mod)
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
        ln.send("connect", **params)
        return ln, ""

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

    def mic_level(self): return min(1.0, self._level / 20000.0)

    def set_rx_volume(self, handle, vol: float):
        for ln in self.links.values():
            if handle in ln.rx: ln.send("out_volume", out=max(0.0, min(1.0, vol)))

    def shutdown(self):
        for ln in list(self.links.values()): ln.close()
        self.links.clear()

    # ---- events ---------------------------------------------------------------
    def _on_event(self, ln: Link, e: dict):
        ev = e.get("ev")
        if ev == "status":
            ln.state = e.get("state", ln.state)
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
