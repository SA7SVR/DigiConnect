"""VoIP phone page: sign in to the SIP server, see who is available, call and talk. Everything shown is what the server says (registered, ringing, busy, ...); when the server says nothing the page says "unknown"."""
import threading, time
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .widgets import label, button, checkbox, panel, vbox, hbox, field, LevelBar, FlowLayout
from .icons import dot
from ..i18n import tr
from ..voip.phone import STATE_TEXT, RINGTONES
from ..voip.texts import reason
from ..voip import signup

DOT = {"available": "#3ecf8e", "free": "#7bd88f", "ringing": "#f5a623", "busy": "#ef5350", "offline": "#6b7a90", "nonumber": "#6b7a90", "unknown": "#6b7a90"}
REG_TONE = {"registered": "green", "registering": "amber", "failed": "red", "unregistered": "muted"}
PAD = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]


class VoipPage(W.QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx; self.ph = ctx.phone; s = ctx.store.settings
        top = vbox(self, s=10)                           # a notice when the Admin's server has closed the phone, and the page itself
        self.closed_note = panel("note"); _cv = vbox(self.closed_note, m=(12, 10, 12, 10), s=8); self.closed_txt = label(""); self.closed_txt.setWordWrap(True); _cv.addWidget(self.closed_txt)
        self.closed_btn = button("♥ Donate", "primary"); self.closed_btn.clicked.connect(self._pay_extra); _cv.addWidget(self.closed_btn, 0, Qt.AlignmentFlag.AlignLeft); top.addWidget(self.closed_note)
        self.body = W.QWidget(); outer = hbox(self.body, s=14); top.addWidget(self.body, 1)

        def column(card, stretch):                       # every column scrolls by itself when the window is small
            sc = W.QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(W.QFrame.Shape.NoFrame); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setWidget(card); sc.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea > QWidget > QWidget{background:transparent;}"); outer.addWidget(sc, stretch)

        class _Root:
            def addWidget(self, w, st=1): column(w, st)
        root = _Root()
        # ---------------- account: five tabs (Account, Network, Audio, Calls, Advanced); everything is saved as soon as it is changed
        acc = panel("card"); av = vbox(acc, m=(16, 14, 16, 14), s=8); root.addWidget(acc, 6)
        av.addWidget(label("ACCOUNT", section=True))
        self.ctl = {}                                    # settings key -> (widget, kind)

        def reg(key, w, kind, default=None):
            self.ctl[key] = (w, kind)
            if kind == "text": w.editingFinished.connect(self._changed)
            elif kind == "int": w.editingFinished.connect(self._changed); w.valueChanged.connect(lambda _v: self._changed())
            elif kind == "bool": w.toggled.connect(lambda _v: self._changed())
            elif kind == "combo": w.currentIndexChanged.connect(lambda _i: self._changed())
            return w

        def spin(lo, hi, val, special="", suffix="", step=1):
            sp = W.QSpinBox(); sp.setRange(lo, hi); sp.setValue(val); sp.setSingleStep(step); sp.setKeyboardTracking(False)
            if special: sp.setSpecialValueText(special)
            if suffix: sp.setSuffix(suffix)
            return sp

        def combo(items, data=None):
            c = W.QComboBox()
            for i, t in enumerate(items): c.addItem(t, (data or items)[i])
            return c

        def page(): w = W.QWidget(); v = vbox(w, m=(0, 6, 0, 0), s=8); return w, v

        def note(text):
            l = label(text, muted=True); l.setWordWrap(True); return l
        self.sections = []
        bar = FlowLayout(hspace=6, vspace=6); barw = W.QWidget(); barw.setLayout(bar); av.addWidget(barw)
        self.stack = W.QStackedWidget(); av.addWidget(self.stack)

        def add_tab(title):
            w, v = page(); self.stack.addWidget(w); b = button(title, "tab", checkable=True); b.clicked.connect(lambda _=False, i=len(self.sections): self._tab(i)); bar.addWidget(b); self.sections.append(b); return v

        # -- Account
        v = add_tab("Account")
        self.acc_state = label("", muted=True); self.acc_state.setWordWrap(True); self.acc_state.setProperty("accstate", ""); v.addWidget(self.acc_state)     # the state of the account the Admin made: green = ready for use
        self.server = reg("voip_server", W.QLineEdit(str(s.get("voip_server", ""))), "text"); self.server.setPlaceholderText("sip.example.org")
        self.port = reg("voip_port", W.QLineEdit(str(s.get("voip_port", 5060))), "text"); self.port.setFixedWidth(80)
        self.transport = reg("voip_transport", combo(["UDP", "TCP", "TLS"]), "combo"); self.transport.setCurrentText(str(s.get("voip_transport", "udp")).upper())
        sr = hbox(s=8); sr.addWidget(field("Server", self.server), 1); sr.addWidget(field("Port", self.port)); sr.addWidget(field("Transport", self.transport)); v.addLayout(sr)
        self.user = reg("voip_user", W.QLineEdit(s.get("voip_user", "")), "text"); self.user.setPlaceholderText("1001")
        self.auth_user = reg("voip_auth_user", W.QLineEdit(s.get("voip_auth_user", "")), "text"); self.auth_user.setPlaceholderText(tr("Same as the username"))
        self.pw = W.QLineEdit(s.get("voip_pw", "") if s.get("voip_remember", True) else ""); self.pw.setEchoMode(W.QLineEdit.EchoMode.Password); self.pw.editingFinished.connect(self._changed)
        self.domain = reg("voip_domain", W.QLineEdit(s.get("voip_domain", "")), "text"); self.domain.setPlaceholderText(tr("Same as the server"))
        self.name = W.QLineEdit(s.get("voip_name") or s.get("op_name") or s.get("callsign", "")); self.name.setPlaceholderText("SA7SVR"); self.name.editingFinished.connect(self._changed)
        v.addWidget(field("Username (extension)", self.user)); v.addWidget(field("Authentication username (if different)", self.auth_user)); v.addWidget(field("Password", self.pw))
        v.addWidget(field("Domain / realm (if different from the server)", self.domain)); v.addWidget(field("Name shown to the other side", self.name))
        self.remember = reg("voip_remember", checkbox("Remember the password on this computer"), "bool"); self.remember.setChecked(bool(s.get("voip_remember", True)))
        self.auto = reg("voip_auto", checkbox("Sign in when DigiConnect starts"), "bool"); self.auto.setChecked(bool(s.get("voip_auto", False)))
        for c in (self.remember, self.auto): v.addWidget(c)
        self.sign = button("Sign in", "primary"); v.addWidget(self.sign)
        self.reg = label("Not signed in", muted=True); self.reg.setWordWrap(True); v.addWidget(self.reg)
        self.req_btn = button("I don't have an account: request one"); self.req_chk = button("Check the request"); self.req_lbl = label("", muted=True); self.req_lbl.setWordWrap(True)
        v.addWidget(self.req_btn); v.addWidget(self.req_chk); v.addWidget(self.req_lbl)
        self.req_btn.clicked.connect(self._req_dialog); self.req_chk.clicked.connect(lambda: self._req_check(False))
        self.acc = ctx.voip_account                                                    # keeps the account in step with the server (also when this page is closed)
        self.acc.note.connect(self._note); self.acc.account_changed.connect(self._load_from_settings); self.acc.state_changed.connect(self._req_refresh)
        v.addWidget(note("The password is entered here by you and sent only to your server. Use a headset: the program has no echo cancellation, so with open speakers the other side hears itself.")); v.addStretch()
        # -- Network
        v = add_tab("Network")
        self.proxy = reg("voip_proxy", W.QLineEdit(s.get("voip_proxy", "")), "text"); self.proxy.setPlaceholderText("proxy.example.org:5060")
        v.addWidget(field("Outbound proxy (optional; the connection goes there, the account stays on the server)", self.proxy))
        self.local_port = reg("voip_local_port", spin(0, 65535, int(s.get("voip_local_port", 0) or 0), special=tr("Automatic")), "int")
        self.expires = reg("voip_expires", spin(30, 86400, int(s.get("voip_expires", 300) or 300), suffix=" s"), "int")
        r = hbox(s=8); r.addWidget(field("Local SIP port", self.local_port)); r.addWidget(field("Registration time", self.expires)); v.addLayout(r)
        self.keepalive = reg("voip_keepalive", checkbox("Keep the NAT router open (keep-alive)"), "bool"); self.keepalive.setChecked(bool(s.get("voip_keepalive", True)))
        self.keepalive_secs = reg("voip_keepalive_secs", spin(0, 600, int(s.get("voip_keepalive_secs", 0) or 0), special=tr("Automatic (25 s UDP, 55 s TCP/TLS)"), suffix=" s"), "int")
        v.addWidget(self.keepalive); v.addWidget(field("Keep-alive every", self.keepalive_secs))
        self.stun = reg("voip_stun", W.QLineEdit(s.get("voip_stun", "")), "text"); self.stun.setPlaceholderText("stun.l.google.com:19302"); v.addWidget(field("STUN server (optional, for audio behind a NAT router)", self.stun))
        self.public_ip = reg("voip_public_ip", W.QLineEdit(s.get("voip_public_ip", "")), "text"); self.public_ip.setPlaceholderText(tr("Automatic")); v.addWidget(field("Public IP address (only if the router needs it set by hand)", self.public_ip))
        self.rtp_lo = reg("voip_rtp_lo", spin(1024, 65534, int(s.get("voip_rtp_lo", 12000) or 12000)), "int"); self.rtp_hi = reg("voip_rtp_hi", spin(1026, 65535, int(s.get("voip_rtp_hi", 12999) or 12999)), "int")
        r = hbox(s=8); r.addWidget(field("Audio ports from", self.rtp_lo)); r.addWidget(field("to", self.rtp_hi)); v.addLayout(r)
        self.tlsv = reg("voip_tls_verify", checkbox("Check the server's certificate (TLS)"), "bool"); self.tlsv.setChecked(bool(s.get("voip_tls_verify", True))); v.addWidget(self.tlsv)
        self.tls_ca = reg("voip_tls_ca", W.QLineEdit(s.get("voip_tls_ca", "")), "text"); self.tls_ca.setPlaceholderText(tr("Only for a server with its own certificate"))
        br = button("Browse…"); br.clicked.connect(self._browse_ca); cr = hbox(s=8); cr.addWidget(self.tls_ca, 1); cr.addWidget(br)
        cw = W.QWidget(); cw.setLayout(cr); v.addWidget(field("Certificate file of the server (.pem, optional)", cw))
        v.addWidget(note("Network changes are used the next time you sign in.")); v.addStretch()
        # -- Audio
        v = add_tab("Audio")
        self.pcmu = reg("voip_pcmu", checkbox("PCMU (G.711 µ-law)"), "bool"); self.pcmu.setChecked(bool(s.get("voip_pcmu", True))); self.pcma = reg("voip_pcma", checkbox("PCMA (G.711 A-law)"), "bool"); self.pcma.setChecked(bool(s.get("voip_pcma", True)))
        self.codec_first = reg("voip_codec_first", combo(["PCMU", "PCMA"]), "combo"); self.codec_first.setCurrentText(str(s.get("voip_codec_first", "PCMU")))
        v.addWidget(label("Codecs", section=True)); v.addWidget(self.pcmu); v.addWidget(self.pcma); v.addWidget(field("Preferred codec", self.codec_first))
        self.dtmf = reg("voip_dtmf", combo(["Automatic", "RTP events (RFC 4733)", "SIP INFO"], ["auto", "rfc4733", "info"]), "combo"); self.dtmf.setCurrentIndex(max(0, self.dtmf.findData(s.get("voip_dtmf", "auto")))); v.addWidget(field("Keypad tones (DTMF) sent as", self.dtmf))
        self.mic_dev = reg("voip_mic", combo([""]), "combo"); self.spk_dev = reg("voip_spk", combo([""]), "combo")
        v.addWidget(label("Sound devices", section=True)); v.addWidget(field("Microphone", self.mic_dev)); v.addWidget(field("Speakers / headset", self.spk_dev))
        rf = button("Refresh the list of devices"); rf.clicked.connect(lambda: self._fill_devices(True)); v.addWidget(rf)
        self.mic_gain = reg("voip_mic_gain", spin(0, 300, int(s.get("voip_mic_gain", 100)), suffix=" %", step=10), "int"); self.spk_vol = reg("voip_spk_vol", spin(0, 300, int(s.get("voip_spk_vol", 100)), suffix=" %", step=10), "int")
        self.ring_vol = reg("voip_ring_vol", spin(0, 100, int(s.get("voip_ring_vol", 50)), suffix=" %", step=10), "int"); self.jitter = reg("voip_jitter_ms", spin(20, 400, int(s.get("voip_jitter_ms", 60)), suffix=" ms", step=20), "int")
        r = hbox(s=8); r.addWidget(field("Microphone level", self.mic_gain)); r.addWidget(field("Speaker volume", self.spk_vol)); v.addLayout(r)
        r = hbox(s=8); r.addWidget(field("Ring volume", self.ring_vol)); r.addWidget(field("Audio delay (jitter buffer)", self.jitter)); v.addLayout(r)
        rk = list(RINGTONES); self.ringtone = reg("voip_ringtone", combo([RINGTONES[k][0] for k in rk] + ["My own sound file (WAV)"], rk + ["file"]), "combo")
        self.ringtone.setCurrentIndex(max(0, self.ringtone.findData(s.get("voip_ringtone", "classic"))))
        self.ring_file = reg("voip_ring_file", W.QLineEdit(s.get("voip_ring_file", "")), "text"); self.ring_file.setPlaceholderText(tr("A WAV file, used when 'My own sound file' is chosen"))
        rb = button("Browse…"); rb.clicked.connect(self._browse_ring); self.ring_play = button("Play", "primary"); self.ring_play.clicked.connect(self._play_ring)
        v.addWidget(label("Ringtone (incoming calls)", section=True)); rr = hbox(s=8); rr.addWidget(self.ringtone, 1); rr.addWidget(self.ring_play); v.addLayout(rr)
        fr = hbox(s=8); fr.addWidget(self.ring_file, 1); fr.addWidget(rb); v.addLayout(fr); self.ring_msg = note(""); v.addWidget(self.ring_msg)
        v.addWidget(note("Devices, codecs and the audio delay are used from the next call. The levels, the ringtone and the ring volume act at once.")); v.addStretch()
        # -- Calls
        v = add_tab("Calls")
        self.auto_answer = reg("voip_auto_answer", checkbox("Answer incoming calls automatically"), "bool"); self.auto_answer.setChecked(bool(s.get("voip_auto_answer", False)))
        self.auto_secs = reg("voip_auto_secs", spin(0, 60, int(s.get("voip_auto_secs", 3)), suffix=" s"), "int")
        self.dnd = reg("voip_dnd", checkbox("Do not disturb (callers hear busy; the call is listed as missed)"), "bool"); self.dnd.setChecked(bool(s.get("voip_dnd", False)))
        self.vm = reg("voip_vm", W.QLineEdit(s.get("voip_vm", "")), "text"); self.vm.setPlaceholderText("*97")
        v.addWidget(self.auto_answer); v.addWidget(field("Answer after", self.auto_secs)); v.addWidget(self.dnd); v.addWidget(field("Voicemail number", self.vm))
        self.vm_btn = button("Call voicemail"); v.addWidget(self.vm_btn)
        v.addWidget(note("These settings act at once.")); v.addStretch()
        # -- Advanced
        v = add_tab("Advanced")
        self.ua_name = reg("voip_ua", W.QLineEdit(s.get("voip_ua", "")), "text"); self.ua_name.setPlaceholderText("DigiConnect-VoIP"); v.addWidget(field("User-Agent (how the program introduces itself)", self.ua_name))
        self.trace = reg("voip_trace", checkbox("Write every SIP message to Diagnostics (passwords are hidden)"), "bool"); self.trace.setChecked(bool(s.get("voip_trace", False))); v.addWidget(self.trace)
        self.defaults_btn = button("Restore the network, audio, call and advanced settings to their defaults", "danger"); self.defaults_btn.clicked.connect(self._defaults); v.addWidget(self.defaults_btn)
        v.addWidget(note("The account (server, username, password), the people and the call list are not touched. Used from the next sign-in.")); v.addStretch()
        self._tab(0); self._loading = False; self._req_refresh(); self.refresh_gate()
        self.ctx.policy_changed.connect(self.refresh_gate); self.ctx.changed.connect(self.refresh_gate)
        QtCore.QTimer.singleShot(1500, lambda: self.acc.ensure_fresh(lambda: None))      # a waiting request / the linked account is looked at now (a lost link is found again)
        self._fill_devices(False)
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
        pe = panel("card"); ev = vbox(pe, m=(16, 14, 16, 14), s=8); root.addWidget(pe, 3)
        ev.addWidget(label("PEOPLE", section=True))
        self.people = W.QListWidget(); self.people.setIconSize(QtCore.QSize(14, 14)); self.people.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.people.setTextElideMode(Qt.TextElideMode.ElideRight); ev.addWidget(self.people, 3)
        self.people_note = label("", muted=True); self.people_note.setWordWrap(True); ev.addWidget(self.people_note)
        ev.addWidget(label("RECENT CALLS", section=True)); self.hist = W.QListWidget(); self.hist.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); ev.addWidget(self.hist, 2)
        br = hbox(s=6); self.add = button("Add"); self.edit = button("Edit"); self.rm = button("Remove"); br.addWidget(self.add, 1); br.addWidget(self.edit, 1); br.addWidget(self.rm, 1); ev.addLayout(br)
        for b in (self.add, self.edit, self.rm): b.setSizePolicy(W.QSizePolicy.Policy.Ignored, b.sizePolicy().verticalPolicy())      # the three share the width equally whatever their texts are (on Windows the fonts made them differ)     # fixed at the very bottom of the panel
        # wiring
        self.vm_btn.clicked.connect(self._voicemail); self.sign.clicked.connect(self._sign); self.call_btn.clicked.connect(self._call); self.hang.clicked.connect(self.ph.hangup); self.answer.clicked.connect(self.ph.answer); self.decline.clicked.connect(self.ph.reject)
        self.mute.toggled.connect(self.ph.set_muted); self.number.returnPressed.connect(self._call)
        self.add.clicked.connect(self._add); self.edit.clicked.connect(self._edit); self.rm.clicked.connect(self._remove); self.people.itemDoubleClicked.connect(self._dial_item)
        self.ph.registration.connect(self._on_reg); self.ph.call_changed.connect(self._on_call); self.ph.presence_changed.connect(lambda _e: self.refresh_people()); self.ph.history_changed.connect(self.refresh_history)
        self.ph.dtmf_in.connect(lambda c, d: self.who.setText(tr("Key pressed by the other side:") + " " + d))
        self.tick = QtCore.QTimer(self); self.tick.setInterval(150); self.tick.timeout.connect(self._tick); self.tick.start()
        self._on_reg(self.ph.reg_state, self.ph.reg_text); self.refresh_people(); self.refresh_history(); self._sync_buttons()

    # ---- account
    # ---- tabs and settings
    def _tab(self, i: int):
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.sections): b.setChecked(k == i)

    def _fill_devices(self, force: bool):
        """The sound devices the system reports (the same list as Settings). The first entry means 'as chosen in Settings'."""
        from .. import audio_devices as AD
        try: ins, outs, err = AD.list_devices(force)
        except Exception as ex: ins, outs, err = [], [], str(ex)
        s = self.ctx.store.settings; self._loading = True
        try:
            for combo, names, key in ((self.mic_dev, ins, "voip_mic"), (self.spk_dev, outs, "voip_spk")):
                combo.blockSignals(True); combo.clear(); combo.addItem(tr("As chosen in Settings"), "")
                for n in names: combo.addItem(str(n), str(n))
                cur = s.get(key, "")
                if cur and combo.findData(cur) < 0: combo.addItem(cur, cur)                         # a device that is not plugged in now stays chosen
                combo.setCurrentIndex(max(0, combo.findData(cur))); combo.blockSignals(False)
        finally: self._loading = False

    def _read(self) -> dict:
        out = {}
        for key, (w, kind) in self.ctl.items():
            if kind == "text": out[key] = w.text().strip()
            elif kind == "int": out[key] = int(w.value())
            elif kind == "bool": out[key] = bool(w.isChecked())
            elif kind == "combo": out[key] = w.currentData() if w.currentData() is not None else w.currentText()
        try: out["voip_port"] = int(out.get("voip_port") or 5060)
        except (TypeError, ValueError): out["voip_port"] = 5060
        if not 0 < out["voip_port"] < 65536: out["voip_port"] = 5060
        out["voip_transport"] = str(out.get("voip_transport", "UDP")).lower()
        out["voip_name"] = self.name.text().strip(); out["voip_pw"] = self.pw.text() if self.remember.isChecked() else ""
        if out.get("voip_rtp_hi", 0) <= out.get("voip_rtp_lo", 0): out["voip_rtp_lo"], out["voip_rtp_hi"] = 12000, 12999
        if not (out.get("voip_pcmu") or out.get("voip_pcma")): out["voip_pcmu"] = out["voip_pcma"] = True            # at least one codec must stay on
        return out

    def save_account(self):
        if getattr(self, "_loading", True): return
        self.ctx.store.settings.update(self._read()); self.ctx.store.save_settings()

    # ---- the Admin's server can close (or open) the phone for this installation
    def refresh_gate(self):
        pol = self.ctx.policy; closed = not pol.allows("VoIP")
        self.closed_note.setVisible(closed); self.body.setEnabled(not closed)
        if closed: self.closed_txt.setText("⚠  " + tr(pol.reason("VoIP")))
        pi = pol.paid_info("VoIP") if closed else None
        self.closed_btn.setVisible(bool(pi))
        if pi:
            from ..license import with_amount
            self.closed_btn.setText(with_amount("♥ Buy" if pi.get("offer") == "buy" else "♥ Donate", pi))

    def _pay_extra(self):
        from .license_dialog import open_donate
        open_donate(self.ctx.policy.paid_link("VoIP"))

    # ---- asking the Admin for an account (see voip/signup.py)
    def _note(self, text: str):
        self.req_lbl.setText(tr(text)); self._req_refresh()

    def _req_refresh(self):
        st = self.ctx.store.settings; state = self.acc.state(); pend = state == "pending"; has = state == "linked"; linked = has and not self.acc.released()
        self.req_btn.setVisible(not pend and not has); self.req_chk.setVisible(pend or has)
        self.req_chk.setText(tr("Check the request") if pend else tr("Check the account now"))
        self.req_btn.setText(tr("Request an account again") if state == "rejected" else tr("I don't have an account: request one"))
        for w in (self.server, self.port, self.user, self.auth_user, self.domain, self.pw, self.transport):           # the Admin's server decides these: grey, and an edit would be overwritten at the next check anyway
            if isinstance(w, W.QLineEdit): w.setReadOnly(linked)
            else: w.setEnabled(not linked)
            w.setProperty("locked", linked); w.setToolTip(tr("Set by the Admin") if linked else ""); w.style().unpolish(w); w.style().polish(w)
        if not self.req_lbl.text():
            if pend: self.req_lbl.setText(tr("Your request is waiting for the Admin. This page checks by itself every few minutes."))
            elif linked: self.req_lbl.setText(tr("This account comes from the Admin: the extension and the password are kept up to date by themselves."))
            elif has: self.req_lbl.setText(tr("The Admin has let you use another server for now: the fields are unlocked and the details saved here stay as they are."))
        b = self.acc.blocked()
        if linked and b[0]: self.req_lbl.setText("⚠  " + self.acc.block_text())
        self.req_lbl.setVisible(bool(self.req_lbl.text()))
        self._acc_state_refresh(state, linked, b[0])

    def _acc_state_refresh(self, state: str, linked: bool, blocked: bool):
        """One line at the top of Account: green when the account made by the Admin is ready for use, red when it is blocked or refused, amber while it waits."""
        ext = str(self.ctx.store.settings.get("voip_user", ""))
        if state == "linked" and not linked: tone, txt = "muted", tr("Another server is in use for now (the Admin has let you go)")
        elif linked and blocked: tone, txt = "red", tr("The account is blocked by the Admin")
        elif linked: tone, txt = "green", tr("Your account is ready for use") + (" — " + tr("extension") + " " + ext if ext else "")
        elif state == "pending": tone, txt = "amber", tr("Your request is waiting for the Admin")
        elif state == "rejected": tone, txt = "red", tr("The request was not approved")
        else: tone, txt = "", ""
        self.acc_state.setText(("●  " + txt) if txt else ""); self.acc_state.setVisible(bool(txt))
        self.acc_state.setProperty("accstate", tone); self.acc_state.style().unpolish(self.acc_state); self.acc_state.style().polish(self.acc_state)

    def _load_from_settings(self):
        """The account in the settings was replaced by what the server sent: the fields show it."""
        a = self.ctx.store.settings; self._loading = True
        try:
            self.user.setText(str(a.get("voip_user", ""))); self.pw.setText(str(a.get("voip_pw", ""))); self.server.setText(str(a.get("voip_server", "")))
            self.port.setText(str(a.get("voip_port") or 5060)); self.transport.setCurrentText(str(a.get("voip_transport", "udp")).upper()); self.domain.setText(str(a.get("voip_domain", ""))); self.auth_user.setText(str(a.get("voip_auth_user", "")))
            self.remember.setChecked(bool(a.get("voip_remember", True))); self.auto.setChecked(bool(a.get("voip_auto", False)))
        finally: self._loading = False

    def _req_dialog(self):
        st = self.ctx.store.settings
        d = W.QDialog(self); d.setWindowTitle(tr("Request a VoIP account")); v = vbox(d, m=(16, 14, 16, 14), s=8); d.setMinimumWidth(480)
        def note(text):
            l = label(text, muted=True); l.setWordWrap(True); return l
        v.addWidget(note("Your request goes to the Admin of the HELLAS Zone VoIP server, who creates the account and approves it. When he does, this program receives the extension and the password by itself."))
        n = W.QLineEdit(st.get("voip_name") or st.get("op_name", "")); cs = W.QLineEdit(st.get("callsign", "")); want = W.QLineEdit(); msg = W.QPlainTextEdit(); msg.setFixedHeight(70)
        want.setPlaceholderText(tr("optional")); v.addWidget(field("Your name", n)); v.addWidget(field("Callsign", cs)); v.addWidget(field("Extension you would like (optional)", want)); v.addWidget(field("Message (optional)", msg))
        ok = checkbox(""); okt = label("I agree that my name and callsign are sent to the HELLAS Zone server only to answer this request"); okt.setWordWrap(True)
        okt.mousePressEvent = lambda e: ok.toggle(); okr = hbox(s=8); okr.addWidget(ok, 0, Qt.AlignmentFlag.AlignTop); okr.addWidget(okt, 1); v.addLayout(okr)      # a check box cannot wrap its text: the text is a label beside it
        err = label("", muted=True); err.setWordWrap(True); v.addWidget(err)
        bb = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Cancel); send = bb.addButton(tr("Send the request"), W.QDialogButtonBox.ButtonRole.AcceptRole); bb.rejected.connect(d.reject); v.addWidget(bb)
        self._req_form = dict(name=n, call=cs, want=want, msg=msg, consent=ok, err=err, dialog=d)

        def go():
            if not ok.isChecked(): err.setText(tr(signup.ERRORS["consent"])); return
            if not n.text().strip(): err.setText(tr(signup.ERRORS["name"])); return
            if not cs.text().strip(): err.setText(tr(signup.ERRORS["call"])); return
            send.setEnabled(False); err.setText(tr("Sending…"))
            f = dict(name=n.text().strip(), call=cs.text().strip(), want=want.text().strip(), msg=msg.toPlainText().strip(), lang=("el" if str(st.get("language", "")).lower().startswith(("el", "gr")) else "en"))
            def done(kind, res):
                if kind != "submit": return
                self.acc.finished.disconnect(done)
                if res[0] == "ok": d.accept()
                else: err.setText(tr(res[1].text) if res[1].code else tr("The server cannot be reached now:") + " " + res[1].text); send.setEnabled(True)
            self.acc.finished.connect(done); self.req_lbl.setText(""); self.acc.submit(**f)
        send.clicked.connect(go); d.exec()

    def _req_check(self, silent: bool):
        if not silent: self.req_lbl.setText(tr("Checking…")); self.req_lbl.show()
        self.acc.check(silent)

    def _changed(self):
        if getattr(self, "_loading", True): return
        self.save_account(); self.ph.apply_levels()

    def _browse_ca(self):
        f, _ = W.QFileDialog.getOpenFileName(self, tr("Certificate file of the server (.pem, optional)"), "", "Certificates (*.pem *.crt *.cer);;All files (*)")
        if f: self.tls_ca.setText(f); self._changed()

    def _browse_ring(self):
        f, _ = W.QFileDialog.getOpenFileName(self, tr("Ringtone (incoming calls)"), "", "WAV (*.wav)")
        if f: self.ring_file.setText(f); self.ringtone.setCurrentIndex(self.ringtone.findData("file")); self._changed()

    def _play_ring(self):
        key = self.ringtone.currentData(); path = self.ring_file.text().strip()
        if key == "file":
            from ..voip.phone import WavRing
            try: WavRing(path)
            except Exception as ex: self.ring_msg.setText(tr("This file cannot be used as a ringtone:") + f" {ex}"); return
        self.ring_msg.setText("")
        if not self.ph.preview_ring(key, path): self.ring_msg.setText(tr("The ring cannot be played now (a call is in progress, or the speakers are not available)."))

    def _defaults(self):
        from ..store import DEFAULTS
        keep = ("voip_released", "voip_server", "voip_port", "voip_transport", "voip_user", "voip_auth_user", "voip_domain", "voip_pw", "voip_name", "voip_remember", "voip_auto", "voip_contacts", "voip_history", "voip_req_id", "voip_req_token", "voip_req_state", "voip_req_reason", "voip_block", "voip_block_until", "voip_block_reason")
        s = self.ctx.store.settings
        for k, v in DEFAULTS.items():
            if k.startswith("voip_") and k not in keep: s[k] = v if not isinstance(v, (list, dict)) else type(v)(v)
        self.ctx.store.save_settings(); self._load_extra()

    def _load_extra(self):
        """Shows the stored values in the tabs (used after the defaults are restored)."""
        s = self.ctx.store.settings; self._loading = True
        try:
            for key, (w, kind) in self.ctl.items():
                if key in ("voip_server", "voip_port", "voip_transport", "voip_user", "voip_auth_user", "voip_domain", "voip_remember", "voip_auto"): continue
                v = s.get(key)
                if kind == "text": w.setText(str(v if v is not None else ""))
                elif kind == "int": w.setValue(int(v or 0))
                elif kind == "bool": w.setChecked(bool(v))
                elif kind == "combo": w.setCurrentIndex(max(0, w.findData(v)))
        finally: self._loading = False

    def _voicemail(self):
        if not self.ph.voicemail(): self.who.setText(tr("Sign in first, then enter a number") if self.ph.reg_state != "registered" else tr("Enter the voicemail number first"))

    def _sign(self):
        if self.ph.reg_state in ("registered", "registering"): self.ph.sign_out(); return
        def go(): self.save_account(); self.ph.sign_in(self.pw.text())
        self.acc.ensure_fresh(go)                                                      # first the newest details from the server (a new password, a block); if it cannot be reached the saved ones are used

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
            it = W.QListWidgetItem(f"{nm}{extra}   {c['number']}\n{reason(txt)}"); it.setIcon(dot(DOT.get(st, DOT['unknown']))); it.setData(Qt.ItemDataRole.UserRole, c["number"]); self.people.addItem(it)
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
            t = time.strftime("%d.%m %H:%M", time.localtime(e.get("t", 0))); dur = f"  ({e['secs'] // 60}:{e['secs'] % 60:02d})" if e.get("secs") else ""
            who = f"{e.get('name')}  {e.get('number')}" if e.get("name") else str(e.get("number"))
            it = W.QListWidgetItem(f"{sym.get(e.get('dir'), '')}  {who}\n{t}{dur}"); it.setData(Qt.ItemDataRole.UserRole, e.get("number")); self.hist.addItem(it)
        self.hist.itemDoubleClicked.connect(self._dial_item) if not getattr(self, "_h_conn", False) else None; self._h_conn = True
