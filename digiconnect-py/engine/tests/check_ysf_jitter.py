#!/usr/bin/env python3
"""Receive-continuity test of dcengine against a fake YSF reflector (no radio, no audio hardware).

Usage: check_ysf_jitter.py /path/to/dcengine [jitter_ms]
A real C4FM repeater/reflector sends one voice packet (5 frames = 100 ms of speech) every 100 ms, but on the Internet the
packets do not arrive exactly 100 ms apart. This test records a transmission made by the engine itself, replays it as a
RECEIVED stream with random arrival jitter (and one longer stall), and reads the engine's own statistics line
("YSF playback stopped: frames played N, gaps (interruptions) G").
PASS = every voice frame was played and the audio had no interruptions."""
import json, os, queue, random, re, socket, subprocess, sys, threading, time

PORT = 42117
engine_bin = sys.argv[1]
JIT = float(sys.argv[2]) if len(sys.argv) > 2 else 70.0      # ms of random extra delay per packet
random.seed(7)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", PORT)); sock.settimeout(0.2)
events: "queue.Queue[dict]" = queue.Queue()
errlines: list = []
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True, bufsize=1)

def reader():
    for line in p.stdout:
        line = line.strip()
        if line.startswith("{"):
            e = json.loads(line)
            if e.get("ev") == "log": errlines.append(str(e.get("text", "")))      # the engine reports the statistics as an event too
            events.put(e)
def err_reader():
    for line in p.stderr:
        errlines.append(line.strip())
threading.Thread(target=reader, daemon=True).start()
threading.Thread(target=err_reader, daemon=True).start()

def send(cmd, **kw):
    p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); p.stdin.flush()

def wait_ev(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        try: e = events.get(timeout=0.2)
        except queue.Empty: continue
        if pred(e): return e
    return None

peer = [None]; captured: list = []; stop = threading.Event()
def reflector():
    while not stop.is_set():
        try: data, addr = sock.recvfrom(2048)
        except socket.timeout: continue
        peer[0] = addr
        if data[:4] == b"YSFP": sock.sendto(b"YSFP" + b"TESTREFLEC", addr)
        elif data[:4] == b"YSFD": captured.append(data)
threading.Thread(target=reflector, daemon=True).start()

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra else ""));
    if not ok: fails.append(name)

send("hello"); check("hello", wait_ev(lambda e: e["ev"] == "hello", 5) is not None)
send("connect", mode="YSF", host="127.0.0.1", port=PORT, callsign="SA7SVR", name="TESTREFLEC")
e = wait_ev(lambda e: e["ev"] == "status" and e["state"] in ("connected", "error", "timeout"), 10)
check("connected", bool(e) and e["state"] == "connected")
send("ptt", on=True); time.sleep(4.2); send("ptt", on=False); time.sleep(2.5)
frames = list(captured)
check("recorded a transmission", len(frames) >= 20, len(frames))
n_voice_frames = 0

# replay as a RECEIVED stream: nominal 100 ms spacing + random jitter + one long stall, packets stay in order
t0 = time.time(); due_prev = 0.0
for i, f in enumerate(frames):
    nominal = i * 0.100
    delay = random.uniform(0, JIT) / 1000.0
    if i == len(frames) // 2: delay += 0.150                       # one stall of 150 ms
    due = max(nominal + delay, due_prev)                           # UDP order is kept
    due_prev = due
    while time.time() - t0 < due: time.sleep(0.001)
    sock.sendto(b"YSFD" + b"REMOTEGW  " + b"DL4LGV    " + b"ALL       " + f[34:], peer[0])
time.sleep(2.5)

stat = [l for l in errlines if "YSF playback stopped" in l]
print("   engine:", stat[-1] if stat else "(no statistics line)")
if not stat: print("   engine output seen:", errlines[-15:])
m = re.search(r"frames played (\d+) , gaps \(interruptions\) (\d+)", stat[-1]) if stat else None
played, gaps = (int(m.group(1)), int(m.group(2))) if m else (0, -1)
check("stream was played", played >= 5 * (len(frames) - 3), f"played={played} of ~{5 * (len(frames) - 2)}")
check("no interruptions in the audio", gaps == 0, f"gaps={gaps}")

send("quit"); time.sleep(0.5); stop.set()
try: p.wait(timeout=4)
except subprocess.TimeoutExpired: p.kill()
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
