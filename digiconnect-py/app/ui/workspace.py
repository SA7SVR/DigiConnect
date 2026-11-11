"""Radio workspace page for one network: directory | selected station | last heard."""
from ..qt import QtWidgets as W, QtCore, Qt
from ..rules import Target, valid_dmr_tg
from .. import i18n
from ..i18n import tr
from ..theme import NET_COLOR, C
from .. import directory
from .widgets import *
from .controls import TxControls
from ..audio_devices import list_devices

PAGE = 100


class Workspace(W.QWidget):
    def __init__(self, ctx, net, on_new_qso):
        super().__init__(); self.ctx, self.net = ctx, net; self.page = 0; self.show_favs = False
        self.entries = directory.entries(net, ctx.hosts)
        root = hbox(self, s=14)
        # --- left: directory
        left = panel(); lv = vbox(left, m=(14, 14, 14, 10), s=10)
        top = hbox(s=6)
        self.b_cat = button("TG catalogue" if net == "DMR" else "Station directory", "seg", checkable=True); self.b_fav = button("My favorites", "seg", checkable=True)
        self.b_cat.setChecked(True); self.b_cat.clicked.connect(lambda: self._mode(False)); self.b_fav.clicked.connect(lambda: self._mode(True))
        self.refresh_btn = button("Refresh"); top.addWidget(self.b_cat); top.addWidget(self.b_fav); top.addStretch(); top.addWidget(self.refresh_btn)
        self.search = W.QLineEdit(); self.search.setPlaceholderText("Search TG, name or callsign…" if net in ("DMR", "NXDN", "P25") else "Search name or callsign…")
        self.country = W.QComboBox(); self.country.addItems([tr("All countries")]); i18n.combo_item(self.country, 0, "All countries")
        self.module = W.QComboBox(); self.module.addItems([tr("Default module")] + [chr(c) for c in range(65, 91)]); i18n.combo_item(self.module, 0, "Default module"); self.module.setVisible(net in ("D-Star", "M17"))
        self.module.setToolTip("Reflector module to link to (REF/XRF default C, DCS/XLX default A)")
        self.manual = button("Manual entry"); cr = hbox(s=6); cr.addWidget(self.country, 1); cr.addWidget(self.module); cr.addWidget(self.manual)
        self.count = label("", muted=True); self.count.setWordWrap(True)
        self.list = W.QListWidget(); self.list.setVerticalScrollMode(W.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.prev = button("Previous"); self.next = button("Next"); self.pager = label("", muted=True)
        pr = hbox(); pr.addWidget(self.pager); pr.addStretch(); pr.addWidget(self.prev); pr.addWidget(self.next)
        lv.addLayout(top); lv.addWidget(self.search); lv.addLayout(cr); lv.addWidget(self.count); lv.addWidget(self.list, 1); lv.addLayout(pr)
        # --- middle: selected station
        mid = panel(); _mo = vbox(mid, s=0); _sc = W.QScrollArea(); _sc.setWidgetResizable(True); _sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); _in = W.QWidget(); _in.setObjectName('scrollinner'); _in.setStyleSheet('QWidget#scrollinner{background:transparent;}'); _sc.setWidget(_in); _mo.addWidget(_sc); mv = vbox(_in, m=(16, 16, 16, 12), s=8)
        mv.addWidget(label("Selected station", eyebrow=True)); self.title = label("Select a station"); self.title.setStyleSheet("font-size:20px;font-weight:700;")
        self.sub = label("Select an entry in the list on the left.", muted=True); mv.addWidget(self.title); mv.addWidget(self.sub)
        self.txcard = panel("tx"); tv = vbox(self.txcard, m=(12, 8, 12, 10), s=4)
        tv.addWidget(label("Transmit server (TX)", muted=True)); self.txname = label("No server configured"); self.txname.setStyleSheet("font-weight:700;")
        self.choose = button("Choose DMR server"); tv.addWidget(self.txname); tv.addWidget(self.choose, 0, Qt.AlignmentFlag.AlignLeft)
        self.txcard.setVisible(net == "DMR"); mv.addWidget(self.txcard)
        self.addfav = button("☆  Add favorite"); mv.addWidget(self.addfav, 0, Qt.AlignmentFlag.AlignLeft)
        self.tx = TxControls(ctx, on_new_qso); mv.addWidget(self.tx)
        mv.addWidget(label("AUDIO", section=True))
        if net == "EchoLink":
            note = panel("note"); nv = vbox(note, m=(12, 10, 12, 10)); nv.addWidget(label("Sign in with your validated EchoLink account to load the directory and listen. Transmit remains disabled."))
            mv.addWidget(note)
            g = W.QGridLayout(); self.el_call = W.QLineEdit(ctx.store.settings.get("echolink_call") or ctx.store.settings.get("callsign", ""))
            self.el_pw = W.QLineEdit(); self.el_pw.setEchoMode(W.QLineEdit.EchoMode.Password)
            g.addWidget(field("Callsign", self.el_call), 0, 0); g.addWidget(field("Password", self.el_pw), 0, 1); mv.addLayout(g)
            self.el_rem = checkbox("Remember password"); self.el_rem.setChecked(True); mv.addWidget(self.el_rem)
            self.el_sign = button("Sign in to account", "primary"); mv.addWidget(self.el_sign, 0, Qt.AlignmentFlag.AlignLeft)
            self.el_sign.clicked.connect(lambda: ctx.toast.emit("EchoLink sign-in needs the EchoLink engine (not connected in this build)"))
        self.mic = W.QComboBox(); self.spk = W.QComboBox(); self._devices()
        mv.addWidget(field("Microphone", self.mic)); mv.addWidget(field("Speakers", self.spk))
        self.dev_info = label("", muted=True)
        ar = FlowLayout(hspace=6, vspace=6); self.b_ref = button("Refresh devices"); self.b_tm = button("Test microphone"); self.b_ts = button("Test speakers")
        for b in (self.b_ref, self.b_tm, self.b_ts): ar.addWidget(b)
        mv.addLayout(ar); mv.addWidget(self.dev_info); self.b_ref.clicked.connect(self._devices); self._devices()
        self.rxvol = W.QSlider(Qt.Orientation.Horizontal); self.rxvol.setRange(0, 100); self.rxvol.setValue(int(ctx.rules.net_volume[net] * 100))
        vr = hbox(); vr.addWidget(label("RX volume", muted=True)); vr.addWidget(self.rxvol, 1); mv.addLayout(vr)
        self.hint = label({"DMR": "Connects to the DMR master set in Settings › Radio networks (DMR ID required). Listen and Connect (TX) are separate.",
                           "EchoLink": "Listening requires a validated EchoLink account. Enable TX only to participate."}.get(net, "Listen links for reception only. Connect (TX) is separate and must be enabled to transmit."), muted=True)
        self.hint.setWordWrap(True); mv.addWidget(self.hint); mv.addStretch()
        # --- right: last heard
        right = panel(); rv = vbox(right, m=(16, 16, 16, 12), s=10)
        rv.addWidget(label("Last station heard")); rv.itemAt(0).widget().setStyleSheet("font-weight:700;font-size:14px;")
        self.lh_empty = label("🎧\nStation details will appear on reception."); self.lh_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lh_empty.setProperty("muted", True); rv.addWidget(self.lh_empty); rv.addSpacing(10)
        rv.addWidget(label("LAST HEARD", section=True)); self.lh_list = label("Waiting for data", muted=True); rv.addWidget(self.lh_list); rv.addStretch()
        left.setMinimumWidth(300); mid.setMinimumWidth(350); right.setMinimumWidth(240); self._right = right
        root.addWidget(left, 5); root.addWidget(mid, 5); root.addWidget(right, 4)
        # wiring
        self.search.textChanged.connect(lambda: (setattr(self, "page", 0), self.fill())); self.country.currentIndexChanged.connect(lambda: self.fill())
        self.prev.clicked.connect(lambda: self._page(-1)); self.next.clicked.connect(lambda: self._page(1))
        self.list.currentRowChanged.connect(self._picked); self.addfav.clicked.connect(self._togglefav)
        self.manual.clicked.connect(self._manual); self.refresh_btn.clicked.connect(lambda: (ctx.refresh_hosts(True), self.fill()))
        self.rxvol.valueChanged.connect(lambda v: ctx.rules.net_volume.__setitem__(net, v / 100))
        self.choose.clicked.connect(self._choose_master); ctx.hosts_changed.connect(self._hosts_loaded)
        ctx.changed.connect(self.refresh); self.fill()

    def _hosts_loaded(self):
        self.entries = directory.entries(self.net, self.ctx.hosts)
        cur = self.country.currentText()
        names = sorted({e.get("country", "") for e in self.entries if e.get("country")})
        self.country.blockSignals(True); self.country.clear(); self.country.addItems([tr("All countries")] + names); i18n.combo_item(self.country, 0, "All countries")
        if cur in names: self.country.setCurrentText(cur)
        self.country.blockSignals(False); self.fill()

    def _choose_master(self):
        masters = self.ctx.hosts.dmr_masters()
        if not masters:
            self.ctx.toast.emit("The DMR master list is not downloaded yet — press Refresh (needs internet)."); self.ctx.refresh_hosts(True); return
        dlg = W.QDialog(self); dlg.setWindowTitle(tr("Choose DMR master server")); dlg.resize(560, 520); v = W.QVBoxLayout(dlg)
        q = W.QLineEdit(); q.setPlaceholderText(tr("Search master name, country or host…")); lst = W.QListWidget(); v.addWidget(q); v.addWidget(lst, 1)
        cnt = W.QLabel(); v.addWidget(cnt)
        def fillm():
            t = q.text().strip().lower(); lst.clear(); n = 0
            for m in masters:
                if t and t not in (m["name"] + " " + m["host"] + " " + m.get("country", "")).lower(): continue
                it = W.QListWidgetItem(f"{m['name']}\n   {m['host']}:{m['port']}"); it.setData(Qt.ItemDataRole.UserRole, m); lst.addItem(it); n += 1
            cnt.setText(f"{n} of {len(masters)} masters")
        q.textChanged.connect(fillm); fillm()
        bb = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok | W.QDialogButtonBox.StandardButton.Cancel); v.addWidget(bb)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lst.itemDoubleClicked.connect(lambda *_: dlg.accept())
        if dlg.exec() and lst.currentItem():
            m = lst.currentItem().data(Qt.ItemDataRole.UserRole); st = self.ctx.store
            st.settings["dmr_server"], st.settings["dmr_port"] = m["host"], int(m["port"]); st.save_settings()
            self.ctx.toast.emit(f"DMR master set to {m['name']} ({m['host']}:{m['port']})"); self.ctx.changed.emit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._right.setVisible(self.width() >= 960)      # narrow window / drawer open: the "last heard" column steps aside instead of squeezing the others

    def _devices(self):
        ins, outs, err = list_devices(); st = self.ctx.store.settings
        self.mic.clear(); self.spk.clear(); self.mic.addItems(ins or [tr("(none found)")]); self.spk.addItems(outs or [tr("(none found)")])
        if st.get("mic") in ins: self.mic.setCurrentText(st["mic"])
        if st.get("speakers") in outs: self.spk.setCurrentText(st["speakers"])
        if hasattr(self, "dev_info"): self.dev_info.setText(err or f"{len(ins)} available microphone{'s' if len(ins) != 1 else ''}")

    # ---- directory --------------------------------------------------------
    def _mode(self, favs):
        self.show_favs = favs; self.b_cat.setChecked(not favs); self.b_fav.setChecked(favs); self.page = 0; self.fill()

    def _page(self, d): self.page = max(0, self.page + d); self.fill()

    def visible_entries(self):
        q = self.search.text().strip().lower()
        src = self.entries
        if self.show_favs: src = [e for e in src if self.ctx.store.is_fav(e["net"], e["id"])]
        manual = [e for e in self.ctx.store.favorites if e["net"] == self.net and not any(x["id"] == e["id"] for x in self.entries)]
        if self.show_favs: src = src + [dict(e, sub=e["id"], activity="Activity unavailable") for e in manual]
        c = self.country.currentText()
        if c and self.country.currentIndex() > 0: src = [e for e in src if e.get("country") == c]
        return [e for e in src if q in (e["name"] + " " + e["id"] + " " + e["sub"] + " " + e.get("country", "")).lower()] if q else src

    def fill(self):
        ents = self.visible_entries(); total = len(ents)
        self.page = min(self.page, max(0, (total - 1) // PAGE))
        chunk = ents[self.page * PAGE:(self.page + 1) * PAGE]
        self.list.blockSignals(True); self.list.clear()
        for e in chunk:
            it = W.QListWidgetItem(); it.setData(Qt.ItemDataRole.UserRole, e)
            it.setText(f"{'★ ' if self.ctx.store.is_fav(e['net'], e['id']) else '☆ '}{e['name']}\n   {e['sub']}\n   {e['activity']}"); self.list.addItem(it)
        self.list.blockSignals(False)
        src = "BrandMeister" if self.net == "DMR" else self.net
        self.count.setText(f"{src} · {total} entries"); a = self.page * PAGE
        if self.net in ("C4FM", "D-Star", "NXDN", "P25", "M17") and not self.ctx.hosts.for_net(self.net):
            self.count.setText(f"{self.net} · worldwide list not downloaded yet — press Refresh (needs internet)")
        self.pager.setText(f"{a + 1 if total else 0}–{min(total, a + PAGE)} / {total}")
        self.prev.setEnabled(self.page > 0); self.next.setEnabled((self.page + 1) * PAGE < total)
        if self.net == "EchoLink" and not total: self.count.setText("EchoLink · 0 entries — the directory appears after signing in")
        self.refresh()

    def _picked(self, row):
        it = self.list.item(row)
        if not it: return
        e = it.data(Qt.ItemDataRole.UserRole); self.ctx.last_net = self.net
        id_ = e["id"]
        if self.net in ("D-Star", "M17") and self.module.currentIndex() > 0 and " " in id_ and e.get("proto"): id_ = id_.split()[0] + " " + self.module.currentText()
        self.ctx.select(Target(e["net"], id_, e["name"]))

    def _togglefav(self):
        t = self.ctx.selected
        if t and t.net == self.net: self.ctx.store.toggle_fav(t.net, t.id, t.name); self.fill(); self.ctx.changed.emit()

    def _manual(self):
        text, ok = W.QInputDialog.getText(self, tr("Manual entry"), tr("TG number (1–16777215)" if self.net in ("DMR", "NXDN", "P25") else "Identifier (e.g. REF001 C / 00006 / M17-DEU A)"))
        if not ok: return
        text = text.strip()
        if self.net in ("DMR", "NXDN", "P25") and not valid_dmr_tg(text):
            self.ctx.toast.emit("A manual TG must be a positive integer no greater than 16777215."); return
        if not text: return
        self.ctx.store.toggle_fav(self.net, text, f"{self.net} {text}") if not self.ctx.store.is_fav(self.net, text) else None
        self.ctx.select(Target(self.net, text, f"{self.net} {text}")); self.fill(); self.ctx.changed.emit()

    def refresh(self):
        t = self.ctx.selected; mine = t is not None and t.net == self.net
        self.title.setText(t.name if mine else "Select a station")
        self.sub.setText(f"{t.net} · {t.id}" if mine else "Select an entry in the list on the left.")
        self.addfav.setEnabled(mine)
        self.addfav.setText("★  Remove favorite" if mine and self.ctx.store.is_fav(t.net, t.id) else "☆  Add favorite")
        self.txname.setText(self.ctx.store.settings.get("dmr_server") or "No server configured")
        heard = [h for h in self.ctx.last_heard if h["net"] == self.net]
        self.lh_empty.setVisible(not heard)
        if heard:
            h = heard[0]
            self.lh_list.setText("<br>".join(f"<b>{x['src']}</b> → {x['dst'] or x['target']} <span style='color:{C['muted']}'>{x['ts']:%H:%M:%S} UTC</span>" for x in heard[:12]))
            self.lh_list.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.lh_list.setText("Waiting for data")
