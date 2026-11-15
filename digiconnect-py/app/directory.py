"""Station directories. HELLAS Zone entries and the public DMR talkgroups come first, then everything from the
worldwide server lists (hostlists.py: YSF, REF/XRF/DCS/XLX). EchoLink loads after sign-in."""

def asl_entries(nodes) -> list[dict]:
    """AllStarLink nodes -> directory rows: title = description (or callsign), second line = node · callsign · place."""
    out = []
    for n in nodes:
        title = (n.get("desc") or "").strip() or n.get("call") or f"Node {n['node']}"
        sub = " · ".join(x for x in (f"Node {n['node']}", n.get("call", ""), n.get("loc", "")) if x)
        out.append(dict(net="AllStar", id=n["node"], name=title, sub=sub, activity="", proto="IAX", country=""))
    return out


def entries(net: str, hosts=None, asl=None) -> list[dict]:
    if net == "AllStar": return asl_entries(asl.nodes) if asl is not None else []
    seed = _seed(net)
    if hosts is None: return seed
    have = {e["id"].split()[0] for e in seed}
    out = seed + [e for e in hosts.for_net(net) if e["id"].split()[0] not in have]
    return dstar_modules(out) if net == "D-Star" else out


MODULES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def dstar_modules(rows: list[dict]) -> list[dict]:
    """A D-Star reflector has up to 26 modules (A-Z) and every client lists each one: the host lists have one line per reflector, so it is
    shown once for every module, the module in the name and in the id ('REF001 B'). The address is the reflector's (the module is only a letter)."""
    out = []
    for e in rows:
        ref = e["id"].split()[0]
        for m in MODULES:
            out.append(dict(e, id=f"{ref} {m}", name=f"{ref} {m}", sub=f"{ref} · module {m} · {e.get('proto', '')}"))
    return out


def _seed(net: str) -> list[dict]:
    mk = lambda id_, name, sub, act="Activity unavailable": dict(net=net, id=id_, name=name, sub=sub, activity=act)
    # C4FM / D-Star: nothing is invented here. Every reflector comes from the downloaded worldwide lists (real names, real addresses).
    # Nothing is typed in here: DMR talkgroups/masters, reflectors and nodes come ONLY from the downloaded source lists.
    return []   # EchoLink: directory loads after sign-in
