"""Asking the owner of the VoIP server for an account. The program sends the request to the licence server (voip_request.php), the owner approves it in the panel,
and the program fetches the extension and the password from there (once: it confirms, the server wipes the password). Everything is a real HTTPS call; the
functions block, so the page runs them on a worker thread. Nothing is invented: an error is the server's own error code or the network's own message."""
import json, urllib.error, urllib.request
from urllib.parse import urlencode
from .. import net

BASE = "https://hellaszone.com/digiconnect/"
ERRORS = {"closed": "The server is not accepting account requests now", "consent": "You must agree before the request is sent", "name": "Write your name", "call": "The callsign does not look right",
          "too_many": "Too many requests from this address today; try again tomorrow", "pending": "A request with this callsign is already waiting for the owner",
          "unknown": "The server does not know this request (it may have been deleted)", "action": "The server did not understand the request"}


class SignupError(Exception):
    """code = the server's own error code ('' for a network problem); text = what is shown."""
    def __init__(self, code: str, text: str): super().__init__(text); self.code, self.text = code, text


def _post(base: str, **f) -> dict:
    req = urllib.request.Request(base.rstrip("/") + "/voip_request.php", urlencode({k: v for k, v in f.items() if v is not None}).encode(), method="POST",
                                 headers={"User-Agent": "DigiConnect (HELLAS Zone)", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=net.context()) as r: raw = r.read(64 * 1024)
        m = json.loads(raw)
    except urllib.error.HTTPError as ex: raise SignupError("", f"HTTP {ex.code}")
    except Exception as ex: raise SignupError("", str(getattr(ex, "reason", ex)))
    if not isinstance(m, dict): raise SignupError("", "unreadable answer")
    if not m.get("ok"):
        c = str(m.get("err", "")); raise SignupError(c, ERRORS.get(c, c or "refused"))
    return m


def is_open(base: str = "") -> bool:
    return bool(_post(base or BASE, action="info").get("open"))


def submit(name: str, call: str, want: str = "", msg: str = "", lang: str = "", base: str = "") -> tuple[int, str]:
    """Sends the request; returns (id, token). The token is the only proof that the request is yours: keep it."""
    m = _post(base or BASE, action="submit", name=name, call=call, want=want, msg=msg, lang=lang, consent="1", website="")
    return int(m.get("id", 0)), str(m.get("token", ""))


def status(rid: int, token: str, base: str = "") -> dict:
    """{'status': 'new'|'approved'|'rejected', ...}; when approved and not yet delivered: ext, password, server, port, transport, domain."""
    return _post(base or BASE, action="status", id=rid, token=token)


def ack(rid: int, token: str, base: str = ""):
    """The details are saved on this computer: the server may erase the password."""
    _post(base or BASE, action="ack", id=rid, token=token)
