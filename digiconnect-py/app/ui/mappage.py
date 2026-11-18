"""Map page: where the stations heard on the networks are, by country, with a list to the right.
Positions: a station with a grid square from the server is drawn at that square; every other station is counted in ONE circle at the centre of its
country (the call sign tells the country) — the number in the circle is how many stations are there. The map zooms (wheel, +/− buttons, double-click)
and moves (drag); hovering a circle lists who is in it; a click (or the Country box) lists that country's stations in the table.
The stations come from the program itself: the people heard on the networks (Last heard), the stations online now, and the EchoLink station list."""
import json, math
from pathlib import Path
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .widgets import label, vbox, hbox, tidy_table
from ..theme import C, NET_COLOR
from .. import countries
from ..rules import NETS
from .. import online
from ..qt import Signal
from ..i18n import tr

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


def _spans() -> dict:
    """Country name (lower case) -> (width, height) in degrees of its largest outline: how far to zoom in to see the whole country."""
    out = {}
    for c in WORLD:
        best = None
        for ring in c["rings"]:
            if not ring: continue
            xs = [p[0] for p in ring]; ys = [p[1] for p in ring]; w, h = max(xs) - min(xs), max(ys) - min(ys)
            if best is None or w * h > best[0]: best = (w * h, (w, h))
        if best: out[c["name"].lower()] = best[1]
    return out

SPANS = _spans()

# Names of the country table that the bundled outlines write differently, and countries/territories too small to be in the outlines (lon, lat).
# Without these a station of the United States, Türkiye, Singapore, Malta ... could not be placed at all.
_ALIAS = {"united states": "united states of america", "türkiye": "turkey", "bosnia & herzegovina": "bosnia and herz.", "congo - kinshasa": "dem. rep. congo",
          "congo - brazzaville": "congo", "myanmar (burma)": "myanmar", "dominican republic": "dominican rep.", "central african republic": "central african rep.",
          "equatorial guinea": "eq. guinea", "south sudan": "s. sudan", "falkland islands": "falkland is.", "palestinian territories": "palestine",
          "trinidad & tobago": "trinidad and tobago", "western sahara": "w. sahara", "solomon islands": "solomon is.", "côte d’ivoire": "côte d'ivoire",
          "french southern territories": "fr. s. antarctic lands", "hong kong sar china": "china", "macao sar china": "china"}
