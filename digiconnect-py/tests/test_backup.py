"""Backups of the server database (2.3.7): hourly copy, only the last 10 kept, download, restore with one button or from a file — real PHP server code."""
import io, json, re, time, urllib.error, urllib.parse, urllib.request, uuid
import pytest
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_server_payments import Admin

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


def files(srv, why=None):
    d = srv.root / "data" / "backups"
    return sorted(p for p in d.glob("digiconnect-*.sqlite") if why is None or f"-{why}-" in p.name) if d.exists() else []


def clear(srv):
    for p in files(srv): p.unlink()


def installs(srv): return sorted(r["id"] for r in srv.sql("SELECT id FROM dc_installs"))


def php(srv, code):
    import subprocess
    from test_license import _php_flags
    (srv.root / "t_bk.php").write_text("<?php require __DIR__.'/lib.php'; " + code)
    r = subprocess.run(["php", *_php_flags(), str(srv.root / "t_bk.php")], capture_output=True, text=True, cwd=srv.root)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip()


def upload(adm, p, field, name, data, **f):
    """a multipart form post like a browser's file field"""
    tok = re.search(r'name="csrf" value="([0-9a-f]+)"', adm.page(p)).group(1)
    b = uuid.uuid4().hex; body = b""
    for k, v in dict(csrf=tok, p=p, **f).items(): body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + f"\r\n--{b}--\r\n".encode()
    rq = urllib.request.Request(adm.base, body, {"Content-Type": f"multipart/form-data; boundary={b}"})
    return adm.op.open(rq).read().decode()


def two(srv):
    lic(srv, "inst-1").register(PERSON); lic(srv, "inst-2").register(dict(PERSON, mail="two@example.org"))


def test_button_makes_a_copy_that_is_listed_and_can_be_downloaded(srv):
    lic(srv).register(PERSON); clear(srv); a = Admin(srv.base)
    out = a.post("backups", "backup_now"); assert "Backup created" in out or "Δημιουργήθηκε αντίγραφο" in out
    f = files(srv); assert len(f) == 1 and "-manual-" in f[0].name
    page = a.page("backups"); assert f[0].name in page and ("Download" in page or "Λήψη" in page)
    raw = a.op.open(a.base + "?" + urllib.parse.urlencode(dict(p="backups", dl=f[0].name))).read()
    assert raw[:16] == b"SQLite format 3\0" and raw == f[0].read_bytes()
    for bad in ("../lib.php", "digiconnect-x.sqlite", "config.php"):
        with pytest.raises(urllib.error.HTTPError) as e: a.op.open(a.base + "?" + urllib.parse.urlencode(dict(p="backups", dl=bad)))
        assert e.value.code == 404


def test_backup_folder_is_closed_to_the_web_and_the_panel_needs_login(srv):
    lic(srv).register(PERSON); clear(srv); Admin(srv.base).post("backups", "backup_now")
    d = srv.root / "data" / "backups"; assert "Require all denied" in (d / ".htaccess").read_text() and (d / "index.html").exists()
    name = files(srv)[0].name
    anon = urllib.request.urlopen(srv.base + "admin/index.php?p=backups&dl=" + name).read()             # not signed in: the sign-in page, never the file
    assert not anon.startswith(b"SQLite") and b'name="u"' in anon


def test_restore_brings_the_database_back_and_keeps_a_safety_copy(srv):
    lic(srv, "inst-1").register(PERSON); clear(srv); a = Admin(srv.base)
    srv.sql("INSERT OR REPLACE INTO dc_kv(k,v) VALUES('check_every','3600')")
    a.post("backups", "backup_now"); good = files(srv)[0].name
    lic(srv, "inst-2").register(dict(PERSON, mail="two@example.org")); srv.sql("UPDATE dc_kv SET v='60' WHERE k='check_every'")
    srv.sql("DELETE FROM dc_codes"); srv.sql("INSERT INTO dc_events(t,kind,detail) VALUES(1,'later','after the backup')")
    assert installs(srv) == ["inst-1", "inst-2"]
    out = a.post("backups", "backup_restore", file=good, confirm="RESTORE"); assert "Restored from the backup" in out or "Έγινε επαναφορά" in out
    assert installs(srv) == ["inst-1"]                                                              # what came after is gone
    assert srv.sql("SELECT v FROM dc_kv WHERE k='check_every'")[0]["v"] == "3600"                    # settings as they were
    assert not srv.sql("SELECT 1 FROM dc_events WHERE kind='later'")
    pre = files(srv, "pre-restore"); assert len(pre) == 1                                            # the state before the restore is kept ...
    import sqlite3
    c = sqlite3.connect(pre[0]); assert c.execute("SELECT COUNT(*) FROM dc_installs").fetchone()[0] == 2; c.close()
    a.post("backups", "backup_restore", file=pre[0].name, confirm="RESTORE"); assert installs(srv) == ["inst-1", "inst-2"]   # ... so a restore can be undone
    assert a.page("backups")                                                                          # still signed in after a restore
    assert srv.sql("SELECT v FROM dc_kv WHERE k='backup_last'")                                       # backup bookkeeping survived


