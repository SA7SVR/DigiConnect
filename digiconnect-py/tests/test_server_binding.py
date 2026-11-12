"""Computer binding and signed licences against the real PHP server (php -S)."""
import base64, json, re, urllib.parse, urllib.request
import pytest
from test_license import srv, PERSON, shutil  # noqa: F401
from test_server_payments import Admin
from app import sigverify

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")
HW1, HW2 = "a" * 32, "b" * 32


def call(srv, page, **q):
    return json.loads(urllib.request.urlopen(srv.base + page, urllib.parse.urlencode(q).encode()).read())


def reg(srv, id, hw, **o):
    d = dict(PERSON); d.update(id=id, hw=hw, consent=1, v="2.3.0", os="windows", **o)
    return call(srv, "register.php", **d)


def test_answer_is_signed_and_verifies_with_public_key_only(srv):
    a = call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW1)
    assert a["sig"] and a["payload"]
    assert sigverify.verify(srv.pub, a["payload"].encode(), a["sig"])
    p = json.loads(a["payload"])
    assert p["id"] == "i1" and p["state"] == a["state"] and p["hw"] == HW1 and p["v"] == 2
    # any change of the payload breaks the signature
    assert not sigverify.verify(srv.pub, a["payload"].replace('"state":"demo"', '"state":"full"').encode(), a["sig"])
    # another key does not verify
    other = base64.b64encode(bytes(32)).decode()
    assert not sigverify.verify(other, a["payload"].encode(), a["sig"])


def test_full_licence_stays_on_first_computer(srv):
    call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW1)
    srv.sql("UPDATE dc_installs SET state='full', lic_by='admin' WHERE id='i1'")
    ok = call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW1)
    assert ok["state"] == "full" and not ok["other_pc"]
    bad = call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW2)             # settings folder copied to another computer
    assert bad["state"] == "locked" and bad["other_pc"] == 1
    p = json.loads(bad["payload"]); assert p["state"] == "locked" and p["other_pc"] == 1 and p["hw"] == HW1 and p["code"] == ""
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind='alert_clone' OR kind='clone'")[0]["n"] >= 1
    assert call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW1)["state"] == "full"      # the real computer is not affected


def test_demo_is_not_restarted_by_clone_and_free_computer_works(srv):
    call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW1)
    srv.sql("UPDATE dc_installs SET state='full', lic_by='admin' WHERE id='i1'")
    assert call(srv, "manifest.php", id="i1", hw=HW2)["other_pc"] == 1
    srv.sql("UPDATE dc_installs SET hw='', hw_set=0 WHERE id='i1'")                    # what the panel button does
    r = call(srv, "manifest.php", id="i1", hw=HW2)
    assert r["state"] == "full" and not r["other_pc"]
    assert call(srv, "manifest.php", id="i1", hw=HW1)["other_pc"] == 1                  # now the old computer is the other one


def test_reinstall_on_same_computer_gets_state_back_and_other_computer_does_not_get_full(srv):
    reg(srv, "old", HW1)
    srv.sql("UPDATE dc_installs SET state='full', lic_by='admin', lic_code='DC-1' WHERE id='old'")
    again = reg(srv, "new", HW1)                                                          # same computer, new id
    assert again["state"] == "full" and json.loads(again["payload"])["id"] == "new"
    other = reg(srv, "third", HW2)                                                        # other computer, same callsign + e-mail
    assert other["state"] != "full"
    assert srv.sql("SELECT COUNT(*) n FROM dc_events WHERE kind LIKE '%clone%'")[0]["n"] >= 1


