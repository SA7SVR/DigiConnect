"""VoIP phone page: sign in to the SIP server, see who is available, call and talk. Everything shown is what the server says (registered, ringing, busy, ...); when the server says nothing the page says "unknown"."""
import time
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .widgets import label, button, checkbox, panel, vbox, hbox, field, LevelBar
from .icons import dot
from ..i18n import tr
from ..voip.phone import STATE_TEXT
from ..voip.texts import reason

DOT = {"available": "#3ecf8e", "free": "#7bd88f", "ringing": "#f5a623", "busy": "#ef5350", "offline": "#6b7a90", "nonumber": "#6b7a90", "unknown": "#6b7a90"}
REG_TONE = {"registered": "green", "registering": "amber", "failed": "red", "unregistered": "muted"}
PAD = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]


class VoipPage(W.QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx; self.ph = ctx.phone; s = ctx.store.settings
        outer = hbox(self, s=14)

        def column(card, stretch):                       # every column scrolls by itself when the window is small
            sc = W.QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(W.QFrame.Shape.NoFrame); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setWidget(card); sc.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea > QWidget > QWidget{background:transparent;}"); outer.addWidget(sc, stretch)

        class _Root:
            def addWidget(self, w, st=1): column(w, st)
        root = _Root()
        # ---------------- account
        acc = panel("card"); av = vbox(acc, m=(16, 14, 16, 14), s=8); root.addWidget(acc, 4)
        av.addWidget(label("ACCOUNT", section=True))
        self.server = W.QLineEdit(s.get("voip_server", "")); self.server.setPlaceholderText("sip.example.org")
        self.port = W.QLineEdit(str(s.get("voip_port", 5060))); self.port.setFixedWidth(80)
        self.transport = W.QComboBox(); self.transport.addItems(["UDP", "TCP", "TLS"]); self.transport.setCurrentText(str(s.get("voip_transport", "udp")).upper())
        sr = hbox(s=8); sr.addWidget(field("Server", self.server), 1); sr.addWidget(field("Port", self.port)); sr.addWidget(field("Transport", self.transport)); av.addLayout(sr)
        self.user = W.QLineEdit(s.get("voip_user", "")); self.user.setPlaceholderText("1001")
        self.pw = W.QLineEdit(s.get("voip_pw", "") if s.get("voip_remember", True) else ""); self.pw.setEchoMode(W.QLineEdit.EchoMode.Password)
        self.name = W.QLineEdit(s.get("voip_name") or s.get("op_name") or s.get("callsign", "")); self.name.setPlaceholderText("SA7SVR")
        av.addWidget(field("Username (extension)", self.user)); av.addWidget(field("Password", self.pw)); av.addWidget(field("Name shown to the other side", self.name))
        self.remember = checkbox("Remember the password on this computer"); self.remember.setChecked(bool(s.get("voip_remember", True)))
        self.auto = checkbox("Sign in when DigiConnect starts"); self.auto.setChecked(bool(s.get("voip_auto", False)))
        self.tlsv = checkbox("Check the server's certificate (TLS)"); self.tlsv.setChecked(bool(s.get("voip_tls_verify", True)))
        for c in (self.remember, self.auto, self.tlsv): av.addWidget(c)
        self.sign = button("Sign in", "primary"); av.addWidget(self.sign)
        self.reg = label("Not signed in", muted=True); self.reg.setWordWrap(True); av.addWidget(self.reg)
        av.addWidget(label("The password is entered here by you and sent only to your server. Use a headset: the program has no echo cancellation, so with open speakers the other side hears itself.", muted=True)); av.itemAt(av.count() - 1).widget().setWordWrap(True)
        av.addStretch()
        # ---------------- phone
        ph = panel("card"); pv = vbox(ph, m=(16, 14, 16, 14), s=8); root.addWidget(ph, 4)
        pv.addWidget(label("PHONE", section=True))
        self.status = label("No call"); self.status.setStyleSheet("font-size:20px;font-weight:700;"); self.status.setWordWrap(True); pv.addWidget(self.status)
        self.who = label("", muted=True); self.who.setWordWrap(True); pv.addWidget(self.who)
        self.timer = label(""); self.timer.setStyleSheet("font-size:15px;"); pv.addWidget(self.timer)
        self.number = W.QLineEdit(); self.number.setPlaceholderText("Number or extension"); self.number.setStyleSheet("font-size:18px;"); pv.addWidget(self.number)
        grid = W.QGridLayout(); grid.setSpacing(6); self.keys = {}
        for i, k in enumerate(PAD):
            b = button(k, "seg"); b.setMinimumHeight(40); b.clicked.connect(lambda _, k=k: self._key(k)); grid.addWidget(b, i // 3, i % 3); self.keys[k] = b
        pv.addLayout(grid)
        r = hbox(s=8); self.call_btn = button("Call", "primary"); self.hang = button("Hang up", "danger"); self.mute = button("Mute", "seg", checkable=True); r.addWidget(self.call_btn, 1); r.addWidget(self.hang, 1); r.addWidget(self.mute); pv.addLayout(r)
        self.in_box = W.QWidget(); ib = hbox(self.in_box, s=8); self.answer = button("Answer", "primary"); self.decline = button("Decline", "danger"); ib.addWidget(self.answer, 1); ib.addWidget(self.decline, 1); pv.addWidget(self.in_box)
        self.mic_bar, self.spk_bar = LevelBar(6), LevelBar(6)
        pv.addWidget(label("Microphone", muted=True)); pv.addWidget(self.mic_bar); pv.addWidget(label("Speakers", muted=True)); pv.addWidget(self.spk_bar)
        self.dev = label("", muted=True); self.dev.setWordWrap(True); pv.addWidget(self.dev); pv.addStretch()
        # ---------------- people
        pe = panel("card"); ev = vbox(pe, m=(16, 14, 16, 14), s=8); root.addWidget(pe, 5)
        ev.addWidget(label("PEOPLE", section=True))
        self.people = W.QListWidget(); self.people.setIconSize(QtCore.QSize(14, 14)); ev.addWidget(self.people, 3)
        br = hbox(s=6); self.add = button("Add"); self.edit = button("Edit"); self.rm = button("Remove"); br.addWidget(self.add); br.addWidget(self.edit); br.addWidget(self.rm); br.addStretch(); ev.addLayout(br)
        self.people_note = label("", muted=True); self.people_note.setWordWrap(True); ev.addWidget(self.people_note)
        ev.addWidget(label("RECENT CALLS", section=True)); self.hist = W.QListWidget(); ev.addWidget(self.hist, 2)
        # wiring
        self.sign.clicked.connect(self._sign); self.call_btn.clicked.connect(self._call); self.hang.clicked.connect(self.ph.hangup); self.answer.clicked.connect(self.ph.answer); self.decline.clicked.connect(self.ph.reject)
        self.mute.toggled.connect(self.ph.set_muted); self.number.returnPressed.connect(self._call)
        self.add.clicked.connect(self._add); self.edit.clicked.connect(self._edit); self.rm.clicked.connect(self._remove); self.people.itemDoubleClicked.connect(self._dial_item)
        self.ph.registration.connect(self._on_reg); self.ph.call_changed.connect(self._on_call); self.ph.presence_changed.connect(lambda _e: self.refresh_people()); self.ph.history_changed.connect(self.refresh_history)
        self.ph.dtmf_in.connect(lambda c, d: self.who.setText(tr("Key pressed by the other side:") + " " + d))
        self.tick = QtCore.QTimer(self); self.tick.setInterval(150); self.tick.timeout.connect(self._tick); self.tick.start()
        self._on_reg(self.ph.reg_state, self.ph.reg_text); self.refresh_people(); self.refresh_history(); self._sync_buttons()

    # ---- account
    def save_account(self):
        s = self.ctx.store.settings
        try: port = int(self.port.text().strip() or 5060)
        except ValueError: port = 5060
        s.update(voip_server=self.server.text().strip(), voip_port=port, voip_transport=self.transport.currentText().lower(), voip_user=self.user.text().strip(), voip_name=self.name.text().strip(),
                 voip_remember=self.remember.isChecked(), voip_auto=self.auto.isChecked(), voip_tls_verify=self.tlsv.isChecked(), voip_pw=self.pw.text() if self.remember.isChecked() else "")
        self.ctx.store.save_settings()

    def _sign(self):
        if self.ph.reg_state in ("registered", "registering"): self.ph.sign_out(); return
        self.save_account(); self.ph.sign_in(self.pw.text())

    def _on_reg(self, state: str, text: str):
        names = {"registered": "Signed in", "registering": "Signing in…", "failed": "Not signed in", "unregistered": "Not signed in"}
        self.reg.setText((tr(names.get(state, "")) + (" — " + reason(text) if text else "")) if text or state != "unregistered" else tr("Not signed in")); self.reg.setProperty("tone", REG_TONE.get(state, "muted")); self.reg.style().unpolish(self.reg); self.reg.style().polish(self.reg)
        self.sign.setText(tr("Sign out") if state in ("registered", "registering") else tr("Sign in")); self._sync_buttons()

    # ---- calls
    def _key(self, k: str):
        c = self.ph.call
        if c and c.state == "active": self.ph.dtmf(k)
        else: self.number.setText(self.number.text() + k)

    def _call(self):
        if self.ph.call and self.ph.call.state != "ended": return
        if not self.ph.dial(self.number.text()):
            self.who.setText(tr("Sign in first, then enter a number") if self.ph.reg_state != "registered" else tr("Enter a number"))

    def _dial_item(self, it):
        n = it.data(Qt.ItemDataRole.UserRole)
        if n: self.number.setText(n); self._call()

    def _on_call(self, call, state: str):
        self._sync_buttons()
        if state == "ended" and call.end_reason: self.status.setText(reason(call.end_reason)); self.who.setText(tr("Call ended")); self.timer.setText("")
        else: self._show_call(call)

    def _show_call(self, c):
        st = c.state if not c.held_by_remote else "held"
        self.status.setText(tr(STATE_TEXT.get(st, st)))
        nm = " · ".join(x for x in (c.remote_name or self.ph.name_of(c.remote_user), c.remote_user) if x) or c.remote_uri
        self.who.setText((tr("From") if c.direction == "in" else tr("To")) + " " + nm)

    def _sync_buttons(self):
        c = self.ph.call; live = bool(c and c.state != "ended"); incoming = bool(c and c.state == "incoming")
        reg = self.ph.reg_state == "registered"
        self.in_box.setVisible(incoming); self.call_btn.setVisible(not live); self.hang.setVisible(live and not incoming); self.mute.setVisible(live and not incoming)
        self.call_btn.setEnabled(reg); self.number.setEnabled(not (live and c.state != "ended" and incoming))
        if not live:
            self.mic_bar.set_level(0); self.spk_bar.set_level(0); self.dev.setText("")
            if not (c and c.state == "ended"): self.status.setText(tr("No call") if reg else tr("Sign in to call")); self.who.setText(""); self.timer.setText("")
            self.mute.setChecked(False)

    def _tick(self):
        c, a = self.ph.call, self.ph.audio
        if c and c.state == "active": 
            d = int(c.duration); self.timer.setText(f"{d // 60:02d}:{d % 60:02d}")
        if a:
            self.mic_bar.set_level(min(1.0, a.mic_level * 6)); self.spk_bar.set_level(min(1.0, a.spk_level * 6))
            txt = []
            if a.mic_used: txt.append(tr("Microphone:") + " " + a.mic_used)
            if a.spk_used: txt.append(tr("Speakers:") + " " + a.spk_used)
            if a.error: txt.append(reason(a.error))
            self.dev.setText("\n".join(txt))

    # ---- people
    def refresh_people(self):
        sel = (self.people.currentItem().data(Qt.ItemDataRole.UserRole) if self.people.currentItem() else None)
        self.people.clear(); cs = self.ph.contacts()
        for c in cs:
            st, txt = self.ph.state_of(c["number"])
            nm = c.get("name") or c.get("callsign") or c["number"]
            extra = f" · {c['callsign']}" if c.get("callsign") and c.get("name") else ""
            it = W.QListWidgetItem(f"{nm}{extra}   {c['number']}   —   {reason(txt)}"); it.setIcon(dot(DOT.get(st, DOT['unknown']))); it.setData(Qt.ItemDataRole.UserRole, c["number"]); self.people.addItem(it)
            if c["number"] == sel: self.people.setCurrentItem(it)
        self.people_note.setText(tr("Add the people you call (name and extension). Their state is what the server reports: available, ringing, on a call or offline.") if not cs else
                                 (tr("Double-click a person to call.") + ("" if self.ph.reg_state == "registered" else " " + tr("Sign in to see who is available."))))

    def _ask(self, title: str, c=None):
        d = W.QDialog(self); d.setWindowTitle(tr(title)); v = vbox(d, m=(16, 14, 16, 14), s=8)
        n = W.QLineEdit((c or {}).get("name", "")); cs = W.QLineEdit((c or {}).get("callsign", "")); num = W.QLineEdit((c or {}).get("number", ""))
        v.addWidget(field("Name", n)); v.addWidget(field("Callsign", cs)); v.addWidget(field("Number or extension", num))
        bb = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok | W.QDialogButtonBox.StandardButton.Cancel); bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); v.addWidget(bb)
        if d.exec() != W.QDialog.DialogCode.Accepted or not num.text().strip(): return None
        return dict(name=n.text().strip(), callsign=cs.text().strip().upper(), number=num.text().strip())

    def _add(self):
        c = self._ask("Add a person")
        if c: self.ph.set_contacts(self.ph.contacts() + [c]); self.refresh_people()

    def _edit(self):
        it = self.people.currentItem()
        if not it: return
        n = it.data(Qt.ItemDataRole.UserRole); cs = self.ph.contacts()
        for i, c in enumerate(cs):
            if c["number"] == n:
                new = self._ask("Edit", c)
                if new: cs[i] = new; self.ph.set_contacts(cs); self.refresh_people()
                return

    def _remove(self):
        it = self.people.currentItem()
        if not it: return
        n = it.data(Qt.ItemDataRole.UserRole); self.ph.set_contacts([c for c in self.ph.contacts() if c["number"] != n]); self.refresh_people()

    def refresh_history(self):
        self.hist.clear(); h = self.ctx.store.settings.get("voip_history") or []
        sym = {"placed": "→", "received": "←", "missed": "✕"}
        for e in h[:30]:
            t = time.strftime("%d %b %H:%M", time.localtime(e.get("t", 0))); dur = f" {e['secs'] // 60}:{e['secs'] % 60:02d}" if e.get("secs") else ""
            it = W.QListWidgetItem(f"{sym.get(e.get('dir'), '')}  {e.get('name') or e.get('number')}  {e.get('number') if e.get('name') else ''}  ·  {t}{dur}"); it.setData(Qt.ItemDataRole.UserRole, e.get("number")); self.hist.addItem(it)
        self.hist.itemDoubleClicked.connect(self._dial_item) if not getattr(self, "_h_conn", False) else None; self._h_conn = True
