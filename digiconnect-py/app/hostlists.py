"""World-wide server lists (YSF reflectors, D-Star REF/XRF/DCS/XLX reflectors, DMR masters).

The lists are downloaded from the public host files the hotspot community maintains (the same
files Pi-Star / WPSD use) and cached in the data folder, so DigiConnect works offline with the
last copy. Nothing here is guessed: an entry exists only if a downloaded file contains it.
The parsers are deliberately tolerant (';', TAB or blanks as separators) because the files
differ slightly between mirrors; lines they cannot understand are skipped and counted."""
import json, re, time, threading, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

UPSTREAM = "http://www.dudetronics.com/ar-dns/"                          # the public host-file site the open-source DV clients use
PISTAR = ["https://hostfiles.w0chp.net/", "https://www.pistar.uk/downloads/"]   # the Pi-Star / WPSD host files: FIRST choice (same lists and descriptions the hotspot dashboards show)
XLX_API = "https://xlxapi.rlx.lu/api.php?do=GetReflectorList"
MAX_AGE = 3600                 # the source lists are refreshed about hourly (Pi-Star: YSF hourly): ask again after an hour
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = 15

# source key -> (file name on the server / upstream, parser, label shown to the user, Pi-Star file names tried on the Pi-Star mirrors; Pi-Star names its downloads <MODE>_Hosts.txt, e.g. YSF_Hosts.txt, FCS_Hosts.txt)
SOURCES = {
    "YSF": ("YSFHosts.txt", "ysf", "YSF reflectors", ["YSF_Hosts.txt"]),
    "FCS": ("FCSRooms.txt", "fcs", "FCS rooms (C4FM)", ["FCS_Hosts.txt"]),
    "REF": ("dplus.txt", "dstar:REF", "D-Star REF (DPlus)", ["DPlus_Hosts.txt", "DStar_Hosts.json"]),
    "XRF": ("dextra.txt", "dstar:XRF", "D-Star XRF (DExtra)", ["DExtra_Hosts.txt", "DStar_Hosts.json"]),
    "DCS": ("dcs.txt", "dstar:DCS", "D-Star DCS", ["DCS_Hosts.txt", "DStar_Hosts.json"]),
    "XLX": ("XLXHosts.txt", "dstar:XLX", "XLX reflectors", ["XLX_Hosts.txt", "XLXHosts.txt"]),
    "DMR": ("DMRHosts.txt", "dmr", "DMR masters", ["DMR_Hosts.txt"]),
    "NXDN": ("NXDNHosts.txt", "num:NXDN", "NXDN talkgroups", ["NXDN_Hosts.txt"]),
    "P25": ("P25Hosts.txt", "num:P25", "P25 talkgroups", ["P25_Hosts.txt"]),
    "M17": ("M17Hosts-full.csv", "m17", "M17 reflectors", ["M17_Hosts.txt"]),
    "TG": ("TalkGroups.json", "tg", "DMR talkgroups", []),          # BrandMeister talkgroup catalogue (public API, see FULL_URL)
}
FULL_URL = {"TG": ["https://api.brandmeister.network/v2/talkgroup", "https://www.pistar.uk/downloads/TGList_BM.txt", "https://hostfiles.w0chp.net/TGList_BM.txt"]}   # the BrandMeister API is what the Pi-Star TG page itself shows (live names, e.g. TG 202)
DEFAULT_PORT = {"YSF": 42000, "FCS": 62500, "REF": 20001, "XRF": 30001, "DCS": 30051, "XLX": 30051, "DMR": 62031, "NXDN": 41400, "P25": 41000, "M17": 17000, "TG": 0}
DEFAULT_MODULE = {"REF": "C", "XRF": "C", "DCS": "A", "XLX": "A", "M17": "A"}
NET_OF = {"YSF": "C4FM", "FCS": "C4FM", "REF": "D-Star", "XRF": "D-Star", "DCS": "D-Star", "XLX": "D-Star", "DMR": "DMR", "NXDN": "NXDN", "P25": "P25", "M17": "M17", "TG": "DMR"}

_HOST = re.compile(r"^(?:\d{1,3}(?:\.\d{1,3}){3}|(?=.*[A-Za-z])[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+)$")


