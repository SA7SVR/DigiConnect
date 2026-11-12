"""One-button diagnostics to the owner, and the visible 'password saved' line in Settings."""
import pytest
from app import diag, diagnostics
from app.ui import license_dialog as LD
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_ui_smoke import win  # noqa: F401
from test_licence_ui import pump


def test_report_has_version_system_engine_and_log_end_but_no_password(tmp_path, win):
    w, ctx, app = win
    diag.start(tmp_path)
    for i in range(400): diag.log(f"engine line {i}")
    ctx.store.settings["dmr_pw"] = "SECRET-PASSWORD"; ctx.store.settings["dmr_id"] = "2400123"
    r = diagnostics.report(ctx.store, "/x/dcengine")
    assert "DigiConnect 2." in r and "/x/dcengine" in r and "engine line 399" in r and "engine line 100" not in r and "dmr_id=2400123" in r
    assert "SECRET-PASSWORD" not in r


def test_diagnostics_button_puts_the_report_in_the_owners_inbox(srv, win, tmp_path):
    w, ctx, app = win; l = lic(srv); l.register(PERSON); diag.start(tmp_path)
    for i in range(300): diag.log(f"engine {i} " + "x" * 40)
    wt = LD.Watcher(l); dlg = LD.LicenceDialog(wt)
    sent = []; dlg._sent_done = lambda ok: (sent.append(ok), dlg.diag_b.setEnabled(True))
    dlg._sent.disconnect(); dlg._sent.connect(dlg._sent_done)
    dlg.diag_b.click(); assert pump(app, lambda: sent) and sent == [True]
    row = srv.sql("SELECT topic, subject, body, src FROM dc_inbox ORDER BY id DESC")[0]
    assert row["topic"] == "diagnostics" and row["src"] == "app" and "engine 299" in row["body"] and len(row["body"]) > 4000


def test_settings_says_whether_the_dmr_password_is_kept(win):
    w, ctx, app = win; d = w.settings
    assert "No password" in d.dpw_state.text() or "Δεν έχει" in d.dpw_state.text()
    d.dpw.setText("abc"); assert "press Save" in d.dpw_state.text() or "Αποθήκευση" in d.dpw_state.text()
    toasts = []; ctx.toast.connect(toasts.append); d._save()
    assert ctx.dmr_password == "abc" and ctx.store.settings["dmr_pw"] == "abc"
    assert "saved on this computer" in d.dpw_state.text() or "αποθηκεύτηκε" in d.dpw_state.text()
    assert any("password saved" in t for t in toasts)
