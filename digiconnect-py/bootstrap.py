"""Start-up loader for automatic updates (pure standard library, lives in the program shell and is never replaced by an update).

An update is a small package of Python code + assets (.dcpkg) that the running program downloaded earlier and unpacked into
<data>/updates/<version>/. At start-up activate() puts that folder in front of the program's own code, so the newer code runs
without any re-install. Safety net: a 'starting' marker is written before the program starts and removed once it has been up
(or exits normally). If the marker is still there at the next start, the previous start crashed and that update is switched off
(rolled back to the code inside the shell); an update that crashes while loading is also switched off at once."""
import json, os, sys, shutil, subprocess
from pathlib import Path

SHELL_VERSION = "2.1.0"          # raised only when the shell itself changes (engine, Qt, Python); then a full installer is needed
BASE_VERSION = "2.1.0"           # version of the app/ code built into the shell (must equal app/version.py in the source tree; a test checks it)


def vtuple(v: str) -> tuple:
    out = []
    for p in str(v).split("."):
        d = "".join(c for c in p if c.isdigit())
        out.append(int(d) if d else 0)
    return tuple(out + [0] * (3 - len(out)))


def newer(a: str, b: str) -> bool: return vtuple(a) > vtuple(b)


def updates_root() -> Path:
    o = os.environ.get("DC_UPDATES_DIR")
    if o: return Path(o)
    if sys.platform.startswith("win"): base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin": base = Path.home() / "Library" / "Application Support"
    else: base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "DigiConnect" / "updates"


def _read(p: Path, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default


def _write(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8"); os.replace(tmp, p)


def current(root: Path | None = None) -> dict | None:
    """The update that should run: {'version', 'dir', 'min_shell'} or None."""
    root = root or updates_root(); c = _read(root / "current.json", None)
    if not c or not (root / c.get("dir", "-") / "app" / "__init__.py").is_file(): return None
    if c["version"] in _read(root / "bad.json", []): return None
    if vtuple(c.get("min_shell", "0")) > vtuple(SHELL_VERSION): return None
    return c


def activate(bundled_version: str, root: Path | None = None) -> str | None:
    """Call first thing, before 'import app'. Returns the version of the update now in use, or None (shell code runs)."""
    root = root or updates_root(); mark = root / "starting"
    try:
        c = current(root)
        if mark.exists():                                # last start never finished: do not trust the update again
            prev = _read(mark, {}).get("version")
            if prev: mark_bad(prev, root)
            mark.unlink(missing_ok=True); c = current(root)
        if not c or not newer(c["version"], bundled_version): return None
        _write(mark, {"version": c["version"]})
        sys.path.insert(0, str(root / c["dir"]))
        return c["version"]
    except Exception:
        return None


def started_ok(root: Path | None = None):
    """Remove the 'starting' marker (the program has been up for a while, or is closing normally)."""
    try: ((root or updates_root()) / "starting").unlink(missing_ok=True)
    except Exception: pass


def mark_bad(version: str, root: Path | None = None):
    root = root or updates_root(); bad = _read(root / "bad.json", [])
    if version not in bad: bad.append(version)
    _write(root / "bad.json", bad)
    c = _read(root / "current.json", None)
    if c and c.get("version") == version: (root / "current.json").unlink(missing_ok=True)


def relaunch():
    """Start a new copy of the program and let this one end (used after an update and after a failed update)."""
    args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.abspath(sys.argv[0])]
    subprocess.Popen(args + sys.argv[1:], close_fds=True)


def prune(keep: int = 2, root: Path | None = None):
    root = root or updates_root(); c = _read(root / "current.json", {}) or {}
    dirs = sorted([d for d in root.glob("v*") if d.is_dir()], key=lambda d: vtuple(d.name[1:]), reverse=True)
    for d in dirs[keep:]:
        if d.name != c.get("dir"): shutil.rmtree(d, ignore_errors=True)
