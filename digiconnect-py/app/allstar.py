"""AllStarLink: sign-in token, node lookup and the worldwide node directory.

How a connection works (AllStarLink standard ASL002 "Application Authentication"):
  1. the user's own AllStarLink portal account (callsign + password) is exchanged ONCE PER CONNECTION for a
     single-use token at https://api.allstarlink.org/v1/appauth/request  (the password never goes to the node);
  2. the node's address comes from AllStarLink DNS: SRV _iax._udp.<node>.nodes.allstarlink.org (host + port);
  3. the engine calls the node over IAX2 as the public user "allstar-public" and puts "TOKEN/CALLSIGN" in the caller name.
Only nodes that accept web/app connections ("allstar-public") can be reached this way; a node whose owner closed it answers with a
refusal, which is shown to the user as it is. Nothing here is guessed: an error is reported, never hidden."""
import json, re, time, uuid, threading, urllib.request, urllib.error
from pathlib import Path

APPAUTH_URL = "https://api.allstarlink.org/v1/appauth/request"
DIRECTORY_URLS = ["https://allmondb.allstarlink.org/allmondb.php"]
DNS_ZONE = "nodes.allstarlink.org"
DEFAULT_PORT = 4569
MIN_REFRESH = 15 * 60               # the directory is cached by AllStarLink for 15 minutes: never ask more often
MAX_AGE = 24 * 3600
TIMEOUT = 15
MAX_BYTES = 32 * 1024 * 1024
PUBLIC_USER, PUBLIC_SECRET = "allstar-public", "allstar"

_NODE = re.compile(r"^\d{3,8}$")
_CALL = re.compile(r"^[A-Za-z0-9]{1,64}$")


def valid_node(text: str) -> bool:
    return bool(_NODE.match((text or "").strip()))


def valid_user(text: str) -> bool:
    return bool(_CALL.match((text or "").strip()))


def dns_name(node: str) -> str: return f"{node.strip()}.{DNS_ZONE}"


def srv_name(node: str) -> str: return f"_iax._udp.{node.strip()}.{DNS_ZONE}"


def caller_name(token: str, callsign: str) -> str:
    """What the node expects in the IAX2 'calling name': TOKEN/CALLSIGN (the callsign of the signed-in portal account)."""
    return f"{token}/{callsign.strip().upper()}"


# ---- token ------------------------------------------------------------------
def client_id(store) -> str:
    """The UUIDv4 the standard requires: made once per installation and kept (rate limits are per client-id)."""
    cid = str(store.settings.get("asl_client_id") or "")
    try:
        if uuid.UUID(cid).version == 4: return cid
    except ValueError:
        pass
    cid = str(uuid.uuid4()); store.settings["asl_client_id"] = cid
    try: store.save_settings()
    except Exception: pass
    return cid