_EXTRA = {"american samoa": (-170.7, -14.3), "andorra": (1.6, 42.5), "anguilla": (-63.1, 18.2), "antigua & barbuda": (-61.8, 17.1), "aruba": (-70.0, 12.5),
          "ascension island": (-14.4, -7.9), "bahrain": (50.55, 26.0), "barbados": (-59.55, 13.2), "bermuda": (-64.75, 32.3), "bouvet island": (3.4, -54.4),
          "british indian ocean territory": (72.4, -7.3), "british virgin islands": (-64.6, 18.4), "canary islands": (-15.6, 28.3), "cape verde": (-23.6, 15.1),
          "caribbean netherlands": (-68.3, 12.2), "cayman islands": (-81.25, 19.3), "ceuta & melilla": (-3.0, 35.5), "christmas island": (105.65, -10.5),
          "clipperton island": (-109.2, 10.3), "cocos (keeling) islands": (96.85, -12.15), "comoros": (43.35, -11.65), "cook islands": (-159.8, -21.2),
          "curaçao": (-69.0, 12.2), "diego garcia": (72.4, -7.3), "dominica": (-61.35, 15.4), "faroe islands": (-6.9, 62.0), "french guiana": (-53.1, 3.9),
          "french polynesia": (-149.4, -17.7), "gibraltar": (-5.35, 36.14), "grenada": (-61.7, 12.1), "guadeloupe": (-61.55, 16.25), "guam": (144.8, 13.45),
          "guernsey": (-2.58, 49.45), "heard & mcdonald islands": (73.5, -53.1), "isle of man": (-4.55, 54.2), "jersey": (-2.13, 49.2), "kiribati": (173.0, 1.4),
          "liechtenstein": (9.55, 47.15), "maldives": (73.5, 3.2), "malta": (14.4, 35.9), "marshall islands": (171.2, 7.1), "martinique": (-61.0, 14.65),
          "mauritius": (57.55, -20.25), "mayotte": (45.15, -12.8), "micronesia": (158.2, 6.9), "monaco": (7.42, 43.74), "montserrat": (-62.2, 16.75),
          "nauru": (166.9, -0.53), "niue": (-169.9, -19.05), "norfolk island": (167.95, -29.05), "northern mariana islands": (145.7, 15.2), "palau": (134.5, 7.5),
          "pitcairn islands": (-128.3, -24.4), "réunion": (55.5, -21.1), "samoa": (-172.1, -13.75), "san marino": (12.45, 43.94), "seychelles": (55.45, -4.65),
          "singapore": (103.82, 1.35), "sint maarten": (-63.05, 18.05), "south georgia & south sandwich islands": (-36.5, -54.3), "st. barthélemy": (-62.85, 17.9),
          "st. helena": (-5.7, -15.95), "st. kitts & nevis": (-62.75, 17.35), "st. lucia": (-60.98, 13.9), "st. martin": (-63.05, 18.08),
          "st. pierre & miquelon": (-56.3, 46.9), "st. vincent & grenadines": (-61.2, 13.25), "svalbard & jan mayen": (16.0, 78.0), "são tomé & príncipe": (6.6, 0.3),
          "tokelau": (-171.8, -9.2), "tonga": (-175.2, -21.2), "tristan da cunha": (-12.3, -37.1), "turks & caicos islands": (-71.8, 21.8), "tuvalu": (178.7, -7.5),
          "u.s. outlying islands": (-169.5, 16.7), "u.s. virgin islands": (-64.85, 18.35), "vatican city": (12.45, 41.9), "wallis & futuna": (-177.15, -13.8),
          "åland islands": (20.0, 60.25), "outlying oceania": (-160.0, -10.0)}


def centre_of(country: str):
    """(lon, lat) of the centre of a country as the program names it, or None when the place is not known (e.g. "European Union")."""
    k = (country or "").strip().lower()
    return CENTRES.get(k) or CENTRES.get(_ALIAS.get(k, "")) or _EXTRA.get(k)


def dominant(items) -> str:
    """The network with most stations in a list of stations."""
    n: dict = {}
    for s in items: n[s["net"]] = n.get(s["net"], 0) + 1
    return max(n, key=lambda k: (n[k], k)) if n else ""


def bubble_radius(n: int) -> float:
    """Pixel radius of a country's circle: grows slowly with the number of stations, never fills the map."""
    return 6.0 if n <= 1 else min(20.0, 7.0 + 1.7 * math.sqrt(n - 1))


