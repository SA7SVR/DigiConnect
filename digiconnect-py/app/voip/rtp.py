"""RTP (RFC 3550) for G.711 audio: packets, jitter buffer, and the keypad tones of RFC 4733 (telephone-event)."""
import queue, random, socket, struct, threading, time
import numpy as np
from . import g711

FRAME = 160                 # samples in 20 ms at 8000 Hz
DTMF_CODES = {**{str(i): i for i in range(10)}, "*": 10, "#": 11, "A": 12, "B": 13, "C": 14, "D": 15}
DTMF_CHARS = {v: k for k, v in DTMF_CODES.items()}


def build_packet(pt: int, seq: int, ts: int, ssrc: int, payload: bytes, marker: bool = False) -> bytes:
    return struct.pack("!BBHII", 0x80, (0x80 if marker else 0) | (pt & 0x7F), seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc) + payload


def parse_packet(data: bytes):
    """(payload type, marker, sequence, timestamp, ssrc, payload) or None when it is not an RTP packet of version 2."""
    if len(data) < 12 or data[0] >> 6 != 2: return None
    cc = data[0] & 0x0F; has_ext = bool(data[0] & 0x10); pad = bool(data[0] & 0x20)
    pt, marker = data[1] & 0x7F, bool(data[1] & 0x80)
    seq, ts, ssrc = struct.unpack("!HII", data[2:12])
    off = 12 + 4 * cc
    if has_ext:
        if len(data) < off + 4: return None
        off += 4 + 4 * struct.unpack("!H", data[off + 2:off + 4])[0]
    end = len(data) - (data[-1] if pad and data else 0)
    if off > end: return None
    return pt, marker, seq, ts, ssrc, data[off:end]


def dtmf_payload(code: int, end: bool, duration: int, volume: int = 10) -> bytes:
    return struct.pack("!BBH", code, (0x80 if end else 0) | (volume & 0x3F), duration & 0xFFFF)


def parse_dtmf(payload: bytes):
    if len(payload) < 4: return None
    code, vb, dur = struct.unpack("!BBH", payload[:4]); return code, bool(vb & 0x80), dur


class JitterBuffer:
    """Takes the packets as they come (late, twice, in the wrong order) and gives one 20 ms frame at the pace of the sound card.
    It waits for `prefill` frames before it starts, repeats a faded copy of the last frame for a lost one, and plays silence on an underrun."""

    def __init__(self, prefill: int = 3, maxlen: int = 25):
        self.prefill, self.maxlen = prefill, maxlen; self.buf: dict[int, np.ndarray] = {}; self.next = None; self.started = False; self.last = np.zeros(FRAME, np.int16)
        self.lost = self.late = self.underruns = self.received = 0; self._empty = 0; self.lock = threading.Lock()

    @staticmethod
    def _ahead(a: int, b: int) -> int: return (a - b) & 0xFFFF            # how far a is ahead of b (0..65535)

    def push(self, seq: int, pcm: np.ndarray):
        with self.lock:
            self.received += 1
            if self.next is not None and self.started and self._ahead(seq, self.next) >= 0x8000: self.late += 1; return      # older than what was already played
            if seq in self.buf: return
            self.buf[seq] = pcm
            if self.next is None: self.next = seq
            elif not self.started and seq != self.next and self._ahead(self.next, seq) < 0x8000: self.next = seq          # an earlier packet arrived late, before playing began: start from it
            while len(self.buf) > self.maxlen and self.next is not None:           # far too much waiting: skip ahead (the speaker is behind)
                self.next = (self.next + 1) & 0xFFFF; self.buf.pop(self.next - 1 if self.next else 0xFFFF, None)

    def pull(self) -> np.ndarray:
        with self.lock:
            if not self.started:
                if len(self.buf) >= self.prefill and self.next is not None:
                    self.started = True
                else: return np.zeros(FRAME, np.int16)
            f = self.buf.pop(self.next, None)
            if f is not None:
                self.next = (self.next + 1) & 0xFFFF; self.last = f; self._empty = 0; return f
            if self.buf:                                                            # a later packet is here: this one is lost
                self.lost += 1; self.next = (self.next + 1) & 0xFFFF; self.last = (self.last * 0.5).astype(np.int16); return self.last
            self.underruns += 1; self._empty += 1
            if self._empty > 10: self.started = False; self.next = None            # the stream stopped: wait for a fresh start
            return np.zeros(FRAME, np.int16)

    def level(self) -> int:
        with self.lock: return len(self.buf)


