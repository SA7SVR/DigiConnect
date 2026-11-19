"""SIP messages: parsing, building and digest authentication (RFC 3261, RFC 7616)."""
import hashlib, os, re, secrets

CRLF = "\r\n"
COMPACT = {"v": "via", "f": "from", "t": "to", "i": "call-id", "m": "contact", "c": "content-type", "l": "content-length", "k": "supported", "s": "subject", "e": "content-encoding"}
NICE = {"call-id": "Call-ID", "cseq": "CSeq", "www-authenticate": "WWW-Authenticate", "user-agent": "User-Agent", "www": "WWW"}
BRANCH_MAGIC = "z9hG4bK"


def nice(name: str) -> str:
    n = name.lower()
    return NICE.get(n) or "-".join(p.capitalize() for p in n.split("-"))


class Message:
    """A SIP request (method, uri) or response (status, reason). Headers keep their order; the names are compared without case."""

    def __init__(self, method: str = "", uri: str = "", status: int = 0, reason: str = "", headers=None, body: bytes = b""):
        self.method, self.uri, self.status, self.reason = method, uri, status, reason
        self.headers: list[tuple[str, str]] = list(headers or [])
        self.body = body or b""

    @property
    def is_request(self) -> bool: return bool(self.method)

    # ---- headers
    def get(self, name: str, default: str = "") -> str:
        n = name.lower()
        for k, v in self.headers:
            if k.lower() == n: return v
        return default

    def all(self, name: str) -> list[str]:
        n = name.lower(); out = []
        for k, v in self.headers:
            if k.lower() == n: out += split_list(v) if n in ("via", "route", "record-route", "contact", "supported", "allow", "require") else [v]
        return out

    def add(self, name: str, value: str): self.headers.append((name, value)); return self

    def set(self, name: str, value: str):
        n = name.lower()
        for i, (k, _) in enumerate(self.headers):
            if k.lower() == n:
                self.headers[i] = (k, value)
                self.headers[:] = [h for j, h in enumerate(self.headers) if j <= i or h[0].lower() != n]
                return self
        return self.add(name, value)

    def remove(self, name: str):
        n = name.lower(); self.headers[:] = [h for h in self.headers if h[0].lower() != n]

    # ---- derived
    @property
    def call_id(self) -> str: return self.get("call-id")

    @property
    def cseq(self) -> tuple[int, str]:
        m = re.match(r"\s*(\d+)\s+(\S+)", self.get("cseq"))
        return (int(m.group(1)), m.group(2).upper()) if m else (0, "")

    @property
    def branch(self) -> str:
        v = self.all("via")
        m = re.search(r";\s*branch=([^;\s,]+)", v[0]) if v else None
        return m.group(1) if m else ""

    def tag(self, name: str) -> str:
        m = re.search(r";\s*tag=([^;\s>,]+)", self.get(name)); return m.group(1) if m else ""

    # ---- wire
    def to_bytes(self) -> bytes:
        first = f"{self.method} {self.uri} SIP/2.0" if self.is_request else f"SIP/2.0 {self.status} {self.reason}"
        hs = [(k, v) for k, v in self.headers if k.lower() != "content-length"]
        hs.append(("Content-Length", str(len(self.body))))
        return (first + CRLF + CRLF.join(f"{k}: {v}" for k, v in hs) + CRLF + CRLF).encode("utf-8") + self.body

    def __repr__(self): return f"<{self.method} {self.uri}>" if self.is_request else f"<{self.status} {self.reason}>"


def split_list(v: str) -> list[str]:
    """Splits a header value at commas that are not inside <...> or quotes (Via and Contact may hold several entries)."""
    out, cur, depth, q = [], "", 0, False
    for ch in v:
        if ch == '"': q = not q
        elif not q and ch == "<": depth += 1
        elif not q and ch == ">": depth = max(0, depth - 1)
        if ch == "," and not q and depth == 0:
            if cur.strip(): out.append(cur.strip())
            cur = ""
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


def parse(data: bytes):
    """One message from bytes (UDP datagram or a framed TCP message), or None when it is not SIP."""
    head, sep, body = data.partition(b"\r\n\r\n")
    if not sep:
        head, sep, body = data.partition(b"\n\n")
        if not sep: head, body = data, b""
    text = head.decode("utf-8", "replace").replace("\r\n", "\n")
    lines = text.split("\n")
    while lines and not lines[0].strip(): lines.pop(0)         # empty lines before the message (keep-alives)
    if not lines: return None
    m = re.match(r"^SIP/2\.0\s+(\d{3})\s*(.*)$", lines[0])
    if m: msg = Message(status=int(m.group(1)), reason=m.group(2).strip())
    else:
        r = re.match(r"^([A-Za-z]+)\s+(\S+)\s+SIP/2\.0\s*$", lines[0])
        if not r: return None
        msg = Message(method=r.group(1).upper(), uri=r.group(2))
    cur = None
    for ln in lines[1:]:
        if ln[:1] in (" ", "\t") and cur is not None:
            k, v = msg.headers[cur]; msg.headers[cur] = (k, v + " " + ln.strip()); continue
        if ":" not in ln: continue
        k, v = ln.split(":", 1); k = k.strip(); k = nice(COMPACT.get(k.lower(), k)); msg.headers.append((k, v.strip())); cur = len(msg.headers) - 1
    try: n = int(msg.get("content-length", "-1"))
    except ValueError: n = -1
    msg.body = body[:n] if 0 <= n <= len(body) else body
    return msg


