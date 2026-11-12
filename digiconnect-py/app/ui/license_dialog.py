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
CODE_ERRORS = {"bad_code": "This code is not valid.", "expired": "This code has expired.", "used": "This code has already been used on another computer.",
               "other_pc": "This licence belongs to another computer."}


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
        t = label(tr("DigiConnect cannot continue") if verdict.kind == "offline" else tr("Waiting for approval") if verdict.state == "pending" else tr("DigiConnect is not active")); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        self.msg = label(tr(verdict.msg)); self.msg.setWordWrap(True); v.addWidget(self.msg)
        row = hbox(); self.quit = button(tr("Quit")); self.donate = button("♥ " + tr("Donate")); self.code = button(tr("Activation code…")); self.contact = button(tr("Contact the owner…")); self.retry = button(tr("Try again"), "primary")
        for b in (self.quit, self.donate, self.code, self.contact): row.addWidget(b)
        row.addStretch(); row.addWidget(self.retry); v.addLayout(row)
        self.donate.setVisible((verdict.info or {}).get("offer", "donate") != "none" and verdict.state != "pending"); self.code.setVisible(verdict.kind != "offline"); self.contact.setVisible(verdict.kind != "offline")
        self.quit.clicked.connect(self.reject); self.donate.clicked.connect(lambda: open_donate(verdict.donate)); self.retry.clicked.connect(self._retry)
        self.code.clicked.connect(self._code); self.contact.clicked.connect(self._contact)

    def _code(self):
        lic = getattr(self.check, "__self__", None)                                  # the License behind the retry callback
        if lic is None: return
        d = ActivationDialog(lic, self)
        if d.exec() and d.answer is not None:
            self.result_verdict = lic.verdict(d.answer)
            if self.result_verdict.allowed: self.accept()
            else: self.verdict = self.result_verdict; self.msg.setText(tr(self.verdict.msg))

    def _contact(self):
        lic = getattr(self.check, "__self__", None)
        if lic is not None: MessageDialog(lic, self).exec()

    def _retry(self):
        self.msg.setText(tr("Checking…")); W.QApplication.processEvents()
        v = self.check()
        if v.allowed: self.result_verdict = v; self.accept()
        else: self.verdict = v; self.msg.setText(tr(v.msg))


class ActivationDialog(W.QDialog):
    """Enter an activation code (a licence or a longer demo). The server answers with a signed licence; nothing is switched on without it."""
    _done = Signal(object, str)

    def __init__(self, lic, parent=None):
        super().__init__(parent); self.lic, self.answer = lic, None
        self.setWindowTitle(tr("Activation code")); self.setModal(True); self.setMinimumWidth(440)
        v = vbox(self, m=(24, 20, 24, 20), s=10)
        t = label(tr("Activation code")); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        i = label(tr("Enter the code you received from the owner or after your payment. The licence stays with this computer."), muted=True); i.setWordWrap(True); v.addWidget(i)
        self.code = W.QLineEdit(); self.code.setPlaceholderText("DC-XXXX-XXXX"); v.addWidget(self.code)
        self.err = label("", tone="amber"); self.err.setWordWrap(True); v.addWidget(self.err)
        row = hbox(); self.cancel = button(tr("Cancel")); self.ok = button(tr("Activate"), "primary"); row.addWidget(self.cancel); row.addStretch(); row.addWidget(self.ok); v.addLayout(row)
        self.cancel.clicked.connect(self.reject); self.ok.clicked.connect(self._send); self.code.returnPressed.connect(self._send); self._done.connect(self._finished)

    def _send(self):
        c = self.code.text().strip()
        if not c: self.err.setText(tr("Enter the code.")); return
        self.err.setText(tr("Checking…")); self.ok.setEnabled(False)
        def work():
            try: self._done.emit(self.lic.redeem(c), "")
            except lic_mod.LicenseError as ex: self._done.emit(None, str(ex))
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, m, err):
        self.ok.setEnabled(True)
        if m is None:
            self.err.setText(tr(CODE_ERRORS[err]) if err in CODE_ERRORS else tr("The server could not be reached ({}). Check the internet connection and try again.").format(err)); return
        if m.get("other_pc"): self.err.setText(tr(CODE_ERRORS["other_pc"])); return
        self.answer = m; self.accept()


