"""What the owner of the server allows in this installation: which radio modes work, whether the program may transmit, and whether this
version is too old. It arrives inside the SIGNED licence answer (field "pol"), so it cannot be edited in the settings file."""
from . import i18n


def pick(text: str) -> str:
    """The server writes its messages as 'Greek line\\nEnglish line'; the person sees the line of the program language."""
    lines = [l.strip() for l in (text or "").split("\n") if l.strip()]
    if not lines: return ""
    return lines[0] if (len(lines) == 1 or i18n.code() == "el") else lines[1]


class Policy:
    def __init__(self, pol: dict | None = None):
        p = pol if isinstance(pol, dict) else {}
        self.off = {str(x) for x in (p.get("off") or [])}
        self.note = str(p.get("note") or "")
        self.tx = bool(p.get("tx", 1))
        self.txnote = str(p.get("txnote") or "")
        self.old = bool(p.get("old"))
        self.minv = str(p.get("minv") or "")

    def allows(self, net: str) -> bool: return net not in self.off

    def reason(self, net: str = "") -> str:
        return pick(self.note) or "This mode is not available yet."

    def tx_reason(self) -> str:
        return pick(self.txnote) or "Transmitting is not available on this installation (listen only)."

    def __eq__(self, o): return isinstance(o, Policy) and (self.off, self.note, self.tx, self.txnote, self.old) == (o.off, o.note, o.tx, o.txnote, o.old)
    def __hash__(self): return hash((frozenset(self.off), self.tx, self.old))
