"""The number a network sends for the talking station is named for that network: DMR ID (DMR), NXDN ID (NXDN), Radio ID (P25); the networks that send
call signs show just "ID" (the NXDN page said "DMR ID")."""
import os, sys, pathlib, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.qt import QtWidgets as W
from app.store import Store
from app.context import Ctx
from app import i18n
from app.rules import id_label
from app.ui.main_window import MainWindow

SAME = 2021015


def _win(tmp_path):
    app = W.QApplication.instance() or W.QApplication([])
    return MainWindow(Ctx(Store(tmp_path))), None


def test_labels():
    assert [id_label(n) for n in ("DMR", "NXDN", "P25")] == ["DMR ID", "NXDN ID", "Radio ID"]
    assert all(id_label(n) == "ID" for n in ("D-Star", "C4FM", "M17", "EchoLink", "AllStar"))


def test_last_heard_header_and_now_talking_name_the_right_id(tmp_path):
    w, _ = _win(tmp_path); ctx = w.ctx
    head = lambda net: [w.ws[net].lh_tbl.horizontalHeaderItem(i).text() for i in range(5)]
    assert head("DMR")[1] == "DMR ID" and head("NXDN")[1] == "NXDN ID" and head("P25")[1] == "Radio ID" and head("M17")[1] == "ID" and head("C4FM")[1] == "ID"
    for net, label in (("NXDN", "NXDN ID"), ("P25", "Radio ID"), ("DMR", "DMR ID")):
        ctx.talking[(net, "x")] = dict(src=str(SAME), stream_src=str(SAME), srcid=SAME, since=time.monotonic()); w.ws[net]._show_now()
        assert w.ws[net].now_info.text().startswith(f"{label} {SAME}"), w.ws[net].now_info.text()
        ctx.talking.clear()


def test_greek_header(tmp_path):
    i18n.set_language("Ελληνικά")
    try:
        w, _ = _win(tmp_path); assert w.ws["NXDN"].lh_tbl.horizontalHeaderItem(1).text() == "NXDN ID"
    finally: i18n.set_language("English")
