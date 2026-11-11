"""Where each directory entry connects to.

Order: addresses the user typed (servers.json) > built-in > the worldwide lists downloaded by
hostlists.py. Only if none knows the entry is the user asked once (host:port); no address is ever guessed. Per-mode defaults (ports) are the standard ones for that protocol."""
import json
from .rules import Target
from .hostlists import HostLists

# Standard UDP ports per protocol (used when the user types just a host name).
DEFAULT_PORT = {"YSF": 42000, "DMR": 62031, "REF": 20001, "XRF": 30001, "DCS": 30051,
                "NXDN": 41400, "P25": 41000, "M17": 17000}

# Entries known with certainty. Add more here as the HELLAS Zone endpoints are confirmed.
BUILTIN: dict[str, dict] = {
    # "C4FM:00006": {"host": "...", "port": 42000},
}


def protocol_for(t: Target) -> str | None:
    if t.net == "C4FM": return "YSF"
    if t.net in ("DMR", "NXDN", "P25", "M17"): return t.net
    if t.net == "D-Star":
        p = t.id.strip().upper()
        if p.startswith("REF"): return "REF"
        if p.startswith("XRF"): return "XRF"
        return "DCS"            # DCSxxx and XLXxxx reflectors both speak DCS
    return None                 # EchoLink: not available in this build


def split_dstar(t: Target) -> tuple[str, str]:
    """'XLXQRZ B' -> ('XLXQRZ', 'B'); module defaults to ' ' when absent."""
    parts = t.id.strip().upper().split()
    return parts[0], (parts[1][0] if len(parts) > 1 and parts[1] else " ")


class Servers:
    def __init__(self, store):
        self.file = store.root / "servers.json"
        self.user: dict[str, dict] = {}
        try:
            self.user = json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            pass
        self.settings = store.settings
        self.hosts = HostLists.for_root(store.root)

    @staticmethod
    def key(t: Target) -> str:
        if t.net in ("D-Star", "M17"): return f"{t.net}:{split_dstar(t)[0]}"      # module is not part of the address
        return f"{t.net}:{t.id}"

    def resolve(self, t: Target) -> dict | None:
        if t.net == "DMR":
            host = (self.settings.get("dmr_server") or "").strip()
            if not host: return None
            return {"host": host, "port": int(self.settings.get("dmr_port") or DEFAULT_PORT["DMR"])}
        k = self.key(t)
        if self.user.get(k) or BUILTIN.get(k): return self.user.get(k) or BUILTIN.get(k)
        if t.net == "C4FM": return self.hosts.find("YSF", t.id)                    # worldwide list, downloaded
        if t.net in ("NXDN", "P25"): return self.hosts.find(t.net, t.id.strip())
        if t.net == "M17": return self.hosts.find("M17", split_dstar(t)[0])
        if t.net == "D-Star":
            ref = split_dstar(t)[0]
            for proto in ("REF", "XRF", "DCS", "XLX"):
                if ref.startswith(proto): return self.hosts.find(proto, ref)
        return None

    def info(self, t: Target) -> tuple[dict | None, str]:
        """(endpoint, where it comes from): 'your address', 'built in', 'DMR master (Settings)', 'worldwide list' or ''."""
        if t.net == "DMR":
            ep = self.resolve(t); return ep, ("DMR master (Settings)" if ep else "")
        k = self.key(t)
        if self.user.get(k): return self.user[k], "your address"
        if BUILTIN.get(k): return BUILTIN[k], "built in"
        ep = self.resolve(t)
        return ep, ("worldwide list" if ep else "")

    def clear(self, t: Target) -> bool:
        """Removes the user's own address for this entry (the list value is used again)."""
        k = self.key(t)
        if k not in self.user: return False
        del self.user[k]; self.file.write_text(json.dumps(self.user, indent=1), encoding="utf-8"); return True

    def remember(self, t: Target, text: str) -> bool:
        """Accepts 'host' or 'host:port'. Returns False when the text is not usable."""
        text = text.strip()
        if not text or " " in text: return False
        host, _, port = text.partition(":")
        proto = protocol_for(t)
        if not proto: return False
        if port and not (port.isdigit() and 0 < int(port) < 65536): return False
        self.user[self.key(t)] = {"host": host, "port": int(port) if port else DEFAULT_PORT[proto]}
        self.file.write_text(json.dumps(self.user, indent=1), encoding="utf-8")
        return True
