"""Registration and licence of this installation, checked against the HELLAS Zone server (https://hellaszone.com/digiconnect/).

What is sent: the installation id, program version, operating system, and (once, from the first-run window) the name, callsign, DMR ID and
email the person typed, with their consent. The server answers with the state of this installation (demo with days left / full / locked), the
Donate address and what the program must do when the server cannot be reached (server setting: require | grace | allow).
Nothing here touches audio, passwords or the radio networks."""
import json, re, time
import urllib.error, urllib.request
from urllib.parse import urlencode
from . import net, diag

BASE = "https://hellaszone.com/digiconnect/"
DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=R6Z7EUN63FGKU"
CALL_RX = re.compile(r"^[0-9]?[A-Z]{1,2}[0-9][0-9A-Z]{0,3}[A-Z](/[0-9A-Z]{1,4})?$")
MAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIELDS = ("name", "call", "dmr_id", "mail")


class LicenseError(Exception):
    """The server could not be reached or gave an unreadable answer."""


class Verdict:
    """What the program must do now: kind = ok | register | blocked | offline."""
    def __init__(self, kind: str, state: str = "", left: str = "", msg: str = "", donate: str = ""):
        self.kind, self.state, self.left, self.msg, self.donate = kind, state, left, msg, donate or DONATE_URL

    @property
    def allowed(self) -> bool: return self.kind == "ok"

    def __repr__(self): return f"Verdict({self.kind}, {self.state!r}, {self.left!r}, {self.msg!r})"


def validate(d: dict) -> list[str]:
    """The fields (name, call, dmr_id, mail) that are not acceptable; empty list = fine."""
    bad = []
    if not (d.get("name") or "").strip(): bad.append("name")
    if not CALL_RX.match((d.get("call") or "").strip().upper()): bad.append("call")
    if not re.fullmatch(r"\d{6,9}", (d.get("dmr_id") or "").strip()): bad.append("dmr_id")
    if not MAIL_RX.match((d.get("mail") or "").strip()): bad.append("mail")
    return bad


class License:
    def __init__(self, store, params, base: str = BASE):
        self.store, self.params, self.base = store, params, base if base.endswith("/") else base + "/"
        self.last: Verdict | None = None

    # ---- the server's last good answer is kept, for the offline rules -------------------
    def cache(self) -> dict: return dict(self.store.settings.get("lic") or {})

    def _remember(self, m: dict):
        c = dict(state=m.get("state", ""), left=m.get("left", ""), msg=m.get("msg", ""), donate=m.get("donate", ""), registered=bool(m.get("registered", 1)),
                 offline=m.get("offline", "require"), offline_days=int(m.get("offline_days", 7) or 7), ts=time.time())
        self.store.settings["lic"] = c; self.store.save_settings()

    # ---- network (blocking: call from a worker thread, or before the window opens) ----------
    def _get(self, url: str, data: bytes | None = None) -> dict:
        try:
            if data is None: raw = net.get(url, 10, 256 * 1024)
            else:
                req = urllib.request.Request(url, data=data, method="POST", headers={"User-Agent": "DigiConnect (HELLAS Zone)", "Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=10, context=net.context()) as r: raw = r.read(256 * 1024)
            m = json.loads(raw)
        except urllib.error.HTTPError as ex: raise LicenseError(f"HTTP {ex.code}")
        except Exception as ex: raise LicenseError(str(getattr(ex, "reason", ex)))
        if not isinstance(m, dict): raise LicenseError("unreadable answer")
        return m

    def check(self) -> dict:
        """Asks the server for the state of this installation (manifest.php, the same call the update check makes)."""
        m = self._get(self.base + "manifest.php?" + urlencode(self.params()))
        if not m.get("ok"): raise LicenseError(str(m.get("err") or "refused"))
        self._remember(m); return m

    def register(self, d: dict, lang: str = "") -> dict:
        """Sends what the person typed (with consent). Returns the server's answer; raises LicenseError with the server's reason code in .args[0]."""
        p = self.params(); f = dict(id=p["id"], v=p["v"], os=p["os"], arch=p["arch"], shell=p["shell"], lang=lang, consent="1",
                                    name=d["name"].strip(), call=d["call"].strip().upper(), dmr_id=d["dmr_id"].strip(), mail=d["mail"].strip())
        m = self._get(self.base + "register.php", urlencode(f).encode())
        if not m.get("ok"): raise LicenseError(str(m.get("err") or "refused"))
        m["registered"] = 1; self._remember(m); return m

    # ---- decision -------------------------------------------------------------------------
    def verdict(self, answer: dict | None = None, error: str = "", now: float | None = None) -> Verdict:
        """answer = the server's answer (None when it could not be reached). The offline rules are the server's setting, remembered from the last answer."""
        now = time.time() if now is None else now
        if answer is not None:
            if not answer.get("registered", 1): v = Verdict("register", donate=answer.get("donate", ""))
            elif answer.get("state") in ("full", "demo"): v = Verdict("ok", answer["state"], answer.get("left", ""), "", answer.get("donate", ""))
            else: v = Verdict("blocked", answer.get("state", "locked"), "", answer.get("msg") or "This installation needs activation.", answer.get("donate", ""))
            self.last = v; return v
        c = self.cache(); text = "The licence server cannot be reached."
        if not c or not c.get("registered"):
            v = Verdict("offline", msg=text + " The first start needs a connection to register this program.")
        elif c.get("state") not in ("full", "demo"):
            v = Verdict("blocked", c.get("state", "locked"), "", c.get("msg") or "This installation needs activation.", c.get("donate", ""))
        elif c.get("offline") == "allow":
            v = Verdict("ok", c["state"], c.get("left", ""), "", c.get("donate", ""))
        elif c.get("offline") == "grace" and now - float(c.get("ts", 0)) < int(c.get("offline_days", 7)) * 86400:
            v = Verdict("ok", c["state"], c.get("left", ""), "", c.get("donate", ""))
        else:
            v = Verdict("offline", c.get("state", ""), c.get("left", ""), text + " This program must be able to reach the HELLAS Zone server to run.", c.get("donate", ""))
        self.last = v; return v

    def evaluate(self) -> Verdict:
        """Blocking: ask the server and decide."""
        try: return self.verdict(self.check())
        except LicenseError as ex:
            diag.log(f"licence: server not reachable: {ex}")
            return self.verdict(None, str(ex))
