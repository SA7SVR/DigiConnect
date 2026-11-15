"""Who is talking? DMR sends only the DMR ID of the station (e.g. 2021015). This looks the ID up in the public RadioID.net database
(callsign, name, city, country) and remembers the answer on this computer, so each ID is asked for only once.
Nothing is invented: when the database does not answer, the card keeps showing the plain ID."""
import json, time, threading
from pathlib import Path
from . import net

URLS = ("https://database.radioid.net/api/dmr/user/?id={}", "https://radioid.net/api/dmr/user/?id={}")     # the same data; the second is tried when the first is down
SOURCE = "RadioID"
KEEP_FOUND = 90 * 86400          # a registered ID changes rarely
RETRY_MISSING = 6 * 3600         # an ID the database does not know: ask again after some hours (people register later)
RETRY_ERROR = 120                # network trouble: try again soon, but not on every frame of the transmission
MAX_ENTRIES = 3000


def parse(data: bytes | str, want: int | None = None) -> dict | None:
    """RadioID answer -> dict(id, call, name, city, state, country) or None when the ID is not in the database."""
    try: j = json.loads(data)
    except (ValueError, TypeError): return None
    rows = j.get("results") if isinstance(j, dict) else None
    if not isinstance(rows, list): return None
    for r in rows:
        if not isinstance(r, dict) or not str(r.get("callsign") or "").strip(): continue
        if want is not None and str(r.get("id", want)) != str(want): continue
        name = " ".join(x for x in (str(r.get("fname") or "").strip(), str(r.get("surname") or "").strip()) if x)
        return dict(id=int(r.get("id") or want or 0), call=str(r["callsign"]).strip().upper(), name=name,
                    city=str(r.get("city") or "").strip(), state=str(r.get("state") or "").strip(), country=str(r.get("country") or "").strip())
    return None


class Callbook:
    def __init__(self, root: Path | None = None, fetch=None):
        self.file = (Path(root) / "callbook_cache.json") if root else None
        self.fetch = fetch or (lambda url: net.get(url, timeout=8, limit=256 * 1024))
        self.mem: dict[int, dict] = {}                 # id -> {"at": time, "info": dict | None}
        self.busy: set[int] = set()
        self._lock = threading.Lock()
        self._load()

    # -- storage ---------------------------------------------------------
    def _load(self):
        try:
            if self.file and self.file.exists():
                d = json.loads(self.file.read_text("utf-8"))
                self.mem = {int(k): v for k, v in d.items() if isinstance(v, dict) and "at" in v}
        except Exception: self.mem = {}

    def _save(self):
        if not self.file: return
        try:
            items = sorted(self.mem.items(), key=lambda kv: kv[1]["at"], reverse=True)[:MAX_ENTRIES]
            tmp = self.file.with_suffix(".tmp"); tmp.write_text(json.dumps({str(k): v for k, v in items}), "utf-8"); tmp.replace(self.file)
        except Exception: pass

    # -- lookup ----------------------------------------------------------
    def cached(self, did: int) -> dict | None:
        e = self.mem.get(int(did)); return e.get("info") if e else None

    def needs_fetch(self, did: int) -> bool:
        did = int(did)
        if did <= 0 or did in self.busy: return False
        e = self.mem.get(did)
        if not e: return True
        age = time.time() - e["at"]
        return age > (KEEP_FOUND if e.get("info") else RETRY_ERROR if e.get("err") else RETRY_MISSING)

    def lookup_now(self, did: int) -> dict | None:
        """One synchronous lookup (runs in a worker thread). Returns the info, or None when unknown / unreachable."""
        did = int(did); last_err = False
        for url in URLS:
            try: raw = self.fetch(url.format(did))
            except Exception: last_err = True; continue
            info = parse(raw, did)
            with self._lock:
                self.mem[did] = dict(at=time.time(), info=info)
                if info is None and not self._is_json(raw): self.mem[did]["err"] = True     # not an answer at all (error page): retry soon
            self._save(); return info
        if last_err:
            with self._lock: self.mem[did] = dict(at=time.time(), info=None, err=True)
        return None

    @staticmethod
    def _is_json(raw) -> bool:
        try: json.loads(raw); return True
        except (ValueError, TypeError): return False

    def ask(self, did: int, done=None) -> bool:
        """Starts a background lookup when the ID is not known yet; done(did, info) is called from the worker thread."""
        did = int(did)
        if not self.needs_fetch(did): return False
        self.busy.add(did)
        def work():
            try: info = self.lookup_now(did)
            except Exception: info = None
            finally: self.busy.discard(did)
            if done: done(did, info)
        threading.Thread(target=work, daemon=True).start(); return True
