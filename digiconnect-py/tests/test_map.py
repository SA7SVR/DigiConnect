"""The Map page: it zooms, moves, shows who is where, and every station lands in its country (the 2.3.5 map had none of this)."""
import os, sys, pathlib, types, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app.qt import QtWidgets as W, QtCore, QtGui, Qt
from app import countries, online, i18n
from app.ui import mappage
from app.ui.mappage import MapPage, WorldMap, centre_of, bubble_radius


def _page(monkeypatch, heard=(), el=(), onl=()):
    monkeypatch.setattr(online, "fetch", lambda: list(onl))
    ctx = types.SimpleNamespace(last_heard=list(heard), el_stations=list(el))
    pg = MapPage(ctx); pg.resize(1100, 640); pg.show()
    time.sleep(0.15); W.QApplication.processEvents()                                  # the background fetch has answered and its signal is delivered
    return pg


def _el(n, country="United States"): return [dict(id=f"{country[:3].upper()}{i}", country=country) for i in range(n)]


def _click(w, x, y, button=Qt.MouseButton.LeftButton):
    pt = QtCore.QPointF(x, y); gp = w.mapToGlobal(pt)
    for t in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
        W.QApplication.sendEvent(w, QtGui.QMouseEvent(t, pt, gp, button, button, Qt.KeyboardModifier.NoModifier))


def _drag(w, x0, y0, x1, y1):
    mk = lambda t, x, y, b, bs: QtGui.QMouseEvent(t, QtCore.QPointF(x, y), w.mapToGlobal(QtCore.QPointF(x, y)), b, bs, Qt.KeyboardModifier.NoModifier)
    L = Qt.MouseButton.LeftButton
    W.QApplication.sendEvent(w, mk(QtCore.QEvent.Type.MouseButtonPress, x0, y0, L, L))
    W.QApplication.sendEvent(w, mk(QtCore.QEvent.Type.MouseMove, (x0 + x1) / 2, (y0 + y1) / 2, Qt.MouseButton.NoButton, L))
    W.QApplication.sendEvent(w, mk(QtCore.QEvent.Type.MouseMove, x1, y1, Qt.MouseButton.NoButton, L))
    W.QApplication.sendEvent(w, mk(QtCore.QEvent.Type.MouseButtonRelease, x1, y1, L, Qt.MouseButton.NoButton))


def _wheel(w, x, y, delta):
    pt = QtCore.QPointF(x, y)
    ev = QtGui.QWheelEvent(pt, w.mapToGlobal(pt), QtCore.QPoint(0, 0), QtCore.QPoint(0, delta), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                           Qt.ScrollPhase.NoScrollPhase, False)
    W.QApplication.sendEvent(w, ev)


def test_every_country_of_the_program_is_placed_except_the_european_union():
    names = set(countries._table().values())
    unplaced = sorted(n for n in names if not centre_of(n))
    assert unplaced == ["European Union"]
    assert centre_of("United States") and centre_of("Türkiye") and centre_of("Singapore") and centre_of("Malta") and centre_of("Greece")
    lon, lat = centre_of("United States"); assert -130 < lon < -60 and 25 < lat < 55          # the contiguous states, not Alaska or Hawaii
    lon, lat = centre_of("Singapore"); assert 103 < lon < 104.5 and 1 < lat < 2


def test_300_stations_in_one_country_are_one_circle_with_the_number(monkeypatch):
    pg = _page(monkeypatch, el=_el(300))
    pg.map.grab()                                                                # paints
    assert len(pg.map._hits) == 1
    x, y, r, name, items = pg.map._hits[0]
    assert name == "United States" and len(items) == 300 and r <= 20.0
    assert bubble_radius(1) < bubble_radius(10) < bubble_radius(1000) == 20.0
    assert "United States (300)" in [pg.cty.itemText(i) for i in range(pg.cty.count())]
    assert "300 stations" in pg.count.text() and "EchoLink 300" in pg.legend.text()
    assert "300" in pg.map.tooltip_for(pg.map._hits[0]) and "United States" in pg.map.tooltip_for(pg.map._hits[0])


def test_wheel_zoom_keeps_the_place_under_the_mouse_and_is_clamped(monkeypatch):
    pg = _page(monkeypatch); m = pg.map
    px, py = 300.0, 200.0
    u = m.u0 + px / (m.width() * m.zoom); v = m.v0 + py / (m.height() * m.zoom)
    _wheel(m, px, py, 120)
    assert m.zoom > 1.0
    assert abs((m.u0 + px / (m.width() * m.zoom)) - u) < 1e-9 and abs((m.v0 + py / (m.height() * m.zoom)) - v) < 1e-9
    for _ in range(80): _wheel(m, px, py, 120)
    assert m.zoom == m.ZMAX
    for _ in range(200): _wheel(m, px, py, -120)
    assert m.zoom == m.ZMIN and m.u0 == 0.0 and m.v0 == 0.0
    m.btn["in"].click(); z1 = m.zoom; assert z1 > 1.0
    m.btn["out"].click(); assert m.zoom < z1
    m.btn["in"].click(); m.btn["in"].click(); m.btn["reset"].click(); assert (m.zoom, m.u0, m.v0) == (1.0, 0.0, 0.0)