def test_redeem_code_returns_signed_full_and_binds(srv):
    srv.sql("INSERT INTO dc_installs(id,first_seen,last_seen,state,demo_until) VALUES('r1',1,1,'demo',9999999999)")
    cols = [c["name"] for c in srv.sql("PRAGMA table_info(dc_codes)")]
    row = {"code": "ABCD-1", "kind": "full", "dur": 0, "unit": "d", "uses": 1, "used": 0}
    row = {k: v for k, v in row.items() if k in cols}
    srv.sql(f"INSERT INTO dc_codes({','.join(row)}) VALUES({','.join('?'*len(row))})", *row.values())
    r = call(srv, "api.php", action="redeem", id="r1", code="ABCD-1", hw=HW1)
    assert r["ok"] and r["state"] == "full" and sigverify.verify(srv.pub, r["payload"].encode(), r["sig"])
    assert json.loads(r["payload"])["code"] == "ABCD-1"
    assert call(srv, "api.php", action="state", id="r1", hw=HW2)["other_pc"] == 1


def test_missing_key_gives_unsigned_answer_and_panel_warns(srv):
    (srv.root / "license-key.php").unlink()
    (srv.root / "data" / "license-key.bak.php").unlink(missing_ok=True)
    r = call(srv, "manifest.php", id="n1", v="2.3.0", hw=HW1)
    assert r["ok"] and r["sig"] == ""
    assert re.search(r"license-key", Admin(srv.base).page("dashboard"))


def test_panel_free_computer_button_and_clone_alert_visible(srv):
    call(srv, "manifest.php", id="i1", v="2.3.0", hw=HW1)
    srv.sql("UPDATE dc_installs SET state='full', lic_by='admin', call='SV1ABC' WHERE id='i1'")
    call(srv, "manifest.php", id="i1", hw=HW2)
    a = Admin(srv.base)
    inst = a.page("installs")
    assert "hw_free" in inst and HW1[:8] in inst
    assert "ΑΛΛΟΝ υπολογιστή" in a.page("dashboard") or "ANOTHER computer" in a.page("dashboard")
    a.post("installs", "hw_free", id="i1")                                       # the button
    assert srv.sql("SELECT hw FROM dc_installs WHERE id='i1'")[0]["hw"] == ""
    assert call(srv, "manifest.php", id="i1", hw=HW2)["state"] == "full"


def test_key_survives_deleting_the_folder_copy(srv):
    call(srv, "manifest.php", id="k1", v="2.3.0", hw=HW1)                          # first signed answer makes the safety copy in data/
    assert (srv.root / "data" / "license-key.bak.php").is_file()
    (srv.root / "license-key.php").unlink()                                          # e.g. the folder was replaced by an update
    a = call(srv, "manifest.php", id="k1", v="2.3.0", hw=HW1)
    assert sigverify.verify(srv.pub, a["payload"].encode(), a["sig"])


def test_registration_approval_is_off_by_default_and_works_when_on(srv):
    assert reg(srv, "a1", HW1)["state"] == "demo"                                       # default: nothing waits
    srv.sql("INSERT INTO dc_kv(k,v) VALUES('reg_approval','1')")
    r = reg(srv, "a2", HW2, mail="new@example.org")
    assert r["state"] == "pending" and "approval" in r["msg"] and sigverify.verify(srv.pub, r["payload"].encode(), r["sig"])
    assert call(srv, "manifest.php", id="a2", hw=HW2)["state"] == "pending"
    a = Admin(srv.base)
    assert "reg_approve" in a.page("installs") and "reg_pending" in [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]
    assert srv.sql("SELECT state FROM dc_installs WHERE id='a1'")[0]["state"] == "demo"      # the one registered before is not touched
    a.post("installs", "reg_approve", id="a2")
    assert call(srv, "manifest.php", id="a2", hw=HW2)["state"] == "demo"                       # approved: the default demo starts now
    r3 = reg(srv, "a3", "c" * 32, mail="third@example.org"); assert r3["state"] == "pending"
    a.post("installs", "reg_reject", id="a3")
    assert call(srv, "manifest.php", id="a3", hw="c" * 32)["state"] == "locked"


def test_reinstall_on_the_same_computer_does_not_wait_for_approval(srv):
    reg(srv, "old", HW1)
    srv.sql("UPDATE dc_installs SET state='full', demo_until=0, lic_by='admin' WHERE id='old'")
    srv.sql("INSERT INTO dc_kv(k,v) VALUES('reg_approval','1')")
    assert reg(srv, "new", HW1)["state"] == "full"


