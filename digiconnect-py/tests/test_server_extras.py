"""Server extras ported from the HAM Digi server (inbox, live chat, visit statistics, Demo page, reinstall inheritance),
run against the real PHP code: the public pages, the user-facing endpoints and the admin panel."""
import json, re, urllib.parse, urllib.request, urllib.error
import pytest
from test_license import srv, lic, PERSON, shutil  # noqa: F401
from test_server_payments import Admin

pytestmark = pytest.mark.skipif(not shutil.which("php"), reason="php not installed")


def get(srv, path, headers=None):
    return urllib.request.urlopen(urllib.request.Request(srv.base + path, headers=headers or {})).read().decode()


def post_json(srv, path, data):
    rq = urllib.request.Request(srv.base + path, json.dumps(data).encode(), {"Content-Type": "application/json"})
    try: return json.loads(urllib.request.urlopen(rq).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())


def post_form(srv, path, **f):
    return json.loads(urllib.request.urlopen(srv.base + path, urllib.parse.urlencode(f).encode()).read())


def test_every_panel_page_renders_without_php_errors(srv):
    a = Admin(srv.base)
    for p in ("dashboard", "stats", "installs", "demos", "licenses", "messages", "inbox", "chat", "activity", "settings", "payments"):
        html = a.page(p)
        assert "<aside>" in html and not re.search(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught)", html), p
    for p in ("demos", "inbox", "chat"):
        assert f"?p={p}" in a.page("dashboard")                                                    # in the menu


def chat_api(a, action, **f):
    """The panel's chat API as its page script calls it (GET for lists, POST with the page's CSRF token for sending)."""
    if not f: return json.loads(a.op.open(a.base + "?chatapi=" + action).read())
    c = re.search(r'CSRF="([0-9a-f]+)"', a.page("chat")).group(1)
    return json.loads(a.op.open(a.base + "?chatapi=" + action, urllib.parse.urlencode(dict(csrf=c, **f)).encode()).read())


def test_a_message_from_the_program_is_a_conversation_the_owner_answers_and_the_user_gets(srv):
    l = lic(srv, "inst-1"); l.register(PERSON)
    assert 'id="ctf"' in get(srv, "index.php") and "talk.php" in get(srv, "index.php")            # the public page has the form and the chat link
    r = post_json(srv, "inbox.php", dict(src="app", id="inst-1", call="sa7svr", topic="bug", subject="Hi", body="it crashes", version="2.2.0"))
    assert r["ok"] == 1 and post_json(srv, "inbox.php", dict(body=""))["ok"] == 0
    assert srv.sql("SELECT COUNT(*) n FROM dc_inbox")[0]["n"] == 0                                 # not in the inbox any more: it is a conversation
    a = Admin(srv.base); th = chat_api(a, "threads")["threads"]
    t = [x for x in th if x["inst"] == "inst-1"][0]
    assert t["unread"] == 1 and "it crashes" in t["last"] and t["call"]                            # the thread belongs to the installation
    assert chat_api(a, "send", token=t["token"], body="please update")["ok"] == 1
    poll = json.loads(get(srv, "inbox.php?chat=poll&id=inst-1&after=0"))                           # the program asks for its conversation
    assert [m["body"] for m in poll["msgs"]] == ["Hi\n\nit crashes", "please update"] and [m["who"] for m in poll["msgs"]] == ["user", "owner"]
    assert "please update" in get(srv, "inbox.php?poll=1&id=inst-1")                               # older programs still get the owner's words as replies
    assert json.loads(get(srv, "inbox.php?chat=poll&id=inst-1&after=%d" % poll["msgs"][-1]["id"]))["msgs"] == []
    assert chat_api(a, "msgs&t=" + t["token"] + "&after=0")["msgs"][1]["rd"] == 0                  # fetched in the background: not "read" yet
    get(srv, "inbox.php?chat=poll&id=inst-1&after=0&read=1")                                          # the user opens the conversation
    assert chat_api(a, "msgs&t=" + t["token"] + "&after=0")["msgs"][1]["rd"] == 1                  # now the owner sees that it was read
    chat_api(a, "send", token=t["token"], body="second")                                              # fetched in the background first (not read) ...
    last = json.loads(get(srv, "inbox.php?chat=poll&id=inst-1&after=%d" % poll["msgs"][-1]["id"]))["msgs"][-1]["id"]
    assert chat_api(a, "msgs&t=" + t["token"] + "&after=0")["msgs"][-1]["rd"] == 0
    get(srv, "inbox.php?chat=poll&id=inst-1&after=%d&read=1" % last)                                  # ... then the conversation is opened with nothing new to fetch
    assert chat_api(a, "msgs&t=" + t["token"] + "&after=0")["msgs"][-1]["rd"] == 1


