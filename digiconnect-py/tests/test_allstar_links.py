"""Stations connected to an AllStar node, read from the AllStarLink stats server (sample = the real answer for node 509830)."""
import json, threading, http.server
from app import allstar

SAMPLE = r'''{"stats":{"id":24313,"node":509830,"data":{"links":["63618","63938"],"keyed":false,"nodes":"T63618,T63938","linkedNodes":[{"Node_ID":81109,"User_ID":"SV1GGF","Status":"Active","name":63618,"callsign":"SV1GGF","server":{"Server_Name":"SV1GGF NODE","Location":"Piraeus "}},{"Node_ID":81958,"User_ID":"DL4LGV","Status":"Active","name":63938,"callsign":"DL4LGV","server":{"Server_Name":"DL4LGV","Location":"JO42tk"}}]},"user_node":{"name":509830,"callsign":"HELLAS Zone Net","server":{"Server_Name":"HELLAS Zone Server"}}},"node":{"name":509830,"callsign":"HELLAS Zone Net","server":{"Server_Name":"HELLAS Zone Server"}},"keyups":[]}'''


def test_parse_real_answer():
    r = allstar.parse_links(json.loads(SAMPLE))
    assert r["title"] == "HELLAS Zone Server" and r["keyed"] is False
    assert [(x["node"], x["callsign"], x["mode"], x["location"]) for x in r["rows"]] == [("63618", "SV1GGF", "T", "Piraeus"), ("63938", "DL4LGV", "T", "JO42tk")]


def test_numbers_only_when_not_in_directory_and_keyed():
    r = allstar.parse_links({"stats": {"data": {"links": ["1999"], "keyed": True, "nodes": "R1999", "linkedNodes": []}}})
    assert r["keyed"] is True and r["rows"] == [dict(node="1999", callsign="", owner="", location="", site="", mode="R", status="")]


def test_fetch_from_a_local_server_and_errors():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = SAMPLE.encode(); self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ok = allstar.fetch_links("509830", url=f"http://127.0.0.1:{srv.server_port}/api/stats/{{}}")
        assert ok["error"] == "" and len(ok["rows"]) == 2
    finally: srv.shutdown()
    bad = allstar.fetch_links("509830", url="http://127.0.0.1:9/api/stats/{}", timeout=2)
    assert bad["error"] and bad["rows"] == []
    assert allstar.fetch_links("abc")["error"]
