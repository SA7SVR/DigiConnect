"""Country of a reflector / talkgroup, worked out from what its name or number says (the public host files carry no country column).
Only a clear match is used; anything else stays empty (it is then listed under 'All countries', never under a wrong country).
Names come from Qt's own country table (English), so no list has to be typed in."""
import re
from functools import lru_cache

# Amateur-radio call-sign prefixes that are not the ISO code of the country (ISO codes themselves are used as they are).
HAM = {"SV": "GR", "SM": "SE", "OZ": "DK", "LA": "NO", "OH": "FI", "PA": "NL", "ON": "BE", "HB": "CH", "OE": "AT", "EA": "ES", "IZ": "IT", "IK": "IT", "IW": "IT",
       "DL": "DE", "HA": "HU", "OK": "CZ", "SP": "PL", "YO": "RO", "LZ": "BG", "YU": "RS", "VK": "AU", "ZL": "NZ", "JA": "JP", "PY": "BR", "LU": "AR", "CT": "PT",
       "EI": "IE", "TA": "TR", "UA": "RU", "RA": "RU", "UR": "UA", "UK": "GB", "G": "GB", "OM": "SK", "9A": "HR", "S5": "SI", "E7": "BA", "LY": "LT", "YL": "LV",
       "ES": "EE", "SU": "EG", "4X": "IL", "ZS": "ZA", "CX": "UY", "XE": "MX", "VE": "CA", "W": "US", "K": "US", "TF": "IS", "5B": "CY", "9H": "MT", "Z3": "MK",
       "ER": "MD", "EW": "BY", "LX": "LU", "OD": "LB", "HZ": "SA", "A4": "OM", "VU": "IN", "BV": "TW", "HL": "KR", "DU": "PH", "HS": "TH", "9M": "MY", "9V": "SG"}
ALIASES = {"usa": "US", "u.s.a": "US", "united states": "US", "america": "US", "uk": "GB", "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
           "deutschland": "DE", "espana": "ES", "españa": "ES", "italia": "IT", "hellas": "GR", "ellada": "GR", "sverige": "SE", "suomi": "FI", "nederland": "NL",
           "osterreich": "AT", "österreich": "AT", "schweiz": "CH", "suisse": "CH", "polska": "PL", "danmark": "DK", "norge": "NO", "brasil": "BR", "czech": "CZ",
           "russia": "RU", "korea": "KR", "holland": "NL", "belgie": "BE", "belgique": "BE", "türkiye": "TR", "turkiye": "TR"}
# Mobile country codes: the first three digits of a DMR talkgroup / radio id are the country (202 = Greece, 240 = Sweden, ...).
MCC = {"202": "GR", "204": "NL", "206": "BE", "208": "FR", "212": "MC", "213": "AD", "214": "ES", "216": "HU", "218": "BA", "219": "HR", "220": "RS", "222": "IT", "225": "VA",
       "226": "RO", "228": "CH", "230": "CZ", "231": "SK", "232": "AT", "234": "GB", "235": "GB", "238": "DK", "240": "SE", "242": "NO", "244": "FI", "246": "LT", "247": "LV",
       "248": "EE", "250": "RU", "255": "UA", "257": "BY", "259": "MD", "260": "PL", "262": "DE", "266": "GI", "268": "PT", "270": "LU", "272": "IE", "274": "IS", "276": "AL",
       "278": "MT", "280": "CY", "282": "GE", "283": "AM", "284": "BG", "286": "TR", "290": "GL", "293": "SI", "294": "MK", "295": "LI", "297": "ME", "302": "CA", "310": "US",
       "311": "US", "312": "US", "313": "US", "316": "US", "334": "MX", "404": "IN", "405": "IN", "440": "JP", "441": "JP", "450": "KR", "460": "CN", "466": "TW", "502": "MY",
       "505": "AU", "510": "ID", "515": "PH", "520": "TH", "525": "SG", "530": "NZ", "602": "EG", "655": "ZA", "722": "AR", "724": "BR", "730": "CL", "732": "CO", "748": "UY"}


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    from .qt import QtCore
    out = {}
    for c in QtCore.QLocale.Country:
        try: code, name = QtCore.QLocale.territoryToCode(c), QtCore.QLocale.territoryToString(c)
        except Exception: continue
        if code and len(code) == 2 and name and "Default" not in name: out[code] = name
    return out


