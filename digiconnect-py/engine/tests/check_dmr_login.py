#!/usr/bin/env python3
"""Login test of dcengine against a fake DMR master that speaks the MMDVM/Homebrew login (no network, no audio hardware).

Usage: check_dmr_login.py /path/to/dcengine
Checks the whole handshake the way BrandMeister / FreeDMR / DMR+ masters do it:
  RPTL(id) -> RPTACK+salt -> RPTK(id, sha256(salt+password)) -> RPTACK -> RPTC(id, config) -> RPTACK -> connected
and that a refusal (MSTNAK) is reported with the step at which it happened:
  wrong DMR ID -> DMR_NAK_ID, wrong password -> DMR_NAK_PASSWORD
"""
import hashlib, json, os, queue, socket, subprocess, sys, threading, time

engine_bin = sys.argv[1]
SALT = bytes([0x12, 0x34, 0x56, 0x78])
fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra and not ok else ""))
    if not ok: fails.append(name)

def scenario(port, dmrid, essid, password, master_id, master_password):
    """Runs one connect against a fake master that only accepts master_id / master_password. Returns (final status event, packets seen by the master)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("127.0.0.1", port)); sock.settimeout(0.2)
    seen, stop = [], threading.Event()
    def master():
        while not stop.is_set():
            try: data, addr = sock.recvfrom(2048)
            except socket.timeout: continue
            tag = data[:4]; rid = int.from_bytes(data[4:8], "big") if len(data) >= 8 else 0
            seen.append((data[:4].decode("latin1"), len(data), rid))
            if tag == b"RPTL":
                sock.sendto((b"RPTACK" + SALT) if rid == master_id else (b"MSTNAK" + data[4:8]), addr)
            elif tag == b"RPTK":
                ok = rid == master_id and data[8:40] == hashlib.sha256(SALT + master_password.encode()).digest()
                sock.sendto((b"RPTACK" + data[4:8]) if ok else (b"MSTNAK" + data[4:8]), addr)
            elif tag == b"RPTC":
                sock.sendto(b"RPTACK" + data[4:8], addr)
            elif tag == b"RPTP":
                sock.sendto(b"MSTPONG" + data[7:11], addr)
    mt = threading.Thread(target=master, daemon=True); mt.start()
    events = queue.Queue()
    p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), text=True, bufsize=1)
    errlines = []
    threading.Thread(target=lambda: [errlines.append(l) for l in p.stderr], daemon=True).start()   # kept: shown if the engine dies on its own
    def reader():
        for line in p.stdout:
            if line.strip().startswith("{"): events.put(json.loads(line))
    threading.Thread(target=reader, daemon=True).start()
    def send(cmd, **kw):
        try: p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); p.stdin.flush()
        except (BrokenPipeError, OSError):
            time.sleep(0.5)
            print("ENGINE DIED BY ITSELF before '%s': exit code %s (negative = killed by that signal); engine stderr:\n%s" % (cmd, p.poll(), "".join(errlines[-40:])))
            raise
    send("hello"); end = time.time() + 5; last = None
    while time.time() < end and not last:
        try:
            if events.get(timeout=0.2)["ev"] == "hello": last = True
        except queue.Empty: pass
    send("connect", mode="DMR", host="127.0.0.1", port=port, callsign="SA7SVR", name="202", dmrid=dmrid, essid=essid, password=password, tg=202, cc=1, slot=2)
    end = time.time() + 10; final = None
    while time.time() < end and not final:
        try: e = events.get(timeout=0.2)
        except queue.Empty: continue
        if e["ev"] == "status" and e["state"] in ("connected", "error", "timeout"): final = e
    send("quit"); time.sleep(0.4); stop.set()
    try: p.wait(timeout=4)
    except subprocess.TimeoutExpired: p.kill()
    mt.join(2); sock.close()
    return final, seen

# 1. right ID, right password, no ESSID: hotspot id = DMR ID
final, seen = scenario(42201, 2400123, 0, "secret-hotspot-pw", 2400123, "secret-hotspot-pw")
check("login accepted with the right DMR ID and password", bool(final) and final["state"] == "connected", (final, seen))
check("handshake order RPTL, RPTK, RPTC", [s[0] for s in seen[:3]] == ["RPTL", "RPTK", "RPTC"], seen)
check("RPTC packet is 302 bytes", any(s[0] == "RPTC" and s[1] == 302 for s in seen), seen)

# 2. ESSID: the hotspot id is DMR ID * 100 + (ESSID - 1) (DroidStar convention kept by the engine)
final, seen = scenario(42202, 2400123, 3, "pw", 240012302, "pw")
check("login with an ESSID uses DMR ID*100+(ESSID-1)", bool(final) and final["state"] == "connected", (final, seen))

# 3. wrong password -> master says MSTNAK to RPTK
final, seen = scenario(42203, 2400123, 0, "wrong", 2400123, "right")
check("wrong password reported as DMR_NAK_PASSWORD", bool(final) and final["state"] == "error" and final.get("msg") == "DMR_NAK_PASSWORD", (final, seen))

# 4. unknown DMR ID -> master says MSTNAK to RPTL
final, seen = scenario(42204, 2400999, 0, "pw", 2400123, "pw")
check("unknown DMR ID reported as DMR_NAK_ID", bool(final) and final["state"] == "error" and final.get("msg") == "DMR_NAK_ID", (final, seen))

print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
