from datetime import datetime
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .. import theme, i18n
from ..i18n import tr
from ..theme import C, qss
from ..rules import NETS
from ..context import Ctx
from .widgets import *
from .icons import icon, dot
from ..theme import NET_COLOR
from .heardpage import HeardPage
from .workspace import Workspace
from .favorites import Favorites
from .qsolog import QsoLog
from .controls import Dock, Mixer
from .drawers import SettingsDrawer, QsoDrawer
from pathlib import Path

def _logo() -> Path:
    """The logo ships next to the program (PyInstaller: <install>/assets). After an automatic update the code runs from the
    update folder, which has no assets, so look in every place the program could be installed."""
    import sys
    here = Path(__file__).resolve().parents[2]
    for base in (here, Path(getattr(sys, "_MEIPASS", here)), Path(sys.executable).resolve().parent, Path(sys.executable).resolve().parent / "_internal"):
        if (base / "assets" / "logo.png").exists(): return base / "assets" / "logo.png"
    return here / "assets" / "logo.png"


LOGO = _logo()
RAIL = [("favorites", "grid", "My favorites"), ("newqso", "plus", "New QSO"), ("log", "doc", "QSO log"), ("analysis", "bars", "Log analysis"),
        ("heard", "clock", "Last heard"), ("mixer", "headphones", "Audio mixer"), ("rec", "circle", "Recordings")]


class Toast(W.QLabel):
    """Short notice at the top of the window: fades in, stays a few seconds (longer for longer text), fades out. Never covers the controls."""
    def __init__(self, parent):
        super().__init__(parent); self.setObjectName("toast")
        self.setWordWrap(True); self.setAlignment(Qt.AlignmentFlag.AlignCenter); self.hide()
        self.fx = W.QGraphicsOpacityEffect(self); self.fx.setOpacity(1.0); self.setGraphicsEffect(self.fx)
        self.anim = QtCore.QPropertyAnimation(self.fx, b"opacity", self); self.anim.finished.connect(self._anim_done)
        self.t = QtCore.QTimer(self); self.t.setSingleShot(True); self.t.timeout.connect(self._fade_out)
        self._closing = False

    def show_msg(self, text):
        self.anim.stop(); self._closing = False
        self.setText(text); self.setFixedWidth(min(440, self.parent().width() - 40)); self.adjustSize()
        self.move((self.parent().width() - self.width()) // 2, 14); self.fx.setOpacity(0.0); self.show(); self.raise_()
        self.anim.setDuration(180); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0); self.anim.start()
        self.t.start(min(6500, 2200 + 45 * len(text)))

    def _fade_out(self):
        self._closing = True; self.anim.stop(); self.anim.setDuration(700); self.anim.setStartValue(self.fx.opacity()); self.anim.setEndValue(0.0); self.anim.start()

    def _anim_done(self):
        if self._closing: self.hide(); self._closing = False


