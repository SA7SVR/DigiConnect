#!/usr/bin/env python3
"""Stall test of dcengine against a fake YSF reflector (no radio, no audio hardware).

Usage: check_ysf_stall.py /path/to/dcengine [stall_ms]
A reflector bridged to another network (e.g. YSF00006 <-> DMR) can deliver a transmission in uneven bursts: the packets
stop for a while in the middle of the speech and then continue. The engine used to declare the stream lost after only
~0.4 s without packets, cut the transmission into several short pieces and the pieces were not heard properly.
This test replays one recorded transmission with a stall of STALL ms in the middle, then a second one, and reads the
engine's own statistics lines. PASS = each transmission is ONE playback (not cut into pieces) and the second one plays too.
(Original description of the recording method follows.)
A real C4FM repeater/reflector sends one voice packet (5 frames = 100 ms of speech) every 100 ms, but on the Internet the
packets do not arrive exactly 100 ms apart. This test records a transmission made by the engine itself, replays it as a
RECEIVED stream with random arrival jitter (and one longer stall), and reads the engine's own statistics line
("YSF playback stopped: frames played N, gaps (interruptions) G").
PASS = every voice frame was played and the audio had no interruptions."""
import json, os, queue, random, re, socket, subprocess, sys, threading, time

PORT = 42118
engine_bin = sys.argv[1]
STALL = float(sys.argv[2]) if len(sys.argv) > 2 else 900.0    # ms without any packet in the middle of the transmission
random.seed(7)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", PORT)); sock.settimeout(0.2)
events: "queue.Queue[dict]" = queue.Queue()
errlines: list = []
logev: list = []                                   # statistics as engine events (the same line also appears on stderr: count it once)
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True, bufsize=1)

def reader():
    for line in p.stdout:
        line = line.strip()
        if line.startswith("{"):
            e = json.loads(line)
            if e.get("ev") == "log": logev.append(str(e.get("text", "")))      # the engine reports the statistics as an event too
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

# replay twice: first with a stall in the middle, then plain
def replay(stall_ms):
    t0 = time.time()
    for i, f in enumerate(frames):
        due = i * 0.100 + (stall_ms / 1000.0 if i >= len(frames) // 2 else 0.0)
        while time.time() - t0 < due: time.sleep(0.001)
        sock.sendto(b"YSFD" + b"REMOTEGW  " + b"DL4LGV    " + b"ALL       " + f[34:], peer[0])
    time.sleep(2.5)

def stats():
    out = []
    for l in logev:
        m = re.search(r"frames played (\d+) , gaps \(interruptions\) (\d+)", l)
        if m and "YSF playback stopped" in l: out.append((int(m.group(1)), int(m.group(2))))
    return out

replay(STALL)
a = stats()
print("   after transmission 1:", a)
check("transmission with a %d ms stall is ONE playback (not cut into pieces)" % STALL, len(a) == 1, a)
if a: check("transmission 1 was played (almost) completely", a[0][0] >= 5 * (len(frames) - 3), "played=%d of ~%d" % (a[0][0], 5 * (len(frames) - 2)))
replay(0)
b = stats()
print("   after transmission 2:", b)
check("second transmission is heard too", len(b) == len(a) + 1 and b[-1][0] >= 5 * (len(frames) - 3), b)

# third transmission: a bridged reflector delivers in BURSTS (10 packets back to back, then a pause); every packet of every burst must be heard
def replay_bursts(burst=10, pause=0.9):
    for i in range(0, len(frames), burst):
        for f in frames[i:i + burst]: sock.sendto(b"YSFD" + b"REMOTEGW  " + b"DL4LGV    " + b"ALL       " + f[34:], peer[0])
        time.sleep(pause)
    time.sleep(2.5)
replay_bursts()
c = stats()
print("   after transmission 3 (bursts):", c)
check("burst-wise transmission is heard completely", len(c) == len(b) + 1 and c[-1][0] >= 5 * (len(frames) - 3), c)
st = [l for l in logev if "YSF receive statistics" in l]
check("the engine reports receive statistics (packets, headers, terminators, longest wait, datagrams read at once)", len(st) >= 3 and "most datagrams read at once" in st[-1], st[-1:] )

send("quit"); time.sleep(0.5); stop.set()
try: p.wait(timeout=4)
except subprocess.TimeoutExpired: p.kill()
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
