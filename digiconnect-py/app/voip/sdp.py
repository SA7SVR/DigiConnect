"""SDP (RFC 4566 / RFC 3264): the offer we send and the answer we read. One audio stream: G.711 (PCMU, PCMA) and telephone-event for the keypad (RFC 4733)."""
import re, secrets, time

PT_PCMU, PT_PCMA, DEFAULT_PT_EVENT = 0, 8, 101
CODECS = {PT_PCMU: "PCMU", PT_PCMA: "PCMA"}


def build(local_ip: str, rtp_port: int, session_name: str = "DigiConnect", sid: str = "", prefer=(PT_PCMU, PT_PCMA), event_pt: int = DEFAULT_PT_EVENT, only=None, direction: str = "sendrecv") -> bytes:
    """An offer or an answer. 'only' limits the codecs (an answer lists only the one we choose)."""
    sid = sid or str(int(time.time()))
    pts = [p for p in prefer if only is None or p in only]
    lines = ["v=0", f"o=- {sid} {sid} IN IP4 {local_ip}", f"s={session_name}", f"c=IN IP4 {local_ip}", "t=0 0",
             f"m=audio {rtp_port} RTP/AVP " + " ".join(str(p) for p in pts + [event_pt])]
    for p in pts: lines.append(f"a=rtpmap:{p} {CODECS[p]}/8000")
    lines += [f"a=rtpmap:{event_pt} telephone-event/8000", f"a=fmtp:{event_pt} 0-16", "a=ptime:20", f"a={direction}"]
    return ("\r\n".join(lines) + "\r\n").encode()


class Remote:
    """What the other side's SDP says: where to send the audio, which codecs it accepts, the telephone-event type and whether it is on hold."""

    def __init__(self): self.ip, self.port, self.codecs, self.event_pt, self.direction, self.ptime = "", 0, [], 0, "sendrecv", 20

    @property
    def on_hold(self) -> bool: return self.direction in ("sendonly", "inactive") or self.ip == "0.0.0.0" or self.port == 0


def parse(body: bytes) -> Remote:
    r = Remote(); text = body.decode("utf-8", "replace").replace("\r\n", "\n"); session_ip = ""; in_audio = False; rtpmap = {}; offered = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if ln.startswith("c=") and not in_audio:
            m = re.match(r"c=IN IP4 (\S+)", ln)
            if m: session_ip = m.group(1)
        elif ln.startswith("m="):
            in_audio = ln.startswith("m=audio")
            if in_audio:
                m = re.match(r"m=audio (\d+) \S+ (.*)$", ln)
                if m: r.port = int(m.group(1)); offered = [int(x) for x in m.group(2).split() if x.isdigit()]
        elif in_audio and ln.startswith("c="):
            m = re.match(r"c=IN IP4 (\S+)", ln)
            if m: r.ip = m.group(1)
        elif in_audio and ln.startswith("a=rtpmap:"):
            m = re.match(r"a=rtpmap:(\d+) ([^/\s]+)/(\d+)", ln)
            if m: rtpmap[int(m.group(1))] = (m.group(2).upper(), int(m.group(3)))
        elif in_audio and ln.startswith("a=ptime:"):
            try: r.ptime = int(ln[8:])
            except ValueError: pass
        elif in_audio and ln in ("a=sendrecv", "a=sendonly", "a=recvonly", "a=inactive"): r.direction = ln[2:]
        elif not in_audio and ln in ("a=sendonly", "a=inactive") and r.direction == "sendrecv": r.direction = ln[2:]
    r.ip = r.ip or session_ip
    for p in offered:
        name = rtpmap.get(p, ("PCMU" if p == 0 else "PCMA" if p == 8 else "", 8000))[0]
        if p in CODECS and CODECS[p] == name: r.codecs.append(p)
        if name == "TELEPHONE-EVENT": r.event_pt = p
    return r


def choose(remote: Remote, prefer=(PT_PCMU, PT_PCMA)) -> int:
    """The codec for the call: our order of preference among those the other side offers (-1 when none is common)."""
    for p in prefer:
        if p in remote.codecs: return p
    return -1
