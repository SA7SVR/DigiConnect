from ..qt import QtWidgets as W, Qt
from ..i18n import tr
from .widgets import *
from ..version import APP_VERSION
import bootstrap


class UpdatesDialog(W.QDialog):
    def __init__(self, updater, parent=None):
        super().__init__(parent); self.u = updater; self.setWindowTitle(tr("Updates")); self.setMinimumWidth(460)
        v = vbox(self, m=(20, 18, 20, 16), s=10)
        t = label("Updates"); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        self.cur = label(""); v.addWidget(self.cur); self.status = label("", muted=True); self.status.setWordWrap(True); v.addWidget(self.status)
        v.addWidget(label("Updates are downloaded automatically, checked, and started the next time the program opens — no re-install. A bad update is switched off automatically.", muted=True)); v.itemAt(v.count() - 1).widget().setWordWrap(True)
        r = hbox(s=8); self.check = button("Check now"); self.restart = button("Restart now", "primary"); self.close_b = button("Close")
        r.addWidget(self.check); r.addWidget(self.restart); r.addStretch(); r.addWidget(self.close_b); v.addLayout(r)
        self.check.clicked.connect(self.u.check); self.restart.clicked.connect(self._restart); self.close_b.clicked.connect(self.accept)
        self.refresh()

    def _restart(self): self.accept(); self.u.restart()

    def refresh(self):
        u = self.u
        self.cur.setText(tr("Running version {} (program shell {})").format(u.running, bootstrap.SHELL_VERSION))
        msg = {"idle": "", "checking": "Checking for updates…", "uptodate": "DigiConnect is up to date.", "downloading": tr("Downloading version {}…").format(u.message),
               "ready": tr("Version {} is installed and starts at the next launch.").format(u.message), "needs_installer": tr("Version {} needs a full installer from the DigiConnect website.").format(u.message),
               "error": tr("Could not update: {}").format(u.message)}.get(u.state, "")
        if u.state in ("checking", "uptodate"): msg = tr(msg)
        self.status.setText(msg); self.restart.setVisible(bool(u.pending)); self.check.setEnabled(u.state not in ("checking", "downloading"))
