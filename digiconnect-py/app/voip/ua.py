"""The SIP user agent (RFC 3261): sign-in (REGISTER with digest), calls in and out (INVITE / ACK / BYE / CANCEL), and who is busy (SUBSCRIBE / NOTIFY, RFC 6665).

All the work runs on ONE worker thread (a queue plus timers), so the logic needs no locks; the sockets only hand data to that thread. Callbacks come from
that thread too: a user interface must pass them on to its own thread (the Qt wrapper in phone.py does)."""
import heapq, itertools, queue, re, socket, ssl, threading, time
from urllib.parse import quote
from . import sipmsg as S, sdp as SDP
from .rtp import RtpSession

T1, T2, TIMER_B = 0.5, 4.0, 32.0
USER_AGENT = "DigiConnect-VoIP"

# what a refusal means, in words for a person (the number and the server's own words are always added)
FAIL_TEXT = {400: "The server did not understand the request", 401: "Wrong username or password", 403: "The server refused (wrong username or password, or this account may not connect from here)",
             404: "No such number", 407: "Wrong username or password", 408: "No answer from the server", 480: "Not available right now", 484: "The number is incomplete", 486: "Busy",
             487: "Cancelled", 488: "The other side does not accept this audio format", 500: "Server error", 503: "Not available right now (the other side is not signed in or the service is busy)", 600: "Busy everywhere", 603: "Declined"}


def fail_text(code: int, reason: str = "") -> str:
    base = FAIL_TEXT.get(code) or ("Refused" if code >= 400 else "Failed")
    return f"{base} ({code} {reason})".strip() if reason and reason.lower() not in base.lower() else f"{base} ({code})"


class Config:
    def __init__(self, server="", port=5060, transport="udp", user="", password="", auth_user="", domain="", display_name="", expires=300, bind_rtp=(12000, 12999), tls_verify=True, tls_ca=""):
        self.server, self.port, self.transport = server.strip(), int(port or 5060), (transport or "udp").lower()
        self.user, self.password, self.auth_user = user.strip(), password, (auth_user or user).strip()
        self.domain = (domain or server).strip(); self.display_name = display_name.strip(); self.expires = int(expires or 300); self.bind_rtp = bind_rtp; self.tls_verify, self.tls_ca = bool(tls_verify), tls_ca


class Transport:
    """UDP, TCP or TLS to the server. Received messages go to on_data(bytes) (one SIP message each)."""

    def __init__(self, cfg: Config, on_data, on_closed, log):
        self.cfg, self.on_data, self.on_closed, self.log = cfg, on_data, on_closed, log; self.sock = None; self.closed = False; self.local = ("0.0.0.0", 0); self.remote = (cfg.server, cfg.port); self._lock = threading.Lock()

    @property
    def reliable(self) -> bool: return self.cfg.transport in ("tcp", "tls")

    @property
    def token(self) -> str: return self.cfg.transport.upper()

    def open(self):
        infos = socket.getaddrinfo(self.cfg.server, self.cfg.port, socket.AF_INET, socket.SOCK_DGRAM if self.cfg.transport == "udp" else socket.SOCK_STREAM)
        if not infos: raise OSError("The server name could not be found")
        self.remote = infos[0][4]
        if self.cfg.transport == "udp":
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", 0)); s.connect(self.remote)           # connect: the address of the interface that reaches the server
        else:
            s = socket.create_connection(self.remote, timeout=10)
            if self.cfg.transport == "tls":
                ctx = ssl.create_default_context()
                try:
                    import certifi; ctx.load_verify_locations(certifi.where())
                except Exception: pass
                if self.cfg.tls_ca: ctx.load_verify_locations(self.cfg.tls_ca)
                if not self.cfg.tls_verify: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE          # only when the user switches the check off for a server with its own certificate
                try: s = ctx.wrap_socket(s, server_hostname=self.cfg.server)
                except ssl.SSLCertVerificationError as ex: s.close(); raise OSError(f"The server's certificate is not trusted ({ex.verify_message})")
        self.local = s.getsockname(); self.sock = s; s.settimeout(0.5)
        threading.Thread(target=self._loop, daemon=True, name="sip-rx").start()

    def _loop(self):
        buf = b""
        while not self.closed:
            try: data = self.sock.recv(65535)
            except socket.timeout: continue
            except (OSError, ssl.SSLError) as ex:
                if not self.closed: self.closed = True; self.on_closed(str(ex))
                return
            if not data:
                if self.reliable and not self.closed: self.closed = True; self.on_closed("The server closed the connection")
                if not self.reliable: continue
                return
            if not self.reliable: self.on_data(data); continue
            buf += data
            while True:
                n = S.frame_length(buf)
                if n < 0: buf = buf[-n:]; continue
                if n == 0: break
                self.on_data(buf[:n]); buf = buf[n:]

    def send(self, data: bytes):
        with self._lock:
            try: self.sock.send(data)
            except (OSError, ssl.SSLError) as ex: self.log(f"send failed: {ex}")

    def close(self):
        self.closed = True
        try: self.sock.close()
        except Exception: pass


class ClientTx:
    def __init__(self, req: S.Message, on_response, on_timeout):
        self.req, self.on_response, self.on_timeout = req, on_response, on_timeout; self.is_invite = req.method == "INVITE"; self.done = False; self.provisional = False; self.interval = T1; self.timer = None; self.deadline = time.time() + TIMER_B * (1 if self.is_invite else 1); self.ack = None