def _tokens(line: str) -> list[str]:
    line = line.strip()
    if not line or line.startswith("#"): return []
    if ";" in line: parts = line.split(";")
    elif "\t" in line: parts = line.split("\t")
    elif "," in line: parts = line.split(",")                 # M17Hosts-full.csv
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
        out.append(_entry("YSF", tok[0], f"YSF{tok[0]} - {name}" + (f" - {desc}" if desc else ""), f"{tok[0]} · YSF",
                          tok[hi], _port_after(tok, hi + 1, DEFAULT_PORT["YSF"])))
    return out


def parse_fcs(text: str) -> list[dict]:
    """FCS rooms: 'FCS00134;Greece;FCS001 - Greece;;;' (id;name;description). An FCS reflector has no address in the list: like YSFGateway
    (g4klx) it is the DNS name <first six characters, e.g. FCS001>.xreflector.net on UDP port 62500."""
    out, seen = [], set()
    for line in text.splitlines():
        tok = _tokens(line) if ";" in line else []
        if len(tok) < 2 or not re.match(r"^FCS\d{5}$", tok[0].upper()) or tok[0].upper() in seen: continue
        id_ = tok[0].upper(); seen.add(id_); name = tok[1] or id_; desc = tok[2] if len(tok) > 2 else ""
        out.append(_entry("FCS", id_, f"{id_} - {name}", desc or f"{id_} · FCS", f"{id_[:6].lower()}.xreflector.net", DEFAULT_PORT["FCS"]))
    return out


def _parse_dstar_json(text: str, proto: str) -> list[dict]:
    out = []
    try: items = json.loads(text).get("reflectors", [])
    except (ValueError, AttributeError): return out
    for r in items:
        if not isinstance(r, dict) or str(r.get("reflector_type", "")).upper() != proto: continue
        ref = str(r.get("name", "")).strip().upper(); host = str(r.get("ipv4") or r.get("host") or "").strip()
        if not re.match(r"^[A-Z0-9]{3,8}$", ref) or not _HOST.match(host): continue
        mod = DEFAULT_MODULE[proto]
        out.append(_entry(proto, f"{ref} {mod}", ref, f"{ref} · module {mod} · {proto}", host, DEFAULT_PORT[proto]))
    return out


def parse_dstar(text: str, proto: str) -> list[dict]:
    if text.lstrip().startswith("{"): return _parse_dstar_json(text, proto)
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 2: continue
        ref = tok[0].upper()
        if proto == "XLX" and re.match(r"^\d{3}$", ref): ref = "XLX" + ref        # Pi-Star XLXHosts.txt: '000;ip;4004' (the port there is not the link port)
        if not re.match(r"^[A-Z0-9]{3,8}$", ref) or (proto == "XLX" and not ref.startswith("XLX")): continue
        hi = _host_index(tok)
        if hi is None: continue
        mod = DEFAULT_MODULE[proto]
        port = DEFAULT_PORT[proto] if proto == "XLX" else _port_after(tok, hi + 1, DEFAULT_PORT[proto])
        out.append(_entry(proto, f"{ref} {mod}", ref, f"{ref} · module {mod} · {proto}", tok[hi], port))
    return out


def parse_numeric(text: str, proto: str) -> list[dict]:
    """NXDN / P25: 'TG host port' per line (talkgroup number first)."""
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 2 or not tok[0].isdigit() or not 0 < int(tok[0]) <= 16777215: continue
        hi = _host_index(tok)
        if hi is None: continue
        name = f"{proto} TG {tok[0]}"; desc = " ".join(x for x in tok[1:hi] if x)
        out.append(_entry(proto, tok[0], name + (f" · {desc}" if desc else ""), f"TG {tok[0]} · {proto}", tok[hi], _port_after(tok, hi + 1, DEFAULT_PORT[proto])))
    return out


def parse_m17(text: str) -> list[dict]:
    """M17: 'M17-XXX host port' per line; the module (A-Z) is chosen when linking."""
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 2: continue
        ref = tok[0].upper()
        if not re.match(r"^M17-[A-Z0-9]{3}$", ref): continue
        hi = _host_index(tok)
        if hi is None: continue
        out.append(_entry("M17", f"{ref} A", ref, f"{ref} · module A · M17", tok[hi], _port_after(tok, hi + 1, DEFAULT_PORT["M17"])))
    return out