@lru_cache(maxsize=1)
def _names() -> list[tuple[re.Pattern, str]]:
    t = _table()
    pats = [(re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", re.I), c) for c, n in t.items() if len(n) >= 5]
    pats += [(re.compile(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", re.I), c) for a, c in ALIASES.items()]
    return pats


def name_of(code: str) -> str: return _table().get(code, "")


def guess(*texts: str) -> str:
    """Country name for a reflector from its name/description, or '' when nothing clear is there."""
    t = _table()
    for text in texts:
        text = (text or "").strip()
        if not text: continue
        head = re.split(r"[^A-Za-z0-9]", text, maxsplit=1)[0].upper()          # 'GR-HELLAS Zone A' -> 'GR', 'DL' ...
        if len(head) <= 3 and re.match(r"^[A-Za-z0-9]+$", head) and len(text) > len(head) and text[len(head)] in "-_ .:/":
            code = HAM.get(head) or (head if head in t else "")
            if code and code in t: return t[code]
        for rx, code in _names():
            if rx.search(text) and code in t: return t[code]
    return ""


def of_talkgroup(tg: str) -> str:
    """Country of a DMR talkgroup from its leading mobile country code (3-digit prefix of 3..7 digit numbers like 202, 20208, 2401)."""
    tg = str(tg)
    if len(tg) >= 3 and tg[:3] in MCC and (len(tg) == 3 or len(tg) >= 4): return _table().get(MCC[tg[:3]], "")
    return ""


# ---- country of an amateur call sign (ITU prefix blocks; only the common ones - an unknown prefix gives '' and the station is listed under 'All countries') ----
def _blocks() -> dict[str, str]:
    def rng(a: str, b: str, code: str, out: dict):
        for x in range(ord(a[-1]), ord(b[-1]) + 1): out[a[:-1] + chr(x)] = code
    o: dict[str, str] = {}
    for a, b, c in (("SA", "SM", "SE"), ("SN", "SR", "PL"), ("SV", "SZ", "GR"), ("3Z", "3Z", "PL"), ("HF", "HF", "PL"), ("OH", "OH", "FI"), ("OF", "OJ", "FI"), ("LA", "LN", "NO"),
                    ("OZ", "OZ", "DK"), ("OU", "OW", "DK"), ("5P", "5Q", "DK"), ("PA", "PI", "NL"), ("ON", "OT", "BE"), ("DA", "DR", "DE"), ("EA", "EH", "ES"), ("IA", "IZ", "IT"),
                    ("HB", "HB", "CH"), ("HE", "HE", "CH"), ("HA", "HA", "HU"), ("HG", "HG", "HU"), ("OK", "OL", "CZ"), ("OM", "OM", "SK"), ("YO", "YR", "RO"), ("LZ", "LZ", "BG"),
                    ("YT", "YU", "RS"), ("YZ", "YZ", "RS"), ("UA", "UI", "RU"), ("RA", "RZ", "RU"), ("UR", "UZ", "UA"), ("EM", "EO", "UA"), ("OE", "OE", "AT"), ("CT", "CT", "PT"),
                    ("CQ", "CU", "PT"), ("EI", "EJ", "IE"), ("TA", "TC", "TR"), ("YM", "YM", "TR"), ("VA", "VG", "CA"), ("VO", "VO", "CA"), ("VY", "VY", "CA"), ("XJ", "XO", "CA"),
                    ("VK", "VK", "AU"), ("ZL", "ZM", "NZ"), ("JA", "JS", "JP"), ("7J", "7N", "JP"), ("8J", "8N", "JP"), ("PP", "PY", "BR"), ("LO", "LW", "AR"), ("CE", "CE", "CL"),
                    ("ZS", "ZU", "ZA"), ("9A", "9A", "HR"), ("S5", "S5", "SI"), ("E7", "E7", "BA"), ("LY", "LY", "LT"), ("YL", "YL", "LV"), ("ES", "ES", "EE"), ("TF", "TF", "IS"),
                    ("5B", "5B", "CY"), ("C4", "C4", "CY"), ("P3", "P3", "CY"), ("9H", "9H", "MT"), ("Z3", "Z3", "MK"), ("ER", "ER", "MD"), ("EW", "EW", "BY"), ("LX", "LX", "LU"),
                    ("4X", "4Z", "IL"), ("VU", "VW", "IN"), ("HL", "HL", "KR"), ("DS", "DT", "KR"), ("BV", "BX", "TW"), ("XE", "XI", "MX"), ("CX", "CX", "UY"), ("ZP", "ZP", "PY")):
        rng(a, b, c, o)
    for p in ("F",): o[p] = "FR"
    for p in ("G", "M", "2E", "2D", "2M", "2I", "2W"): o[p] = "GB"
    for p in ("W", "K", "N", "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK", "AL"): o[p] = "US"
    for p in ("D",): o.setdefault(p, "DE")
    for p in ("I",): o.setdefault(p, "IT")
    for p in ("R", "U"): o.setdefault(p, "RU")
    return o


@lru_cache(maxsize=1)
def _call_blocks() -> dict[str, str]: return _blocks()


def of_callsign(call: str) -> str:
    """Country name from the prefix of a call sign ('SV1ABC-R' -> Greece); '' when the prefix is not known or the name is not a call sign (*CONF*, *ECHOTEST*)."""
    c = (call or "").strip().upper()
    if not c or c.startswith("*") or c.startswith("?"): return ""
    c = re.sub(r"-[A-Z]$", "", c); c = c.split("/")[0] if "/" in c and len(c.split("/")[0]) >= 3 else c
    if not re.match(r"^[A-Z0-9]{3,10}$", c) or not re.search(r"\d", c): return ""
    t, b = _table(), _call_blocks()
    code = b.get(c[:2]) or b.get(c[:1]) or ""
    return t.get(code, "") if code else ""
