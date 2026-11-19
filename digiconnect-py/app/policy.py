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
        paid = p.get("paid")
        self.paid = {str(k): v for k, v in paid.items() if isinstance(v, dict)} if isinstance(paid, dict) else {}     # extras that are closed until paid: {mode: {offer, amount, link, msg}}
        self.minv = str(p.get("minv") or "")
        self.user_off: set = set()          # modes this person switched off on the network tabs (settings, not the owner's)

    def allows(self, net: str) -> bool: return net not in self.off and net not in self.user_off

    def paid_info(self, net: str):
        """The extra that is closed on this installation until it is paid (offer, amount, link, message), or None."""
        i = self.paid.get(net)
        return i if (i and net in self.off) else None

    def paid_link(self, net: str) -> str:
        l = str((self.paid.get(net) or {}).get("link") or "")
        return l if l.lower().startswith("https://") else ""                      # only https; empty = the program's own donation link

    def reason(self, net: str = "") -> str:
        i = self.paid_info(net)
        if i:
            first = i18n.tr(net + (" is an extra. To unlock it, make an additional donation with the button on this page." if i.get("offer") != "buy" else " is an extra. To unlock it, buy it with the button on this page."))
            own = pick(str(i.get("msg") or ""))
            return first + ("\n\n" + own if own else "")
        return pick(self.note) or "This mode is not available yet."

    def tx_reason(self) -> str:
        return pick(self.txnote) or "Transmitting is not available on this installation (listen only)."

    def __eq__(self, o): return isinstance(o, Policy) and (self.off, self.note, self.tx, self.txnote, self.old, self.paid) == (o.off, o.note, o.tx, o.txnote, o.old, o.paid)
    def __hash__(self): return hash((frozenset(self.off), self.tx, self.old, frozenset(self.paid)))
