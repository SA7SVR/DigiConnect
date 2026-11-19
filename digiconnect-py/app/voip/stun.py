"""STUN (RFC 5389): asks a STUN server which public address and port a UDP socket has behind a NAT router. Used for the audio port, so the other side
sends the sound to an address that reaches us. The answer is read exactly as the server sends it; when there is none, nothing is assumed."""
import os, socket, struct, time

MAGIC = 0x2112A442


def parse_host(text: str, default_port: int = 3478):
    t = (text or "").strip()
    if t.lower().startswith("stun:"): t = t[5:]
    if not t: return None
    host, _, port = t.rpartition(":") if t.count(":") == 1 else (t, "", "")
    host = host or t
    try: return host, int(port) if port else default_port
    except ValueError: return None


def request(tid: bytes | None = None) -> tuple[bytes, bytes]:
    tid = tid or os.urandom(12)
    return struct.pack("!HHI", 0x0001, 0, MAGIC) + tid, tid


def parse_response(data: bytes, tid: bytes):
    """(ip, port) from a Binding success response with our transaction id, else None."""
    if len(data) < 20: return None
    typ, ln, magic = struct.unpack("!HHI", data[:8])
    if typ != 0x0101 or magic != MAGIC or data[8:20] != tid or len(data) < 20 + ln: return None
    i, end, mapped = 20, 20 + ln, None
    while i + 4 <= end:
        at, al = struct.unpack("!HH", data[i:i + 4]); v = data[i + 4:i + 4 + al]
        if at == 0x0020 and al >= 8 and v[1] == 1:                                   # XOR-MAPPED-ADDRESS, IPv4
            port = struct.unpack("!H", v[2:4])[0] ^ (MAGIC >> 16); ip = struct.unpack("!I", v[4:8])[0] ^ MAGIC
            return socket.inet_ntoa(struct.pack("!I", ip)), port
        if at == 0x0001 and al >= 8 and v[1] == 1: mapped = (socket.inet_ntoa(v[4:8]), struct.unpack("!H", v[2:4])[0])            # MAPPED-ADDRESS (old servers)
        i += 4 + al + (-al % 4)
    return mapped


def discover(sock: socket.socket, server, timeout: float = 1.5, tries: int = 3):
    """Binding request from this socket. Returns (ip, port) or None. The socket's timeout is restored."""
    old = sock.gettimeout(); addr = None
    try:
        addr = (socket.gethostbyname(server[0]), server[1]); msg, tid = request()
        for n in range(tries):
            sock.sendto(msg, addr)
            sock.settimeout(max(0.05, timeout / tries))
            t0 = time.time()
            while time.time() - t0 < timeout / tries:
                try: data, frm = sock.recvfrom(2048)
                except (socket.timeout, OSError): break
                r = parse_response(data, tid)
                if r: return r
        return None
    except OSError: return None
    finally:
        try: sock.settimeout(old)
        except OSError: pass
