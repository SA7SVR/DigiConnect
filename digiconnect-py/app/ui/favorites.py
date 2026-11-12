"""My favorites: card grid with filters, listening mode, display options, DTMF, colour legend."""
from ..qt import QtWidgets as W, QtCore, Qt, Signal
from ..rules import Target, ListenMode, CardState, valid_favorite_name, valid_dtmf
from ..theme import NET_COLOR, C
from ..i18n import tr
from .widgets import *


class Card(W.QFrame):
    clicked = Signal(object)
    rename = Signal(object)

    def __init__(self, fav, names_only):
        super().__init__(); self.setObjectName("card"); self.fav = fav; self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(70 if names_only else 160); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        v = vbox(self, m=(14, 10, 12, 10), s=4)
        top = hbox(); net = label(fav["net"], net=fav["net"])
        star = label("★", tone="amber"); self.badge = label(""); self.badge.setVisible(False); self.badge.setStyleSheet("font-weight:700;")
        top.addWidget(net); top.addStretch(); top.addWidget(self.badge); top.addWidget(star); v.addLayout(top)
        self.name = label(fav["name"]); self.name.setStyleSheet("font-size:15px;font-weight:700;"); self.name.setWordWrap(True); v.addWidget(self.name)
        if not names_only:
            v.addWidget(label(f"{fav['id']} · {'YSF' if fav['net'] == 'C4FM' else fav['net']}", muted=True))
            v.addWidget(label("•  Activity unavailable", muted=True)); v.addStretch()
            self.tx = label("Transmit disconnected", muted=True); b = hbox(); b.addWidget(self.tx); b.addStretch()
            self.edit = button("", "rail", "pencil"); self.edit.setFixedSize(26, 26); self.edit.clicked.connect(lambda: self.rename.emit(self.fav)); b.addWidget(self.edit)
            v.addLayout(b)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton: self.rename.emit(self.fav)
        else: self.clicked.emit(self.fav)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F2: self.rename.emit(self.fav)
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self.clicked.emit(self.fav)
        else: super().keyPressEvent(e)