class MessageDialog(W.QDialog):
    """Write to the owner (the message appears in his control panel; the answer comes back into this program)."""
    _done = Signal(str)

    def __init__(self, lic, parent=None):
        super().__init__(parent); self.lic = lic
        self.setWindowTitle(tr("Message to the owner")); self.setModal(True); self.setMinimumWidth(460)
        v = vbox(self, m=(24, 20, 24, 20), s=10)
        t = label(tr("Message to the owner")); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        self.subject = W.QLineEdit(); self.subject.setPlaceholderText(tr("Subject")); v.addWidget(self.subject)
        self.body = W.QPlainTextEdit(); self.body.setMinimumHeight(140); v.addWidget(self.body)
        self.msg = label("", tone="amber"); self.msg.setWordWrap(True); v.addWidget(self.msg)
        row = hbox(); self.close_b = button(tr("Close")); self.send = button(tr("Send"), "primary"); row.addWidget(self.close_b); row.addStretch(); row.addWidget(self.send); v.addLayout(row)
        self.close_b.clicked.connect(self.reject); self.send.clicked.connect(self._send); self._done.connect(self._finished)

    def _send(self):
        b = self.body.toPlainText().strip()
        if not b: self.msg.setText(tr("Write your message first.")); return
        self.msg.setText(tr("Sending…")); self.send.setEnabled(False); subj = self.subject.text().strip(); lang = lang_code()
        def work():
            try: self.lic.inbox_send(b, "app", subj, lang); self._done.emit("")
            except lic_mod.LicenseError as ex: self._done.emit(str(ex))
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, err):
        self.send.setEnabled(True)
        if err: self.msg.setText(tr("Could not send ({}). Try again later.").format(tr("too many messages, try later") if err == "too_many" else err)); return
        self.body.clear(); self.subject.clear(); self.msg.setText(tr("Sent. The answer will appear here."))


