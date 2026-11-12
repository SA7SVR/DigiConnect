"""Registration and licence of this installation, checked against the HELLAS Zone server (https://hellaszone.com/digiconnect/).

What is sent: the installation id, program version, operating system, and (once, from the first-run window) the name, callsign, DMR ID and
email the person typed, with their consent. The server answers with the state of this installation (demo with days left / full / locked), the
Donate address and what the program must do when the server cannot be reached (server setting: require | grace | allow).
Nothing here touches audio, passwords or the radio networks."""
import json, re, secrets, time
import urllib.error, urllib.request
from urllib.parse import urlencode
from . import net, diag, hwid, sigverify

BASE = "https://hellaszone.com/digiconnect/"
# Public keys that the server's licence answers must be signed with (Ed25519, base64). A list, so a new key can be added before the old one is retired.
PUBKEYS = ["82Ej9S1qEVWkbA3VXGqpXx+WsNmriBoJpi5gO5utJbM="]
DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=R6Z7EUN63FGKU"
CALL_RX = re.compile(r"^[0-9]?[A-Z]{1,2}[0-9][0-9A-Z]{0,3}[A-Z](/[0-9A-Z]{1,4})?$")
MAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIELDS = ("name", "call", "dmr_id", "mail")


class LicenseError(Exception):
    """The server could not be reached or gave an unreadable answer."""