def test_licence_per_major_version(srv):
    a = Admin(srv.base)
    call(srv, "manifest.php", id="v1", v="2.3.0", hw=HW1)
    srv.sql("UPDATE dc_installs SET state='full', demo_until=0, lic_by='admin' WHERE id='v1'")
    assert call(srv, "manifest.php", id="v1", v="3.0.0", hw=HW1)["state"] == "full"            # off by default: a licence covers every version
    srv.sql("INSERT INTO dc_kv(k,v) VALUES('lic_scope','major'),('lic_grandfather','2')")
    assert call(srv, "manifest.php", id="v1", v="2.9.0", hw=HW1)["state"] == "full"            # existing licence = version 2.x
    r = call(srv, "manifest.php", id="v1", v="3.0.0", hw=HW1)
    assert r["state"] == "locked" and "3.x" in r["msg"] and srv.sql("SELECT lic_major FROM dc_installs WHERE id='v1'")[0]["lic_major"] == 2
    a.post("installs", "lic_one", id="v1", do="full")                                           # a new licence for 3.x (code / payment / panel)
    assert srv.sql("SELECT lic_major FROM dc_installs WHERE id='v1'")[0]["lic_major"] == 3
    assert call(srv, "manifest.php", id="v1", v="3.1.0", hw=HW1)["state"] == "full"
    srv.sql("UPDATE dc_installs SET state='free', lic_major=2 WHERE id='v1'")
    assert call(srv, "manifest.php", id="v1", v="9.0.0", hw=HW1)["state"] == "full"            # a free (no limit) installation is never limited


def test_update_offer_is_signed_and_bound_to_the_request(srv):
    srv.sql("INSERT INTO dc_releases(version,min_shell,sha256,size,status,published) VALUES('9.9.9','2.2.0',?,1234,'active',?)", "ab" * 32, 1)
    a = call(srv, "manifest.php", id="u1", v="2.3.0", hw=HW1, n="1" * 32)
    assert a["update"] == "available" and sigverify.verify(srv.pub, a["upd"].encode(), a["upd_sig"])
    d = json.loads(a["upd"]); assert (d["version"], d["sha256"], d["size"], d["n"]) == ("9.9.9", "ab" * 32, 1234, "1" * 32)
    b = call(srv, "manifest.php", id="u1", v="2.3.0", hw=HW1, n="2" * 32)
    assert json.loads(b["upd"])["n"] == "2" * 32 and b["upd_sig"] != a["upd_sig"]                    # another request, another signature
    assert not sigverify.verify(srv.pub, a["upd"].replace("ab" * 32, "cd" * 32).encode(), a["upd_sig"])   # a changed hash does not verify
    assert "upd" not in call(srv, "manifest.php", id="u1", v="9.9.9", hw=HW1, n="3" * 32)             # nothing to install when up to date


def test_program_accepts_the_servers_update_offer_and_refuses_a_forged_one(srv, tmp_path):
    from app import updater as U
    from app.store import Store
    srv.sql("INSERT INTO dc_releases(version,min_shell,sha256,size,status,published) VALUES('9.9.9','2.2.0',?,1234,'active',?)", "ab" * 32, 1)
    (tmp_path / "d").mkdir(); u = U.Updater(Store(tmp_path / "d"), tmp_path / "u", srv.base + "manifest.php", pubkeys=[srv.pub])
    m = call(srv, "manifest.php", id="u1", v="2.3.0", hw=HW1, n="5" * 32)
    assert u.verify_update(m, "5" * 32) == {"version": "9.9.9", "sha256": "ab" * 32, "size": 1234, "min_shell": "2.2.0"}
    with pytest.raises(U.UpdateError, match="replay"): u.verify_update(m, "6" * 32)
    forged = dict(m, upd=m["upd"].replace("ab" * 32, "00" * 32))
    with pytest.raises(U.UpdateError, match="wrong signature"): u.verify_update(forged, "5" * 32)
    with pytest.raises(U.UpdateError, match="not signed"): u.verify_update({k: v for k, v in m.items() if k != "upd_sig"}, "5" * 32)
