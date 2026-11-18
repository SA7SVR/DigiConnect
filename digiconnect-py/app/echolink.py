"""EchoLink: the directory (sign-in and station list) and what the stations themselves tell us.

The voice part (RTP/RTCP over UDP 5198/5199, GSM audio) is in the engine (engine/src/elink.cpp). This module is the directory side:
  1. sign in to a directory server over TCP port 5200 with the callsign and the password of the user's own validated EchoLink account;
  2. ask for the station list ('s') and turn it into directory rows (callsign, place, node number, IP address, status), grouped by the country of the call sign;
  3. keep the account 'online' (the station we connect to checks in the directory that the caller is valid), and say 'offline' when the program closes.
The wire format follows SvxLink's EchoLink directory client (src/echolib/EchoLinkDirectory.cpp, EchoLinkStationData.cpp), the open-source client that
talks to the real directory every day. It has not been tried from the build environment (that needs the user's validated account and the network), so every
answer is kept and can be shown (Test connection).
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
    """As SvxLink sends it: 'l' + callsign + 0xAC 0xAC + password + CR + 'ONLINE3.38(HH:MM)' | 'BUSY3.40(HH:MM)' | 'OFF-V3.40' + CR + description + CR."""
    now = now or time.localtime()
    head = b"l" + call.strip().upper().encode("latin-1", "replace") + b"\xac\xac" + password.encode("latin-1", "replace")
    st = "OFF-V3.40" if state == "OFFLINE" else (f"BUSY3.40({now.tm_hour:02d}:{now.tm_min:02d})" if state == "BUSY" else f"ONLINE3.38({now.tm_hour:02d}:{now.tm_min:02d})")
    return head + f"\r{st}\r{(location or '').strip()}\r".encode("latin-1", "replace")


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


def parse_list(raw: bytes) -> tuple[list[dict], list[str]]:
    """The directory's answer to 's', read exactly as SvxLink reads it: a line '@@@', a line with the number of records, then per record 4 lines
    (call sign, description with '[ON] hh:mm' or '[BUSY] hh:mm' at the end, node number, IP address), then '+++'.
    A record whose call sign is blank is a message of the directory (its text is in the description), a record '.' is skipped.
    Result: (stations, messages). Lines are NOT stripped before they are told apart: the blank call sign of a message record is a line of its own."""
    lines = raw.decode("latin-1", "replace").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    marks = [i for i, l in enumerate(lines) if l.strip() == "@@@"]
    if not marks: return [], []
    i = marks[0] + 1
    try: count = int(lines[i].strip())
    except (IndexError, ValueError): return [], []
    i += 1; out, msgs = [], []
    while count > 0 and i + 3 < len(lines) + 0 and not lines[i].startswith("+++"):
        call, data, node, ip = lines[i], lines[i + 1], lines[i + 2].strip(), lines[i + 3].strip(); i += 4
        if call.strip() == ".": continue                                   # a filler record: not counted
        count -= 1
        if call.strip() == "": msgs.append(data.strip()); continue       # a message of the directory
        call = call.strip(); desc, status, at = data, "", ""
        k = data.rfind("[")
        if k >= 0:
            tail = data[k + 1:]; status = "BUSY" if "BUSY" in tail else ("ON" if "ON" in tail else ""); desc = data[:k]
            sp = data[k:].find(" "); at = data[k:][sp + 1:sp + 6] if sp >= 0 else ""
        out.append(dict(call=call, place=desc.rstrip(), node=node if node.isdigit() else "", ip=ip, status="BUSY" if status == "BUSY" else "ON", at=at, kind=kind_of(call)))
    return out, msgs


def parse_stations(raw: bytes) -> list[dict]:
    return parse_list(raw)[0]


KIND_ORDER = {"repeater": 0, "link": 1, "station": 2, "conference": 3}


def directory_rows(stations: list[dict]) -> list[dict]:
    """Directory rows for the EchoLink page. Country: from the prefix of the call sign, else from the place text (conference rooms have no usable call sign)."""
    rows = []
    for s in stations:
        country = countries.of_callsign(s["call"]) or countries.guess(s["place"])      # the call sign decides (as EchoLink itself groups): "HELLAS Zone Net" in the place text of SA7SVR-L must not move a Swedish node to Greece
        kind = {"conference": "Conference", "repeater": "Repeater", "link": "Link", "station": "Station"}[s["kind"]]
        sub = " · ".join(x for x in (kind, s["place"], f"Node {s['node']}" if s["node"] else "", "busy" if s["status"] == "BUSY" else "") if x)
        rows.append(dict(net="EchoLink", id=s["call"], name=s["call"], sub=sub, activity="", proto="ELINK", country=country, host=s["ip"], port=VOICE_PORT, kind=s["kind"], status=s["status"]))
    rows.sort(key=lambda r: (KIND_ORDER[r["kind"]], r["id"].upper()))          # the order of the official EchoLink list: by type (repeaters, links, users, conferences), then by call sign
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
    res = dict(ok=False, error="", server="", login_raw="", list_raw="", stations=[], messages=[])
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
        res["stations"], msgs = parse_list(lraw); res["messages"] = msgs
        bad = next((m for m in msgs if m.upper().startswith("INCORRECT PASSWORD")), "")
        if bad: res["error"] = "The EchoLink directory did not accept the sign-in: " + bad[:120]; return res
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
