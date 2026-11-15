"""Radio workspace page for one network: directory | selected station | last heard."""
from ..qt import QtWidgets as W, QtCore, Qt
from ..rules import Target, valid_dmr_tg
from .. import i18n
from ..i18n import tr
from ..theme import NET_COLOR, C
from .. import directory, countries
from .widgets import *
from .controls import TxControls
from .audioblock import AudioBlock

PAGE = 100


def valid_node_text(t): from ..allstar import valid_node; return valid_node(t)
def valid_user_text(t): from ..allstar import valid_user; return valid_user(t)


def norm_dstar(text: str) -> str | None:
    """What a person types for a reflector ('ref001c', 'REF001 c', 'xlx307', 'DCS 003 B') -> 'REF001 C'; a missing module gets the usual one (REF/XRF: C, DCS/XLX: A)."""
    import re
    t = re.sub(r"[\s_-]+", "", (text or "").upper())
    m = re.fullmatch(r"(REF|XRF|DCS|XLX)(\d{3})([A-Z]?)", t)
    if not m: return None
    return f"{m.group(1)}{m.group(2)} {m.group(3) or ('C' if m.group(1) in ('REF', 'XRF') else 'A')}"


class Workspace(W.QWidget):
    def __init__(self, ctx, net, on_new_qso):
        super().__init__(); self.ctx, self.net = ctx, net; self.page = 0; self.show_favs = False
        self.entries = directory.entries(net, ctx.hosts, ctx.asl_nodes, ctx.el_stations)
        root = hbox(self, s=14)
        # --- left: directory
        left = panel(); lv = vbox(left, m=(14, 14, 14, 10), s=10)
        top = hbox(s=6)
        self.b_cat = button("TG catalogue" if net == "DMR" else "Station directory", "seg", checkable=True); self.b_fav = button("My favorites", "seg", checkable=True)
        self.b_cat.setChecked(True); self.b_cat.clicked.connect(lambda: self._mode(False)); self.b_fav.clicked.connect(lambda: self._mode(True))
        self.refresh_btn = button("Refresh"); top.addWidget(self.b_cat); top.addWidget(self.b_fav); top.addStretch(); top.addWidget(self.refresh_btn)
        self.search = W.QLineEdit(); self.search.setPlaceholderText("Search TG, name or callsign…" if net in ("DMR", "NXDN", "P25") else ("Search node number, callsign or description…" if net == "AllStar" else "Search name or callsign…"))
        self.country = W.QComboBox(); self.country.addItems([tr("All countries")]); i18n.combo_item(self.country, 0, "All countries")
        first = "All modules" if net == "D-Star" else "Default module"
        self.module = W.QComboBox(); self.module.addItems([tr(first)] + [chr(c) for c in range(65, 91)]); i18n.combo_item(self.module, 0, first); self.module.setVisible(net in ("D-Star", "M17"))
        self.module.setToolTip("D-Star: show only this module of every reflector. M17: module to link to.")
        self.country.setVisible(net != "AllStar")
        self.manual = button("Manual entry"); cr = hbox(s=6); cr.addWidget(self.country, 1); cr.addWidget(self.module); cr.addWidget(self.manual)
        self.count = label("", muted=True); self.count.setWordWrap(True)
        self.list = W.QListWidget(); self.list.setVerticalScrollMode(W.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.prev = button("Previous"); self.next = button("Next"); self.pager = label("", muted=True)
        pr = hbox(); pr.addWidget(self.pager); pr.addStretch(); pr.addWidget(self.prev); pr.addWidget(self.next)
        lv.addLayout(top); lv.addWidget(self.search); lv.addLayout(cr); lv.addWidget(self.count); lv.addWidget(self.list, 1); lv.addLayout(pr)
        # --- middle: selected station
        mid = panel(); _mo = vbox(mid, s=0); _sc = W.QScrollArea(); _sc.setWidgetResizable(True); _sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); _in = W.QWidget(); _in.setObjectName('scrollinner'); _in.setStyleSheet('QWidget#scrollinner{background:transparent;}'); _sc.setWidget(_in); _mo.addWidget(_sc); mv = vbox(_in, m=(16, 16, 16, 12), s=8)
        self._sc = _sc; self.closed_note = panel("note"); _cv = vbox(self.closed_note, m=(12, 10, 12, 10)); self.closed_txt = label(""); self.closed_txt.setWordWrap(True); _cv.addWidget(self.closed_txt); self.closed_note.setVisible(False); _mo.insertWidget(0, self.closed_note)      # shown when the owner's server has closed this mode
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
        self.srv_edit = W.QWidget(); ev = vbox(self.srv_edit, s=4); ev.addWidget(label("Server used for this station", muted=True))
        self.srv_host = W.QLineEdit(); self.srv_port = W.QLineEdit(); self.srv_port.setMaximumWidth(110)
        self.srv_host.setPlaceholderText("host name or IP address"); self.srv_port.setPlaceholderText("port")
        hr = hbox(s=6); hr.addWidget(field("Server (host / IP)", self.srv_host), 1); hr.addWidget(field("Port", self.srv_port)); ev.addLayout(hr)
        self.srv_src = label("", muted=True); self.srv_src.setWordWrap(True); ev.addWidget(self.srv_src)
        br = FlowLayout(hspace=6, vspace=6); self.srv_save = button("Use this address"); self.srv_reset = button("Back to the list value"); br.addWidget(self.srv_save); br.addWidget(self.srv_reset)
        ev.addLayout(br); sv.addWidget(self.srv_edit)
        # DMR page: the transmit server is picked from the downloaded lists (name + address shown, nothing typed here); the other pages keep their address fields
        self.tx_title = label("Transmit server (TX)", muted=True); self.tx_name = label(""); self.tx_name.setStyleSheet("font-weight:700;font-size:15px;"); self.tx_addr = label("", muted=True)
        self.choose = button("Choose DMR server")
        for w_ in (self.tx_title, self.tx_name, self.tx_addr): sv.addWidget(w_)
        sv.addWidget(self.choose, 0, Qt.AlignmentFlag.AlignLeft)
        for w_ in (self.tx_title, self.tx_name, self.tx_addr, self.choose): w_.setVisible(net == "DMR")
        self.srv_edit.setVisible(net != "DMR")
        if net == "DMR":
            self.dm_box = W.QWidget(); dv = vbox(self.dm_box, s=4)
            self.dm_pw = W.QLineEdit(); self.dm_pw.setEchoMode(W.QLineEdit.EchoMode.Password); self.dm_pw.setText(ctx.dmr_password)
            dv.addWidget(field("Password (your BrandMeister hotspot password)", self.dm_pw))
            self.dm_rem = checkbox("Remember on this computer (enter it only once)"); self.dm_rem.setChecked(bool(ctx.store.settings.get("remember_pw", True))); dv.addWidget(self.dm_rem)
            self.dm_note = label("Needed to connect to a DMR master. When ticked, it is kept in this program's settings file on this computer (not encrypted).", muted=True); self.dm_note.setWordWrap(True); dv.addWidget(self.dm_note)
            self.dm_state = label("", muted=True); self.dm_state.setWordWrap(True); dv.addWidget(self.dm_state)
            def pw_changed(*_):
                ctx.set_dmr_password(self.dm_pw.text(), self.dm_rem.isChecked())
                self.dm_state.setText(tr("No password entered yet") if not self.dm_pw.text() else tr("✓ Password saved on this computer") if self.dm_rem.isChecked() else tr('Password kept only until you close the program ("Remember" is off)'))
            self.dm_pw.textChanged.connect(pw_changed); self.dm_rem.toggled.connect(pw_changed); pw_changed()
            sv.addWidget(self.dm_box); self.dm_box.setVisible(False)                 # the password and DMR ID are entered once, in Settings > Radio networks
            self.tx_hint = label("", muted=True); self.tx_hint.setWordWrap(True); sv.addWidget(self.tx_hint)
        self.txname = label(""); self.txname.setVisible(False)
        mv.addWidget(self.srvcard)
        self.addfav = button("☆  Add favorite"); mv.addWidget(self.addfav, 0, Qt.AlignmentFlag.AlignLeft)
        self.dtmf = button("DTMF", "", "grid"); self.dtmf.setVisible(net in ("AllStar", "EchoLink")); self.dtmf.setToolTip("Send DTMF digits to the connected AllStarLink node or EchoLink station (control codes)")
        mv.addWidget(self.dtmf, 0, Qt.AlignmentFlag.AlignLeft); self.dtmf.clicked.connect(self._dtmf)
        self.tx = TxControls(ctx, on_new_qso); mv.addWidget(self.tx)
        self.tx.setVisible(False)            # the same controls are in the fixed bar at the bottom of every page (the widget stays, its signals still work)
        mv.addWidget(label("AUDIO", section=True))
        if net == "EchoLink":
            g = W.QGridLayout(); self.el_call = W.QLineEdit(ctx.store.settings.get("echolink_call") or ctx.store.settings.get("callsign", ""))
            self.el_pw = W.QLineEdit(); self.el_pw.setEchoMode(W.QLineEdit.EchoMode.Password); self.el_pw.setText(ctx.el_password)
            g.addWidget(field("EchoLink callsign", self.el_call), 0, 0); g.addWidget(field("EchoLink password", self.el_pw), 0, 1); mv.addLayout(g)
            self.el_rem = checkbox("Remember on this computer (enter it only once)"); self.el_rem.setChecked(bool(ctx.store.settings.get("el_remember", True))); mv.addWidget(self.el_rem)
            note = label("The callsign and password of your own validated EchoLink account. When ticked, the password is kept in this program's settings file on this computer (not encrypted).", muted=True); note.setWordWrap(True); mv.addWidget(note)
            br_ = FlowLayout(hspace=6, vspace=6); self.el_sign = button("Sign in to EchoLink", "primary"); self.el_test = button("Test connection"); br_.addWidget(self.el_sign); br_.addWidget(self.el_test); mv.addLayout(br_)
            self.el_state = label("", muted=True); self.el_state.setWordWrap(True); mv.addWidget(self.el_state)
            self.el_call.textChanged.connect(self._el_login); self.el_pw.textChanged.connect(self._el_login); self.el_rem.toggled.connect(self._el_login)
            self.el_sign.clicked.connect(self._el_sign_in); self.el_test.clicked.connect(self._el_test_run)
            ctx.el_changed.connect(self._el_show); self._el_testing = False
            if ctx.el_password and not ctx.el_signed_in and not ctx.el_busy and ctx.store.settings.get("echolink_call", ctx.store.settings.get("callsign")): ctx.el_sign_in(silent=True)     # sign in once when the page opens (account already entered)
        self.audio = AudioBlock(ctx); mv.addWidget(self.audio)
        self.rxvol = W.QSlider(Qt.Orientation.Horizontal); self.rxvol.setRange(0, 100); self.rxvol.setValue(int(ctx.rules.net_volume[net] * 100))
        vr = hbox(); vr.addWidget(label("RX volume", muted=True)); vr.addWidget(self.rxvol, 1); mv.addLayout(vr)
        self.hint = label({"DMR": "Connects to the DMR master set in Settings › Radio networks (DMR ID required). Listen and Connect (TX) are separate.",
                           "EchoLink": "Connects to the chosen EchoLink station with your validated account. Listen and Connect (TX) are separate; EchoLink carries one conversation at a time.",
                           "AllStar": "Connects to the chosen AllStarLink node with your portal account. Listen and Connect (TX) are separate; the node must allow app connections."}.get(net, "Listen links for reception only. Connect (TX) is separate and must be enabled to transmit."), muted=True)
        self.hint.setWordWrap(True); mv.addWidget(self.hint); mv.addStretch()
        # --- right: last heard
        right = panel(); rv = vbox(right, m=(16, 16, 16, 12), s=10)
        rv.addWidget(label("Last station heard")); rv.itemAt(0).widget().setStyleSheet("font-weight:700;font-size:14px;")
        # "now talking" block on top: who is on the air on this network, and a bar while they talk
        self.now_box = W.QFrame(); self.now_box.setObjectName("nowTalking"); nb = vbox(self.now_box, m=(10, 10, 10, 10), s=4)
        self.now_head = label("NOW TALKING", section=True); nb.addWidget(self.now_head)
        self.now_call = label("Nobody is talking right now."); self.now_call.setStyleSheet("font-size:20px;font-weight:700;"); self.now_call.setWordWrap(True); nb.addWidget(self.now_call)
        self.now_info = label("", muted=True); self.now_info.setWordWrap(True); nb.addWidget(self.now_info)
        self.now_bar = W.QProgressBar(); self.now_bar.setRange(0, 0); self.now_bar.setTextVisible(False); self.now_bar.setFixedHeight(6); self.now_bar.setVisible(False); nb.addWidget(self.now_bar)
        rv.addWidget(self.now_box); rv.addSpacing(6)
        # last heard: its own table, so the talk time is not folded under the callsign
        rv.addWidget(label("LAST HEARD", section=True))
        self.lh_tbl = W.QTableWidget(0, 5); self.lh_tbl.setHorizontalHeaderLabels([tr(c) for c in ("Callsign", "DMR ID", "Country", "UTC", "Talk")])
        self.lh_tbl.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers); self.lh_tbl.verticalHeader().setVisible(False)
        self.lh_tbl.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows); self.lh_tbl.setMinimumHeight(160)
        rv.addWidget(self.lh_tbl, 1)
        if net == "AllStar":
            rv.addSpacing(8); rv.addWidget(label("CONNECTED TO THIS NODE", section=True))
            self.asl_head = label("Connect to a node to see who is connected to it.", muted=True); self.asl_head.setWordWrap(True); rv.addWidget(self.asl_head)
            self.asl_list = W.QListWidget(); self.asl_list.setMinimumHeight(140); rv.addWidget(self.asl_list, 1)
            ctx.asl_links_changed.connect(self._asl_links_show); ctx.changed.connect(self._asl_links_show)
        if net == "EchoLink":
            rv.addSpacing(8); rv.addWidget(label("CONNECTED TO THIS NODE", section=True))
            self.el_head = label("Connect to a station to see who is connected to it.", muted=True); self.el_head.setWordWrap(True); rv.addWidget(self.el_head)
            self.el_list = W.QListWidget(); self.el_list.setMinimumHeight(140); rv.addWidget(self.el_list, 1)
            self.el_msgs = label("", muted=True); self.el_msgs.setWordWrap(True); rv.addWidget(self.el_msgs)
            ctx.el_changed.connect(self._el_nodes_show); ctx.changed.connect(self._el_nodes_show)
        rv.addStretch()
        left.setMinimumWidth(300); mid.setMinimumWidth(350); right.setMinimumWidth(240); self._right = right
        root.addWidget(left, 5); root.addWidget(mid, 5); root.addWidget(right, 4)
        # wiring
        self.search.textChanged.connect(lambda: (setattr(self, "page", 0), self.fill())); self.country.currentIndexChanged.connect(lambda: self.fill())
        self.prev.clicked.connect(lambda: self._page(-1)); self.next.clicked.connect(lambda: self._page(1))
        self.list.currentRowChanged.connect(self._picked); self.addfav.clicked.connect(self._togglefav)
        self.module.currentIndexChanged.connect(self._module_changed)
        self.manual.clicked.connect(self._manual); self.refresh_btn.clicked.connect(lambda: ((ctx.refresh_asl(True) if net == "AllStar" else (ctx.el_refresh() if net == "EchoLink" else ctx.refresh_hosts(True))), self.fill()))
        self.rxvol.valueChanged.connect(lambda v: ctx.rules.net_volume.__setitem__(net, v / 100))
        self.choose.clicked.connect(self._choose_master); ctx.hosts_changed.connect(self._hosts_loaded); ctx.dmr_server_changed.connect(self._tx_show)
        self.srv_save.clicked.connect(self._srv_save); self.srv_reset.clicked.connect(self._srv_reset); self._srv_key = None
        ctx.changed.connect(self.refresh); self._hosts_loaded(); self._tx_show()

    def _dtmf(self):
        t = self.ctx.dtmf_peer()
        if t is None: self.ctx.toast.emit("DTMF is sent to the connected AllStarLink node or EchoLink station. Select it and connect first (EchoLink: with Connect (TX) on)."); return
        s, ok = W.QInputDialog.getText(self, "DTMF", tr("Node {}\nSequence (0-9 A-D * #, up to 32):").format(t.id))
        if ok: self.ctx.send_dtmf(s, t)

    # ---- EchoLink page -----------------------------------------------------------------------------------------
    def _el_login(self):
        self.ctx.set_el_login(self.el_call.text(), self.el_pw.text(), self.el_rem.isChecked())

    def _el_sign_in(self):
        self._el_login(); self.ctx.el_sign_in()

    def _el_test_run(self):
        """Signs in again and then shows exactly what the EchoLink directory answered - for finding out why a sign-in or the list does not work."""
        self._el_login(); self._el_testing = True; self.ctx.el_sign_in()

    def _el_show(self):
        c = self.ctx
        self.el_state.setText(tr(c.el_status) if c.el_status else tr("Not signed in"))
        self.el_sign.setEnabled(not c.el_busy); self.el_test.setEnabled(not c.el_busy)
        if self._el_testing and not c.el_busy:
            self._el_testing = False; r = c.el_result or {}
            lines = [tr("Server") + ": " + (r.get("server") or "—"), tr("Sign-in answer") + ": " + (r.get("login_raw") or "—"), tr("Stations read") + f": {len(r.get('stations', []))}"]
            if r.get("error"): lines.append(tr("Problem") + ": " + tr(r["error"]))
            if r.get("list_raw"): lines += ["", tr("Start of the station list as the directory sent it") + ":", r["list_raw"][:1200]]
            box = W.QMessageBox(self); box.setWindowTitle(tr("EchoLink test")); box.setText(tr("Result of the EchoLink test") + (": OK" if r.get("ok") else ": " + tr("failed")))
            box.setDetailedText("\n".join(lines)); box.setInformativeText("\n".join(lines[:4])); box.exec()
        self._hosts_loaded() if c.el_stations and len(self.entries) != len(c.el_stations) else None

    def _el_nodes_show(self):
        """Who is connected to the station we are connected to: the call signs in what the station itself sends (greeting, conference user list), as EchoLink shows them."""
        if self.net != "EchoLink": return
        t = self.ctx.selected; call = t.id.upper() if (t is not None and t.net == "EchoLink") else ""
        self.el_list.clear(); self.el_msgs.setText("")
        if not call or not self.ctx._el_in_use():
            self.el_head.setText(tr("Connect to a station to see who is connected to it.")); return
        st = self.ctx.el_nodes.get(call)
        if not st: self.el_head.setText(tr("Waiting for the station to tell who is connected …")); return
        self.el_head.setText(tr("{} · {} connected").format(call, len(st.get("calls", []))))
        for c in st.get("calls", []):
            country = countries.of_callsign(c)
            self.el_list.addItem(c + (f"  ·  {country}" if country else ""))
        self.el_msgs.setText("\n".join(st.get("lines", [])[-6:]))

    def _asl_login(self):
        self.ctx.set_asl_login(self.asl_user.text(), self.asl_pw.text(), self.asl_rem.isChecked())

    def _hosts_loaded(self):
        self.entries = directory.entries(self.net, self.ctx.hosts, self.ctx.asl_nodes, self.ctx.el_stations)
        cur = self.country.currentText()
        names = sorted({e.get("country", "") for e in self.entries if e.get("country")})
        self.country.blockSignals(True); self.country.clear(); self.country.addItems([tr("All countries")] + names); i18n.combo_item(self.country, 0, "All countries")
        if cur in names: self.country.setCurrentText(cur)
        elif self.net == "EchoLink" and names and not getattr(self, "_el_country_set", False):          # EchoLink: the list opens on the user's own country (then it stays as the user picked it)
            own = countries.of_callsign(self.ctx.store.settings.get("echolink_call") or self.ctx.store.settings.get("callsign") or "")
            if own in names: self.country.setCurrentText(own); self._el_country_set = True
        self.country.blockSignals(False); self.fill()

    def _asl_links_show(self):
        """The stations connected to the selected AllStar node (from the AllStarLink stats server), as every AllStar program shows them."""
        if self.net != "AllStar": return
        t = self.ctx.selected; node = t.id if (t is not None and t.net == "AllStar") else ""
        res = self.ctx.asl_links.get(node) if node else None
        self.asl_list.clear()
        if not node or node not in self.ctx._asl_nodes_in_use():
            self.asl_head.setText(tr("Connect to a node to see who is connected to it.")); return
        if res is None: self.asl_head.setText(tr("Reading the connections of node {} …").format(node)); return
        if res.get("error"): self.asl_head.setText(tr(res["error"])); return
        head = tr("Node {} · {} connected").format(node, len(res["rows"])) + ((" · " + res["title"]) if res.get("title") else "")
        if res.get("keyed"): head += " · " + tr("● transmitting now")
        self.asl_head.setText(head)
        for r in res["rows"]:
            mode = {"T": tr("transceive"), "R": tr("receive only"), "C": tr("connecting")}.get(r["mode"], "")
            line1 = f"{r['callsign'] or '—'}  ·  {r['node']}" + (f"  ·  {mode}" if mode else "")
            line2 = "   " + "  ·  ".join(x for x in (r["site"], r["location"]) if x)
            self.asl_list.addItem(line1 + ("\n" + line2 if line2.strip() else ""))

    def _choose_master(self):
        from .dmr_picker import choose_dmr_server
        choose_dmr_server(self, self.ctx)

    def _tx_show(self):
        """DMR page: the chosen transmit server (name and address, as the list gives them). Settings > Radio networks carries the same server and port."""
        if self.net != "DMR": return
        from .dmr_picker import chosen_name
        s = self.ctx.store.settings; host, port = str(s.get("dmr_server") or ""), s.get("dmr_port") or ""
        self.tx_name.setText(chosen_name(self.ctx) if host else tr("No server chosen")); self.tx_addr.setText(f"{host} : {port}" if host else "")
        self.tx_hint.setText("" if self.ctx.dmr_password and s.get("dmr_id") else tr("Enter your DMR ID and your password in Settings › Radio networks to connect."))

    # ---- server address of the selected station (shown from the list, editable, and really used by the engine) ----------
    def _srv_target(self):
        t = self.ctx.selected
        return t if (t is not None and t.net == self.net) else (Target("DMR", "0", "") if self.net == "DMR" else None)

    def _srv_show(self, t, force=False):
        t = t or self._srv_target()
        key = (t.net, t.id) if t else None
        stamp = (key, self.ctx.store.settings.get("dmr_server"), self.ctx.store.settings.get("dmr_port"), len(self.ctx.hosts.entries), len(self.ctx.servers.user), len(self.ctx.servers.el_hosts))
        if not force and stamp == getattr(self, "_srv_stamp", None): return          # do not overwrite what the user is typing
        self._srv_stamp = stamp
        if t is None:
            self.srv_host.clear(); self.srv_port.clear(); self.srv_src.setText("Select a station to see its server address."); self._srv_en(False); return
        ep, src = self.ctx.servers.info(t)
        self.srv_host.setText(ep["host"] if ep else ""); self.srv_port.setText(str(ep["port"]) if ep else "")
        self.srv_src.setText({"your address": "Source: your own address (used instead of the list).", "built in": "Source: built into DigiConnect.",
                              "DMR master (Settings)": "Source: the DMR master you chose. Press «Choose DMR server» to change it.",
                              "worldwide list": "Source: the downloaded worldwide server list.",
                              "AllStarLink DNS": "Source: AllStarLink node address (looked up when you connect).",
                              "EchoLink directory": "Source: the EchoLink directory (the address of this station)."}.get(src, "Not in the downloaded lists yet — press Refresh, or type the address here."))
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
        if self.net == "D-Star" and self.module.currentIndex() > 0 and not self.show_favs:           # the module box filters the list: only the chosen module of every reflector
            src = [e for e in src if e["id"].endswith(" " + self.module.currentText())]
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
        if self.net == "EchoLink":
            self.count.setText(f"EchoLink · {total} stations" if self.ctx.el_stations else "EchoLink · sign in to load the station list")
        self.refresh()

    def _module_changed(self, _=None):
        if self.net == "D-Star": setattr(self, "page", 0); self.fill()
        elif self.list.currentRow() >= 0: self._picked(self.list.currentRow())               # M17: the chosen module applies to the entry that is selected now

    def _picked(self, row):
        it = self.list.item(row)
        if not it: return
        e = it.data(Qt.ItemDataRole.UserRole); self.ctx.last_net = self.net
        id_ = e["id"]
        if self.net == "M17" and self.module.currentIndex() > 0 and " " in id_ and e.get("proto"): id_ = id_.split()[0] + " " + self.module.currentText()
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
        if self.net == "D-Star":
            text = norm_dstar(text)
            if not text: self.ctx.toast.emit("A D-Star reflector looks like REF001 C, XRF012 A, DCS003 B or XLX307 D (name, then the module letter)."); return
        if self.net == "AllStar" and not valid_node_text(text):
            self.ctx.toast.emit("An AllStarLink node number has 3 to 8 digits."); return
        self.ctx.store.toggle_fav(self.net, text, f"{self.net} {text}") if not self.ctx.store.is_fav(self.net, text) else None
        self.ctx.select(Target(self.net, text, f"{self.net} {text}")); self.fill(); self.ctx.changed.emit()


    def _show_now(self):
        """Who is on the air on this network right now (callsign, DMR ID, site) and a bar while they talk."""
        live = [v for (n, _), v in self.ctx.talking.items() if n == self.net]
        if live:
            v = live[0]; info = self.ctx.station_info(v.get("srcid") or 0) or {}
            self.now_call.setText(v.get("src") or "?")
            bits = [f"DMR ID {v['srcid']}"] if v.get("srcid") else []
            site = ", ".join(x for x in (info.get("name"), info.get("city"), info.get("country")) if x)
            if site: bits.append(site)
            self.now_info.setText(" · ".join(bits)); self.now_bar.setVisible(True)
            self.now_head.setText("NOW TALKING ●")
            col = NET_COLOR.get(self.net, C["muted"]) if isinstance(NET_COLOR, dict) else C["muted"]
            self.now_box.setStyleSheet(f"#nowTalking {{ border:2px solid {col}; border-radius:8px; }}")
        else:
            self.now_call.setText("Nobody is talking right now."); self.now_info.setText("")
            self.now_bar.setVisible(False); self.now_head.setText("NOW TALKING")
            self.now_box.setStyleSheet("")

    def _fill_heard(self, rows):
        from .heardpage import duration
        rows = rows[:40]
        self.lh_tbl.setRowCount(len(rows))
        for r, h in enumerate(rows):
            info = self.ctx.station_info(h.get("srcid") or 0) if h.get("srcid") else None
            vals = [h["src"] + (" (you)" if h.get("me") else ""), str(h.get("srcid") or "—"), (info or {}).get("country") or "—",
                    f"{h['ts']:%H:%M:%S}", duration(h)]
            for c, val in enumerate(vals): self.lh_tbl.setItem(r, c, W.QTableWidgetItem(val))
        hd = self.lh_tbl.horizontalHeader(); hd.setStretchLastSection(False)
        hd.setSectionResizeMode(W.QHeaderView.ResizeMode.Stretch)             # the six columns share the width: nothing is cut off
        self.lh_tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def refresh(self):
        closed = not self.ctx.policy.allows(self.net)
        self.closed_note.setVisible(closed); self._sc.setEnabled(not closed)
        if closed: self.closed_txt.setText("⚠  " + tr(self.ctx.policy.reason(self.net)))
        t = self.ctx.selected; mine = t is not None and t.net == self.net
        self.title.setText(t.name if mine else "Select a station")
        self.sub.setText(f"{t.net} · {t.id}" if mine else "Select an entry in the list on the left.")
        self.addfav.setEnabled(mine)
        self.addfav.setText("★  Remove favorite" if mine and self.ctx.store.is_fav(t.net, t.id) else "☆  Add favorite")
        self._srv_show(t if mine else None); self._tx_show()
        self._show_now()
        self._fill_heard(list(self.ctx.last_heard))          # every network, newest first (a station heard on C4FM also shows on the DMR page)
