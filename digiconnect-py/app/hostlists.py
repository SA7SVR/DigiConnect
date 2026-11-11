"""World-wide server lists (YSF reflectors, D-Star REF/XRF/DCS/XLX reflectors, DMR masters).

The lists are downloaded from the public host files the hotspot community maintains (the same
files Pi-Star / WPSD use) and cached in the data folder, so DigiConnect works offline with the
last copy. Nothing here is guessed: an entry exists only if a downloaded file contains it.
The parsers are deliberately tolerant (';', TAB or blanks as separators) because the files
differ slightly between mirrors; lines they cannot understand are skipped and counted."""
import json, re, time, threading, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

MIRRORS = ["https://hostfiles.w0chp.net/", "https://www.pistar.uk/downloads/", "http://www.pistar.uk/downloads/"]
XLX_API = "https://xlxapi.rlx.lu/api.php?do=GetReflectorList"
MAX_AGE = 24 * 3600
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = 15

# source key -> (file name, parser, label shown to the user)
SOURCES = {
    "YSF": ("YSFHosts.txt", "ysf", "YSF reflectors"),
    "REF": ("DPlus_Hosts.txt", "dstar:REF", "D-Star REF (DPlus)"),
    "XRF": ("DExtra_Hosts.txt", "dstar:XRF", "D-Star XRF (DExtra)"),
    "DCS": ("DCS_Hosts.txt", "dstar:DCS", "D-Star DCS"),
    "XLX": ("XLXHosts.txt", "dstar:XLX", "XLX reflectors"),
    "DMR": ("DMR_Hosts.txt", "dmr", "DMR masters"),
}
DEFAULT_PORT = {"YSF": 42000, "REF": 20001, "XRF": 30001, "DCS": 30051, "XLX": 30051, "DMR": 62031}
DEFAULT_MODULE = {"REF": "C", "XRF": "C", "DCS": "A", "XLX": "A"}
NET_OF = {"YSF": "C4FM", "REF": "D-Star", "XRF": "D-Star", "DCS": "D-Star", "XLX": "D-Star", "DMR": "DMR"}

_HOST = re.compile(r"^(?:\d{1,3}(?:\.\d{1,3}){3}|(?=.*[A-Za-z])[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+)$")


def _tokens(line: str) -> list[str]:
    line = line.strip()
    if not line or line.startswith("#"): return []
    if ";" in line: parts = line.split(";")
    elif "\t" in line: parts = line.split("\t")
    else: parts = line.split()
    return [p.strip() for p in parts]


def _host_index(tok: list[str]) -> int | None:
    cand = [i for i, t in enumerate(tok) if i and _HOST.match(t)]
    for i in cand:                                   # a host name followed by a port is the address; descriptions may contain dots too
        if i + 1 < len(tok) and tok[i + 1].isdigit() and 0 < int(tok[i + 1]) < 65536: return i
    return cand[0] if cand else None


def _port_after(tok: list[str], start: int, default: int) -> int:
    for t in tok[start:]:
        if t.isdigit() and 0 < int(t) < 65536: return int(t)
    return default


def _entry(proto: str, id_: str, name: str, sub: str, host: str, port: int, country: str = "") -> dict:
    return dict(net=NET_OF[proto], proto=proto, id=id_, name=name, sub=sub, activity="From the worldwide server list",
                host=host, port=port, country=country)


