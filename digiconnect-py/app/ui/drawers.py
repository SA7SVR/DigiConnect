"""Right-hand drawers: Settings (5 tabs) and New QSO form with drafts."""
from ..qt import QtWidgets as W, QtCore, Qt, Signal
from ..rules import valid_text_size, NETS
from ..theme import C
from .. import i18n
from ..i18n import tr
from .widgets import *
from .audioblock import AudioBlock
import json, zipfile, datetime as dt, platform


def _drawer_head(title, sub, close_cb):
    h = hbox(m=(16, 14, 16, 8)); t = vbox(s=2); a = label(title); a.setStyleSheet("font-size:18px;font-weight:700;"); t.addWidget(a); t.addWidget(label(sub, muted=True))
    h.addLayout(t); h.addStretch(); c = button("", "rail", "close"); c.setFixedSize(34, 34); c.clicked.connect(close_cb); h.addWidget(c); return h


class SettingsDrawer(W.QFrame):
    closed = Signal(); applied = Signal()

    def __init__(self, ctx):
        super().__init__(); self.setObjectName("drawer"); self.ctx = ctx; self.setFixedWidth(330); s = ctx.store.settings
        v = vbox(self, s=0); v.addLayout(_drawer_head("Settings", "DigiConnect · HELLAS Zone", self.closed.emit))
        tabs = hbox(m=(16, 0, 16, 6), s=6); self.tb = {}; self.stack = W.QStackedWidget()
        grid = W.QGridLayout(); grid.setSpacing(6)
        for i, n in enumerate(["My station", "Radio networks", "Audio", "Callbooks", "Backup"]):
            b = button(n, "seg", checkable=True); b.clicked.connect(lambda _, i=i: self._tab(i)); self.tb[i] = b; grid.addWidget(b, 0 if i < 3 else 1, i if i < 3 else i - 3, 1, 1 if i < 3 else 1)
        gw = W.QWidget(); gw.setLayout(grid); gw.layout().setContentsMargins(16, 0, 16, 6); v.addWidget(gw)
        # -- My station
        self.f = {}
        def le(k, ph=""):
            e = W.QLineEdit(str(s.get(k, ""))); e.setPlaceholderText(ph); self.f[k] = e; return e
        p1 = W.QWidget(); l1 = vbox(p1, m=(16, 4, 16, 4), s=8)
        l1.addWidget(field("Callsign", le("callsign"))); r = hbox(); r.addWidget(field("Grid locator", le("locator"))); r.addWidget(field("Module", le("module"))); l1.addLayout(r)
        l1.addWidget(field("Equipment", le("equipment"))); l1.addWidget(field("Radio message", le("radio_message")))
        self.lang = W.QComboBox(); self.lang.addItems(list(i18n.LANGS)); self.lang.setCurrentText(s["language"]); l1.addWidget(field("Language", self.lang))
        self.theme = W.QComboBox(); self.theme.addItem(tr("Dark"), "dark"); self.theme.addItem(tr("Light"), "light"); i18n.combo_item(self.theme, 0, "Dark"); i18n.combo_item(self.theme, 1, "Light"); self.sync_theme(); l1.addWidget(field("Theme", self.theme))
        self.size = W.QSpinBox(); self.size.setRange(11, 20); self.size.setValue(s["text_size"]); self.ptt = W.QComboBox(); self.ptt.addItems(["60 s", "120 s", "180 s"]); self.ptt.setCurrentText(f"{s['max_ptt']} s")
        r2 = hbox(); r2.addWidget(field("Text size", self.size)); r2.addWidget(field("Maximum PTT duration (s)", self.ptt)); l1.addLayout(r2)
        self.favview = W.QComboBox(); self.favview.addItem(tr("Full cards"), "Full cards"); self.favview.addItem(tr("Names only"), "Names only"); i18n.combo_item(self.favview, 0, "Full cards"); i18n.combo_item(self.favview, 1, "Names only"); self.favview.setCurrentIndex(max(0, self.favview.findData(s["fav_view"]))); l1.addWidget(field("Favorites display", self.favview))
        l1.addWidget(label("PROFILES", section=True)); pr = hbox(); self.prof = W.QComboBox(); self.prof.addItem("—"); self.prof.addItems(sorted(s.get("profiles", {})))
        self.load = button("Load"); pr.addWidget(self.prof, 1); pr.addWidget(self.load); l1.addLayout(pr)
        self.pname = W.QLineEdit(); l1.addWidget(field("Profile name", self.pname)); self.saveprof = button("Save profile"); l1.addWidget(self.saveprof, 0, Qt.AlignmentFlag.AlignLeft); l1.addStretch()
        # -- Radio networks
        p2 = W.QWidget(); l2 = vbox(p2, m=(16, 4, 16, 4), s=8); l2.addWidget(label("DMR", section=True))
        r = hbox(); r.addWidget(field("DMR ID (also used for P25)", le("dmr_id"))); r.addWidget(field("ESSID", le("essid"))); l2.addLayout(r); l2.addWidget(field("NXDN ID", le("nxdn_id")))
        l2.addWidget(field("DMR master server (host)", le("dmr_server", "hostname"))); r = hbox(); r.addWidget(field("DMR master port", le("dmr_port")))
        self.slot = W.QComboBox(); self.slot.addItems(["1", "2"]); self.slot.setCurrentText(str(s["slot"])); r.addWidget(field("Time slot", self.slot)); l2.addLayout(r)
        l2.addWidget(field("Color code", le("cc"))); self.dpw = W.QLineEdit(); self.dpw.setEchoMode(W.QLineEdit.EchoMode.Password); l2.addWidget(field("Password", self.dpw))
        l2.addWidget(label("Passwords are kept for the current session only in this build (not written to disk).", muted=True))
        l2.addWidget(label("These fields are for the DMR master only. Every other station shows its own server and port on its page (Selected station › Server).", muted=True)); l2.addStretch()
        # -- Audio
        p3 = W.QWidget(); l3 = vbox(p3, m=(16, 4, 16, 4), s=8)
        self.audio = AudioBlock(ctx); l3.addWidget(self.audio)
        self.duck = checkbox("Lower other channels while transmitting"); self.duck.setChecked(s["duck"]); l3.addWidget(self.duck)
        l3.addWidget(label("RECORDINGS", section=True)); self.recp = label(s.get("rec_path") or str(ctx.store.root / "Recordings"), muted=True); self.recp.setWordWrap(True); l3.addWidget(self.recp)
        self.choose = button("Choose"); l3.addWidget(self.choose, 0, Qt.AlignmentFlag.AlignLeft); l3.addStretch()
        # -- Callbooks / Backup
        p4 = W.QWidget(); l4 = vbox(p4, m=(16, 4, 16, 4), s=8); self.pref = W.QComboBox(); self.pref.addItems(["QRZ.com", "QRZCQ.com", "RadioID"]); l4.addWidget(field("Preferred callbook", self.pref))
        l4.addWidget(label("Callbook lookups are not connected in this build.", muted=True)); l4.addStretch()
        p5 = W.QWidget(); l5 = vbox(p5, m=(16, 4, 16, 4), s=8); self.bk = button("Back up application"); self.rs = button("Restore a backup"); self.dg = button("Export diagnostics")
        for b in (self.bk, self.rs, self.dg): l5.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        l5.addWidget(label("Backup is a ZIP of settings, favorites and the journal. Restoring replaces them.", muted=True)); l5.addStretch()
        for p in (p1, p2, p3, p4, p5):
            sc = W.QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(p); self.stack.addWidget(sc)
        v.addWidget(self.stack, 1)
        foot = hbox(m=(16, 8, 16, 14), s=8); self.save = button("Save", "primary"); cl = button("Close"); foot.addWidget(self.save); foot.addWidget(cl); foot.addStretch(); v.addLayout(foot)
        cl.clicked.connect(self.closed.emit); self.save.clicked.connect(self._save); self.saveprof.clicked.connect(self._saveprof); self.load.clicked.connect(self._load)
        self.bk.clicked.connect(self._backup); self.rs.clicked.connect(self._restore); self.dg.clicked.connect(self._diag); self.choose.clicked.connect(self._choose)
        self._tab(0)

    def sync_theme(self):
        self.theme.setCurrentIndex(max(0, self.theme.findData(self.ctx.store.settings.get("theme", "dark"))))

    def _tab(self, i):
        self.stack.setCurrentIndex(i)
        for k, b in self.tb.items(): b.setChecked(k == i)
    def open_tab(self, i): self._tab(i)

    def _choose(self):
        d = W.QFileDialog.getExistingDirectory(self, tr("Recordings folder"))
        if d: self.recp.setText(d); self.ctx.store.settings["rec_path"] = d

    def _collect(self):
        s = self.ctx.store.settings
        self.ctx.set_dmr_password(self.dpw.text())
        for k, e in self.f.items():
            val = e.text().strip()
            if k in ("dmr_port", "cc"):
                if val.isdigit(): s[k] = int(val)          # keep the previous value if not numeric
            elif k in ("callsign", "locator"):
                s[k] = val.upper()
            else:
                s[k] = val
        s.update(language=self.lang.currentText(), theme=self.theme.currentData() or "dark", text_size=self.size.value(), max_ptt=int(self.ptt.currentText().split()[0]), fav_view=self.favview.currentData() or "Full cards",
                 slot=int(self.slot.currentText()), duck=self.duck.isChecked())

    def _save(self):
        self._collect(); s = self.ctx.store.settings
        if not valid_text_size(s["text_size"]): self.ctx.toast.emit("Text size must be between 11 and 20 pixels."); return
        self.ctx.store.save_settings(); self.ctx.rules.ducking = s["duck"]
        if not self.ctx.rules.ptt: self.ctx.rules.limit = s["max_ptt"]
        self.applied.emit(); self.ctx.changed.emit(); self.ctx.toast.emit("Settings saved")

    def _saveprof(self):
        n = self.pname.text().strip()
        if not n: self.ctx.toast.emit("Enter a profile name first."); return
        self._collect(); s = self.ctx.store.settings; prof = {k: v for k, v in s.items() if k not in ("profiles", "mic", "speakers")}
        s.setdefault("profiles", {})[n] = prof; self.ctx.store.save_settings()
        if self.prof.findText(n) < 0: self.prof.addItem(n)
        self.ctx.toast.emit(f"Profile '{n}' saved (passwords are never copied into profiles)")

    def _load(self):
        n = self.prof.currentText(); p = self.ctx.store.settings.get("profiles", {}).get(n)
        if not p: return
        self.ctx.stop_all(); self.ctx.store.settings.update(p); self.ctx.store.save_settings()
        for k, e in self.f.items(): e.setText(str(self.ctx.store.settings.get(k, "")))
        self.applied.emit(); self.ctx.toast.emit(f"Profile '{n}' loaded. Active connections were stopped; check network, devices and credentials.")

    def _backup(self):
        fn, _ = W.QFileDialog.getSaveFileName(self, tr("Backup"), f"DigiConnect-backup-{dt.date.today()}.zip")
        if not fn: return
        self.ctx.store.db.commit()
        with zipfile.ZipFile(fn, "w", zipfile.ZIP_DEFLATED) as z:
            for f in (self.ctx.store.settings_file, self.ctx.store.fav_file, self.ctx.store.root / "journal.sqlite3"):
                if f.exists(): z.write(f, f.name)
        self.ctx.toast.emit("Backup written")

    def _restore(self):
        fn, _ = W.QFileDialog.getOpenFileName(self, tr("Restore a backup"), "", "ZIP (*.zip)")
        if not fn: return
        if W.QMessageBox.question(self, tr("Restore"), tr("Restoring replaces settings, favorites and the journal. Continue?")) != W.QMessageBox.StandardButton.Yes: return
        self.ctx.stop_all(); root = self.ctx.store.root; stamp = root / f"BeforeRestore_{dt.datetime.now():%Y%m%d_%H%M%S}"; stamp.mkdir()
        self.ctx.store.db.close()
        for n in ("settings.json", "favorites.json", "journal.sqlite3"):
            if (root / n).exists(): (root / n).replace(stamp / n)
        with zipfile.ZipFile(fn) as z: z.extractall(root)
        W.QMessageBox.information(self, tr("Restore"), tr("Backup restored. Please restart DigiConnect."))

    def _diag(self):
        fn, _ = W.QFileDialog.getSaveFileName(self, tr("Export diagnostics"), "digiconnect-diagnostics.json")
        if not fn: return
        r = self.ctx.rules; d = dict(product="DigiConnect", utc=dt.datetime.now(dt.timezone.utc).isoformat(), os=platform.platform(), engine=self.ctx.engine.name,
                                    mode=r.mode.value, receivers=[(x.target.net, x.target.id) for x in r.rx], tx_connected=r.tx_connected,
                                    hostlists=self.ctx.hosts.status, log=diag.tail(300).splitlines())
        open(fn, "w").write(json.dumps(d, indent=1)); self.ctx.toast.emit("Diagnostics exported (no passwords)")


