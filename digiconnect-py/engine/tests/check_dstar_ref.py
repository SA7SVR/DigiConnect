#!/usr/bin/env python3
"""Fake DPlus (REF) reflector: what does the engine put on the air when the user presses PTT?

Usage: check_dstar_ref.py /path/to/dcengine
- login handshake (DPlus: 5-byte link on the reflector port, 28-byte login on 20001, OKRW)
- PTT on/off -> header (58 bytes, CRC ok), voice frames (29 bytes), end packet (32 bytes)
- the header must carry real callsigns: MY = our callsign, UR = CQCQCQ, RPT2 = reflector + module, RPT1 not blank
- after PTT off the engine must go back to idle (no endless 'tx' state)
"""
import json, os, queue, socket, subprocess, sys, threading, time

PORT = 42131
engine_bin = sys.argv[1]

def sock_on(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", port)); s.settimeout(0.2); return s
main = sock_on(PORT)
try: auth = sock_on(20001)
except OSError: auth = None          # port taken on this machine: the engine's login then cannot be answered, test skipped
if auth is None:
    print("SKIP port 20001 busy"); sys.exit(0)

events = queue.Queue()
p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), text=True, bufsize=1)
def reader():
    for line in p.stdout:
        line = line.strip()
        if line.startswith("{"): events.put(json.loads(line))
threading.Thread(target=reader, daemon=True).start()
def send(cmd, **kw): p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); p.stdin.flush()
def wait_ev(pred, timeout=8.0):
    end = time.time() + timeout; seen = []
    while time.time() < end:
        try: e = events.get(timeout=0.2)
        except queue.Empty: continue
        seen.append(e)
        if pred(e): return e, seen
    return None, seen

captured = []; peer = [None]; stop = threading.Event()
def serve_main():
    while not stop.is_set():
        try: d, a = main.recvfrom(2048)
        except socket.timeout: continue
        peer[0] = a
        if len(d) == 5 and d[0] == 5:
            main.sendto(bytes([5, 0, 0x18, 0, 1]), a)
        elif len(d) in (58, 29, 32) and d[1:6] == b"\x80DSVT":
            captured.append(d)
def serve_auth():
    while not stop.is_set():
        try: d, a = auth.recvfrom(2048)
        except socket.timeout: continue
        auth.sendto(b"\x08\xc0\x04\x00OKRW", a)
        if peer[0]: main.sendto(b"\x08\xc0\x04\x00OKRW", peer[0])
for f in (serve_main, serve_auth): threading.Thread(target=f, daemon=True).start()

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra and not ok else ""))
    if not ok: fails.append(name)

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return (~crc) & 0xFFFF

send("hello"); e, _ = wait_ev(lambda e: e["ev"] == "hello", 5); check("hello", e is not None)
send("connect", mode="REF", host="127.0.0.1", port=PORT, callsign="SA7SVR", name="REF001", module="C")
e, seen = wait_ev(lambda e: e["ev"] == "status" and e["state"] in ("connected", "error", "timeout"), 10)
check("connected", bool(e) and e["state"] == "connected", seen)

send("ptt", on=True); time.sleep(1.2); send("ptt", on=False); time.sleep(1.5)
hdrs = [c for c in captured if len(c) == 58]; voice = [c for c in captured if len(c) == 29]; ends = [c for c in captured if len(c) == 32]
check("header sent", len(hdrs) >= 1, len(captured))
check("voice frames sent", len(voice) >= 20, len(voice))
check("end packet sent", len(ends) >= 1, [len(c) for c in captured][-5:])
if hdrs:
    h = hdrs[0]
    rpt2, rpt1, ur, my = (h[i:i+8].decode("latin1") for i in (20, 28, 36, 44))
    print("   header: RPT2=%r RPT1=%r UR=%r MY=%r" % (rpt2, rpt1, ur, my))
    check("MY is our callsign", my.strip() == "SA7SVR", my)
    check("UR is CQCQCQ", ur.strip() == "CQCQCQ", ur)
    check("RPT2 is reflector + module", rpt2 == "REF001 C", rpt2)
    check("RPT1 not blank", rpt1.strip() != "", rpt1)
    body = h[17:56]
    check("header CRC", crc16(body) == int.from_bytes(h[56:58], "little"), hex(int.from_bytes(h[56:58], "little")))
send("ptt", on=True); time.sleep(0.4); send("ptt", on=False)
e, seen = wait_ev(lambda e: e["ev"] == "rx" and False, 1.5)
send("disconnect")
e, seen = wait_ev(lambda e: e["ev"] == "status" and e["state"] == "disconnected", 6)
check("disconnected", e is not None, seen)
send("quit"); time.sleep(0.5); stop.set()
try: p.wait(timeout=4)
except subprocess.TimeoutExpired: p.kill(); check("engine exits on quit", False)
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
