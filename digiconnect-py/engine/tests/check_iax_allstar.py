#!/usr/bin/env python3
"""AllStarLink call of dcengine against a fake AllStar node (no network, no audio hardware).

Usage: check_iax_allstar.py /path/to/dcengine
The fake node behaves like an Asterisk/app_rpt node that accepts "allstar-public": it answers the call-token request, checks the NEW
frame (called number "s", calling number = node, calling name "TOKEN/CALLSIGN", user "allstar-public"), asks for MD5 authentication
with the shared secret "allstar", verifies the answer and accepts the call.  PASS = the engine reports "connected"."""
import hashlib, json, os, queue, socket, struct, subprocess, sys, threading, time

PORT = 42461
engine_bin = sys.argv[1]
NODE, CALL, TOKEN = "1999", "SA7SVR", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

AST_FRAME_CONTROL, AST_FRAME_IAX = 4, 6
CMD = dict(NEW=1, ACK=4, HANGUP=5, REJECT=6, ACCEPT=7, AUTHREQ=8, AUTHREP=9, CALLTOKEN=40)
IE_CALLED, IE_CALLING_NUM, IE_CALLING_NAME, IE_USER, IE_AUTHMETHODS, IE_CHALLENGE, IE_MD5, IE_CALLTOKEN = 1, 2, 4, 6, 14, 15, 16, 54

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("127.0.0.1", PORT)); sock.settimeout(0.2)
events: "queue.Queue[dict]" = queue.Queue()
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
p = subprocess.Popen([engine_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True, bufsize=1)

def reader():
    for line in p.stdout:
        line = line.strip()
        if line.startswith("{"): events.put(json.loads(line))
threading.Thread(target=reader, daemon=True).start()
threading.Thread(target=lambda: [None for _ in p.stderr], daemon=True).start()

def send(cmd, **kw):
    p.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n"); p.stdin.flush()

def wait_ev(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        try: e = events.get(timeout=0.2)
        except queue.Empty: continue
        if pred(e): return e
    return None

def ies(buf):
    out, i = {}, 12
    while i + 2 <= len(buf):
        t, n = buf[i], buf[i + 1]; out[t] = bytes(buf[i + 2:i + 2 + n]); i += 2 + n
    return out

def frame(dcall, ftype, sub, body=b"", oseq=0, iseq=1):
    return struct.pack(">HHIBBBB", 0x8000 | 1, dcall & 0x7fff, 0, oseq, iseq, ftype, sub) + body

seen = {"new": [], "authrep": None, "dtmf": []}; stop = threading.Event(); secret = b"allstar"
challenge = b"1234567890"
def node():
    while not stop.is_set():
        try: data, addr = sock.recvfrom(2048)
        except socket.timeout: continue
        if len(data) < 12 or not (data[0] & 0x80): continue
        client_call = ((data[0] & 0x7f) << 8) | data[1]
        if data[10] == 1: seen["dtmf"].append(chr(data[11])); continue          # AST_FRAME_DTMF: the key is the subclass
        if data[10] != AST_FRAME_IAX: continue
        sub = data[11]
        if sub == CMD["NEW"]:
            e = ies(data); seen["new"].append(e)
            if not e.get(IE_CALLTOKEN):                      # first NEW has an empty token: ask for call-token handling
                sock.sendto(frame(client_call, AST_FRAME_IAX, CMD["CALLTOKEN"], bytes([IE_CALLTOKEN, 8]) + b"TOKEN123"), addr)
            else:
                body = bytes([IE_AUTHMETHODS, 2, 0, 2]) + bytes([IE_CHALLENGE, len(challenge)]) + challenge
                sock.sendto(frame(client_call, AST_FRAME_IAX, CMD["AUTHREQ"], body), addr)
        elif sub == CMD["AUTHREP"]:
            seen["authrep"] = ies(data).get(IE_MD5)
            ok = seen["authrep"] == hashlib.md5(challenge + secret).hexdigest().encode()
            if ok:
                sock.sendto(frame(client_call, AST_FRAME_IAX, CMD["ACCEPT"], bytes([9, 4, 0, 0, 0, 4]), oseq=1, iseq=2), addr)
                sock.sendto(frame(client_call, AST_FRAME_CONTROL, 4, b"", oseq=2, iseq=2), addr)      # AST_CONTROL_ANSWER
            else:
                sock.sendto(frame(client_call, AST_FRAME_IAX, CMD["REJECT"], bytes([22, 6]) + b"denied"), addr)
threading.Thread(target=node, daemon=True).start()

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + str(extra) if extra else ""))
    if not ok: fails.append(name)

send("hello"); check("hello", wait_ev(lambda e: e["ev"] == "hello", 5) is not None)
send("connect", mode="IAX", host="127.0.0.1", port=PORT, callsign=CALL, name=NODE, iax_user="allstar-public", iax_pass="allstar",
     iax_name=f"{TOKEN}/{CALL}", vocoder="Software vocoder")
e = wait_ev(lambda e: e["ev"] == "status" and e["state"] in ("connected", "error", "timeout", "disconnected"), 10)
check("connected", bool(e) and e["state"] == "connected", e)
new = seen["new"][-1] if seen["new"] else {}
check("called number is 's'", new.get(IE_CALLED) == b"s", new.get(IE_CALLED))
check("calling number is the node", new.get(IE_CALLING_NUM) == NODE.encode(), new.get(IE_CALLING_NUM))
check("calling name is TOKEN/CALLSIGN", new.get(IE_CALLING_NAME) == f"{TOKEN}/{CALL}".encode(), new.get(IE_CALLING_NAME))
check("user is allstar-public", new.get(IE_USER) == b"allstar-public", new.get(IE_USER))
check("MD5 answer with the shared secret", seen["authrep"] == hashlib.md5(challenge + secret).hexdigest().encode(), seen["authrep"])

send("dtmf", keys="*3#"); time.sleep(1.0)
check("DTMF keys reach the node", seen["dtmf"] == ["*", "3", "#"], seen["dtmf"])

send("quit"); time.sleep(0.5); stop.set()
try: p.wait(timeout=4)
except subprocess.TimeoutExpired: p.kill()
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