class Favorites(W.QWidget):
    def __init__(self, ctx, on_new_qso):
        super().__init__(); self.ctx = ctx; self.filter = "all"
        v = vbox(self, s=12)
        self.nq = button("New QSO", "", "plus"); self.add = button("☆ Add favorite", "primary")   # placed in the page head by MainWindow
        tb = FlowLayout(hspace=8, vspace=8); self.search = W.QLineEdit(); self.search.setPlaceholderText("Search favorites…"); self.search.setFixedWidth(280)
        tb.addWidget(self.search); self.fb = {}
        for k, txt in (("all", "All"), ("active", "Active"), ("conn", "Connections")):
            b = button(txt, "seg", checkable=True); b.clicked.connect(lambda _, k=k: self._filter(k)); tb.addWidget(b); self.fb[k] = b
        self.fb["all"].setChecked(True); self.refresh_b = button("Refresh"); tb.addWidget(self.refresh_b)
        self.single = button("Single listening", "seg", checkable=True); self.multi = button("Multiple listening", "seg", checkable=True)
        self.display = button("Display"); self.dtmf = button("DTMF", "", "grid")
        for b in (self.single, self.multi, self.display, self.dtmf): tb.addWidget(b)
        v.addLayout(tb)
        self.scroll = W.QScrollArea(); self.scroll.setWidgetResizable(True); self.host = W.QWidget(); self.grid = W.QGridLayout(self.host)
        self.grid.setSpacing(12); self.grid.setAlignment(Qt.AlignmentFlag.AlignTop); self.host.setObjectName('scrollinner'); self.host.setStyleSheet('QWidget#scrollinner{background:transparent;}'); self.scroll.setWidget(self.host); v.addWidget(self.scroll, 1)
        self.empty = label("No favorites yet. Use the star in a station directory or press Add favorite.", muted=True); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        leg = hbox(s=18)
        self.legend = []
        for key, txt in (("green", "Traffic detected"), ("accent", "Selection"), ("pink", "Listening enabled"), ("amber", "Receiving audio"), ("muted", "Connections")):
            d = label("", muted=True); d.setTextFormat(Qt.TextFormat.RichText); self.legend.append((d, key, txt)); leg.addWidget(d)
        self.restyle()
        leg.addStretch(); self.updated = label("", muted=True); leg.addWidget(self.updated); v.addLayout(leg)
        self.search.textChanged.connect(self.rebuild); self.refresh_b.clicked.connect(self.rebuild)
        self.single.clicked.connect(lambda: ctx.set_mode(ListenMode.SINGLE)); self.multi.clicked.connect(lambda: ctx.set_mode(ListenMode.MULTIPLE))
        self.display.clicked.connect(self._display); self.dtmf.clicked.connect(self._dtmf); self.add.clicked.connect(self._add)
        ctx.changed.connect(self.refresh_state); self.rebuild()

    def restyle(self):
        for d, key, txt in self.legend: d.setText(f"<span style='color:{C[key]}'>●</span> {tr(txt)}")

    def _filter(self, k):
        self.filter = k
        for kk, b in self.fb.items(): b.setChecked(kk == k)
        self.rebuild()

    def _display(self):
        s = self.ctx.store.settings
        s["fav_view"] = "Names only" if s["fav_view"] == "Full cards" else "Full cards"; self.ctx.store.save_settings(); self.rebuild()

    def _add(self):
        self.ctx.toast.emit("Select a station in a network tab and press ☆ Add favorite (or use Manual entry).")

    def _dtmf(self):
        r = self.ctx.rules; at = self.ctx.dtmf_target()
        if at is not None:
            s, ok = W.QInputDialog.getText(self, "DTMF", tr("Node {}\nSequence (0-9 A-D * #, up to 32):").format(at.id))
            if ok: self.ctx.send_dtmf(s, at)
            return
        if not (r.tx_connected and r.tx_target and r.tx_target.net == "EchoLink"):
            self.ctx.toast.emit("DTMF is sent to the connected EchoLink peer. Sign in and enable Connect (TX) on that peer first."); return
        s, ok = W.QInputDialog.getText(self, "DTMF", tr("Peer {}\nSequence (0-9 A-D * #, up to 32):").format(r.tx_target.id))
        if ok and not valid_dtmf(s.upper()): self.ctx.toast.emit("DTMF accepts 1 to 32 characters from 0-9, A-D, * and #.")

    def _rename(self, fav):
        txt, ok = W.QInputDialog.getText(self, tr("Rename favorite"), tr("Display name (1–80 characters):"), text=fav["name"])
        if ok:
            if not valid_favorite_name(txt.strip()): self.ctx.toast.emit("A favorite name must be 1 to 80 characters."); return
            fav["name"] = txt.strip(); self.ctx.store.save_favorites(); self.rebuild()

    def _click(self, fav):
        t = Target(fav["net"], fav["id"], fav["name"]); self.ctx.select(t)
        if not self.ctx.rules.is_listening(t): self.ctx.toggle_listen()   # one click starts listening
        else: self.ctx.rules.listen(t); self.ctx.changed.emit()          # already listened: focus, no duplicate

    def rebuild(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None and w is not self.empty:
                w.hide(); w.setParent(None); w.deleteLater()
        favs = self.ctx.store.favorites; q = self.search.text().strip().lower(); r = self.ctx.rules
        names_only = self.ctx.store.settings["fav_view"] == "Names only"
        shown = [f for f in favs if q in (f["name"] + f["id"] + f["net"]).lower()]
        if self.filter == "conn": shown = [f for f in shown if r.tx_connected and r.tx_target == Target(f["net"], f["id"])]
        if self.filter == "active": shown = [f for f in shown if r.is_listening(Target(f["net"], f["id"]))]
        self.cards = []
        cols = 4 if not names_only else 5
        for i, f in enumerate(shown):
            c = Card(f, names_only); c.clicked.connect(self._click); c.rename.connect(self._rename)
            self.grid.addWidget(c, i // cols, i % cols); self.cards.append(c)
        for i in range(cols): self.grid.setColumnStretch(i, 1)
        self.grid.setRowStretch(len(shown) // cols + 1, 1)
        if not shown: self.grid.addWidget(self.empty, 0, 0, 1, cols)
        self.refresh_state()

    def refresh_state(self):
        r = self.ctx.rules
        self.single.setChecked(r.mode is ListenMode.SINGLE); self.multi.setChecked(r.mode is ListenMode.MULTIPLE)
        for c in getattr(self, "cards", []):
            t = Target(c.fav["net"], c.fav["id"]); rx = next((x for x in r.rx if x.target == t), None)
            c.setProperty("state", r.card_state(rx).value if rx else "neutral")
            st = r.card_state(rx).value if rx else "neutral"           # a text badge too, so the listened stations are seen at a glance
            c.badge.setVisible(rx is not None)
            if rx is not None:
                c.badge.setText("● " + tr({"amber": "Receiving audio", "green": "Listening · traffic"}.get(st, "Listening")))
                c.badge.setStyleSheet(f"font-weight:700;color:{C[{'amber': 'amber', 'green': 'green'}.get(st, 'pink')]};")
            c.setProperty("sel", bool(r.selected == t)); repolish(c)
            if hasattr(c, "tx"): c.tx.setText("Transmit ready" if r.tx_connected and r.tx_target == t else "Transmit disconnected")
        self.updated.setText(tr("Updated {}").format(self.ctx.utc_now().strftime("%H:%M:%S UTC")))
