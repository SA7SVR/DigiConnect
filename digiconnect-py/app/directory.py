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
    return seed + [e for e in hosts.for_net(net) if e["id"].split()[0] not in have]


def _seed(net: str) -> list[dict]:
    mk = lambda id_, name, sub, act="Activity unavailable": dict(net=net, id=id_, name=name, sub=sub, activity=act)
    # C4FM / D-Star: nothing is invented here. Every reflector comes from the downloaded worldwide lists (real names, real addresses).
    if net == "DMR":
        tg = [("1", "Local"), ("2", "Cluster"), ("8", "Regional"), ("9", "Local"), ("91", "World-wide"), ("92", "Europe"),
              ("93", "North America"), ("94", "Asia, Middle East"), ("95", "Australia, New Zealand"), ("202", "Greece"), ("240", "Sweden")]
        from .countries import of_talkgroup
        return [dict(mk(i, n, f"TG {i} · Not specified", "Idle" if int(i) >= 91 else "Activity unavailable"), country=of_talkgroup(i)) for i, n in tg]
    return []   # EchoLink: directory loads after sign-in