class Call:
    """One call. Read its fields from any thread; use its methods (they post to the worker thread)."""

    def __init__(self, ua: "UserAgent", direction: str, remote_uri: str):
        self.ua, self.direction, self.remote_uri = ua, direction, remote_uri; self.state = "new"; self.end_reason = ""; self.created = time.time(); self.answered_at = 0.0
        self.call_id = ""; self.local_tag = S.new_tag(); self.remote_tag = ""; self.local_uri = ""; self.remote_target = ""; self.route_set: list[str] = []; self.cseq = 1; self.remote_cseq = 0
        self.remote_user = ""; self.remote_name = ""; self.invite: S.Message | None = None; self.invite_tx: ClientTx | None = None; self.media: RtpSession | None = None; self.remote_sdp = None
        self.cancel_requested = False; self.dtmf_in: list[str] = []; self.local_sdp = b""; self.final_resp: S.Message | None = None; self.acked = False; self.muted = False; self.held_by_remote = False
        self.auth_tries = 0; self.ring_timer = None; self.resp_timer = None; self.ended_cb = None

    # thread-safe API
    def answer(self): self.ua.post(lambda: self.ua._answer(self))
    def reject(self, code: int = 603): self.ua.post(lambda: self.ua._reject(self, code))
    def hangup(self): self.ua.post(lambda: self.ua._hangup(self))
    def send_dtmf(self, digit: str): self.ua.post(lambda: self.media and self.media.send_dtmf(digit))

    @property
    def active(self) -> bool: return self.state == "active"

    @property
    def duration(self) -> float: return (time.time() - self.answered_at) if self.answered_at and self.state == "active" else 0.0


class Subscription:
    def __init__(self, ext: str, event: str):
        self.ext, self.event = ext, event; self.call_id = S.new_call_id(); self.local_tag = S.new_tag(); self.remote_tag = ""; self.cseq = 1; self.state = "new"; self.route_set = []; self.target = ""
        self.timer = None; self.expires = 300; self.auth_tries = 0; self.fails = 0; self.active = False; self.tx = None