def parse_dmr(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        tok = _tokens(line)
        if len(tok) < 3: continue
        hi = _host_index(tok)
        if hi is None or tok[hi].startswith("127."): continue          # DMRGateway / DMR2YSF ... are local gateway lines, not servers
        name = tok[0]; parts = name.split("_")
        country = (" ".join(parts[2:]) if parts[0] == "BM" and len(parts) >= 3 and parts[1].isdigit()          # real file: BM_2402_Sweden
                   else " ".join(parts[1:-1]) if len(parts) >= 3 and parts[-1].isdigit() else "")
        e = _entry("DMR", name, name, f"{tok[hi]}", tok[hi], _port_after(tok, hi + 2, DEFAULT_PORT["DMR"]), country)
        after = [t for t in tok[hi + 1:] if t]
        e["password"] = after[0] if len(after) >= 2 and not after[0].isdigit() else ""          # the list's own password column (public, shared by all users of that master)
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


def parse_tg(text: str) -> list[dict]:
    """DMR talkgroup catalogue. Accepts the BrandMeister API answer (JSON object {id: name} or {id: {Name: ..}}, or a list of
    objects) and plain text lines 'id;name'. Entries without a numeric id in 1..16777215 are skipped."""
    out, seen = [], set()
    def add(id_, name):
        id_ = str(id_).strip()
        if not id_.isdigit() or not 0 < int(id_) <= 16777215 or id_ in seen: return
        seen.add(id_); name = (name or "").strip()
        out.append(_entry("TG", id_, f"TG {id_}" + (f" · {name}" if name else ""), f"TG {id_} · {name or 'DMR talkgroup'}", "", 0))
    t = text.lstrip()
    if t[:1] in "{[":
        try: data = json.loads(t)
        except ValueError: data = None
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict): v = v.get("Name") or v.get("name") or v.get("Description") or ""
                add(k, v if isinstance(v, str) else "")
        elif isinstance(data, list):
            for r in data:
                if not isinstance(r, dict): continue
                add(r.get("id") or r.get("TG") or r.get("tg") or r.get("talkgroup") or "", r.get("name") or r.get("Name") or "")
        return out
    for line in text.splitlines():
        tok = _tokens(line)
        if not tok or not tok[0].isdigit(): continue
        if len(tok) >= 4 and tok[1] in ("0", "1", "2"): add(tok[0], tok[2])          # Pi-Star TGList_BM.txt:  id;option;NAME;TGid
        else: add(tok[0], " ".join(x for x in tok[1:] if x))
    return out


def parse(kind: str, text: str) -> list[dict]:
    if kind == "tg": return parse_tg(text)
    if kind == "ysf": return parse_ysf(text)
    if kind == "fcs": return parse_fcs(text)
    if kind == "dmr": return parse_dmr(text)
    if kind == "m17": return parse_m17(text)
    if kind.startswith("num:"): return parse_numeric(text, kind.split(":")[1])
    return parse_dstar(text, kind.split(":")[1])


