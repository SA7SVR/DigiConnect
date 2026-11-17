"""Map page: where the stations heard on the networks are, by country, with their call signs and a list to the right.
Positions: each station is placed at the centre of its country (the call sign tells the country). Exact places come later.
The stations come from the program itself: the people heard on the networks (Last heard) and the EchoLink station list."""
import json
from pathlib import Path
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .widgets import label, vbox, hbox
from ..theme import C, NET_COLOR
from .. import countries
from ..rules import NETS
from .. import online
from ..qt import Signal

WORLD = json.loads((Path(__file__).resolve().parent.parent / "data" / "world110.json").read_text(encoding="utf-8"))


def _centres() -> dict:
    """Country name (lower case) -> (lon, lat) at the centre of its largest outline."""
    out = {}
    for c in WORLD:
        best = None
        for ring in c["rings"]:
            if not ring: continue
            xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if best is None or area > best[0]: best = (area, ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
        if best:
            out[c["name"].lower()] = best[1]
            if c["iso"]: out.setdefault(c["iso"].lower(), best[1])
    return out

CENTRES = _centres()


class WorldMap(W.QWidget):
    """Equirectangular world map drawn from the bundled outlines, with a dot and a call sign for each station."""
    LAT_TOP, LAT_BOTTOM = 84.0, -58.0

    def __init__(self):
        super().__init__(); self.setMinimumHeight(260); self.stations: list[dict] = []; self.setMouseTracking(True)
        self.setToolTipDuration(4000)

    def set_stations(self, st): self.stations = st; self.update()

    def _xy(self, lon, lat):
        w, h = self.width(), self.height()
        x = (lon + 180.0) / 360.0 * w
        y = (self.LAT_TOP - lat) / (self.LAT_TOP - self.LAT_BOTTOM) * h
        return x, y

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(C["groove"]))
        land = QtGui.QColor("#2b3a57"); land_hit = QtGui.QColor("#3f5d8f"); edge = QtGui.QPen(QtGui.QColor("#1b2740"), 0.6)
        hit = {}
        for s in self.stations:
            if s.get("country"): hit[s["country"].lower()] = True
        p.setPen(edge)
        for c in WORLD:
            key = c["name"].lower()
            p.setBrush(land_hit if key in hit else land)
            for ring in c["rings"]:
                poly = QtGui.QPolygonF([QtCore.QPointF(*self._xy(lon, lat)) for lon, lat in ring])
                p.drawPolygon(poly)
        # one dot per station; stations of the same country are spread on a small circle around the centre
        groups: dict = {}
        placed = []
        for s in self.stations:
            if s.get("pos"):                                   # a grid square from the server: the exact centre of that square
                x, y = self._xy(*s["pos"]); col = QtGui.QColor(NET_COLOR.get(s["net"], C["accent"]))
                p.setPen(QtGui.QPen(QtGui.QColor("#0b1222"), 1)); p.setBrush(col); p.drawEllipse(QtCore.QPointF(x, y), 4.5, 4.5)
                p.setPen(QtGui.QColor(C["text"])); p.drawText(QtCore.QPointF(x + 6, y + 4), s["call"])
            elif s.get("country"): groups.setdefault(s["country"].lower(), []).append(s)
        font = p.font(); font.setPointSize(max(7, font.pointSize() - 1)); p.setFont(font)
        for key, items in groups.items():
            ctr = CENTRES.get(key)
            if not ctr: continue
            cx, cy = self._xy(*ctr)
            for i, s in enumerate(items):
                ang = i * 0.9; r = 0 if len(items) == 1 else 6 + 3 * (i // 6)
                x, y = cx + r * (1 if len(items) == 1 else __import__("math").cos(ang)), cy + r * (0 if len(items) == 1 else __import__("math").sin(ang))
                col = QtGui.QColor(NET_COLOR.get(s["net"], C["accent"]))
                p.setPen(QtGui.QPen(QtGui.QColor("#0b1222"), 1)); p.setBrush(col); p.drawEllipse(QtCore.QPointF(x, y), 4.5, 4.5)
                if i < 4:
                    p.setPen(QtGui.QColor(C["text"])); p.drawText(QtCore.QPointF(x + 6, y + 4), s["call"])
                    p.setPen(QtGui.QPen(QtGui.QColor("#0b1222"), 1))
        p.end()


class MapPage(W.QWidget):
    NET_CHOICES = ["All networks"] + list(NETS)
    online_ready = Signal(object)

    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx; self.online_now: list = []; self.online_ready.connect(self._online_got)
        v = vbox(self, m=(24, 18, 24, 18), s=10)
        t = label("Map"); t.setStyleSheet("font-size:22px;font-weight:700;"); v.addWidget(t)
        self.sub = label("", muted=True); self.sub.setWordWrap(True); v.addWidget(self.sub)
        top = hbox(s=10); top.addWidget(label("Network")); self.net = W.QComboBox(); self.net.addItems(self.NET_CHOICES); self.net.setMaximumWidth(220)
        top.addWidget(self.net); top.addStretch(1); self.count = label("", muted=True); top.addWidget(self.count); v.addLayout(top)
        body = hbox(s=14)
        self.map = WorldMap(); body.addWidget(self.map, 3)
        self.table = W.QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["Call sign", "Network", "Country", "Last seen"])
        self.table.verticalHeader().setVisible(False); self.table.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True); body.addWidget(self.table, 2)
        v.addLayout(body, 1)
        self.net.currentIndexChanged.connect(lambda _: self.refresh())
        self._t = QtCore.QTimer(self); self._t.setInterval(5000); self._t.timeout.connect(self.refresh); self._t.start()
        self._online_t = QtCore.QTimer(self); self._online_t.setInterval(60000); self._online_t.timeout.connect(self._fetch_online); self._online_t.start()
        self._fetch_online(); self.refresh()

    def _fetch_online(self):
        """The server's list of stations online now, fetched in the background (the page never waits for the network)."""
        import threading
        threading.Thread(target=lambda: self.online_ready.emit(online.fetch()), daemon=True).start()

    def _online_got(self, rows):
        self.online_now = rows; self.refresh()

    def _stations(self) -> list[dict]:
        """Stations from the program: the people heard on the networks, and the EchoLink stations in the directory (their country)."""
        out, seen = [], set()
        for h in list(self.ctx.last_heard)[:60]:
            call = (h.get("src") or "").strip()
            if not call: continue
            country = countries.of_callsign(call)
            if not country: continue
            key = (h["net"], call)
            if key in seen: continue
            seen.add(key); out.append(dict(call=call, net=h["net"], country=country, seen=h.get("last"), source="heard"))
        for o in self.online_now:
            key = (online.net_of(o["rx"], o["tx"]), o["call"])
            if key in seen: continue
            seen.add(key)
            out.append(dict(call=o["call"], net=key[0], country=countries.of_callsign(o["call"]) or "", seen=None, source="online",
                            pos=online.grid_centre(o["grid"]), grid=o["grid"], ptt=o["ptt"]))
        for s in getattr(self.ctx, "el_stations", []) or []:
            if not s.get("country"): continue
            key = ("EchoLink", s["id"])
            if key in seen: continue
            seen.add(key); out.append(dict(call=s["id"], net="EchoLink", country=s["country"], seen=None, source="directory"))
        return out

    def refresh(self):
        choice = self.net.currentText()
        st = [s for s in self._stations() if choice == "All networks" or s["net"] == choice]
        self.map.set_stations(st)
        self.count.setText(f"{len(st)} stations · {len({s['country'] for s in st if s.get('country')})} countries")
        self.sub.setText("Stations heard on the networks, and the EchoLink station list. Each dot is at the centre of the station's country, "
                         "not at its exact place. Heard stations stay here for the time the program keeps them.")
        self.table.setRowCount(len(st))
        for i, s in enumerate(st):
            seen = s["seen"].strftime("%H:%M:%S") + " UTC" if s.get("seen") else ("online" + (" · " + s["grid"] if s.get("grid") else "") if s["source"] == "online" else ("directory" if s["source"] == "directory" else "")) 
            for j, val in enumerate([s["call"], s["net"], s["country"], seen]):
                self.table.setItem(i, j, W.QTableWidgetItem(val))
