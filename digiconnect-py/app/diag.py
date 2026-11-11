"""Plain-text log in the data folder (digiconnect.log). Records what the program really did: list downloads, which server an entry
resolved to, the engine's answers, every message shown to the user. Never contains passwords. Size-limited (2 files of ~512 KB)."""
import datetime as dt, threading
from pathlib import Path

_lock = threading.Lock()
_path: Path | None = None
MAX = 512 * 1024


def start(root: Path):
    global _path
    _path = Path(root) / "digiconnect.log"
    log("--- start ---")


def path() -> Path | None: return _path


def log(msg: str):
    if _path is None: return
    line = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z {msg}".replace("\n", " ⏎ ")[:600]
    try:
        with _lock:
            if _path.exists() and _path.stat().st_size > MAX: _path.replace(_path.with_suffix(".log.1"))
            with open(_path, "a", encoding="utf-8") as f: f.write(line + "\n")
    except OSError:
        pass


def tail(n=200) -> str:
    try: return "\n".join(_path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]) if _path else ""
    except OSError: return ""