def test_restore_needs_the_confirmation_and_a_real_copy(srv):
    two(srv); clear(srv); a = Admin(srv.base); a.post("backups", "backup_now"); name = files(srv)[0].name
    lic(srv, "inst-3").register(dict(PERSON, mail="three@example.org"))
    out = a.post("backups", "backup_restore", file=name); assert "not confirmed" in out or "δεν επιβεβαιώθηκε" in out
    assert installs(srv) == ["inst-1", "inst-2", "inst-3"] and not files(srv, "pre-restore")
    out = a.post("backups", "backup_restore", file="../lib.php", confirm="RESTORE"); assert "not found" in out or "Δεν βρέθηκε" in out
    out = a.post("backups", "backup_restore", file="digiconnect-20200101-000000-auto-aaaaaaaaaaaa.sqlite", confirm="RESTORE"); assert "not found" in out or "Δεν βρέθηκε" in out
    assert installs(srv) == ["inst-1", "inst-2", "inst-3"]


def test_restore_from_a_file_on_the_computer_and_refuses_anything_else(srv):
    two(srv); clear(srv); a = Admin(srv.base); a.post("backups", "backup_now"); data = files(srv)[0].read_bytes()
    lic(srv, "inst-3").register(dict(PERSON, mail="three@example.org")); assert len(installs(srv)) == 3
    out = upload(a, "backups", "bkfile", "mine.sqlite", b"hello, I am not a database", a="backup_restore_upload", confirm="RESTORE")
    assert ("not a database" in out or "δεν είναι αντίγραφο" in out) and len(installs(srv)) == 3
    out = upload(a, "backups", "bkfile", "mine.sqlite", b"SQLite format 3\0" + b"\0" * 6000, a="backup_restore_upload", confirm="RESTORE")   # looks like SQLite, is not ours
    assert len(installs(srv)) == 3 and not files(srv, "pre-restore")
    upload(a, "backups", "bkfile", "mine.sqlite", data, a="backup_restore_upload")                                         # no confirmation
    assert len(installs(srv)) == 3
    upload(a, "backups", "bkfile", "mine.sqlite", data, a="backup_restore_upload", confirm="RESTORE")
    assert installs(srv) == ["inst-1", "inst-2"] and len(files(srv, "pre-restore")) == 1


def test_an_automatic_copy_is_made_after_an_hour_by_a_heartbeat_and_not_twice(srv):
    lic(srv).register(PERSON); time.sleep(0.5); clear(srv)
    srv.sql("INSERT OR REPLACE INTO dc_kv(k,v) VALUES('backup_last',?)", str(int(time.time()) - 3700))     # an hour and a bit has passed ...
    srv.sql("INSERT OR REPLACE INTO dc_kv(k,v) VALUES('backup_claim','0')")                                # ... and nobody is making one right now
    urllib.request.urlopen(srv.base + "ping.php?id=inst-1&v=2.3.7").read()
    for _ in range(40):
        if files(srv, "auto"): break
        time.sleep(0.15)
    assert len(files(srv, "auto")) == 1
    urllib.request.urlopen(srv.base + "ping.php?id=inst-1&v=2.3.7").read(); urllib.request.urlopen(srv.base + "manifest.php?id=inst-1&v=2.3.7").read(); time.sleep(0.6)
    assert len(files(srv, "auto")) == 1                                                             # one per hour
    srv.sql("UPDATE dc_kv SET v=? WHERE k='backup_last'", str(int(time.time()) - 1800)); urllib.request.urlopen(srv.base + "ping.php?id=inst-1&v=2.3.7").read(); time.sleep(0.6)
    assert len(files(srv, "auto")) == 1                                                             # not yet an hour


def test_only_the_last_10_automatic_copies_are_kept_and_manual_ones_are_kept_apart(srv):
    lic(srv).register(PERSON); clear(srv)
    for i in range(13): php(srv, "echo dc_backup_make('auto');")
    assert len(files(srv, "auto")) == 10
    for i in range(12): php(srv, "echo dc_backup_make('manual');")
    assert len(files(srv, "manual")) == 10 and len(files(srv, "auto")) == 10                       # manual copies do not push out the automatic ones
    names = [p.name for p in files(srv, "auto")]; assert len(set(names)) == 10
    for p in files(srv): assert p.read_bytes()[:16] == b"SQLite format 3\0"


def test_a_broken_copy_is_never_kept_and_the_error_shows_in_the_panel(srv):
    lic(srv).register(PERSON); clear(srv); a = Admin(srv.base)
    d = srv.root / "data" / "backups"
    shutil.rmtree(d); d.write_text("a file where the folder should be")                            # backups cannot be written
    out = a.post("backups", "backup_now"); assert "class='flash bad'" in out
    assert installs(srv) == ["inst-1"]
    d.unlink()


def test_panel_page_and_menu_exist_and_the_dashboard_nav_still_works(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    page = a.page("backups"); assert "digiconnect" in page.lower() and 'name="bkfile"' in page and "backup_now" in page
    assert "?p=backups" in a.page("dashboard") and "?p=backups" in a.page("settings")
    for p in ("dashboard", "installs", "modes", "licenses", "activity", "settings"): assert "Fatal error" not in a.page(p) and "Warning:" not in a.page(p)


def test_the_dashboard_warns_when_there_is_no_recent_copy_and_not_otherwise(srv):
    lic(srv).register(PERSON); a = Admin(srv.base)
    srv.sql("INSERT OR REPLACE INTO dc_kv(k,v) VALUES('backup_last',?)", str(int(time.time()) - 30 * 3600))
    assert "?p=backups" in a.page("dashboard") and ("no recent backup" in a.page("dashboard") or "πρόσφατο αντίγραφο" in a.page("dashboard"))
    a.post("backups", "backup_now"); page = a.page("dashboard")
    assert "no recent backup" not in page and "πρόσφατο αντίγραφο" not in page
