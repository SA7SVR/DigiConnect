#!/usr/bin/env python3
"""NXDN and P25: the engine must report 'connected' only when the reflector answers its poll, say so when nothing answers,
and report a received voice stream (fake reflectors, no radio, no audio hardware).

Usage: check_nxdn_p25.py /path/to/dcengine
"""
import json, os, queue, socket, subprocess, sys, threading, time

engine_bin = sys.argv[1]
fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra)[:600] if extra and not ok else ""))
    if not ok: fails.append(name)

class Engine:
    def __init__(self):
        self.q = queue.Queue()
        self.p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), text=True, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()
        self.send("hello"); self.wait(lambda e: e["ev"] == "hello", 5)
    def _read(self):
        for line in self.p.stdout:
            if line.strip().startswith("{"): self.q.put(json.loads(line))
    def send(self, cmd, **kw): self.p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); self.p.stdin.flush()
    def wait(self, pred, timeout=10.0):
        end = time.time() + timeout; seen = []
        while time.time() < end:
            try: e = self.q.get(timeout=0.2)
            except queue.Empty: continue
            seen.append(e)
            if pred(e): return e, seen
        return None, seen
    def quit(self):
        self.send("quit"); time.sleep(0.4)
        try: self.p.wait(timeout=4)
        except subprocess.TimeoutExpired: self.p.kill()

def reflector(port, answer_len, answer_first_bytes):
    """UDP reflector: answers every poll with an echo of answer_len bytes; keeps the sender so frames can be pushed back."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("127.0.0.1", port)); sock.settimeout(0.2)
    st = dict(peer=None, polls=0, stop=False, sock=sock)
    def run():
        while not st["stop"]:
            try: data, addr = sock.recvfrom(2048)
            except socket.timeout: continue
            st["peer"] = addr
            if data[:len(answer_first_bytes)] == answer_first_bytes and len(data) == answer_len:
                st["polls"] += 1; sock.sendto(data, addr)
    st["thread"] = threading.Thread(target=run, daemon=True); st["thread"].start()
    return st

def stop(st):
    st["stop"] = True; st["thread"].join(2); st["sock"].close()

# ---- NXDN: poll = 'NXDNP' + callsign(10) + TG(2) = 17 bytes, the reflector echoes it
r = reflector(41491, 17, b"NXDNP")
e = Engine(); e.send("connect", mode="NXDN", host="127.0.0.1", port=41491, callsign="SA7SVR", name="20", nxdnid=20202)
ev, seen = e.wait(lambda x: x["ev"] == "status" and x["state"] in ("connected", "error", "timeout"), 10)
check("NXDN connected after the reflector answered", bool(ev) and ev["state"] == "connected", seen)
check("NXDN reflector saw polls", r["polls"] >= 1, r["polls"])
frame = b"NXDND" + bytes([0x4E, 0x20, 0x00, 0x14, 0x00, 0x00]) + bytes(32)         # 43 bytes: voice frame, ids 0x4E20 -> 0x0014
for _ in range(10):
    r["sock"].sendto(frame, r["peer"]); time.sleep(0.04)
ev, seen = e.wait(lambda x: x["ev"] == "rx" and x["state"] in ("new", "streaming", "end"), 6)
check("NXDN received voice stream is reported", ev is not None, seen)
e.quit(); stop(r)

# ---- P25: poll = 0xF0 + callsign(10) = 11 bytes, the reflector echoes it
r = reflector(41492, 11, b"\xf0")
e = Engine(); e.send("connect", mode="P25", host="127.0.0.1", port=41492, callsign="SA7SVR", name="10200", dmrid=2400123)
ev, seen = e.wait(lambda x: x["ev"] == "status" and x["state"] in ("connected", "error", "timeout"), 10)
check("P25 connected after the reflector answered", bool(ev) and ev["state"] == "connected", seen)
check("P25 reflector saw polls", r["polls"] >= 1, r["polls"])
for _ in range(10):
    r["sock"].sendto(bytes([0x62]) + bytes(21), r["peer"]); time.sleep(0.04)
ev, seen = e.wait(lambda x: x["ev"] == "rx" and x["state"] in ("new", "streaming", "end"), 6)
check("P25 received voice stream is reported", ev is not None, seen)
e.quit(); stop(r)

# ---- nobody answers: the engine must say so (and never claim a connection)
for mode, kw in (("NXDN", dict(name="20", nxdnid=20202)), ("P25", dict(name="10200", dmrid=2400123))):
    e = Engine(); e.send("connect", mode=mode, host="127.0.0.1", port=41499, callsign="SA7SVR", **kw)
    ev, seen = e.wait(lambda x: x["ev"] == "status" and x["state"] in ("connected", "error", "timeout"), 20)
    check(f"{mode} without any answer ends with an error, not 'connected'", bool(ev) and ev["state"] == "error" and "No answer" in ev.get("msg", ""), seen)
    e.quit()

print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