class UserAgent:
    def __init__(self, cfg: Config, on_event=None, log=None):
        self.cfg = cfg; self.on_event = on_event or (lambda *a, **k: None); self._log = log or (lambda t: None)
        self.q: "queue.Queue" = queue.Queue(); self.timers: list = []; self._tc = itertools.count(); self.running = False; self.tr: Transport | None = None
        self.reg_state = "unregistered"; self.reg_text = ""; self.reg_call_id = S.new_call_id(); self.reg_cseq = 0; self.reg_tag = S.new_tag(); self.reg_tx = None; self.reg_tries = 0; self.reg_backoff = 0; self.reg_timer = None; self._reg_fail_final = False
        self.pub_ip = ""; self.pub_port = 0; self.txs: dict[str, ClientTx] = {}; self.calls: dict[str, Call] = {}; self.subs: dict[str, Subscription] = {}; self.sub_by_callid: dict[str, Subscription] = {}
        self.server_txs: dict[tuple, S.Message] = {}; self.watch_list: list[tuple[str, str]] = []; self.presence: dict[str, tuple[str, str]] = {}; self.keepalive_timer = None; self.nc = 0
        self.stopping = False; self.auth_cache: dict[str, dict] = {}

    # ---- plumbing ----------------------------------------------------------------------------------------------
    def log(self, t: str):
        try: self._log(t)
        except Exception: pass

    def emit(self, name: str, **kw):
        try: self.on_event(name, **kw)
        except Exception as ex: self.log(f"event handler error: {ex!r}")

    def post(self, fn):
        if self.running or not self.stopping: self.q.put(fn)

    def call_later(self, delay: float, fn):
        t = [time.time() + delay, next(self._tc), fn, True]; heapq.heappush(self.timers, t); self.q.put(lambda: None); return t

    @staticmethod
    def cancel(t):
        if t: t[3] = False

    def _worker(self):
        while self.running:
            now = time.time(); timeout = 1.0
            while self.timers and (not self.timers[0][3] or self.timers[0][0] <= now):
                t = heapq.heappop(self.timers)
                if t[3]:
                    try: t[2]()
                    except Exception as ex: self.log(f"timer error: {ex!r}")
            if self.timers: timeout = max(0.01, min(1.0, self.timers[0][0] - time.time()))
            try: fn = self.q.get(timeout=timeout)
            except queue.Empty: continue
            try: fn()
            except Exception as ex:
                import traceback; self.log("worker error: " + "".join(traceback.format_exception(ex))[-600:])

    # ---- start / stop -------------------------------------------------------------------------------------------
    def start(self):
        if self.running: return
        self.running = True; self.stopping = False
        threading.Thread(target=self._worker, daemon=True, name="sip-worker").start()
        self.post(self._open_and_register)

    def stop(self, wait: float = 2.0):
        """Ends the calls, leaves the server (REGISTER with Expires 0) and closes the sockets. Waits a little for the server's answer."""
        if not self.running: return
        done = threading.Event(); self.stopping = True
        def work():
            for c in list(self.calls.values()): self._hangup(c)
            for sub in list(self.subs.values()): self._unsubscribe(sub)
            if self.reg_state == "registered": self._register(0)
            self.call_later(min(wait, 1.5), done.set)
        self.q.put(work); done.wait(wait + 0.5)
        self.running = False
        if self.tr: self.tr.close()
        self.reg_state = "unregistered"

    # ---- registration -------------------------------------------------------------------------------------------
    def _set_reg(self, state: str, text: str = ""):
        self.reg_state, self.reg_text = state, text; self.emit("registration", state=state, text=text)

    def _open_and_register(self):
        try:
            self.tr = Transport(self.cfg, lambda d: self.post(lambda: self._on_data(d)), lambda why: self.post(lambda: self._on_closed(why)), self.log); self.tr.open()
        except Exception as ex:
            self._set_reg("failed", f"Cannot reach the server {self.cfg.server}:{self.cfg.port} ({getattr(ex, 'strerror', None) or ex})"); self._retry_register(); return
        self.log(f"transport {self.cfg.transport.upper()} {self.tr.local} -> {self.tr.remote}")
        self._register(self.cfg.expires)

    def _on_closed(self, why: str):
        if self.stopping: return
        self.log(f"connection lost: {why}"); self._set_reg("failed", f"Connection lost ({why})")
        for c in list(self.calls.values()): self._end(c, "Connection lost")
        self.cancel(self.keepalive_timer); self._retry_register()

    def _retry_register(self):
        if self.stopping or self._reg_fail_final: return
        self.reg_backoff = min(120, max(15, self.reg_backoff * 2 if self.reg_backoff else 15))
        self.cancel(self.reg_timer); self.reg_timer = self.call_later(self.reg_backoff, lambda: self._reconnect())

    def _reconnect(self):
        if self.stopping: return
        if self.tr and self.tr.closed or self.reg_state in ("failed",):
            try: self.tr and self.tr.close()
            except Exception: pass
            self._open_and_register()
        else: self._register(self.cfg.expires)

    def contact_uri(self) -> str:
        ip, port = (self.tr.local if self.tr else ("0.0.0.0", 0))
        param = "" if self.cfg.transport == "udp" else f";transport={self.cfg.transport}"
        return f"sip:{self.cfg.user}@{ip}:{port}{param}"

    def _via(self, branch: str) -> str:
        ip, port = self.tr.local
        return f"SIP/2.0/{self.tr.token} {ip}:{port};branch={branch};rport"

    def _from(self, tag: str) -> str:
        n = self.cfg.display_name; dn = f'"{n}" ' if n else ""
        return f"{dn}<sip:{self.cfg.user}@{self.cfg.domain}>;tag={tag}"

    def _base(self, method: str, uri: str, call_id: str, cseq: int, frm: str, to: str, branch: str = "") -> S.Message:
        m = S.Message(method=method, uri=uri); m.add("Via", self._via(branch or S.new_branch())); m.add("Max-Forwards", "70"); m.add("From", frm); m.add("To", to)
        m.add("Call-ID", call_id); m.add("CSeq", f"{cseq} {method}"); m.add("User-Agent", USER_AGENT); return m

    def _register(self, expires: int):
        if not self.tr or self.tr.closed: return
        self.reg_cseq += 1; uri = f"sip:{self.cfg.domain}"
        m = self._base("REGISTER", uri, self.reg_call_id, self.reg_cseq, self._from(self.reg_tag), f"<sip:{self.cfg.user}@{self.cfg.domain}>")
        m.add("Contact", f"<{self.contact_uri()}>;expires={expires}"); m.add("Expires", str(expires)); m.add("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, NOTIFY, MESSAGE, INFO, UPDATE")
        a = self.auth_cache.get("REGISTER")
        if a: self._authorize(m, a, uri)
        if expires and self.reg_state != "registered": self._set_reg("registering", "")
        self._send_request(m, lambda r, expires=expires: self._on_reg_response(r, expires), lambda: self._on_reg_timeout(expires))

    def _authorize(self, m: S.Message, ch: dict, uri: str, proxy: bool = False):
        self.nc += 1
        key = ch.get("nonce", ""); cnt = ch.setdefault("_nc", 0) + 1; ch["_nc"] = cnt
        m.set("Proxy-Authorization" if proxy else "Authorization", S.digest_response(ch, self.cfg.auth_user, self.cfg.password, m.method, uri, nc=cnt, body=m.body))

    def _challenge(self, r: S.Message):
        proxy = r.status == 407
        hdrs = r.all("proxy-authenticate" if proxy else "www-authenticate")
        chs = [S.parse_challenge(h) for h in hdrs]; chs = [c for c in chs if S.supported(c)]
        if not chs: return None, proxy
        chs.sort(key=lambda c: 0 if (c.get("algorithm", "").upper().startswith("SHA-256")) else 1)
        return chs[0], proxy

    def _on_reg_response(self, r: S.Message, expires: int):
        if r.status < 200: return
        if r.status in (401, 407):
            ch, proxy = self._challenge(r)
            first = "REGISTER" not in self.auth_cache or self.auth_cache["REGISTER"].get("nonce") != (ch or {}).get("nonce") or ((ch or {}).get("stale", "").lower() == "true")
            if ch and first and self.reg_tries < 1:
                self.reg_tries += 1; self.auth_cache["REGISTER"] = ch; ch.pop("_nc", None); self._register(expires); return
            self.reg_tries = 0; self.auth_cache.pop("REGISTER", None)
            self._reg_fail_final = True                                              # a wrong password is never retried by itself: the server could lock this address out
            self._set_reg("failed", fail_text(r.status, r.reason) + " - not trying again; check the username and password and press Sign in"); return
        self.reg_tries = 0
        if 200 <= r.status < 300:
            if expires == 0: self._set_reg("unregistered", ""); return
            self.reg_backoff = 0; self._reg_fail_final = False
            self._learn_public(r)
            exp = self._reg_expires(r, expires)
            self._set_reg("registered", f"Registered as {self.cfg.user}@{self.cfg.domain}")
            self.cancel(self.reg_timer); self.reg_timer = self.call_later(max(20, exp * 0.8), lambda: self._register(self.cfg.expires))
            self._start_keepalive()
            if self.watch_list and not self.subs: self._start_watch()
            return
        if r.status == 423:                                                           # interval too brief: the server wants a longer time
            m = re.search(r"(\d+)", r.get("min-expires")); 
            if m and self.reg_tries < 3: self.reg_tries += 1; self.cfg.expires = int(m.group(1)); self._register(self.cfg.expires); return
        self._reg_fail_final = r.status in (400, 403, 404, 405, 484)
        self._set_reg("failed", fail_text(r.status, r.reason)); self._retry_register()

    def _reg_expires(self, r: S.Message, asked: int) -> int:
        mine = self.cfg.user
        for c in r.all("contact"):
            if mine in c or str(self.tr.local[1]) in c:
                m = re.search(r";\s*expires=(\d+)", c)
                if m: return int(m.group(1))
        m = re.match(r"\s*(\d+)", r.get("expires"))
        return int(m.group(1)) if m else asked

    def _on_reg_timeout(self, expires: int):
        if expires == 0: return
        self._set_reg("failed", f"The server {self.cfg.server} did not answer (no reply in {int(TIMER_B)} s)"); self._retry_register()

    def _learn_public(self, r: S.Message):
        v = r.all("via"); 
        if not v: return
        m1 = re.search(r";\s*received=([\d.]+)", v[0]); m2 = re.search(r";\s*rport=(\d+)", v[0])
        if m1: self.pub_ip = m1.group(1)
        if m2: self.pub_port = int(m2.group(1))

    def _start_keepalive(self):
        self.cancel(self.keepalive_timer)
        def ka():
            if self.tr and not self.tr.closed and self.reg_state == "registered": self.tr.send(b"\r\n\r\n")
            self.keepalive_timer = self.call_later(25 if self.cfg.transport == "udp" else 55, ka)
        self.keepalive_timer = self.call_later(25 if self.cfg.transport == "udp" else 55, ka)

    # ---- transactions ---------------------------------------------------------------------------------------------
    def _send_request(self, m: S.Message, on_response, on_timeout=None) -> ClientTx:
        tx = ClientTx(m, on_response, on_timeout or (lambda: None)); self.txs[m.branch] = tx
        self.tr.send(m.to_bytes()); self._dump("out", m)
        if not self.tr.reliable: self._schedule_retx(tx)
        else: tx.timer = self.call_later(TIMER_B, lambda: self._tx_timeout(tx))
        return tx

    def _schedule_retx(self, tx: ClientTx):
        if tx.done: return
        if time.time() >= tx.deadline: self._tx_timeout(tx); return
        def retx():
            if tx.done: return
            if tx.is_invite and tx.provisional: self._schedule_retx(tx) if False else None; return
            self.tr.send(tx.req.to_bytes()); tx.interval = min(tx.interval * 2, T2) if not tx.is_invite else tx.interval * 2; self._schedule_retx(tx)
        tx.timer = self.call_later(min(tx.interval, max(0.05, tx.deadline - time.time())), retx)
        if tx.is_invite: self.call_later(TIMER_B, lambda: (not tx.done and not tx.provisional) and self._tx_timeout(tx))

    def _tx_timeout(self, tx: ClientTx):
        if tx.done: return
        tx.done = True; self.txs.pop(tx.req.branch, None); tx.on_timeout()

    def _finish_tx(self, tx: ClientTx):
        tx.done = True; self.cancel(tx.timer)
        self.call_later(32 if not self.tr.reliable else 1, lambda: self.txs.pop(tx.req.branch, None))

    def _dump(self, way: str, m: S.Message):
        first = f"{m.method} {m.uri}" if m.is_request else f"{m.status} {m.reason}"
        self.log(f"SIP {way}: {first}  [{m.get('cseq')}]")
        if getattr(self, "debug", False):
            txt = m.to_bytes().decode("utf-8", "replace")
            txt = re.sub(r"(?im)^((?:proxy-)?authorization:).*$", r"\1 (hidden)", txt); self.log(txt)

    # ---- receiving -----------------------------------------------------------------------------------------------------
    def _on_data(self, data: bytes):
        m = S.parse(data)
        if not m: return
        self._dump("in", m)
        if m.is_request: self._on_request(m)
        else: self._on_response(m)

    def _on_response(self, r: S.Message):
        tx = self.txs.get(r.branch)
        if not tx:
            if r.cseq[1] == "INVITE" and 200 <= r.status < 300:                      # a retransmitted 2xx for an INVITE we already finished: ACK it again
                c = self.calls.get(r.call_id)
                if c and c.state in ("active", "connecting") and c.direction == "out": self._send_ack(c)
            return
        if r.status < 200:
            tx.provisional = True; tx.on_response(r); return
        if tx.done:
            if tx.is_invite and tx.ack and r.status >= 300: self.tr.send(tx.ack.to_bytes())
            return
        if tx.is_invite and r.status >= 300:
            tx.ack = self._ack_for_error(tx.req, r); self.tr.send(tx.ack.to_bytes())
        self._finish_tx(tx); tx.on_response(r)

    def _ack_for_error(self, req: S.Message, r: S.Message) -> S.Message:
        a = S.Message(method="ACK", uri=req.uri); a.add("Via", req.all("via")[0]); a.add("Max-Forwards", "70"); a.add("From", req.get("from")); a.add("To", r.get("to")); a.add("Call-ID", req.call_id)
        a.add("CSeq", f"{req.cseq[0]} ACK"); 
        for rt in req.all("route"): a.add("Route", rt)
        return a

    def _reply(self, req: S.Message, status: int, reason: str, extra=None, body: bytes = b"", to_tag: str = "") -> S.Message:
        r = S.Message(status=status, reason=reason)
        for v in req.all("via"): r.add("Via", v)
        for k in ("From", "Call-ID", "CSeq"): r.add(k, req.get(k))
        to = req.get("to")
        if to_tag and ";tag=" not in to: to += f";tag={to_tag}"
        r.add("To", to)
        for k, v in (extra or []): r.add(k, v)
        r.add("User-Agent", USER_AGENT)
        if body: r.add("Content-Type", "application/sdp")
        r.body = body; self.tr.send(r.to_bytes()); self._dump("out", r); return r

    def _on_request(self, m: S.Message):
        key = (m.branch, m.method if m.method != "ACK" else "INVITE")
        if m.method not in ("ACK",) and key in self.server_txs:                       # a retransmitted request: the same answer again
            last = self.server_txs[key]
            if last is not None: self.tr.send(last.to_bytes())
            return
        meth = m.method
        if meth == "OPTIONS": self.server_txs[key] = self._reply(m, 200, "OK", [("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, NOTIFY, INFO, UPDATE"), ("Accept", "application/sdp")])
        elif meth == "INVITE": self._on_invite(m, key)
        elif meth == "ACK": self._on_ack(m)
        elif meth == "BYE": self._on_bye(m, key)
        elif meth == "CANCEL": self._on_cancel(m, key)
        elif meth == "NOTIFY": self._on_notify(m, key)
        elif meth in ("INFO", "UPDATE", "MESSAGE"): self._on_other_in_dialog(m, key)
        else: self.server_txs[key] = self._reply(m, 405, "Method Not Allowed", [("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, NOTIFY, INFO, UPDATE")])
        if len(self.server_txs) > 200:
            for k in list(self.server_txs)[:100]: self.server_txs.pop(k, None)

    # ---- calls ------------------------------------------------------------------------------------------------------------
    def _target_uri(self, target: str) -> str:
        t = target.strip()
        if t.lower().startswith(("sip:", "sips:")): return t
        if "@" in t: return "sip:" + t
        return f"sip:{quote(t, safe='*+()-_.!~')}@{self.cfg.domain}"

    def call(self, target: str) -> "Call | None":
        """Places a call to a number or name. Returns the Call at once; its state changes arrive as events."""
        c = Call(self, "out", self._target_uri(target)); c.remote_user = S.uri_parts(c.remote_uri)["user"] or target.strip()
        def go():
            if self.reg_state != "registered": c.state = "ended"; c.end_reason = "Not signed in to the server"; self.emit("call", call=c, state="ended"); return
            self._start_invite(c)
        self.post(go); return c

    def _new_rtp(self, call=None) -> RtpSession:
        r = RtpSession(port_range=self.cfg.bind_rtp, on_dtmf=(lambda d: self.emit("dtmf", call=call, digit=d)) if call is not None else None); r.start(); return r

    def _media_ip(self) -> str:
        return self.pub_ip or (self.tr.local[0] if self.tr else "0.0.0.0")

    def _start_invite(self, c: Call):
        c.call_id = S.new_call_id(); c.local_uri = f"sip:{self.cfg.user}@{self.cfg.domain}"; c.media = self._new_rtp(c)
        c.local_sdp = SDP.build(self._media_ip(), c.media.port)
        self.calls[c.call_id] = c; c.state = "calling"; self.emit("call", call=c, state="calling")
        self._send_invite(c)

    def _send_invite(self, c: Call, auth: tuple | None = None):
        c.cseq += 0 if auth is None else 1
        m = self._base("INVITE", c.remote_uri, c.call_id, c.cseq, self._from(c.local_tag), f"<{c.remote_uri}>")
        m.add("Contact", f"<{self.contact_uri()}>"); m.add("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, NOTIFY, INFO, UPDATE"); m.add("Content-Type", "application/sdp"); m.body = c.local_sdp
        if auth: self._authorize(m, auth[0], c.remote_uri, proxy=auth[1])
        c.invite = m; c.invite_tx = self._send_request(m, lambda r, c=c: self._on_invite_response(c, r), lambda c=c: self._end(c, "No answer from the server", send_bye=False))

    def _on_invite_response(self, c: Call, r: S.Message):
        if c.state == "ended": return
        if r.status in (401, 407) and c.auth_tries < 1:
            ch, proxy = self._challenge(r)
            if ch: c.auth_tries += 1; ch.pop("_nc", None); self._send_invite(c, (ch, proxy)); return
        if r.status < 200:
            c.remote_tag = r.tag("to") or c.remote_tag
            if r.status in (180, 183) or r.status == 181: self._set_call(c, "ringing")
            if r.body and r.get("content-type").lower().startswith("application/sdp"): self._early_media(c, r)
            if c.cancel_requested: self._send_cancel(c)
            return
        if r.status < 300:
            c.remote_tag = r.tag("to"); c.final_resp = r
            self._dialog_from_response(c, r)
            if r.body: self._early_media(c, r)
            self._send_ack(c)
            if c.cancel_requested: self._hangup(c); return
            if c.media and not c.remote_sdp: self._end(c, "The server's answer had no audio description", send_bye=True); return
            c.answered_at = time.time(); self._set_call(c, "active"); return
        if c.cancel_requested and r.status == 487: self._end(c, "Cancelled", send_bye=False); return
        self._end(c, fail_text(r.status, r.reason), send_bye=False)

    def _early_media(self, c: Call, r: S.Message):
        rem = SDP.parse(r.body)
        if not rem.ip or not rem.port: return
        pt = SDP.choose(rem)
        if pt < 0:
            if r.status >= 200: self._end(c, "No common audio format with the other side", send_bye=True)
            return
        c.remote_sdp = rem
        if c.media: c.media.set_remote(rem.ip, rem.port, pt, rem.event_pt); self._punch(c)

    def _punch(self, c: Call):
        """Sends a few frames of silence at once: this opens the NAT router for the answer before the other side speaks."""
        import numpy as np
        for _ in range(3):
            if c.media: c.media.send_frame(np.zeros(160, np.int16))

    def _dialog_from_response(self, c: Call, r: S.Message):
        c.remote_target = S.uri_of(r.get("contact")) or c.remote_uri
        rr = r.all("record-route"); c.route_set = list(reversed(rr))

    def _send_ack(self, c: Call):
        a = self._base("ACK", c.remote_target or c.remote_uri, c.call_id, c.invite.cseq[0] if c.invite else c.cseq, self._from(c.local_tag), c.final_resp.get("to") if c.final_resp else f"<{c.remote_uri}>;tag={c.remote_tag}")
        for rt in c.route_set: a.add("Route", rt)
        self.tr.send(a.to_bytes()); self._dump("out", a)

    def _send_cancel(self, c: Call):
        if not c.invite or getattr(c, "cancel_sent", False): return
        c.cancel_sent = True; req = c.invite
        m = S.Message(method="CANCEL", uri=req.uri); m.add("Via", req.all("via")[0]); m.add("Max-Forwards", "70"); m.add("From", req.get("from")); m.add("To", req.get("to")); m.add("Call-ID", req.call_id)
        m.add("CSeq", f"{req.cseq[0]} CANCEL"); m.add("User-Agent", USER_AGENT)
        for rt in req.all("route"): m.add("Route", rt)
        self.txs[m.branch] = tx = ClientTx(m, lambda r: None, lambda: None); self.tr.send(m.to_bytes()); self._dump("out", m)
        self.call_later(10, lambda: (c.state not in ("ended",)) and self._end(c, "Cancelled", send_bye=False))

    def _set_call(self, c: Call, state: str):
        if c.state == state or c.state == "ended": return
        c.state = state; self.emit("call", call=c, state=state)

    def _end(self, c: Call, reason: str, send_bye: bool = False):
        if c.state == "ended": return
        c.end_reason = reason; c.state = "ended"
        self.cancel(c.ring_timer); self.cancel(c.resp_timer)
        if c.media: c.media.stop()
        self.calls.pop(c.call_id, None)
        self.emit("call", call=c, state="ended")

    def _hangup(self, c: Call):
        if c.state == "ended": return
        if c.direction == "out" and c.state in ("calling", "ringing"):
            c.cancel_requested = True
            if c.state == "ringing" or (c.invite_tx and c.invite_tx.provisional): self._send_cancel(c)
            else: self.call_later(0.5, lambda: c.state not in ("ended",) and c.cancel_requested and (c.invite_tx and c.invite_tx.provisional) and self._send_cancel(c))
            self.call_later(5, lambda: c.state in ("calling", "ringing") and self._end(c, "Cancelled")); return
        if c.direction == "in" and c.state == "incoming": self._reject(c, 603); return
        self._bye(c)
        self._end(c, "Hung up")

    def _bye(self, c: Call):
        c.cseq += 1
        to = f"<{c.remote_uri}>;tag={c.remote_tag}" if c.direction == "out" else None
        if c.direction == "out": m = self._base("BYE", c.remote_target or c.remote_uri, c.call_id, c.cseq, self._from(c.local_tag), to)
        else:
            m = self._base("BYE", c.remote_target or c.remote_uri, c.call_id, c.cseq, f"<{c.local_uri}>;tag={c.local_tag}", f"{c.invite.get('from')}")
        for rt in c.route_set: m.add("Route", rt)
        self._send_request(m, lambda r: None, lambda: None)

    # --- incoming call
    def _on_invite(self, m: S.Message, key):
        cid = m.call_id; c = self.calls.get(cid)
        if c and c.state != "ended" and m.tag("to"):                                    # a re-INVITE inside a call (hold, a new address)
            self._on_reinvite(c, m, key); return
        if self.stopping or self.reg_state != "registered" and False:
            self.server_txs[key] = self._reply(m, 480, "Temporarily Unavailable"); return
        if len([x for x in self.calls.values() if x.state != "ended"]) >= 1:                # one call at a time: the next caller hears busy
            self.server_txs[key] = self._reply(m, 486, "Busy Here", to_tag=S.new_tag()); return
        c = Call(self, "in", S.uri_of(m.get("from"))); c.call_id = cid; c.invite = m; c.remote_tag = m.tag("from"); c.local_uri = S.uri_of(m.get("to")); c.remote_target = S.uri_of(m.get("contact")) or c.remote_uri
        c.route_set = m.all("record-route"); c.remote_cseq = m.cseq[0]
        c.remote_user = S.uri_parts(c.remote_uri)["user"] or c.remote_uri; c.remote_name = S.display_name(m.get("from"))
        c.remote_user = S.uri_parts(S.uri_of(m.get("p-asserted-identity") or ""))["user"] or c.remote_user if m.get("p-asserted-identity") else c.remote_user
        if m.body:
            rem = SDP.parse(m.body); c.remote_sdp = rem
            if SDP.choose(rem) < 0:
                self.server_txs[key] = self._reply(m, 488, "Not Acceptable Here", to_tag=c.local_tag); return
        self.calls[cid] = c; c.state = "incoming"
        self._invite_key = key
        c._key = key
        self._reply(m, 100, "Trying")
        c.last_resp = self._reply(m, 180, "Ringing", [("Contact", f"<{self.contact_uri()}>")], to_tag=c.local_tag); self.server_txs[key] = c.last_resp
        self.emit("call", call=c, state="incoming")
        c.ring_timer = self.call_later(60, lambda: c.state == "incoming" and self._reject(c, 480))

    def _answer(self, c: Call):
        if c.state != "incoming": return
        c.media = self._new_rtp(c); rem = c.remote_sdp
        pt = SDP.choose(rem) if rem else 0
        ip = self._media_ip()
        c.local_sdp = SDP.build(ip, c.media.port, only=[pt] if pt >= 0 else None)
        if rem: c.media.set_remote(rem.ip, rem.port, pt, rem.event_pt); self._punch(c)
        r = self._reply(c.invite, 200, "OK", [("Contact", f"<{self.contact_uri()}>"), ("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, NOTIFY, INFO, UPDATE")], body=c.local_sdp, to_tag=c.local_tag)
        self.server_txs[c._key] = r; c.final_resp = r; c.answered_at = time.time(); c.acked = False; self.cancel(c.ring_timer)
        self._set_call(c, "connecting")
        self._retransmit_200(c, r, T1, time.time())

    def _retransmit_200(self, c: Call, r: S.Message, iv: float, t0: float):
        def go():
            if c.acked or c.state not in ("connecting",): return
            if time.time() - t0 > TIMER_B: self._bye(c); self._end(c, "No acknowledgement from the other side"); return
            self.tr.send(r.to_bytes()); self._retransmit_200(c, r, min(iv * 2, T2), t0)
        c.resp_timer = self.call_later(iv, go)

    def _on_ack(self, m: S.Message):
        c = self.calls.get(m.call_id)
        if not c or c.acked: return
        c.acked = True; self.cancel(c.resp_timer)
        if m.body and not c.remote_sdp:                                                  # the offer was in our 200 and the answer comes in the ACK
            rem = SDP.parse(m.body); c.remote_sdp = rem
            if c.media: c.media.set_remote(rem.ip, rem.port, max(0, SDP.choose(rem)), rem.event_pt); self._punch(c)
        if c.state == "connecting": c.answered_at = time.time(); self._set_call(c, "active")

    def _reject(self, c: Call, code: int):
        if c.state != "incoming": return
        text = {603: "Decline", 486: "Busy Here", 480: "Temporarily Unavailable"}.get(code, "Decline")
        r = self._reply(c.invite, code, text, to_tag=c.local_tag); self.server_txs[c._key] = r; c.final_resp = r
        self._end(c, "Declined" if code == 603 else "Missed")

    def _on_cancel(self, m: S.Message, key):
        c = self.calls.get(m.call_id)
        if not c or c.state != "incoming": self.server_txs[key] = self._reply(m, 481, "Call/Transaction Does Not Exist"); return
        self.server_txs[key] = self._reply(m, 200, "OK")
        r = self._reply(c.invite, 487, "Request Terminated", to_tag=c.local_tag); self.server_txs[c._key] = r
        self._end(c, "Missed call")

    def _on_bye(self, m: S.Message, key):
        c = self.calls.get(m.call_id)
        if not c: self.server_txs[key] = self._reply(m, 481, "Call/Transaction Does Not Exist"); return
        self.server_txs[key] = self._reply(m, 200, "OK"); self._end(c, "The other side hung up")

    def _on_reinvite(self, c: Call, m: S.Message, key):
        if m.body:
            rem = SDP.parse(m.body)
            held = rem.on_hold; c.held_by_remote = held
            if rem.ip and rem.port and not held and c.media:
                pt = SDP.choose(rem); 
                if pt >= 0: c.media.set_remote(rem.ip, rem.port, pt, rem.event_pt); c.remote_sdp = rem
            direction = "recvonly" if held else "sendrecv"
            ans = SDP.build(self._media_ip(), c.media.port if c.media else 0, only=[c.media.pt] if c.media else None, direction=direction)
            self.server_txs[key] = self._reply(m, 200, "OK", [("Contact", f"<{self.contact_uri()}>")], body=ans)
        else: self.server_txs[key] = self._reply(m, 200, "OK", [("Contact", f"<{self.contact_uri()}>")], body=c.local_sdp)
        self.emit("call", call=c, state="held" if c.held_by_remote else "active")

    def _on_other_in_dialog(self, m: S.Message, key):
        c = self.calls.get(m.call_id)
        if m.method == "INFO" and c and "dtmf" in m.get("content-type").lower():
            mm = re.search(r"Signal\s*=\s*([0-9A-D*#])", m.body.decode("utf-8", "replace"))
            if mm: self.emit("dtmf", call=c, digit=mm.group(1))
        self.server_txs[key] = self._reply(m, 200, "OK")

    # ---- who is busy (SUBSCRIBE / NOTIFY) -------------------------------------------------------------------------------------
    def watch(self, extensions: list[str], events=("dialog",)):
        """Asks the server about each number (Event: dialog = on a call / ringing / free, RFC 4235; Event: presence = online / offline, RFC 3856)."""
        def go():
            self.watch_list = [(e, ev) for e in extensions for ev in events]
            for s in list(self.subs.values()):
                if (s.ext, s.event) not in self.watch_list: self._unsubscribe(s)
            if self.reg_state == "registered": self._start_watch()
        self.post(go)

    def _start_watch(self):
        delay = 0.0
        for ext, ev in self.watch_list:
            k = f"{ev}:{ext}"
            if k in self.subs: continue
            sub = Subscription(ext, ev); self.subs[k] = sub; self.sub_by_callid[sub.call_id] = sub
            self.call_later(delay, lambda s=sub: self._subscribe(s)); delay += 0.1

    def _subscribe(self, s: Subscription, expires: int = 300):
        if self.stopping and expires: return
        if not self.tr or self.tr.closed or self.reg_state != "registered" and expires: return
        s.cseq += 1; uri = f"sip:{quote(s.ext, safe='*+')}@{self.cfg.domain}"
        to = f"<{uri}>" + (f";tag={s.remote_tag}" if s.remote_tag else "")
        m = self._base("SUBSCRIBE", s.target or uri, s.call_id, s.cseq, self._from(s.local_tag), to)
        m.add("Contact", f"<{self.contact_uri()}>"); m.add("Event", s.event); m.add("Expires", str(expires))
        m.add("Accept", "application/dialog-info+xml" if s.event == "dialog" else "application/pidf+xml")
        for rt in s.route_set: m.add("Route", rt)
        a = self.auth_cache.get(f"SUB:{s.ext}")
        if a: self._authorize(m, a[0], m.uri, proxy=a[1])
        s.tx = self._send_request(m, lambda r, s=s, e=expires: self._on_sub_response(s, r, e), lambda s=s: self._sub_failed(s, "No answer from the server"))

    def _on_sub_response(self, s: Subscription, r: S.Message, expires: int):
        if r.status < 200: return
        if r.status in (401, 407) and s.auth_tries < 1:
            ch, proxy = self._challenge(r)
            if ch: s.auth_tries += 1; ch.pop("_nc", None); self.auth_cache[f"SUB:{s.ext}"] = (ch, proxy); s.cseq -= 0; self._subscribe(s, expires); return
        if 200 <= r.status < 300:
            if expires == 0: s.active = False; return
            s.auth_tries = 0; s.fails = 0; s.active = True
            s.remote_tag = r.tag("to") or s.remote_tag
            ct = S.uri_of(r.get("contact")); s.target = ct or s.target
            if r.all("record-route"): s.route_set = list(reversed(r.all("record-route")))
            m = re.match(r"\s*(\d+)", r.get("expires")); s.expires = int(m.group(1)) if m else expires
            self.cancel(s.timer); s.timer = self.call_later(max(20, s.expires * 0.7), lambda: self._subscribe(s))
            return
        self._sub_failed(s, fail_text(r.status, r.reason), r.status)

    def _sub_failed(self, s: Subscription, why: str, code: int = 0):
        s.active = False; s.fails += 1
        self._set_presence(s, "unknown", why)
        self.cancel(s.timer)
        if code in (400, 403, 404, 405, 480, 489, 501, 603) and s.fails >= 2: return           # the server will not tell: asking again and again would only fill its log
        s.remote_tag = ""; s.target = ""; s.route_set = []
        s.timer = self.call_later(min(600, 30 * 2 ** min(s.fails, 4)), lambda: self._subscribe(s))

    def _unsubscribe(self, s: Subscription):
        self.cancel(s.timer)
        if s.active and self.tr and not self.tr.closed: self._subscribe(s, 0)
        self.subs.pop(f"{s.event}:{s.ext}", None); self.sub_by_callid.pop(s.call_id, None)

    def _on_notify(self, m: S.Message, key):
        s = self.sub_by_callid.get(m.call_id)
        if not s: self.server_txs[key] = self._reply(m, 481, "Subscription does not exist"); return
        self.server_txs[key] = self._reply(m, 200, "OK")
        ss = m.get("subscription-state").lower()
        if not s.remote_tag: s.remote_tag = m.tag("from")
        if ss.startswith("terminated"):
            s.active = False
            self._set_presence(s, "unknown", "The server ended the subscription")
            if "noresource" not in ss and "rejected" not in ss: s.timer = self.call_later(5, lambda: self._subscribe(s))
            return
        st, text = parse_presence(m.body.decode("utf-8", "replace"), s.event, m.get("content-type"))
        self._set_presence(s, st, text)

    def _set_presence(self, s: Subscription, state: str, text: str = ""):
        k = (s.event, s.ext); cur = self.presence.get(k)
        if cur == (state, text): return
        self.presence[k] = (state, text); self.emit("presence", ext=s.ext, event=s.event, state=state, text=text)


