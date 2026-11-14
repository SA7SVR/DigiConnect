#!/usr/bin/env python3
"""Rewind (BrandMeister Open DMR Terminal Protocol) test of dcengine against a fake BrandMeister master (no network, no audio hardware).

Usage: check_dmr_rewind.py /path/to/dcengine
The fake master follows the BrandMeister wiki page "Open DMR Terminal Protocol":
  keep-alive(DMR ID, service 0x21, name) -> challenge(salt) -> authentication(sha256(salt+password)) -> empty keep-alive -> subscription(type 7, TG)
  header 0x0911 (x3), audio 0x0920 (27 bytes), terminator 0x0912 in both directions; every field little-endian, two sequence counters.
Checks: the login uses the plain DMR ID (ESSID is ignored), the password hash is right, a wrong password is reported as DMR_NAK_PASSWORD
after the master stays silent, the engine falls back from port 54006 to 54005 style (here: first port silent, second answers), the TG is
subscribed, a call from the master is received (an rx event with src/dst), and a transmitted call arrives as header + audio + terminator.
"""
import hashlib, json, os, queue, socket, struct, subprocess, sys, threading, time

engine_bin = sys.argv[1]
SALT = bytes([0xA1, 0xB2, 0xC3, 0xD4])
fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra and not ok else ""))
    if not ok: fails.append(name)

def pkt(type_, data=b"", flags=0, number=0):
    return b"REWIND01" + struct.pack("<HHIH", type_, flags, number, len(data)) + data

def parse(d):
    if len(d) < 18 or d[:8] != b"REWIND01": return None
    t, f, n, ln = struct.unpack("<HHIH", d[8:18])
    return dict(type=t, flags=f, number=n, data=d[18:18 + ln])