def fetch(url: str) -> str:
    from . import net
    return net.get(url, TIMEOUT, MAX_BYTES).decode("utf-8", "replace")


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
        from . import countries
        for e in entries:                                   # the host files have no country column: work it out from the name / talkgroup number
            if e.get("country"): continue
            try:
                if e["proto"] == "TG": e["country"] = countries.of_talkgroup(e["id"])
                elif e["proto"] in ("YSF", "XLX", "NXDN", "P25"): e["country"] = countries.guess(e.get("name", "").split(" · ")[0], e.get("name", ""))
                elif e["proto"] == "FCS": e["country"] = countries.guess(e.get("name", "").split(" - ", 1)[-1])
            except Exception:
                e["country"] = ""
        idx = {}
        for e in entries: idx[(e["proto"], e["id"].split()[0] if e["proto"] in DEFAULT_MODULE else e["id"])] = e
        with self._lock:
            self.entries, self.status, self.fetched, self._index = entries, status, fetched, idx

    def stale(self) -> bool: return not self.entries or time.time() - self.fetched > MAX_AGE

    def for_net(self, net: str) -> list[dict]:
        order = {"YSF": "0", "FCS": "1"}                                   # C4FM: YSF reflectors first, then FCS rooms
        return sorted((e for e in self.entries if e["net"] == net and e["proto"] != "DMR"),
                      key=lambda e: (order.get(e["proto"], e["proto"]), 0, int(e["id"]), "") if e["id"].isdigit() else (order.get(e["proto"], e["proto"]), 1, 0, e["id"]))

    def dmr_default_password(self, host: str) -> str:
        """The password the host list gives for this DMR master ('' if none). BrandMeister's list entry is only a placeholder: every user has a personal hotspot password."""
        for e in self.entries:
            if e["proto"] == "DMR" and e["host"].lower() == (host or "").strip().lower() and e.get("password"): return e["password"]
        return ""

    @staticmethod
    def dmr_network(e: dict) -> str:
        """The network a DMR master belongs to, as the host list itself names it: the part of the name before the first '_' (BM_2402_Sweden -> BrandMeister, DMR+_IPSC2-X -> DMR+, FreeDMR_... -> FreeDMR)."""
        p = (e.get("name") or "").split("_", 1)[0].strip()
        return "BrandMeister" if p.upper() == "BM" else (p or "Other")

    def dmr_networks(self) -> list[tuple[str, int]]:
        c: dict[str, int] = {}
        for e in self.entries:
            if e["proto"] == "DMR": n = self.dmr_network(e); c[n] = c.get(n, 0) + 1
        return sorted(c.items(), key=lambda kv: (-kv[1], kv[0].lower()))

    def dmr_masters(self) -> list[dict]: return sorted((e for e in self.entries if e["proto"] == "DMR"), key=lambda e: e["name"].lower())

    def find(self, proto: str, ref: str) -> dict | None:
        """proto YSF/REF/XRF/DCS/XLX, ref = '00006' or 'REF001' (module already stripped). Returns {'host','port'} or None."""
        e = self._index.get((proto, ref.strip().upper() if proto != "YSF" else ref.strip()))
        return dict(host=e["host"], port=e["port"]) if e else None

    def status_lines(self) -> list[tuple[str, bool, str]]:
        """[(label, ok, text)] for every list: how many entries, where from, or why it failed. Shown to the user (Settings › Radio networks)."""
        out = []
        for k, (_f, _kind, label, _alt) in SOURCES.items():
            n = sum(1 for e in self.entries if e["proto"] == k); st = self.status.get(k, "")
            if st.startswith("failed"): out.append((label, False, (f"{n} entries (saved copy) · " if n else "") + st[len("failed: "):]))
            elif n: out.append((label, True, f"{n} entries" + (" · " + st.split(" · ", 1)[1] if " · " in st else "")))
            else: out.append((label, False, "not downloaded yet"))
        return out

    def summary(self) -> str:
        n = {k: sum(1 for e in self.entries if e["proto"] == k) for k in SOURCES}
        return " · ".join(f"{SOURCES[k][2]} {v}" for k, v in n.items() if v) or "no lists downloaded yet"

    # ---- download ---------------------------------------------------------
    @staticmethod
    def candidates(key: str, mirrors=None) -> list[str]:
        fname, _, _, alt = SOURCES[key]
        if mirrors: return [m + fname for m in mirrors]            # tests / custom mirrors
        if key in FULL_URL: return list(FULL_URL[key])
        c = []
        for a in alt: c += [m + a for m in PISTAR]
        return c + [UPSTREAM + fname]

    def download(self, mirrors=None, xlx_api=XLX_API) -> tuple[int, list[str]]:
        """Downloads the worldwide lists: the public host-file site first, then Pi-Star mirrors.
        A host that cannot be reached at all is skipped for the rest of the run (no waiting 15 s per file when offline).
        Keeps the old copy of any list that fails. Returns (number of entries, problems)."""
        from urllib.parse import urlparse
        old: dict[str, list[dict]] = {}
        for e in self.entries: old.setdefault(e["proto"], []).append(e)
        new, status, problems = {}, {}, []
        dead: set[str] = set()
        for key, (fname, kind, label, _alt) in SOURCES.items():
            got, errs = None, []
            for url in self.candidates(key, mirrors):
                host = urlparse(url).netloc
                if host in dead: errs.append(f"{host}: unreachable"); continue
                try:
                    es = parse(kind, fetch(url))
                    if es: got = es; status[key] = f"ok {len(es)} · {host}"; break
                    errs.append(f"{host}: no usable lines")
                except urllib.error.HTTPError as ex:
                    errs.append(f"{host}: HTTP {ex.code}")
                except Exception as ex:
                    dead.add(host); errs.append(f"{host}: {getattr(ex, 'reason', ex)}")
            if got is None:
                err = " | ".join(errs) or "not available"
                problems.append(f"{label}: {err}")
                status[key] = "failed: " + err
                if key in old: new[key] = old[key]
            else:
                new[key] = got
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