def parse_presence(body: str, event: str, ctype: str = "") -> tuple[str, str]:
    """From a NOTIFY body: ('free' | 'ringing' | 'busy' | 'online' | 'offline' | 'unknown', the server's words).
    dialog-info (RFC 4235): no dialog or only terminated ones = free; early / trying / proceeding = ringing; confirmed = busy.
    pidf (RFC 3863): <basic>open</basic> = online, closed = offline."""
    b = body or ""
    if "dialog-info" in b or event == "dialog":
        states = re.findall(r"<state[^>]*>\s*([a-zA-Z]+)\s*</state>", b)
        dirs = re.findall(r"<direction>\s*(\w+)\s*</direction>", b)
        live = [s.lower() for s in states if s.lower() != "terminated"]
        if not b.strip(): return "unknown", "empty notification"
        if not live: return "free", "no call"
        if "confirmed" in live: return "busy", "on a call"
        if any(s in ("early", "trying", "proceeding") for s in live): return "ringing", "ringing"
        return "unknown", ", ".join(live)
    if "<basic" in b or "pidf" in (ctype or ""):
        m = re.search(r"<(?:\w+:)?basic>\s*(open|closed)\s*</", b, re.I)
        note = re.search(r"<(?:\w+:)?note>\s*([^<]*)</", b)
        if m: return ("online" if m.group(1).lower() == "open" else "offline"), (note.group(1).strip() if note else "")
        return "unknown", "no status in the notification"
    return "unknown", "unreadable notification"