from .. import diag


class QsoDrawer(W.QFrame):
    closed = Signal(); saved = Signal()

    def __init__(self, ctx):
        super().__init__(); self.setObjectName("drawer"); self.ctx = ctx; self.setFixedWidth(330); self.editing = None
        v = vbox(self, s=0); v.addLayout(_drawer_head("New QSO", "Review the details before saving.", self.closed.emit))
        body = W.QWidget(); b = vbox(body, m=(16, 4, 16, 4), s=8); sc = W.QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(body); v.addWidget(sc, 1)
        self.w = {}
        def le(k): e = W.QLineEdit(); self.w[k] = e; return e
        b.addWidget(field("Callsign", le("callsign")))
        r = hbox(); r.addWidget(field("Start UTC", le("start_utc"))); r.addWidget(field("End UTC", le("end_utc"))); b.addLayout(r)
        self.sys = W.QComboBox(); self.sys.addItems(list(NETS)); r = hbox(); r.addWidget(field("System", self.sys)); r.addWidget(field("TG / reflector / room", le("dest"))); b.addLayout(r)
        b.addWidget(field("Name", le("name")))
        for pair in (("country", "Country", "qth", "QTH / city"), ("grid", "Grid locator", "band", "Band"), ("freq", "Frequency MHz", "equipment", "Equipment"), ("rst_s", "RST sent", "rst_r", "RST received")):
            r = hbox(); r.addWidget(field(pair[1], le(pair[0]))); r.addWidget(field(pair[3], le(pair[2]))); b.addLayout(r)
        self.notes = W.QPlainTextEdit(); self.notes.setFixedHeight(80); b.addWidget(field("Personal notes", self.notes))
        self.src = label("Source: Manual entry\nYour manual corrections are preserved.", muted=True); b.addWidget(self.src)
        r = hbox(); self.cb = button("Fill from callbook"); self.hist = button("Contact history"); r.addWidget(self.cb); r.addWidget(self.hist); b.addLayout(r)
        r = hbox(); self.drafts = W.QComboBox(); self.drafts.addItem(tr("Saved drafts…")); i18n.combo_item(self.drafts, 0, "Saved drafts…"); self.resume = button("Resume"); r.addWidget(self.drafts, 1); r.addWidget(self.resume); b.addLayout(r); b.addStretch()
        foot = hbox(m=(16, 8, 16, 14), s=8); self.save = button("Save", "primary"); self.next = button("Next contact"); foot.addWidget(self.save); foot.addWidget(self.next); foot.addStretch(); v.addLayout(foot)
        self.cb.clicked.connect(lambda: ctx.toast.emit("Callbook lookups are not connected in this build. Enter the details manually; nothing is invented."))
        self.hist.clicked.connect(self._history); self.save.clicked.connect(self._save); self.next.clicked.connect(self._next); self.resume.clicked.connect(self._resume)
        self.parked: list[dict] = []; ctx.changed.connect(lambda: None)

    def prepare(self, t=None):
        """Open a draft. An unsaved active draft is protected (parked), not silently replaced."""
        cur = self.read()
        if self.editing is None and (cur["callsign"] or cur["notes"]): self.parked.append(cur); self._drafts()
        self.clear(); now = self.ctx.utc_now().strftime("%Y-%m-%dT%H:%M:%S"); s = self.ctx.store.settings
        self.w["start_utc"].setText(now); self.w["equipment"].setText(s.get("equipment", "")); self.w["grid"].setText("")
        t = t or self.ctx.selected
        if t: self.sys.setCurrentText(t.net); self.w["dest"].setText(t.id)

    def clear(self):
        for e in self.w.values(): e.clear()
        self.notes.clear(); self.editing = None

    def read(self):
        d = {k: e.text().strip() for k, e in self.w.items()}; d["system"] = self.sys.currentText(); d["notes"] = self.notes.toPlainText().strip(); return d

    def _drafts(self):
        self.drafts.clear(); self.drafts.addItem(tr("Saved drafts…")); i18n.combo_item(self.drafts, 0, "Saved drafts…")
        for d in self.parked: self.drafts.addItem(f"{d['callsign'] or '(no call)'} · {d['start_utc']}")

    def _resume(self):
        i = self.drafts.currentIndex() - 1
        if i < 0: return
        cur = self.read()
        if cur["callsign"]: self.parked.append(cur)
        d = self.parked.pop(i); self.clear(); [self.w[k].setText(d.get(k, "")) for k in self.w]; self.sys.setCurrentText(d["system"]); self.notes.setPlainText(d["notes"]); self._drafts()

    def _history(self):
        c = self.w["callsign"].text().strip()
        rows = self.ctx.store.search_qso(c) if c else []
        W.QMessageBox.information(self, tr("Contact history"), "\n".join(f"{r['start_utc']}  {r['system']}  {r['dest']}" for r in rows[:15]) or tr("No earlier contacts."))

    def _save(self):
        d = self.read(); cs = d["callsign"].upper()
        import re
        if not re.fullmatch(r"[A-Z0-9/]{3,15}", cs) or not re.search(r"\d", cs): self.ctx.toast.emit("Enter a valid callsign before saving."); return
        d["callsign"] = cs
        try: s = dt.datetime.fromisoformat(d["start_utc"])
        except ValueError: self.ctx.toast.emit("Start UTC must look like 2026-11-11T14:30:00."); return
        if d["end_utc"]:
            try:
                if dt.datetime.fromisoformat(d["end_utc"]) < s: self.ctx.toast.emit("End UTC must not precede start UTC."); return
            except ValueError: self.ctx.toast.emit("End UTC must look like 2026-11-11T14:35:00."); return
        if d["grid"] and not re.fullmatch(r"[A-Ra-r]{2}\d{2}([A-Xa-x]{2}(\d{2})?)?", d["grid"]): self.ctx.toast.emit("The locator is not a valid Maidenhead locator."); return
        if d["freq"]:
            try:
                if float(d["freq"]) <= 0: raise ValueError
            except ValueError: self.ctx.toast.emit("Frequency must be a positive value in MHz."); return
        near = [r for r in self.ctx.store.search_qso(cs, d["system"]) if abs((dt.datetime.fromisoformat(r["start_utc"]) - s).total_seconds()) <= 120]
        if near and W.QMessageBox.question(self, tr("Possible duplicate"), tr(f"{cs} on {d['system']} was already saved within two minutes of this time. Save both entries?")) != W.QMessageBox.StandardButton.Yes: return
        self.ctx.store.add_qso(d); self.clear(); self.saved.emit(); self.ctx.toast.emit(f"QSO with {cs} saved")

    def _next(self):
        d = self.read()
        if d["callsign"] and W.QMessageBox.question(self, tr("Next contact"), tr("The current entry is not saved. Discard it and prepare the next contact?")) != W.QMessageBox.StandardButton.Yes: return
        self.prepare()
