#!/usr/bin/env python3
"""Loopback test of dcengine against a fake YSF reflector (no radio, no audio hardware).

Usage: test_ysf_loopback.py /path/to/dcengine
1. engine connects -> fake reflector answers the YSFP handshake
2. PTT on/off -> engine must emit YSFD voice frames (header, voice, terminator)
3. the captured frames are replayed back -> engine must report an RX stream
4. disconnect -> engine must report 'disconnected'
"""
import json, os, queue, socket, subprocess, sys, threading, time

PORT = 42113
engine_bin = sys.argv[1]

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", PORT))
sock.settimeout(0.2)

events: "queue.Queue[dict]" = queue.Queue()
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=(None if os.environ.get("DC_ENGINE_STDERR") else subprocess.DEVNULL), env=env, text=True, bufsize=1)

def sample_later():
    """Diagnostic for CI: if the engine is still waiting after N seconds, print where each thread is (macOS 'sample')."""
    n = float(os.environ.get("DC_SAMPLE_AFTER", "0") or 0)
    if n <= 0: return
    time.sleep(n)
    if p.poll() is None and not pings[0]:
        print("--- no YSFP seen after %.0f s: process sample ---" % n, flush=True)
        try: print(subprocess.run(["sample", str(p.pid), "2"], capture_output=True, text=True, timeout=30).stdout[-6000:], flush=True)
        except Exception as ex: print("sample failed:", ex, flush=True)
pings = [0]
threading.Thread(target=sample_later, daemon=True).start()

def reader():
    for line in p.stdout:
        line = line.strip()
        if line.startswith("{"):
            events.put(json.loads(line))
threading.Thread(target=reader, daemon=True).start()

def send(cmd, **kw):
    p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); p.stdin.flush()

def wait_ev(pred, timeout=8.0):
    end = time.time() + timeout
    seen = []
    while time.time() < end:
        try:
            e = events.get(timeout=0.2)
        except queue.Empty:
            continue
        seen.append(e)
        if pred(e):
            return e, seen
    return None, seen

peer = [None]
captured: list = []
stop = threading.Event()
def reflector():
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        peer[0] = addr
        if data[:4] == b"YSFP":
            pings[0] += 1
            sock.sendto(b"YSFP" + b"TESTREFLEC", addr)   # 14 bytes -> engine marks CONNECTED
        elif data[:4] == b"YSFD":
            captured.append(data)
threading.Thread(target=reflector, daemon=True).start()

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra and not ok else ""))
    if not ok: fails.append(name)

send("hello")
e, _ = wait_ev(lambda e: e["ev"] == "hello", 5)
check("hello", e is not None)

send("connect", mode="YSF", host="127.0.0.1", port=PORT, callsign="SA7SVR", name="TESTREFLEC")
e, seen = wait_ev(lambda e: e["ev"] == "status" and e["state"] in ("connected", "error", "timeout"), 10)
check("connected", bool(e) and e["state"] == "connected", seen)

send("ptt", on=True); time.sleep(1.6); send("ptt", on=False); time.sleep(3.0)
check("TX frames emitted", len(captured) >= 3, len(captured))
check("TX frame size 155", all(len(f) == 155 for f in captured), {len(f) for f in captured})
print("   captured", len(captured), "YSFD frames")

# replay as RX
frames = list(captured)
for f in frames:
    # make them look like they come from a remote gateway
    g = b"REMOTEGW  "
    sock.sendto(b"YSFD" + g + b"DL4LGV    " + b"ALL       " + f[34:], peer[0])
    time.sleep(0.02)
e, seen = wait_ev(lambda e: e["ev"] == "rx" and e["state"] in ("new", "streaming", "end"), 8)
check("RX stream event received (not just own TX)", e is not None, seen)
if e: print("   first rx:", e)
states = [x["state"] for x in seen if x["ev"] == "rx"]
print("   rx states:", states)

send("disconnect")
e, seen = wait_ev(lambda e: e["ev"] == "status" and e["state"] == "disconnected", 6)
check("disconnected", e is not None, seen)

send("quit"); time.sleep(0.5)
stop.set()
try: p.wait(timeout=4)
except subprocess.TimeoutExpired:
    p.kill(); check("engine exits on quit", False)
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
