"""'I am online' signal for the HELLAS Zone server panel (the right-hand Stations list).

While the program runs it sends, about every 30 seconds, a very small message to <server>/ping.php:
  installation id, program version, operating system, callsign + name (as typed in Settings), and what the station is doing right now
  (which network/target it listens to, which one it transmits to, whether it is transmitting).
No audio, no passwords, no files. Can be switched off in Settings > My station (setting share_presence)."""
import json, platform, sys, threading
from urllib.parse import urlencode
from .qt import QtCore, Signal
from . import net, diag

DEFAULT_URL = "https://hellaszone.com/digiconnect/ping.php"
EVERY_S = 30            # also how fast a change made in the server panel reaches the program (see 'rev')


def activity(ctx) -> dict:
    """What the station is doing, taken from the live session rules (nothing is invented)."""
    r = ctx.rules
    rx = [f"{x.target.net}:{x.target.id}" for x in r.rx][:4]
    tx = f"{r.tx_target.net}:{r.tx_target.id}" if r.tx_connected and r.tx_target else ""
    return dict(rx=",".join(rx), tx=tx, ptt=1 if r.ptt else 0)


class Presence(QtCore.QObject):
    rev_changed = Signal()        # the server says: something for this installation changed (licence, modes, messages) -> ask for the full answer now
    def __init__(self, ctx, updater, url: str = DEFAULT_URL, every: int = EVERY_S):
        super().__init__(); self.ctx, self.updater, self.url = ctx, updater, url
        self.last_ok = False; self.last_error = ""; self.sent = 0
        self._busy = False; self.rev = None
        self._timer = QtCore.QTimer(self); self._timer.setInterval(every * 1000); self._timer.timeout.connect(self.ping)

    def start(self):
        self.ping(); self._timer.start()

    def stop(self):
        self._timer.stop()

    def enabled(self) -> bool:
        return bool(self.ctx.store.settings.get("share_presence", True))

    def query(self) -> dict:
        s = self.ctx.store.settings; p = self.updater.params()
        q = dict(id=p["id"], v=p["v"], os=p["os"], arch=p["arch"], call=(s.get("callsign") or "").strip().upper(),
                 grid=(s.get("locator") or "").strip().upper(), eq=(s.get("equipment") or "")[:40])
        q.update(activity(self.ctx))
        return q

    def ping(self):
        if self._busy or not self.enabled(): return
        self._busy = True; q = self.query()
        threading.Thread(target=self._send, args=(q,), daemon=True).start()

    def _send(self, q: dict):
        try:
            r = json.loads(net.get(self.url + "?" + urlencode(q), 10, 64 * 1024).decode("utf-8"))
            self.last_ok = bool(r.get("ok")); self.last_error = "" if self.last_ok else str(r.get("err", "refused"))
            self.sent += 1
            rev = str(r.get("rev") or "")
            if rev:
                changed = self.rev is not None and rev != self.rev; self.rev = rev
                if changed: self.rev_changed.emit()
        except Exception as e:
            self.last_ok = False; self.last_error = f"{type(e).__name__}: {e}"
        finally:
            self._busy = False
            if not self.last_ok and self.sent == 0: diag.log(f"presence: {self.last_error}")
