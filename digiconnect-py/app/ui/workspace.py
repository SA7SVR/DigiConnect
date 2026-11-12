"""Radio workspace page for one network: directory | selected station | last heard."""
from ..qt import QtWidgets as W, QtCore, Qt
from ..rules import Target, valid_dmr_tg
from .. import i18n
from ..i18n import tr
from ..theme import NET_COLOR, C
from .. import directory
from .widgets import *
from .controls import TxControls
from .audioblock import AudioBlock

PAGE = 100


def valid_node_text(t): from ..allstar import valid_node; return valid_node(t)
def valid_user_text(t): from ..allstar import valid_user; return valid_user(t)


class Workspace(W.QWidget):
    def __init__(self, ctx, net, on_new_qso):
        super().__init__(); self.ctx, self.net = ctx, net; self.page = 0; self.show_favs = False
        self.entries = directory.entries(net, ctx.hosts, ctx.asl_nodes)
        root = hbox(self, s=14)
        # --- left: directory
        left = panel(); lv = vbox(left, m=(14, 14, 14, 10), s=10)
        top = hbox(s=6)
        self.b_cat = button("TG catalogue" if net == "DMR" else "Station directory", "seg", checkable=True); self.b_fav = button("My favorites", "seg", checkable=True)
        self.b_cat.setChecked(True); self.b_cat.clicked.connect(lambda: self._mode(False)); self.b_fav.clicked.connect(lambda: self._mode(True))
        self.refresh_btn = button("Refresh"); top.addWidget(self.b_cat); top.addWidget(self.b_fav); top.addStretch(); top.addWidget(self.refresh_btn)
        self.search = W.QLineEdit(); self.search.setPlaceholderText("Search TG, name or callsign…" if net in ("DMR", "NXDN", "P25") else ("Search node number, callsign or description…" if net == "AllStar" else "Search name or callsign…"))
        self.country = W.QComboBox(); self.country.addItems([tr("All countries")]); i18n.combo_item(self.country, 0, "All countries")
        self.module = W.QComboBox(); self.module.addItems([tr("Default module")] + [chr(c) for c in range(65, 91)]); i18n.combo_item(self.module, 0, "Default module"); self.module.setVisible(net in ("D-Star", "M17"))
        self.module.setToolTip("Reflector module to link to (REF/XRF default C, DCS/XLX default A)")
        self.country.setVisible(net != "AllStar")
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
        if net == "AllStar":
            note = panel("note"); nv = vbox(note, m=(12, 10, 12, 10))
            nv.addWidget(label("Sign in with your own AllStarLink portal account, then pick a node. Experimental: only nodes that accept AllStarLink app connections can be reached.")); note.findChildren(W.QLabel)[0].setWordWrap(True)
            mv.addWidget(note)
            g = W.QGridLayout(); self.asl_user = W.QLineEdit(ctx.store.settings.get("asl_user") or ctx.store.settings.get("callsign", ""))
            self.asl_pw = W.QLineEdit(); self.asl_pw.setEchoMode(W.QLineEdit.EchoMode.Password); self.asl_pw.setText(ctx.asl_password); self.asl_rem = checkbox("Remember on this computer (enter it only once)"); self.asl_rem.setChecked(bool(ctx.store.settings.get("asl_remember", True)))
            g.addWidget(field("AllStarLink username (callsign)", self.asl_user), 0, 0); g.addWidget(field("AllStarLink password", self.asl_pw), 0, 1); mv.addLayout(g)
            mv.addWidget(self.asl_rem); self.asl_note = label("When ticked, the password is kept in this program's settings file on this computer (not encrypted). Untick it to keep it only in memory.", muted=True); self.asl_note.setWordWrap(True); mv.addWidget(self.asl_note)
            self.asl_user.textChanged.connect(self._asl_login); self.asl_pw.textChanged.connect(self._asl_login); self.asl_rem.toggled.connect(self._asl_login)
        self.srvcard = panel("tx"); sv = vbox(self.srvcard, m=(12, 8, 12, 10), s=4)
        sv.addWidget(label("Server used for this station", muted=True))
        self.srv_host = W.QLineEdit(); self.srv_port = W.QLineEdit(); self.srv_port.setMaximumWidth(110)
        self.srv_host.setPlaceholderText("host name or IP address"); self.srv_port.setPlaceholderText("port")
        hr = hbox(s=6); hr.addWidget(field("Server (host / IP)", self.srv_host), 1); hr.addWidget(field("Port", self.srv_port)); sv.addLayout(hr)
        self.srv_src = label("", muted=True); self.srv_src.setWordWrap(True); sv.addWidget(self.srv_src)
        br = FlowLayout(hspace=6, vspace=6); self.srv_save = button("Use this address"); self.srv_reset = button("Back to the list value"); br.addWidget(self.srv_save); br.addWidget(self.srv_reset)
        self.choose = button("Choose DMR server"); self.choose.setVisible(net == "DMR"); br.addWidget(self.choose); sv.addLayout(br)
        if net == "DMR":
            self.dm_pw = W.QLineEdit(); self.dm_pw.setEchoMode(W.QLineEdit.EchoMode.Password); self.dm_pw.setText(ctx.dmr_password)
            sv.addWidget(field("Password (your BrandMeister hotspot password)", self.dm_pw))
            self.dm_rem = checkbox("Remember on this computer (enter it only once)"); self.dm_rem.setChecked(bool(ctx.store.settings.get("remember_pw", True))); sv.addWidget(self.dm_rem)
            self.dm_note = label("Needed to connect to a DMR master. When ticked, it is kept in this program's settings file on this computer (not encrypted).", muted=True); self.dm_note.setWordWrap(True); sv.addWidget(self.dm_note)
            self.dm_pw.textChanged.connect(lambda: ctx.set_dmr_password(self.dm_pw.text(), self.dm_rem.isChecked())); self.dm_rem.toggled.connect(lambda: ctx.set_dmr_password(self.dm_pw.text(), self.dm_rem.isChecked()))
        self.txname = label(""); self.txname.setVisible(False)
        mv.addWidget(self.srvcard)
        self.addfav = button("☆  Add favorite"); mv.addWidget(self.addfav, 0, Qt.AlignmentFlag.AlignLeft)
        self.dtmf = button("DTMF", "", "grid"); self.dtmf.setVisible(net == "AllStar"); self.dtmf.setToolTip("Send DTMF digits to the connected AllStarLink node (control codes of the node)")
        mv.addWidget(self.dtmf, 0, Qt.AlignmentFlag.AlignLeft); self.dtmf.clicked.connect(self._dtmf)
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
        self.audio = AudioBlock(ctx); mv.addWidget(self.audio)
        self.rxvol = W.QSlider(Qt.Orientation.Horizontal); self.rxvol.setRange(0, 100); self.rxvol.setValue(int(ctx.rules.net_volume[net] * 100))
        vr = hbox(); vr.addWidget(label("RX volume", muted=True)); vr.addWidget(self.rxvol, 1); mv.addLayout(vr)
        self.hint = label({"DMR": "Connects to the DMR master set in Settings › Radio networks (DMR ID required). Listen and Connect (TX) are separate.",
                           "EchoLink": "Listening requires a validated EchoLink account. Enable TX only to participate.",
                           "AllStar": "Connects to the chosen AllStarLink node with your portal account. Listen and Connect (TX) are separate; the node must allow app connections."}.get(net, "Listen links for reception only. Connect (TX) is separate and must be enabled to transmit."), muted=True)
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
        self.manual.clicked.connect(self._manual); self.refresh_btn.clicked.connect(lambda: ((ctx.refresh_asl(True) if net == "AllStar" else ctx.refresh_hosts(True)), self.fill()))
        self.rxvol.valueChanged.connect(lambda v: ctx.rules.net_volume.__setitem__(net, v / 100))
        self.choose.clicked.connect(self._choose_master); ctx.hosts_changed.connect(self._hosts_loaded)
        self.srv_save.clicked.connect(self._srv_save); self.srv_reset.clicked.connect(self._srv_reset); self._srv_key = None
        ctx.changed.connect(self.refresh); self._hosts_loaded()

    def _dtmf(self):
        t = self.ctx.dtmf_target()
        if t is None: self.ctx.toast.emit("DTMF is sent to the connected AllStarLink node. Select the node and connect first."); return
        s, ok = W.QInputDialog.getText(self, "DTMF", tr("Node {}\nSequence (0-9 A-D * #, up to 32):").format(t.id))
        if ok: self.ctx.send_dtmf(s, t)

    def _asl_login(self):
        self.ctx.set_asl_login(self.asl_user.text(), self.asl_pw.text(), self.asl_rem.isChecked())

    def _hosts_loaded(self):
        self.entries = directory.entries(self.net, self.ctx.hosts, self.ctx.asl_nodes)
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
            st.settings["dmr_server"], st.settings["dmr_port"] = m["host"], int(m["port"]); st.save_settings(); self._srv_show(None, True)
            self.ctx.toast.emit(f"DMR master set to {m['name']} ({m['host']}:{m['port']})"); self.ctx.changed.emit()

    # ---- server address of the selected station (shown from the list, editable, and really used by the engine) ----------
    def _srv_target(self):
        t = self.ctx.selected
        return t if (t is not None and t.net == self.net) else (Target("DMR", "0", "") if self.net == "DMR" else None)

    def _srv_show(self, t, force=False):
        t = t or self._srv_target()
        key = (t.net, t.id) if t else None
        stamp = (key, self.ctx.store.settings.get("dmr_server"), self.ctx.store.settings.get("dmr_port"), len(self.ctx.hosts.entries), len(self.ctx.servers.user))
        if not force and stamp == getattr(self, "_srv_stamp", None): return          # do not overwrite what the user is typing
        self._srv_stamp = stamp
        if t is None:
            self.srv_host.clear(); self.srv_port.clear(); self.srv_src.setText("Select a station to see its server address."); self._srv_en(False); return
        ep, src = self.ctx.servers.info(t)
        self.srv_host.setText(ep["host"] if ep else ""); self.srv_port.setText(str(ep["port"]) if ep else "")
        self.srv_src.setText({"your address": "Source: your own address (used instead of the list).", "built in": "Source: built into DigiConnect.",
                              "DMR master (Settings)": "Source: the DMR master you chose. Press «Choose DMR server» to change it.",
                              "worldwide list": "Source: the downloaded worldwide server list.",
                              "AllStarLink DNS": "Source: AllStarLink node address (looked up when you connect)."}.get(src, "Not in the downloaded lists yet — press Refresh, or type the address here."))
        self._srv_en(True)
        self.srv_reset.setEnabled(src == "your address")

    def _srv_en(self, on):
        for w in (self.srv_host, self.srv_port, self.srv_save): w.setEnabled(on)
        if not on: self.srv_reset.setEnabled(False)

    def _srv_save(self):
        t = self._srv_target()
        if t is None: return
        host, port = self.srv_host.text().strip(), self.srv_port.text().strip()
        if not host or " " in host or (port and not (port.isdigit() and 0 < int(port) < 65536)):
            self.ctx.toast.emit("Enter a host name or IP address, and a port between 1 and 65535."); return
        if t.net == "DMR":
            st = self.ctx.store; st.settings["dmr_server"] = host; st.settings["dmr_port"] = int(port or 62031); st.save_settings()
        elif not self.ctx.servers.remember(t, host + (":" + port if port else "")):
            self.ctx.toast.emit("Enter a host name or IP address, and a port between 1 and 65535."); return
        from .. import diag; diag.log(f"server address set by user for {t.net}:{t.id} -> {host}:{port}")
        self.ctx.toast.emit(f"Server address saved: {host}:{port or 'default port'}. It is used the next time you connect.")
        self._srv_show(t if self.ctx.selected is not None and self.ctx.selected.net == self.net else None, True)

    def _srv_reset(self):
        t = self._srv_target()
        if t is not None and self.ctx.servers.clear(t): self.ctx.toast.emit("The list value is used again.")
        self._srv_show(t, True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._right.setVisible(self.width() >= 960)      # narrow window / drawer open: the "last heard" column steps aside instead of squeezing the others

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
        if q and not self.show_favs and self.net == "AllStar" and valid_node_text(q) and not any(e["id"] == q for e in src):
            src = [dict(net="AllStar", id=q, name=f"AllStar node {q}", sub=f"Node {q} · typed number", activity="", proto="IAX", country="")] + src
        res = [e for e in src if q in (e["name"] + " " + e["id"] + " " + e["sub"] + " " + e.get("country", "")).lower()] if q else src
        if q and not self.show_favs and self.net in ("DMR", "NXDN", "P25") and valid_dmr_tg(q) and not any(e["id"] == q for e in res):
            # the catalogue never holds every talkgroup: a typed number can always be used
            res = [dict(net=self.net, id=q, name=f"{self.net} TG {q}", sub=f"TG {q} · typed number", activity="Typed talkgroup number")] + res
        return res

    def fill(self):
        ents = self.visible_entries(); total = len(ents)
        self.page = min(self.page, max(0, (total - 1) // PAGE))
        chunk = ents[self.page * PAGE:(self.page + 1) * PAGE]
        self.list.blockSignals(True); self.list.clear()
        for e in chunk:
            it = W.QListWidgetItem(); it.setData(Qt.ItemDataRole.UserRole, e)
            it.setText(f"{'★ ' if self.ctx.store.is_fav(e['net'], e['id']) else '☆ '}{tr(e['name'])}\n   {tr(e['sub'])}" + (f"\n   {tr(e['activity'])}" if e.get("activity") else "")); self.list.addItem(it)
        self.list.blockSignals(False)
        src = "BrandMeister" if self.net == "DMR" else self.net
        self.count.setText(f"{src} · {total} entries"); a = self.page * PAGE
        if self.net in ("C4FM", "D-Star", "NXDN", "P25", "M17") and not self.ctx.hosts.for_net(self.net):
            self.count.setText(f"{self.net} · worldwide list not downloaded yet — press Refresh (needs internet)")
        self.pager.setText(f"{a + 1 if total else 0}–{min(total, a + PAGE)} / {total}")
        self.prev.setEnabled(self.page > 0); self.next.setEnabled((self.page + 1) * PAGE < total)
        if self.net == "DMR":
            n_tg = sum(1 for e in self.ctx.hosts.entries if e["proto"] == "TG"); n_ms = len(self.ctx.hosts.dmr_masters())
            if not n_tg or not n_ms:
                why = lambda k: (self.ctx.hosts.status.get(k, "") or "not downloaded yet").replace("failed: ", "")
                bits = ([tr("TG list: {}").format(tr(why('TG')))] if not n_tg else []) + ([tr("DMR master list: {}").format(tr(why('DMR')))] if not n_ms else [])
                self.count.setText(tr("DMR · {} entries — {} — press Refresh").format(total, " · ".join(bits)))
        if self.net == "AllStar":
            self.count.setText(f"AllStarLink · {total} nodes" if self.ctx.asl_nodes.nodes else "AllStarLink · node list not downloaded yet — press Refresh (needs internet), or type a node number")
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
        text, ok = W.QInputDialog.getText(self, tr("Manual entry"), tr("TG number (1–16777215)" if self.net in ("DMR", "NXDN", "P25") else ("AllStarLink node number (digits)" if self.net == "AllStar" else "Identifier (e.g. REF001 C / 00006 / M17-DEU A)")))
        if not ok: return
        text = text.strip()
        if self.net in ("DMR", "NXDN", "P25") and not valid_dmr_tg(text):
            self.ctx.toast.emit("A manual TG must be a positive integer no greater than 16777215."); return
        if not text: return
        if self.net == "AllStar" and not valid_node_text(text):
            self.ctx.toast.emit("An AllStarLink node number has 3 to 8 digits."); return
        self.ctx.store.toggle_fav(self.net, text, f"{self.net} {text}") if not self.ctx.store.is_fav(self.net, text) else None
        self.ctx.select(Target(self.net, text, f"{self.net} {text}")); self.fill(); self.ctx.changed.emit()

    def refresh(self):
        t = self.ctx.selected; mine = t is not None and t.net == self.net
        self.title.setText(t.name if mine else "Select a station")
        self.sub.setText(f"{t.net} · {t.id}" if mine else "Select an entry in the list on the left.")
        self.addfav.setEnabled(mine)
        self.addfav.setText("★  Remove favorite" if mine and self.ctx.store.is_fav(t.net, t.id) else "☆  Add favorite")
        self._srv_show(t if mine else None)
        heard = list(self.ctx.last_heard)                    # every network, newest first (a station heard on C4FM also shows on the DMR page)
        self.lh_empty.setVisible(not heard)
        if heard:
            from .heardpage import html_rows
            self.lh_list.setText(html_rows(heard, C['muted']))
            self.lh_list.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.lh_list.setText("Waiting for data")