class WorldMap(W.QWidget):
    """Equirectangular world map from the bundled outlines. Zoomable and movable; one circle per country (with the number of stations), a dot and
    the call sign for a station with an exact place."""
    LAT_TOP, LAT_BOTTOM = 84.0, -58.0
    ZMIN, ZMAX = 1.0, 40.0
    country_clicked = Signal(str)
    station_clicked = Signal(object)          # a single station's dot was clicked (the station dict)

    def __init__(self):
        super().__init__(); self.setMinimumHeight(260); self.stations: list[dict] = []; self.setMouseTracking(True)
        self.zoom = 1.0; self.u0 = 0.0; self.v0 = 0.0          # the view: top-left corner as a fraction of the whole map, and the zoom
        self.selected = ""                                      # country (lower case) chosen in the list or by a click
        self.hover = None                                       # (net, call) of the dot under the pointer: it grows and shows its call sign
        self.hl = None                                          # (net, call) of the station to point out (chosen in a radio page or in the table)
        self._hits: list = []                                   # circles and dots of the last paint: (x, y, radius, country, [stations])
        self._press = None; self._moved = False
        self.btn = {}
        for key, txt, tip, fn in (("in", "+", "Zoom in", lambda: self.zoom_by(1.6)), ("out", "−", "Zoom out", lambda: self.zoom_by(1 / 1.6)),
                                  ("reset", "⟲", "Show the whole world", self.reset_view)):
            b = W.QPushButton(txt, self); b.setFixedSize(32, 32); b.setToolTip(tip); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus); b.clicked.connect(fn); b.setStyleSheet("QPushButton{font-size:17px;font-weight:700;padding:0;}")
            self.btn[key] = b
        self._place_buttons()

    # ---- the view ----
    def _place_buttons(self):
        x = self.width() - 40
        for i, k in enumerate(("in", "out", "reset")): self.btn[k].move(x, 8 + i * 36)

    def resizeEvent(self, e): self._place_buttons(); self._clamp(); super().resizeEvent(e)

    def _clamp(self):
        span = 1.0 / self.zoom
        self.u0 = min(max(self.u0, 0.0), 1.0 - span); self.v0 = min(max(self.v0, 0.0), 1.0 - span)

    def set_stations(self, st): self.stations = st; self.update()

    def _xy(self, lon, lat):
        w, h = max(1, self.width()), max(1, self.height())
        u = (lon + 180.0) / 360.0; v = (self.LAT_TOP - lat) / (self.LAT_TOP - self.LAT_BOTTOM)
        return (u - self.u0) * self.zoom * w, (v - self.v0) * self.zoom * h

    def zoom_at(self, factor, px=None, py=None):
        """Zoom around a point of the widget (the middle when none), so that the place under it stays under it."""
        w, h = max(1, self.width()), max(1, self.height())
        px = w / 2 if px is None else px; py = h / 2 if py is None else py
        u = self.u0 + px / (w * self.zoom); v = self.v0 + py / (h * self.zoom)
        z = min(max(self.zoom * factor, self.ZMIN), self.ZMAX)
        self.zoom = z; self.u0 = u - px / (w * z); self.v0 = v - py / (h * z); self._clamp(); self.update()

    def zoom_by(self, factor): self.zoom_at(factor)

    def reset_view(self): self.zoom = 1.0; self.u0 = 0.0; self.v0 = 0.0; self.update()

    def focus(self, country: str):
        """Highlight a country and bring it to the middle of the view (zoomed in when the whole world is shown)."""
        self.selected = (country or "").lower(); ctr = centre_of(self.selected)
        if not ctr: self.update(); return
        sp = SPANS.get(self.selected) or SPANS.get(_ALIAS.get(self.selected, ""))
        fit = min(0.6 / (sp[0] / 360.0), 0.6 / (sp[1] / (self.LAT_TOP - self.LAT_BOTTOM))) if sp else 12.0          # the whole country fills ~60 % of the view
        self.zoom = min(self.ZMAX, max(2.0, fit))
        u = (ctr[0] + 180.0) / 360.0; v = (self.LAT_TOP - ctr[1]) / (self.LAT_TOP - self.LAT_BOTTOM)
        self.u0 = u - 0.5 / self.zoom; self.v0 = v - 0.5 / self.zoom; self._clamp(); self.update()

    # ---- the mouse ----
    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d: self.zoom_at(1.25 ** (d / 120.0), e.position().x(), e.position().y())
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = (e.position().x(), e.position().y()); self._moved = False; self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        x, y = e.position().x(), e.position().y()
        if self._press is not None:
            dx, dy = x - self._press[0], y - self._press[1]
            if abs(dx) + abs(dy) > 3: self._moved = True
            if self._moved:
                w, h = max(1, self.width()), max(1, self.height())
                self.u0 -= dx / (w * self.zoom); self.v0 -= dy / (h * self.zoom); self._clamp(); self._press = (x, y); self.update()
            return
        hit = self.hit_at(x, y)
        now = (hit[4][0]["net"], hit[4][0]["call"]) if hit and len(hit[4]) == 1 else None
        if now != self.hover: self.hover = now; self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor if hit else Qt.CursorShape.OpenHandCursor)
        if hit: W.QToolTip.showText(e.globalPosition().toPoint(), self.tooltip_for(hit), self)
        else: W.QToolTip.hideText()

    def leaveEvent(self, e):
        if self.hover is not None: self.hover = None; self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._press is None: return
        moved = self._moved; self._press = None; self._moved = False; self.setCursor(Qt.CursorShape.OpenHandCursor)
        if not moved:
            hit = self.hit_at(e.position().x(), e.position().y())
            if hit and len(hit[4]) == 1 and self.selected: self.station_clicked.emit(hit[4][0])          # an opened country: its stations are separate dots
            elif hit: self.country_clicked.emit(hit[3])

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.zoom_at(2.0, e.position().x(), e.position().y())

    def hit_at(self, x, y):
        """The circle or dot under a point of the widget (the nearest), or None."""
        best = None
        for h in self._hits:
            d = math.hypot(h[0] - x, h[1] - y)
            if d <= h[2] + 3 and (best is None or d < best[0]): best = (d, h)
        return best[1] if best else None

    SOURCE_TEXT = {"heard": "heard by this program", "online": "online now (HELLAS Zone server)", "directory": "EchoLink directory", "server": "server / reflector list", "allstar": "AllStarLink node list"}

    def tooltip_for(self, hit) -> str:
        items = hit[4]; names = {}
        if len(items) == 1:
            s = items[0]; bits = [f"<b>{s['call']}</b> · {s['net']}"]
            if s.get("name"): bits.append(s["name"])
            bits.append(s.get("country") or "—")
            if s.get("grid"): bits.append(f"{tr('Grid locator')} {s['grid']}")
            if s.get("seen"): bits.append(f"{tr('Last seen')} {s['seen']:%H:%M:%S} UTC")
            return "<br>".join((" · ".join(bits[:1] + [x for x in bits[1:] if x]), f"<i>{tr(self.SOURCE_TEXT.get(s.get('source'), ''))}</i>"))
        for s in items: names[s["net"]] = names.get(s["net"], 0) + 1
        nets = " · ".join(f"{n} {c}" for n, c in sorted(names.items(), key=lambda kv: -kv[1]))
        calls = ", ".join(s["call"] for s in items[:12]) + (f" … +{len(items) - 12}" if len(items) > 12 else "")
        where = (items[0].get("grid") and f" · {items[0]['grid']}") or ""
        return (f"<b>{hit[3]}</b>{where} — {len(items)} {tr('station' if len(items) == 1 else 'stations')}<br>{nets}<br>{calls}"
                f"<br><i>{tr('Click to list them in the table')}</i>")

    # ---- the picture ----
    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(C["groove"]))
        land = QtGui.QColor("#2b3a57"); land_hit = QtGui.QColor("#3f5d8f"); land_sel = QtGui.QColor("#5a7fb8"); edge = QtGui.QPen(QtGui.QColor("#1b2740"), 0.6)
        hit_c = {_ALIAS.get(s["country"].lower(), s["country"].lower()) for s in self.stations if s.get("country")}
        p.setPen(edge)
        for c in WORLD:
            key = c["name"].lower()
            p.setBrush(land_sel if key == _ALIAS.get(self.selected, self.selected) else land_hit if key in hit_c else land)
            for ring in c["rings"]:
                p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*self._xy(lon, lat)) for lon, lat in ring]))
        self._hits = []
        groups: dict = {}; exact = [s for s in self.stations if s.get("pos")]
        for s in self.stations:
            if not s.get("pos") and s.get("country"): groups.setdefault(s["country"].lower(), []).append(s)
        font = p.font(); font.setPointSize(max(8, font.pointSize() - 1)); p.setFont(font)
        # a circle per country, the largest first so that the small ones stay on top and can be reached
        for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            ctr = centre_of(key)
            if not ctr: continue
            x, y = self._xy(*ctr)
            if x < -30 or y < -30 or x > self.width() + 30 or y > self.height() + 30: continue
            if key == self.selected and len(items) > 1:                       # the chosen country is opened: every station is its own dot
                self._spread(p, font, key, items, x, y); continue
            r = bubble_radius(len(items)); col = QtGui.QColor(NET_COLOR.get(dominant(items), C["accent"])); fill = QtGui.QColor(col); fill.setAlpha(215)
            p.setPen(QtGui.QPen(QtGui.QColor("#ffffff") if key == self.selected else QtGui.QColor("#0b1222"), 2.2 if key == self.selected else 1.2))
            p.setBrush(fill); p.drawEllipse(QtCore.QPointF(x, y), r, r)
            name = items[0]["country"]
            if len(items) > 1:
                f2 = QtGui.QFont(font); f2.setBold(True); p.setFont(f2); p.setPen(QtGui.QColor("#0b1222"))
                p.drawText(QtCore.QRectF(x - r, y - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, str(len(items))); p.setFont(font)
            if self.zoom >= 2.0 or len(items) == 1:
                p.setPen(QtGui.QColor(C["text"])); p.drawText(QtCore.QPointF(x + r + 4, y + 4), items[0]["call"] if len(items) == 1 else name)
            self._hits.append((x, y, r, name, items))
        # stations with an exact place (a grid square from the server): a dot each; their call signs show when there is room (few, or zoomed in)
        show_calls = len(exact) <= 25 or self.zoom >= 3.0
        for s in exact:
            x, y = self._xy(*s["pos"])
            if x < -30 or y < -30 or x > self.width() + 30 or y > self.height() + 30: continue
            col = QtGui.QColor(NET_COLOR.get(s["net"], C["accent"]))
            p.setPen(QtGui.QPen(QtGui.QColor("#0b1222"), 1)); p.setBrush(col); p.drawEllipse(QtCore.QPointF(x, y), 5.0, 5.0)
            if show_calls: p.setPen(QtGui.QColor(C["text"])); p.drawText(QtCore.QPointF(x + 7, y + 4), s["call"])
            self._hits.append((x, y, 5.0, s.get("country") or s["call"], [s]))
        p.end()


    @staticmethod
    def spacing_for(n: int) -> float:
        """Distance between the dots of an opened country: wide enough to read the call signs when there are few, tight when there are many."""
        return 46.0 if n <= 12 else 34.0 if n <= 30 else 12.0

    def _spread(self, p, font, key, items, cx, cy):
        """The stations of the opened country, one dot each, laid out in a sunflower pattern around the country's centre. Only the country is known for
        them (no grid square), so the pattern is a way to show them separately and is NOT their real place; a faint ring marks the cluster."""
        items = sorted(items, key=lambda s: (s["net"], s["call"].upper()))
        pos = []; sp = self.spacing_for(len(items))
        for i, s in enumerate(items):
            r = sp * math.sqrt(i + 0.5); a = i * 2.399963229728653          # golden angle: even, never in rows
            pos.append((cx + r * math.cos(a), cy + r * math.sin(a), s))
        rad = sp * math.sqrt(len(items) + 0.5) + 10
        ring = QtGui.QColor(C["muted"]); ring.setAlpha(120); p.setPen(QtGui.QPen(ring, 1.2, Qt.PenStyle.DashLine)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QtCore.QPointF(cx, cy), rad, rad)
        f2 = QtGui.QFont(font); f2.setBold(True); p.setFont(f2); p.setPen(QtGui.QColor(C["text"]))
        p.drawText(QtCore.QPointF(cx - rad * 0.9, cy - rad - 6), f"{items[0]['country']} · {len(items)}  ({tr('places inside the country are not exact')})"); p.setFont(font)
        label_all = len(items) <= 30
        for x, y, s in pos:
            if x < -20 or y < -20 or x > self.width() + 20 or y > self.height() + 20: continue
            col = QtGui.QColor(NET_COLOR.get(s["net"], C["accent"])); key = (s["net"], s["call"]); mine = self.hl == key; lit = mine or self.hover == key
            p.setPen(QtGui.QPen(QtGui.QColor("#ffffff") if lit else QtGui.QColor("#0b1222"), 2.4 if lit else 1)); p.setBrush(col)
            p.drawEllipse(QtCore.QPointF(x, y), 6.5 if lit else 4.6, 6.5 if lit else 4.6)
            if label_all or lit:
                f3 = QtGui.QFont(font); f3.setBold(lit); p.setFont(f3); p.setPen(QtGui.QColor(C["text"])); p.drawText(QtCore.QPointF(x + 9, y + 4), s["call"]); p.setFont(font)
            self._hits.append((x, y, 5.0, s.get("country") or s["call"], [s]))


class MapPage(W.QWidget):
    NET_CHOICES = ["All networks"] + list(NETS)
    ALL = "All countries"
    online_ready = Signal(object)

    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx; self.online_now: list = []; self.online_ready.connect(self._online_got)
        v = vbox(self, m=(24, 18, 24, 18), s=10)
        t = label("Map"); t.setStyleSheet("font-size:22px;font-weight:700;"); v.addWidget(t)
        self.sub = label("", muted=True); self.sub.setWordWrap(True); v.addWidget(self.sub)
        top = hbox(s=10); top.addWidget(label("Network")); self.net = W.QComboBox(); self.net.addItems(self.NET_CHOICES); self.net.setMaximumWidth(220)
        top.addWidget(self.net); top.addWidget(label("Country")); self.cty = W.QComboBox(); self.cty.setMaximumWidth(260); self.cty.setMinimumWidth(160)
        self.cty.addItem(tr(self.ALL), ""); top.addWidget(self.cty); top.addStretch(1); self.count = label("", muted=True); top.addWidget(self.count); v.addLayout(top)
        body = hbox(s=14)
        left = vbox(s=6); self.map = WorldMap(); left.addWidget(self.map, 1)
        self.legend = label("", muted=True); self.legend.setTextFormat(Qt.TextFormat.RichText); self.legend.setWordWrap(True); left.addWidget(self.legend)
        body.addLayout(left, 3)
        self.table = W.QTableWidget(0, 4); self.table.setHorizontalHeaderLabels([tr(x) for x in ("Call sign", "Network", "Country", "Last seen")])
        self.table.verticalHeader().setVisible(False); self.table.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True); tidy_table(self.table); body.addWidget(self.table, 2)
        v.addLayout(body, 1)
        self.net.currentIndexChanged.connect(lambda _: self.refresh())
        self.cty.activated.connect(self._country_chosen)
        self.map.country_clicked.connect(self.choose_country); self.map.station_clicked.connect(self._station_clicked)
        self.table.cellClicked.connect(self._row_clicked)
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
        for n in getattr(getattr(self.ctx, "asl_nodes", None), "nodes", []) or []:          # AllStarLink nodes: the call sign tells the country
            call = (n.get("call") or "").strip()
            key = ("AllStar", call or str(n.get("node")))
            country = countries.of_callsign(call) if call else ""
            if not country or key in seen: continue
            seen.add(key); out.append(dict(call=call, net="AllStar", country=country, seen=None, source="allstar", name=(n.get("desc") or "").strip()[:60]))
        for e in getattr(getattr(self.ctx, "hosts", None), "entries", []) or []:          # the servers / reflectors of the downloaded worldwide lists, where the list itself gives the country
            if e.get("proto") == "TG" or not e.get("country"): continue
            key = (e["net"], e["id"])
            if key in seen: continue
            seen.add(key); out.append(dict(call=e["id"], net=e["net"], country=e["country"], seen=None, source="server"))
        return out

    # ---- choosing a country: the Country box, a click on a circle, or a row of the table ----
    def choose_country(self, name: str):
        i = self.cty.findData((name or "").lower())
        if i < 0: return                                         # not a country of the list (e.g. a dot without a country): nothing changes
        self.cty.setCurrentIndex(i); self._country_chosen()

    def _country_chosen(self, *_):
        key = self.cty.currentData() or ""
        self.map.selected = key
        if key: self.map.focus(key)
        else: self.map.reset_view()
        self.refresh()

    def follow_selected(self):
        """The map follows the station chosen in a radio page: it zooms to that station's country (the country the lists themselves give for it)."""
        t = getattr(self.ctx, "selected", None)
        if t is None: return
        country = ""
        if t.net == "EchoLink":
            country = next((x.get("country", "") for x in (getattr(self.ctx, "el_stations", []) or []) if x["id"] == t.id), "")
        elif t.net in ("DMR", "NXDN", "P25"): country = countries.of_talkgroup(t.id)
        if not country:
            country = next((e.get("country", "") for e in (getattr(getattr(self.ctx, "hosts", None), "entries", []) or []) if e["net"] == t.net and e["id"] == t.id), "")
        if not country: country = countries.of_callsign(t.id)
        self.map.hl = (t.net, t.id)
        self.refresh()
        if country: self.choose_country(country)

    def _station_clicked(self, s):
        """A dot of the opened country was clicked: its row is selected in the table and the dot is pointed out."""
        self.map.hl = (s["net"], s["call"]); self.map.update()
        for i in range(self.table.rowCount()):
            a, b = self.table.item(i, 0), self.table.item(i, 1)
            if a and b and a.text() == s["call"] and b.text() == s["net"]: self.table.selectRow(i); self.table.scrollToItem(a); break

    def _row_clicked(self, row, _col):
        a, b, it = self.table.item(row, 0), self.table.item(row, 1), self.table.item(row, 2)
        if a and b: self.map.hl = (b.text(), a.text())
        if it and it.text(): self.choose_country(it.text())
        self.map.update()

    def refresh(self):
        choice = self.net.currentText()
        st = [s for s in self._stations() if choice == "All networks" or s["net"] == choice]
        # the Country box lists the countries that have stations (with their number); the chosen one stays chosen
        n: dict = {}
        for s in st:
            if s.get("country"): n[s["country"]] = n.get(s["country"], 0) + 1
        cur = self.cty.currentData() or ""
        want = [("", tr(self.ALL))] + [(c.lower(), f"{c} ({k})") for c, k in sorted(n.items(), key=lambda kv: kv[0])]
        have = [(self.cty.itemData(i), self.cty.itemText(i)) for i in range(self.cty.count())]
        if want != have:
            self.cty.blockSignals(True); self.cty.clear()
            for d, t in want: self.cty.addItem(t, d)
            i = self.cty.findData(cur); self.cty.setCurrentIndex(i if i >= 0 else 0); self.cty.blockSignals(False)
        cur = self.cty.currentData() or ""
        self.map.selected = cur
        shown = [s for s in st if not cur or (s.get("country") or "").lower() == cur]
        self.map.set_stations(shown)
        unplaced = sum(1 for s in shown if not s.get("pos") and not centre_of(s.get("country") or ""))
        ncty = len({s['country'] for s in shown if s.get('country')})
        self.count.setText(f"{len(shown)} stations · {ncty} countries" + (f" · {unplaced} not on the map (country unknown)" if unplaced else ""))
        self.sub.setText("Scroll to zoom · drag to move · double-click zooms in · the buttons at the top right of the map zoom or show the whole world. "
                         "A circle sits at the centre of a country and its number is how many stations are there (hover it to see who). Click it and the country opens: every station is its own dot "
                         "(hover for details, click to find it in the table). Inside an opened country only the country is known, so the dots are spread out to be seen separately, not at their real places; "
                         "a dot with a known grid square is at its real place.")
        cnt: dict = {}
        for s in shown: cnt[s["net"]] = cnt.get(s["net"], 0) + 1
        self.legend.setText("&nbsp;&nbsp;".join(f"<span style='color:{NET_COLOR.get(k, C['accent'])};font-size:15px'>●</span> {k} {v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
        self.table.setHorizontalHeaderLabels([tr(x) for x in ("Call sign", "Network", "Country", "Last seen")])
        self.table.setRowCount(len(shown))
        for i, s in enumerate(shown):
            seen = s["seen"].strftime("%H:%M:%S") + " UTC" if s.get("seen") else ("online" + (" · " + s["grid"] if s.get("grid") else "") if s["source"] == "online" else ("directory" if s["source"] == "directory" else ("server list" if s["source"] == "server" else "")))
            for j, val in enumerate([s["call"], s["net"], s["country"], seen]):
                self.table.setItem(i, j, W.QTableWidgetItem(val))
