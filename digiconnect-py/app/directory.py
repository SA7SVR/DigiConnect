"""Station directories. HELLAS Zone entries and the public DMR talkgroups come first, then everything from the
worldwide server lists (hostlists.py: YSF, REF/XRF/DCS/XLX). EchoLink loads after sign-in."""

def entries(net: str, hosts=None) -> list[dict]:
    seed = _seed(net)
    if hosts is None: return seed
    have = {e["id"].split()[0] for e in seed}
    return seed + [e for e in hosts.for_net(net) if e["id"].split()[0] not in have]


def _seed(net: str) -> list[dict]:
    mk = lambda id_, name, sub, act="Activity unavailable": dict(net=net, id=id_, name=name, sub=sub, activity=act)
    if net == "C4FM":
        return [mk("00006", "GR-HELLAS Zone A · (YCS202)", "00006 · YSF"), mk("00010", "GR-HELLAS Zone B · DX Zone", "00010 · YSF"),
                mk("00011", "GR-HELLAS Zone C · CQ Zone", "00011 · YSF"), mk("00012", "GR-XLXQRZ · QRZ Net", "00012 · YSF")]
    if net == "DMR":
        tg = [("1", "Local"), ("2", "Cluster"), ("8", "Regional"), ("9", "Local"), ("91", "World-wide"), ("92", "Europe"),
              ("93", "North America"), ("94", "Asia, Middle East"), ("95", "Australia, New Zealand"), ("202", "Greece"), ("240", "Sweden")]
        return [mk(i, n, f"TG {i} · Not specified", "Idle" if int(i) >= 91 else "Activity unavailable") for i, n in tg]
    if net == "D-Star":
        return [mk("XLXQRZ B", "HELLAS Zone XLX · module B", "XLX · module B")]
    return []   # EchoLink: directory loads after sign-in
