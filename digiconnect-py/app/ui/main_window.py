from datetime import datetime
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from ..theme import C, qss
from ..rules import NETS
from ..context import Ctx
from .widgets import *
from .icons import icon, dot
from ..theme import NET_COLOR
from .workspace import Workspace
from .favorites import Favorites
from .qsolog import QsoLog
from .controls import Dock, Mixer
from .drawers import SettingsDrawer, QsoDrawer
from pathlib import Path

LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
RAIL = [("favorites", "grid", "My favorites"), ("newqso", "plus", "New QSO"), ("log", "doc", "QSO log"), ("analysis", "bars", "Log analysis"),
        ("heard", "clock", "Last heard"), ("mixer", "headphones", "Audio mixer"), ("rec", "circle", "Recordings")]


class Toast(W.QLabel):
    def __init__(self, parent):
        super().__init__(parent); self.setStyleSheet(f"background:#241f4d;border:1px solid {C['accent']};border-radius:10px;padding:10px 16px;")
        self.setWordWrap(True); self.hide(); self.t = QtCore.QTimer(self); self.t.setSingleShot(True); self.t.timeout.connect(self.hide)

    def show_msg(self, text):
        self.setText(text); self.setFixedWidth(min(520, self.parent().width() - 40)); self.adjustSize()
        self.move((self.parent().width() - self.width()) // 2, self.parent().height() - self.height() - 110); self.show(); self.raise_(); self.t.start(5000)


class MainWindow(W.QMainWindow):
    def __init__(self, ctx: Ctx | None = None):
        super().__init__(); self.ctx = ctx or Ctx(); self.setWindowTitle("DigiConnect · HELLAS Zone"); self.resize(1500, 900); self.setMinimumSize(1100, 700)
        if LOGO.exists(): self.setWindowIcon(QtGui.QIcon(str(LOGO)))
        root = W.QWidget(); root.setObjectName("root"); self.setCentralWidget(root); outer = vbox(root, s=0)
        body = hbox(s=0); outer.addLayout(body, 1)
        # rail
        rail = W.QFrame(); rail.setObjectName("rail"); rail.setFixedWidth(72); rv = vbox(rail, m=(12, 14, 12, 14), s=8)
        lg = W.QLabel(); lg.setPixmap(QtGui.QPixmap(str(LOGO)).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)); lg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rv.addWidget(lg); rv.addSpacing(10); self.rail_btn = {}
        def rb(key, ic, tip):
            b = button("", "rail", checkable=True, tip=tip); b.setIcon(icon(ic)); b.setIconSize(QtCore.QSize(22, 22)); b.setFixedSize(46, 42); b.clicked.connect(lambda _, k=key: self.nav(k)); self.rail_btn[key] = b; return b
        for k, ic, tip in RAIL: rv.addWidget(rb(k, ic, tip), 0, Qt.AlignmentFlag.AlignHCenter)
        rv.addStretch()
        for k, ic, tip in (("updates", "download", "Updates"), ("help", "help", "Help"), ("settings", "gear", "Settings")): rv.addWidget(rb(k, ic, tip), 0, Qt.AlignmentFlag.AlignHCenter)
        self.avatar = W.QLabel("SA"); self.avatar.setFixedSize(36, 36); self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setStyleSheet(f"background:#26305f;border-radius:18px;font-weight:700;"); rv.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(rail)
        # centre column
        col = vbox(s=0); body.addLayout(col, 1)
        top = W.QFrame(); top.setObjectName("topbar"); top.setFixedHeight(64); th = hbox(top, m=(24, 8, 20, 8), s=14)
        th.addStretch()
        self.clock = label(""); self.clock.setAlignment(Qt.AlignmentFlag.AlignRight); th.addWidget(self.clock)
        self.callsign = label(""); self.callsign.setStyleSheet(f"color:{C['accent']};font-weight:700;"); th.addWidget(self.callsign)
        self.set_top = button("Settings", "", "gear"); th.addWidget(self.set_top); col.addWidget(top)
        # head (page title + tabs) – used by workspace pages
        self.head = W.QWidget(); hv = vbox(self.head, m=(24, 14, 24, 8), s=8)
        hr = hbox(); tl = vbox(s=2); self.title = label(""); self.title.setStyleSheet("font-size:26px;font-weight:700;"); tl.addWidget(self.title)
        self.subtitle = label("", muted=True); tl.addWidget(self.subtitle); hr.addLayout(tl); hr.addStretch()
        self.h_nq = button("New QSO", "", "plus"); self.h_set = button("Settings", "", "gear"); self.h_add = button("☆ Add favorite", "primary"); hr.addWidget(self.h_nq); hr.addWidget(self.h_add); hr.addWidget(self.h_set); hv.addLayout(hr)
        tabs = hbox(s=10); self.tabs = {}
        for k in ("favorites", *NETS):
            b = button("My favorites" if k == "favorites" else k, "tab", checkable=True); b.clicked.connect(lambda _, k=k: self.nav("favorites" if k == "favorites" else "net:" + k)); self.tabs[k] = b; tabs.addWidget(b)
        tabs.addStretch(); hv.addLayout(tabs); col.addWidget(self.head)
        # pages + right drawers
        mid = hbox(s=0); col.addLayout(mid, 1)
        self.pages = W.QStackedWidget(); pw = W.QWidget(); pl = vbox(pw, m=(24, 4, 24, 10)); pl.addWidget(self.pages); mid.addWidget(pw, 1)
        self.settings = SettingsDrawer(self.ctx); self.qdrawer = QsoDrawer(self.ctx); self.settings.hide(); self.qdrawer.hide(); mid.addWidget(self.settings); mid.addWidget(self.qdrawer)
        self.favs = Favorites(self.ctx, self.open_qso); self.log = QsoLog(self.ctx, self.open_qso)
        self.ws = {n: Workspace(self.ctx, n, self.open_qso) for n in NETS}
        self.pages.addWidget(self.favs); self.pages.addWidget(self.log)
        for n in NETS: self.pages.addWidget(self.ws[n])
        self.mixer = Mixer(self.ctx); self.dock = Dock(self.ctx, lambda: None)
        col.addWidget(self.mixer); col.addWidget(self._pad(self.dock))
        foot = W.QFrame(); foot.setObjectName("footer"); foot.setFixedHeight(28); fh = hbox(foot, m=(24, 0, 24, 0))
        self.foot_l = label("DigiConnect · HELLAS Zone · Public activity depends on information available from each network. Engine: " + self.ctx.engine.name); fh.addWidget(self.foot_l); fh.addStretch()
        self.lang = label(self.ctx.store.settings["language"]); fh.addWidget(self.lang); outer.addWidget(foot)
        self.toast = Toast(root); self.ctx.toast.connect(self.toast.show_msg)
        # wiring
        self.mixer.hide_requested.connect(lambda: self.mixer.setVisible(False)); self.h_nq.clicked.connect(self.open_qso); self.h_set.clicked.connect(lambda: self.open_settings())
        self.set_top.clicked.connect(lambda: self.open_settings()); self.settings.closed.connect(self._close_drawers); self.qdrawer.closed.connect(self._close_drawers)
        self.qdrawer.saved.connect(self.log.reload); self.settings.applied.connect(self.apply_settings)
        self.ctx.changed.connect(self._sync_chrome); self.ctx.need_endpoint.connect(self._need_endpoint)
        t = QtCore.QTimer(self); t.timeout.connect(self._clock); t.start(1000)
        QtGui.QShortcut(QtGui.QKeySequence("F4"), self, activated=self._mute_all)
        QtGui.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._f2)
        self.current = "net:DMR"; self.apply_settings(); self.nav("net:DMR"); self._clock()

    @staticmethod
    def _pad(w):
        f = W.QWidget(); l = vbox(f, m=(24, 6, 24, 8)); l.addWidget(w); return f

    # ---- navigation -------------------------------------------------------
    def nav(self, key):
        if key == "settings": self.open_settings(); return
        if key == "newqso": self.open_qso(); return
        if key == "mixer": self.mixer.setVisible(not self.mixer.isVisible()); self._sync_chrome(); return
        if key in ("analysis",): self.nav("log"); self.log._analysis(); return
        if key in ("heard", "rec", "updates", "help"):
            msg = {"heard": "Last heard appears in the right column of each network page when a station is received.", "rec": "Recordings: none yet. Recording needs a running receiver (engine step).",
                   "updates": "Updates: open the release page for DigiConnect to check for a newer build.", "help": "Help: see docs/SPEC.md (operating rules) in the source package."}[key]
            self.ctx.toast.emit(msg); return
        self.current = key
        if key == "favorites": self.pages.setCurrentWidget(self.favs); self.favs.rebuild()
        elif key == "log": self.pages.setCurrentWidget(self.log); self.log.reload()
        elif key.startswith("net:"):
            n = key[4:]; self.pages.setCurrentWidget(self.ws[n]); self.ctx.last_net = n
        self._sync_chrome()

    def _sync_chrome(self):
        k, ws = self.current, self.current.startswith("net:")
        self.head.setVisible(k == "favorites" or ws)
        net = k[4:] if ws else None
        self.title.setText("My favorites" if k == "favorites" else (f"Radio workspace  {net}" if ws else ""))
        self.title.setTextFormat(Qt.TextFormat.RichText)
        if ws: self.title.setText(f"Radio workspace <span style='color:{__import__('app.theme', fromlist=['NET_COLOR']).NET_COLOR[net]}'>{net}</span>")
        for t, b in self.tabs.items(): b.setChecked((t == "favorites" and k == "favorites") or (t == net))
        for t, b in self.tabs.items():
            if t != "favorites": b.setText(t); b.setIcon(dot(NET_COLOR[t])); b.setIconSize(QtCore.QSize(10, 10))
        self.subtitle.setText("All your networks. One radio workspace." if k == "favorites" else "Choose a station, then Listen. Connect transmission separately to participate.")
        self.h_add.setVisible(k == "favorites")
        self.tabs["favorites"].setText(f"My favorites   {len(self.ctx.store.favorites)}")
        for key, b in self.rail_btn.items():
            b.setChecked((key == "favorites" and k == "favorites") or (key == "log" and k == "log") or (key == "mixer" and self.mixer.isVisible()))
        self.dock.setVisible(not ws and k != "favorites" or k in ("favorites", "log")); self.dock.parentWidget().setVisible(k in ("favorites", "log"))
        self.h_nq.setVisible(ws or k == 'favorites'); self.h_set.setVisible(ws)
        n = len(getattr(self.ctx.engine, "links", {}))
        self.foot_l.setText("DigiConnect · HELLAS Zone · Public activity depends on information available from each network. Engine: " + self.ctx.engine.name + (f" · {n} link{'s' if n != 1 else ''}" if n else ""))

    def _need_endpoint(self, t):
        text, ok = W.QInputDialog.getText(self, "Server address", f"Server for {t.net} · {t.id}\nEnter host or host:port (saved for next time):")
        if not ok: return
        if not self.ctx.engine.servers.remember(t, text):
            self.ctx.toast.emit("That address is not valid. Use host or host:port, without spaces."); return
        self.ctx.select(t); self.ctx.retry_pending()

    def closeEvent(self, e):
        if hasattr(self.ctx.engine, "shutdown"): self.ctx.engine.shutdown()
        super().closeEvent(e)

    def _close_drawers(self): self.settings.hide(); self.qdrawer.hide()

    def open_settings(self, tab=0):
        self.qdrawer.hide(); self.settings.show(); self.settings.open_tab(tab)

    def open_qso(self, *_):
        self.settings.hide(); self.qdrawer.show(); self.qdrawer.prepare()

    def apply_settings(self):
        s = self.ctx.store.settings; self.callsign.setText(s.get("callsign") or "—"); self.lang.setText(s["language"])
        self.avatar.setText((s.get("callsign") or "DC")[:2].upper()); W.QApplication.instance().setStyleSheet(qss(s["text_size"]))
        self.favs.rebuild() if hasattr(self, "favs") else None

    def _clock(self):
        from datetime import timezone; u = datetime.now(timezone.utc); l = datetime.now()
        self.clock.setText(f"<b style='font-size:16px'>{u:%H:%M:%S}</b> <span style='color:{C['muted']}'>UTC</span><br><span style='color:{C['muted']}'>{l:%I:%M:%S %p}</span>")

    def _mute_all(self):
        r = self.ctx.rules; m = not all(r.net_muted.values())
        for n in NETS: r.net_muted[n] = m; self.mixer.mutes[n].setChecked(m)
        self.ctx.changed.emit()

    def _f2(self):
        f = W.QApplication.focusWidget()
        if f is None or isinstance(f, (W.QLineEdit, W.QPlainTextEdit, W.QSpinBox)): return
        if self.current != "favorites": self.open_qso()

    # ---- focus / keys -----------------------------------------------------
    def event(self, e):
        if e.type() == QtCore.QEvent.Type.WindowDeactivate: self.ctx.focus_lost()
        return super().event(e)

    def keyPressEvent(self, e):
        f = W.QApplication.focusWidget()
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat() and not isinstance(f, (W.QLineEdit, W.QPlainTextEdit, W.QSpinBox, W.QComboBox)):
            self.ctx.ptt_down(False); return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat(): self.ctx.ptt_up(); return
        super().keyReleaseEvent(e)
