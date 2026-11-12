"""Persistent data: settings + favorites (JSON) and QSO journal (SQLite)."""
import json, os, sqlite3, datetime as dt
from pathlib import Path
from .qt import QtCore


def data_dir() -> Path:
    base = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.AppDataLocation)
    p = Path(base or Path.home() / ".digiconnect") / "DigiConnect"
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULTS = dict(callsign="", locator="", module="D", equipment="", radio_message="DigiConnect",
                language="English", theme="dark", text_size=14, max_ptt=120, fav_view="Full cards",
                mic="", speakers="", mic_gain=100, duck=True, rec_path="", listen_mode="multiple",
                dmr_id="", nxdn_id="", essid="", dmr_server="", dmr_port=62031, slot=2, cc=1,
                remember_pw=True, echolink_call="", share_presence=True, asl_user="", asl_client_id="", asl_remember=True, asl_pw="")


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()
        from . import diag; diag.start(self.root)
        self.settings_file = self.root / "settings.json"
        self.fav_file = self.root / "favorites.json"
        self.settings = dict(DEFAULTS)
        self.favorites: list[dict] = []
        self._load()
        self.db = sqlite3.connect(self.root / "journal.sqlite3")
        self.db.execute("""CREATE TABLE IF NOT EXISTS qso(id INTEGER PRIMARY KEY, callsign TEXT, start_utc TEXT, end_utc TEXT,
            system TEXT, dest TEXT, name TEXT, country TEXT, qth TEXT, grid TEXT, band TEXT, freq TEXT, equipment TEXT,
            rst_s TEXT, rst_r TEXT, notes TEXT, audio TEXT, deleted INTEGER DEFAULT 0)""")
        self.db.commit()

    def _load(self):
        for f, apply in ((self.settings_file, lambda d: self.settings.update(d)),
                         (self.fav_file, lambda d: setattr(self, "favorites", d))):
            try:
                apply(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass

    def save_settings(self):
        self.settings_file.write_text(json.dumps(self.settings, indent=1, ensure_ascii=False), encoding="utf-8")

    def save_favorites(self):
        self.fav_file.write_text(json.dumps(self.favorites, indent=1, ensure_ascii=False), encoding="utf-8")

    # favorites
    def is_fav(self, net, id_): return any(f["net"] == net and f["id"] == id_ for f in self.favorites)

    def toggle_fav(self, net, id_, name):
        for f in self.favorites:
            if f["net"] == net and f["id"] == id_:
                self.favorites.remove(f); break
        else:
            self.favorites.append(dict(net=net, id=id_, name=name))
        self.save_favorites()

    # journal
    FIELDS = ("callsign start_utc end_utc system dest name country qth grid band freq equipment rst_s rst_r notes audio").split()

    def add_qso(self, q: dict) -> int:
        cur = self.db.execute(f"INSERT INTO qso({','.join(self.FIELDS)}) VALUES({','.join('?'*len(self.FIELDS))})",
                              [q.get(k, "") for k in self.FIELDS])
        self.db.commit(); return cur.lastrowid

    def search_qso(self, text="", system="", d_from="", d_to="", country="", trash=False):
        sql, args = "SELECT * FROM qso WHERE deleted=?", [1 if trash else 0]
        if text:
            like = f"%{text}%"
            sql += " AND (callsign LIKE ? OR dest LIKE ? OR notes LIKE ? OR name LIKE ?)"; args += [like] * 4
        if system: sql += " AND system=?"; args.append(system)
        if d_from: sql += " AND substr(start_utc,1,10)>=?"; args.append(d_from)
        if d_to: sql += " AND substr(start_utc,1,10)<=?"; args.append(d_to)
        if country: sql += " AND country LIKE ?"; args.append(f"%{country}%")
        self.db.row_factory = sqlite3.Row
        rows = [dict(r) for r in self.db.execute(sql + " ORDER BY start_utc DESC", args)]
        self.db.row_factory = None
        return rows

    def set_deleted(self, ids, flag):
        self.db.executemany("UPDATE qso SET deleted=? WHERE id=?", [(1 if flag else 0, i) for i in ids]); self.db.commit()

    # exports (use the current filters: caller passes filtered rows)
    @staticmethod
    def to_csv(rows) -> str:
        cols = ["callsign", "start_utc", "end_utc", "system", "dest", "name", "country", "qth", "grid", "band", "freq", "equipment", "rst_s", "rst_r", "notes"]
        esc = lambda v: '"' + str(v or "").replace('"', '""') + '"'
        return "\n".join([";".join(cols)] + [";".join(esc(r.get(c)) for c in cols) for r in rows]) + "\n"

    @staticmethod
    def to_adif(rows, own_call="") -> str:
        def f(tag, v):
            v = "" if v is None else str(v)
            return f"<{tag}:{len(v.encode())}>{v} " if v else ""
        out = ["DigiConnect ADIF export\n<ADIF_VER:5>3.1.4 <EOH>\n"]
        for r in rows:
            s = (r.get("start_utc") or "").replace("-", "").replace(":", "").replace("T", " ").replace(" ", "")
            e = (r.get("end_utc") or "").replace("-", "").replace(":", "").replace("T", " ").replace(" ", "")
            out.append(f("CALL", r["callsign"]) + f("QSO_DATE", s[:8]) + f("TIME_ON", s[8:14]) + f("QSO_DATE_OFF", e[:8]) + f("TIME_OFF", e[8:14])
                       + f("MODE", "DIGITALVOICE") + f("SUBMODE", r["system"]) + f("NAME", r["name"]) + f("COUNTRY", r["country"])
                       + f("QTH", r["qth"]) + f("GRIDSQUARE", r["grid"]) + f("BAND", r["band"]) + f("FREQ", r["freq"])
                       + f("RST_SENT", r["rst_s"]) + f("RST_RCVD", r["rst_r"]) + f("NOTES", r["notes"])
                       + f("APP_DIGICONNECT_DEST", r["dest"]) + f("STATION_CALLSIGN", own_call) + "<EOR>\n")
        return "".join(out)

    @staticmethod
    def parse_adif(text: str):
        import re
        body = re.split(r"<eoh>", text, flags=re.I)[-1]
        recs = []
        for chunk in re.split(r"<eor>", body, flags=re.I):
            d = {}
            for m in re.finditer(r"<(\w+):(\d+)(?::\w+)?>", chunk):
                d[m.group(1).upper()] = chunk[m.end():m.end() + int(m.group(2))]
            if d.get("CALL"): recs.append(d)
        return recs

    def import_adif(self, text: str, skip_dups=True):
        added = skipped = 0
        for d in self.parse_adif(text):
            date, tm = d.get("QSO_DATE", ""), (d.get("TIME_ON", "") + "000000")[:6]
            if len(date) != 8: skipped += 1; continue
            start = f"{date[:4]}-{date[4:6]}-{date[6:]}T{tm[:2]}:{tm[2:4]}:{tm[4:]}"
            net = d.get("SUBMODE") if d.get("SUBMODE") in ("DMR", "D-Star", "EchoLink", "C4FM") else "ADIF"
            if skip_dups and self.db.execute("SELECT 1 FROM qso WHERE callsign=? AND system=? AND start_utc=? AND deleted=0",
                                             (d["CALL"], net, start)).fetchone():
                skipped += 1; continue
            self.add_qso(dict(callsign=d["CALL"], start_utc=start, system=net, dest=d.get("APP_DIGICONNECT_DEST", ""), name=d.get("NAME", ""),
                              country=d.get("COUNTRY", ""), qth=d.get("QTH", ""), grid=d.get("GRIDSQUARE", ""), band=d.get("BAND", ""),
                              freq=d.get("FREQ", ""), rst_s=d.get("RST_SENT", ""), rst_r=d.get("RST_RCVD", ""), notes=d.get("NOTES", "")))
            added += 1
        return added, skipped