class MainWindow(W.QMainWindow):
    def __init__(self, ctx: Ctx | None = None):
        super().__init__(); self.ctx = ctx or Ctx(); theme.set_theme(self.ctx.store.settings.get("theme", "dark")); i18n.set_language(self.ctx.store.settings.get("language", "English")); self.setWindowTitle("DigiConnect · HELLAS Zone"); self.resize(1500, 900); self.setMinimumSize(1100, 700)
        if LOGO.exists(): self.setWindowIcon(QtGui.QIcon(str(LOGO)))
        root = W.QWidget(); root.setObjectName("root"); self.setCentralWidget(root); outer = vbox(root, s=0)
        body = hbox(s=0); outer.addLayout(body, 1)
        # rail
        rail = W.QFrame(); rail.setObjectName("rail"); rail.setFixedWidth(132); rv = vbox(rail, m=(8, 14, 8, 14), s=8)
        lg = W.QLabel(); lg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _pm = QtGui.QPixmap(str(LOGO)); _bb = QtGui.QRegion(_pm.createMaskFromColor(QtGui.QColor(0, 0, 0, 0), Qt.MaskMode.MaskOutColor)).boundingRect() if not _pm.isNull() else QtCore.QRect()   # cut the empty transparent margin so the logo fills the rail
        if not _bb.isEmpty(): _pm = _pm.copy(_bb)
        lg.setPixmap(_pm.scaled(116, 116, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        rv.addWidget(lg); rv.addSpacing(10); self.rail_btn = {}
        def rb(key, ic, tip):
            b = button("", "rail", checkable=True, tip=tip); b.setIcon(icon(ic)); b.setProperty("icon_name", ic); b.setIconSize(QtCore.QSize(22, 22)); b.setFixedSize(46, 42); b.clicked.connect(lambda _, k=key: self.nav(k)); self.rail_btn[key] = b; return b
        for k, ic, tip in RAIL: rv.addWidget(rb(k, ic, tip), 0, Qt.AlignmentFlag.AlignHCenter)
        rv.addStretch()
        for k, ic, tip in (("updates", "download", "Updates"), ("help", "help", "Help"), ("settings", "gear", "Settings")): rv.addWidget(rb(k, ic, tip), 0, Qt.AlignmentFlag.AlignHCenter)
        self.avatar = W.QLabel("SA"); self.avatar.setFixedSize(36, 36); self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setObjectName("avatar"); rv.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(rail)
        # centre column
        col = vbox(s=0); body.addLayout(col, 1)
        top = W.QFrame(); top.setObjectName("topbar"); top.setFixedHeight(64); th = hbox(top, m=(24, 8, 20, 8), s=14)
        self.brand_top = W.QLabel("HELLAS ZONE NET"); self.brand = W.QLabel()
        bv = vbox(s=0); bv.addWidget(self.brand_top); bv.addWidget(self.brand); th.addLayout(bv); self._brand_style()
        th.addStretch()
        self.clock = label(""); self.clock.setAlignment(Qt.AlignmentFlag.AlignRight); th.addWidget(self.clock)
        self.callsign = label(""); self.callsign.setProperty("tone", "accent"); th.addWidget(self.callsign)
        self.upd_btn = button("New version", "primary", "download"); self.upd_btn.setVisible(False); self.upd_btn.clicked.connect(self.show_updates); th.addWidget(self.upd_btn)
        self.theme_btn = button("", ""); th.addWidget(self.theme_btn); self.set_top = button("Settings", "", "gear"); th.addWidget(self.set_top); col.addWidget(top)
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
        self.heard = HeardPage(self.ctx); self.pages.addWidget(self.favs); self.pages.addWidget(self.log); self.pages.addWidget(self.heard)
        for n in NETS: self.pages.addWidget(self.ws[n])
        self.mixer = Mixer(self.ctx); self.dock = Dock(self.ctx, lambda: None)
        col.addWidget(self.mixer); col.addWidget(self._pad(self.dock))
        foot = W.QFrame(); foot.setObjectName("footer"); foot.setFixedHeight(28); fh = hbox(foot, m=(24, 0, 24, 0))
        self.foot_l = label("DigiConnect · HELLAS Zone · Public activity depends on information available from each network. Engine: " + self.ctx.engine.name); fh.addWidget(self.foot_l); fh.addStretch()
        self.lang = label(self.ctx.store.settings["language"]); fh.addWidget(self.lang); outer.addWidget(foot)
        self.toast = Toast(root); self.ctx.toast.connect(self.toast.show_msg)
        # wiring
        self.mixer.hide_requested.connect(lambda: self.mixer.setVisible(False)); self.h_nq.clicked.connect(self.open_qso); self.h_set.clicked.connect(lambda: self.open_settings())
        self.set_top.clicked.connect(lambda: self.open_settings()); self.theme_btn.clicked.connect(self.toggle_theme); self.settings.closed.connect(self._close_drawers); self.qdrawer.closed.connect(self._close_drawers)
        self.qdrawer.saved.connect(self.log.reload); self.settings.applied.connect(self.apply_settings)
        self.ctx.changed.connect(self._sync_chrome)
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
        if key == "mixer": self._mixer_user = True; self.mixer.setVisible(not self.mixer.isVisible()); self._sync_chrome(); return
        if key in ("analysis",): self.nav("log"); self.log._analysis(); return
        if key == "updates": self.show_updates(); return
        if key in ("rec", "help"):
            msg = {"rec": "Recordings: none yet. Recording needs a running receiver (engine step).",
                   "updates": "Updates: open the release page for DigiConnect to check for a newer build.", "help": "Help: see docs/SPEC.md (operating rules) in the source package."}[key]
            self.ctx.toast.emit(msg); return
        self.current = key
        if key == "favorites": self.pages.setCurrentWidget(self.favs); self.favs.rebuild()
        elif key == "log": self.pages.setCurrentWidget(self.log); self.log.reload()
        elif key == "heard": self.pages.setCurrentWidget(self.heard); self.heard.reload()
        elif key.startswith("net:"):
            n = key[4:]; self.pages.setCurrentWidget(self.ws[n]); self.ctx.last_net = n
        self.settings.set_mode(key[4:] if key.startswith("net:") else None)         # the settings follow the mode of the page
        self._sync_chrome()

    def _sync_chrome(self):
        k, ws = self.current, self.current.startswith("net:")
        self.head.setVisible(k == "favorites" or ws)
        net = k[4:] if ws else None
        self.title.setText("My favorites" if k == "favorites" else (f"Radio workspace  {net}" if ws else ""))
        self.title.setTextFormat(Qt.TextFormat.RichText)
        if ws: self.title.setText(f"{tr('Radio workspace')} <span style='color:{__import__('app.theme', fromlist=['NET_COLOR']).NET_COLOR[net]}'>{net}</span>")
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

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # small window: the mixer would squeeze the pages, so it starts hidden (the headphone button still opens it)
        if hasattr(self, "mixer") and not getattr(self, "_mixer_user", False): self.mixer.setVisible(self.height() >= 820); self._sync_chrome()

    # ---- updates ---------------------------------------------------------------
    def bind_updater(self):
        u = self.updater; self._upd_dlg = None
        u.changed.connect(self._upd_changed)

    def _upd_changed(self, state, msg):
        u = self.updater; self.upd_btn.setVisible(bool(u.pending) or state == "needs_installer")
        if u.pending: self.upd_btn.setText(tr("New version") + " " + str(u.pending))
        elif state == "needs_installer": self.upd_btn.setText(tr("New version") + " " + str(msg))
        if state == "ready": self.ctx.toast.emit(tr("Update {} is ready. It starts the next time DigiConnect is opened (Updates › Restart now).").format(msg))
        elif state == "needs_installer": self.ctx.toast.emit(tr("Version {} needs a new full installer (engine change). Download it from the DigiConnect website.").format(msg))
        if self._upd_dlg is not None: self._upd_dlg.refresh()

    def show_updates(self):
        from .updates_dialog import UpdatesDialog
        self._upd_dlg = UpdatesDialog(self.updater, self); self._upd_dlg.exec(); self._upd_dlg = None

    def closeEvent(self, e):
        if hasattr(self.ctx.engine, "shutdown"): self.ctx.engine.shutdown()
        super().closeEvent(e)

    def _close_drawers(self): self.settings.hide(); self.qdrawer.hide()

    def open_settings(self, tab=0):
        self.qdrawer.hide(); self.settings.show(); self.settings.open_tab(tab)

    def open_qso(self, *_):
        self.settings.hide(); self.qdrawer.show(); self.qdrawer.prepare()

    def _brand_style(self):
        """Title in the top bar: small 'HELLAS ZONE NET' over DIGI (text colour) + CONNECT (green); follows the theme."""
        self.brand_top.setStyleSheet(f"color:{C['text']}; font-size:10px; font-weight:700; letter-spacing:2.5px;")
        self.brand.setText(f"<span style='color:{C['text']}'>DIGI</span><span style='color:{C['green']}'>CONNECT</span>")
        self.brand.setStyleSheet("font-size:24px; font-weight:800; letter-spacing:1px;")

    def apply_settings(self):
        s = self.ctx.store.settings; self.callsign.setText(s.get("callsign") or "—"); self.lang.setText(s["language"])
        theme.set_theme(s.get("theme", "dark")); i18n.set_language(s.get("language", "English")); i18n.retranslate()
        self.heard.retranslate()
        for _w in self.ws.values(): _w.fill()          # list rows are built from text, so they are rebuilt in the new language
        self.theme_btn.setText("☀  Light" if theme.current == "dark" else "☾  Dark")
        self.avatar.setText((s.get("callsign") or "DC")[:2].upper()); W.QApplication.instance().setStyleSheet(qss(s["text_size"]))
        repaint_icons(); self._brand_style()
        if hasattr(self, "favs"): self.favs.restyle(); self.favs.rebuild(); self._sync_chrome()

    def toggle_theme(self):
        s = self.ctx.store.settings; s["theme"] = "light" if theme.current == "dark" else "dark"; self.ctx.store.save_settings()
        self.apply_settings(); self.settings.sync_theme()

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
