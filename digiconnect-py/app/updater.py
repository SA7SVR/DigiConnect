"""Automatic updates, like HAM Digi: no re-install.

Flow: ask the server's manifest.php (this installation's id, version, OS) -> if a newer package exists: download it, check
size + SHA-256, unpack it into <data>/updates/v<version>/ and switch current.json to it. The new code starts at the next
launch (bootstrap.activate), or at once when the user presses Restart. Nothing is replaced in place, so a bad update can
always be dropped (bootstrap rolls back automatically if the new code fails to start).

Package (.dcpkg) = gzip(JSON): {"app":"digiconnect-py","format":2,"version":"2.0.1","minShell":"2.0.0","files":{"app/x.py":"<base64>",...}}.
Only app/ and assets/ and LICENSES/ may be written. A package that needs a newer shell (engine / Qt) is not installed;
the user is told that a full installer is needed."""
import base64, gzip, hashlib, json, platform, shutil, sys, threading, uuid, os
from pathlib import Path
from .qt import QtCore, Signal
from . import net
import bootstrap
from .version import APP_VERSION

DEFAULT_URL = "https://hellaszone.com/digiconnect/manifest.php"
ALLOWED = ("app/", "assets/", "LICENSES/")
MAX_PKG = 64 * 1024 * 1024


class UpdateError(Exception): pass


def store_lang(store) -> str:
    try: return str(store.settings.get("language") or "")
    except Exception: return ""


def running_version(root: Path) -> str:
    """The version of the code that is executing now: the unpacked update when this process was started from it, else the shell's own."""
    f = (sys.modules.get("app").__file__ or "") if "app" in sys.modules else ""
    c = bootstrap.current(root)
    return c["version"] if c and str(root / c["dir"]) in f and bootstrap.newer(c["version"], APP_VERSION) else APP_VERSION


def notes_for(m: dict, lang: str = "") -> list:
    """The release notes of a manifest as a list of lines. 'notes' may be a string, a list, or {language: string|list}; nothing is invented."""
    n = m.get("notes")
    if isinstance(n, dict):
        k = next((k for k in n if lang and str(k).lower() in (lang.lower(), lang[:2].lower(), "el" if lang.lower().startswith(("ελ", "gr")) else "")), None)
        n = n.get(k) if k is not None else (n.get("en") or n.get("English") or next(iter(n.values()), ""))
    if isinstance(n, str): n = [x.strip(" -•\t") for x in n.replace("\r", "").split("\n")]
    return [str(x).strip() for x in (n or []) if str(x).strip()]


def install_package(blob: bytes, root: Path, expect_sha: str = "", expect_size: int = 0, on_step=None) -> dict:
    """Validates and unpacks a .dcpkg. Returns {'version','dir','min_shell'} (also written to current.json). Raises UpdateError.
    on_step('verifying' | 'installing') is called before each phase."""
    if on_step: on_step("verifying")
    if expect_size and len(blob) != expect_size: raise UpdateError("size does not match the manifest")
    if expect_sha and hashlib.sha256(blob).hexdigest().lower() != expect_sha.lower(): raise UpdateError("SHA-256 does not match the manifest")
    try: pkg = json.loads(gzip.decompress(blob).decode("utf-8"))
    except Exception: raise UpdateError("not a valid .dcpkg package")
    if pkg.get("app") != "digiconnect-py" or pkg.get("format") != 2: raise UpdateError("package is not for this program")
    ver = str(pkg.get("version") or ""); files = pkg.get("files")
    if not ver or not all(c.isdigit() or c == "." for c in ver) or not isinstance(files, dict) or "app/__init__.py" not in files:
        raise UpdateError("package is incomplete")
    if on_step: on_step("installing")
    out = {}
    for name, b64 in files.items():
        parts = Path(name).parts
        if name.startswith(("/", "\\")) or ".." in parts or ":" in name or not name.startswith(ALLOWED): raise UpdateError(f"forbidden path {name}")
        data = base64.b64decode(b64); out[name] = data
        if name.endswith(".py"):
            try: compile(data, name, "exec")
            except SyntaxError as e: raise UpdateError(f"{name}: {e.msg} (line {e.lineno})")
    dname = "v" + ver; final = root / dname; tmp = root / (dname + ".new")
    shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(final, ignore_errors=True)
    for name, data in out.items():
        p = tmp / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    os.replace(tmp, final)
    cur = {"version": ver, "dir": dname, "min_shell": str(pkg.get("minShell") or "0")}
    bootstrap._write(root / "current.json", cur)
    bad = bootstrap._read(root / "bad.json", [])
    if ver in bad: bootstrap._write(root / "bad.json", [b for b in bad if b != ver])
    bootstrap.prune(2, root)
    return cur