def test_the_owner_can_start_a_conversation_with_any_user_from_the_users_list(srv):
    l = lic(srv, "inst-7"); l.register(PERSON)
    a = Admin(srv.base)
    users = chat_api(a, "threads&users=1")["threads"]
    u = [x for x in users if x["inst"] == "inst-7"][0]                                              # listed although the user never wrote
    assert u["token"] and chat_api(a, "threads&users=1&q=zzzz-none")["threads"] == []
    info = chat_api(a, "msgs&t=" + u["token"] + "&after=0&i=inst-7")
    assert info["ok"] == 1 and info["msgs"] == [] and info["inst"] == "inst-7"
    assert chat_api(a, "send", token=u["token"], inst="inst-7", body="Hello, new version is out")["ok"] == 1
    poll = json.loads(get(srv, "inbox.php?chat=poll&id=inst-7&after=0"))
    assert [(m["who"], m["body"]) for m in poll["msgs"]] == [("owner", "Hello, new version is out")]
    post_form(srv, "inbox.php", chat="send", id="inst-7", body="thank you")                          # the user answers in the same conversation
    th = [x for x in chat_api(a, "threads")["threads"] if x["inst"] == "inst-7"]
    assert len(th) == 1 and th[0]["unread"] == 1 and th[0]["on"] == 1 and "thank you" in th[0]["last"]
    assert json.loads(get(srv, "inbox.php?chat=poll&id=nobody&after=0"))["msgs"] == []              # an unknown id never creates a conversation
    assert srv.sql("SELECT COUNT(*) n FROM dc_chat WHERE token=?", chat_api(a, "threads")["threads"][0]["token"])[0]["n"] == 2


def test_diagnostics_stay_reports_and_a_web_form_message_without_an_installation_stays_in_the_inbox(srv):
    l = lic(srv, "inst-2"); l.register(PERSON)
    d = post_json(srv, "inbox.php", dict(src="app", id="inst-2", topic="diagnostics", subject="Diagnostics 2.3", body="LOG LINE " * 50))
    w = post_json(srv, "inbox.php", dict(src="web", lang="en", topic="reinstall", email="x@example.org", body="lost the installer"))
    assert d["ok"] == 1 and w["ok"] == 1
    a = Admin(srv.base); html = a.page("inbox")
    assert "LOG LINE" in html and "lost the installer" in html and "x@example.org" in html
    assert srv.sql("SELECT COUNT(*) n FROM dc_chat")[0]["n"] == 0                                    # reports are not talk
    a.post("inbox", "inbox_close", iid_msg=str(w["id"]))
    assert "lost the installer" not in a.page("inbox")


def test_the_old_inbox_moves_into_the_conversations_once_and_nothing_is_lost(srv):
    l = lic(srv, "inst-3"); l.register(PERSON)
    srv.sql("INSERT INTO dc_inbox(t,install,call,topic,subject,body,ip,src,status,reply,reply_t) VALUES(1000,'inst-3','SA7SVR','bug','Old','old problem','1.1.1.1','app','replied','old answer',2000)")
    srv.sql("INSERT INTO dc_inbox(t,install,call,topic,subject,body,ip,src,status) VALUES(1500,'','','diagnostics','Diag','report','1.1.1.1','app','new')")
    srv.sql("DELETE FROM dc_kv WHERE k='chat_unified_v1'")
    a = Admin(srv.base); a.page("chat")                                                              # the next page load runs the move
    poll = json.loads(get(srv, "inbox.php?chat=poll&id=inst-3&after=0"))
    assert [(m["who"], m["body"]) for m in poll["msgs"]] == [("user", "Old\n\nold problem"), ("owner", "old answer")]
    assert srv.sql("SELECT COUNT(*) n FROM dc_inbox WHERE status<>'closed'")[0]["n"] == 1             # only the diagnostics report is still open
    a.page("chat"); a.page("dashboard")
    assert len(json.loads(get(srv, "inbox.php?chat=poll&id=inst-3&after=0"))["msgs"]) == 2             # a second run adds nothing


def test_inbox_flood_guard(srv):
    for i in range(6): assert post_json(srv, "inbox.php", dict(body=f"m{i}"))["ok"] == 1
    assert post_json(srv, "inbox.php", dict(body="one too many"))["ok"] == 0


