"""The Updates window: what runs now, what the server offers, what is new in it, and every step of the download with a progress bar."""
import html
from ..qt import QtWidgets as W, Qt
from ..i18n import tr
from .widgets import *
from ..version import APP_VERSION
import bootstrap

# (state that is active, label) — a step is done when a later state has been reached
STEPS = (("downloading", "Downloading"), ("verifying", "Checking size and SHA-256"), ("installing", "Unpacking and testing the code"), ("ready", "Ready for the next start"))
ORDER = ("checking", "downloading", "verifying", "installing", "ready")


def mb(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, round(n / 1024))} KB"


class UpdatesDialog(W.QDialog):
    def __init__(self, updater, parent=None):
        super().__init__(parent); self.u = updater; self.setWindowTitle(tr("Updates")); self.setMinimumWidth(520)
        v = vbox(self, m=(22, 20, 22, 18), s=10)
        t = label("Updates"); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        self.cur = label(""); v.addWidget(self.cur)
        self.new = label(""); self.new.setWordWrap(True); self.new.setTextFormat(Qt.TextFormat.RichText); v.addWidget(self.new)
        self.status = label("", muted=True); self.status.setWordWrap(True); v.addWidget(self.status)
        self.bar = W.QProgressBar(); self.bar.setRange(0, 100); self.bar.setFixedHeight(10); self.bar.setTextVisible(False); v.addWidget(self.bar)
        self.steps = label(""); self.steps.setTextFormat(Qt.TextFormat.RichText); v.addWidget(self.steps)
        self.notes_h = label("What is new in this version"); self.notes_h.setStyleSheet("font-weight:700;"); v.addWidget(self.notes_h)
        self.notes = W.QTextBrowser(); self.notes.setMinimumHeight(110); self.notes.setMaximumHeight(200); self.notes.setOpenExternalLinks(True); v.addWidget(self.notes)
        self.how = label("Updates are downloaded automatically, checked, and started the next time the program opens — no re-install. A bad update is switched off automatically.", muted=True)
        self.how.setWordWrap(True); v.addWidget(self.how)
        r = hbox(s=8); self.check = button("Check now"); self.restart = button("Restart now", "primary"); self.close_b = button("Close")
        r.addWidget(self.check); r.addWidget(self.restart); r.addStretch(); r.addWidget(self.close_b); v.addLayout(r)
        self.check.clicked.connect(self.u.check); self.restart.clicked.connect(self._restart); self.close_b.clicked.connect(self.accept)
        self.u.progress.connect(self._pct)
        self.refresh()

    def done(self, r):
        try: self.u.progress.disconnect(self._pct)
        except Exception: pass
        super().done(r)

    def _restart(self): self.accept(); self.u.restart()

    def _pct(self, p):
        if p < 0: self.bar.setRange(0, 0)
        else: self.bar.setRange(0, 100); self.bar.setValue(p)
        self._steps()

    def _steps(self):
        u = self.u; st = u.state
        if st not in ORDER[1:] and not u.pending: self.steps.setText(""); return
        at = ORDER.index("ready") if st == "ready" else (ORDER.index(st) if st in ORDER else -1)
        rows = []
        for key, text in STEPS:
            i = ORDER.index(key)
            if i < at or (key == "ready" and st == "ready"): mark, extra = "✓", ""
            elif i == at: mark, extra = "●", (f" {u.pct}%" if key == "downloading" and u.pct >= 0 else "")
            else: mark, extra = "○", ""
            rows.append(f"{mark}&nbsp; {html.escape(tr(text))}{extra}")
        self.steps.setText("<br>".join(rows))

    def refresh(self):
        u = self.u; info = u.info or {}; st = u.state
        self.cur.setText(tr("Running version {} (program shell {})").format(u.running, bootstrap.SHELL_VERSION))
        offered = info.get("version") or u.pending or ""
        if offered and (st in ("downloading", "verifying", "installing", "ready", "needs_installer") or u.pending):
            size = f" · {mb(info['size'])}" if info.get("size") else ""
            self.new.setText("<b>" + html.escape(tr("New version {}").format(offered)) + "</b>" + html.escape(size)); self.new.setVisible(True)
        else: self.new.setVisible(False)
        msg = {"idle": "", "checking": "Checking for updates…", "uptodate": "DigiConnect is up to date.", "downloading": tr("Downloading version {}…").format(u.message),
               "verifying": tr("Checking version {}…").format(u.message), "installing": tr("Installing version {}…").format(u.message),
               "ready": tr("Version {} is installed and starts at the next launch.").format(u.message), "needs_installer": tr("Version {} needs a full installer from the DigiConnect website.").format(u.message),
               "error": tr("Could not update: {}").format(u.message)}.get(st, "")
        if st in ("checking", "uptodate"): msg = tr(msg)
        self.status.setText(msg)
        busy = st in ("downloading", "verifying", "installing")
        self.bar.setVisible(busy or st == "ready")
        if st == "ready": self.bar.setRange(0, 100); self.bar.setValue(100)
        elif st in ("verifying", "installing"): self.bar.setRange(0, 100); self.bar.setValue(100)
        elif st == "downloading": self._pct(u.pct)
        self._steps()
        notes = info.get("notes") or []
        show_notes = bool(notes) and bool(offered)
        self.notes_h.setVisible(show_notes); self.notes.setVisible(show_notes)
        if show_notes: self.notes.setHtml("<ul style='margin-left:-18px'>" + "".join(f"<li>{html.escape(n)}</li>" for n in notes) + "</ul>")
        self.restart.setVisible(bool(u.pending)); self.check.setEnabled(st not in ("checking", "downloading", "verifying", "installing"))
