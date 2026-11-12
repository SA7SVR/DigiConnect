"""World-wide server lists: parsers (the formats of the public host files), a real HTTP download from a local
test server, the offline cache, and the connection lookup that uses the downloaded entries."""
import os, sys, pathlib, tempfile, threading, http.server, functools
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app import hostlists as H
from app.rules import Target

YSF = """# YSF hosts
00006;GR-HELLAS;Zone A (YCS202);ysf.example.gr;42000;012
00010;DX Zone;with www.note.org in text;dx.example.gr;42001;003
10001;Some Reflector;desc;93.184.216.34;42000;000
FCS00101;FCS001-01;foo;fcs001.xreflector.net;62500;000
badline
"""
DPLUS = "# dplus\nREF001\t1.2.3.4\t20001\nREF030  ref030.example.org  20001\nXYZ999 9.9.9.9\n"
DEXTRA = "XRF001  xrf001.example.net  30001\nXRF757\t5.6.7.8\n"
DCS = "DCS001;dcs001.example.com;30051\n"
XLX = "XLX001;xlx001.example.org;4\nXLXQRZ;xlxqrz.example.gr;\n"
NXDN = "# nxdn\n65000 nxdn.example.org 41400\n10200;nxdn2.example.org;41401\nbad\n"
P25 = "10100 p25.example.org 41000\n10200 192.0.2.7\n"
M17 = "M17-DEU  m17-deu.example.org  17000\nM17-USA  203.0.113.5\nfoo bar\n"
M17CSV = "# name,?,host,?,port\nM17-DEU,x,m17-deu.example.org,y,17000\nM17-USA,x,203.0.113.5,y,17001\nbad,line\n"
DSJSON = '{"reflectors":[{"name":"REF001","reflector_type":"REF","ipv4":"1.2.3.4"},{"name":"XRF002","reflector_type":"XRF","ipv4":"5.6.7.8"},{"name":"DCS003","reflector_type":"DCS","ipv4":"x"}]}'
DMR = ("# name\n"
       "BM_Greece_202\t0\t0\t0\t0\tgreece.master.example.net\tpassw0rd\t62031\n"
       "BM_United_States_3101\t0\t0\t0\t0\t3101.master.example.net\tpassw0rd\t62031\n"
       "DMR+_IPSC2-Test\t0\t0\t0\t0\tdmrplus.example.de\tpassw0rd\t55555\n")
XLXAPI = """<?xml version="1.0"?><reflectorlist><reflector><name>XLX001</name><lastip>1.1.1.1</lastip><dns>xlx001.example.org</dns><country>Germany</country><comment>Test net</comment></reflector>
<reflector><name>XLX999</name><dns>xlx999.example.org</dns><country>Sweden</country></reflector></reflectorlist>"""


def test_parsers():
    y = H.parse_ysf(YSF); assert [e["id"] for e in y] == ["00006", "00010", "10001"]       # FCS and junk are not YSF
    assert y[0]["host"] == "ysf.example.gr" and y[0]["port"] == 42000
    assert y[1]["host"] == "dx.example.gr" and y[1]["port"] == 42001                          # a dotted word in the description is not the host
    assert y[2]["host"] == "93.184.216.34"
    d = H.parse_dstar(DPLUS, "REF"); assert [(e["id"], e["host"], e["port"]) for e in d] == [("REF001 C", "1.2.3.4", 20001), ("REF030 C", "ref030.example.org", 20001), ("XYZ999 C", "9.9.9.9", 20001)]
    x = H.parse_dstar(DEXTRA, "XRF"); assert x[1]["host"] == "5.6.7.8" and x[1]["port"] == 30001   # default port when the file has none
    assert H.parse_dstar(DCS, "DCS")[0]["host"] == "dcs001.example.com"
    assert [e["id"] for e in H.parse_dstar(XLX, "XLX")] == ["XLX001 A", "XLXQRZ A"]
    m = H.parse_dmr(DMR); assert len(m) == 3 and m[0]["country"] == "Greece" and m[1]["country"] == "United States" and m[2]["port"] == 55555
    assert m[0]["host"] == "greece.master.example.net" and m[0]["port"] == 62031
    nx = H.parse_numeric(NXDN, "NXDN"); assert [(e["id"], e["host"], e["port"]) for e in nx] == [("65000", "nxdn.example.org", 41400), ("10200", "nxdn2.example.org", 41401)]
    p = H.parse_numeric(P25, "P25"); assert p[1]["host"] == "192.0.2.7" and p[1]["port"] == 41000 and p[0]["net"] == "P25"
    m7 = H.parse_m17(M17); assert [(e["id"], e["port"]) for e in m7] == [("M17-DEU A", 17000), ("M17-USA A", 17000)]
    m7c = H.parse_m17(M17CSV); assert [(e["id"], e["host"], e["port"]) for e in m7c] == [("M17-DEU A", "m17-deu.example.org", 17000), ("M17-USA A", "203.0.113.5", 17001)]
    dj = H.parse_dstar(DSJSON, "REF"); assert [(e["id"], e["host"], e["port"]) for e in dj] == [("REF001 C", "1.2.3.4", 20001)] and H.parse_dstar(DSJSON, "XRF")[0]["host"] == "5.6.7.8"
    assert [e["id"] for e in H.parse_dstar("XLX307\t9.9.9.9\nPY2KEP\tpy.example.org\n", "REF")] == ["XLX307 C", "PY2KEP C"]   # dplus.txt also lists non-REF names
    a = H.parse_xlx_api(XLXAPI); assert {e["id"] for e in a} == {"XLX001 A", "XLX999 A"} and a[0]["country"] == "Germany"


