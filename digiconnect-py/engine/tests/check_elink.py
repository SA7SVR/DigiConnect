#!/usr/bin/env python3
"""EchoLink voice of dcengine against a fake station (no network, no audio hardware).

Usage: check_elink.py /path/to/dcengine
The fake station listens on RTP/RTCP ports 42500/42501 on 127.0.0.1.  It checks the engine's first RTCP packet (empty receiver report + SDES
with the callsign), answers with its own SDES (= accepted), sends a text message ("who is connected") and GSM audio, and then checks that the engine
reports connected / rx new / nodetext / rx end, sends DTMF as GSM voice, and says goodbye (RTCP BYE) on disconnect."""
import json, os, queue, socket, struct, subprocess, sys, threading, time

RTP, RTCP, CALL = 42500, 42501, "SA7SVR"
engine_bin = sys.argv[1]
rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); rtp.bind(("127.0.0.1", RTP)); rtp.settimeout(0.2)
rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); rtcp.bind(("127.0.0.1", RTCP)); rtcp.settimeout(0.2)
events: "queue.Queue[dict]" = queue.Queue()
p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), text=True, bufsize=1)
threading.Thread(target=lambda: [events.put(json.loads(l)) for l in p.stdout if l.startswith("{")], daemon=True).start()
threading.Thread(target=lambda: [None for _ in p.stderr], daemon=True).start()
send = lambda cmd, **kw: (p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"), p.stdin.flush())

def wait_ev(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        try: e = events.get(timeout=0.2)
        except queue.Empty: continue
        if pred(e): return e
    return None

def recv(sock, timeout=6.0):
    end = time.time() + timeout
    while time.time() < end:
        try: return sock.recvfrom(2048)
        except socket.timeout: pass
    return None, None

def sdes(ssrc, call, name):
    items = b"".join(bytes([t, len(v)]) + v for t, v in ((1, call.encode()), (2, (call + "      " + name).encode()), (6, b"fakeEL"))) + b"\0"
    while (len(items) + 8) % 4: items += b"\0"
    return struct.pack(">BBHI", 0x80, 0xC9, 1, ssrc) + struct.pack(">BBHI", 0x81, 0xCA, (len(items) + 4) // 4, ssrc) + items

fails = []
def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what)
    if not ok: fails.append(what)

try:
    send("hello"); wait_ev(lambda e: e.get("ev") == "hello", 5)
    send("connect", mode="ELINK", host="127.0.0.1", port=RTP, callsign=CALL, name="*TEST*", el_name="Hellas", el_loc="Test", vocoder="Software vocoder")
    data, addr = recv(rtcp)
    check(data is not None, "engine sends an RTCP packet to the station")
    if data:
        check(data[0] == 0x80 and data[1] == 0xC9, "starts with an empty receiver report")
        check(b"\x81\xca" in data and CALL.encode() in data, "contains an SDES with the callsign")
        check(b"Hellas" in data, "SDES carries the operator name")
    rtcp.sendto(sdes(0x1234, "*TEST*", "Test conference"), addr)          # the station accepts: it answers with its own SDES
    e = wait_ev(lambda e: e.get("ev") == "status" and e.get("state") in ("connected", "error", "timeout"))
    check(e is not None and e.get("state") == "connected", f"engine reports connected ({e})")
    # text + audio from the station
    rtp.sendto(struct.pack(">BBHII", 0x80, 3, 1, 0, 0x1234) + b"oNDATA*TEST*\rConference users:\rSM0ABC SV1XYZ\r", ("127.0.0.1", addr[1] - 1 if addr[1] else 5198))
    for i in range(6):
        rtp.sendto(struct.pack(">BBHII", 0x80, 3, 2 + i, 640 * i, 0x1234) + bytes(132), ("127.0.0.1", addr[1] - 1 if addr[1] else 5198)); time.sleep(0.08)
    n = wait_ev(lambda e: e.get("ev") == "nodetext")
    check(n is not None and "SM0ABC" in n.get("text", ""), f"station text reaches the app ({n})")
    r = wait_ev(lambda e: e.get("ev") == "rx" and e.get("state") == "new")
    check(r is not None and r.get("src") == "*TEST*", f"rx new with the station's callsign ({r})")
    r = wait_ev(lambda e: e.get("ev") == "rx" and e.get("state") == "end", 5)
    check(r is not None, "rx end after the station stops")
    # DTMF is sent as GSM voice
    send("dtmf", keys="5")
    d, _ = recv(rtp, 4)
    check(d is not None and len(d) == 12 + 132 and (d[1] & 0x7f) == 3, f"DTMF goes out as a GSM RTP packet ({None if d is None else len(d)} bytes)")
    send("disconnect")
    d, _ = recv(rtcp, 4)
    check(d is not None and b"\x81\xcb" in d, "RTCP BYE on disconnect")
finally:
    send("quit"); time.sleep(0.3); p.kill()
sys.exit(1 if fails else 0)