def parse_ysf(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 3 or not tok[0].isdigit(): continue          # FCS and other lines are not YSF
        hi = _host_index(tok)
        if hi is None: continue
        name = tok[1] or tok[0]; desc = " ".join(x for x in tok[2:hi] if x)
        out.append(_entry("YSF", tok[0], name + (f" · {desc}" if desc and desc != name else ""), f"{tok[0]} · YSF",
                          tok[hi], _port_after(tok, hi + 1, DEFAULT_PORT["YSF"])))
    return out


def parse_dstar(text: str, proto: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 2: continue
        ref = tok[0].upper()
        if not re.match(rf"^{proto}[A-Z0-9]{{1,6}}$", ref): continue
        hi = _host_index(tok)
        if hi is None: continue
        mod = DEFAULT_MODULE[proto]
        out.append(_entry(proto, f"{ref} {mod}", ref, f"{ref} · module {mod} · {proto}", tok[hi], _port_after(tok, hi + 1, DEFAULT_PORT[proto])))
    return out


def parse_dmr(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 3: continue
        hi = _host_index(tok)
        if hi is None: continue
        name = tok[0]; parts = name.split("_")
        country = " ".join(parts[1:-1]) if len(parts) >= 3 and parts[-1].isdigit() else ""
        e = _entry("DMR", name, name.replace("_", " "), f"{tok[hi]}", tok[hi], _port_after(tok, hi + 2, DEFAULT_PORT["DMR"]), country)
        out.append(e)
    return out


def parse_xlx_api(text: str) -> list[dict]:
    """XLX API (XML): enriches XLX reflectors with country and description."""
    out = []
    try: root = ET.fromstring(text)
    except ET.ParseError: return out
    for r in root.iter("reflector"):
        f = {c.tag: (c.text or "").strip() for c in r}
        name = f.get("name", "").upper(); host = f.get("dns") or f.get("lastip") or ""
        if not re.match(r"^XLX[A-Z0-9]{3}$", name) or not _HOST.match(host): continue
        desc = f.get("comment", "")
        e = _entry("XLX", f"{name} A", name + (f" · {desc}" if desc else ""), f"{name} · module A · XLX", host, DEFAULT_PORT["XLX"], f.get("country", ""))
        out.append(e)
    return out


def parse(kind: str, text: str) -> list[dict]:
    if kind == "ysf": return parse_ysf(text)
    if kind == "dmr": return parse_dmr(text)
    return parse_dstar(text, kind.split(":")[1])


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DigiConnect (HELLAS Zone)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES: raise ValueError("file too large")
    return data.decode("utf-8", "replace")


class HostLists:
    _shared: dict[str, "HostLists"] = {}

    @classmethod
    def for_root(cls, root: Path) -> "HostLists":
        k = str(root)
        if k not in cls._shared: cls._shared[k] = cls(root)
        return cls._shared[k]

    def __init__(self, root: Path):
        self.file = Path(root) / "hosts.json"
        self.fetched = 0.0
        self.entries: list[dict] = []
        self.status: dict[str, str] = {}
        self._index: dict[tuple[str, str], dict] = {}
        self._lock = threading.Lock()
        try:
            d = json.loads(self.file.read_text(encoding="utf-8"))
            self._set(d.get("entries", []), d.get("status", {}), float(d.get("fetched", 0)))
        except Exception:
            pass

    # ---- access -----------------------------------------------------------
    def _set(self, entries, status, fetched):
        idx = {}
        for e in entries: idx[(e["proto"], e["id"].split()[0] if e["proto"] in DEFAULT_MODULE else e["id"])] = e
        with self._lock:
            self.entries, self.status, self.fetched, self._index = entries, status, fetched, idx

    def stale(self) -> bool: return not self.entries or time.time() - self.fetched > MAX_AGE

    def for_net(self, net: str) -> list[dict]:
        return sorted((e for e in self.entries if e["net"] == net and e["proto"] != "DMR"), key=lambda e: (e["proto"], e["id"]))

    def dmr_masters(self) -> list[dict]: return sorted((e for e in self.entries if e["proto"] == "DMR"), key=lambda e: e["name"].lower())

    def find(self, proto: str, ref: str) -> dict | None:
        """proto YSF/REF/XRF/DCS/XLX, ref = '00006' or 'REF001' (module already stripped). Returns {'host','port'} or None."""
        e = self._index.get((proto, ref.strip().upper() if proto != "YSF" else ref.strip()))
        return dict(host=e["host"], port=e["port"]) if e else None

    def summary(self) -> str:
        n = {k: sum(1 for e in self.entries if e["proto"] == k) for k in SOURCES}
        return " · ".join(f"{SOURCES[k][2]} {v}" for k, v in n.items() if v) or "no lists downloaded yet"

    # ---- download ---------------------------------------------------------
    def download(self, mirrors=None, xlx_api=XLX_API) -> tuple[int, list[str]]:
        """Downloads every list (several mirrors per file). Keeps the old copy of any list that fails.
        Returns (number of entries, problems)."""
        mirrors = mirrors or MIRRORS
        old: dict[str, list[dict]] = {}
        for e in self.entries: old.setdefault(e["proto"], []).append(e)
        new, status, problems = {}, {}, []
        for key, (fname, kind, label) in SOURCES.items():
            got, err = None, ""
            for m in mirrors:
                try:
                    es = parse(kind, fetch(m + fname))
                    if es: got = es; break
                    err = f"{fname}: no usable lines"
                except Exception as ex:
                    err = f"{fname}: {ex}"
            if got is None:
                problems.append(f"{label}: {err or 'not available'}")
                status[key] = "failed: " + err
                if key in old: new[key] = old[key]
            else:
                new[key] = got; status[key] = f"ok {len(got)}"
        if xlx_api:                       # XLX country/description from the XLX API; hosts file stays the base
            try:
                api = {e["id"].split()[0]: e for e in parse_xlx_api(fetch(xlx_api))}
                base = {e["id"].split()[0]: e for e in new.get("XLX", [])}
                for k, e in api.items():
                    if k in base: base[k]["country"] = e["country"]; base[k]["name"] = e["name"]
                    else: base[k] = e
                if base: new["XLX"] = list(base.values()); status["XLX"] = f"ok {len(base)}"
            except Exception as ex:
                status["XLX-API"] = f"failed: {ex}"
        entries = [e for k in SOURCES for e in new.get(k, [])]
        if entries:
            self._set(entries, status, time.time())
            try: self.file.write_text(json.dumps(dict(fetched=self.fetched, entries=entries, status=status), ensure_ascii=False), encoding="utf-8")
            except OSError as ex: problems.append(f"could not save the lists: {ex}")
        return len(entries), problems
