"""Last heard: one row per transmission, clean destination, own transmissions marked, shown on every page and on the Last heard page."""
import os, types, datetime as dt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.qt import QtWidgets
from app.store import Store
from app.context import Ctx
from app.rules import Target


def test_heard_rows(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    st = Store(tmp_path); st.settings["callsign"] = "SA7SVR"; ctx = Ctx(st)
    ln = types.SimpleNamespace(rx=set(), target=Target("C4FM", "00006", "GR"), tx=False)
    t0 = dt.datetime(2026, 11, 12, 0, 0, 0, tzinfo=dt.timezone.utc); now = [t0]
    ctx.utc_now = lambda: now[0]
    for i in range(30):                                   # 30 frames of ONE transmission, 2 s long
        now[0] = t0 + dt.timedelta(milliseconds=70 * i); ctx._on_heard(ln, {"state": "new" if i % 7 == 0 else "streaming", "src": "69/SA7SVR", "dst": "**********", "gw": "GW"})
    assert len(ctx.last_heard) == 1 and ctx.last_heard[0]["dst"] == "" and ctx.last_heard[0]["me"] is True
    now[0] = t0 + dt.timedelta(seconds=30); ctx._on_heard(ln, {"state": "new", "src": "SV1ABC", "dst": "ALL", "gw": ""})
    ctx._on_heard(ln, {"state": "new", "src": "SV1ABC", "dst": "ALL", "gw": ""})
    assert [h["src"] for h in ctx.last_heard] == ["SV1ABC", "69/SA7SVR"] and ctx.last_heard[0]["me"] is False
    from app.ui.heardpage import HeardPage, html_rows
    pg = HeardPage(ctx); assert pg.tbl.rowCount() == 2 and pg.tbl.item(1, 5).text() == "2 s" and "ALL" in pg.tbl.item(0, 2).text()
    assert "SV1ABC" in html_rows(ctx.last_heard, "#888") and "(you)" in html_rows(ctx.last_heard, "#888")
