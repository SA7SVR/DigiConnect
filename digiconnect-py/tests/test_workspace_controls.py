"""Every workspace page has its own Listen / Connect (TX) / PTT controls AND the fixed bar at the bottom of the window shows them too."""
import os, sys, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def test_workspace_keeps_its_own_controls_and_the_bottom_bar_is_there_too(tmp_path):
    from app.qt import QtWidgets
    from app.store import Store
    from app.context import Ctx
    from app.theme import qss
    from app.ui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    (tmp_path / "ui").mkdir(); st = Store(tmp_path / "ui"); st.settings["callsign"] = "SA7SVR"
    ctx = Ctx(st); app.setStyleSheet(qss(14))
    w = MainWindow(ctx); w.resize(1500, 950); w.show(); app.processEvents()
    for net in ("DMR", "D-Star", "C4FM", "NXDN", "P25", "M17", "AllStar", "EchoLink"):
        w.nav("net:" + net); app.processEvents()
        ws = w.ws[net]
        assert ws.tx.isVisibleTo(ws), net                                   # the page's own Listen / Connect / PTT
        assert w.dock.isVisible(), net                                      # the fixed bar at the bottom
    w.close()