class Updater(QtCore.QObject):
    changed = Signal(str, str)           # state, message
    progress = Signal(int)               # download percent 0..100 (-1 = size unknown)
    _done = Signal(str, str)
    _pct = Signal(int)

    def __init__(self, store, root: Path | None = None, url: str | None = None, pubkeys: list | None = None):
        super().__init__()
        from . import license as _lic
        self.pubkeys = list(_lic.PUBKEYS if pubkeys is None else pubkeys)                 # an update is accepted only when HELLAS Zone signed it
        self.store, self.root = store, root or bootstrap.updates_root()
        self.url = url or store.settings.get("update_url") or DEFAULT_URL
        self.state, self.message, self.pending = "idle", "", None     # pending = version waiting for a restart
        self.info = {}                    # what the server offers: version, size, notes (list of lines), pkg; empty until a check found something
        self.pct = 0
        self._pct.connect(self._on_pct)
        self.running = running_version(self.root)
        self._busy = False; self._done.connect(self._finish)
        self._timer = QtCore.QTimer(self); self._timer.timeout.connect(lambda: self.check()); self._every = 6 * 3600

    # ---- identity -------------------------------------------------------------
    def install_id(self) -> str:
        s = self.store.settings
        if not s.get("install_id"): s["install_id"] = uuid.uuid4().hex; self.store.save_settings()
        return s["install_id"]

    def params(self) -> dict:
        m = platform.machine().lower(); arch = "arm64" if m in ("arm64", "aarch64") else ("x64" if m in ("x86_64", "amd64") else m)
        os_ = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
        from . import hwid
        return dict(id=self.install_id(), v=self.running, os=os_, arch=arch, shell=bootstrap.SHELL_VERSION, hw=hwid.get())

    # ---- check / download -------------------------------------------------------
    def start(self):
        """Check now (in the background) and then every few hours while the program runs."""
        self.check(); self._timer.start(self._every * 1000)

    def check(self):
        if self._busy: return
        self._busy = True; self._set("checking", "")
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        try:
            from urllib.parse import urlencode
            import secrets
            nonce = secrets.token_hex(16)
            m = json.loads(net.get(self.url + ("&" if "?" in self.url else "?") + urlencode(dict(self.params(), n=nonce)), 15, 1024 * 1024).decode("utf-8"))
            every = int(m.get("checkEvery") or 0)
            if every >= 60: self._every = every
            if m.get("update") != "available":
                self._done.emit("uptodate", ""); return
            # what to install (version, hash, size, shell) is believed only from the part the server SIGNED; a nonce stops an old answer being replayed
            sig = self.verify_update(m, nonce)
            m = dict(m, **sig)
            if not bootstrap.newer(str(m.get("version", "0")), self.running if not self.pending else self.pending):
                self._done.emit("uptodate", ""); return
            ver = str(m["version"])
            self.info = {"version": ver, "size": int(m.get("size") or 0), "notes": notes_for(m, store_lang(self.store)), "min_shell": str(m.get("min_shell") or "")}
            if bootstrap.vtuple(m.get("min_shell") or "0") > bootstrap.vtuple(bootstrap.SHELL_VERSION):
                self._done.emit("needs_installer", ver); return
            self._done.emit("downloading", ver)
            blob = net.get(m["pkg"], 60, MAX_PKG, progress=lambda d, t: self._pct.emit(int(d * 100 / t) if t else (int(d * 100 / self.info["size"]) if self.info["size"] else -1)))
            self._pct.emit(100)
            cur = install_package(blob, self.root, m.get("sha256", ""), int(m.get("size") or 0), on_step=lambda st: self._done.emit(st, ver))
            self._done.emit("ready", cur["version"])
        except UpdateError as e: self._done.emit("error", f"update rejected: {e}")
        except Exception as e: self._done.emit("error", f"{type(e).__name__}: {e}")

    def verify_update(self, m: dict, nonce: str) -> dict:
        """The signed facts of an update offer: {version, sha256, size, min_shell}. Raises UpdateError when the offer is not signed by us or is an old answer."""
        from . import sigverify
        up, sg = m.get("upd"), m.get("upd_sig")
        if not up or not sg: raise UpdateError("the update offer is not signed by HELLAS Zone")
        if not any(sigverify.verify(k, str(up).encode(), str(sg)) for k in self.pubkeys): raise UpdateError("the update offer has a wrong signature")
        d = json.loads(up)
        if d.get("n") != nonce: raise UpdateError("old update offer (replay)")
        return {k: d[k] for k in ("version", "sha256", "size", "min_shell") if k in d}

    def _on_pct(self, p):
        self.pct = p; self.progress.emit(p)

    def _finish(self, state, msg):
        if state in ("downloading", "verifying", "installing"):
            if state == "downloading": self.pct = 0
            self._set(state, msg); return
        self._busy = False
        if state == "ready": self.pending = msg
        self._set(state, msg)

    def _set(self, state, msg):
        self.state, self.message = state, msg; self.changed.emit(state, msg)

    def restart(self):
        """Start the new version now (the new copy is started, this one quits)."""
        bootstrap.started_ok(self.root); bootstrap.relaunch()
        from .qt import QtWidgets
        QtWidgets.QApplication.quit()