def frame_length(buf: bytes) -> int:
    """For TCP: the length of the first complete message in buf, 0 when it is not complete yet, -1 when only keep-alive line breaks are in front."""
    i = 0
    while i < len(buf) and buf[i:i + 2] == b"\r\n": i += 2
    if i: return -(i)
    end = buf.find(b"\r\n\r\n")
    if end < 0: return 0
    m = re.search(rb"(?im)^(?:content-length|l)[ \t]*:[ \t]*(\d+)", buf[:end])
    n = int(m.group(1)) if m else 0
    total = end + 4 + n
    return total if len(buf) >= total else 0


# ---- addresses --------------------------------------------------------------------------------------------------
def uri_of(header_value: str) -> str:
    """The URI of a From / To / Contact value: sip:user@host from '"Name" <sip:user@host>;tag=x' or 'sip:user@host'."""
    m = re.search(r"<([^>]*)>", header_value)
    if m: return m.group(1)
    return header_value.split(";")[0].strip()


def uri_parts(uri: str) -> dict:
    m = re.match(r"^(sips?):(?:([^@;]*?)(?::[^@]*)?@)?([^:;>?]+|\[[^\]]+\])(?::(\d+))?(;[^?]*)?(\?.*)?$", uri.strip())
    if not m: return dict(scheme="sip", user="", host="", port=0, params="")
    return dict(scheme=m.group(1), user=m.group(2) or "", host=m.group(3), port=int(m.group(4) or 0), params=m.group(5) or "")


def display_name(header_value: str) -> str:
    m = re.match(r'^\s*"([^"]*)"', header_value)
    if m: return m.group(1)
    m = re.match(r"^\s*([^<\"]+?)\s*<", header_value)
    return m.group(1).strip() if m else ""


def new_branch() -> str: return BRANCH_MAGIC + secrets.token_hex(8)
def new_tag() -> str: return secrets.token_hex(5)
def new_call_id(host: str = "digiconnect") -> str: return secrets.token_hex(10) + "@" + host


# ---- digest authentication ----------------------------------------------------------------------------------------
def parse_challenge(value: str) -> dict:
    """WWW-Authenticate / Proxy-Authenticate: Digest realm="x", nonce="y", qop="auth,auth-int", algorithm=MD5 -> dict (names in lower case)."""
    v = value.strip()
    if v[:6].lower() != "digest": return {}
    out = {}
    for m in re.finditer(r'([a-zA-Z_-]+)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^,\s]+))', v[6:]):
        out[m.group(1).lower()] = m.group(2) if m.group(2) is not None else m.group(3)
    return out


def _h(alg: str):
    a = alg.upper().replace("-SESS", "")
    return hashlib.sha256 if a in ("SHA-256", "SHA256") else hashlib.md5


def supported(ch: dict) -> bool:
    a = (ch.get("algorithm") or "MD5").upper().replace("-SESS", "")
    return bool(ch) and a in ("MD5", "SHA-256", "SHA256")


def digest_response(ch: dict, user: str, password: str, method: str, uri: str, nc: int = 1, cnonce: str = "", body: bytes = b"") -> str:
    """The value of the Authorization / Proxy-Authorization header for a challenge (RFC 7616; with qop=auth, or the old RFC 2069 form without qop)."""
    alg = ch.get("algorithm") or "MD5"; H = _h(alg); hx = lambda s: H(s.encode("utf-8")).hexdigest()
    realm, nonce = ch.get("realm", ""), ch.get("nonce", "")
    qops = [q.strip() for q in (ch.get("qop") or "").split(",") if q.strip()]
    qop = "auth" if "auth" in qops else ("auth-int" if "auth-int" in qops else "")
    cnonce = cnonce or secrets.token_hex(8)
    ha1 = hx(f"{user}:{realm}:{password}")
    if alg.upper().endswith("-SESS"): ha1 = hx(f"{ha1}:{nonce}:{cnonce}")
    ha2 = hx(f"{method}:{uri}") if qop != "auth-int" else hx(f"{method}:{uri}:{H(body).hexdigest()}")
    ncs = f"{nc:08x}"
    resp = hx(f"{ha1}:{nonce}:{ncs}:{cnonce}:{qop}:{ha2}") if qop else hx(f"{ha1}:{nonce}:{ha2}")
    parts = [f'username="{user}"', f'realm="{realm}"', f'nonce="{nonce}"', f'uri="{uri}"', f'response="{resp}"']
    if ch.get("algorithm"): parts.append(f"algorithm={ch['algorithm']}")
    if qop: parts += [f"qop={qop}", f'cnonce="{cnonce}"', f"nc={ncs}"]
    if ch.get("opaque") is not None: parts.append(f'opaque="{ch["opaque"]}"')
    return "Digest " + ", ".join(parts)