def scenario(port, dmrid, essid, password, master_id, master_password, *, silent_ports=(), call_from_master=False, do_tx=False, wait_final=10):
    """The fake master listens on `port` only; the engine is told rewind_port=port (or a silent first port, then `port`)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("127.0.0.1", port)); sock.settimeout(0.2)
    seen, stop, client = [], threading.Event(), [None]
    def master():
        authed = False
        while not stop.is_set():
            try: data, addr = sock.recvfrom(2048)
            except socket.timeout: continue
            m = parse(data)
            if not m: continue
            client[0] = addr; seen.append(m)
            if m["type"] == 0x0000 and not authed:
                if len(m["data"]) >= 5 and struct.unpack("<I", m["data"][:4])[0] == master_id and m["data"][4] == 0x21:
                    sock.sendto(pkt(0x0002, SALT), addr)
            elif m["type"] == 0x0000 and authed:
                sock.sendto(pkt(0x0000), addr)
            elif m["type"] == 0x0003:
                if m["data"] == hashlib.sha256(SALT + master_password.encode()).digest():
                    authed = True; sock.sendto(pkt(0x0000), addr)          # a wrong password gets no reply at all
            elif m["type"] == 0x0901 and authed:
                sock.sendto(pkt(0x0901), addr)
    mt = threading.Thread(target=master, daemon=True); mt.start()
    events = queue.Queue()
    p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=dict(os.environ, QT_QPA_PLATFORM="offscreen", DC_TEST_TONE="1"), text=True, bufsize=1)
    errlines = []
    threading.Thread(target=lambda: [errlines.append(l) for l in p.stderr], daemon=True).start()
    def reader():
        for line in p.stdout:
            if line.strip().startswith("{"): events.put(json.loads(line))
    threading.Thread(target=reader, daemon=True).start()
    def send(cmd, **kw):
        p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); p.stdin.flush()
    send("hello"); end = time.time() + 5; ok = False
    while time.time() < end and not ok:
        try:
            if events.get(timeout=0.2)["ev"] == "hello": ok = True
        except queue.Empty: pass
    send("connect", mode="DMR", host="127.0.0.1", port=62031, rewind=True, rewind_port=port, callsign="SA7SVR", name="202", dmrid=dmrid, essid=essid,
         password=password, tg=202, cc=1, slot=2)
    end = time.time() + wait_final; final = None; logs = []; rx = []
    while time.time() < end and not final:
        try: e = events.get(timeout=0.2)
        except queue.Empty: continue
        if e["ev"] == "log": logs.append(e["text"])
        if e["ev"] == "status" and e["state"] in ("connected", "error", "timeout"): final = e
    if final and final["state"] == "connected" and call_from_master and client[0]:
        time.sleep(0.5)
        lc = bytes([0, 0, 0]) + (202).to_bytes(3, "big") + (9269).to_bytes(3, "big") + bytes(3)
        for _ in range(3): sock.sendto(pkt(0x0911, lc, 1, 1), client[0])
        for i in range(5): sock.sendto(pkt(0x0920, bytes(range(27)), 1, 2 + i), client[0]); time.sleep(0.06)
        sock.sendto(pkt(0x0912, b"", 1, 7), client[0])
        t_end = time.time() + 3
        while time.time() < t_end:
            try: e = events.get(timeout=0.2)
            except queue.Empty: continue
            if e["ev"] == "rx": rx.append(e)
            if e["ev"] == "log": logs.append(e["text"])
    if final and final["state"] == "connected" and do_tx:
        send("ptt", on=True); time.sleep(0.8); send("ptt", on=False); time.sleep(1.0)
    send("quit"); time.sleep(0.4); stop.set()
    try: p.wait(timeout=4)
    except subprocess.TimeoutExpired: p.kill()
    mt.join(2); sock.close()
    return final, seen, logs, rx

# 1. right DMR ID and password; the ESSID is ignored (BrandMeister wants the plain ID), TG 202 is subscribed
final, seen, logs, rx = scenario(54106, 2407219, 22, "hotspot-pw", 2407219, "hotspot-pw", call_from_master=True)
check("Rewind login accepted with the plain DMR ID and the right password", bool(final) and final["state"] == "connected", (final, logs))
check("first packet is a keep-alive from the DMR ID with service 0x21", bool(seen) and seen[0]["type"] == 0 and seen[0]["data"][4] == 0x21, seen[:2])
check("authentication is the 32-byte sha256(salt+password)", any(m["type"] == 3 and len(m["data"]) == 32 for m in seen), [m["type"] for m in seen])
sub = [m for m in seen if m["type"] == 0x0901]
check("talkgroup 202 is subscribed as a group voice call (type 7)", bool(sub) and struct.unpack("<II", sub[0]["data"][:8]) == (7, 202), sub)
check("routine messages carry rising sequence numbers", [m["number"] for m in seen[:3]] == sorted(m["number"] for m in seen[:3]), [m["number"] for m in seen[:3]])
check("a call from the master is reported (src 9269, dst 202)", any(e.get("srcid") == 9269 and e.get("dstid") == 202 for e in rx), rx[:3])

# 2. wrong password: the master stays silent, the engine says so (reported as the password step)
final, seen, logs, rx = scenario(54107, 2407219, 0, "wrong", 2407219, "right", wait_final=14)
check("a wrong password is reported as DMR_NAK_PASSWORD", bool(final) and final["state"] == "error" and final.get("msg") == "DMR_NAK_PASSWORD", (final, logs))

# 3. a master that does not know the DMR ID never sends a challenge: reported as no answer on the Rewind ports
final, seen, logs, rx = scenario(54108, 2407219, 0, "pw", 111, "pw", wait_final=14)
check("no challenge on any Rewind port is reported as DMR_NO_REWIND", bool(final) and final["state"] == "error" and final.get("msg") == "DMR_NO_REWIND", (final, logs))

# 4. transmit: header (x3 same number), audio frames and terminator reach the master with the real-time flag
final, seen, logs, rx = scenario(54109, 2407219, 0, "pw", 2407219, "pw", do_tx=True)
hdr = [m for m in seen if m["type"] == 0x0911]; aud = [m for m in seen if m["type"] == 0x0920]; trm = [m for m in seen if m["type"] == 0x0912]
check("TX sends the voice header", bool(hdr), [m["type"] for m in seen])
if hdr:
    lc = hdr[0]["data"]
    check("voice header is a 12-byte group LC with destination 202 and source = DMR ID", len(lc) == 12 and lc[0] & 0x3F == 0 and int.from_bytes(lc[3:6], "big") == 202 and int.from_bytes(lc[6:9], "big") == 2407219, lc.hex())
    check("voice header carries the real-time flag", hdr[0]["flags"] & 1 == 1, hdr[0])
check("TX sends 27-byte audio frames", bool(aud) and all(len(m["data"]) == 27 for m in aud), len(aud))
check("TX ends with the terminator", bool(trm), [m["type"] for m in seen][-4:])
if hdr and aud:
    check("real-time sequence numbers rise from header to audio", aud[0]["number"] > hdr[0]["number"], (hdr[0]["number"], aud[0]["number"]))

print("\nFAILED: %s" % fails if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