class RtpSession:
    """One call's audio: a UDP socket that sends and receives (the same port both ways, so a NAT router lets the answer in)."""

    def __init__(self, bind_ip: str = "0.0.0.0", port_range=(12000, 12999), on_dtmf=None):
        self.sock = None; self.pt = 0; self.event_pt = 101; self.remote = None; self.ssrc = random.getrandbits(32); self.seq = random.getrandbits(16); self.ts = random.getrandbits(32)
        self.on_dtmf = on_dtmf; self.jitter = JitterBuffer(); self.running = False; self.sent = self.recv = 0; self._first = True; self._dtmf_ts = {}; self._send_lock = threading.Lock(); self._dtmf_q = queue.Queue()
        self.last_rx = 0.0; self.peer_seen = None
        lo, hi = port_range; ports = list(range(lo - lo % 2, hi, 2)); random.shuffle(ports)
        for p in ports:                                                            # an even port, as RTP asks
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try: s.bind((bind_ip, p)); self.sock = s; self.port = p; break
            except OSError: s.close()
        if self.sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind((bind_ip, 0)); self.sock = s; self.port = s.getsockname()[1]
        self.sock.settimeout(0.2)
        try: self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 18)
        except OSError: pass

    def start(self):
        self.running = True; threading.Thread(target=self._loop, daemon=True, name="rtp-rx").start(); threading.Thread(target=self._dtmf_worker, daemon=True, name="rtp-dtmf").start()

    def set_remote(self, ip: str, port: int, pt: int, event_pt: int = 101):
        self.remote = (ip, port) if ip and port else None; self.pt = pt; self.event_pt = event_pt or 101

    def stop(self):
        self.running = False
        try: self.sock.close()
        except OSError: pass

    def _loop(self):
        while self.running:
            try: data, addr = self.sock.recvfrom(2048)
            except socket.timeout: continue
            except OSError: return
            p = parse_packet(data)
            if not p: continue
            pt, marker, seq, ts, ssrc, payload = p
            self.last_rx = time.time(); self.recv += 1
            if self.remote is None or (self.peer_seen is None):                     # symmetric RTP: answer to where the audio really comes from (NAT)
                self.peer_seen = addr
            if self.peer_seen != addr and self.recv < 5: self.peer_seen = addr
            if pt in (0, 8): self.jitter.push(seq, g711.decode(payload, pt))
            elif pt == self.event_pt:
                d = parse_dtmf(payload)
                if d and self.on_dtmf:
                    code, end, _ = d
                    if end and self._dtmf_ts.get(ssrc) != ts and code in DTMF_CHARS: self._dtmf_ts[ssrc] = ts; self.on_dtmf(DTMF_CHARS[code])

    def _target(self):
        return self.peer_seen if (self.peer_seen and self.recv) else self.remote

    def send_frame(self, pcm: np.ndarray):
        """One 20 ms frame (160 samples int16) to the other side."""
        t = self._target()
        if not (self.running and t): return
        with self._send_lock:
            pkt = build_packet(self.pt, self.seq, self.ts, self.ssrc, g711.encode(pcm, self.pt), marker=self._first)
            self._first = False; self.seq = (self.seq + 1) & 0xFFFF; self.ts = (self.ts + FRAME) & 0xFFFFFFFF
            try: self.sock.sendto(pkt, t); self.sent += 1
            except OSError: pass

    def send_dtmf(self, digit: str, ms: int = 160):
        """The keypad tone of one key as telephone-event packets (RFC 4733): start, updates every 20 ms, and the end packet three times.
        Keys pressed quickly are sent one after the other (each with its own timestamp and a pause between them), never mixed together."""
        code = DTMF_CODES.get(digit.upper())
        if code is None or not (self.running and self._target()): return False
        self._dtmf_q.put((code, ms)); return True

    def _dtmf_worker(self):
        while self.running:
            try: code, ms = self._dtmf_q.get(timeout=0.2)
            except queue.Empty: continue
            t = self._target()
            if t: self._send_digit(code, ms, t)
            time.sleep(0.06)                                                                   # RFC 4733: a gap between two events

    def _send_digit(self, code: int, ms: int, t):
        with self._send_lock: ts0 = self.ts; mk = True
        n = max(1, ms // 20)
        for i in range(n):
            with self._send_lock:
                pkt = build_packet(self.event_pt, self.seq, ts0, self.ssrc, dtmf_payload(code, False, FRAME * (i + 1)), marker=mk); mk = False
                self.seq = (self.seq + 1) & 0xFFFF; self.ts = (self.ts + FRAME) & 0xFFFFFFFF
            try: self.sock.sendto(pkt, t)
            except OSError: return
            time.sleep(0.02)
        for _ in range(3):
            with self._send_lock:
                pkt = build_packet(self.event_pt, self.seq, ts0, self.ssrc, dtmf_payload(code, True, FRAME * n)); self.seq = (self.seq + 1) & 0xFFFF
            try: self.sock.sendto(pkt, t)
            except OSError: return
        with self._send_lock: self.ts = (self.ts + FRAME) & 0xFFFFFFFF
