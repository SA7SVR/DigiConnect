"""EchoLink: the directory (sign-in and station list) and what the stations themselves tell us.

The voice part (RTP/RTCP over UDP 5198/5199, GSM audio) is in the engine (engine/src/elink.cpp). This module is the directory side:
  1. sign in to a directory server over TCP port 5200 with the callsign and the password of the user's own validated EchoLink account;
  2. ask for the station list ('s') and turn it into directory rows (callsign, place, node number, IP address, status), grouped by the country of the call sign;
  3. keep the account 'online' (the station we connect to checks in the directory that the caller is valid), and say 'offline' when the program closes.
The wire format here follows what other open-source EchoLink clients do; it has NOT been tried against the real directory from the build
environment (that needs a validated account). That is why every answer is kept and can be shown (Test connection), so a difference can be seen and fixed at once.
Nothing is guessed silently: a refusal or an unreadable answer is reported as it came."""
import re, socket, time
from . import countries

SERVERS = ["servers.echolink.org"]
PORT = 5200
VOICE_PORT = 5198
VERSION = "DigiConnect"
CONNECT_TIMEOUT = 8.0
READ_TIMEOUT = 15.0
MAX_BYTES = 8 * 1024 * 1024
STAY_ONLINE_EVERY = 5 * 60              # seconds between two 'online' messages while the program is open


def build_login(call: str, password: str, location: str = "", state: str = "ONLINE", now: time.struct_time | None = None) -> bytes:
    """'l' + callsign + 0xAC 0xAC + password + CR + STATE + version(HH:MM) + CR + location + CR   (state: ONLINE, BUSY or OFFLINE)."""
    now = now or time.localtime()
    head = b"l" + call.strip().upper().encode("latin-1", "replace") + b"\xac\xac" + password.encode("latin-1", "replace")
    tail = f"\r{state}{VERSION}({now.tm_hour:02d}:{now.tm_min:02d})\r{(location or '').strip()}\r".encode("latin-1", "replace")
    return head + tail


def parse_login_reply(raw: bytes) -> tuple[bool, str]:
    """(accepted, the answer as text). The server answers 'OK' when the call sign and password are valid; anything else is a refusal that is shown as it is."""
    text = raw.decode("latin-1", "replace").strip()
    return text.upper().startswith("OK"), text


def kind_of(call: str) -> str:
    c = call.strip().upper()
    if c.startswith("*") and c.endswith("*"): return "conference"
    if c.endswith("-R"): return "repeater"
    if c.endswith("-L"): return "link"
    return "station"


def parse_stations(raw: bytes) -> list[dict]:
    """The station list: after the '@@@' line, 4 lines per station - call sign, place (with the status in square brackets), node number, IP address.
    Tolerant: a count line, blank lines or CR LF are accepted; a record that does not fit is skipped, not guessed."""
    lines = [l.strip() for l in raw.decode("latin-1", "replace").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    if "@@@" in lines: lines = lines[lines.index("@@@") + 1:]
    lines = [l for l in lines if l != ""] if len(lines) % 4 else lines
    if lines and lines[0].isdigit() and (len(lines) - 1) % 4 == 0: lines = lines[1:]
    out = []
    for i in range(0, len(lines) - 3, 4):
        call, place, node, ip = lines[i:i + 4]
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) or not call: continue
        status = "BUSY" if "BUSY" in place.upper() else "ON"
        loc = re.sub(r"\s*\[[^\]]*\]\s*$", "", place).strip()
        out.append(dict(call=call, place=loc, node=node if node.isdigit() else "", ip=ip, status=status, kind=kind_of(call)))
    return out


def directory_rows(stations: list[dict]) -> list[dict]:
    """Directory rows for the EchoLink page. Country: from the place when it names one, else from the prefix of the call sign."""
    rows = []
    for s in stations:
        country = countries.guess(s["place"]) or countries.of_callsign(s["call"])
        kind = {"conference": "Conference", "repeater": "Repeater", "link": "Link", "station": "Station"}[s["kind"]]
        sub = " · ".join(x for x in (kind, s["place"], f"Node {s['node']}" if s["node"] else "", "busy" if s["status"] == "BUSY" else "") if x)
        rows.append(dict(net="EchoLink", id=s["call"], name=s["call"], sub=sub, activity="", proto="ELINK", country=country, host=s["ip"], port=VOICE_PORT, kind=s["kind"], status=s["status"]))
    return rows