def request_token(username: str, password: str, cid: str, url: str = APPAUTH_URL, timeout: float = TIMEOUT) -> tuple[str, str]:
    """(token, '') or ('', reason in words). Blocking: call it from a worker thread."""
    username = (username or "").strip()
    if not valid_user(username): return "", "Enter your AllStarLink portal username (your callsign, letters and digits only)."
    if not password: return "", "Enter your AllStarLink portal password."
    body = json.dumps({"username": username, "password": password, "client-id": cid, "request-id": uuid.uuid4().hex}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json", "User-Agent": "DigiConnect (HELLAS Zone)"})
    try:
        from . import net
        ctx = net.context() if url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read(65536)
    except urllib.error.HTTPError as ex:
        if ex.code == 429: return "", "AllStarLink says: too many sign-in requests. Wait a minute and try again."
        return "", f"AllStarLink sign-in refused (HTTP {ex.code})."
    except Exception as ex:
        return "", f"Cannot reach AllStarLink sign-in ({getattr(ex, 'reason', ex)})."
    try: data = json.loads(raw)
    except ValueError: return "", "AllStarLink sign-in gave an unreadable answer."
    tok = data.get("auth-token") if isinstance(data, dict) else None
    if isinstance(data, dict) and data.get("status") is True and isinstance(tok, str) and tok:
        return tok, ""
    return "", "AllStarLink did not accept this callsign / password (the portal account must be active and its callsign validated)."


# ---- node address -------------------------------------------------------------
def srv_lookup(node: str, done, timeout_ms: int = 5000):
    """Asks AllStarLink DNS for the node's SRV record; done(host, port) is called ONCE, from the Qt event loop.
    On any failure it is done(<node>.nodes.allstarlink.org, 4569): the A record of that name is the node's address (the engine resolves it)."""
    from .qt import QtCore, QtNetwork
    fallback = (dns_name(node), DEFAULT_PORT)
    state = {"done": False}

    def finish(host, port):
        if state["done"]: return
        state["done"] = True; done(host, port)
    try:
        look = QtNetwork.QDnsLookup(QtNetwork.QDnsLookup.Type.SRV, srv_name(node))
    except Exception:
        finish(*fallback); return None

    def on_done():
        try:
            recs = look.serviceRecords() if look.error() == QtNetwork.QDnsLookup.Error.NoError else []
            if recs:
                r = sorted(recs, key=lambda x: (x.priority(), -x.weight()))[0]
                host = str(r.target()).rstrip("."); port = int(r.port())
                if host and 0 < port < 65536: finish(host, port); return
        except Exception:
            pass
        finish(*fallback)
    look.finished.connect(on_done)
    QtCore.QTimer.singleShot(timeout_ms, lambda: (look.abort(), finish(*fallback)))
    look.lookup()
    return look


# ---- worldwide node directory ---------------------------------------------------
def parse_nodes(text: str) -> list[dict]:
    """Node list -> [{'node','call','desc','loc'}]. Accepts the AllStarLink node database lines  node|callsign|description|location
    (also ';' / TAB separated) and a JSON list. Lines that are not understood are skipped."""
    out, seen = [], set()
    text = (text or "").strip()
    rows: list[list[str]] = []
    if text[:1] in "[{":
        try:
            d = json.loads(text)
            if isinstance(d, dict): d = d.get("nodes") or d.get("data") or list(d.values())
            for x in d:
                if isinstance(x, dict):
                    rows.append([str(x.get("node", x.get("node_id", x.get("id", "")))), str(x.get("callsign", x.get("call", ""))),
                                 str(x.get("description", x.get("desc", x.get("name", "")))), str(x.get("location", x.get("loc", "")))])
                elif isinstance(x, (list, tuple)): rows.append([str(i) for i in x])
        except ValueError:
            pass
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            sep = "|" if "|" in line else (";" if ";" in line else ("\t" if "\t" in line else None))
            if sep is None: continue
            rows.append([p.strip() for p in line.split(sep)])
    for r in rows:
        if not r or not valid_node(r[0]) or r[0] in seen: continue
        seen.add(r[0])
        out.append(dict(node=r[0], call=(r[1] if len(r) > 1 else "").upper(), desc=r[2] if len(r) > 2 else "", loc=r[3] if len(r) > 3 else ""))
    return out


class NodeDirectory:
    """The worldwide AllStarLink node list, cached in the data folder."""
    _shared: dict[str, "NodeDirectory"] = {}

    @classmethod
    def for_root(cls, root: Path) -> "NodeDirectory":
        k = str(root)
        if k not in cls._shared: cls._shared[k] = cls(root)
        return cls._shared[k]

    def __init__(self, root: Path):
        self.file = Path(root) / "asl_nodes.json"
        self.fetched = 0.0
        self.nodes: list[dict] = []
        self.status = ""
        self._by: dict[str, dict] = {}
        self._lock = threading.Lock()
        try:
            d = json.loads(self.file.read_text(encoding="utf-8")); self._set(d.get("nodes", []), float(d.get("fetched", 0)))
        except Exception:
            pass

    def _set(self, nodes, fetched):
        by = {n["node"]: n for n in nodes}
        with self._lock: self.nodes, self.fetched, self._by = nodes, fetched, by

    def stale(self) -> bool: return not self.nodes or time.time() - self.fetched > MAX_AGE

    def can_refresh(self) -> bool: return time.time() - self.fetched > MIN_REFRESH or not self.nodes

    def get(self, node: str) -> dict | None: return self._by.get((node or "").strip())

    def search(self, query: str, limit: int = 300) -> list[dict]:
        """Matches node number, callsign, description and location (all words must match)."""
        words = [w for w in (query or "").lower().split() if w]
        if not words: return self.nodes[:limit]
        out = []
        for n in self.nodes:
            hay = f"{n['node']} {n['call']} {n['desc']} {n['loc']}".lower()
            if all(w in hay for w in words):
                out.append(n)
                if len(out) >= limit: break
        return out

    def download(self, urls=None) -> tuple[int, str]:
        """(number of nodes, problem). Keeps the saved copy when the download fails."""
        from . import net
        errs = []
        for url in (urls or DIRECTORY_URLS):
            try:
                nodes = parse_nodes(net.get(url, TIMEOUT, MAX_BYTES).decode("utf-8", "replace"))
                if nodes:
                    self._set(nodes, time.time()); self.status = f"ok {len(nodes)}"
                    try: self.file.write_text(json.dumps(dict(fetched=self.fetched, nodes=nodes), ensure_ascii=False), encoding="utf-8")
                    except OSError as ex: return len(nodes), f"could not save the node list: {ex}"
                    return len(nodes), ""
                errs.append("no usable lines")
            except Exception as ex:
                errs.append(str(getattr(ex, "reason", ex)))
        self.status = "failed: " + "; ".join(errs)
        return 0, "AllStarLink node list: " + "; ".join(errs)


# ---- who is connected to a node (AllStarLink stats server) -------------------------
STATS_URL = "https://stats.allstarlink.org/api/stats/{}"          # 30 requests per minute per IP are allowed; the program asks every 15 s for the node it is connected to


def parse_links(j) -> dict:
    """The nodes linked to a node, from the stats server's JSON ('stats' > 'data' > 'linkedNodes', with the 'nodes' string such as 'T63618,R70111'
    giving the mode: T = transceive, R = receive only, C = connecting). Returns {title, keyed, rows[{node, callsign, owner, location, site, mode, status}]}."""
    stats = (j or {}).get("stats") or {}; data = stats.get("data") or {}
    modes = {}
    for part in str(data.get("nodes") or "").split(","):
        part = part.strip()
        if len(part) > 1 and part[0].isalpha() and part[1:].isdigit(): modes[part[1:]] = part[0].upper()
        elif part.isdigit(): modes[part] = ""
    rows, seen = [], set()
    for n in data.get("linkedNodes") or []:
        if not isinstance(n, dict): continue
        node = str(n.get("name") or "").strip()
        if not node or node in seen: continue
        seen.add(node); srv = n.get("server") or {}
        rows.append(dict(node=node, callsign=str(n.get("callsign") or n.get("User_ID") or "").strip(), owner=str(n.get("User_ID") or "").strip(),
                         location=str(srv.get("Location") or "").strip(), site=str(srv.get("Server_Name") or "").strip(),
                         mode=modes.get(node, ""), status=str(n.get("Status") or "")))
    for node in data.get("links") or []:                            # linked, but not in the directory (private / numbers only): still show the number
        node = str(node).strip()
        if node and node not in seen: seen.add(node); rows.append(dict(node=node, callsign="", owner="", location="", site="", mode=modes.get(node, ""), status=""))
    me = (j or {}).get("node") or (stats.get("user_node") or {})
    srv = me.get("server") or {}
    return dict(title=str(srv.get("Server_Name") or me.get("callsign") or "").strip(), keyed=bool(data.get("keyed")), rows=rows)


def fetch_links(node: str, url: str = STATS_URL, timeout: float = 10) -> dict:
    """Blocking (call from a worker thread). Returns parse_links(...) plus 'error' ('' when fine)."""
    node = (node or "").strip()
    if not valid_node(node): return dict(title="", keyed=False, rows=[], error="Not a valid node number.")
    try:
        from . import net
        out = parse_links(json.loads(net.get(url.format(node), timeout, 2 * 1024 * 1024)))
        out["error"] = ""
        return out
    except Exception as ex:
        return dict(title="", keyed=False, rows=[], error=f"Cannot read the node's connections ({getattr(ex, 'reason', ex)})")
