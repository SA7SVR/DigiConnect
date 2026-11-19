"""The server side of engine updates, against the real PHP code: engine packages are uploaded in the panel, the manifest offers the right one for each
system inside the SIGNED part, download.php serves it, and the panel shows what is missing before a release is made active."""
import gzip, hashlib, json, re, urllib.error, urllib.parse, urllib.request, uuid
import pytest
from test_license import srv, shutil  # noqa: F401
from test_server_payments import Admin
from app import sigverify

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


def multipart(fields, files):
    """files: [(field, filename, bytes)] -> (body, content-type)"""
    b = uuid.uuid4().hex; out = b""
    for k, v in fields.items(): out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, fn, data in files: out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n"
    return out + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def upload(a, page, action, files, **fields):
    tok = re.search(r'name="csrf" value="([0-9a-f]+)"', a.page(page)).group(1)
    body, ct = multipart(dict(csrf=tok, p=page, a=action, **fields), files)
    return a.op.open(urllib.request.Request(a.base, body, {"Content-Type": ct})).read().decode()


def dcpkg(version, min_engine):
    return gzip.compress(json.dumps({"app": "digiconnect-py", "format": 2, "version": version, "minShell": "2.0.0", "minEngine": min_engine, "files": {"app/__init__.py": ""}}).encode())


def manifest(srv, os_, arch, nonce="a" * 32):
    q = urllib.parse.urlencode(dict(id="inst-1", v="2.0.0", os=os_, arch=arch, shell="2.2.0", n=nonce))
    return json.loads(urllib.request.urlopen(srv.base + "manifest.php?" + q).read())


def test_engine_packages_are_offered_to_the_right_system_inside_the_signed_offer(srv):
    a = Admin(srv.base)
    upload(a, "releases", "rel_upload", [("pkg", "DigiConnect-2.9.5.dcpkg", dcpkg("2.9.5", "9.0.0"))])
    r = srv.sql("SELECT * FROM dc_releases")[0]; assert (r["version"], r["min_engine"]) == ("2.9.5", "9.0.0")
    win = b"\x1f\x8b" + b"windows engine bytes" * 100; lin = b"\x1f\x8b" + b"linux engine bytes" * 100; old = b"\x1f\x8b" + b"old mac engine" * 100
    page = upload(a, "releases", "eng_upload", [("eng[]", "DigiConnect-engine-9.0.0-windows-x64.dceng", win), ("eng[]", "DigiConnect-engine-9.0.0-linux-x64.dceng", lin),
                                              ("eng[]", "DigiConnect-engine-8.0.0-macos-arm64.dceng", old), ("eng[]", "evil.dceng", b"\x1f\x8bx"), ("eng[]", "DigiConnect-engine-9.0.0-macos-x64.dceng", b"not gzip")])
    rows = {(e["version"], e["os"], e["arch"]): e for e in srv.sql("SELECT * FROM dc_engines")}
    assert set(rows) == {("9.0.0", "windows", "x64"), ("9.0.0", "linux", "x64"), ("8.0.0", "macos", "arm64")}          # the badly named and the non-package files were refused
    assert "evil.dceng" in page and "DigiConnect-engine-9.0.0-macos-x64.dceng" in page          # the panel names the refused files
    assert rows[("9.0.0", "windows", "x64")]["sha256"] == hashlib.sha256(win).hexdigest() and rows[("9.0.0", "windows", "x64")]["size"] == len(win)
    a.post("releases", "rel_forceall", version="2.9.5")

    n = "c" * 32
    for os_, arch, blob in (("windows", "x64", win), ("linux", "x64", lin)):
        m = manifest(srv, os_, arch, n); assert m["update"] == "available" and m["version"] == "2.9.5"
        assert any(sigverify.verify(srv.pub, m["upd"].encode(), m["upd_sig"]) for _ in [0]), "the offer must be signed"
        d = json.loads(m["upd"]); assert d["n"] == n and d["min_engine"] == "9.0.0"
        assert d["eng"] == {"version": "9.0.0", "sha256": hashlib.sha256(blob).hexdigest(), "size": len(blob)}               # hash and size are in the SIGNED part
        assert urllib.request.urlopen(m["engine_pkg"]).read() == blob                                                            # and the download is exactly that file
    for os_, arch in (("macos", "arm64"), ("macos", "x64"), ("windows", "arm64")):                                               # no suitable engine: only the requirement, no 'eng'
        m = manifest(srv, os_, arch, n); d = json.loads(m["upd"])
        assert d["min_engine"] == "9.0.0" and "eng" not in d and "engine_pkg" not in m, (os_, arch)                              # 8.0.0 is older than the release needs

    for q, code in (("f=engine&v=9.0.0&os=windows&arch=x64", 200), ("f=engine&v=9.0.0&os=macos&arch=x64", 404), ("f=engine&v=9.0.0&os=beos&arch=x64", 400),
                    ("f=engine&v=../../x&os=windows&arch=x64", 400), ("f=engine&v=9.0.0&os=windows&arch=../x", 400)):
        try: got = urllib.request.urlopen(srv.base + "download.php?" + q).status
        except urllib.error.HTTPError as e: got = e.code
        assert got == code, q

    html = a.page("releases")
    assert not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", html)
    assert "✓ windows/x64" in html and "✓ linux/x64" in html and "✗ macos/arm64" in html and "✗ macos/x64" in html           # the panel shows what is missing before going live
    a.post("releases", "eng_del", eid=str(rows[("9.0.0", "linux", "x64")]["id"]))
    assert ("9.0.0", "linux", "x64") not in {(e["version"], e["os"], e["arch"]) for e in srv.sql("SELECT * FROM dc_engines")}


def test_a_release_without_an_engine_requirement_offers_none(srv):
    a = Admin(srv.base)
    upload(a, "releases", "rel_upload", [("pkg", "DigiConnect-2.9.6.dcpkg", dcpkg("2.9.6", "0"))])
    upload(a, "releases", "eng_upload", [("eng[]", "DigiConnect-engine-9.0.0-windows-x64.dceng", b"\x1f\x8b" + b"x" * 50)])
    a.post("releases", "rel_forceall", version="2.9.6")
    d = json.loads(manifest(srv, "windows", "x64")["upd"])
    assert d["version"] == "2.9.6" and "min_engine" not in d and "eng" not in d


@pytest.mark.parametrize("lang,win,mac", [("el", "Περισσότερες πληροφορίες › Εκτέλεση", "Άνοιγμα ούτως ή άλλως"), ("en", "More info › Run anyway", "Open Anyway"),
                                          ("sv", "Mer information › Kör ändå", "Öppna ändå"), ("it", "Ulteriori informazioni › Esegui comunque", "Apri comunque")])
def test_the_download_section_explains_the_windows_and_mac_warnings_in_every_language(srv, lang, win, mac):
    html = urllib.request.urlopen(srv.base + "index.php?lang=" + lang).read().decode()
    assert not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", html)
    assert win in html and mac in html and "DigiConnect-Setup.exe" in html