def _exchange(host: str, payload: bytes, timeout: float = READ_TIMEOUT, connect_timeout: float = CONNECT_TIMEOUT) -> bytes:
    """One request on a fresh TCP connection, answer read until the server closes it (or the size limit)."""
    with socket.create_connection((host, PORT), timeout=connect_timeout) as s:
        s.settimeout(timeout); s.sendall(payload); chunks, total = [], 0
        while total < MAX_BYTES:
            try: b = s.recv(65536)
            except socket.timeout: break
            if not b: break
            chunks.append(b); total += len(b)
    return b"".join(chunks)


def sign_in(call: str, password: str, location: str = "", state: str = "ONLINE", want_list: bool = True, servers: list[str] | None = None, exchange=_exchange) -> dict:
    """Blocking (run it in a worker thread). Result: ok, error (words), server, login_raw, list_raw (the answers as received), stations (parsed)."""
    call = (call or "").strip().upper()
    res = dict(ok=False, error="", server="", login_raw="", list_raw="", stations=[])
    if not re.match(r"^[A-Z0-9/*-]{3,20}$", call): res["error"] = "Enter your callsign (the one of your validated EchoLink account)."; return res
    if not password: res["error"] = "Enter your EchoLink password."; return res
    last = ""
    for server in (servers or SERVERS):
        try:
            raw = exchange(server, build_login(call, password, location, state))
        except Exception as ex:
            last = f"Cannot reach the EchoLink directory ({server}: {getattr(ex, 'strerror', None) or ex})."; continue
        ok, text = parse_login_reply(raw)
        res.update(server=server, login_raw=text)
        if not ok:
            res["error"] = ("The EchoLink directory did not accept the sign-in: " + text[:120]) if text else "The EchoLink directory gave no answer to the sign-in."
            return res
        if state == "OFFLINE" or not want_list: res["ok"] = True; return res
        try:
            lraw = exchange(server, b"s")
        except Exception as ex:
            res["error"] = f"Signed in, but the station list could not be read ({getattr(ex, 'strerror', None) or ex})."; return res
        res["list_raw"] = lraw[:4000].decode("latin-1", "replace")
        res["stations"] = parse_stations(lraw)
        if not res["stations"]: res["error"] = "Signed in, but the station list was empty or in an unexpected form (Test connection shows what the directory sent)."; return res
        res["ok"] = True; return res
    res["error"] = last or "Cannot reach the EchoLink directory."
    return res


# ---- what a station tells us (greeting, 'who is connected') ------------------------------------------------------
_CALL = re.compile(r"(?<![A-Za-z0-9*])(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{3,7}(?:-[LR])?(?![A-Za-z0-9*])")
_LEFT = re.compile(r"\b(disconnect\w*|left|leaving|bye|removed)\b|^\s*-", re.I)
_NOISE = {"WELCOME", "CONFERENCE", "USERS", "ECHOLINK"}


def calls_in(text: str) -> list[str]:
    """Call signs written in a message, in order, without duplicates."""
    seen, out = set(), []
    for m in _CALL.findall((text or "").upper()):
        if m not in seen and m not in _NOISE: seen.add(m); out.append(m)
    return out


def apply_text(state: dict, text: str, keep: int = 40) -> dict:
    """Keeps the last lines a station sent and the call signs that are connected to it: a call sign in a line is added, unless the line says it left."""
    lines = state.setdefault("lines", []); calls = state.setdefault("calls", [])
    for line in (text or "").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line: continue
        lines.append(line)
        for c in calls_in(line):
            if _LEFT.search(line):
                if c in calls: calls.remove(c)
            elif c not in calls: calls.append(c)
    del lines[:-keep]
    state["ts"] = time.time()
    return state