class LicenceDialog(W.QDialog):
    """Licence status of this installation, the owner's messages and replies, activation code, and writing to the owner."""
    _got = Signal(object)
    _sent = Signal(bool)

    def __init__(self, watcher, parent=None):
        super().__init__(parent); self.watcher = watcher; self.lic = watcher.lic; self._sent.connect(self._sent_done); self.setWindowTitle(tr("Licence and messages")); self.setMinimumSize(560, 560)
        v = vbox(self, m=(24, 20, 24, 20), s=10)
        t = label(tr("Licence and messages")); t.setStyleSheet("font-size:20px;font-weight:700;"); v.addWidget(t)
        self.status = label("", muted=True); self.status.setWordWrap(True); self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); v.addWidget(self.status)
        row = hbox(); self.code = button(tr("Activation code…")); self.donate = button("♥ " + tr("Donate")); self.write = button(tr("Write to the owner…"))
        self.diag_b = button(tr("Send diagnostics to the owner")); self.diag_b.setToolTip("Sends the program version, system and the end of the log (no passwords) so the owner can see why something does not work")
        for b in (self.code, self.donate, self.write, self.diag_b): row.addWidget(b)
        row.addStretch(); v.addLayout(row)
        v.addWidget(label(tr("Messages"), muted=True))
        self.list = W.QListWidget(); self.list.setWordWrap(True); v.addWidget(self.list, 1)
        self.close_b = button(tr("Close")); r2 = hbox(); r2.addStretch(); r2.addWidget(self.close_b); v.addLayout(r2)
        self.close_b.clicked.connect(self.accept); self.code.clicked.connect(self._code); self.write.clicked.connect(self._write); self.diag_b.clicked.connect(self._diag)
        self.donate.clicked.connect(lambda: open_donate((self.lic.last.donate if self.lic.last else "")))
        self._got.connect(self._fill); self.render(); self.refresh()

    def render(self):
        v = self.lic.last; i = (v.info if v else {}) or {}
        state = {"full": tr("Licensed"), "demo": tr("Demo"), "free": tr("Free")}.get(v.state if v else "", tr(v.state) if v and v.state else "—")
        lines = [f"{tr('Status')}: {state}" + (f" · {tr(v.left)}" if v and v.left else "")]
        if i.get("no"): lines.append(f"{tr('Installation')}: {i['no']}" + (f" · {i['call']}" if i.get("call") else ""))
        if i.get("own"): lines.append(f"{tr('Licensed to')}: {i['own']}")
        lines.append(f"{tr('This computer')}: {self.lic.hw[:8]}")
        self.status.setText("\n".join(lines)); self.donate.setVisible(i.get("offer", "donate") != "none")

    def refresh(self):
        def work():
            try: r = self.lic.replies()
            except Exception: r = []
            self._got.emit(r)
        threading.Thread(target=work, daemon=True).start()

    def _fill(self, replies):
        self.list.clear(); items = []
        for m in self.lic.msgs:
            el = lang_code() == "el"
            items.append((m.get("t", 0), m["id"], (m.get("title_el") if el else m.get("title_en")) or "", (m.get("el") if el else m.get("en")) or ""))
        for r in replies: items.append((r.get("t", 0), r["id"], tr("Reply") + ": " + (r.get("subject") or ""), r.get("reply", "")))
        for t, mid, title, body in sorted(items, reverse=True):
            it = W.QListWidgetItem((title + "\n" if title else "") + body); it.setData(Qt.ItemDataRole.UserRole, mid); self.list.addItem(it)
        if not items: self.list.addItem(tr("No messages."))
        self.watcher.mark_seen([i[1] for i in items])

    def _write(self):
        MessageDialog(self.lic, self).exec(); self.refresh()

    def _diag(self):
        from ..diagnostics import report
        self.diag_b.setEnabled(False); self.diag_b.setText(tr("Sending…"))
        def work():
            try: self.lic.inbox_send(report(getattr(self.lic, "store", None)), topic="diagnostics", subject="Diagnostics " + self.lic.params().get("v", ""), lang=lang_code()); ok = True
            except Exception: ok = False
            self._sent.emit(ok)
        threading.Thread(target=work, daemon=True).start()

    def _sent_done(self, ok):
        self.diag_b.setEnabled(True); self.diag_b.setText(tr("Send diagnostics to the owner"))
        W.QMessageBox.information(self, tr("Diagnostics"), tr("Sent. Thank you — the owner can now see what happened.") if ok else tr("Could not send (no connection to the server). Try again later."))

    def _code(self):
        d = ActivationDialog(self.lic, self)
        if d.exec() and d.answer is not None:
            self.watcher.changed.emit(self.lic.verdict(d.answer)); self.render()


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
    unread_changed = Signal(int)
    _got = Signal(object)

    def __init__(self, lic, every_s: int = 1800):
        super().__init__(); self.lic = lic; self._busy = False
        self._got.connect(self._arrived)
        self._t = QtCore.QTimer(self); self._t.setInterval(every_s * 1000); self._t.timeout.connect(self.check)

    def start(self): self._t.start(); self.check()

    def check(self):
        if self._busy: return
        self._busy = True
        def work():
            try:
                v = self.lic.evaluate()
                try: self.lic.reply_ids = [r["id"] for r in self.lic.replies()]
                except Exception: pass
            finally: self._busy = False
            self._got.emit(v)
        threading.Thread(target=work, daemon=True).start()

    def _arrived(self, v):
        self.changed.emit(v); self.unread_changed.emit(self.unread())

    def unread(self) -> int:
        seen = set(self.lic.store.settings.get("msgs_seen") or [])
        ids = [m["id"] for m in (self.lic.msgs or [])] + list(getattr(self.lic, "reply_ids", []) or [])
        return len([i for i in ids if i not in seen])

    def mark_seen(self, ids):
        s = self.lic.store.settings; cur = set(s.get("msgs_seen") or []); new = cur | set(ids)
        if new != cur: s["msgs_seen"] = sorted(new)[-300:]; self.lic.store.save_settings()
        self.unread_changed.emit(self.unread())
