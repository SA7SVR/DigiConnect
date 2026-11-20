"""Who is talking? DMR and NXDN send only a numeric ID of the station (e.g. DMR 2021015, NXDN 1538 - NXDN IDs are usually short:
unlike DMR's 7-digit RadioID numbers, they are self- or manually-assigned and have no fixed length). RadioID.net runs these as two
separate registries with two separate lookup addresses, so a number can be a real ID in one and mean nothing (or someone else) in
the other: a DMR ID and an NXDN ID of the same value are never assumed to be the same station. This looks the ID up in whichever
registry the network calls for (callsign, name, city, country) and remembers the answer on this computer, so each ID is asked for
only once. Nothing is invented: when the database does not answer, the card keeps showing the plain ID."""
import json, time, threading
from pathlib import Path
from . import net

URLS = {
    "DMR": ("https://database.radioid.net/api/dmr/user/?id={}", "https://radioid.net/api/dmr/user/?id={}"),
    "NXDN": ("https://database.radioid.net/api/nxdn/user/?id={}", "https://radioid.net/api/nxdn/user/?id={}"),
}
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
        self.file_nxdn = (Path(root) / "callbook_cache_nxdn.json") if root else None
        self.fetch = fetch or (lambda url: net.get(url, timeout=8, limit=256 * 1024))
        self.mem: dict[int, dict] = {}                 # DMR id -> {"at": time, "info": dict | None} (also used for P25, which reuses the DMR ID)
        self.mem_nxdn: dict[int, dict] = {}             # NXDN id -> same shape, kept apart: an NXDN id is a different registration than a DMR id of the same number
        self.busy: set[int] = set()
        self.busy_nxdn: set[int] = set()
        self._lock = threading.Lock()
        self._load(); self._load_nxdn()

    def _mem(self, cb_net: str) -> dict: return self.mem_nxdn if cb_net == "NXDN" else self.mem
    def _busy(self, cb_net: str) -> set: return self.busy_nxdn if cb_net == "NXDN" else self.busy
    def _file(self, cb_net: str): return self.file_nxdn if cb_net == "NXDN" else self.file

    # -- storage ---------------------------------------------------------
    def _load(self):
        try:
            if self.file and self.file.exists():
                d = json.loads(self.file.read_text("utf-8"))
                self.mem = {int(k): v for k, v in d.items() if isinstance(v, dict) and "at" in v}
        except Exception: self.mem = {}

    def _load_nxdn(self):
        try:
            if self.file_nxdn and self.file_nxdn.exists():
                d = json.loads(self.file_nxdn.read_text("utf-8"))
                self.mem_nxdn = {int(k): v for k, v in d.items() if isinstance(v, dict) and "at" in v}
        except Exception: self.mem_nxdn = {}

    def _save(self, cb_net: str = "DMR"):
        mem, file = self._mem(cb_net), self._file(cb_net)
        if not file: return
        try:
            items = sorted(mem.items(), key=lambda kv: kv[1]["at"], reverse=True)[:MAX_ENTRIES]
            tmp = file.with_suffix(".tmp"); tmp.write_text(json.dumps({str(k): v for k, v in items}), "utf-8"); tmp.replace(file)
        except Exception: pass

    # -- lookup ----------------------------------------------------------
    def cached(self, did: int, cb_net: str = "DMR") -> dict | None:
        e = self._mem(cb_net).get(int(did)); return e.get("info") if e else None

    def forget(self, did: int, cb_net: str = "DMR"):
        """Drop a cached answer (e.g. the person asked to look it up again)."""
        self._mem(cb_net).pop(int(did), None)

    def needs_fetch(self, did: int, cb_net: str = "DMR") -> bool:
        did = int(did); mem, busy = self._mem(cb_net), self._busy(cb_net)
        if did <= 0 or did in busy: return False
        e = mem.get(did)
        if not e: return True
        age = time.time() - e["at"]
        return age > (KEEP_FOUND if e.get("info") else RETRY_ERROR if e.get("err") else RETRY_MISSING)

    def lookup_now(self, did: int, cb_net: str = "DMR") -> dict | None:
        """One synchronous lookup (runs in a worker thread). Returns the info, or None when unknown / unreachable."""
        did = int(did); last_err = False; mem = self._mem(cb_net)
        for url in URLS.get(cb_net, URLS["DMR"]):
            try: raw = self.fetch(url.format(did))
            except Exception: last_err = True; continue
            info = parse(raw, did)
            with self._lock:
                mem[did] = dict(at=time.time(), info=info)
                if info is None and not self._is_json(raw): mem[did]["err"] = True     # not an answer at all (error page): retry soon
            self._save(cb_net); return info
        if last_err:
            with self._lock: mem[did] = dict(at=time.time(), info=None, err=True)
        return None

    @staticmethod
    def _is_json(raw) -> bool:
        try: json.loads(raw); return True
        except (ValueError, TypeError): return False

    def ask(self, did: int, done=None, cb_net: str = "DMR") -> bool:
        """Starts a background lookup when the ID is not known yet; done(did, info) is called from the worker thread."""
        did = int(did)
        if not self.needs_fetch(did, cb_net): return False
        self._busy(cb_net).add(did)
        def work():
            try: info = self.lookup_now(did, cb_net)
            except Exception: info = None
            finally: self._busy(cb_net).discard(did)
            if done: done(did, info)
        threading.Thread(target=work, daemon=True).start(); return True