def test_dragging_moves_the_map_and_stays_inside(monkeypatch):
    pg = _page(monkeypatch); m = pg.map
    m.zoom_at(4.0); u, v = m.u0, m.v0
    _drag(m, 400, 300, 300, 250)
    assert m.u0 > u and m.v0 > v                                                   # dragged left/up: the view goes right/down
    _drag(m, 100, 100, 5000, 5000); assert m.u0 >= 0.0 and m.v0 >= 0.0
    _drag(m, 5000, 5000, 0, 0); _drag(m, 5000, 5000, 0, 0)
    assert m.u0 <= 1.0 - 1.0 / m.zoom + 1e-9 and m.v0 <= 1.0 - 1.0 / m.zoom + 1e-9
    m.reset_view(); _drag(m, 400, 300, 100, 100); assert (m.u0, m.v0) == (0.0, 0.0)  # whole world: nothing to move


def test_click_on_a_circle_chooses_the_country_filters_the_table_and_zooms(monkeypatch):
    pg = _page(monkeypatch, el=_el(30) + _el(5, "Greece") + _el(2, "Sweden")); m = pg.map; m.grab()
    assert len(m._hits) == 3 and pg.table.rowCount() == 37
    gr = next(h for h in m._hits if h[3] == "Greece")
    _click(m, gr[0], gr[1])
    assert pg.cty.currentData() == "greece" and m.selected == "greece" and m.zoom >= 4.0
    assert pg.table.rowCount() == 5 and {pg.table.item(i, 2).text() for i in range(5)} == {"Greece"}
    assert "5 stations" in pg.count.text()
    # the Country box back to all: the whole world and all the rows again
    pg.cty.setCurrentIndex(0); pg.cty.activated.emit(0)
    assert pg.table.rowCount() == 37 and m.zoom == 1.0
    # a row of the table chooses its country too
    pg._row_clicked(0, 2); assert pg.cty.currentData() != ""
    # a click on the empty sea changes nothing
    pg.cty.setCurrentIndex(0); pg.cty.activated.emit(0); m.grab(); n = pg.table.rowCount()
    _click(m, 3, m.height() - 3); assert pg.cty.currentData() == "" and pg.table.rowCount() == n


def test_country_box_zooms_to_the_country_and_survives_refresh(monkeypatch):
    pg = _page(monkeypatch, el=_el(4, "Sweden") + _el(9)); m = pg.map
    i = pg.cty.findData("sweden"); assert i > 0
    pg.cty.setCurrentIndex(i); pg.cty.activated.emit(i)
    assert m.zoom >= 4.0 and pg.table.rowCount() == 4
    z, u0, v0 = m.zoom, m.u0, m.v0
    pg.refresh(); pg.refresh()
    assert pg.cty.currentData() == "sweden" and (m.zoom, m.u0, m.v0) == (z, u0, v0) and pg.table.rowCount() == 4
    ctr = centre_of("sweden"); x, y = m._xy(*ctr); assert 0 <= x <= m.width() and 0 <= y <= m.height()    # the country is in view
    # a network filter that removes the country does not leave a stale choice
    pg.net.setCurrentText("DMR"); assert pg.cty.currentData() == "" and pg.table.rowCount() == 0


def test_a_station_with_an_exact_place_is_a_dot_not_part_of_a_circle(monkeypatch):
    onl = [dict(call="SA7SVR", rx="", tx="", grid="JO87", ptt=False)]
    monkeypatch.setattr(online, "net_of", lambda rx, tx: "EchoLink"); monkeypatch.setattr(online, "grid_centre", lambda g: (14.0, 57.5))
    pg = _page(monkeypatch, el=_el(3, "Sweden"), onl=onl); m = pg.map; m.grab()
    dots = [h for h in m._hits if len(h[4]) == 1 and h[4][0].get("pos")]
    circles = [h for h in m._hits if not (len(h[4]) == 1 and h[4][0].get("pos"))]
    assert len(dots) == 1 and dots[0][2] == 5.0 and dots[0][4][0]["call"] == "SA7SVR"
    assert len(circles) == 1 and len(circles[0][4]) == 3                                       # the exact one is not counted in the circle
    x, y = m._xy(14.0, 57.5); assert abs(dots[0][0] - x) < 1e-6 and abs(dots[0][1] - y) < 1e-6


def test_united_states_and_turkiye_are_drawn(monkeypatch):
    pg = _page(monkeypatch, el=_el(2, "United States") + _el(2, "Türkiye") + _el(1, "Singapore")); pg.map.grab()
    assert {h[3] for h in pg.map._hits} == {"United States", "Türkiye", "Singapore"} and "not on the map" not in pg.count.text()


def test_unknown_country_is_counted_not_hidden(monkeypatch):
    pg = _page(monkeypatch, el=_el(2, "European Union") + _el(1, "Greece")); pg.map.grab()
    assert "2 not on the map" in pg.count.text() and pg.table.rowCount() == 3 and len(pg.map._hits) == 1


def test_greek_texts_of_the_map_page(monkeypatch):
    i18n.set_language("Ελληνικά")
    try:
        pg = _page(monkeypatch, el=_el(3))
        assert "σταθμοί" in pg.count.text() and "χώρες" in pg.count.text() and pg.cty.itemText(0) == "Όλες οι χώρες"
        assert "zoom" in pg.sub.text() and pg.map.btn["in"].toolTip() == "Μεγέθυνση"
        assert pg.table.horizontalHeaderItem(0).text() == "Διακριτικό"
    finally: i18n.set_language("English")
