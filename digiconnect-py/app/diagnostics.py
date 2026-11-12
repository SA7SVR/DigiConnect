"""A diagnostics report the person can send to the owner with one button (Licence › Send diagnostics).
It holds the program version, system, what the engine did (the end of digiconnect.log) and, on a Mac, the newest crash report of the
protocol engine. It never contains passwords (the log does not, and the settings are listed by name, not copied)."""
import glob, os, platform, sys
from pathlib import Path
from . import diag
from .version import APP_VERSION

SAFE = ("callsign", "dmr_id", "essid", "cc", "slot", "language", "mic", "speakers", "listen_mode", "nxdn_id")


def crash_reports(limit: int = 6000) -> str:
    """macOS: the newest crash report of the engine (DiagnosticReports), cut to `limit` characters."""
    if sys.platform != "darwin": return ""
    try:
        files = []
        for pat in ("dcengine*.ips", "dcengine*.crash", "DigiConnect*.ips", "DigiConnect*.crash"):
            files += glob.glob(str(Path.home() / "Library" / "Logs" / "DiagnosticReports" / pat))
        files.sort(key=os.path.getmtime, reverse=True)
        return "\n\n".join(f"--- {Path(f).name} ---\n" + Path(f).read_text(encoding="utf-8", errors="replace")[:limit] for f in files[:2])
    except OSError:
        return ""


def report(store=None, engine_path: str | None = None, lines: int = 250) -> str:
    from .engine_client import find_engine
    s = (store.settings if store is not None else {}) or {}
    head = [f"DigiConnect {APP_VERSION}", f"System: {platform.platform()} · {platform.machine()} · Python {platform.python_version()}",
            f"Engine: {engine_path or find_engine() or 'NOT FOUND'}",
            "Settings: " + ", ".join(f"{k}={s.get(k)}" for k in SAFE if s.get(k) not in (None, ""))]
    cr = crash_reports()
    out = "\n".join(head) + "\n\n--- digiconnect.log (end) ---\n" + (diag.tail(lines) or "(empty)")
    if cr: out += "\n\n--- crash report ---\n" + cr
    return out[-58000:]