def test_site_chat_is_private_and_the_owner_replies_from_the_panel(srv):
    r = post_form(srv, "talk.php?api=send", body="hello owner", call="sv1abc", name="Nick")
    assert r["ok"] == 1 and len(r["token"]) == 32
    tok = r["token"]
    assert "hello owner" in get(srv, f"talk.php?t={tok}") and "hello owner" not in get(srv, "talk.php?t=" + "0" * 32)   # a visitor sees only their own thread
    a = Admin(srv.base); html = a.page("chat")
    assert "window" in html and "Συνομιλίες" in html
    th = json.loads(a.op.open(a.base + "?chatapi=threads").read())
    assert th["ok"] == 1 and any(t["token"] == tok and t["unread"] == 1 for t in th["threads"])
    c = re.search(r'CSRF="([0-9a-f]+)"', html).group(1)                                      # the page hands its token to the chat script
    rep = json.loads(a.op.open(a.base + "?chatapi=send", urllib.parse.urlencode(dict(csrf=c, token=tok, body="hi Nick")).encode()).read())
    assert rep["ok"] == 1
    poll = json.loads(get(srv, f"talk.php?api=poll&t={tok}&after=0"))
    assert [m["body"] for m in poll["msgs"]] == ["hello owner", "hi Nick"]
    assert json.loads(a.op.open(a.base + "?chatapi=threads").read())["threads"][0]["unread"] == 0
    kinds = [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")]
    assert "chat_new" in kinds and "chat_reply" in kinds


def test_chat_api_and_pictures_need_the_admin_login(srv):
    r = post_form(srv, "talk.php?api=send", body="secret")
    with pytest.raises(Exception): json.loads(get(srv, "admin/index.php?chatapi=threads"))       # not signed in -> the login page, not JSON
    assert "secret" not in get(srv, "admin/index.php?chatapi=threads")


def test_visits_are_counted_robots_and_own_ip_are_not(srv):
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
    get(srv, "index.php?lang=en", ua)
    get(srv, "talk.php?lang=el", {"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"})
    rows = srv.sql("SELECT page, lang, bot, br, os FROM dc_visits ORDER BY id")
    assert len(rows) == 2 and rows[0]["bot"] == 0 and rows[0]["br"] == "Chrome" and rows[0]["os"] == "Windows" and rows[1]["bot"] == 1
    a = Admin(srv.base); html = a.page("stats")
    assert "Επισκέψεις στο site" in html and not re.search(r"(Fatal error|Warning:|Notice:)", html)
    csv = a.op.open(a.base + "?p=stats&r=30&export=csv").read().decode()
    assert "time_utc" in csv and "Chrome" in csv
    get(srv, "index.php?lang=sv", ua); assert len(srv.sql("SELECT id FROM dc_visits")) == 2          # a reload within 30 s counts once
    srv.sql("UPDATE dc_visits SET t=t-100")
    a.post("stats", "stats_ignore")                                                              # do not count my own visits
    get(srv, "index.php?lang=sv", ua)
    assert len(srv.sql("SELECT id FROM dc_visits")) == 2
    a.post("stats", "stats_ignore", remove="1"); get(srv, "index.php?lang=sv", ua)
    assert len(srv.sql("SELECT id FROM dc_visits")) == 3


def test_demo_page_lists_demo_users_and_days_used(srv):
    l = lic(srv, "inst-1"); l.register(PERSON); l.check()
    assert srv.sql("SELECT COUNT(*) n FROM dc_daily WHERE id='inst-1'")[0]["n"] == 1                               # one row per day it was seen
    a = Admin(srv.base); html = a.page("demos")
    assert "DC-00001" in html and "SA7SVR" in html and not re.search(r"(Fatal error|Warning:|Notice:)", html)


def test_reinstall_takes_the_licence_and_raises_an_alert(srv):
    old = lic(srv, "old-1"); old.register(PERSON)
    a = Admin(srv.base)
    srv.sql("UPDATE dc_installs SET state='full', lic_by='payment T1', lic_since=1 WHERE id='old-1'")
    new = lic(srv, "new-9", hw=old.hw); new.register(PERSON)                                      # same computer, new installation id
    row = srv.sql("SELECT state FROM dc_installs WHERE id='new-9'")[0]
    assert row["state"] == "full"
    ev = srv.sql("SELECT kind FROM dc_events WHERE kind='reinstall_id'")
    assert ev and "reinstall_id" in [e["kind"] for e in srv.sql("SELECT kind FROM dc_events")] and "Επανεγκατάσταση" in a.page("dashboard")
    a.post("settings", "set_lic", offline="require", offline_days="7")                           # checkbox off -> setting 0
    assert srv.sql("SELECT v FROM dc_kv WHERE k='reinstall_id'")[0]["v"] == "0"
    third = lic(srv, "third-3", hw=old.hw); third.register(PERSON)                               # same computer again, but the setting is off
    assert srv.sql("SELECT state FROM dc_installs WHERE id='third-3'")[0]["state"] != "full"