class Verdict:
    """What the program must do now: kind = ok | register | blocked | offline."""
    def __init__(self, kind: str, state: str = "", left: str = "", msg: str = "", donate: str = "", info: dict | None = None):
        self.kind, self.state, self.left, self.msg, self.donate = kind, state, left, msg, donate or DONATE_URL
        self.info = info or {}                                                    # the signed facts: owner, call, code, offer, amount, other_pc ...

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
    def __init__(self, store, params, base: str = BASE, hw: str | None = None, pubkeys: list | None = None):
        self.store, self.params, self.base = store, params, base if base.endswith("/") else base + "/"
        self.hw = hw or hwid.get(); self.pubkeys = list(PUBKEYS if pubkeys is None else pubkeys)
        self.last: Verdict | None = None; self.msgs: list = []

    def _p(self) -> dict:
        p = dict(self.params()); p["hw"] = self.hw; return p

    # ---- the signed answer ----------------------------------------------------------------
    def _trusted(self, payload: str, sig: str) -> dict | None:
        """The facts of a signed answer, or None when the signature is not one of ours or the answer is for another installation/computer."""
        try:
            if not payload or not sig or not any(sigverify.verify(k, payload.encode(), sig) for k in self.pubkeys): return None
            d = json.loads(payload)
            if not isinstance(d, dict) or d.get("id") != self._p()["id"]: return None
            if d.get("state") == "full" and not d.get("other_pc") and d.get("hw") and d["hw"] != self.hw: return None    # a licence of another computer
            return d
        except Exception:
            return None

    def _verify(self, m: dict, nonce: str) -> dict:
        """Only the SIGNED part of the answer is believed. A nonce makes an old recorded answer useless (replay)."""
        if not m.get("ok"): raise LicenseError(str(m.get("err") or "refused"))
        if not m.get("payload") or not m.get("sig"): raise LicenseError("unsigned answer (the server has no licence key)")
        d = self._trusted(m["payload"], m["sig"])
        if d is None: raise LicenseError("bad signature")
        if d.get("n") != nonce: raise LicenseError("old answer (replay)")
        d["_payload"], d["_sig"] = m["payload"], m["sig"]
        self.msgs = m.get("msgs") or self.msgs
        return d

    # ---- the server's last good answer is kept (signed), for the offline rules -------------------
    def cache(self) -> dict:
        c = self.store.settings.get("lic") or {}
        d = self._trusted(c.get("payload", ""), c.get("sig", ""))
        if d is None: return {}
        d["ts"] = float(d.get("now") or 0); d["registered"] = bool(d.get("registered", 1)); return d

    def _remember(self, d: dict):
        self.store.settings["lic"] = {"payload": d["_payload"], "sig": d["_sig"]}
        self.store.settings["lic_seen"] = max(float(self.store.settings.get("lic_seen") or 0), time.time()); self.store.save_settings()

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

    def _ask(self, page: str, fields: dict, post: bool) -> dict:
        n = secrets.token_hex(16); f = dict(fields, n=n)
        m = self._get(self.base + page + ("" if post else "?" + urlencode(f)), urlencode(f).encode() if post else None)
        d = self._verify(m, n); self._remember(d); return d

    def check(self) -> dict:
        """Asks the server for the state of this installation (manifest.php, the same call the update check makes)."""
        return self._ask("manifest.php", self._p(), False)

    def register(self, d: dict, lang: str = "") -> dict:
        """Sends what the person typed (with consent). Returns the server's answer; raises LicenseError with the server's reason code in .args[0]."""
        p = self._p(); f = dict(id=p["id"], v=p["v"], os=p["os"], arch=p["arch"], shell=p["shell"], hw=p["hw"], lang=lang, consent="1",
                                name=d["name"].strip(), call=d["call"].strip().upper(), dmr_id=d["dmr_id"].strip(), mail=d["mail"].strip())
        return self._ask("register.php", f, True)

    def redeem(self, code: str) -> dict:
        """An activation code (demo extension or licence). Raises LicenseError with bad_code | expired | used | other_pc."""
        p = self._p()
        d = self._ask("api.php", dict(action="redeem", id=p["id"], os=p["os"], hw=p["hw"], code=code.strip()), True)
        return d

    def inbox_send(self, body: str, topic: str = "", subject: str = "", lang: str = "") -> bool:
        """A message from the user to the owner (shown in the control panel). Returns True when the server stored it."""
        p = self._p(); c = self.cache()
        f = dict(id=p["id"], os=p["os"], version=p["v"], lang=lang, topic=topic, subject=subject, body=body, src="app", call=c.get("call", ""))
        m = self._get(self.base + "inbox.php", urlencode(f).encode())
        if not m.get("ok"): raise LicenseError(str(m.get("error") or "refused"))
        return True

    def replies(self) -> list:
        """The owner's replies to this installation (newest first): [{id, t, subject, reply}]."""
        m = self._get(self.base + "inbox.php?" + urlencode(dict(poll="1", id=self._p()["id"])))
        return list(m.get("replies") or [])

    # ---- decision -------------------------------------------------------------------------
    def verdict(self, answer: dict | None = None, error: str = "", now: float | None = None) -> Verdict:
        """answer = the server's verified answer (None when it could not be reached). The offline rules are the server's setting, remembered from the last answer."""
        now = time.time() if now is None else now
        if answer is not None:
            if not answer.get("registered", 1): v = Verdict("register", donate=answer.get("donate", ""), info=answer)
            elif answer.get("state") in ("full", "demo", "free"): v = Verdict("ok", answer["state"], answer.get("left", ""), "", answer.get("donate", ""), answer)
            else: v = Verdict("blocked", answer.get("state", "locked"), "", answer.get("msg") or "This installation needs activation.", answer.get("donate", ""), answer)
            self.last = v; return v
        c = self.cache(); text = "The licence server cannot be reached."
        if error.startswith(("unsigned", "bad signature", "old answer")): text = f"The licence answer could not be trusted ({error})."
        rolled_back = now + 86400 < float(self.store.settings.get("lic_seen") or 0)               # the computer clock was set back to stay inside the offline period
        if not c or not c.get("registered"):
            v = Verdict("offline", msg=text + " The first start needs a connection to register this program.")
        elif c.get("state") not in ("full", "demo", "free"):
            v = Verdict("blocked", c.get("state", "locked"), "", c.get("msg") or "This installation needs activation.", c.get("donate", ""), c)
        elif c.get("exp") and now > float(c["exp"]) and c.get("state") != "free":
            v = Verdict("offline", c["state"], "", text + " The licence period has ended; the server must be reached.", c.get("donate", ""), c)
        elif c.get("offline") == "allow" and not rolled_back:
            v = Verdict("ok", c["state"], c.get("left", ""), "", c.get("donate", ""), c)
        elif c.get("offline") == "grace" and not rolled_back and -600 <= now - float(c.get("ts", 0)) < int(c.get("offline_days", 7)) * 86400:
            v = Verdict("ok", c["state"], c.get("left", ""), "", c.get("donate", ""), c)
        else:
            v = Verdict("offline", c.get("state", ""), c.get("left", ""), text + " This program must be able to reach the HELLAS Zone server to run.", c.get("donate", ""), c)
        self.last = v; return v

    def evaluate(self) -> Verdict:
        """Blocking: ask the server and decide."""
        try: return self.verdict(self.check())
        except LicenseError as ex:
            diag.log(f"licence: server not reachable: {ex}")
            return self.verdict(None, str(ex))
