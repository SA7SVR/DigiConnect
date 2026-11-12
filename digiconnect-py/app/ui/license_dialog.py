"""First-run registration window, the 'cannot continue' window (locked / demo ended / no connection) and the licence watcher."""
import threading
from ..qt import QtWidgets as W, QtCore, QtGui, Qt, Signal
from ..i18n import tr, code as lang_code
from .. import license as lic_mod
from .widgets import *

PRIVACY = ("Controller: Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net. Data: name, callsign, DMR ID, email, plus installation ID, program version, operating system, language and IP address. "
           "Purpose: licensing (demo period, switching a copy on or off). Legal basis: your consent and providing the program. "
           "Not shared with anyone, not used for advertising; kept while you use the program or until you ask for erasure. "
           "You have the right to access, correct or erase your data and to withdraw your consent at any time, and to complain to your data protection authority.")
PRIVACY_URL = lic_mod.BASE + "privacy.php"
ERRORS = {"name": "Enter your name.", "call": "Enter a valid callsign (for example SA7SVR).", "dmr_id": "Enter your DMR ID: 6 to 9 digits.",
          "mail": "Enter a valid email address.", "consent": "Please tick the box to agree."}


def open_donate(url: str = ""):
    QtGui.QDesktopServices.openUrl(QtCore.QUrl(url or lic_mod.DONATE_URL))


class RegistrationDialog(W.QDialog):
    _done = Signal(object, str)

    def __init__(self, lic, store, parent=None, lang=""):
        super().__init__(parent); self.lic, self.store, self.lang, self.answer = lic, store, lang, None
        self.setWindowTitle(tr("Welcome to DigiConnect")); self.setModal(True); self.setMinimumWidth(520)
        v = vbox(self, m=(24, 20, 24, 20), s=10)
        t = label(tr("Welcome to DigiConnect")); t.setStyleSheet("font-size:22px;font-weight:700;"); v.addWidget(t)
        intro = label(tr("Please enter your details once. All four are required."), muted=True); intro.setWordWrap(True); v.addWidget(intro)
        s = store.settings
        self.name = W.QLineEdit(s.get("op_name", "")); self.call = W.QLineEdit(s.get("callsign", "")); self.dmr = W.QLineEdit(str(s.get("dmr_id", "")))
        self.mail = W.QLineEdit(s.get("email", ""))
        self.call.setPlaceholderText("SA7SVR"); self.dmr.setPlaceholderText("2400123"); self.mail.setPlaceholderText("name@example.com")
        self.f = {"name": self.name, "call": self.call, "dmr_id": self.dmr, "mail": self.mail}
        for k, title in (("name", "Name"), ("call", "Callsign"), ("dmr_id", "DMR ID"), ("mail", "Email")): v.addWidget(field(tr(title), self.f[k]))
        self.agree = checkbox(tr("I agree that these details are stored on the HELLAS Zone server for this purpose.")); v.addWidget(self.agree)
        p = label(tr(PRIVACY), muted=True); p.setWordWrap(True); v.addWidget(p)
        self.policy = button(tr("Privacy policy")); self.policy.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(PRIVACY_URL + (f"?lang={lang_code()}" if lang_code() in ("el", "en", "sv", "it") else ""))))
        v.addWidget(self.policy, 0, Qt.AlignmentFlag.AlignLeft)
        self.err = label("", tone="amber"); self.err.setWordWrap(True); v.addWidget(self.err)
        row = hbox(); self.quit = button(tr("Quit")); self.ok = button(tr("Register"), "primary"); row.addWidget(self.quit); row.addStretch(); row.addWidget(self.ok); v.addLayout(row)
        self.ok.clicked.connect(self._send); self.quit.clicked.connect(self.reject); self._done.connect(self._finished)

    def _send(self):
        d = {k: e.text().strip() for k, e in self.f.items()}; bad = lic_mod.validate(d)
        if bad: self.err.setText(tr(ERRORS[bad[0]])); self.f[bad[0]].setFocus(); return
        if not self.agree.isChecked(): self.err.setText(tr(ERRORS["consent"])); return
        self.err.setText(tr("Registering…")); self.ok.setEnabled(False)
        def work():
            try: self._done.emit(self.lic.register(d, self.lang), "")
            except lic_mod.LicenseError as ex: self._done.emit(None, str(ex))
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, m, err):
        self.ok.setEnabled(True)
        if m is None:
            self.err.setText(tr(ERRORS[err]) if err in ERRORS else tr("The server could not be reached ({}). Check the internet connection and try again.").format(err)); return
        s = self.store.settings                                                    # what was typed here is also the station's identity in Settings
        s.update(op_name=self.name.text().strip(), callsign=self.call.text().strip().upper(), dmr_id=self.dmr.text().strip(), email=self.mail.text().strip(), registered=True)
        self.store.save_settings(); self.answer = m; self.accept()


class BlockDialog(W.QDialog):
    """Shown when the program may not continue: locked, demo ended, or the server is needed but cannot be reached. Retry / Donate / Quit."""
    def __init__(self, verdict, check, parent=None):
        super().__init__(parent); self.verdict, self.check = verdict, check; self.result_verdict = None
        self.setWindowTitle("DigiConnect"); self.setModal(True); self.setMinimumWidth(480)
        v = vbox(self, m=(24, 20, 24, 20), s=10)
        t = label(tr("DigiConnect cannot continue") if verdict.kind == "offline" else tr("DigiConnect is not active")); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        self.msg = label(tr(verdict.msg)); self.msg.setWordWrap(True); v.addWidget(self.msg)
        row = hbox(); self.quit = button(tr("Quit")); self.donate = button("♥ " + tr("Donate")); self.retry = button(tr("Try again"), "primary")
        row.addWidget(self.quit); row.addWidget(self.donate); row.addStretch(); row.addWidget(self.retry); v.addLayout(row)
        self.quit.clicked.connect(self.reject); self.donate.clicked.connect(lambda: open_donate(verdict.donate)); self.retry.clicked.connect(self._retry)

    def _retry(self):
        self.msg.setText(tr("Checking…")); W.QApplication.processEvents()
        v = self.check()
        if v.allowed: self.result_verdict = v; self.accept()
        else: self.verdict = v; self.msg.setText(tr(v.msg))


def run_gate(lic, store, parent=None, lang="") -> bool:
    """Before the main window: register on the first run, then the demo / licence / offline rules. True = the program may start."""
    v = lic.evaluate()
    while True:
        if v.kind == "register":
            d = RegistrationDialog(lic, store, parent, lang)
            if not d.exec(): return False
            v = lic.verdict(d.answer)
        if v.allowed: return True
        d = BlockDialog(v, lic.evaluate, parent)
        if not d.exec(): return False
        v = d.result_verdict or lic.evaluate()
        if v.allowed: return True


class Watcher(QtCore.QObject):
    """While the program runs: asks the server again every hour (and on request) and tells the window the new verdict."""
    changed = Signal(object)
    _got = Signal(object)

    def __init__(self, lic, every_s: int = 3600):
        super().__init__(); self.lic = lic; self._busy = False
        self._got.connect(self.changed.emit)
        self._t = QtCore.QTimer(self); self._t.setInterval(every_s * 1000); self._t.timeout.connect(self.check)

    def start(self): self._t.start(); self.check()

    def check(self):
        if self._busy: return
        self._busy = True
        def work():
            try: v = self.lic.evaluate()
            finally: self._busy = False
            self._got.emit(v)
        threading.Thread(target=work, daemon=True).start()
