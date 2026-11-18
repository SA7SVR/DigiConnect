"""My favorites: card grid with filters, listening mode, display options, DTMF, colour legend."""
from ..qt import QtWidgets as W, QtCore, Qt, Signal
from ..rules import Target, ListenMode, CardState, valid_favorite_name, valid_dtmf, id_label
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
            self.act = label("•  Activity unavailable", muted=True); v.addWidget(self.act)
            self.who = label(""); self.who.setWordWrap(True); self.who.setStyleSheet("font-size:15px;font-weight:700;"); self.who.setVisible(False); v.addWidget(self.who)
            self.who2 = label("", muted=True); self.who2.setWordWrap(True); self.who2.setVisible(False); v.addWidget(self.who2)
            self.lvl = LevelBar(); self.lvl.setVisible(False); v.addWidget(self.lvl); v.addStretch()
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


class StationPanel(W.QFrame):
    """Opens beside the cards while something is being listened to: the group, and the station that is talking (or was heard last) with callsign, name, DMR ID and country."""

    def __init__(self, ctx, on_new_qso):
        super().__init__(); self.setObjectName("panel"); self.ctx = ctx; self.on_new_qso = on_new_qso; self.setFixedWidth(300); self.setVisible(False); self.cur = None
        v = vbox(self, m=(16, 12, 16, 10), s=4)
        v.addWidget(label("🎧  LISTENING STATION DETAILS", section=True))
        body = W.QWidget(); body.setObjectName("spbody"); body.setStyleSheet("#spbody{background:transparent;}"); bv = vbox(body, m=(0, 0, 4, 0), s=4)
        scroll = W.QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(W.QFrame.Shape.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea > QWidget > QWidget{background:transparent;}"); scroll.setWidget(body); v.addWidget(scroll, 1)       # many rows (EchoLink) scroll instead of overlapping
        self.state = label(""); self.state.setStyleSheet("font-weight:700;"); bv.addWidget(self.state)
        self.group = label(""); self.group.setWordWrap(True); self.group.setStyleSheet("font-size:15px;font-weight:700;"); bv.addWidget(self.group)
        self.net = label("", muted=True); bv.addWidget(self.net); bv.addSpacing(4)
        self.call = label(""); self.call.setStyleSheet("font-size:30px;font-weight:800;"); self.call.setWordWrap(True); bv.addWidget(self.call)
        self.name = label(""); self.name.setStyleSheet("font-size:16px;font-weight:700;"); self.name.setWordWrap(True); bv.addWidget(self.name); bv.addSpacing(6)
        self.lvl = LevelBar(6); bv.addWidget(self.lvl)
        self.rows = label(""); self.rows.setTextFormat(Qt.TextFormat.RichText); self.rows.setWordWrap(False); bv.addWidget(self.rows)
        self.also = label("", muted=True); self.also.setTextFormat(Qt.TextFormat.RichText); self.also.setWordWrap(True); bv.addWidget(self.also)        # EchoLink: who else is connected to the station
        self.src = label("", muted=True); self.src.setWordWrap(True); bv.addWidget(self.src); bv.addStretch()
        self.empty = label("Waiting for a station. Its details appear here as soon as someone talks on the group you are listening to.", muted=True); self.empty.setWordWrap(True); bv.addWidget(self.empty)
        b = hbox(s=8); self.nq = button("New QSO", "primary", "plus"); self.rf = button("Refresh"); b.addWidget(self.nq); b.addWidget(self.rf); b.addStretch(); v.addLayout(b)
        self.nq.clicked.connect(self._qso); self.rf.clicked.connect(self._refresh)

    def _focus(self):
        """(state text, tone, target, station dict or None) - the group talking right now, else the last station heard on a group we listen to, else the selected / first listened group."""
        r = self.ctx.rules
        if not r.rx: return None
        live = [(self.ctx.talking[(x.target.net, x.target.id)], x.target) for x in r.rx if x.reports_traffic and (x.target.net, x.target.id) in self.ctx.talking]
        if live:
            tk, t = max(live, key=lambda p: p[0]["since"]); return "Traffic detected", "green", t, self.ctx.talker(t)
        mine = {(x.target.net, x.target.id): x.target for x in r.rx}
        for h in self.ctx.last_heard:
            t = mine.get((h["net"], h["target"]))
            if t is not None:
                st = dict(src=h["src"], srcid=h.get("srcid") or 0); info = self.ctx.station_info(st["srcid"])
                if info: st.update(name=info["name"], country=info["country"], city=info["city"], state=info["state"])
                return "Last station heard", "pink", t, st
        t = r.selected if r.selected is not None and r.is_listening(r.selected) else r.rx[0].target
        return "Idle", "pink", t, None

    def refresh(self):
        f = self._focus(); self.setVisible(f is not None); self.cur = None
        if f is None: return
        state, tone, t, st = f
        self.state.setStyleSheet(f"font-weight:700;color:{C[tone]};")
        self.group.setText(t.name or t.id); self.net.setText(f"{t.net} · " + (f"TG {t.id}" if t.net == "DMR" else t.id))
        if st is None and t.net == "EchoLink": st, state = dict(src=t.id), "Connected · nobody talking"       # EchoLink: the station we are on is shown even when it is quiet
        self.empty.setVisible(st is None); self.nq.setEnabled(st is not None); self.rf.setEnabled(st is not None and bool(st.get("srcid")))
        self.state.setText(state); self.also.setText("")
        for w in (self.call, self.name, self.rows, self.src): w.setVisible(st is not None)
        self.lvl.setVisible(st is not None and state == "Traffic detected")
        if st is None: return
        self.cur = st; self.call.setText(st["src"]); self.call.setStyleSheet(f"font-size:30px;font-weight:800;color:{C[tone]};"); self.name.setText(st.get("name") or "")
        rows = []
        if t.net == "EchoLink":
            from .. import countries
            el = self.ctx.el_info(t.id) or {}; me = (self.ctx.store.settings.get("echolink_call") or self.ctx.store.settings.get("callsign") or "").upper()
            kind = tr({"conference": "Conference", "repeater": "Repeater", "link": "Link", "station": "Station"}.get(el.get("kind", ""), "Station"))
            parts = el.get("sub", "").split(" · "); place = parts[1] if len(parts) > 1 and not parts[1].startswith("Node") else ""
            node = next((x[5:] for x in parts if x.startswith("Node ")), "")
            self.net.setText("EchoLink")                                          # the station's call sign is the title above: not repeated
            rows.append((tr("Station"), kind + (f" · {place}" if place else "")))
            if node: rows.append((tr("Node"), node + (" · " + tr("busy") if el.get("status") == "BUSY" else "")))
            st = dict(st, country=st.get("country") or el.get("country") or countries.of_callsign(st["src"]))
            tx = self.ctx.rules.tx_connected and self.ctx.rules.tx_target == t
            rows.append((tr("You"), f"{me or '—'} · " + (tr("listening and transmitting") if tx else tr("listening"))))
            calls = self.ctx.el_nodes.get(t.id.upper(), {}).get("calls", [])
            if calls: self.also.setText(tr("Also connected here") + f" ({len(calls)}): <b>" + ", ".join(calls[:6]) + "</b>" + (f" … +{len(calls) - 6}" if len(calls) > 6 else ""))
        if st.get("srcid"): rows.append((tr(id_label(t.net)), str(st["srcid"])))
        if st.get("country"): rows.append((tr("Country"), st["country"]))
        place = ", ".join(x for x in (st.get("city"), st.get("state")) if x)
        if place: rows.append((tr("City"), place))
        self.rows.setText("<table cellspacing='4'>" + "".join(f"<tr><td style='color:{C['muted']}'>{k}&nbsp;&nbsp;</td><td><b>{v}</b></td></tr>" for k, v in rows) + "</table>"); self.rows.setMinimumHeight(28 * len(rows) + 6)
        if st.get("name") or st.get("country"): self.src.setText(tr("Source:") + " RadioID")
        elif t.net == "DMR" and st.get("srcid"): self.src.setText(tr("Not found in RadioID yet (or no internet): only the DMR ID is shown. Nothing is invented."))
        else: self.src.setText("")

    def _refresh(self):
        c = self.cur
        if c and c.get("srcid"):
            self.ctx.callbook.mem.pop(int(c["srcid"]), None); self.ctx._ask_station(int(c["srcid"]))

    def _qso(self):
        c = self.cur
        if not c: return
        f = self._focus(); t = f[2] if f else None
        self.ctx.qso_prefill = dict(callsign=c["src"] if not c["src"].isdigit() else "", name=c.get("name", ""), country=c.get("country", ""),
                                    qth=", ".join(x for x in (c.get("city"), c.get("state")) if x), net=t.net if t else "", dest=t.id if t else "")
        self.on_new_qso()


class Favorites(W.QWidget):
    def __init__(self, ctx, on_new_qso):
        super().__init__(); self.ctx = ctx; self.filter = "all"
        outer = hbox(self, s=14); left = W.QWidget(); outer.addWidget(left, 1)
        self.side = StationPanel(ctx, on_new_qso); outer.addWidget(self.side)
        v = vbox(left, s=12)
        self.nq = button("New QSO", "", "plus"); self.add = button("☆ Add favorite", "primary")   # placed in the page head by MainWindow
        tb = FlowLayout(hspace=8, vspace=8); self.search = W.QLineEdit(); self.search.setPlaceholderText("Search favorites…"); self.search.setFixedWidth(280)
        tb.addWidget(self.search); self.fb = {}
        for k, txt in (("all", "All"), ("active", "Active"), ("conn", "Connections")):
            b = button(txt, "seg", checkable=True); b.clicked.connect(lambda _, k=k: self._filter(k)); tb.addWidget(b); self.fb[k] = b
        self.fb["all"].setChecked(True); self.refresh_b = button("Refresh"); tb.addWidget(self.refresh_b)
        self.single = button("Single listening", "seg", checkable=True); self.multi = button("Multiple listening", "seg", checkable=True)
        self.display = button("Display"); self.dtmf = button("DTMF", "", "grid", checkable=True)
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
        self._lv = QtCore.QTimer(self); self._lv.setInterval(90); self._lv.timeout.connect(self._levels); self._lv.start()

    def _levels(self):
        """The received audio moves a thin bar on the station that is talking (not on the microphone: that one moves only when I speak)."""
        try: lv = float(self.ctx.engine.rx_level()) if not self.ctx.rules.ptt else 0.0
        except Exception: lv = 0.0
        for c in getattr(self, "cards", []):
            if hasattr(c, "lvl") and not c.lvl.isHidden(): c.lvl.set_level(lv)
        if not self.side.lvl.isHidden(): self.side.lvl.set_level(lv)

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
        """The DTMF keypad opens over the cards (a second press closes it)."""
        if getattr(self, "pad", None) is None:
            from .dtmfpad import DtmfPad
            self.pad = DtmfPad(self.ctx, self.window()); self.pad.closed.connect(lambda: self.dtmf.setChecked(False))
        if self.pad.isVisible(): self.pad.close_pad(); return
        self.dtmf.setChecked(True); self.pad.refresh(); self.pad.adjustSize()
        top = self.window(); pos = self.dtmf.mapTo(top, QtCore.QPoint(0, self.dtmf.height() + 6))      # over the whole window, so it is never cut off by the page
        self.pad.setParent(top); self.pad.adjustSize()
        if self.pad.moved: self.pad.place(self.pad.pos())                     # the user has put it somewhere: it opens there again
        else: self.pad.move(max(0, min(pos.x() - 40, top.width() - self.pad.width() - 8)), max(0, min(pos.y(), top.height() - self.pad.height() - 8)))
        self.pad.show(); self.pad.raise_(); self.pad.setFocus()

    def _rename(self, fav):
        txt, ok = W.QInputDialog.getText(self, tr("Rename favorite"), tr("Display name (1–80 characters):"), text=fav["name"])
        if ok:
            if not valid_favorite_name(txt.strip()): self.ctx.toast.emit("A favorite name must be 1 to 80 characters."); return
            fav["name"] = txt.strip(); self.ctx.store.save_favorites(); self.rebuild()

    def _click(self, fav):
        t = Target(fav["net"], fav["id"], fav["name"]); self.ctx.select(t)
        self.ctx.toggle_listen()                                          # first click starts listening, second click on the same card stops it

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
            closed = not self.ctx.policy.allows(t.net)
            if bool(c.property("closed")) != closed: c.setProperty("closed", closed); repolish(c)
            tk = self.ctx.talker(t) if rx is not None and rx.reports_traffic else None
            if hasattr(c, "act"):
                c.badge.setVisible(False)                       # the full card says it in its own line instead of the corner text
                audible = rx is not None and st == "amber"
                if rx is None: c.act.setText("•  Activity unavailable"); c.act.setStyleSheet("")
                elif tk: c.act.setText("●  " + tr("Receiving audio" if audible else "Traffic detected")); c.act.setStyleSheet(f"font-weight:700;color:{C['amber' if audible else 'green']};")
                else: c.act.setText("●  " + tr("Idle")); c.act.setStyleSheet(f"font-weight:700;font-size:14px;color:{C['pink']};")
                c.who.setVisible(bool(tk)); c.lvl.setVisible(bool(tk)); c.who2.setVisible(bool(tk and (tk.get("name") or tk.get("country"))))
                if tk:
                    c.who.setText(tk["src"]); c.who2.setText(" · ".join(x for x in (tk.get("name"), tk.get("country")) if x))
            if hasattr(c, "tx"):
                c.tx.setText("Mode closed" if closed else "Transmit ready" if r.tx_connected and r.tx_target == t else "Receive only" if rx is not None else "Transmit disconnected")
        self.side.refresh()
        self.updated.setText(tr("Updated {}").format(self.ctx.utc_now().strftime("%H:%M:%S UTC")))
