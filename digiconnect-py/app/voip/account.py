"""The VoIP account the Admin gave to this installation (see signup.py), kept in step with the server.

States (settings "voip_req_state"): "" nothing asked, "pending" waiting for the Admin, "rejected", "linked" = the account exists on the server and this program holds its token.
A linked account is asked from the server again at every sign-in and every few minutes, so
  - a new password the Admin sets in the panel arrives by itself (nobody types anything),
  - a block (for a time, or until the Admin lifts it) stops the phone here, with the Admin's reason,
  - an account that was deleted on the server is noticed.
Everything is a real call to the licence server; nothing is invented. If the server cannot be reached, the saved details are used as they are."""
import threading, time
from ..qt import QtCore
from . import signup
from .. import i18n

AUTO = True            # automatic look-ups (recovering a lost link at start-up); the tests switch it off
EVERY_MS = 300000


class AccountSync(QtCore.QObject):
    note = QtCore.Signal(str)                 # a sentence for the VoIP page (English; the page translates it)
    account_changed = QtCore.Signal()         # extension / password / server in the settings were replaced: the page refreshes its fields
    state_changed = QtCore.Signal()           # the request / link / block state changed
    finished = QtCore.Signal(str, object)     # (kind, ("ok", answer) | ("err", SignupError)) after it was handled
    _done = QtCore.Signal(str, object, object)

    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx; self._timer = QtCore.QTimer(self); self._timer.setInterval(EVERY_MS); self._timer.timeout.connect(lambda: self.check(True))
        self._done.connect(self._handle)

    def start(self): self._timer.start()

    # ---- what is known
    @property
    def st(self) -> dict: return self.ctx.store.settings

    def state(self) -> str:
        s = self.st.get("voip_req_state", ""); return s if s in ("pending", "rejected", "linked") else ""

    def inst(self) -> str: return str(self.st.get("install_id", ""))

    def released(self) -> bool: return self.state() == "linked" and bool(self.st.get("voip_released"))

    def blocked(self):
        """(blocked now?, until (0 = until the Admin lifts it), reason)"""
        if not self.st.get("voip_block"): return False, 0, ""
        u = int(self.st.get("voip_block_until", 0) or 0)
        if u and u <= time.time(): return False, 0, ""
        return True, u, str(self.st.get("voip_block_reason", ""))

    def block_text(self) -> str:
        b, u, r = self.blocked()
        return "" if not b else i18n.tr("This account is blocked by the Admin") + (": " + r if r else "")

    def _save(self): self.ctx.store.save_settings()

    # ---- the calls (on a worker thread; the answer is handled on the Qt thread)
    def _run(self, kind: str, fn, silent: bool = True, then=None):
        def work():
            try: res = ("ok", fn())
            except signup.SignupError as ex: res = ("err", ex)
            except Exception as ex: res = ("err", signup.SignupError("", str(ex)))
            try: self._done.emit(kind, res, (silent, then))
            except RuntimeError: pass
        threading.Thread(target=work, daemon=True, name="voip-account").start()

    def submit(self, **f):
        f.setdefault("inst", self.inst()); self._run("submit", lambda: signup.submit(**f), False)

    def check(self, silent: bool = True, then=None) -> bool:
        """Asks the server about a waiting request or a linked account. then() is called afterwards in every case (also when the server cannot be reached)."""
        s = self.st
        if self.state() not in ("pending", "linked") or not s.get("voip_req_token"):
            if then: then()
            return False
        rid, tok, inst = int(s.get("voip_req_id", 0)), s["voip_req_token"], self.inst()
        if not silent: self.note.emit("Checking…")
        self._run("status", lambda: signup.status(rid, tok, inst=inst), silent, then); return True

    def recover(self, then=None):
        s = self.st; call = str(s.get("callsign", "")).strip()
        if not call or not self.inst(): 
            if then: then()
            return
        inst = self.inst(); self._run("recover", lambda: signup.recover(call, inst), True, then)

    def ensure_fresh(self, then):
        """Before signing in: take the newest details from the server (a new password, a block). With no link and no account, a lost link is looked for first."""
        if AUTO and self.state() in ("", "rejected") and not self.st.get("voip_user"): self.recover(then); return
        self.check(True, then)

    # ---- the answers
    def _handle(self, kind: str, res, extra):
        silent, then = extra; ok, val = res; s = self.st
        try:
            if ok == "err": self._error(kind, val, silent)
            elif kind == "submit":
                s.update(voip_req_id=val[0], voip_req_token=val[1], voip_req_state="pending", voip_req_reason=""); self._save(); self.note.emit("The request was sent. You will receive the account here as soon as the Admin approves it."); self.state_changed.emit()
            elif kind == "recover":
                s.update(voip_req_id=val[0], voip_req_token=val[1], voip_req_state="linked"); self._save()
                self.check(True, then); then = None                                           # the answer to this check calls then()
            else: self._status(val, silent)
        finally:
            self.finished.emit(kind, res)
            if then: then()

    def _error(self, kind: str, ex, silent: bool):
        s = self.st
        if ex.code == "unknown" and kind == "status":                                        # the server has no such request / account any more
            was = self.state(); s.update(voip_req_state="", voip_req_token="", voip_req_id=0, voip_block=False, voip_block_until=0, voip_block_reason="", voip_released=False); self._save(); self.state_changed.emit()
            self.note.emit("The Admin removed this account from the server: the fields are unlocked and you can use any server. The details saved here stay as they are." if was == "linked" else "The server no longer has this request.")
        elif kind != "recover" and not (silent and not ex.code): self.note.emit(ex.text if ex.code else "The server cannot be reached now: " + ex.text)

    def _status(self, a: dict, silent: bool):
        s = self.st; state = a.get("status")
        if state == "rejected":
            s.update(voip_req_state="rejected", voip_req_token="", voip_req_reason=a.get("reason", "")); self._save(); self.state_changed.emit()
            self.note.emit("The Admin did not approve the request." + (" " + a["reason"] if a.get("reason") else "")); return
        if state != "approved":
            if not silent or self.state() == "pending": self.note.emit("Your request is still waiting for the Admin.")
            return
        if a.get("released"):                                                                 # the Admin let this user go for now: nothing is changed or taken back, the fields are free
            was = bool(s.get("voip_released")); s.update(voip_req_state="linked", voip_released=True, voip_block=False, voip_block_until=0, voip_block_reason=""); self._save(); self.state_changed.emit()
            if not was: self.note.emit("The Admin has let you use another server for now: the fields are unlocked and the details saved here stay as they are.")
            return
        was_free = bool(s.get("voip_released")); first = self.state() != "linked"; ph = self.ctx.phone
        new = dict(voip_user=str(a.get("ext", "")), voip_pw=str(a.get("password", "")), voip_server=str(a.get("server", "")) or s.get("voip_server", ""), voip_port=int(a.get("port") or 5060),
                   voip_transport=str(a.get("transport", "udp")).lower(), voip_domain=str(a.get("domain", "")), voip_auth_user="")
        changed = any(s.get(k) != v for k, v in new.items()); was_in = ph.reg_state in ("registered", "registering")
        s.update(new); s.update(voip_req_state="linked", voip_remember=True, voip_released=False)
        if first: s["voip_auto"] = True                                                       # an account that came from the server signs in when the program starts (the box in Account can be unticked)
        bl_before = self.blocked()[0]
        s.update(voip_block=bool(a.get("blocked")), voip_block_until=int(a.get("block_until") or 0), voip_block_reason=str(a.get("block_reason", "")))
        self._save(); bl = self.blocked()[0]
        if changed: self.account_changed.emit()
        self.state_changed.emit()
        if bl and not bl_before:
            ph.hangup(); ph.sign_out(0.0); m = self.block_text(); self.ctx.note_problem(m); self.ctx.toast.emit(m); self.note.emit(m)
        elif bl_before and not bl: self.note.emit("The block was lifted. You can sign in again.")
        elif was_free: self.note.emit("The Admin has put the account back: your details were replaced by the server's and locked."); self.state_changed.emit()
        elif first:
            self.note.emit("The account was approved and filled in: extension {}. Press Sign in.".format(new["voip_user"]))
            self.ctx.toast.emit("Your VoIP account is ready for use: extension {}.".format(new["voip_user"]))             # the Admin created it: the user is told, also when another page is open
        elif changed and not bl: self.note.emit("The Admin changed the account details; they were updated here.")
        if changed and was_in and not bl: ph.sign_out(0.0); ph.sign_in()                    # a phone that was signed in is signed in again with the Admin's new details; nobody types anything
