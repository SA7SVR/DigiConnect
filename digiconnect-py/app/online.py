"""The stations that are online now, from the HELLAS Zone server (online.php): call sign, grid square, what they listen to and transmit.
Only the public parts are asked for; nothing about the person is sent. The map uses the grid square for the position."""
import json
from . import net, diag

ONLINE_URL = "https://hellaszone.com/digiconnect/online.php"


def fetch(url: str = ONLINE_URL, timeout: int = 12) -> list[dict]:
    """The stations online now. Returns [] (and logs why) when the server cannot be reached or answers something else."""
    try:
        data = json.loads(net.get(url, timeout=timeout, limit=512 * 1024).decode("utf-8", "replace"))
    except Exception as e:
        diag.log(f"online list: {e}"); return []
    if not isinstance(data, dict) or not data.get("ok"): return []
    out = []
    for s in data.get("stations") or []:
        if not isinstance(s, dict) or not s.get("call"): continue
        out.append(dict(call=str(s["call"])[:15], grid=str(s.get("grid") or "")[:8], rx=str(s.get("rx") or "")[:120], tx=str(s.get("tx") or "")[:60], ptt=int(bool(s.get("ptt")))))
    return out


def grid_centre(grid: str):
    """Maidenhead locator (4 or 6 characters, e.g. JO89 or JO89ab) -> (lon, lat) at the centre of the square; None when it is not one."""
    g = (grid or "").strip().upper()
    if len(g) < 4 or not (g[0] in "ABCDEFGHIJKLMNOPQR" and g[1] in "ABCDEFGHIJKLMNOPQR" and g[2].isdigit() and g[3].isdigit()): return None
    lon = (ord(g[0]) - 65) * 20 - 180 + int(g[2]) * 2
    lat = (ord(g[1]) - 65) * 10 - 90 + int(g[3]) * 1
    w, h = 2.0, 1.0
    if len(g) >= 6 and g[4].isalpha() and g[5].isalpha():
        w, h = 2.0 / 24, 1.0 / 24
        lon += (ord(g[4]) - 65) * (2.0 / 24); lat += (ord(g[5]) - 65) * (1.0 / 24)
    return lon + w / 2, lat + h / 2


def net_of(rx: str, tx: str) -> str:
    """The network of what the station listens to ('DMR:24015' -> DMR); 'Program' when it is not known."""
    for part in (rx or "", tx or ""):
        head = part.split(",")[0].split(":")[0].strip()
        if head: return head
    return "Program"