TGJSON = '{"91": "World-wide", "202": "Greece", "20208": {"name": "Hellas Zone"}, "x": "skip", "0": "zero"}'


def test_parse_tg():
    t = H.parse_tg(TGJSON); assert [(e["id"], e["net"]) for e in t] == [("91", "DMR"), ("202", "DMR"), ("20208", "DMR")] and "Hellas Zone" in t[2]["name"]
    assert [e["id"] for e in H.parse_tg('[{"id": 2, "name": "Cluster"}, {"TG": "9"}]')] == ["2", "9"]
    assert [e["id"] for e in H.parse_tg("240;Sweden\n# c\nabc;no\n262,Germany\n")] == ["240", "262"]


@pytest.fixture
def web(tmp_path):
    root = tmp_path / "www"; root.mkdir()
    for n, t in {"YSFHosts.txt": YSF, "dplus.txt": DPLUS, "dextra.txt": DEXTRA, "dcs.txt": DCS, "XLXHosts.txt": XLX, "DMRHosts.txt": DMR, "TalkGroups.json": TGJSON, "NXDNHosts.txt": NXDN, "P25Hosts.txt": P25, "M17Hosts-full.csv": M17CSV, "xlx.xml": XLXAPI}.items():
        (root / n).write_text(t, encoding="utf-8")
    (root / "FCSRooms.txt").write_text("FCS00134;Greece;FCS001 - Greece;;;\n", encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/", root
    srv.shutdown()


def test_download_cache_and_resolve(tmp_path, web):
    base, root = web
    store = type("S", (), {"root": tmp_path / "d", "settings": {}})(); store.root.mkdir()
    hl = H.HostLists(store.root); assert hl.stale() and not hl.entries
    # first mirror is dead on purpose: the second one must be used
    n, problems = hl.download(mirrors=["http://127.0.0.1:9/", base], xlx_api=base + "xlx.xml")
    assert not problems and n >= 10, (n, problems)
    assert {k: v for k, v in hl.status.items()} and all(v.startswith("ok") for v in hl.status.values()), hl.status
    assert hl.find("YSF", "00006") == {"host": "ysf.example.gr", "port": 42000}
    assert hl.find("REF", "ref030") == {"host": "ref030.example.org", "port": 20001}
    assert hl.find("NXDN", "65000")["host"] == "nxdn.example.org" and hl.find("P25", "10100")["port"] == 41000 and hl.find("M17", "M17-DEU")["host"] == "m17-deu.example.org"
    assert hl.find("XLX", "XLX999")["host"] == "xlx999.example.org"                          # added from the API
    assert [e["country"] for e in hl.entries if e["id"] == "XLX001 A"] == ["Germany"]
    assert len(hl.dmr_masters()) == 3 and [e["id"] for e in hl.for_net("DMR")] == ["91", "202", "20208"] and len(hl.for_net("C4FM")) == 4 and len(hl.for_net("D-Star")) >= 6
    assert not hl.stale()
    # persisted: a new object (a later start of the program, maybe offline) sees the same data
    again = H.HostLists(store.root); assert len(again.entries) == len(hl.entries) and again.find("XRF", "XRF001")["host"] == "xrf001.example.net"
    # one list disappears from the server: the old copy of it is kept, the problem is reported
    (root / "dcs.txt").unlink()
    n2, problems2 = hl.download(mirrors=[base], xlx_api="")
    assert any("DCS" in p for p in problems2) and hl.find("DCS", "DCS001")["host"] == "dcs001.example.com"
    # everything unreachable: nothing is lost
    before = len(hl.entries); n3, p3 = hl.download(mirrors=["http://127.0.0.1:9/"], xlx_api="")
    assert len(hl.entries) == before and p3


def test_servers_resolve_from_lists(tmp_path, web):
    from app.servers import Servers
    base, _ = web
    store = type("S", (), {"root": tmp_path / "d2", "settings": {}})(); store.root.mkdir()
    sv = Servers(store); assert sv.resolve(Target("C4FM", "00006")) is None                  # nothing downloaded: never guessed
    sv.hosts.download(mirrors=[base], xlx_api="")
    assert sv.resolve(Target("C4FM", "00006")) == {"host": "ysf.example.gr", "port": 42000}
    assert sv.resolve(Target("D-Star", "REF001 B")) == {"host": "1.2.3.4", "port": 20001}    # module is not part of the address
    assert sv.resolve(Target("D-Star", "XRF757 A")) == {"host": "5.6.7.8", "port": 30001}
    assert sv.resolve(Target("C4FM", "99999")) is None
    sv.user["C4FM:00006"] = {"host": "mine.example", "port": 1}                              # the user's own entry wins
    assert sv.resolve(Target("C4FM", "00006")) == {"host": "mine.example", "port": 1}


def test_directory_and_ui(tmp_path, web):
    from app.qt import QtWidgets
    from app.store import Store
    from app.context import Ctx
    from app.theme import qss
    from app.ui.main_window import MainWindow
    base, _ = web
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    (tmp_path / "ui").mkdir(); st = Store(tmp_path / "ui"); st.settings["callsign"] = "SA7SVR"
    ctx = Ctx(st); app.setStyleSheet(qss(14)); w = MainWindow(ctx); w.show(); app.processEvents()
    ws = w.ws["D-Star"]; before = ws.list.count()
    assert "not downloaded yet" in ws.count.text()
    ctx.hosts.download(mirrors=[base], xlx_api=base + "xlx.xml"); ctx.hosts_changed.emit(); app.processEvents()
    texts = [ws.list.item(i).text() for i in range(ws.list.count())]
    assert any("REF030" in t for t in texts) and ws.list.count() > before
    assert "Germany" in [ws.country.itemText(i) for i in range(ws.country.count())]
    ws.country.setCurrentText("Germany"); app.processEvents(); assert all("XLX001" in ws.list.item(i).text() for i in range(ws.list.count())) and ws.list.count() == 1
    ws.country.setCurrentIndex(0); ws.search.setText("REF030"); app.processEvents(); assert ws.list.count() == 1
    ws.module.setCurrentText("F"); ws.list.setCurrentRow(0); assert ctx.selected == Target("D-Star", "REF030 F", "REF030")
    # the server card shows the address read from the downloaded list for whatever is selected
    assert ws.srv_host.text() == "ref030.example.org" and ws.srv_port.text() == "20001" and "worldwide" in ws.srv_src.text()
    cw = w.ws["C4FM"]; assert cw.list.count() == len(ctx.hosts.for_net("C4FM")) >= 3          # nothing invented: exactly what the list holds
    cw.search.setText("00006"); app.processEvents(); cw.list.setCurrentRow(0)
    assert (cw.srv_host.text(), cw.srv_port.text()) == ("ysf.example.gr", "42000")
    cw.srv_host.setText("mine.example"); cw.srv_port.setText("42001"); cw.srv_save.click(); app.processEvents()
    assert ctx.servers.resolve(Target("C4FM", "00006")) == {"host": "mine.example", "port": 42001} and "your own" in cw.srv_src.text()
    cw.srv_reset.click(); app.processEvents(); assert cw.srv_host.text() == "ysf.example.gr" and cw.srv_port.text() == "42000"
    cw.srv_host.setText("bad host"); cw.srv_save.click(); assert ctx.servers.resolve(Target("C4FM", "00006"))["host"] == "ysf.example.gr"   # invalid input is refused
    # DMR / NXDN / P25: a typed talkgroup number that is not in the catalogue can still be used
    dw = w.ws["DMR"]; dw.search.setText("20208"); app.processEvents(); assert dw.list.count() >= 1 and "20208" in dw.list.item(0).text()
    dw.list.setCurrentRow(0); assert ctx.selected.id == "20208" and ctx.selected.net == "DMR"
    w.close()


def test_real_pistar_formats():
    """Lines exactly as in the Pi-Star / WPSD host files: names and descriptions come from the list, nothing is added by us."""
    y = H.parse_ysf("00006;GR-HELLAS Zone A;(YCS202);185.243.214.85;42000;010\n62674;----------------;EXPERIMENTS;198.251.70.144;42003;000\n")
    assert y[0]["name"] == "YSF00006 - GR-HELLAS Zone A - (YCS202)" and y[0]["host"] == "185.243.214.85" and y[0]["port"] == 42000
    d = H.parse_dmr("DMRGateway\t\t\t0000\t127.0.0.1\t\t\t\tnone\t\t62031\n"
                    "BM_2402_Sweden\t\t\t2402\t2402.master.brandmeister.network\t\tpassw0rd\t62031\n"
                    "DMR+_IPSC2-ANDALUCIA\t\t124734\t141.94.206.232\t\t\t\tPASSWORD\t55555\n"
                    "XLX_493\t\t\t\t0000\t104.218.221.46\t\t\t\tpassw0rd\t62030\n")
    assert [e["name"] for e in d] == ["BM_2402_Sweden", "DMR+_IPSC2-ANDALUCIA", "XLX_493"]      # local gateway lines are not servers
    assert d[0]["country"] == "Sweden" and d[0]["port"] == 62031 and d[1]["port"] == 55555 and d[2]["port"] == 62030
    x = H.parse_dstar("000;71.41.121.226;4004\n", "XLX"); assert x[0]["id"] == "XLX000 A" and x[0]["port"] == 30051
    t = H.parse_tg("1;0;LOCAL;TG1\n240;0;SWEDEN;TG240\n"); assert t[1]["name"] == "TG 240 · SWEDEN"
    assert H.HostLists.candidates("YSF")[0].startswith("https://hostfiles.w0chp.net/") and H.HostLists.candidates("TG")[0].startswith("https://api.brandmeister")


def test_fcs_rooms():
    """FCS room list as published (id;name;description): address = <FCS###>.xreflector.net:62500 (the rule YSFGateway uses); the engine gets the room id."""
    f = H.parse_fcs("# comment\nFCS00134;Greece;FCS001 - Greece;;;\nFCS20269;Greece;FCS202 - Greece;;;\nbad line\n")
    assert [e["id"] for e in f] == ["FCS00134", "FCS20269"] and f[1]["name"] == "FCS20269 - Greece" and f[1]["sub"] == "FCS202 - Greece"
    assert f[1]["host"] == "fcs202.xreflector.net" and f[1]["port"] == 62500 and f[1]["net"] == "C4FM"
    from app.servers import Servers
    import tempfile, pathlib
    from app.store import Store
    hl = H.HostLists(pathlib.Path(tempfile.mkdtemp())); hl._set(f, {}, 1.0)
    assert hl.find("FCS", "FCS20269") == dict(host="fcs202.xreflector.net", port=62500) and [e["id"] for e in hl.for_net("C4FM")] == ["FCS00134", "FCS20269"]


def test_dmr_networks_come_from_the_list_names():
    d = H.parse_dmr("BM_2402_Sweden\t\t\t2402\t2402.master.brandmeister.network\t\tpassw0rd\t62031\n"
                    "BM_2022_Greece\t\t\t2022\t2022.master.brandmeister.network\t\tpassw0rd\t62031\n"
                    "DMR+_IPSC2-ANDALUCIA\t\t124734\t141.94.206.232\t\t\t\tPASSWORD\t55555\n"
                    "FreeDMR_Spain\t\t\t1\tfreedmr.example.org\t\tpassw0rd\t62031\n")
    hl = H.HostLists.__new__(H.HostLists); hl.entries = d
    assert [H.HostLists.dmr_network(e) for e in d] == ["BrandMeister", "BrandMeister", "DMR+", "FreeDMR"]
    assert hl.dmr_networks()[0] == ("BrandMeister", 2) and {n for n, _ in hl.dmr_networks()} == {"BrandMeister", "DMR+", "FreeDMR"}
