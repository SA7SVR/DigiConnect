<?php
/* DigiConnect — admin control panel (self-contained). Same layout/options as the HAM Digi panel.
   Manages installs, demo/activation, releases, licence codes, web registrations, broadcast messages. */
require __DIR__ . '/../lib.php';
if (session_status() !== PHP_SESSION_ACTIVE) session_start();
$cfg = dc_cfg();

/* ---- language ---- */
$LANG = $_GET['lang'] ?? ($_SESSION['dc_lang'] ?? 'el');
if (!in_array($LANG, ['el','en','sv'], true)) $LANG = 'el';
$_SESSION['dc_lang'] = $LANG;
function L($el, $en = '', $sv = '') { global $LANG; return $LANG === 'en' ? ($en ?: $el) : ($LANG === 'sv' ? ($sv ?: $en ?: $el) : $el); }
function h($s) { return dc_h($s); }

/* ---- extra table for broadcast messages (safe, additive) ---- */
dc_db();                                                       // creates / upgrades the tables (dc_messages included)

/* ---- auth (+ "remember me": 180 days on this browser, stored as a hash, cancelled by Log out) ---- */
const DC_REMEMBER_DAYS = 180;
function rm_list() { $l = json_decode((string)dc_kv('remember', '[]'), true); return is_array($l) ? array_values(array_filter($l, fn($r) => ($r['exp'] ?? 0) > time())) : []; }
function rm_cookie($v, $exp) { setcookie('dc_remember', $v, ['expires' => $exp, 'path' => '/', 'secure' => !empty($_SERVER['HTTPS']), 'httponly' => true, 'samesite' => 'Lax']); }
function rm_issue() {
  $id = bin2hex(random_bytes(8)); $tok = bin2hex(random_bytes(32)); $exp = time() + DC_REMEMBER_DAYS * 86400;
  $l = rm_list(); $l[] = ['id' => $id, 'h' => hash('sha256', $tok), 'exp' => $exp, 'ua' => substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 120)];
  dc_kv_set('remember', json_encode(array_slice($l, -20))); rm_cookie($id . ':' . $tok, $exp);
}
function rm_drop() {
  $id = explode(':', (string)($_COOKIE['dc_remember'] ?? ''))[0];
  if ($id !== '') dc_kv_set('remember', json_encode(array_values(array_filter(rm_list(), fn($r) => $r['id'] !== $id))));
  rm_cookie('', time() - 3600);
}
if (isset($_POST['login'])) {
  if (hash_equals((string)$cfg['admin_user'], (string)($_POST['u'] ?? '')) && hash_equals((string)$cfg['admin_pass'], (string)($_POST['p'] ?? ''))) {
    session_regenerate_id(true); $_SESSION['dc_admin'] = 1; dc_event('admin_login', dc_ip());
    if (!empty($_POST['remember'])) rm_issue();
    header('Location: ?p=dashboard'); exit;
  } else { $login_err = L('Λάθος στοιχεία', 'Wrong credentials', 'Fel uppgifter'); dc_event('admin_login_failed', dc_ip()); }
}
if (empty($_SESSION['dc_admin']) && !empty($_COOKIE['dc_remember']) && strpos((string)$_COOKIE['dc_remember'], ':') !== false) {
  list($rid, $rtok) = explode(':', (string)$_COOKIE['dc_remember'], 2);
  foreach (rm_list() as $r) if (hash_equals($r['id'], $rid) && hash_equals($r['h'], hash('sha256', $rtok))) { session_regenerate_id(true); $_SESSION['dc_admin'] = 1; break; }
}
if (isset($_GET['logout'])) { rm_drop(); unset($_SESSION['dc_admin']); header('Location: index.php'); exit; }
$auth = !empty($_SESSION['dc_admin']);

/* ---- helpers for actions ---- */
$flash = null;
function flash($k, $m) { global $flash; $flash = [$k, $m]; }
$CSRF = dc_csrf();
function csrf() { global $CSRF; return '<input type="hidden" name="csrf" value="' . $CSRF . '">'; }

/* ---- live-chat API for the Chats page (JSON; admin only) ---- */
if ($auth && (isset($_GET['chatapi']) || isset($_GET['chatimg']))) {
  if (isset($_GET['chatimg'])) dc_chat_serve_image((int)$_GET['chatimg'], null);
  $ca = (string)$_GET['chatapi']; $post = $_SERVER['REQUEST_METHOD'] === 'POST';
  if ($post && !hash_equals($CSRF, (string)($_POST['csrf'] ?? ''))) dc_chat_json(['ok' => 0, 'err' => L('Η σελίδα ήταν παλιά — φόρτωσέ την ξανά.', 'The page was out of date — reload it.')]);
  $tk = preg_replace('/[^a-f0-9]/', '', (string)($_POST['token'] ?? $_GET['t'] ?? '')); if (strlen($tk) !== 32) $tk = '';
  if ((int)dc_kv('chat_owner_seen', 0) < time() - 5) dc_kv_set('chat_owner_seen', time());   // "SA7SVR is online" for the visitors
  try {
    if ($ca === 'threads') {
      $arch = (int)($_GET['arch'] ?? 0) ? 1 : 0; $needle = mb_strtolower(trim((string)($_GET['q'] ?? '')));
      $rows = dc_q("SELECT c.token, MAX(c.t) lt, SUM(c.who='user' AND c.read_owner=0 AND c.del=0) unread, COUNT(*) n,
          (SELECT CASE WHEN c2.del=1 THEN '' WHEN c2.body='' AND c2.img<>'' THEN '\u{1F4F7}' ELSE c2.body END FROM dc_chat c2 WHERE c2.token=c.token ORDER BY c2.id DESC LIMIT 1) last,
          (SELECT c2.who FROM dc_chat c2 WHERE c2.token=c.token ORDER BY c2.id DESC LIMIT 1) lastwho,
          (SELECT \"call\" FROM dc_chat c3 WHERE c3.token=c.token AND \"call\"<>'' ORDER BY c3.id ASC LIMIT 1) callsign,
          (SELECT name FROM dc_chat c4 WHERE c4.token=c.token AND name<>'' ORDER BY c4.id ASC LIMIT 1) name,
          (SELECT email FROM dc_chat c5 WHERE c5.token=c.token AND email<>'' ORDER BY c5.id ASC LIMIT 1) email,
          COALESCE(h.arch,0) arch, COALESCE(h.pin,0) pin, COALESCE(h.seen_u,0) seen_u, COALESCE(h.typ_u,0) typ_u
        FROM dc_chat c LEFT JOIN dc_chat_th h ON h.token=c.token GROUP BY c.token ORDER BY COALESCE(h.pin,0) DESC, lt DESC LIMIT 400")->fetchAll();
      $out = []; $unreadAll = 0; $archN = 0; $now = time();
      foreach ($rows as $r) {
        if ((int)$r['arch']) { $archN++; if ((int)$r['unread'] > 0) { dc_q('UPDATE dc_chat_th SET arch=0 WHERE token=?', [$r['token']]); $r['arch'] = 0; $archN--; } }   // a new message brings a chat back from the archive
        $unreadAll += (int)$r['unread'];
        if ((int)$r['arch'] !== $arch) continue;
        $hay = mb_strtolower($r['name'] . ' ' . $r['callsign'] . ' ' . $r['email'] . ' ' . $r['last']);
        if ($needle !== '' && mb_strpos($hay, $needle) === false) continue;
        $out[] = ['token' => $r['token'], 'name' => (string)$r['name'], 'call' => (string)$r['callsign'], 'email' => (string)$r['email'], 'last' => mb_substr((string)$r['last'], 0, 90), 'lastwho' => $r['lastwho'], 'lt' => (int)$r['lt'], 'unread' => (int)$r['unread'], 'pin' => (int)$r['pin'], 'on' => $r['seen_u'] > $now - 15 ? 1 : 0, 'typ' => $r['typ_u'] > $now - 4 ? 1 : 0];
      }
      dc_chat_json(['ok' => 1, 'threads' => $out, 'unread' => $unreadAll, 'archived' => $archN, 'now' => $now]);
    }
    if ($ca === 'msgs') {
      if (!$tk) dc_chat_json(['ok' => 0]);
      $after = (int)($_GET['after'] ?? 0); $now = time();
      $msgs = []; foreach (dc_q('SELECT * FROM dc_chat WHERE token=? AND id>? ORDER BY id ASC LIMIT 300', [$tk, $after]) as $r) $msgs[] = dc_chat_row_out($r);
      $upd = []; foreach (dc_q("SELECT * FROM dc_chat WHERE token=? AND id<=? AND ((who='owner' AND read_user=1) OR del=1) ORDER BY id DESC LIMIT 60", [$tk, $after]) as $r) $upd[] = dc_chat_row_out($r);
      dc_q("UPDATE dc_chat SET read_owner=1 WHERE token=? AND who='user' AND read_owner=0", [$tk]);
      $th = dc_q('SELECT * FROM dc_chat_th WHERE token=?', [$tk])->fetch() ?: [];
      $who = dc_q("SELECT \"call\",email,name FROM dc_chat WHERE token=? AND who='user' AND (\"call\"<>'' OR name<>'' OR email<>'') ORDER BY id ASC LIMIT 1", [$tk])->fetch() ?: [];
      $first = (int)dc_scalar('SELECT MIN(t) FROM dc_chat WHERE token=?', [$tk]);
      $inst = $who ? dc_inst_for($who['call'] ?? '', $who['email'] ?? '') : false;
      dc_chat_json(['ok' => 1, 'msgs' => $msgs, 'upd' => $upd, 'on' => (int)($th['seen_u'] ?? 0) > $now - 15 ? 1 : 0, 'typ' => (int)($th['typ_u'] ?? 0) > $now - 4 ? 1 : 0, 'arch' => (int)($th['arch'] ?? 0), 'pin' => (int)($th['pin'] ?? 0), 'note' => (string)($th['note'] ?? ''),
        'name' => (string)($who['name'] ?? ''), 'call' => (string)($who['call'] ?? ''), 'email' => (string)($who['email'] ?? ''), 'first' => $first, 'inst' => $inst ? $inst['id'] : '', 'now' => $now]);
    }
    if (!$post) dc_chat_json(['ok' => 0]);
    if (!$tk) dc_chat_json(['ok' => 0]);
    if ($ca === 'send') {
      $body = trim((string)($_POST['body'] ?? '')); if (function_exists('mb_substr')) $body = mb_substr($body, 0, 4000);
      try { $img = dc_chat_save_image('image'); } catch (Exception $e) { dc_chat_json(['ok' => 0, 'err' => dc_chat_img_error($e->getMessage(), $LANG)]); }
      if ($body === '' && $img === '') dc_chat_json(['ok' => 0]);
      dc_q("INSERT INTO dc_chat(token,t,who,body,img,read_owner,read_user) VALUES(?,?,'owner',?,?,1,0)", [$tk, time(), $body, $img]);
      $id = (int)dc_db()->lastInsertId(); dc_q("UPDATE dc_chat SET read_owner=1 WHERE token=? AND who='user'", [$tk]); dc_q('UPDATE dc_chat_th SET typ_o=0 WHERE token=?', [$tk]);
      dc_event('chat_reply', $tk . '|' . mb_substr($body !== '' ? $body : '[photo]', 0, 60));
      dc_chat_json(['ok' => 1, 'msg' => dc_chat_row_out(dc_q('SELECT * FROM dc_chat WHERE id=?', [$id])->fetch())]);
    }
    if ($ca === 'typing') { dc_upsert('dc_chat_th', ['token' => $tk], ['typ_o' => time()]); dc_chat_json(['ok' => 1]); }
    if ($ca === 'flag') { // archive / pin
      $k = ($_POST['k'] ?? '') === 'pin' ? 'pin' : 'arch'; dc_upsert('dc_chat_th', ['token' => $tk], [$k => (int)($_POST['v'] ?? 0) ? 1 : 0]); dc_chat_json(['ok' => 1]);
    }
    if ($ca === 'note') { dc_upsert('dc_chat_th', ['token' => $tk], ['note' => mb_substr((string)($_POST['note'] ?? ''), 0, 2000)]); dc_chat_json(['ok' => 1]); }
    if ($ca === 'delmsg') { dc_q('UPDATE dc_chat SET del=1, body=\'\' WHERE id=? AND token=?', [(int)($_POST['id'] ?? 0), $tk]); dc_chat_purge_old(); dc_chat_json(['ok' => 1]); }
    if ($ca === 'delthread') {
      foreach (dc_q("SELECT img FROM dc_chat WHERE token=? AND img<>''", [$tk])->fetchAll() as $r) @unlink(dc_chat_dir() . '/' . basename($r['img']));
      dc_q('DELETE FROM dc_chat WHERE token=?', [$tk]); dc_q('DELETE FROM dc_chat_th WHERE token=?', [$tk]); dc_event('chat_delete', $tk); dc_chat_json(['ok' => 1]);
    }
  } catch (Throwable $e) { error_log((string)$e); dc_chat_json(['ok' => 0, 'err' => 'server']); }
  dc_chat_json(['ok' => 0]);
}

/* ---- POST actions (auth + csrf) ---- */
if ($auth && $_SERVER['REQUEST_METHOD'] === 'POST' && dc_csrf_ok()) {
  $a = $_POST['a'] ?? $_POST['act'] ?? '';
  $iid = $_POST['iid'] ?? '';
  // install state
  if ($a === 'demo')     { $d = max(1, (int)($_POST['days'] ?? 7)); dc_lic_set($iid, 'demo', dc_lic_add(time(), $d, 'd'), 'panel'); flash('ok', L("Demo $d ημέρες", "Demo $d days")); }
  if ($a === 'activate') { dc_lic_set($iid, 'full', 0, 'panel'); flash('ok', L('Ενεργοποιήθηκε (full)', 'Activated (full)')); }
  if ($a === 'lock')     { dc_lic_set($iid, 'locked', 0, 'panel'); flash('ok', L('Κλειδώθηκε', 'Locked')); }
  if ($a === 'enable')   { dc_q("UPDATE dc_installs SET enabled=1 WHERE id=?", [$iid]); dc_event('enable', $iid); flash('ok', L('Ενεργό', 'Enabled')); }
  if ($a === 'disable')  { dc_q("UPDATE dc_installs SET enabled=0, state='disabled' WHERE id=?", [$iid]); dc_event('disable', $iid); flash('ok', L('Απενεργοποιήθηκε', 'Disabled')); }
  if ($a === 'note')     { dc_q("UPDATE dc_installs SET note=? WHERE id=?", [$_POST['note'] ?? '', $iid]); flash('ok', L('Σημείωση αποθηκεύτηκε', 'Note saved')); }
  if ($a === 'ident')    { dc_q("UPDATE dc_installs SET call=?, name=?, mail=? WHERE id=?", [strtoupper(trim($_POST['call'] ?? '')), trim($_POST['name'] ?? ''), trim($_POST['mail'] ?? ''), $iid]); flash('ok', L('Στοιχεία ενημερώθηκαν', 'Details updated')); }
  if ($a === 'del_inst') { $who = dc_inst_no($iid) . '|' . (dc_one('SELECT call FROM dc_installs WHERE id=?', [$iid])['call'] ?? ''); dc_q("DELETE FROM dc_installs WHERE id=?", [$iid]); dc_event('del_inst', $who); flash('ok', L('Διαγράφηκε', 'Deleted')); }
  // releases
  if ($a === 'rel_activate') { dc_q("UPDATE dc_releases SET status='archived' WHERE status='active'"); dc_q("UPDATE dc_releases SET status='active', published=? WHERE version=?", [time(), $_POST['version']]); dc_event('rel_activate', $_POST['version']); flash('ok', L('Ενεργή έκδοση: ', 'Active release: ') . $_POST['version']); }
  if ($a === 'rel_rollout')  { $r = max(0, min(100, (int)$_POST['rollout'])); dc_q("UPDATE dc_releases SET rollout=? WHERE version=?", [$r, $_POST['version']]); flash('ok', "Rollout $r%"); }
  if ($a === 'rel_forceall') { dc_q("UPDATE dc_releases SET rollout=100, status='active', published=? WHERE version=?", [time(), $_POST['version']]); dc_q("UPDATE dc_releases SET status='archived' WHERE status='active' AND version<>?", [$_POST['version']]); dc_event('rel_forceall', $_POST['version']); flash('ok', L('Επιβλήθηκε σε όλους: ', 'Forced to everyone: ') . $_POST['version']); }
  if ($a === 'rel_del')      { dc_q("DELETE FROM dc_releases WHERE version=?", [$_POST['version']]); flash('ok', L('Έκδοση διαγράφηκε', 'Release deleted')); }
  if ($a === 'rel_upload' && !empty($_FILES['pkg']['tmp_name'])) {
    $ver = trim($_POST['ver'] ?? ''); $minshell = trim($_POST['minshell'] ?? '');
    // the new DigiConnect packages carry their own version and minimum shell: read them, so nothing can be typed wrong
    $raw = @file_get_contents($_FILES['pkg']['tmp_name']); $meta = $raw !== false ? @json_decode((string)@gzdecode($raw), true) : null;
    if (is_array($meta) && ($meta['app'] ?? '') === 'digiconnect-py' && !empty($meta['version'])) { $ver = (string)$meta['version']; $minshell = (string)($meta['minShell'] ?? '2.0.0'); }
    unset($raw, $meta);
    if ($ver === '') flash('bad', L('Λείπει ο αριθμός έκδοσης', 'Missing version'));
    else {
      @mkdir($cfg['pkg_dir'], 0775, true);
      $fn = 'DigiConnect-' . preg_replace('/[^0-9A-Za-z._-]/', '', $ver) . '.dcpkg';
      $dest = $cfg['pkg_dir'] . '/' . $fn;
      if (move_uploaded_file($_FILES['pkg']['tmp_name'], $dest)) {
        $sha = hash_file('sha256', $dest); $sz = filesize($dest);
        dc_q("INSERT INTO dc_releases(version,min_shell,pkg,sha256,size,files,notes_el,notes_en,notes_sv,notes_it,status,rollout,published)
              VALUES(?,?,?,?,?,?,?,?,?,?, 'draft',100,NULL)
              ON CONFLICT(version) DO UPDATE SET pkg=excluded.pkg, sha256=excluded.sha256, size=excluded.size, min_shell=excluded.min_shell,
              notes_el=excluded.notes_el, notes_en=excluded.notes_en, notes_sv=excluded.notes_sv, notes_it=excluded.notes_it",
          [$ver, $minshell !== '' ? $minshell : '1.0.0', $fn, $sha, $sz, 0, $_POST['n_el'] ?? '', $_POST['n_en'] ?? '', $_POST['n_sv'] ?? '', $_POST['n_it'] ?? '']);
        dc_event('rel_upload', $ver); flash('ok', L('Ανέβηκε η έκδοση ', 'Uploaded release ') . $ver);
      } else flash('bad', L('Αποτυχία ανεβάσματος', 'Upload failed'));
    }
  }
  // codes (created with code_new below)
  if ($a === 'code_del') { dc_q("DELETE FROM dc_codes WHERE code=?", [$_POST['code']]); flash('ok', L('Κωδικός διαγράφηκε', 'Code deleted')); }
  // messages (same as HAM Digi)
  if ($a === 'msg_new') {
    $target = ''; $t = trim($_POST['target'] ?? ''); $ok = true;
    if ($t !== '') { $r0 = dc_one('SELECT id FROM dc_installs WHERE rowid=?', [(int)preg_replace('/\D/', '', $t)]); $target = $r0 ? $r0['id'] : ''; if (!$target) { flash('bad', L('Δεν βρέθηκε η εγκατάσταση.', 'Installation not found.')); $ok = false; } }
    $el = trim($_POST['body_el'] ?? ''); $en = trim($_POST['body_en'] ?? '');
    if ($ok && $el === '' && $en === '') { flash('bad', L('Γράψε το μήνυμα.', 'Write the message.')); $ok = false; }
    if ($ok) {
      $days = max(0, (int)($_POST['days'] ?? 30)); $link = trim($_POST['link'] ?? ''); if ($link !== '' && !preg_match('#^https://[^\s"<>]+$#', $link)) $link = '';
      $te = substr(trim($_POST['title_el'] ?? ''), 0, 200); $tn = substr(trim($_POST['title_en'] ?? ''), 0, 200);
      dc_q("INSERT INTO dc_messages(t,scope,target,title,body,title_el,title_en,body_el,body_en,link,until,active) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)", [time(), $target ? 'one' : 'all', $target, $te ?: $tn, substr($el ?: $en, 0, 4000), $te, $tn, substr($el, 0, 4000), substr($en, 0, 4000), $link, $days ? time() + $days * 86400 : 0]);
      dc_event('msg_send', ($target ? dc_inst_no($target) : 'all') . '|' . substr($el ?: $en, 0, 60));
      flash('ok', L('Το μήνυμα στάλθηκε. Ο server το προσφέρει σε κάθε έλεγχο· το πρόγραμμα δεν το εμφανίζει ακόμη.', 'Message sent. The server offers it at every check; the program does not show it yet.'));
    }
  }
  if ($a === 'msg_send') { dc_q("INSERT INTO dc_messages(t,scope,target,title,body,active) VALUES(?,?,?,?,?,1)", [time(), ($_POST['scope'] ?? 'all'), trim($_POST['target'] ?? ''), trim($_POST['title'] ?? ''), trim($_POST['body'] ?? '')]); dc_event('msg_send', $_POST['title'] ?? ''); flash('ok', L('Το μήνυμα στάλθηκε', 'Message sent')); }
  if ($a === 'msg_off') { dc_q("UPDATE dc_messages SET active=0 WHERE id=?", [(int)$_POST['mid']]); flash('ok', L('Το μήνυμα σταμάτησε.', 'Message stopped.')); }
  if ($a === 'msg_del') { dc_q("DELETE FROM dc_messages WHERE id=?", [(int)$_POST['mid']]); flash('ok', L('Το μήνυμα διαγράφηκε.', 'Message deleted.')); }
  // host lists — run the refresh now (fetches full lists for all modes)
  if ($a === 'hosts_refresh') {
    $rep = is_file(__DIR__ . '/../hosts/refresh.php') ? (require __DIR__ . '/../hosts/refresh.php') : [];
    $ok = is_array($rep) ? count(array_filter($rep, fn($r)=>!empty($r['ok']))) : 0;
    $tot = is_array($rep) ? count($rep) : 0;
    $bad = is_array($rep) ? array_filter($rep, fn($r)=>empty($r['ok'])) : [];
    $why = $bad ? ' — ' . key($bad) . ': ' . mb_substr((string)(reset($bad)['err'] ?? ''), 0, 160) : '';
    flash($ok > 0 && !$bad ? 'ok' : 'bad', L("Ανανεώθηκαν οι λίστες: $ok/$tot OK$why", "Host lists refreshed: $ok/$tot OK$why"));
  }
  // settings
  if ($a === 'set_check') { $m = max(1, (int)$_POST['mins']); dc_kv_set('check_every', $m * 60); flash('ok', L("Έλεγχος κάθε $m λεπτά", "Check every $m min")); }
  if ($a === 'set_gate')  { dc_kv_set('gate', ($_POST['gate'] ?? '') === '1' ? '1' : '0'); flash('ok', L('Έλεγχος άδειας ενημερώθηκε', 'Licence gate updated')); }
  if ($a === 'set_lic') {
    $off = in_array($_POST['offline'] ?? '', ['require', 'grace', 'allow'], true) ? $_POST['offline'] : 'require';
    dc_kv_set('offline', $off); dc_kv_set('offline_days', max(1, (int)($_POST['offline_days'] ?? 7)));
    dc_kv_set('reinstall_id', !empty($_POST['reinstall_id']) ? '1' : '0');
    dc_kv_set('reg_approval', !empty($_POST['reg_approval']) ? '1' : '0');
    dc_kv_set('lic_scope', !empty($_POST['lic_scope']) ? 'major' : 'all'); dc_kv_set('lic_grandfather', max(1, (int)($_POST['lic_grandfather'] ?? 2)));
    // the demo length and the Donate address are set on the Licences page (default settings, as in HAM Digi)
    flash('ok', L('Ρυθμίσεις άδειας αποθηκεύτηκαν', 'Licence settings saved'));
  }
  if ($a === 'set_pause') { dc_kv_set('paused', ($_POST['paused'] ?? '') === '1' ? '1' : '0'); flash('ok', L('Κατάσταση ενημερώσεων ενημερώθηκε', 'Update pause updated')); }

  $ceNow = (int)round(((int)dc_kv('check_every', $cfg['check_every'])) / 60);
  // ---------- licences, activation codes, payments (same actions as the HAM Digi panel) ----------
  $UN = ['h', 'd', 'm', 'y'];
  if ($a === 'lic_default') {
    $mode = in_array($_POST['mode'] ?? '', ['free', 'demo', 'locked'], true) ? $_POST['mode'] : 'demo';
    dc_kv_set('lic_default', json_encode(['mode' => $mode, 'n' => max(1, (int)($_POST['n'] ?? 14)), 'unit' => in_array($_POST['unit'] ?? '', $UN, true) ? $_POST['unit'] : 'd',
      'msg_el' => substr(trim($_POST['msg_el'] ?? ''), 0, 300), 'msg_en' => substr(trim($_POST['msg_en'] ?? ''), 0, 300),
      'offer' => in_array($_POST['offer'] ?? '', ['none', 'donate', 'buy'], true) ? $_POST['offer'] : 'donate', 'amount' => substr(trim($_POST['amount'] ?? ''), 0, 30),
      'link' => preg_match('#^https://[^\s"<>]+$#', trim($_POST['link'] ?? '')) ? trim($_POST['link']) : ''], JSON_UNESCAPED_UNICODE));
    dc_event('licence', 'default|' . $mode); flash('ok', L('Η προεπιλογή για τις νέες εγκαταστάσεις αποθηκεύτηκε.', 'The default for new installations was saved.'));
  }
  if ($a === 'lic_reset_all') {
    $n = dc_q("UPDATE dc_installs SET state='', demo_until=0, lic_by='' WHERE (lic_by='default' OR lic_by IS NULL OR lic_by='') AND enabled=1 AND state<>'disabled'")->rowCount();
    dc_event('licence', "reset|$n to default"); flash('ok', L("$n εγκαταστάσεις ακολουθούν πάλι την προεπιλογή.", "$n installations follow the default again."));
  }
  if ($a === 'lic_one') {
    $id = $_POST['id'] ?? ''; $do = $_POST['do'] ?? ''; $n = max(1, (int)($_POST['n'] ?? 1)); $u = in_array($_POST['unit'] ?? '', $UN, true) ? $_POST['unit'] : 'd';
    $cur = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
    if (!$cur) flash('bad', L('Δεν βρέθηκε η εγκατάσταση.', 'Installation not found.'));
    else {
      $base = max(time(), (int)$cur['demo_until']);
      if ($do === 'demo') dc_lic_set($id, 'demo', dc_lic_add(time(), $n, $u), 'panel');
      elseif ($do === 'extend') dc_lic_set($id, $cur['state'] === 'full' ? 'full' : 'demo', dc_lic_add($base, $n, $u), 'panel');
      elseif ($do === 'full') dc_lic_set($id, 'full', 0, 'panel');
      elseif ($do === 'full_until') dc_lic_set($id, 'full', dc_lic_add(time(), $n, $u), 'panel');
      elseif ($do === 'lock') dc_lic_set($id, 'locked', 0, 'panel');
      elseif ($do === 'free') dc_lic_set($id, 'free', 0, 'panel');
      elseif ($do === 'default') { dc_q("UPDATE dc_installs SET state='', demo_until=0, lic_by='', enabled=1 WHERE id=?", [$id]); dc_event('licence', "$id|default"); }
      flash('ok', L('Η άδεια άλλαξε. Το πρόγραμμα την παίρνει στον επόμενο έλεγχο (το πολύ ' . $ceNow . ' λεπτά) ή στην επόμενη εκκίνηση.', 'Licence changed. The program picks it up at its next check (at most ' . $ceNow . ' minutes) or at its next start.'));
    }
  }
  if ($a === 'reg_approve' || $a === 'reg_reject') {
    $id = $_POST['id'] ?? ''; $cur = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
    if ($cur && $cur['state'] === 'pending') {
      if ($a === 'reg_approve') { dc_q("UPDATE dc_installs SET state='', demo_until=0, lic_by='', lic_set=? WHERE id=?", [time(), $id]); dc_event('reg_approve', $id . '|' . dc_inst_no($id) . '|' . $cur['call']); flash('ok', L('Εγκρίθηκε. Το πρόγραμμα ενεργοποιείται στον επόμενο έλεγχο (ή με «Δοκίμασε ξανά»).', 'Approved. The program activates at its next check (or with "Try again").')); }
      else { dc_lic_set($id, 'locked', 0, 'panel (registration rejected)'); flash('ok', L('Απορρίφθηκε (κλειδωμένο).', 'Rejected (locked).')); }
    }
  }
  if ($a === 'hw_free') {
    $id = $_POST['id'] ?? '';
    if (dc_one('SELECT id FROM dc_installs WHERE id=?', [$id])) {
      dc_q("UPDATE dc_installs SET hw='', hw_set=0 WHERE id=?", [$id]); dc_event('hw_free', $id . '|' . dc_inst_no($id));
      flash('ok', L('Ο υπολογιστής ελευθερώθηκε: η άδεια δένεται με τον επόμενο υπολογιστή που θα συνδεθεί.', 'Computer freed: the licence binds to the next computer that connects.'));
    }
  }

  // ---------- modes and policies (page Modes) ----------
  $MN = ['on' => L('Ενεργό', 'On'), 'off' => L('Κλειστό', 'Off'), 'beta' => L('Μόνο δοκιμαστές', 'Testers only')];
  if ($a === 'mode_set') {
    $m = $_POST['mode'] ?? ''; $v = $_POST['state'] ?? '';
    if (in_array($m, DC_MODES, true) && in_array($v, ['on', 'off', 'beta'], true)) { dc_kv_set(dc_mode_key($m), $v); dc_event('modes', "all|$m → " . $v); flash('ok', "$m: " . $MN[$v] . L(' — για όλους.', ' — for everyone.')); }
  }
  if ($a === 'modes_all') {
    $v = $_POST['state'] ?? ''; if (in_array($v, ['on', 'off'], true)) { foreach (DC_MODES as $m) dc_kv_set(dc_mode_key($m), $v); dc_event('modes', 'all|' . L('όλα τα modes', 'all modes') . ' → ' . $v); flash('ok', L('Όλα τα modes: ', 'All modes: ') . $MN[$v]); }
  }
  if ($a === 'modes_note') {
    foreach (['modes_note_el', 'modes_note_en', 'tx_note_el', 'tx_note_en', 'min_msg_el', 'min_msg_en'] as $k) dc_kv_set($k, substr(trim($_POST[$k] ?? ''), 0, 300));
    $mv = trim($_POST['min_version'] ?? ''); dc_kv_set('min_version', preg_match('/^\d+(\.\d+){0,3}$/', $mv) ? $mv : '');
    dc_kv_set('tx_all', ($_POST['tx_all'] ?? '1') === '0' ? '0' : '1');
    dc_event('modes', 'all|' . L('μηνύματα / ελάχιστη έκδοση / εκπομπή', 'messages / minimum version / transmit')); flash('ok', L('Αποθηκεύτηκε.', 'Saved.'));
  }
  if ($a === 'mode_inst') {
    $ids = array_values(array_filter((array)($_POST['ids'] ?? []), 'is_string')); $ms = array_values(array_intersect(DC_MODES, (array)($_POST['modes'] ?? []))); $act = $_POST['act'] ?? '';
    $tx = $_POST['txset'] ?? ''; $te = $_POST['testerset'] ?? '';
    if (!$ids) flash('bad', L('Διάλεξε τουλάχιστον μία εγκατάσταση.', 'Select at least one installation.'));
    elseif (!$ms && $act !== '' && $act !== '-') flash('bad', L('Διάλεξε τουλάχιστον ένα mode.', 'Select at least one mode.'));
    else {
      $n = 0;
      foreach ($ids as $id) {
        $r = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]); if (!$r) continue; $n++;
        $o = dc_mode_ovr($r);
        if (in_array($act, ['on', 'off'], true)) foreach ($ms as $m) $o[$m] = $act;
        elseif ($act === 'reset') foreach ($ms as $m) unset($o[$m]);
        dc_q('UPDATE dc_installs SET mode_ovr=? WHERE id=?', [$o ? json_encode($o) : '', $id]);
        if ($tx === '1' || $tx === '0' || $tx === 'def') dc_q('UPDATE dc_installs SET tx_ovr=? WHERE id=?', [$tx === 'def' ? '' : $tx, $id]);
        if ($te === '1' || $te === '0') dc_q('UPDATE dc_installs SET tester=? WHERE id=?', [(int)$te, $id]);
      }
      $what = ($act === 'on' ? L('άνοιγμα ', 'open ') : ($act === 'off' ? L('κλείσιμο ', 'close ') : ($act === 'reset' ? L('γενική ρύθμιση ', 'general setting ') : ''))) . implode(', ', $ms)
        . ($tx !== '' && $tx !== '-' ? ' TX=' . $tx : '') . ($te !== '' && $te !== '-' ? ' tester=' . $te : '');
      dc_event('modes', "$n|" . trim($what)); flash('ok', L("Εφαρμόστηκε σε $n εγκαταστάσεις: ", "Applied to $n installations: ") . trim($what));
    }
  }
  if ($a === 'code_new') {
    $kind = ($_POST['kind'] ?? '') === 'full' ? 'full' : 'demo'; $perm = !empty($_POST['perm']) && $kind === 'full';
    $n = $perm ? 0 : max(1, (int)($_POST['n'] ?? 6)); $u = in_array($_POST['unit'] ?? '', $UN, true) ? $_POST['unit'] : 'd';
    $uses = max(0, (int)($_POST['uses'] ?? 1)); $vd = max(0, (int)($_POST['valid_days'] ?? 0)); $cnt = max(1, min(200, (int)($_POST['count'] ?? 1))); $made = [];
    for ($i = 0; $i < $cnt; $i++) {
      $code = dc_new_code();
      dc_q('INSERT INTO dc_codes(code,kind,dur,unit,uses,used,created,valid_until,note) VALUES(?,?,?,?,?,0,?,?,?)', [$code, $kind, $n, $u, $uses, time(), $vd ? time() + $vd * 86400 : 0, substr(trim($_POST['note'] ?? ''), 0, 120)]);
      $made[] = $code;
    }
    dc_event('codes_make', ($kind) . ' x' . $cnt . ' ' . implode(',', $made)); flash('ok', L('Νέοι κωδικοί: ', 'New codes: ') . implode('  ', $made));
  }
  if ($a === 'code_more') { dc_q('UPDATE dc_codes SET uses=uses+1 WHERE code=? AND uses>0', [$_POST['code'] ?? '']); flash('ok', L('Ο κωδικός δέχεται έναν υπολογιστή ακόμη.', 'The code accepts one more computer.')); }
  if ($a === 'alerts_seen') { dc_kv_set('alerts_seen', time()); }
  if ($a === 'pay_settings') {
    dc_kv_set('pay_auto', !empty($_POST['auto']) ? '1' : '0'); dc_kv_set('pay_min', (string)max(0, (float)str_replace(',', '.', $_POST['min'] ?? '0')));
    dc_kv_set('pay_receiver', strtolower(trim($_POST['receiver'] ?? ''))); dc_kv_set('pay_sandbox', !empty($_POST['sandbox']) ? '1' : '0'); dc_kv_set('pay_skip_hd', !empty($_POST['skip_hd']) ? '1' : '0');
    flash('ok', L('Οι ρυθμίσεις πληρωμών αποθηκεύτηκαν.', 'Payment settings saved.'));
  }
  if ($a === 'mail_settings') {
    dc_kv_set('mail_on', !empty($_POST['mail_on']) ? '1' : '0'); dc_kv_set('alert_mail', !empty($_POST['alert_mail']) ? '1' : '0');
    $am = trim((string)($_POST['admin_mail'] ?? '')); dc_kv_set('admin_mail', filter_var($am, FILTER_VALIDATE_EMAIL) ? $am : '');
    $mf = trim((string)($_POST['mail_from'] ?? '')); dc_kv_set('mail_from', filter_var($mf, FILTER_VALIDATE_EMAIL) ? $mf : '');
    flash('ok', L('Οι ρυθμίσεις email αποθηκεύτηκαν.', 'E-mail settings saved.'));
  }
  if ($a === 'mail_test') {
    $ok = dc_mail(trim((string)dc_kv('admin_mail', '')), 'DigiConnect — test', "Δοκιμαστικό email από το DigiConnect panel.\nTest e-mail from the DigiConnect panel.\n" . gmdate('c'));
    flash($ok ? 'ok' : 'bad', $ok ? L('Το email στάλθηκε — δες τα εισερχόμενα (και τα ανεπιθύμητα).', 'The e-mail was sent — check your inbox (and spam).') : L('Το email δεν στάλθηκε: ενεργοποίησε την αποστολή, γράψε email διαχειριστή ή έλεγξε τη mail() του server.', 'Not sent: switch sending on, enter an admin e-mail or check the server mail().'));
  }
  if ($a === 'pay_assign') {
    $to = dc_one('SELECT id FROM dc_installs WHERE rowid=?', [(int)preg_replace('/\D/', '', $_POST['to'] ?? '')]);
    if (!$to) flash('bad', L('Δεν βρέθηκε η εγκατάσταση (γράψε π.χ. DC-00012).', 'Installation not found (enter e.g. DC-00012).'));
    else { $code = dc_pay_activate((int)$_POST['pid'], $to['id'], 'panel'); flash('ok', L('Ενεργοποιήθηκε η ', 'Activated ') . dc_inst_no($to['id']) . ' · ' . $code); }
  }
  if ($a === 'pay_add') {
    $amt = (float)str_replace(',', '.', $_POST['amount'] ?? '0'); $txn = 'MAN-' . strtoupper(bin2hex(random_bytes(4)));
    dc_q('INSERT INTO dc_payments(t,txn,status,amount,currency,payer_email,payer_name,memo,custom,raw) VALUES(?,?,?,?,?,?,?,?,?,?)', [time(), $txn, 'Completed', $amt, strtoupper(substr(trim($_POST['currency'] ?? 'EUR'), 0, 5)) ?: 'EUR', strtolower(trim($_POST['email'] ?? '')), substr(trim($_POST['name'] ?? ''), 0, 60), substr(trim($_POST['memo'] ?? ''), 0, 300), '', 'manual']);
    $pid = (int)dc_db()->lastInsertId(); dc_event('payment', "$txn|$amt " . strtoupper(trim($_POST['currency'] ?? 'EUR')) . '|' . trim($_POST['name'] ?? '') . '|' . trim($_POST['email'] ?? ''));
    $to = dc_one('SELECT id FROM dc_installs WHERE rowid=?', [(int)preg_replace('/\D/', '', $_POST['to'] ?? '')]);
    if ($to) { $code = dc_pay_activate($pid, $to['id'], 'panel'); flash('ok', L('Καταχωρήθηκε και ενεργοποιήθηκε η ', 'Recorded and activated ') . dc_inst_no($to['id']) . ' · ' . $code); } else flash('ok', L('Η πληρωμή καταχωρήθηκε.', 'Payment recorded.'));
  }
  if ($a === 'pay_note') { dc_q('UPDATE dc_payments SET note=? WHERE id=?', [substr(trim($_POST['note'] ?? ''), 0, 200), (int)$_POST['pid']]); }
  // a payment that is not yours (e.g. a HAM Digi donation without a number) can be set aside: it is left out of the totals; "restore" brings it back
  if ($a === 'pay_ignore')  { dc_q("UPDATE dc_payments SET status='Ignored' WHERE id=? AND status='Completed' AND (install IS NULL OR install='')", [(int)$_POST['pid']]); flash('ok', L('Η πληρωμή αγνοήθηκε (δεν μετράει στα σύνολα).', 'Payment ignored (not counted in the totals).')); }
  if ($a === 'pay_restore') { dc_q("UPDATE dc_payments SET status='Completed' WHERE id=? AND status='Ignored'", [(int)$_POST['pid']]); flash('ok', L('Η πληρωμή επανήλθε.', 'Payment restored.')); }

  // ---- messages from users (inbox) ----
  if ($a === 'inbox_reply') {
    $mid = (int)($_POST['iid_msg'] ?? 0); $m = dc_one('SELECT * FROM dc_inbox WHERE id=?', [$mid]); $rep = trim((string)($_POST['reply'] ?? ''));
    if (!$m) flash('bad', L('Το μήνυμα δεν βρέθηκε.', 'Message not found.'));
    elseif ($rep === '') flash('bad', L('Γράψε την απάντηση.', 'Write the reply.'));
    else {
      dc_q('UPDATE dc_inbox SET reply=?, reply_t=?, status=? WHERE id=?', [substr($rep, 0, 4000), time(), 'replied', $mid]);
      if ($m['install']) {   // delivered through the server message system and the inbox poll
        $ttl = L('Απάντηση', 'Reply') . ($m['subject'] ? ' · ' . $m['subject'] : '');
        dc_q("INSERT INTO dc_messages(t,scope,target,title,body,title_el,title_en,body_el,body_en,link,until,active) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
          [time(), 'one', $m['install'], substr($ttl, 0, 200), substr($rep, 0, 4000), substr($ttl, 0, 200), substr($ttl, 0, 200), substr($rep, 0, 4000), substr($rep, 0, 4000), '', 0]);
      }
      dc_event('inbox_reply', ($m['call'] ?: 'web') . '|' . $m['subject']);
      flash('ok', $m['install'] ? L('Η απάντηση αποθηκεύτηκε και μπήκε στα μηνύματα της εγκατάστασης (το DigiConnect δεν τα εμφανίζει ακόμη μέσα στο πρόγραμμα).', 'Reply saved and queued as a message for the installation (DigiConnect does not show them inside the program yet).') : L('Η απάντηση αποθηκεύτηκε. Στείλ’ την με email στον χρήστη.', 'Reply saved. Send it to the user by e-mail.'));
    }
  }
  if ($a === 'inbox_close') { dc_q("UPDATE dc_inbox SET status='closed' WHERE id=?", [(int)($_POST['iid_msg'] ?? 0)]); }
  if ($a === 'inbox_del')   { dc_q('DELETE FROM dc_inbox WHERE id=?', [(int)($_POST['iid_msg'] ?? 0)]); }
  // ---- site statistics: do not count my own visits ----
  if ($a === 'stats_ignore') {
    $ipx = dc_ip(); $l = array_values(array_filter(explode(',', (string)dc_kv('stats_ignore', ''))));
    if (!empty($_POST['remove'])) $l = array_values(array_diff($l, [$ipx])); else $l[] = $ipx;
    dc_kv_set('stats_ignore', implode(',', array_unique($l)));
    flash('ok', !empty($_POST['remove']) ? L('Οι επισκέψεις σου μετριούνται ξανά.', 'Your own visits are counted again.') : L('Οι δικές σου επισκέψεις από αυτή την IP δεν θα μετριούνται.', 'Your own visits from this IP are no longer counted.'));
  }

  if (!$flash) $flash = ['ok', 'OK'];
  $_SESSION['dc_flash'] = $flash;
  header('Location: ?p=' . ($_POST['p'] ?? 'dashboard')); exit;
}
if (!empty($_SESSION['dc_flash'])) { $flash = $_SESSION['dc_flash']; unset($_SESSION['dc_flash']); }

/* ---- page ---- */
$p = $_GET['p'] ?? 'dashboard';
$PAGES = ['dashboard' => L('Επισκόπηση','Overview','Översikt'), 'stats' => L('Στατιστικά','Statistics','Statistik'), 'releases' => L('Εκδόσεις','Releases','Versioner'),
  'installs' => L('Εγκαταστάσεις','Installations','Installationer'), 'demos' => L('Demo','Demo','Demo'), 'downloads' => L('Λήψεις / Εγγραφές','Downloads / Sign-ups','Nedladdningar'),
  'licenses' => L('Άδειες / Κωδικοί','Licences / Codes','Licenser'), 'modes' => L('Modes / Πολιτικές','Modes / Policies','Lägen / Regler'), 'payments' => L('Πληρωμές','Payments','Betalningar'), 'servers' => L('Servers / Λίστες','Servers / Host lists','Servrar'), 'messages' => L('Μηνύματα','Messages','Meddelanden'), 'inbox' => L('Μηνύματα χρηστών','From users','Från användare'), 'chat' => L('Συνομιλίες','Chats','Chattar'),
  'activity' => L('Δραστηριότητα','Activity','Aktivitet'), 'settings' => L('Ρυθμίσεις','Settings','Inställningar')];
if (!isset($PAGES[$p])) $p = 'dashboard';

if (!$auth) { login_page($login_err ?? ''); exit; }
if ($auth && $p === 'stats' && ($_GET['export'] ?? '') === 'csv') {
  $R0 = (int)($_GET['r'] ?? 30); $R = in_array($R0, [1, 7, 30, 90, 365], true) ? $R0 : 30;
  header('Content-Type: text/csv; charset=utf-8'); header('Content-Disposition: attachment; filename="digiconnect-visits-' . gmdate('Ymd') . '.csv"');
  $o = fopen('php://output', 'w'); fwrite($o, "\xEF\xBB\xBF"); fputcsv($o, ['time_utc', 'ip', 'page', 'lang', 'browser', 'system', 'device', 'referrer', 'robot'], ';');
  foreach (dc_q('SELECT * FROM dc_visits WHERE t>=? ORDER BY t DESC', [time() - $R * 86400]) as $r) fputcsv($o, [gmdate('Y-m-d H:i:s', $r['t']), $r['ip'], $r['page'], $r['lang'], $r['br'], $r['os'], $r['dev'], $r['ref'], $r['bot']], ';');
  exit;
}
if (isset($_GET['rail'])) { header('Content-Type: text/html; charset=utf-8'); header('Cache-Control: no-store'); echo rail_html(); exit; }

/* counts for the sidebar badges */
$ceMin = (int)round(((int)dc_kv('check_every', $cfg['check_every'])) / 60);
$gate  = dc_kv('gate', $cfg['gate'] ? '1' : '0');
$paused = dc_kv('paused', '0') === '1';
$off = dc_offline();
$act   = dc_one("SELECT * FROM dc_releases WHERE status='active' ORDER BY published DESC LIMIT 1");
$onNow = (int)dc_one('SELECT COUNT(*) c FROM dc_installs WHERE last_ping>=?', [time() - DC_ONLINE_S])['c'];

head($PAGES[$p]);

/* ---------- SIDEBAR ---------- */
$icons = [
 'stats' => 'M4 20V11M10 20V4M16 20v-7M22 20H2',
 'dashboard' => 'M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z',
 'releases' => 'M12 3v12M7 10l5 5 5-5M5 21h14',
 'installs' => 'M3 5h18v11H3zM8 20h8M12 16v4',
 'downloads' => 'M4 17v3h16v-3M12 3v13M7 11l5 5 5-5',
 'licenses' => 'M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5zM12 15v2',
 'modes' => 'M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6',
 'payments' => 'M3 6h18v12H3zM3 10h18M7 15h3',
 'servers' => 'M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01',
 'messages' => 'M4 5h16v11H8l-4 4z',
 'inbox' => 'M3 13l3-8h12l3 8v6H3zM3 13h5l1 3h6l1-3h5',
 'chat' => 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12zM8 11h8M8 14h5',
 'demos' => 'M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z',
 'activity' => 'M3 12h4l3 7 4-14 3 7h4',
 'settings' => 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z'];
$seenA = (int)dc_kv('alerts_seen', 0); $phA = implode(',', array_fill(0, count(DC_ALERTS), '?'));
$BADGE = ['dashboard' => [(int)dc_one("SELECT COUNT(*) c FROM dc_events WHERE kind IN ($phA) AND t>?", array_merge(DC_ALERTS, [$seenA]))['c'], 'o'],
  'payments' => [(int)dc_one("SELECT COUNT(*) c FROM dc_payments WHERE status='Completed' AND (install IS NULL OR install='')")['c'], 'o'],
  'inbox' => [(int)dc_scalar("SELECT COUNT(*) FROM dc_inbox WHERE status='new'"), 'o'],
  'chat' => [(int)dc_scalar("SELECT COUNT(*) FROM dc_chat WHERE who='user' AND read_owner=0 AND del=0"), 'o'],
  'demos' => [(int)dc_scalar("SELECT COUNT(*) FROM dc_installs WHERE state='demo' AND demo_until>?", [time()]), 'g'],
  'installs' => [$onNow, 'g'], 'downloads' => [(int)dc_one("SELECT COUNT(*) c FROM dc_webdl WHERE t>=?", [time() - 7*86400])['c'], 'o']];
echo '<aside><div class="logo"><b>DigiConnect</b><small>Control Panel · by SA7SVR · v' . DC_SERVER_VERSION . '</small></div><nav>';
foreach ($PAGES as $k => $t)
  echo "<a href='?p=$k' class='" . ($p === $k ? 'on' : '') . "'><svg viewBox='0 0 24 24'><path d='{$icons[$k]}'/></svg><span>" . h($t) . '</span>'
     . (!empty($BADGE[$k][0]) ? "<b class='nb {$BADGE[$k][1]}'>" . $BADGE[$k][0] . '</b>' : '') . '</a>';
echo '</nav><div class="side-f">'
  . ($paused ? '<span class="pill bad">' . L('Ενημερώσεις σε παύση','Updates paused') . '</span>'
     : ($act ? '<span class="pill ok">' . L('Ενεργή','Active') . ' v' . h($act['version']) . '</span>' : '<span class="pill">' . L('Καμία ενεργή έκδοση','No active release') . '</span>'))
  . '<div class="lang theme" id="thm"><a href="#" data-t="auto" title="' . L('Όπως το σύστημα','Like the system') . '">Auto</a><a href="#" data-t="light" title="' . L('Ανοιχτό','Light') . '">☀</a><a href="#" data-t="dark" title="' . L('Σκούρο','Dark') . '">☾</a></div>'
  . '<div class="lang"><a href="?p=' . $p . '&lang=el" class="' . ($LANG==='el'?'on':'') . '">EL</a><a href="?p=' . $p . '&lang=en" class="' . ($LANG==='en'?'on':'') . '">EN</a><a href="?p=' . $p . '&lang=sv" class="' . ($LANG==='sv'?'on':'') . '">SV</a></div>'
  . '<a href="../../hamdigi/update/admin/index.php" class="logout">← HAM Digi panel</a>'
  . '<a href="?logout=1" class="logout">' . L('Αποσύνδεση','Log out') . '</a></div></aside><main>';

if ($flash) echo "<div class='flash {$flash[0]}'>" . h($flash[1]) . '</div>';
$SUB = ['stats' => L('Νέες εγκαταστάσεις και λήψεις ανά ημέρα, συστήματα και εκδόσεις.','New installations and downloads per day, systems and versions.','Nya installationer och nedladdningar per dag, system och versioner.'),
  'dashboard' => L('Τι συμβαίνει τώρα: χρήστες σε σύνδεση, εκδόσεις και στατιστικά.','What is happening now: users online, versions and statistics.'),
  'releases' => L('Ανέβασε νέα έκδοση (.dcpkg) — όλες οι εγκαταστάσεις την παίρνουν αυτόματα.','Upload a new version — every installation gets it automatically.'),
  'installs' => L('Κάθε εγκατάσταση: demo, ενεργοποίηση, κλείδωμα, ενεργό/ανενεργό.','Every installation: demo, activate, lock, enable/disable.'),
  'downloads' => L('Ποιος κατέβασε το πρόγραμμα από τη σελίδα (callsign, OS, IP).','Who downloaded from the website (callsign, OS, IP).'),
  'licenses' => L('Demo, άδειες και κωδικοί ενεργοποίησης.','Demo, licences and activation codes.'),
  'modes' => L('Άνοιξε ή κλείσε modes σε όλους ή σε επιλεγμένους, μόνο ακρόαση, ελάχιστη έκδοση.','Open or close modes for everyone or selected installations, listen-only, minimum version.'),
  'payments' => L('Δωρεές PayPal, ποιος πληρώνει και πόσα (€ και SEK ξεχωριστά) και αυτόματη ενεργοποίηση.','PayPal donations, who pays and how much (EUR and SEK separately) and automatic activation.'),
  'messages' => L('Μήνυμα σε όλους ή σε μία εγκατάσταση — εμφανίζεται μέσα στο πρόγραμμα.','A message to everyone or one installation — it shows inside the program.'),
  'demos' => L('Ποιος δοκιμάζει το πρόγραμμα, πόσο χρόνο έχει ακόμη και αν το χρησιμοποίησε.','Who is trying the program, how much time is left and whether it was used.'),
  'inbox' => L('Μηνύματα που στέλνουν οι χρήστες· απάντησε από εδώ.','Messages from users; reply from here.'),
  'chat' => L('Ζωντανές συνομιλίες από τη σελίδα του DigiConnect.','Live chats from the DigiConnect website.'),
  'activity' => L('Όλα όσα έγιναν, με τη σειρά.','Everything that happened, in order.'),
  'settings' => L('Ενημερώσεις, έλεγχος άδειας και συντήρηση.','Updates, licence gate and maintenance.')];
echo '<header class="ph"><div><h1>' . h($PAGES[$p]) . '</h1><p class="muted">' . h($SUB[$p] ?? '') . '</p></div><div class="strip">'
  . '<span class="st ' . ($paused ? 'bad' : ($act ? 'ok' : '')) . '"><i></i>' . ($paused ? L('σε παύση','paused') : ($act ? 'v' . h($act['version']) . ' ' . L('ενεργή','active') : L('καμία έκδοση','no release'))) . '</span>'
  . '<span class="st ' . ($onNow ? 'ok' : '') . '"><i></i>' . $onNow . L(' σε σύνδεση',' online') . '</span>'
  . ($BADGE['payments'][0] ? '<a class="st o" href="?p=payments"><i></i>' . $BADGE['payments'][0] . L(' πληρωμές χωρίς ενεργοποίηση',' payments not activated') . '</a>' : '')
  . '<a class="st" href="../" target="_blank"><i></i>' . L('Δημόσια σελίδα ↗','Public page ↗') . '</a></div></header>';

/* ===================== DASHBOARD ===================== */
if ($p === 'dashboard') {
  $total = (int)dc_one('SELECT COUNT(*) c FROM dc_installs')['c'];
  $demo  = (int)dc_one("SELECT COUNT(*) c FROM dc_installs WHERE state='demo'")['c'];
  $full  = (int)dc_one("SELECT COUNT(*) c FROM dc_installs WHERE state='full'")['c'];
  $lock  = (int)dc_one("SELECT COUNT(*) c FROM dc_installs WHERE state IN('locked','disabled') OR enabled=0")['c'];
  $a7    = (int)dc_one('SELECT COUNT(*) c FROM dc_installs WHERE last_seen>=?', [time()-7*86400])['c'];
  $dl7   = (int)dc_one('SELECT COUNT(*) c FROM dc_webdl WHERE t>=?', [time()-7*86400])['c'];
  $kpi = function ($l,$v,$s='',$c='') { return "<div class='kpi $c'><span>$l</span><b>$v</b><small>$s</small></div>"; };
  // things that need your attention: new payments, refunds
  $seen = (int)dc_kv('alerts_seen', 0); $phD = implode(',', array_fill(0, count(DC_ALERTS), '?'));
  $al = dc_q("SELECT * FROM dc_events WHERE kind IN ($phD) AND t>? ORDER BY t DESC LIMIT 30", array_merge(DC_ALERTS, [$seen]))->fetchAll();
  $si = dc_sign_info();
  if (!$si['ok']) echo '<section class="card" style="border-color:var(--tx)"><h2>⚠ ' . L('Υπογραφή αδειών ανενεργή', 'Licence signing is off') . '</h2><p>' . ($si['why'] === 'php-sodium'
    ? L('Η PHP του server δεν έχει την επέκταση <b>sodium</b>. Ζήτα από τον πάροχο να την ενεργοποιήσει.', 'The server PHP has no <b>sodium</b> extension. Ask the host to enable it.')
    : L('Λείπει το αρχείο <b>license-key.php</b> δίπλα στο lib.php. Ανέβασέ το μία φορά (το έχεις στο ζιπ του server που σου έδωσα) και κράτα αντίγραφο. Μέχρι τότε οι άδειες δεν υπογράφονται.', 'The file <b>license-key.php</b> next to lib.php is missing. Upload it once (it is in the server zip I gave you) and keep a backup. Until then licences are not signed.')) . '</p></section>';
  if ($al) echo '<section class="card" style="border-color:var(--tx)"><h2>⚠ ' . L('Ειδοποιήσεις','Alerts') . ' <small>(' . count($al) . ')</small></h2>' . activity_rows($al) . '<form method="post" style="margin-top:10px">' . csrf() . '<input type="hidden" name="p" value="dashboard"><input type="hidden" name="a" value="alerts_seen"><button class="btn sm">' . L('Τα είδα','Mark as seen') . '</button></form></section>';
  echo '<div class="kpis">'
    . $kpi(L('Εγκαταστάσεις','Installations'), $total, L('συνολικά','total'))
    . $kpi(L('Σε σύνδεση','Online'), $onNow, L('στέλνουν σήμα τώρα','sending a signal now'), 'g')
    . $kpi(L('Demo','Demo'), $demo, '', 'o')
    . $kpi(L('Ενεργές','Licensed'), $full, 'full', 'g')
    . $kpi(L('Κλειδωμένες','Locked'), $lock, '', $lock?'r':'')
    . $kpi(L('Λήψεις 7 ημ.','Downloads 7d'), $dl7, L('από τη σελίδα','from website'))
    . '</div>';
  $pt = dc_pay_totals(); $pn = (int)dc_one("SELECT COUNT(*) c FROM dc_payments WHERE status='Completed' AND (install IS NULL OR install='')")['c'];
  echo '<div class="kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">'
    . $kpi(L('Πληρωμές αυτόν τον μήνα · EUR','Payments this month · EUR'), number_format($pt['EUR']['month'], 2) . ' €', '<a href="?p=payments">' . L('Πληρωμές →','Payments →') . '</a>', 'g')
    . $kpi(L('Πληρωμές αυτόν τον μήνα · SEK','Payments this month · SEK'), number_format($pt['SEK']['month'], 2) . ' kr', '<a href="?p=payments">' . L('Πληρωμές →','Payments →') . '</a>', 'g')
    . $kpi(L('Σύνολο · EUR / SEK','Total · EUR / SEK'), number_format($pt['EUR']['total'], 2) . ' € / ' . number_format($pt['SEK']['total'], 2) . ' kr', $pt['EUR']['n'] + $pt['SEK']['n'] . L(' πληρωμές',' payments'))
    . $kpi(L('Πληρωμές χωρίς εγκατάσταση','Payments without installation'), $pn, L('ενεργοποίησέ τες στις Πληρωμές','activate them in Payments'), $pn ? 'o' : '')
    . '</div>';
  // version shares
  $vers = dc_q("SELECT version, COUNT(*) c FROM dc_installs WHERE version IS NOT NULL AND version<>'' GROUP BY version ORDER BY c DESC LIMIT 8")->fetchAll();
  echo '<div class="grid2"><section class="card"><h2>' . L('Εκδόσεις σε χρήση','Versions in use') . '</h2><div class="shares">';
  $max = 0; foreach ($vers as $v) $max = max($max, (int)$v['c']);
  if ($vers) foreach ($vers as $v) { $pct = $max ? round($v['c']*100/$max) : 0; $hl = ($act && $v['version']===$act['version'])?' hl':'';
    echo "<div class='sh$hl'><span class='sl'>v" . h($v['version']) . "</span><span class='sb'><i style='width:{$pct}%'></i></span><span class='sv'>" . (int)$v['c'] . "</span></div>"; }
  else echo '<p class="muted">' . L('Καμία εγκατάσταση ακόμη.','No installations yet.') . '</p>';
  echo '</div></section>';
  // recent activity
  $ev = dc_q("SELECT * FROM dc_events ORDER BY t DESC LIMIT 12")->fetchAll();
  echo '<section class="card"><h2>' . L('Πρόσφατη δραστηριότητα','Recent activity') . '</h2>' . activity_rows($ev) . '<a class="more" href="?p=activity">' . L('όλα →','all →') . '</a></section></div>';
  // live stations list (who is connecting) — like the HAM Digi panel
  $stn = dc_q("SELECT rowid AS rno, * FROM dc_installs ORDER BY (COALESCE(last_ping,0)>=" . (time()-DC_ONLINE_S) . ") DESC, MAX(COALESCE(last_ping,0),COALESCE(last_seen,0)) DESC LIMIT 60")->fetchAll();
  $onC = 0; foreach ($stn as $r2) if (dc_online($r2)) $onC++;
  echo '<section class="card"><h2>' . L('Σταθμοί','Stations') . ' <small><span style="color:var(--rx)">● ' . $onC . ' ' . L('online','online') . '</span> · ' . (count($stn) - $onC) . ' offline · ' . L('ανανεώνεται κάθε 30″','auto-refresh 30s') . '</small></h2>' . station_cards($stn) . '</section>';
  echo '<script>setTimeout(function(){location.reload();},30000);</script>';
}

/* ===================== STATISTICS ===================== */
elseif ($p === 'stats') {
  $days = 30; $t0 = strtotime(gmdate('Y-m-d 00:00:00')) - ($days - 1) * 86400;
  $bucket = function ($sql) use ($t0, $days) { $m = array_fill(0, $days, 0); foreach (dc_q($sql, [$t0])->fetchAll() as $r) { $i = (int)floor(((int)$r['t'] - $t0) / 86400); if ($i >= 0 && $i < $days) $m[$i]++; } return $m; };
  $newI = $bucket('SELECT first_seen t FROM dc_installs WHERE first_seen>=?');
  $dl   = $bucket('SELECT t FROM dc_webdl WHERE t>=?');
  $act  = $bucket('SELECT COALESCE(last_ping,last_seen) t FROM dc_installs WHERE COALESCE(last_ping,last_seen)>=CAST(? AS INTEGER)');
  $bars = function ($vals, $cls = '') use ($t0, $days) {
    $mx = max(1, max($vals)); $o = '<div class="bars ' . $cls . '">';
    foreach ($vals as $i => $v) $o .= '<span title="' . gmdate('d/m', $t0 + $i * 86400) . ': ' . $v . '"><i style="height:' . ($v ? max(4, round($v * 100 / $mx)) : 0) . '%"></i></span>';
    return $o . '</div><div class="bax"><span>' . gmdate('d/m', $t0) . '</span><span>' . gmdate('d/m', $t0 + ($days - 1) * 86400) . '</span></div>';
  };
  $tot = (int)dc_one('SELECT COUNT(*) c FROM dc_installs')['c'];
  $kpi = function ($l,$v,$s2='',$c='') { return "<div class='kpi $c'><span>$l</span><b>$v</b><small>$s2</small></div>"; };
  echo '<div class="kpis">'
    . $kpi(L('Εγκαταστάσεις','Installations'), $tot, L('συνολικά','total'))
    . $kpi(L('Νέες 7 ημ.','New 7d'), array_sum(array_slice($newI, -7)), '', 'g')
    . $kpi(L('Νέες 30 ημ.','New 30d'), array_sum($newI), '')
    . $kpi(L('Ενεργές 7 ημ.','Active 7d'), (int)dc_one('SELECT COUNT(*) c FROM dc_installs WHERE COALESCE(last_ping,last_seen)>=CAST(? AS INTEGER)', [time()-7*86400])['c'], '', 'g')
    . $kpi(L('Λήψεις 7 ημ.','Downloads 7d'), array_sum(array_slice($dl, -7)), '', 'o')
    . $kpi(L('Λήψεις 30 ημ.','Downloads 30d'), array_sum($dl), '')
    . '</div><div class="grid2">'
    . '<section class="card"><h2>' . L('Νέες εγκαταστάσεις (30 ημέρες)','New installations (30 days)') . '</h2>' . $bars($newI) . '</section>'
    . '<section class="card"><h2>' . L('Λήψεις από τη σελίδα (30 ημέρες)','Website downloads (30 days)') . '</h2>' . $bars($dl, 'o') . '</section>'
    . '<section class="card"><h2>' . L('Ενεργοί σταθμοί ανά ημέρα','Active stations per day') . '</h2>' . $bars($act, 'g') . '</section>';
  $split = function ($col) { $rows = dc_q("SELECT COALESCE(NULLIF($col,''),'?') k, COUNT(*) c FROM dc_installs GROUP BY k ORDER BY c DESC LIMIT 8")->fetchAll(); $mx = 0; foreach ($rows as $r) $mx = max($mx, (int)$r['c']);
    $o = '<div class="shares">'; foreach ($rows as $r) $o .= "<div class='sh'><span class='sl'>" . h($r['k']) . "</span><span class='sb'><i style='width:" . ($mx ? round($r['c']*100/$mx) : 0) . "%'></i></span><span class='sv'>" . (int)$r['c'] . "</span></div>";
    return $o . ($rows ? '' : '<p class="muted">' . L('Καμία εγκατάσταση ακόμη.','No installations yet.') . '</p>') . '</div>'; };
  echo '<section class="card"><h2>' . L('Συστήματα','Systems') . '</h2>' . $split('os') . '</section>'
    . '<section class="card"><h2>' . L('Εκδόσεις σε χρήση','Versions in use') . '</h2>' . $split('version') . '</section></div>';
  // ===== site visits (the public page and the live chat), same as HAM Digi =====
  $R0 = (int)($_GET['r'] ?? 30); $R = in_array($R0, [1, 7, 30, 90, 365], true) ? $R0 : 30; $tV = time() - $R * 86400; $mine = dc_ip();
  $ignored = in_array($mine, array_filter(explode(',', (string)dc_kv('stats_ignore', ''))), true);
  $pgName = ['home' => L('Αρχική σελίδα','Home page','Startsida'), 'chat' => L('Συνομιλία','Live chat','Livechatt')];
  $lgName = ['el' => 'Ελληνικά', 'en' => 'English', 'sv' => 'Svenska', 'it' => 'Italiano', '' => '—'];
  $whoIp = []; // who is behind an IP: from website downloads and registrations (only IPs we already hold)
  foreach (dc_q("SELECT ip, call, name FROM dc_webdl WHERE ip<>'' ORDER BY t")->fetchAll() as $r) $whoIp[$r['ip']] = trim($r['call'] . ' · ' . $r['name'], ' ·');
  foreach (dc_q("SELECT ip, call, name FROM dc_installs WHERE ip<>'' AND call<>'' AND consent_at IS NOT NULL")->fetchAll() as $r) $whoIp[$r['ip']] = trim($r['call'] . ' · ' . $r['name'], ' ·');
  $shr = function ($sql, $args, $map = null) { $o = []; foreach (dc_q($sql, $args)->fetchAll() as $r) { $k = $r['k'] === '' || $r['k'] === null ? '—' : $r['k']; $k = $map[$k] ?? $k; $o[$k] = ($o[$k] ?? 0) + (int)$r['n']; } return $o; };
  $share = function ($m, $tot) { $mx = max(1, $m ? max($m) : 1); $o = '<div class="shares vw">'; foreach ($m as $k => $n) $o .= "<div class='sh'><span class='sl'>" . h($k) . "</span><span class='sb'><i style='width:" . round($n * 100 / $mx) . "%'></i></span><span class='sv'>" . (int)$n . ($tot ? ' · ' . round($n * 100 / $tot) . '%' : '') . '</span></div>'; return $o . ($m ? '' : '<p class="muted">—</p>') . '</div>'; };
  $series = function ($lab, $val, $cls = '') { $mx = max(1, $val ? max($val) : 1); $o = '<div class="bars ' . $cls . '">'; foreach ($val as $i => $v) $o .= '<span title="' . h($lab[$i]) . ': ' . $v . '"><i style="height:' . ($v ? max(4, round($v * 100 / $mx)) : 0) . '%"></i></span>'; return $o . '</div><div class="bax"><span>' . h($lab[0] ?? '') . '</span><span>' . h($lab[count($lab) - 1] ?? '') . '</span></div>'; };
  $dayser = function ($n, $sql) use ($tV) { $lab = []; $val = []; $map = []; foreach (dc_q($sql, [strtotime(gmdate('Y-m-d', time() - ($n - 1) * 86400))])->fetchAll() as $r) $map[$r['d']] = (int)$r['n']; for ($i = $n - 1; $i >= 0; $i--) { $d = gmdate('Y-m-d', time() - $i * 86400); $lab[] = substr($d, 5); $val[] = $map[$d] ?? 0; } return [$lab, $val]; };
  echo '<style>.shares.vw .sh{grid-template-columns:minmax(80px,40%) 1fr auto}.shares.vw .sv{white-space:nowrap;text-align:right}</style>';
  echo '<h2 style="margin:22px 4px 10px">' . L('Επισκέψεις στο site','Site visits','Webbplatsbesök') . '</h2>';
  echo '<section class="card"><div class="filters" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">';
  foreach ([1 => L('24 ώρες','24 hours','24 timmar'), 7 => L('7 ημέρες','7 days','7 dagar'), 30 => L('30 ημέρες','30 days','30 dagar'), 90 => L('90 ημέρες','90 days','90 dagar'), 365 => L('1 έτος','1 year','1 år')] as $d => $lb) echo '<a class="btn sm' . ($R === $d ? ' pri' : '') . '" href="?p=stats&r=' . $d . '">' . $lb . '</a>';
  echo '<span class="spacer" style="flex:1"></span><a class="btn sm" href="?p=stats&r=' . $R . '&export=csv">⇩ CSV</a>'
    . '<form method="post" style="margin:0">' . csrf() . '<input type="hidden" name="p" value="stats"><input type="hidden" name="a" value="stats_ignore">' . ($ignored ? '<input type="hidden" name="remove" value="1">' : '') . '<button class="btn sm" title="' . h($mine) . '">' . ($ignored ? L('Μέτρα ξανά τις δικές μου επισκέψεις','Count my own visits again','Räkna mina egna besök igen') : L('Μην μετράς τις δικές μου επισκέψεις','Do not count my own visits','Räkna inte mina egna besök')) . '</button></form></div>'
    . '<p class="muted" style="margin:8px 0 0">' . L('Μετριέται κάθε προβολή σελίδας του site (αρχική, συνομιλία), ανεξάρτητα από το αν κάποιος κατεβάσει το πρόγραμμα. Τα ρομπότ των μηχανών αναζήτησης δεν μετράνε στους αριθμούς.','Every page view of the site (home, chat) is counted, whether or not someone downloads the program. Search-engine robots are not in the numbers.','Varje sidvisning på webbplatsen (startsida, chatt) räknas, oavsett om någon laddar ner programmet. Sökmotorrobotar ingår inte i siffrorna.') . '</p></section>';
  $vis = (int)dc_scalar('SELECT COUNT(*) FROM dc_visits WHERE bot=0 AND t>=?', [$tV]);
  $uniq = (int)dc_scalar('SELECT COUNT(DISTINCT ip) FROM dc_visits WHERE bot=0 AND t>=?', [$tV]);
  $ret = (int)dc_scalar("SELECT COUNT(*) FROM (SELECT ip FROM dc_visits WHERE bot=0 AND t>=? GROUP BY ip HAVING COUNT(DISTINCT strftime('%Y-%m-%d', t, 'unixepoch'))>1)", [$tV]);
  $now5 = (int)dc_scalar('SELECT COUNT(DISTINCT ip) FROM dc_visits WHERE bot=0 AND t>=?', [time() - 300]);
  $bots = (int)dc_scalar('SELECT COUNT(*) FROM dc_visits WHERE bot=1 AND t>=?', [$tV]);
  $dls = (int)dc_scalar('SELECT COUNT(*) FROM dc_webdl WHERE t>=?', [$tV]);
  $kp = function ($label, $val, $sub = '', $cls = '') { return "<div class='kpi $cls'><span>$label</span><b>$val</b><small>$sub</small></div>"; };
  echo '<div class="kpis">' . $kp(L('Επισκέψεις σελίδων','Page views','Sidvisningar'), $vis, $uniq ? number_format($vis / $uniq, 1) . L(' σελίδες ανά επισκέπτη',' pages per visitor',' sidor per besökare') : '—')
    . $kp(L('Μοναδικοί επισκέπτες','Unique visitors','Unika besökare'), $uniq, L('διαφορετικές IP','different IP addresses','olika IP-adresser'), 'g')
    . $kp(L('Ξαναγύρισαν','Came back','Kom tillbaka'), $ret, L('σε περισσότερες από 1 ημέρα','on more than 1 day','på mer än 1 dag'))
    . $kp(L('Τώρα στο site','On the site now','På webbplatsen nu'), $now5, L('τελευταία 5 λεπτά','last 5 minutes','senaste 5 minuterna'), $now5 ? 'g' : '')
    . $kp(L('Λήψεις από το site','Downloads from the site','Nedladdningar från webbplatsen'), $dls, $uniq ? number_format($dls * 100 / $uniq, 1) . L('% των επισκεπτών','% of visitors','% av besökarna') : '—', 'g')
    . $kp(L('Ρομπότ (εκτός αριθμών)','Robots (not counted)','Robotar (ej räknade)'), $bots, L('μηχανές αναζήτησης κ.λπ.','search engines etc.','sökmotorer m.m.')) . '</div>';
  $nd = max($R, 7);
  list($vl, $vv) = $dayser($nd, "SELECT strftime('%Y-%m-%d', t, 'unixepoch') d, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY d");
  list($ul, $uv) = $dayser($nd, "SELECT d, COUNT(*) n FROM (SELECT DISTINCT strftime('%Y-%m-%d', t, 'unixepoch') d, ip FROM dc_visits WHERE bot=0 AND t>=?) GROUP BY d");
  echo '<div class="grid2"><section class="card"><h2>' . L('Επισκέψεις ανά ημέρα (προβολές σελίδων)','Visits per day (page views)','Besök per dag (sidvisningar)') . '</h2>' . $series($vl, $vv) . '</section>'
    . '<section class="card"><h2>' . L('Μοναδικοί επισκέπτες ανά ημέρα','Unique visitors per day','Unika besökare per dag') . '</h2>' . $series($ul, $uv, 'g') . '</section></div>';
  $hr = array_fill(0, 24, 0); foreach (dc_q("SELECT CAST(strftime('%H', t, 'unixepoch') AS INTEGER) k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k", [$tV])->fetchAll() as $r) $hr[(int)$r['k']] = (int)$r['n'];
  $wk = array_fill(0, 7, 0); foreach (dc_q("SELECT CAST(strftime('%w', t, 'unixepoch') AS INTEGER) k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k", [$tV])->fetchAll() as $r) $wk[(int)$r['k']] = (int)$r['n'];
  $wn = $LANG === 'el' ? ['Κυρ','Δευ','Τρί','Τετ','Πέμ','Παρ','Σάβ'] : ($LANG === 'sv' ? ['Sön','Mån','Tis','Ons','Tor','Fre','Lör'] : ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']);
  $wl = []; $wv = []; foreach ([1, 2, 3, 4, 5, 6, 0] as $k) { $wl[] = $wn[$k]; $wv[] = $wk[$k]; }
  echo '<div class="grid2"><section class="card"><h2>' . L('Ώρα της ημέρας','Time of day','Tid på dygnet') . ' <small>UTC</small></h2>' . $series(array_map(function ($h) { return sprintf('%02d:00', $h); }, array_keys($hr)), array_values($hr), 'o') . '</section>'
    . '<section class="card"><h2>' . L('Ημέρα της εβδομάδας','Day of the week','Veckodag') . '</h2>' . $series($wl, $wv, 'o') . '</section></div>';
  echo '<div class="grid2"><section class="card"><h2>' . L('Σελίδες','Pages','Sidor') . '</h2>' . $share($shr('SELECT page k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k ORDER BY n DESC', [$tV], $pgName), $vis)
    . '</section><section class="card"><h2>' . L('Γλώσσα σελίδας','Page language','Sidans språk') . '</h2>' . $share($shr('SELECT lang k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k ORDER BY n DESC', [$tV], $lgName), $vis) . '</section></div>';
  echo '<div class="grid2"><section class="card"><h2>' . L('Από πού ήρθαν','Where they came from','Varifrån de kom') . '</h2>' . $share($shr("SELECT CASE WHEN ref='' THEN '" . L('Απευθείας / σελιδοδείκτης','Direct / bookmark','Direkt / bokmärke') . "' ELSE ref END k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k ORDER BY n DESC LIMIT 12", [$tV]), $vis)
    . '</section><section class="card"><h2>Browser · ' . L('σύστημα · συσκευή','system · device','system · enhet') . '</h2>' . $share($shr('SELECT br k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k ORDER BY n DESC', [$tV]), $vis) . '<div style="height:12px"></div>'
    . $share($shr('SELECT os k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k ORDER BY n DESC', [$tV]), $vis) . '<div style="height:12px"></div>' . $share($shr('SELECT dev k, COUNT(*) n FROM dc_visits WHERE bot=0 AND t>=? GROUP BY k ORDER BY n DESC', [$tV]), $vis) . '</section></div>';
  // who: the most active visitors and the latest visits
  $fip = trim((string)($_GET['ip'] ?? ''));
  $top = dc_q("SELECT ip, COUNT(*) n, COUNT(DISTINCT strftime('%Y-%m-%d', t, 'unixepoch')) days, MIN(t) f, MAX(t) l, GROUP_CONCAT(DISTINCT page) pg, MAX(br) br, MAX(os) os FROM dc_visits WHERE bot=0 AND t>=? GROUP BY ip ORDER BY n DESC, l DESC LIMIT 30", [$tV])->fetchAll();
  echo '<section class="card"><h2>' . L('Επισκέπτες','Visitors','Besökare') . ' <small>' . L('οι 30 πιο ενεργοί · το όνομα φαίνεται μόνο αν η ίδια IP έκανε λήψη ή εγγραφή','the 30 most active · a name shows only when the same IP made a download or registration','de 30 mest aktiva · ett namn visas bara om samma IP gjort en nedladdning eller registrering') . '</small></h2>';
  if (!$top) echo '<div class="muted">' . L('Δεν υπάρχουν επισκέψεις ακόμη σε αυτή την περίοδο.','No visits in this period yet.','Inga besök under perioden ännu.') . '</div>';
  else { echo '<div class="tw"><table class="tbl"><tr><th>IP</th><th>' . L('Ποιος','Who','Vem') . '</th><th>' . L('Προβολές','Views','Visningar') . '</th><th>' . L('Ημέρες','Days','Dagar') . '</th><th>' . L('Σελίδες','Pages','Sidor') . '</th><th>Browser · ' . L('σύστημα','system','system') . '</th><th>' . L('Πρώτη','First','Första') . '</th><th>' . L('Τελευταία','Last','Senaste') . '</th></tr>';
    foreach ($top as $r) echo '<tr><td class="mono"><a href="?p=stats&r=' . $R . '&ip=' . urlencode($r['ip']) . '">' . h($r['ip']) . '</a></td><td>' . (isset($whoIp[$r['ip']]) ? '<b>' . h($whoIp[$r['ip']]) . '</b>' : '<span class="muted">—</span>') . '</td><td>' . (int)$r['n'] . '</td><td>' . (int)$r['days'] . '</td><td>' . h(implode(', ', array_map(function ($x) use ($pgName) { return $pgName[$x] ?? $x; }, explode(',', (string)$r['pg'])))) . '</td><td>' . h($r['br'] . ' · ' . $r['os']) . '</td><td>' . dc_dt($r['f']) . '</td><td>' . dc_dt($r['l']) . '</td></tr>';
    echo '</table></div>'; }
  echo '</section>';
  $wh = $fip !== '' ? 'bot=0 AND ip=?' : 'bot=0 AND t>=?'; $arg = $fip !== '' ? [$fip] : [$tV];
  $rec = dc_q("SELECT * FROM dc_visits WHERE $wh ORDER BY t DESC LIMIT 100", $arg)->fetchAll();
  echo '<section class="card"><h2>' . ($fip !== '' ? L('Επισκέψεις της IP ','Visits of IP ','Besök från IP ') . '<span class="mono">' . h($fip) . '</span> <small><a href="?p=stats&r=' . $R . '">' . L('← όλες','← all','← alla') . '</a></small>' : L('Τελευταίες επισκέψεις','Latest visits','Senaste besöken')) . '</h2>';
  if (!$rec) echo '<div class="muted">' . L('Καμία ακόμη.','None yet.','Inga ännu.') . '</div>';
  else { echo '<div class="tw"><table class="tbl"><tr><th>' . L('Ώρα','Time','Tid') . '</th><th>IP</th><th>' . L('Ποιος','Who','Vem') . '</th><th>' . L('Σελίδα','Page','Sida') . '</th><th>' . L('Γλώσσα','Lang','Språk') . '</th><th>Browser · ' . L('σύστημα','system','system') . '</th><th>' . L('Ήρθε από','Came from','Kom från') . '</th></tr>';
    foreach ($rec as $r) echo '<tr><td>' . dc_dt($r['t']) . '</td><td class="mono"><a href="?p=stats&r=' . $R . '&ip=' . urlencode($r['ip']) . '">' . h($r['ip']) . '</a></td><td>' . (isset($whoIp[$r['ip']]) ? '<b>' . h($whoIp[$r['ip']]) . '</b>' : '<span class="muted">—</span>') . '</td><td>' . h($pgName[$r['page']] ?? $r['page']) . '</td><td>' . h($lgName[$r['lang']] ?? $r['lang']) . '</td><td>' . h($r['br'] . ' · ' . $r['os'] . ' · ' . $r['dev']) . '</td><td>' . h($r['ref'] ?: '—') . '</td></tr>';
    echo '</table></div>'; }
  echo '</section>';
}

/* ===================== RELEASES ===================== */
elseif ($p === 'releases') {
  echo '<section class="card"><h2>' . L('Ανέβασμα νέας έκδοσης','Upload a new version') . '</h2>'
    . '<form class="form" method="post" enctype="multipart/form-data">' . csrf() . '<input type="hidden" name="a" value="rel_upload"><input type="hidden" name="p" value="releases">'
    . '<div class="g2"><label>' . L('Αριθμός έκδοσης','Version') . '<input name="ver" placeholder="' . L('αυτόματα από το πακέτο','read from the package') . '"></label>'
    . '<label>' . L('Ελάχιστο shell','Min shell') . '<input name="minshell" placeholder="' . L('αυτόματα από το πακέτο','read from the package') . '"></label></div>'
    . '<label>' . L('Αρχείο πακέτου (.dcpkg)','Package file (.dcpkg)') . '<input type="file" name="pkg" accept=".dcpkg" required></label>'
    . '<div class="g2"><label>' . L('Σημειώσεις (EL)','Notes (EL)') . '<textarea name="n_el" rows="2"></textarea></label><label>' . L('Σημειώσεις (EN)','Notes (EN)') . '<textarea name="n_en" rows="2"></textarea></label></div>'
    . '<button class="btn pri">' . L('Ανέβασμα','Upload') . '</button></form></section>';
  $rels = dc_q("SELECT * FROM dc_releases ORDER BY COALESCE(published,0) DESC, id DESC")->fetchAll();
  echo '<section class="card"><h2>' . L('Εκδόσεις','Releases') . ' <small>(' . count($rels) . ')</small></h2>';
  if (!$rels) echo '<p class="empty">' . L('Καμία έκδοση. Ανέβασε την πρώτη.','No releases yet. Upload the first.') . '</p>';
  foreach ($rels as $r) {
    $on = $r['status'] === 'active';
    echo '<details class="relrow' . ($on ? ' active' : '') . '"' . ($on ? ' open' : '') . '><summary><span class="ver">v' . h($r['version']) . '</span>'
      . '<span class="pill ' . ($on ? 'ok' : 'dim') . '">' . h($r['status']) . '</span>'
      . '<span class="muted">' . round(($r['size'] ?? 0)/1024) . ' KB · rollout ' . (int)$r['rollout'] . '% · ' . dc_dt($r['published']) . '</span></summary>'
      . '<div class="relbody"><div class="acts">'
      . '<form method="post">' . csrf() . '<input type="hidden" name="p" value="releases"><input type="hidden" name="version" value="' . h($r['version']) . '"><button class="btn" name="a" value="rel_activate">' . L('Ενεργοποίηση','Make active') . '</button></form>'
      . '<form method="post">' . csrf() . '<input type="hidden" name="p" value="releases"><input type="hidden" name="version" value="' . h($r['version']) . '"><button class="btn pri" name="a" value="rel_forceall">' . L('Επιβολή σε όλους','Force to everyone') . '</button></form>'
      . '<form method="post" class="ro">' . csrf() . '<input type="hidden" name="p" value="releases"><input type="hidden" name="version" value="' . h($r['version']) . '"><label>rollout <input type="number" name="rollout" min="0" max="100" value="' . (int)$r['rollout'] . '"></label><button class="btn" name="a" value="rel_rollout">%</button></form>'
      . '<form method="post" onsubmit="return confirm(\'Delete v' . h($r['version']) . '?\')">' . csrf() . '<input type="hidden" name="p" value="releases"><input type="hidden" name="version" value="' . h($r['version']) . '"><button class="btn danger" name="a" value="rel_del">' . L('Διαγραφή','Delete') . '</button></form>'
      . '</div><p class="muted mono" style="margin-top:10px">sha256: ' . h(substr($r['sha256'] ?? '', 0, 32)) . '…</p>'
      . ($r['notes_el'] ? '<pre class="notes">' . h($r['notes_el']) . '</pre>' : '') . '</div></details>';
  }
  echo '</section>';
}

/* ===================== INSTALLS ===================== */
elseif ($p === 'installs') {
  $qf = trim($_GET['q'] ?? ''); $sf = $_GET['st'] ?? '';
  $w = []; $args = [];
  if ($qf !== '') { $no = dc_no_filter($qf); $w[] = '(call LIKE ? OR id LIKE ? OR name LIKE ? OR mail LIKE ? OR dmr_id LIKE ?' . ($no !== null ? ' OR rowid=' . $no : '') . ')'; array_push($args, "%$qf%", "%$qf%", "%$qf%", "%$qf%", "%$qf%"); }
  if (in_array($sf, ['demo','full','free','locked','disabled'], true)) { $w[] = 'state=?'; $args[] = $sf; }
  $where = $w ? ('WHERE ' . implode(' AND ', $w)) : '';
  $rows = dc_q("SELECT rowid AS rno, * FROM dc_installs $where ORDER BY MAX(COALESCE(last_ping,0),COALESCE(last_seen,0)) DESC LIMIT 500", $args)->fetchAll();
  echo '<section class="card"><h2>' . L('Εγκαταστάσεις','Installations') . ' <small>(' . count($rows) . ')</small></h2>'
    . '<form class="filters" method="get"><input type="hidden" name="p" value="installs"><input name="q" value="' . h($qf) . '" placeholder="' . L('διακριτικό, DC-…, email…','callsign, DC-…, email…') . '">'
    . '<select name="st"><option value="">' . L('όλες','all') . '</option>'
    . '<option value="demo"' . ($sf==='demo'?' selected':'') . '>demo</option><option value="full"' . ($sf==='full'?' selected':'') . '>full</option><option value="free"' . ($sf==='free'?' selected':'') . '>free</option><option value="locked"' . ($sf==='locked'?' selected':'') . '>locked</option><option value="disabled"' . ($sf==='disabled'?' selected':'') . '>disabled</option></select>'
    . '<button class="btn sm">' . L('Φίλτρο','Filter') . '</button></form>'
    . '<div class="tw"><table class="tbl"><tr><th>' . L('Διακριτικό / Αρ. εγκατάστασης','Callsign / Installation no.') . '</th><th>' . L('Έκδοση','Version') . '</th><th>OS</th><th>' . L('Κατάσταση','State') . '</th><th>' . L('Τελευταία','Last seen') . '</th><th style="width:38%">' . L('Ενέργειες','Actions') . '</th></tr>';
  $paid = [];                                                      // what each installation has paid, every currency on its own
  foreach (dc_q("SELECT install, currency c, SUM(amount) s FROM dc_payments WHERE status='Completed' AND install IS NOT NULL AND install<>'' GROUP BY install, currency")->fetchAll() as $x) $paid[$x['install']][] = number_format((float)$x['s'], 2) . ' ' . strtoupper($x['c']);
  foreach ($rows as $r) {
    $online = dc_online($r);
    echo '<tr><td><b>' . h($r['call'] ?: '—') . '</b><br><span class="muted mono" style="font-size:12px"><b>' . sprintf('DC-%05d', $r['rno']) . '</b></span>'
       . ($r['name'] ? '<br><span class="muted" style="font-size:11px">' . h($r['name']) . '</span>' : '')
       . ($r['mail'] ? '<br><span class="muted" style="font-size:11px">' . h($r['mail']) . '</span>' : '')
       . ($r['dmr_id'] ? '<br><span class="muted" style="font-size:11px">DMR ID ' . h($r['dmr_id']) . '</span>' : '')
       . (!empty($paid[$r['id']]) ? '<br><span class="pill ok" title="' . h(L('Πληρωμές αυτής της εγκατάστασης','Payments of this installation')) . '">♥ ' . h(implode(' · ', $paid[$r['id']])) . '</span>' : '') . '</td>'
       . '<td>' . h($r['version'] ?: '—') . '</td><td>' . h($r['os'] ?: '—') . '</td>'
       . '<td><span class="pill onl ' . ($online?'ok':'') . '"><i></i>' . ($online ? 'online' : 'offline') . '</span><br>' . dc_lic_label($r) . '</td>'
       . '<td class="muted">' . dc_dt(dc_last($r)) . '</td><td><div class="acts">'
       . lic_form($r, 'installs') . hw_form($r, 'installs')
       . ((int)$r['enabled'] === 1
          ? '<form method="post">' . csrf() . '<input type="hidden" name="p" value="installs"><input type="hidden" name="iid" value="' . h($r['id']) . '"><button class="btn sm danger" name="a" value="disable">' . L('Απενεργ.','Disable') . '</button></form>'
          : '<form method="post">' . csrf() . '<input type="hidden" name="p" value="installs"><input type="hidden" name="iid" value="' . h($r['id']) . '"><button class="btn sm" name="a" value="enable">' . L('Ενεργό','Enable') . '</button></form>')
       . '</div></td></tr>';
  }
  echo '</table></div>';
  if (!$rows) echo '<p class="empty">' . L('Καμία εγκατάσταση.','No installations.') . '</p>';
  echo '</section>';
}

/* ===================== DOWNLOADS / SIGN-UPS ===================== */
elseif ($p === 'downloads') {
  $rows = dc_q("SELECT * FROM dc_webdl ORDER BY t DESC LIMIT 500")->fetchAll();
  echo '<section class="card"><h2>' . L('Λήψεις από τη σελίδα','Website downloads') . ' <small>(' . count($rows) . ')</small></h2>'
    . '<div class="tw"><table class="tbl"><tr><th>' . L('Πότε','When') . '</th><th>' . L('Διακριτικό','Callsign') . '</th><th>' . L('Όνομα','Name') . '</th><th>Email</th><th>OS</th><th>IP</th></tr>';
  foreach ($rows as $r)
    echo '<tr><td class="muted">' . dc_dt($r['t']) . '</td><td><b>' . h($r['call'] ?: '—') . '</b></td><td>' . h($r['name'] ?: '—') . '</td><td class="muted">' . h($r['email'] ?: '—') . '</td><td>' . h($r['os'] ?: '—') . '</td><td class="muted mono">' . h($r['ip'] ?: '—') . '</td></tr>';
  echo '</table></div>';
  if (!$rows) echo '<p class="empty">' . L('Καμία λήψη ακόμη.','No downloads yet.') . '</p>';
  echo '</section>';
}

/* ===================== LICENCES / CODES (same page as HAM Digi) ===================== */
elseif ($p === 'licenses') {
  $S = dc_lic_settings(); $sel = function ($v, $c) { return $v === $c ? ' selected' : ''; };
  $hp = '<input type="hidden" name="p" value="licenses">';
  echo '<section class="card"><h2>' . L('Νέες εγκαταστάσεις (προεπιλογή)', 'New installations (default)') . '</h2><form method="post" class="form">' . csrf() . $hp . '<input type="hidden" name="a" value="lic_default"><div class="g2">'
    . '<label>' . L('Τι παίρνει κάθε νέα εγκατάσταση', 'What every new installation gets') . '<select name="mode"><option value="free"' . $sel('free', $S['mode']) . '>' . L('Δωρεάν — λειτουργεί χωρίς όριο', 'Free — works without limit') . '</option><option value="demo"' . $sel('demo', $S['mode']) . '>' . L('Demo — λήγει μετά από τη διάρκεια', 'Demo — ends after the duration') . '</option><option value="locked"' . $sel('locked', $S['mode']) . '>' . L('Κλειδωμένη — μέχρι να την ενεργοποιήσω', 'Locked — until I activate it') . '</option></select></label>'
    . '<label>' . L('Διάρκεια demo', 'Demo duration') . '<span style="display:flex;gap:6px"><input name="n" type="number" min="1" value="' . (int)$S['n'] . '" style="width:90px"><select name="unit"><option value="h"' . $sel('h', $S['unit']) . '>' . L('ώρες', 'hours') . '</option><option value="d"' . $sel('d', $S['unit']) . '>' . L('ημέρες', 'days') . '</option><option value="m"' . $sel('m', $S['unit']) . '>' . L('μήνες', 'months') . '</option><option value="y"' . $sel('y', $S['unit']) . '>' . L('χρόνια', 'years') . '</option></select></span></label>'
    . '<label>' . L('Μήνυμα στην οθόνη κλειδώματος (Ελληνικά)', 'Message on the lock screen (Greek)') . '<textarea name="msg_el" rows="2" placeholder="' . L('π.χ. Ευχαριστώ που δοκιμάζεις το DigiConnect!', 'e.g. Thank you for trying DigiConnect!') . '">' . h($S['msg_el']) . '</textarea></label><label>' . L('Μήνυμα στην οθόνη κλειδώματος (Αγγλικά)', 'Message on the lock screen (English)') . '<textarea name="msg_en" rows="2">' . h($S['msg_en']) . '</textarea></label>'
    . '<label>' . L('Κουμπί στο πρόγραμμα (σε όλες τις εγκαταστάσεις)', 'Button in the program (on every installation)') . '<select name="offer"><option value="none"' . $sel('none', $S['offer']) . '>' . L('Τίποτα — χωρίς αναφορά σε αγορά ή δωρεά', 'Nothing — no mention of buying or donating') . '</option><option value="donate"' . $sel('donate', $S['offer']) . '>' . L('Δωρεά (Donate)', 'Donation (Donate)') . '</option><option value="buy"' . $sel('buy', $S['offer']) . '>' . L('Αγορά', 'Buy') . '</option></select></label>'
    . '<label>' . L('Ποσό που φαίνεται στο κουμπί (π.χ. 5 €, προαιρετικό)', 'Amount shown on the button (e.g. 5 €, optional)') . '<input name="amount" value="' . h($S['amount']) . '" maxlength="30"></label>'
    . '<label style="grid-column:1/-1">' . L('Σύνδεσμος του κουμπιού (https://…, π.χ. PayPal.me ή σελίδα του hellaszone.com· κενό = το PayPal του προγράμματος)', 'Button link (https://…, e.g. PayPal.me or a hellaszone.com page; empty = the program’s own PayPal)') . '<input name="link" value="' . h($S['link']) . '" placeholder="https://www.paypal.com/donate/?hosted_button_id=…"></label>'
    . '</div><div class="help">' . L('Το demo μιας νέας εγκατάστασης μετρά από την πρώτη φορά που συνδέθηκε. Ό,τι ορίσεις χωριστά σε μια εγκατάσταση (παρακάτω) υπερισχύει της προεπιλογής. Το «Όταν ο server δεν είναι προσβάσιμος» είναι στις Ρυθμίσεις. Το πρόγραμμα χρησιμοποιεί προς το παρόν μόνο τον σύνδεσμο· το «Κουμπί» και το «Ποσό» στέλνονται στο πρόγραμμα αλλά δεν τα διαβάζει ακόμη.', 'A new installation’s demo counts from its first contact. Whatever you set for one installation (below) overrides the default. “When this server cannot be reached” is in Settings. For now the program only uses the link; “Button” and “Amount” are sent to it but it does not read them yet.') . '</div><button class="btn pri">' . L('Αποθήκευση', 'Save') . '</button></form>'
    . '<form method="post" style="margin-top:10px" onsubmit="return confirm(\'' . L('Όλες οι εγκαταστάσεις που πήραν την προεπιλογή θα την ξαναπάρουν με τις νέες ρυθμίσεις. Συνέχεια;', 'All installations that got the default will take it again with the new settings. Continue?') . '\')">' . csrf() . $hp . '<input type="hidden" name="a" value="lic_reset_all"><button class="btn sm">' . L('Εφαρμογή της προεπιλογής και στις υπάρχουσες (όσες δεν έχουν δική τους ρύθμιση)', 'Apply the default to existing installations too (those without their own setting)') . '</button></form></section>';

  // activation codes
  echo '<details class="card codes"' . (isset($_GET['codes']) ? ' open' : '') . '><summary><h2 style="display:inline">' . L('Ειδικές περιπτώσεις: κωδικοί ενεργοποίησης', 'Special cases: activation codes') . '</h2> <small class="muted">' . L('— η ενεργοποίηση μετά από πληρωμή γίνεται αυτόματα (ή με το κουμπί «Ενεργοποίηση» στις Πληρωμές)· οι κωδικοί είναι μόνο για ειδικές περιπτώσεις', '— activation after a payment is automatic (or with the “Activate” button in Payments); codes are only for special cases') . '</small></summary><form method="post" class="form">' . csrf() . $hp . '<input type="hidden" name="a" value="code_new"><div class="g2">'
    . '<label>' . L('Τύπος', 'Type') . '<select name="kind"><option value="demo">Demo</option><option value="full">' . L('Άδεια', 'Licence') . '</option></select></label>'
    . '<label>' . L('Διάρκεια', 'Duration') . '<span style="display:flex;gap:6px;align-items:center"><input name="n" type="number" min="1" value="6" style="width:90px"><select name="unit"><option value="h">' . L('ώρες', 'hours') . '</option><option value="d" selected>' . L('ημέρες', 'days') . '</option><option value="m">' . L('μήνες', 'months') . '</option><option value="y">' . L('χρόνια', 'years') . '</option></select><label class="chk" style="display:flex;flex-direction:row;gap:6px;align-items:center"><input type="checkbox" name="perm" value="1"> ' . L('μόνιμη (μόνο για Άδεια)', 'permanent (Licence only)') . '</label></span></label>'
    . '<label>' . L('Πόσοι υπολογιστές μπορούν να τον χρησιμοποιήσουν (0 = απεριόριστοι)', 'How many computers can use it (0 = unlimited)') . '<input name="uses" type="number" min="0" value="1"></label>'
    . '<label>' . L('Ο κωδικός ισχύει για (ημέρες, 0 = πάντα)', 'The code itself is valid for (days, 0 = always)') . '<input name="valid_days" type="number" min="0" value="0"></label>'
    . '<label>' . L('Πόσους κωδικούς να φτιάξω', 'How many codes to make') . '<input name="count" type="number" min="1" max="200" value="1"></label><label>' . L('Σημείωση (π.χ. για ποιον)', 'Note (e.g. who it is for)') . '<input name="note" maxlength="120"></label>'
    . '</div><div class="help">' . L('Προσοχή: το πρόγραμμα DigiConnect δεν έχει ακόμη πεδίο για να γράψει ο χρήστης κωδικό· ο server τους δέχεται (api.php) και θα χρησιμοποιηθούν όταν προστεθεί. Η διάρκεια μετρά από τη στιγμή που γράφεται ο κωδικός.', 'Note: the DigiConnect program does not have a field for typing a code yet; the server accepts codes (api.php) and they will be usable once it is added. The duration counts from the moment the code is entered.') . '</div><button class="btn pri">' . L('Δημιουργία', 'Create') . '</button></form>';
  echo '<div class="tw"><table class="tbl"><tr><th>' . L('Κωδικός', 'Code') . '</th><th>' . L('Τύπος', 'Type') . '</th><th>' . L('Διάρκεια', 'Duration') . '</th><th>' . L('Χρήσεις', 'Uses') . '</th><th>' . L('Ισχύει έως', 'Valid until') . '</th><th>' . L('Σημείωση', 'Note') . '</th><th>' . L('Τελευταία χρήση', 'Last used') . '</th><th></th></tr>';
  foreach (dc_q('SELECT * FROM dc_codes ORDER BY created DESC LIMIT 300')->fetchAll() as $c) { $d = dc_unit_name((string)$c['unit'], $c['dur']);
    echo '<tr><td class="mono"><b>' . h($c['code']) . '</b></td><td>' . ($c['kind'] === 'full' ? L('Άδεια', 'Licence') : 'Demo') . '</td><td>' . ($c['kind'] === 'full' && !$c['dur'] ? L('μόνιμη', 'permanent') : h(L($d[0], $d[1]))) . '</td><td>' . (int)$c['used'] . ' / ' . ((int)$c['uses'] ? (int)$c['uses'] : '∞') . '</td><td>' . (!empty($c['valid_until']) ? dc_dt($c['valid_until']) : '—') . '</td><td>' . h($c['note']) . '</td><td>' . ($c['last_used'] ? dc_dt($c['last_used']) . ' · <a class="mono" href="?p=installs&q=' . urlencode(dc_inst_no($c['last_install'])) . '">' . h(dc_inst_no($c['last_install']) ?: '—') . '</a>' : '—') . '</td><td><form method="post" onsubmit="return confirm(\'OK?\')" style="display:inline">' . csrf() . $hp . '<input type="hidden" name="a" value="code_del"><input type="hidden" name="code" value="' . h($c['code']) . '"><button class="btn sm">' . L('Διαγραφή', 'Delete') . '</button></form>'
      . ((int)$c['uses'] > 0 && (int)$c['used'] >= (int)$c['uses'] ? '<form method="post" style="display:inline;margin-left:4px">' . csrf() . $hp . '<input type="hidden" name="a" value="code_more"><input type="hidden" name="code" value="' . h($c['code']) . '"><button class="btn sm" title="' . h(L('Δέχεται έναν υπολογιστή ακόμη', 'Accepts one more computer')) . '">+1</button></form>' : '') . '</td></tr>'; }
  echo '</table></div></details>';

  // every installation with its licence
  $fq = trim($_GET['q'] ?? ''); $w = ''; $args = [];
  if ($fq !== '') { $no = dc_no_filter($fq); $w = ' WHERE (id LIKE ? OR call LIKE ? OR note LIKE ? OR owner LIKE ? OR mail LIKE ?' . ($no !== null ? ' OR rowid=' . $no : '') . ')'; $args = array_fill(0, 5, "%$fq%"); }
  echo '<section class="card"><h2>' . L('Εγκαταστάσεις και άδειες', 'Installations and licences') . '</h2><form class="filters" method="get"><input type="hidden" name="p" value="licenses"><input name="q" value="' . h($fq) . '" placeholder="' . L('Αναζήτηση: call, αριθμός DC-…, ID, σημείωση', 'Search: call, number DC-…, ID, note') . '"><button class="btn">' . L('Φίλτρο', 'Filter') . '</button></form><div class="tw"><table class="tbl"><tr><th>Call</th><th>' . L('Σύστημα', 'System') . '</th><th>' . L('Κατάσταση', 'Status') . '</th><th>' . L('Ορίστηκε', 'Set by') . '</th><th>' . L('Τελευταίος έλεγχος', 'Last check') . '</th><th>' . L('Αλλαγή', 'Change') . '</th></tr>';
  foreach (dc_q('SELECT rowid AS rno, * FROM dc_installs' . $w . ' ORDER BY MAX(COALESCE(last_ping,0), COALESCE(last_seen,0)) DESC LIMIT 300', $args)->fetchAll() as $r) {
    echo '<tr><td><span class="mono muted" style="white-space:nowrap">' . sprintf('DC-%05d', $r['rno']) . '</span><br><b>' . h($r['call'] ?: substr($r['id'], 0, 8)) . '</b>' . ($r['owner'] ? '<br><small>' . h($r['owner']) . '</small>' : '') . ($r['note'] ? '<br><small class="muted">' . h($r['note']) . '</small>' : '') . '</td><td>' . h($r['os'] ?: '—') . '</td><td>' . dc_lic_label($r) . '</td><td><small class="muted">' . h($r['lic_by'] ?: L('προεπιλογή', 'default')) . '</small></td><td class="muted">' . dc_dt(dc_last($r)) . '</td><td>' . lic_form($r, 'licenses') . '</td></tr>';
  }
  echo '</table></div></section>';
}

/* ===================== MODES / POLICIES ===================== */
elseif ($p === 'modes') {
  $hp = '<input type="hidden" name="p" value="modes">'; $MN = ['on' => L('Ενεργό', 'On'), 'off' => L('Κλειστό', 'Off'), 'beta' => L('Μόνο δοκιμαστές', 'Testers only')];
  $total = (int)dc_scalar('SELECT COUNT(*) FROM dc_installs'); $tst = (int)dc_scalar('SELECT COUNT(*) FROM dc_installs WHERE tester=1');
  $all = dc_q('SELECT rowid AS rno, * FROM dc_installs')->fetchAll();
  $mc = ['on' => 'ok', 'off' => 'bad', 'beta' => 'o'];
  echo '<section class="card"><h2>' . L('Modes — για όλους', 'Modes — for everyone') . '</h2><p class="muted">' . L('Κλείνεις ή ανοίγεις ένα mode σε όλες τις εγκαταστάσεις. «Μόνο δοκιμαστές» = ανοιχτό μόνο στις εγκαταστάσεις που έχεις σημάδει ως δοκιμαστές (παρακάτω). Η αλλαγή φτάνει στα προγράμματα στον επόμενο έλεγχο, χωρίς καμία ενέργεια από τον χρήστη.', 'Close or open a mode on every installation. “Testers only” = open only on installations you marked as testers (below). The change reaches the programs at their next check, with nothing for the user to do.') . '</p>'
    . '<div class="mgrid">';
  foreach (DC_MODES as $m) {
    $g = dc_mode_global($m); $nOn = 0; foreach ($all as $r) if (dc_mode_for($r, $m) === 'on') $nOn++;
    echo '<form method="post" class="mcard ' . $g . '">' . csrf() . $hp . '<input type="hidden" name="a" value="mode_set"><input type="hidden" name="mode" value="' . h($m) . '">'
      . '<div class="mh"><b>' . h($m) . '</b><span class="pill ' . $mc[$g] . '">' . h($MN[$g]) . '</span></div>'
      . '<div class="seg">';
    foreach (['on', 'off', 'beta'] as $v) echo '<button name="state" value="' . $v . '" class="' . ($g === $v ? 'sel ' . $v : '') . '">' . h($MN[$v]) . '</button>';
    echo '</div><small class="muted">' . sprintf(L('Ανοιχτό σε %d από %d εγκαταστάσεις', 'Open on %d of %d installations'), $nOn, $total) . '</small></form>';
  }
  echo '</div><div class="mall"><form method="post" style="display:inline">' . csrf() . $hp . '<input type="hidden" name="a" value="modes_all"><input type="hidden" name="state" value="on"><button class="btn sm">' . L('Άνοιγμα ΟΛΩΝ', 'Open ALL') . '</button></form> '
    . '<form method="post" style="display:inline" onsubmit="return confirm(\'' . L('Να κλείσουν ΟΛΑ τα modes σε όλους;', 'Close ALL modes for everyone?') . '\')">' . csrf() . $hp . '<input type="hidden" name="a" value="modes_all"><input type="hidden" name="state" value="off"><button class="btn sm danger">' . L('Κλείσιμο ΟΛΩΝ', 'Close ALL') . '</button></form></div></section>';

  $txg = dc_kv('tx_all', '1') !== '0';
  echo '<section class="card"><h2>' . L('Εκπομπή, ελάχιστη έκδοση και μηνύματα', 'Transmit, minimum version and messages') . '</h2><form method="post" class="form">' . csrf() . $hp . '<input type="hidden" name="a" value="modes_note"><div class="g2">'
    . '<label>' . L('Εκπομπή (PTT) στα προγράμματα', 'Transmit (PTT) in the programs') . '<select name="tx_all"><option value="1"' . ($txg ? ' selected' : '') . '>' . L('Επιτρέπεται', 'Allowed') . '</option><option value="0"' . (!$txg ? ' selected' : '') . '>' . L('Μόνο ακρόαση (χωρίς εκπομπή)', 'Listen only (no transmit)') . '</option></select></label>'
    . '<label>' . L('Ελάχιστη έκδοση προγράμματος (κενό = καμία)', 'Minimum program version (empty = none)') . '<input name="min_version" value="' . h(dc_kv('min_version', '')) . '" placeholder="2.3.0" maxlength="14"></label>'
    . '<label>' . L('Μήνυμα για κλειστό mode (Ελληνικά)', 'Message for a closed mode (Greek)') . '<textarea name="modes_note_el" rows="2" placeholder="Αυτό το mode δεν είναι ακόμη διαθέσιμο.">' . h(dc_kv('modes_note_el', '')) . '</textarea></label>'
    . '<label>' . L('Μήνυμα για κλειστό mode (Αγγλικά)', 'Message for a closed mode (English)') . '<textarea name="modes_note_en" rows="2" placeholder="This mode is not available yet.">' . h(dc_kv('modes_note_en', '')) . '</textarea></label>'
    . '<label>' . L('Μήνυμα όταν δεν επιτρέπεται εκπομπή (Ελληνικά)', 'Message when transmit is off (Greek)') . '<textarea name="tx_note_el" rows="2">' . h(dc_kv('tx_note_el', '')) . '</textarea></label>'
    . '<label>' . L('Μήνυμα όταν δεν επιτρέπεται εκπομπή (Αγγλικά)', 'Message when transmit is off (English)') . '<textarea name="tx_note_en" rows="2">' . h(dc_kv('tx_note_en', '')) . '</textarea></label>'
    . '<label>' . L('Μήνυμα για παλιά έκδοση (Ελληνικά)', 'Message for an old version (Greek)') . '<textarea name="min_msg_el" rows="2">' . h(dc_kv('min_msg_el', '')) . '</textarea></label>'
    . '<label>' . L('Μήνυμα για παλιά έκδοση (Αγγλικά)', 'Message for an old version (English)') . '<textarea name="min_msg_en" rows="2">' . h(dc_kv('min_msg_en', '')) . '</textarea></label>'
    . '</div><div class="help">' . L('Όσες εγκαταστάσεις έχουν έκδοση μικρότερη από την ελάχιστη κλείνουν όλα τα modes και ζητούν ενημέρωση (το κουμπί ενημέρωσης μένει ενεργό). Αν αφήσεις τα μηνύματα κενά, το πρόγραμμα δείχνει ένα έτοιμο κείμενο.', 'Installations older than the minimum close every mode and ask for an update (the update button stays available). Empty messages use a ready-made text.') . '</div><button class="btn pri">' . L('Αποθήκευση', 'Save') . '</button></form></section>';

  // selected installations
  $fq = trim($_GET['q'] ?? ''); $w = ''; $args = [];
  if ($fq !== '') { $no = dc_no_filter($fq); $w = ' WHERE (id LIKE ? OR call LIKE ? OR note LIKE ? OR owner LIKE ? OR mail LIKE ? OR name LIKE ?' . ($no !== null ? ' OR rowid=' . $no : '') . ')'; $args = array_fill(0, 6, "%$fq%"); }
  $rows = dc_q('SELECT rowid AS rno, * FROM dc_installs' . $w . ' ORDER BY MAX(COALESCE(last_ping,0), COALESCE(last_seen,0)) DESC LIMIT 400', $args)->fetchAll();
  echo '<section class="card"><h2>' . L('Modes — σε επιλεγμένους', 'Modes — for selected installations') . ' <small>(' . count($rows) . ' / ' . $total . ' · ' . $tst . ' ' . L('δοκιμαστές', 'testers') . ')</small></h2>'
    . '<form class="filters" method="get"><input type="hidden" name="p" value="modes"><input name="q" value="' . h($fq) . '" placeholder="' . L('Αναζήτηση: call, όνομα, αριθμός DC-…, ID, email', 'Search: call, name, number DC-…, ID, email') . '"><button class="btn">' . L('Φίλτρο', 'Filter') . '</button></form>'
    . '<form method="post" class="form" id="mi">' . csrf() . $hp . '<input type="hidden" name="a" value="mode_inst">'
    . '<div class="mbar"><div><b>' . L('1. Ποια modes', '1. Which modes') . '</b><div class="mchk">';
  foreach (DC_MODES as $m) echo '<label class="chk"><input type="checkbox" name="modes[]" value="' . h($m) . '"> ' . h($m) . '</label>';
  echo '</div></div><div><b>' . L('2. Τι να γίνει', '2. What to do') . '</b><select name="act"><option value="-">' . L('— τίποτα στα modes —', '— nothing for modes —') . '</option><option value="on">' . L('Άνοιγμα (ενεργό)', 'Open (on)') . '</option><option value="off">' . L('Κλείσιμο', 'Close') . '</option><option value="reset">' . L('Επαναφορά στη γενική ρύθμιση', 'Back to the general setting') . '</option></select></div>'
    . '<div><b>' . L('Εκπομπή', 'Transmit') . '</b><select name="txset"><option value="-">—</option><option value="1">' . L('Επιτρέπεται', 'Allowed') . '</option><option value="0">' . L('Μόνο ακρόαση', 'Listen only') . '</option><option value="def">' . L('Όπως η γενική ρύθμιση', 'Like the general setting') . '</option></select></div>'
    . '<div><b>' . L('Δοκιμαστής', 'Tester') . '</b><select name="testerset"><option value="-">—</option><option value="1">' . L('Ναι (δοκιμαστής)', 'Yes (tester)') . '</option><option value="0">' . L('Όχι', 'No') . '</option></select></div>'
    . '<div style="align-self:end"><button class="btn pri">' . L('3. Εφαρμογή στους τσεκαρισμένους', '3. Apply to the ticked') . '</button></div></div>'
    . '<div class="tw"><table class="tbl"><tr><th><input type="checkbox" id="mall" title="' . h(L('Όλοι', 'All')) . '"></th><th>Call</th><th>' . L('Έκδοση', 'Version') . '</th>';
  foreach (DC_MODES as $m) echo '<th class="mh2">' . h($m) . '</th>';
  echo '<th>TX</th><th>' . L('Δοκιμ.', 'Tester') . '</th></tr>';
  foreach ($rows as $r) {
    $ov = dc_mode_ovr($r);
    echo '<tr><td><input type="checkbox" name="ids[]" value="' . h($r['id']) . '" class="mrow"></td><td><span class="mono muted">' . sprintf('DC-%05d', $r['rno']) . '</span> <b>' . h($r['call'] ?: substr($r['id'], 0, 8)) . '</b>' . ($r['name'] ? '<br><small class="muted">' . h($r['name']) . '</small>' : '') . '</td><td class="muted">' . h($r['version'] ?: '—') . '</td>';
    foreach (DC_MODES as $m) { $e = dc_mode_for($r, $m); echo '<td><span class="dot ' . ($e === 'on' ? 'on' : 'off') . '" title="' . h($m . ': ' . $MN[$e] . (isset($ov[$m]) ? ' (' . L('δική του ρύθμιση', 'own setting') . ')' : '')) . '"></span>' . (isset($ov[$m]) ? '<sup>*</sup>' : '') . '</td>'; }
    $tx = dc_tx_for($r);
    echo '<td>' . ($tx ? '<span class="pill ok">TX</span>' : '<span class="pill bad">RX</span>') . ($r['tx_ovr'] !== null && $r['tx_ovr'] !== '' ? '<sup>*</sup>' : '') . '</td><td>' . (!empty($r['tester']) ? '<span class="pill o">' . L('δοκιμαστής', 'tester') . '</span>' : '<span class="muted">—</span>') . '</td></tr>';
  }
  echo '</table></div><p class="muted">' . L('Πράσινη τελεία = το mode δουλεύει σε αυτή την εγκατάσταση, γκρι = κλειστό. Το αστεράκι * σημαίνει ότι η εγκατάσταση έχει δική της ρύθμιση που υπερισχύει της γενικής.', 'Green dot = the mode works on this installation, grey = closed. The star * means the installation has its own setting that overrides the general one.') . '</p></form>'
    . '<script>(function(){var a=document.getElementById("mall");if(a)a.addEventListener("change",function(){document.querySelectorAll(".mrow").forEach(function(c){c.checked=a.checked})})})();</script></section>';
}

/* ===================== PAYMENTS (same page as HAM Digi: who pays and how much; EUR and SEK are never added together) ===================== */
elseif ($p === 'payments') {
  $P = dc_pay_settings(); $ipn = dc_base_url() . 'ipn.php'; $chk = function ($b) { return $b ? ' checked' : ''; };
  $tot = dc_pay_totals(); $cur_order = array_merge(['EUR', 'SEK'], array_values(array_diff(array_keys($tot), ['EUR', 'SEK'])));
  $sym = ['EUR' => '€', 'SEK' => 'kr'];
  foreach ($cur_order as $c) {
    $t = $tot[$c];
    echo '<div class="kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))"><div class="kpi g"><span>' . L('Σύνολο', 'Total') . ' ' . h($c) . '</span><b>' . number_format($t['total'], 2) . ' ' . h($sym[$c] ?? $c) . '</b><small>' . $t['n'] . L(' πληρωμές', ' payments') . '</small></div>'
      . '<div class="kpi"><span>' . L('Αυτόν τον μήνα', 'This month') . ' · ' . h($c) . '</span><b>' . number_format($t['month'], 2) . ' ' . h($sym[$c] ?? $c) . '</b><small>' . gmdate('Y-m') . '</small></div>'
      . '<div class="kpi"><span>' . L('Φέτος', 'This year') . ' · ' . h($c) . '</span><b>' . number_format($t['year'], 2) . ' ' . h($sym[$c] ?? $c) . '</b><small>' . gmdate('Y') . '</small></div>'
      . '<div class="kpi"><span>' . L('Πληρωμές', 'Payments') . ' · ' . h($c) . '</span><b>' . $t['n'] . '</b><small>' . L('ολοκληρωμένες', 'completed') . '</small></div></div>';
  }
  $unact = (int)dc_one("SELECT COUNT(*) c FROM dc_payments WHERE status='Completed' AND (install IS NULL OR install='')")['c'];
  echo '<div class="kpis" style="grid-template-columns:repeat(3,minmax(0,1fr))"><div class="kpi o"><span>' . L('Χωρίς ενεργοποίηση', 'Not activated') . '</span><b>' . $unact . '</b><small>' . L('δες παρακάτω', 'see below') . '</small></div>'
    . '<div class="kpi"><span>' . L('Διαφορετικοί πληρωτές', 'Different payers') . '</span><b>' . (int)dc_one("SELECT COUNT(DISTINCT COALESCE(NULLIF(install,''), payer_email)) c FROM dc_payments WHERE status='Completed'")['c'] . '</b><small>' . L('εγκαταστάσεις ή email', 'installations or e-mails') . '</small></div>'
    . '<div class="kpi"><span>' . L('Τελευταία πληρωμή', 'Last payment') . '</span><b style="font-size:20px">' . (($lp = dc_one("SELECT t FROM dc_payments WHERE status='Completed' ORDER BY t DESC LIMIT 1")) ? gmdate('Y-m-d', (int)$lp['t']) : '—') . '</b><small></small></div></div>';

  // who pays: one line per installation (or per e-mail when the payment has no installation yet), each currency in its own column
  $who = []; 
  foreach (dc_q("SELECT install, payer_email, payer_name, currency, amount, t FROM dc_payments WHERE status='Completed'")->fetchAll() as $x) {
    $k = $x['install'] ?: ('mail:' . strtolower($x['payer_email'] ?: $x['payer_name']));
    if (!isset($who[$k])) $who[$k] = ['install' => $x['install'], 'name' => $x['payer_name'], 'email' => $x['payer_email'], 'n' => 0, 'last' => 0, 'cur' => []];
    $who[$k]['n']++; $who[$k]['last'] = max($who[$k]['last'], (int)$x['t']); if (!$who[$k]['name']) $who[$k]['name'] = $x['payer_name'];
    $cc = strtoupper($x['currency']) ?: '?'; $who[$k]['cur'][$cc] = ($who[$k]['cur'][$cc] ?? 0) + (float)$x['amount'];
  }
  uasort($who, function ($a, $b) { return $b['last'] <=> $a['last']; });
  echo '<section class="card"><h2>' . L('Ποιος πληρώνει και πόσα', 'Who pays and how much') . ' <small>(' . count($who) . ')</small></h2><div class="tw"><table class="tbl"><tr><th>' . L('Πληρωτής', 'Payer') . '</th><th>' . L('Εγκατάσταση', 'Installation') . '</th><th>' . L('Πληρωμές', 'Payments') . '</th>';
  foreach ($cur_order as $c) echo '<th>' . h($c) . '</th>';
  echo '<th>' . L('Τελευταία', 'Last') . '</th></tr>';
  if (!$who) echo '<tr><td colspan="' . (4 + count($cur_order)) . '" class="muted">' . L('Καμία πληρωμή ακόμη.', 'No payments yet.') . '</td></tr>';
  foreach ($who as $w) {
    $ins = $w['install'] ? dc_one('SELECT rowid AS rno, * FROM dc_installs WHERE id=?', [$w['install']]) : null;
    echo '<tr><td><b>' . h($w['name'] ?: '—') . '</b><br><small class="muted">' . h($w['email']) . '</small></td><td>' . ($ins ? '<a href="?p=installs&q=' . sprintf('DC-%05d', $ins['rno']) . '"><b class="mono">' . sprintf('DC-%05d', $ins['rno']) . '</b></a> ' . h($ins['call']) : '<span class="muted">' . L('χωρίς εγκατάσταση', 'no installation') . '</span>') . '</td><td>' . $w['n'] . '</td>';
    foreach ($cur_order as $c) echo '<td>' . (isset($w['cur'][$c]) ? '<b>' . number_format($w['cur'][$c], 2) . '</b> ' . h($sym[$c] ?? $c) : '<span class="muted">—</span>') . '</td>';
    echo '<td class="muted">' . gmdate('Y-m-d', $w['last']) . '</td></tr>';
  }
  echo '</table></div></section>';

  // list
  echo '<section class="card"><h2>' . L('Πληρωμές', 'Payments') . '</h2><div class="tw"><table class="tbl"><tr><th>' . L('Ώρα', 'Time') . '</th><th>' . L('Ποσό', 'Amount') . '</th><th>' . L('Από', 'From') . '</th><th>' . L('Σημείωση', 'Note') . '</th><th>' . L('Εγκατάσταση / κωδικός', 'Installation / code') . '</th></tr>';
  $rows = dc_q('SELECT * FROM dc_payments ORDER BY t DESC LIMIT 300')->fetchAll(); if (!$rows) echo '<tr><td colspan="5" class="muted">' . L('Καμία πληρωμή ακόμη.', 'No payments yet.') . '</td></tr>';
  foreach ($rows as $x) {
    $st = $x['status'] === 'Completed' ? '' : ' <span class="pill ' . (in_array($x['status'], ['Refunded', 'Reversed'], true) ? 'bad' : 'o') . '">' . h($x['status']) . '</span>';
    list($guess) = $x['install'] ? [null] : dc_pay_match(['custom' => $x['custom'], 'memo' => $x['memo'], 'payer_email' => $x['payer_email']]);
    if ($x['install']) $act = '<a href="?p=installs&q=' . urlencode(dc_inst_no($x['install'])) . '"><b>' . h(dc_inst_no($x['install'])) . '</b></a> <span class="mono">' . h($x['code']) . '</span><br><small class="muted">' . h($x['matched_by']) . '</small>';
    elseif ($x['status'] === 'Ignored') $act = '<form method="post" class="licf">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="pay_restore"><input type="hidden" name="pid" value="' . $x['id'] . '"><button class="btn sm">' . L('Επαναφορά', 'Restore') . '</button></form>';
    else $act = '<form method="post" class="licf">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="pay_assign"><input type="hidden" name="pid" value="' . $x['id'] . '"><input name="to" placeholder="DC-00012" value="' . h($guess ? dc_inst_no($guess) : '') . '" style="width:120px"><button class="btn sm pri">' . L('Ενεργοποίηση', 'Activate') . '</button></form>'
      . ($x['status'] === 'Completed' ? '<form method="post" style="margin-top:4px" onsubmit="return confirm(\'' . L('Να αγνοηθεί αυτή η πληρωμή; Δεν θα μετράει στα σύνολα.', 'Ignore this payment? It will not count in the totals.') . '\')">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="pay_ignore"><input type="hidden" name="pid" value="' . $x['id'] . '"><button class="btn sm">' . L('Αγνόηση', 'Ignore') . '</button></form>' : '');
    echo '<tr><td>' . dc_dt($x['t']) . '<br><small class="mono muted">' . h($x['txn']) . '</small></td><td><b>' . h(number_format((float)$x['amount'], 2) . ' ' . $x['currency']) . '</b>' . $st . '</td><td>' . h($x['payer_name']) . '<br><small class="muted">' . h($x['payer_email']) . '</small></td><td><small>' . h($x['memo']) . '</small>'
      . '<form method="post" class="licf" style="margin-top:4px">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="pay_note"><input type="hidden" name="pid" value="' . $x['id'] . '"><input name="note" value="' . h($x['note']) . '" placeholder="' . L('δική σου σημείωση', 'your note') . '" style="width:150px"><button class="btn sm">✓</button></form></td><td>' . $act . '</td></tr>';
  }
  echo '</table></div></section>';

  // per month, every currency in its own column
  $mon = [];
  foreach (dc_q("SELECT strftime('%Y-%m', t, 'unixepoch') m, currency c, SUM(amount) s, COUNT(*) n FROM dc_payments WHERE status='Completed' GROUP BY m, c ORDER BY m DESC")->fetchAll() as $x) { $c = strtoupper($x['c']) ?: '?'; $mon[$x['m']][$c] = [(float)$x['s'], (int)$x['n']]; }
  echo '<div class="grid2"><section class="card"><h2>' . L('Ανά μήνα', 'Per month') . '</h2><table class="tbl"><tr><th>' . L('Μήνας', 'Month') . '</th>';
  foreach ($cur_order as $c) echo '<th>' . h($c) . '</th>';
  echo '</tr>';
  foreach (array_slice($mon, 0, 24, true) as $m => $by) { echo '<tr><td>' . h($m) . '</td>'; foreach ($cur_order as $c) echo '<td>' . (isset($by[$c]) ? '<b>' . number_format($by[$c][0], 2) . '</b> ' . h($sym[$c] ?? $c) . ' <small class="muted">(' . $by[$c][1] . ')</small>' : '<span class="muted">—</span>') . '</td>'; echo '</tr>'; }
  if (!$mon) echo '<tr><td colspan="' . (1 + count($cur_order)) . '" class="muted">—</td></tr>';
  echo '</table></section><section class="card"><h2>' . L('Καταχώρηση πληρωμής με το χέρι', 'Record a payment by hand') . '</h2><form method="post" class="form">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="pay_add"><div class="g2">'
    . '<label>' . L('Ποσό', 'Amount') . '<input name="amount" placeholder="5.00"></label><label>' . L('Νόμισμα', 'Currency') . '<input name="currency" value="EUR" list="curl"><datalist id="curl"><option value="EUR"><option value="SEK"></datalist></label><label>' . L('Όνομα', 'Name') . '<input name="name"></label><label>Email<input name="email" type="email"></label>'
    . '<label>' . L('Σημείωση (π.χ. τράπεζα, Swish)', 'Note (e.g. bank, Swish)') . '<input name="memo"></label><label>' . L('Ενεργοποίηση εγκατάστασης (προαιρετικό)', 'Activate installation (optional)') . '<input name="to" placeholder="DC-00012"></label></div><button class="btn pri">' . L('Καταχώρηση', 'Record') . '</button></form></section></div>';
  // settings
  echo '<section class="card"><h2>' . L('PayPal και αυτόματη ενεργοποίηση', 'PayPal and automatic activation') . '</h2><div class="help">' . L(
    '<b>Ο λογαριασμός PayPal είναι κοινός με το HAM Digi και το PayPal δέχεται ΜΙΑ διεύθυνση IPN.</b> Γι’ αυτό το HAM Digi (ipn.php) προωθεί ένα αντίγραφο κάθε πληρωμής εδώ: <b class="mono">' . h($ipn) . '</b> (το απόσπασμα είναι στο ΔΙΑΒΑΣΕ-ΜΕ.txt). Το DigiConnect ξαναρωτά το PayPal ότι είναι γνήσια.<br>Αν βρεθεί η εγκατάσταση (αριθμός DC-… στη σημείωση, το email της εγγραφής ή το διακριτικό στη σημείωση), ενεργοποιείται αμέσως — το πρόγραμμα το βλέπει στον επόμενο έλεγχο. Αλλιώς η πληρωμή περιμένει εδώ και πατάς «Ενεργοποίηση». Πληρωμές με αριθμό HD-… (HAM Digi) αγνοούνται.',
    '<b>The PayPal account is shared with HAM Digi and PayPal accepts ONE IPN address.</b> So HAM Digi (ipn.php) forwards a copy of every payment here: <b class="mono">' . h($ipn) . '</b> (the snippet is in ΔΙΑΒΑΣΕ-ΜΕ.txt). DigiConnect asks PayPal again that it is genuine.<br>If the installation is found (DC-… number in the note, the registration e-mail or the callsign in the note) it is activated at once — the program sees it at its next check. Otherwise the payment waits here and you press “Activate”. Payments carrying an HD-… number (HAM Digi) are ignored.') . '</div>'
    . '<form method="post" class="form">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="pay_settings"><div class="g2">'
    . '<label class="chk"><input type="checkbox" name="auto" value="1"' . $chk($P['auto']) . '> ' . L('Αυτόματη ενεργοποίηση μετά την πληρωμή', 'Activate automatically after payment') . '</label>'
    . '<label class="chk"><input type="checkbox" name="skip_hd" value="1"' . $chk($P['skip_hd']) . '> ' . L('Αγνόησε πληρωμές με αριθμό HD-… (είναι του HAM Digi)', 'Ignore payments with an HD-… number (they belong to HAM Digi)') . '</label>'
    . '<label>' . L('Ελάχιστο ποσό για αυτόματη ενεργοποίηση (0 = κάθε ποσό)', 'Minimum amount for automatic activation (0 = any amount)') . '<input name="min" value="' . h(dc_kv('pay_min', '0')) . '"></label>'
    . '<label>' . L('Το email του PayPal σου (έλεγχος ότι η πληρωμή ήρθε σε σένα — προαιρετικό)', 'Your PayPal e-mail (checks the payment came to you — optional)') . '<input name="receiver" type="email" value="' . h($P['receiver']) . '"></label>'
    . '<label class="chk"><input type="checkbox" name="sandbox" value="1"' . $chk($P['sandbox']) . '> ' . L('PayPal Sandbox (μόνο για δοκιμές)', 'PayPal Sandbox (tests only)') . '</label>'
    . '</div><button class="btn pri">' . L('Αποθήκευση', 'Save') . '</button></form></section>';
  echo '<section class="card"><h2>E-mail</h2><div class="help">' . L('Ο server δεν στέλνει email αν δεν το ενεργοποιήσεις εδώ. Με ενεργή αποστολή: ο πληρωτής παίρνει τον κωδικό ενεργοποίησης και εσύ ειδοποιήσεις για νέες πληρωμές.', 'This server sends no e-mail unless you switch it on here. When on: the payer gets the activation code and you get alerts about new payments.') . '</div>'
    . '<form method="post" class="form">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="mail_settings"><div class="g2">'
    . '<label class="chk"><input type="checkbox" name="mail_on" value="1"' . $chk(dc_kv('mail_on', '0') === '1') . '> ' . L('Ενεργή αποστολή email από αυτόν τον server', 'Sending e-mail from this server is on') . '</label>'
    . '<label class="chk"><input type="checkbox" name="alert_mail" value="1"' . $chk(dc_kv('alert_mail', '1') === '1') . '> ' . L('Στείλε μου email για νέες πληρωμές', 'E-mail me about new payments') . '</label>'
    . '<label>' . L('Το email σου (διαχειριστή)', 'Your (admin) e-mail') . '<input name="admin_mail" type="email" value="' . h(dc_kv('admin_mail', '')) . '"></label>'
    . '<label>' . L('Διεύθυνση αποστολέα (προαιρετικό)', 'Sender address (optional)') . '<input name="mail_from" type="email" value="' . h(dc_kv('mail_from', '')) . '"></label></div>'
    . '<button class="btn pri">' . L('Αποθήκευση', 'Save') . '</button></form>'
    . '<form method="post" style="margin-top:8px">' . csrf() . '<input type="hidden" name="p" value="payments"><input type="hidden" name="a" value="mail_test"><button class="btn sm">' . L('Δοκιμαστικό email', 'Send a test e-mail') . '</button></form></section>';
}

/* ===================== SERVERS / HOST LISTS ===================== */
elseif ($p === 'servers') {
  require_once __DIR__ . '/../hosts/functions.php';
  $SOURCES = require __DIR__ . '/../hosts/sources.php';
  $pubDir = realpath(__DIR__ . '/../hosts/pub') ?: (__DIR__ . '/../hosts/pub');
  $dataDir = dirname(dc_cfg()['db']) . '/hosts';
  $last = dc_kv('hostsync_last', '—');
  $chk = function (string $d) { return is_dir($d) ? (is_writable($d) ? '<span class="pill ok">' . L('εγγράψιμο','writable') . '</span>' : '<span class="pill bad">' . L('ΜΗ εγγράψιμο','NOT writable') . '</span>') : '<span class="pill bad">' . L('δεν υπάρχει','missing') . '</span>'; };
  echo '<section class="card"><h2>' . L('Αυτόματη ανανέωση λιστών','Automatic host-list sync') . '</h2>'
    . '<p class="muted">' . L('Πλήρεις λίστες server για όλα τα modes, με τους HELLAS Zone reflectors σου πρώτους. Τελευταία ανανέωση: ','Full server lists for every mode, your HELLAS Zone reflectors first. Last sync: ') . h($last) . '</p>'
    . '<p class="help">' . L('Έλεγχος συστήματος: ','System check: ') . '<span class="mono">hosts/pub</span> ' . $chk(__DIR__ . '/../hosts/pub') . ' · <span class="mono">data/hosts</span> ' . $chk($dataDir)
    . ' · cURL ' . (function_exists('curl_init') ? '<span class="pill ok">OK</span>' : '<span class="pill bad">' . L('λείπει','missing') . '</span>')
    . ' · allow_url_fopen ' . (ini_get('allow_url_fopen') ? '<span class="pill ok">OK</span>' : '<span class="pill o">off</span>') . '</p>'
    . '<form method="post" style="margin:10px 0">' . csrf() . '<input type="hidden" name="p" value="servers"><button class="btn pri" name="a" value="hosts_refresh">↻ ' . L('Ανανέωση τώρα','Refresh now') . '</button></form>'
    . '<p class="help">' . L('Για συνεχή αυτόματη ανανέωση, βάλε στο cron: ','For continuous auto-update, add to cron: ') . '<span class="mono">*/30 * * * * php ' . h(realpath(__DIR__ . '/../hosts/refresh.php') ?: '.../hosts/refresh.php') . '</span></p></section>';
  echo '<section class="card"><h2>' . L('Λίστες ανά mode','Lists per mode') . '</h2><div class="tw"><table class="tbl"><tr><th>' . L('Αρχείο','File') . '</th><th>' . L('Mode','Mode') . '</th><th>' . L('Γραμμές','Lines') . '</th><th>' . L('Κατάσταση','Status') . '</th><th>URL</th></tr>';
  $modeName = ['DMRHosts.txt'=>'DMR','YSFHosts.txt'=>'YSF/C4FM','FCSHosts.txt'=>'FCS','P25Hosts.txt'=>'P25','NXDNHosts.txt'=>'NXDN','M17Hosts.txt'=>'M17','ASLHosts.txt'=>'AllStar','dplus.txt'=>'D-Star REF','dextra.txt'=>'D-Star XRF','dcs.txt'=>'D-Star DCS','DMRIDs.dat'=>'DMR IDs'];
  foreach ($SOURCES as $file => $urls) {
    $pp = hosts_find($file); $lines = $pp ? hosts_count_lines($pp) : 0;
    $okInfo = dc_kv("hostsync_ok_$file", ''); $errInfo = dc_kv("hostsync_err_$file", '');
    $viaPub = $pp && strpos(str_replace('\\', '/', $pp), '/hosts/pub/') !== false;
    $status = $lines > 0 ? '<span class="pill ok">' . L('ΟΚ','OK') . '</span>' : '<span class="pill bad">' . L('κενό','empty') . '</span>';
    if ($errInfo) $status .= ' <span class="pill o">' . ($lines > 0 ? L('προειδοποίηση','warning') : L('σφάλμα','error')) . '</span><br><span class="muted" style="font-size:11px;word-break:break-word">' . h($errInfo) . '</span>';
    if ($lines === 0) $okInfo = '';
    $link = $pp ? ($viaPub ? '../hosts/pub/' . rawurlencode($file) : '../hosts/get.php?f=' . rawurlencode($file)) : '';
    echo '<tr><td class="mono">' . h($file) . '</td><td>' . h($modeName[$file] ?? '—') . '</td><td>' . ($lines ? number_format($lines) : '—') . '</td><td>' . $status . ($okInfo ? '<br><span class="muted" style="font-size:11px">' . h($okInfo) . '</span>' : '') . '</td>'
       . '<td>' . ($link ? '<a href="' . h($link) . '" target="_blank" class="mono" style="font-size:11px">' . h(ltrim(substr($link, 3), '/')) . '</a>' : '<span class="muted">—</span>') . '</td></tr>';
  }
  echo '</table></div></section>';
  echo '<section class="card"><h2>' . L('Οι δικοί σου reflectors','Your own reflectors') . '</h2><p class="muted">' . L('Μπαίνουν πρώτοι σε κάθε λίστα. Βρίσκονται στο ','They are prepended to each list. Edit them in ') . '<span class="mono">digiconnect/hosts/custom/&lt;file&gt;</span></p></section>';
}

/* ===================== MESSAGES ===================== */
elseif ($p === 'messages') {
  echo '<section class="card"><h2>' . L('Νέο μήνυμα', 'New message') . '</h2><form method="post" class="form">' . csrf() . '<input type="hidden" name="p" value="messages"><input type="hidden" name="a" value="msg_new"><div class="g2">'
    . '<label>' . L('Προς (κενό = όλοι, ή αριθμός DC-…)', 'To (empty = everyone, or a DC-… number)') . '<input name="target" placeholder="' . L('όλοι', 'everyone') . '"></label><label>' . L('Εμφανίζεται για (ημέρες, 0 = πάντα)', 'Shown for (days, 0 = always)') . '<input name="days" type="number" min="0" value="30"></label>'
    . '<label>' . L('Τίτλος (Ελληνικά)', 'Title (Greek)') . '<input name="title_el" maxlength="200"></label><label>' . L('Τίτλος (Αγγλικά)', 'Title (English)') . '<input name="title_en" maxlength="200"></label>'
    . '<label>' . L('Κείμενο (Ελληνικά)', 'Text (Greek)') . '<textarea name="body_el" rows="5"></textarea></label><label>' . L('Κείμενο (Αγγλικά)', 'Text (English)') . '<textarea name="body_en" rows="5"></textarea></label>'
    . '<label style="grid-column:1/-1">' . L('Σύνδεσμος (προαιρετικό, https://…)', 'Link (optional, https://…)') . '<input name="link"></label></div>'
    . '<div class="help">' . L('Ο server προσφέρει το μήνυμα σε κάθε έλεγχο (όλοι ή μία εγκατάσταση). Προσοχή: το πρόγραμμα DigiConnect δεν το εμφανίζει ακόμη — χρειάζεται αλλαγή στο πρόγραμμα.', 'The server offers the message at every check (everyone or one installation). Note: the DigiConnect program does not show it yet — that needs a change in the program.') . '</div><button class="btn pri">' . L('Αποστολή', 'Send') . '</button></form></section>';
  echo '<section class="card"><h2>' . L('Μηνύματα', 'Messages') . '</h2><div class="tw"><table class="tbl"><tr><th>' . L('Ώρα', 'Time') . '</th><th>' . L('Προς', 'To') . '</th><th>' . L('Μήνυμα', 'Message') . '</th><th>' . L('Κατάσταση', 'State') . '</th><th></th></tr>';
  foreach (dc_q('SELECT * FROM dc_messages ORDER BY t DESC LIMIT 200')->fetchAll() as $m) {
    $live = $m['active'] && (!(int)$m['until'] || (int)$m['until'] > time()); $ttl = $m['title_el'] ?: ($m['title_en'] ?: $m['title']); $bd = $m['body_el'] ?: ($m['body_en'] ?: $m['body']);
    echo '<tr><td>' . dc_dt($m['t']) . '</td><td>' . ($m['target'] ? '<a href="?p=installs&q=' . urlencode(dc_inst_no($m['target'])) . '">' . h(dc_inst_no($m['target']) ?: $m['target']) . '</a>' : L('όλοι', 'everyone')) . '</td><td><b>' . h($ttl) . '</b><br><small>' . nl2br(h(mb_substr((string)$bd, 0, 300))) . '</small></td><td>' . ($live ? '<span class="pill ok">' . L('ενεργό', 'active') . '</span>' . ((int)$m['until'] ? '<br><small class="muted">' . L('έως ', 'until ') . dc_dt($m['until']) . '</small>' : '') : '<span class="pill">' . L('τέλος', 'ended') . '</span>') . '</td><td>'
      . ($live ? '<form method="post" style="display:inline">' . csrf() . '<input type="hidden" name="p" value="messages"><input type="hidden" name="a" value="msg_off"><input type="hidden" name="mid" value="' . (int)$m['id'] . '"><button class="btn sm">' . L('Σταμάτημα', 'Stop') . '</button></form> ' : '')
      . '<form method="post" style="display:inline" onsubmit="return confirm(\'' . L('Διαγραφή;', 'Delete?') . '\')">' . csrf() . '<input type="hidden" name="p" value="messages"><input type="hidden" name="a" value="msg_del"><input type="hidden" name="mid" value="' . (int)$m['id'] . '"><button class="btn sm danger">' . L('Διαγραφή', 'Delete') . '</button></form></td></tr>';
  }
  echo '</table></div></section>';
}

/* ===================== DEMO ===================== */
elseif ($p === 'demos') {
  $now = time(); $IDLE = 86400;   // a running demo that shows no sign of life for 24 h = probably stopped
  $f = ['s' => $_GET['s'] ?? 'all', 'q' => trim($_GET['q'] ?? '')];
  if (!in_array($f['s'], ['all', 'run', 'soon', 'stopped', 'exp', 'rep'], true)) $f['s'] = 'all';
  $seenC = 'MAX(COALESCE(i.last_ping,0), COALESCE(i.last_seen,0))';
  // "the same person again": another demo installation with the same e-mail, callsign or DMR ID
  $repW = "EXISTS (SELECT 1 FROM dc_installs o WHERE o.id<>i.id AND o.state='demo' AND ((COALESCE(i.mail,'')<>'' AND lower(o.mail)=lower(i.mail)) OR (COALESCE(i.call,'')<>'' AND upper(o.call)=upper(i.call)) OR (COALESCE(i.dmr_id,'')<>'' AND o.dmr_id=i.dmr_id)))";
  $runW = "(COALESCE(i.demo_until,0)=0 OR i.demo_until>$now)";
  $cnt = function ($w) { return (int)dc_scalar("SELECT COUNT(*) FROM dc_installs i WHERE i.state='demo'" . ($w ? " AND $w" : '')); };
  $nRun = $cnt($runW); $nSoon = $cnt("i.demo_until>$now AND i.demo_until<=" . ($now + 86400)); $nStop = $cnt("$runW AND $seenC<" . ($now - $IDLE));
  $nExp = $cnt("i.demo_until>0 AND i.demo_until<=$now"); $nRep = $cnt($repW);
  $kp = function ($label, $val, $sub, $cls = '') { return "<div class='kpi $cls'><span>$label</span><b>$val</b><small>$sub</small></div>"; };
  echo '<div class="kpis" style="grid-template-columns:repeat(auto-fit,minmax(168px,1fr))">'
    . $kp(L('Τρέχουν τώρα','Running now','Pågår nu'), $nRun, L('demo που δεν έχουν λήξει','demos that have not ended','demo som inte har gått ut'), 'g')
    . $kp(L('Λήγουν σε 24 ώρες','Ending within 24 h','Slutar inom 24 h'), $nSoon, L('σύντομα χωρίς άδεια','soon without a licence','snart utan licens'), $nSoon ? 'o' : '')
    . $kp(L('Σταμάτησαν να το χρησιμοποιούν','Stopped using it','Slutade använda'), $nStop, L('τρέχει demo αλλά καμία δραστηριότητα 24+ ώρες','demo running but no activity for 24 h+','demo pågår men ingen aktivitet på 24 h+'), $nStop ? 'r' : '')
    . $kp(L('Έληξαν','Ended','Slut'), $nExp, L('ο χρόνος τους τελείωσε','their time is over','tiden är slut'))
    . $kp(L('Επαναλαμβανόμενα','Repeated','Upprepade'), $nRep, L('ίδιο email, call ή DMR ID σε περισσότερα demo','same e-mail, callsign or DMR ID in more demos','samma e-post, signal eller DMR-ID i flera demo'), $nRep ? 'r' : '') . '</div>';
  $w = ["i.state='demo'"]; $a = [];
  if ($f['s'] === 'run') $w[] = $runW; elseif ($f['s'] === 'soon') $w[] = "i.demo_until>$now AND i.demo_until<=" . ($now + 86400);
  elseif ($f['s'] === 'stopped') $w[] = "$runW AND $seenC<" . ($now - $IDLE); elseif ($f['s'] === 'exp') $w[] = "i.demo_until>0 AND i.demo_until<=$now"; elseif ($f['s'] === 'rep') $w[] = $repW;
  if ($f['q'] !== '') {
    $no = dc_no_filter($f['q']); $like = '%' . $f['q'] . '%';
    $cols = ['i.id', 'i.call', 'i.name', 'i.mail', 'i.dmr_id', 'i.ip', 'i.note'];
    $w[] = '(' . ($no !== null ? 'i.rowid=? OR ' : '') . implode(' OR ', array_map(function ($c) { return "$c LIKE ?"; }, $cols)) . ')';
    if ($no !== null) $a[] = $no; foreach ($cols as $c) $a[] = $like;
  }
  $where = ' WHERE ' . implode(' AND ', $w);
  $total = (int)dc_scalar('SELECT COUNT(*) FROM dc_installs i' . $where, $a); $pg = max(1, (int)($_GET['pg'] ?? 1)); $per = 50; $off = ($pg - 1) * $per;
  $opt = function ($v, $t) use ($f) { return '<option value="' . $v . '"' . ($f['s'] === $v ? ' selected' : '') . '>' . $t . '</option>'; };
  echo '<section class="card"><form class="filters" method="get"><input type="hidden" name="p" value="demos"><select name="s">'
    . $opt('all', L('Όλα τα demo','All demos','Alla demo')) . $opt('run', L('Τρέχουν τώρα','Running now','Pågår nu')) . $opt('soon', L('Λήγουν σε 24 ώρες','Ending within 24 h','Slutar inom 24 h')) . $opt('stopped', L('Σταμάτησαν να το χρησιμοποιούν','Stopped using it','Slutade använda'))
    . $opt('exp', L('Έληξαν','Ended','Slut')) . $opt('rep', L('Επαναλαμβανόμενα','Repeated','Upprepade')) . '</select>'
    . '<input name="q" value="' . h($f['q']) . '" placeholder="' . L('Αναζήτηση: DC-…, call, όνομα, email, IP, σημείωση','Search: DC-…, call, name, e-mail, IP, note','Sök: DC-…, signal, namn, e-post, IP, anteckning') . '"><button class="btn">' . L('Φίλτρο','Filter','Filter') . '</button><span class="spacer"></span><span class="muted">' . $total . L(' demo',' demos',' demo') . '</span></form>';
  $rows = dc_q("SELECT i.rowid AS rno, i.*,
      (SELECT COUNT(*) FROM dc_events e WHERE e.kind='dl_pkg' AND e.detail LIKE i.id || '|%') AS dl_upd,
      (SELECT COUNT(*) FROM dc_webdl w WHERE (w.call<>'' AND upper(w.call)=upper(i.call)) OR (w.email<>'' AND lower(w.email)=lower(i.mail))) AS dl_web,
      (SELECT COUNT(*) FROM dc_daily dd WHERE dd.id=i.id) AS days
    FROM dc_installs i" . $where . " ORDER BY (CASE WHEN i.demo_until>0 AND i.demo_until<=$now THEN 1 ELSE 0 END), (CASE WHEN i.demo_until>$now THEN i.demo_until END) ASC, i.demo_until DESC LIMIT $per OFFSET $off", $a)->fetchAll();
  $osn = function ($o, $a = '') { $n = ['windows' => 'Windows', 'macos' => 'macOS', 'linux' => 'Linux'][$o] ?? $o; return trim($n . ' ' . $a); };
  echo '<div class="tw"><table class="tbl demot"><tr><th>' . L('Αρ. εγκατάστασης','Installation no.','Install.nr') . '</th><th>Call</th><th>' . L('Κατάσταση','Status','Status') . '</th><th>' . L('Αντίστροφη μέτρηση','Countdown','Nedräkning') . '</th><th>' . L('Ξεκίνησε','Started','Startade') . '</th><th>' . L('Λήγει','Ends','Slutar') . '</th>'
    . '<th>' . L('Λήψεις','Downloads','Nedladdningar') . '</th><th>' . L('Ημέρες χρήσης','Days in use','Dagar i bruk') . '</th><th>' . L('Τελευταία δραστηριότητα','Last activity','Senaste aktivitet') . '</th><th>' . L('Ίδιος χρήστης','Same user','Samma användare') . '</th><th>' . L('Σύστημα','System','System') . '</th></tr>';
  foreach ($rows as $r) {
    $start = (int)($r['lic_set'] ?: $r['first_seen']); $end = (int)$r['demo_until']; $last = max((int)$r['last_ping'], (int)$r['last_seen']);
    $ended = $end > 0 && $end <= $now; $live = $last >= $now - 900; $idle = !$ended && $last < $now - $IDLE;
    if ($ended) $st = '<span class="pill dim">' . L('Έληξε','Ended','Slut') . '</span>';
    elseif ($live) $st = '<span class="pill ok onl"><i></i>' . L('Σε χρήση τώρα','In use now','Används nu') . '</span>';
    elseif ($idle) $st = '<span class="pill bad">' . L('Σταμάτησε;','Stopped?','Slutat?') . '</span>';
    else $st = '<span class="pill o">' . L('Τρέχει','Running','Pågår') . '</span>';
    $others = dc_q("SELECT o.rowid AS rno, o.id, o.lic_set FROM dc_installs o WHERE o.id<>? AND o.state='demo' AND ((COALESCE(?,'')<>'' AND lower(o.mail)=lower(?)) OR (COALESCE(?,'')<>'' AND upper(o.call)=upper(?)) OR (COALESCE(?,'')<>'' AND o.dmr_id=?)) ORDER BY o.lic_set LIMIT 8",
      [$r['id'], $r['mail'], $r['mail'], $r['call'], $r['call'], $r['dmr_id'], $r['dmr_id']])->fetchAll();
    $pct = ($end > $start) ? max(0, min(100, round(($now - $start) / ($end - $start) * 100))) : ($ended ? 100 : 0);
    $left = $end > 0 ? max(0, $end - $now) : 0;
    $cd = $end > 0
      ? '<div class="cd" data-s="' . $start . '" data-e="' . $end . '"><b class="cd-t">' . ($ended ? L('έληξε','ended','slut') : (intdiv($left, 86400) ? intdiv($left, 86400) . ' ' . L('ημ.','d','d') . ' ' : '') . gmdate('H:i:s', $left % 86400)) . '</b><div class="prog"><i style="width:' . $pct . '%"></i></div><small class="muted cd-p">' . $pct . '%</small></div>'
      : '<span class="muted">' . L('χωρίς λήξη','no end','inget slut') . '</span>';
    $rep = '';
    foreach ($others as $o) $rep .= '<a class="mono" href="?p=installs&q=' . sprintf('DC-%05d', $o['rno']) . '" title="' . h(dc_dt((int)$o['lic_set'])) . '">' . h(sprintf('DC-%05d', $o['rno'])) . '</a> ';
    $call = $r['call'];
    echo '<tr><td class="mono" style="white-space:nowrap"><a href="?p=installs&q=' . sprintf('DC-%05d', $r['rno']) . '"><b>' . sprintf('DC-%05d', $r['rno']) . '</b></a></td>'
      . '<td><a href="?p=installs&q=' . sprintf('DC-%05d', $r['rno']) . '"><b>' . h($call ?: substr($r['id'], 0, 8)) . '</b></a>' . ($r['name'] || $r['mail'] ? '<br><small>' . h($r['name']) . '</small><br><small class="muted">' . h($r['mail']) . '</small>' : '') . ($r['ip'] ? '<br><small class="mono muted">' . h($r['ip']) . '</small>' : '') . '</td>'
      . '<td>' . $st . ($others ? '<br><span class="pill bad" style="margin-top:4px">↻ ' . L('Επανάληψη demo','Repeated demo','Upprepad demo') . ' ×' . (count($others) + 1) . '</span>' : '') . '</td>'
      . '<td style="min-width:150px">' . $cd . '</td><td style="white-space:nowrap">' . dc_dt($start) . '</td><td style="white-space:nowrap">' . ($end ? dc_dt($end) : '—') . '</td>'
      . '<td style="white-space:nowrap" title="' . h(L('σελίδα · αυτόματες ενημερώσεις','website · automatic updates','webbplats · automatiska uppdateringar')) . '"><b>' . (int)$r['dl_web'] . '</b> · ' . (int)$r['dl_upd'] . '</td>'
      . '<td>' . (int)$r['days'] . '</td><td style="white-space:nowrap">' . ($last ? dc_dt($last) . '<br><small class="' . ($idle ? 'bad' : 'muted') . '">' . h(ago($last)) . '</small>' : '—') . '</td>'
      . '<td>' . ($rep !== '' ? $rep : '<span class="muted">—</span>') . '</td><td><small>' . h($osn($r['os'], $r['arch'])) . '<br>v' . h($r['version']) . '</small></td></tr>';
  }
  if (!$rows) echo '<tr><td colspan="11" class="muted" style="text-align:center;padding:22px">' . L('Κανένα demo με αυτά τα κριτήρια.','No demo matches these filters.','Inget demo matchar filtret.') . '</td></tr>';
  $pages = max(1, (int)ceil($total / $per)); $pgr = '';
  if ($pages > 1) { $pgr = '<div class="filters" style="justify-content:center;margin-top:10px">'; for ($i = 1; $i <= $pages; $i++) $pgr .= '<a class="btn sm' . ($i === $pg ? ' pri' : '') . '" href="?p=demos&s=' . urlencode($f['s']) . '&q=' . urlencode($f['q']) . '&pg=' . $i . '">' . $i . '</a>'; $pgr .= '</div>'; }
  echo '</table></div>' . $pgr
    . '<p class="help">' . L('Το ρολόι μετράει από τη στιγμή που ξεκίνησε το demo (πρώτη επαφή της εγκατάστασης με τον server). «Σταμάτησε;» = το demo τρέχει αλλά το πρόγραμμα δεν έδωσε σημείο ζωής πάνω από 24 ώρες — ίσως κάτι πήγε στραβά. «Επανάληψη demo» = ίδιο email, call ή DMR ID σε περισσότερα demo.',
        'The clock counts from when the demo started (the installation’s first contact with the server). “Stopped?” = the demo is running but the program has shown no sign of life for over 24 hours — maybe something went wrong. “Repeated demo” = the same e-mail, callsign or DMR ID in more than one demo.',
        'Klockan räknar från att demot startade (installationens första kontakt med servern). ”Slutat?” = demot pågår men programmet har inte visat livstecken på över 24 timmar. ”Upprepat demo” = samma e-post, signal eller DMR-ID i fler än ett demo.') . '</p></section>';
  echo '<script>(function(){var off=' . $now . '*1000-Date.now(),D=' . json_encode(L('ημ.','d','d')) . ',E=' . json_encode(L('έληξε','ended','slut')) . ';function p(n){return(n<10?"0":"")+n}'
    . 'function tick(){var t=Math.floor((Date.now()+off)/1000);document.querySelectorAll(".cd").forEach(function(c){var s=+c.dataset.s,e=+c.dataset.e,l=e-t,b=c.querySelector(".cd-t"),i=c.querySelector(".prog i"),q=c.querySelector(".cd-p");'
    . 'var pc=e>s?Math.max(0,Math.min(100,Math.round((t-s)/(e-s)*100))):100;i.style.width=pc+"%";q.textContent=pc+"%";'
    . 'if(l<=0){b.textContent=E;c.classList.add("done");return}var d=Math.floor(l/86400),h=Math.floor(l%86400/3600),m=Math.floor(l%3600/60),x=l%60;'
    . 'b.textContent=(d?d+" "+D+" ":"")+p(h)+":"+p(m)+":"+p(x);c.classList.toggle("soon",l<86400)})}tick();setInterval(tick,1000)})();</script>'
    . '<style>.cd-t{font-family:var(--mono);font-size:17px;font-variant-numeric:tabular-nums}.cd.soon .cd-t{color:var(--tx)}.cd.done .cd-t{color:var(--muted)}.cd .prog{margin:4px 0 2px;height:8px;border-radius:5px;background:var(--line);overflow:hidden}.cd .prog i{display:block;height:100%;background:var(--acc)}.demot td{vertical-align:top}</style>';
}

/* ===================== MESSAGES FROM USERS ===================== */
elseif ($p === 'inbox') {
  // ---- incoming: messages from users (program + website) ----
  echo '<div class="help" style="margin-bottom:12px">' . L('Μηνύματα που στέλνουν οι χρήστες — είτε από το site είτε από το πρόγραμμα. Απάντα: η απάντηση μπαίνει στο μηχανισμό μηνυμάτων του server προς την εγκατάσταση του χρήστη· αν έγραψε από το site χωρίς εγκατάσταση, απάντα με email (σύνδεσμος ✉). Σημείωση: το DigiConnect δεν εμφανίζει ακόμη τα μηνύματα του server μέσα στο πρόγραμμα.',
      'Messages that users send — from the website or from the program. Reply: the reply goes into the server’s message system for the user’s installation; if they wrote from the website without an installation, reply by e-mail (✉ link). Note: DigiConnect does not show server messages inside the program yet.',
      'Meddelanden från användare — från webbplatsen eller programmet. Svara: svaret läggs i serverns meddelandesystem för användarens installation; om de skrev från webbplatsen utan installation, svara med e-post (✉). Obs: DigiConnect visar ännu inte servermeddelanden i programmet.') . '</div>';
  $inbox = dc_q("SELECT * FROM dc_inbox WHERE status!='closed' ORDER BY (reply IS NOT NULL AND reply<>''), t DESC LIMIT 200")->fetchAll();
  $newN = (int)dc_scalar("SELECT COUNT(*) FROM dc_inbox WHERE status='new'");
  dc_q('UPDATE dc_inbox SET read_t=? WHERE read_t IS NULL', [time()]);
  echo '<section class="card"><h2>📥 ' . L('Εισερχόμενα από χρήστες','Incoming from users','Inkommande från användare') . ($newN ? ' <span class="pill o">' . $newN . ' ' . L('νέα','new','nya') . '</span>' : '') . '</h2>';
  if (!$inbox) echo '<div class="muted">' . L('Δεν υπάρχουν μηνύματα από χρήστες ακόμη.','No messages from users yet.','Inga meddelanden från användare ännu.') . '</div>';
  $topics = ['reinstall' => L('Επανεγκατάσταση / χάθηκε το installer','Reinstall / lost installer','Ominstallation / förlorad installerare'), 'activation' => L('Ενεργοποίηση','Activation','Aktivering'), 'bug' => L('Πρόβλημα','Bug','Problem'), 'other' => L('Άλλο','Other','Annat')];
  foreach ($inbox as $m) {
    $who = h($m['call'] ?: ($m['name'] ?: ($m['email'] ?: ($m['src'] === 'web' ? L('ιστοσελίδα','website','webbplats') : L('άγνωστος','unknown','okänd')))));
    $tp = $topics[$m['topic']] ?? ($m['topic'] ? h($m['topic']) : '');
    $meta = [];
    if ($m['email']) $meta[] = '✉ <a href="mailto:' . h($m['email']) . '">' . h($m['email']) . '</a>';
    if ($m['install']) { $no = dc_inst_no($m['install']); if ($no) $meta[] = '<a href="?p=installs&q=' . $no . '">' . h($no) . '</a>'; }
    if ($m['version']) $meta[] = 'v' . h($m['version']);
    if ($m['os']) $meta[] = h($m['os']);
    $meta[] = '<span class="muted">' . h($m['src'] === 'web' ? L('από το site','from site','från webbplatsen') : L('από το πρόγραμμα','from app','från programmet')) . '</span>';
    echo '<div class="card" style="margin:10px 0;border-left:3px solid ' . ($m['status'] === 'new' ? 'var(--tx)' : 'var(--line)') . '">'
      . '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b>' . $who . '</b>' . ($tp ? ' <span class="pill">' . $tp . '</span>' : '') . ($m['status'] === 'replied' ? ' <span class="pill ok">' . L('απαντήθηκε','replied','besvarat') . '</span>' : '') . '<span class="spacer" style="flex:1"></span><small class="muted">' . dc_dt($m['t']) . '</small></div>'
      . '<div class="muted" style="font-size:12px;margin:2px 0 8px">' . implode(' · ', $meta) . '</div>'
      . ($m['subject'] ? '<b>' . h($m['subject']) . '</b><br>' : '') . '<div style="white-space:pre-wrap;margin:4px 0 10px;user-select:text">' . h($m['body']) . '</div>'
      . ($m['reply'] ? '<div style="background:color-mix(in srgb,var(--acc) 8%,transparent);border-radius:8px;padding:8px 10px;margin:0 0 10px"><small class="muted">' . L('Η απάντησή σου','Your reply','Ditt svar') . ' · ' . dc_dt($m['reply_t']) . '</small><br><div style="white-space:pre-wrap">' . h($m['reply']) . '</div></div>' : '')
      . '<form method="post" class="form"><input type="hidden" name="p" value="inbox"><input type="hidden" name="iid_msg" value="' . (int)$m['id'] . '">' . csrf()
      . '<textarea name="reply" rows="3" style="width:100%" placeholder="' . L('Γράψε απάντηση…','Write a reply…','Skriv ett svar…') . '">' . h($m['reply'] ?: '') . '</textarea>'
      . '<div style="display:flex;gap:6px;margin-top:6px"><button class="btn pri sm" name="a" value="inbox_reply">' . ($m['install'] ? L('Αποστολή απάντησης','Send reply','Skicka svar') : L('Αποθήκευση','Save','Spara')) . '</button>'
      . '<button class="btn sm" name="a" value="inbox_close" formnovalidate>' . L('Κλείσιμο','Close','Stäng') . '</button>'
      . '<button class="btn sm danger" name="a" value="inbox_del" formnovalidate onclick="return confirm(\'' . L('Διαγραφή;','Delete?','Radera?') . '\')">' . L('Διαγραφή','Delete','Radera') . '</button></div></form></div>';
  }
  echo '</section>';
}

/* ===================== LIVE CHATS ===================== */
elseif ($p === 'chat') {
  // ---- live chats from the website (talk.php): two-pane messenger, pictures, formatting, emoji, archive — everything stays on this server ----
  $LB = ['title' => L('Συνομιλίες', 'Chats'), 'pick' => L('Διάλεξε μια συνομιλία από τα αριστερά.', 'Pick a chat from the list.'), 'drop' => L('Άφησε τη φωτογραφία εδώ', 'Drop the picture here'),
    'hint' => L('Enter = αποστολή · Shift+Enter = νέα γραμμή', 'Enter = send · Shift+Enter = new line'), 'send' => L('Αποστολή', 'Send'), 'det' => L('Στοιχεία', 'Details'), 'note' => L('Ιδιωτική σημείωση', 'Private note'),
    'notehint' => L('Τη βλέπεις μόνο εσύ — δεν φαίνεται στον επισκέπτη.', 'Only you see this — never shown to the visitor.'), 'search' => L('Αναζήτηση…', 'Search…'), 'active' => L('Ενεργές', 'Active'), 'archived' => L('Αρχείο', 'Archive'),
    'ph' => L('Γράψε μήνυμα…', 'Write a message…'), 'newmsg' => L('νέα μηνύματα', 'new messages'), 'info' => L('Στοιχεία επισκέπτη', 'Visitor details'), 'pin' => L('Καρφίτσωμα', 'Pin'), 'archive' => L('Αρχειοθέτηση', 'Archive'), 'unarchive' => L('Επαναφορά από το αρχείο', 'Restore from archive'),
    'delthread' => L('Διαγραφή συνομιλίας', 'Delete chat'), 'photo' => L('Φωτογραφία', 'Photo'), 'bold' => L('έντονα', 'bold'), 'ital' => L('πλάγια', 'italic'), 'code' => L('κώδικας', 'code'), 'visitor' => L('Επισκέπτης', 'Visitor'), 'you' => L('Εσύ', 'You'),
    'typing' => L('γράφει…', 'typing…'), 'visitor_typing' => L('Ο επισκέπτης γράφει…', 'The visitor is typing…'), 'online' => L('στη σελίδα τώρα', 'on the page now'), 'offline' => L('εκτός σελίδας', 'not on the page'),
    'noarch' => L('Το αρχείο είναι άδειο.', 'The archive is empty.'), 'nores' => L('Κανένα αποτέλεσμα.', 'No results.'), 'nochats' => L('Καμία συνομιλία ακόμη. Οι χρήστες γράφουν από τη σελίδα επικοινωνίας.', 'No chats yet. Users write from the contact page.'),
    'today' => L('Σήμερα', 'Today'), 'yest' => L('Χθες', 'Yesterday'), 'now' => L('τώρα', 'now'), 'min' => L('λ.', 'min'), 'removed' => L('Το μήνυμα αφαιρέθηκε', 'This message was removed'), 'copy' => L('Αντιγραφή', 'Copy'), 'del' => L('Διαγραφή', 'Delete'),
    'seen' => L('Διαβάστηκε', 'Read'), 'sent' => L('Στάλθηκε', 'Sent'), 'name' => L('Όνομα', 'Name'), 'call' => L('Διακριτικό', 'Callsign'), 'started' => L('Ξεκίνησε', 'Started'), 'install' => L('Εγκατάσταση', 'Installation'), 'open' => L('Άνοιγμα', 'Open'),
    'errtype' => L('Μόνο εικόνες JPG, PNG, GIF ή WebP.', 'Only JPG, PNG, GIF or WebP pictures.'), 'errbig' => L('Η φωτογραφία είναι πολύ μεγάλη (μέχρι 5 MB).', 'The picture is too big (max 5 MB).'), 'errsend' => L('Δεν στάλθηκε — ξαναδοκίμασε.', 'Not sent — please try again.'),
    'delmsgq' => L('Να αφαιρεθεί αυτό το μήνυμα και για τους δύο;', 'Remove this message for both of you?'), 'delthreadq' => L('Να διαγραφεί ΟΡΙΣΤΙΚΑ όλη η συνομιλία (και οι φωτογραφίες της);', 'Permanently delete the whole chat (and its pictures)?')];
  $tpl = <<<'HTMLCHAT'
<style>
body{grid-template-columns:230px minmax(0,1fr)!important}.rail{display:none!important}main{max-width:none!important;padding-bottom:18px}
@media (max-width:1250px){.hc-tool small{display:none}}
.hc{display:grid;grid-template-columns:330px minmax(0,1fr);height:calc(100vh - 128px);min-height:520px;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow,none)}
.hc *{box-sizing:border-box}
.hc button{font:inherit;color:inherit;cursor:pointer}
.hc-l{display:flex;flex-direction:column;border-right:1px solid var(--line);min-height:0;background:var(--bg2)}
.hc-lh{padding:14px 14px 10px;display:flex;flex-direction:column;gap:10px}
.hc-lh h2{margin:0;font-size:17px;display:flex;align-items:center;gap:8px}
.hc-lh h2 .bd{background:var(--bad);color:#fff;font-size:11px;font-weight:700;border-radius:999px;padding:1px 8px}
.hc-srch{position:relative}.hc-srch input{width:100%;padding:9px 12px 9px 34px;border-radius:10px;background:var(--bg)}
.hc-srch svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);width:16px;height:16px;stroke:var(--muted);fill:none;stroke-width:2}
.hc-tabs{display:flex;gap:4px;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:3px}
.hc-tabs button{flex:1;border:0;background:transparent;padding:6px 8px;border-radius:8px;font-size:13px;font-weight:600;color:var(--muted)}
.hc-tabs button.on{background:var(--card);color:var(--text);box-shadow:0 1px 3px rgba(0,0,0,.25)}
.hc-list{flex:1;overflow-y:auto;overscroll-behavior:contain;min-height:0}
.hc-th{display:flex;gap:11px;padding:11px 14px;cursor:pointer;border-bottom:1px solid var(--line);position:relative;align-items:center}
.hc-th:hover{background:color-mix(in srgb,var(--acc) 7%,transparent)}
.hc-th.on{background:color-mix(in srgb,var(--acc) 15%,transparent)}
.hc-th.on:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acc)}
.hc-av{flex:0 0 auto;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:15px;color:#fff;position:relative;letter-spacing:.02em}
.hc-av i{position:absolute;right:-1px;bottom:-1px;width:12px;height:12px;border-radius:50%;background:var(--muted);border:2px solid var(--bg2)}
.hc-av i.on{background:var(--rx)}
.hc-tb{flex:1;min-width:0}
.hc-t1{display:flex;gap:8px;align-items:baseline}
.hc-t1 b{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}
.hc-t1 small{color:var(--muted);font-size:11.5px;white-space:nowrap}
.hc-t2{display:flex;gap:8px;align-items:center;margin-top:2px}
.hc-t2 span{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted);font-size:13px}
.hc-t2 span.typ{color:var(--rx);font-style:italic}
.hc-t2 em{font-style:normal;background:var(--acc);color:#04142e;font-size:11px;font-weight:800;border-radius:999px;min-width:20px;text-align:center;padding:1px 6px}
.hc-pin{width:13px;height:13px;stroke:var(--muted);fill:var(--muted)}
.hc-none{padding:30px 18px;color:var(--muted);text-align:center;font-size:13.5px}
.hc-r{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--bg)}
.hc-rh{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--bg2)}
.hc-back{display:none;border:1px solid var(--line2);background:transparent;border-radius:9px;width:36px;height:36px;font-size:18px}
.hc-who{flex:1;min-width:0}
.hc-who b{display:block;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hc-who small{display:block;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hc-who small.on{color:var(--rx)}
.hc-ic{display:flex;gap:4px}
.hc-ib{width:36px;height:36px;border:1px solid transparent;background:transparent;border-radius:9px;display:grid;place-items:center;color:var(--muted)}
.hc-ib:hover{background:var(--line);color:var(--text)}.hc-ib.on{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 40%,transparent)}
.hc-ib svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.hc-body{flex:1;display:flex;min-height:0}
.hc-feedw{flex:1;position:relative;min-width:0;min-height:0;display:flex;flex-direction:column}
.hc-feed{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:16px 18px;display:flex;flex-direction:column;gap:3px;min-height:0;scroll-behavior:auto}
.hc-day{align-self:center;margin:12px 0 6px;font-size:12px;color:var(--muted);background:var(--bg2);border:1px solid var(--line);border-radius:999px;padding:2px 12px}
.hc-m{display:flex;gap:8px;max-width:78%;align-items:flex-end}
.hc-m.me{align-self:flex-end;flex-direction:row-reverse}
.hc-m.first{margin-top:8px}
.hc-bub{position:relative;padding:7px 11px 5px;border-radius:16px;line-height:1.45;word-wrap:break-word;overflow-wrap:anywhere;min-width:64px}
.hc-m.them .hc-bub{background:var(--card);border:1px solid var(--line2);border-bottom-left-radius:5px}
.hc-m.me .hc-bub{background:#1f6feb;color:#fff;border-bottom-right-radius:5px}
.hc-m.me .hc-bub a{color:#fff;text-decoration:underline}
.hc-bub .tx{white-space:normal}
.hc-bub code{font:12.5px var(--mono);background:rgba(127,127,127,.25);border-radius:5px;padding:1px 5px}
.hc-bub pre{margin:6px 0;padding:8px 10px;background:rgba(0,0,0,.3);border-radius:9px;font:12.5px/1.45 var(--mono);white-space:pre-wrap;overflow-x:auto;color:#e8eef5}
.hc-bub img.ph{display:block;padding:0!important;width:240px;max-width:100%;height:auto;border-radius:11px;margin:2px 0 4px;cursor:zoom-in;background:var(--line)}
.hc-bub .ft{display:flex;gap:5px;justify-content:flex-end;align-items:center;font-size:11px;opacity:.7;margin-top:1px;white-space:nowrap}
.hc-bub .tk{font-size:12px;letter-spacing:-3px}.hc-bub .tk.rd{color:#7ff0b0;opacity:1}
.hc-bub .del{font-style:italic;opacity:.65}
.hc-act{position:absolute;top:-12px;right:6px;display:none;gap:2px;background:var(--card);border:1px solid var(--line2);border-radius:9px;padding:2px;box-shadow:0 4px 14px rgba(0,0,0,.35);z-index:2}
.hc-m.me .hc-act{right:auto;left:6px}
.hc-bub:hover .hc-act{display:flex}
.hc-act button{border:0;background:transparent;width:26px;height:26px;border-radius:6px;color:var(--text);font-size:13px}.hc-act button:hover{background:var(--line)}
.hc-mav{flex:0 0 auto;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:700;color:#fff}
.hc-typ{height:22px;padding:0 20px;color:var(--rx);font-size:12.5px;font-style:italic}
.hc-new{position:absolute;right:18px;bottom:10px;border:0;background:var(--acc);color:#04142e;font-weight:700;border-radius:999px;padding:6px 14px;box-shadow:0 6px 18px rgba(0,0,0,.4);display:none;z-index:3}
.hc-comp{border-top:1px solid var(--line);background:var(--bg2);padding:8px 14px 12px;position:relative}
.hc-tool{display:flex;gap:2px;margin-bottom:6px;align-items:center}
.hc-tool button{border:0;background:transparent;border-radius:8px;min-width:32px;height:30px;color:var(--muted);font-size:14px;padding:0 6px}
.hc-tool button:hover{background:var(--line);color:var(--text)}
.hc-tool .sp{flex:1}.hc-tool small{color:var(--muted);font-size:11.5px}
.hc-row{display:flex;gap:10px;align-items:flex-end}
.hc-row textarea{flex:1;resize:none;min-height:44px;max-height:170px;border-radius:12px;padding:11px 13px;line-height:1.4;background:var(--bg)}
.hc-send{border:0;background:var(--acc);color:#04142e;font-weight:700;border-radius:12px;height:44px;padding:0 20px;display:flex;align-items:center;gap:7px}
.hc-send:disabled{opacity:.45;cursor:default}
.hc-send svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.hc-att{display:none;margin:0 0 8px;align-items:center;gap:10px;background:var(--bg);border:1px solid var(--line2);border-radius:11px;padding:6px 10px}
.hc-att img{height:54px;border-radius:8px}.hc-att span{flex:1;font-size:12.5px;color:var(--muted);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hc-att button{border:0;background:var(--line);border-radius:50%;width:26px;height:26px}
.hc-err{color:var(--bad);font-size:12.5px;min-height:0;margin-bottom:4px}
.hc-side{width:270px;flex:0 0 auto;border-left:1px solid var(--line);background:var(--bg2);padding:14px;display:none;flex-direction:column;gap:10px;overflow-y:auto}
.hc-side.open{display:flex}
.hc-side h4{margin:0;font-size:13px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.hc-side textarea{width:100%;min-height:140px;resize:vertical;border-radius:10px}
.hc-side dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:5px 10px;font-size:13px}.hc-side dt{color:var(--muted)}.hc-side dd{margin:0;overflow-wrap:anywhere}
.hc-empty{flex:1;display:grid;place-items:center;color:var(--muted);text-align:center;padding:30px}
.hc-empty svg{width:56px;height:56px;stroke:var(--line2);fill:none;stroke-width:1.5;margin-bottom:10px}
.hc-lb{position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:100;display:none;align-items:center;justify-content:center;cursor:zoom-out;padding:20px}
.hc-lb.on{display:flex}.hc-lb img{max-width:100%;max-height:100%;border-radius:8px}
.hc-drop{position:absolute;inset:0;background:color-mix(in srgb,var(--acc) 22%,transparent);border:3px dashed var(--acc);border-radius:12px;display:none;place-items:center;font-weight:700;font-size:18px;z-index:5;pointer-events:none}
.hc-feedw.drag .hc-drop{display:grid}
@media (max-width:980px){.hc-side.open{position:absolute;right:0;top:0;bottom:0;z-index:6;box-shadow:-10px 0 30px rgba(0,0,0,.4)}.hc-r{position:relative}}
@media (max-width:820px){
 .hc{grid-template-columns:1fr;height:calc(100vh - 20px)}
 .hc-r{display:none}.hc.open .hc-l{display:none}.hc.open .hc-r{display:flex}.hc-back{display:inline-block}
 .hc-m{max-width:92%}
}
</style>
<div class="hc" id="hc">
 <div class="hc-l">
  <div class="hc-lh">
   <h2>💬 <span id="L_title"></span> <span class="bd" id="hcBadge" style="display:none"></span></h2>
   <div class="hc-srch"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="hcQ" type="search" autocomplete="off"></div>
   <div class="hc-tabs"><button id="tabA" class="on"></button><button id="tabB"></button></div>
  </div>
  <div class="hc-list" id="hcList"></div>
 </div>
 <div class="hc-r" id="hcR">
  <div class="hc-empty" id="hcEmpty"><div><svg viewBox="0 0 24 24"><path d="M4 4h16v12H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg><div id="L_pick"></div></div></div>
  <div id="hcConv" style="display:none;flex-direction:column;flex:1;min-height:0">
   <div class="hc-rh">
    <button class="hc-back" id="hcBack" type="button">←</button>
    <div class="hc-av" id="hAv"></div>
    <div class="hc-who"><b id="hName"></b><small id="hSub"></small></div>
    <div class="hc-ic">
     <button class="hc-ib" id="bInfo" type="button"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/></svg></button>
     <button class="hc-ib" id="bPin" type="button"><svg viewBox="0 0 24 24"><path d="M12 17v5M9 3h6l-1 6 4 4H6l4-4z"/></svg></button>
     <button class="hc-ib" id="bArch" type="button"><svg viewBox="0 0 24 24"><path d="M3 4h18v4H3zM5 8v12h14V8M10 12h4"/></svg></button>
     <button class="hc-ib" id="bDel" type="button"><svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/></svg></button>
    </div>
   </div>
   <div class="hc-body">
    <div class="hc-feedw" id="hcFW">
     <div class="hc-feed" id="hcFeed"></div>
     <div class="hc-typ" id="hcTyp"></div>
     <button class="hc-new" id="hcNew" type="button"></button>
     <div class="hc-drop" id="L_drop"></div>
     <div class="hc-comp">
      <div class="hc-err" id="hcErr"></div>
      <div class="hc-att" id="hcAtt"><img id="hcAttImg" alt=""><span id="hcAttName"></span><button type="button" id="hcAttX">✕</button></div>
      <div class="hc-tool">
       <button type="button" id="tB"><b>B</b></button><button type="button" id="tI"><i>I</i></button><button type="button" id="tS"><s>S</s></button><button type="button" id="tC" style="font-family:monospace">&lt;/&gt;</button>
       <button type="button" id="tE">😀</button><button type="button" id="tP" title="">📎</button>
       <span class="sp"></span><small id="L_hint"></small>
      </div>
      <div class="hc-row"><textarea id="hcTa" rows="1"></textarea><button class="hc-send" id="hcSend" type="button"><span id="L_send"></span><svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></svg></button></div>
      <input type="file" id="hcFile" accept="image/jpeg,image/png,image/gif,image/webp" style="display:none">
     </div>
    </div>
    <div class="hc-side" id="hcSide">
     <h4 id="L_det"></h4><dl id="hcDl"></dl>
     <h4 id="L_note"></h4><textarea id="hcNote"></textarea><small class="muted" id="L_notehint"></small>
    </div>
   </div>
  </div>
 </div>
</div>
<div class="hc-lb" id="hcLb"><img alt=""></div>
<script src="../chat.js"></script>
<script>
(function(){
var C=window.DCChat, CSRF=__CSRF__, LB=__LBL__, OPEN=__TOKEN__;
var $=function(i){return document.getElementById(i);};
var cur='', last=0, arch=0, threads=[], lastUnread=-1, stick=true, pendingFile=null, sending=false, lastDay='', lastWho='', typSent=0, srch='', loadedFirst=false, now=Math.floor(Date.now()/1000), seenIds={}, info={};
['title','pick','drop','hint','send','det','note','notehint'].forEach(function(k){var e=$('L_'+k);if(e)e.textContent=LB[k];});
$('hcQ').placeholder=LB.search;$('tabA').textContent=LB.active;$('hcTa').placeholder=LB.ph;$('hcNew').textContent='↓ '+LB.newmsg;
$('bInfo').title=LB.info;$('bPin').title=LB.pin;$('bArch').title=LB.archive;$('bDel').title=LB.delthread;$('tP').title=LB.photo;$('tB').title='**'+LB.bold+'**';$('tI').title='*'+LB.ital+'*';$('tC').title=LB.code;
function api(a,fd){var u='?chatapi='+a;if(!fd)return fetch(u,{credentials:'same-origin'}).then(function(r){return r.json();});return fetch(u,{method:'POST',body:fd,credentials:'same-origin'}).then(function(r){return r.json();});}
function post(a,o){var fd=new FormData();fd.append('csrf',CSRF);fd.append('token',cur);for(var k in o)fd.append(k,o[k]);return api(a,fd);}
function hue(s){var h=0;for(var i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))%360;return 'hsl('+h+',52%,42%)';}
function nm(t){return (t.name+' '+t.call).trim()||LB.visitor;}
function ini(t){var n=(t.call||t.name||'?').replace(/[^A-Za-z0-9Ͱ-Ͽ]/g,'');return (n.slice(0,2)||'?').toUpperCase();}
function setBadge(n){var b=$('hcBadge');b.style.display=n?'':'none';b.textContent=n;document.title=(n?'('+n+') ':'')+document.title.replace(/^\(\d+\) /,'');
 var nav=document.querySelector('nav a[href*="p=chat"] .cnt, nav a[href*="p=chat"] .badge');if(nav)nav.textContent=n||'';}
/* ---------- thread list ---------- */
function renderList(){
 var L=$('hcList');L.innerHTML='';
 if(!threads.length){L.innerHTML='<div class="hc-none">'+C.esc(arch?LB.noarch:(srch?LB.nores:LB.nochats))+'</div>';return;}
 threads.forEach(function(t){
  var d=document.createElement('div');d.className='hc-th'+(t.token===cur?' on':'');d.dataset.t=t.token;
  var pv=t.typ?'<span class="typ">'+C.esc(LB.typing)+'</span>':'<span>'+(t.lastwho==='owner'?C.esc(LB.you)+': ':'')+C.esc(t.last.replace(/[*`_~]/g,''))+'</span>';
  d.innerHTML='<div class="hc-av" style="background:'+hue(t.token)+'">'+C.esc(ini(t))+'<i class="'+(t.on?'on':'')+'"></i></div><div class="hc-tb"><div class="hc-t1"><b>'+C.esc(nm(t))+'</b>'+(t.pin?'<svg class="hc-pin" viewBox="0 0 24 24"><path d="M12 17v5M9 3h6l-1 6 4 4H6l4-4z"/></svg>':'')+'<small>'+C.ago(t.lt,now,LB)+'</small></div><div class="hc-t2">'+pv+(t.unread?'<em>'+t.unread+'</em>':'')+'</div></div>';
  d.addEventListener('click',function(){openThread(t.token);});
  L.appendChild(d);});
}
var listBusy=false;
function loadList(){if(listBusy)return;listBusy=true;
 api('threads&arch='+arch+'&q='+encodeURIComponent(srch)).then(function(j){listBusy=false;if(!j||!j.ok)return;
  now=j.now;threads=j.threads;renderList();setBadge(j.unread);$('tabB').textContent=LB.archived+(j.archived?' ('+j.archived+')':'');
  if(lastUnread>=0&&j.unread>lastUnread){C.beep();}lastUnread=j.unread;
  var t=threads.filter(function(x){return x.token===cur;})[0];if(t&&cur){$('hSub').className=t.on?'on':'';}
 }).catch(function(){listBusy=false;});}
/* ---------- conversation ---------- */
function openThread(tk){
 cur=tk;last=0;lastDay='';lastWho='';seenIds={};stick=true;info={};$('hcFeed').innerHTML='';$('hcErr').textContent='';clearAtt();
 $('hcEmpty').style.display='none';$('hcConv').style.display='flex';$('hc').classList.add('open');
 try{history.replaceState(null,'','?p=chat&t='+tk);}catch(e){}
 renderList();loadMsgs(true);setTimeout(function(){$('hcTa').focus();},50);}
function closeThread(){cur='';$('hc').classList.remove('open');$('hcConv').style.display='none';$('hcEmpty').style.display='';try{history.replaceState(null,'','?p=chat');}catch(e){}renderList();}
function tickHtml(m){return m.who==='owner'?'<span class="tk'+(m.rd?' rd':'')+'" title="'+C.esc(m.rd?LB.seen:LB.sent)+'">'+(m.rd?'✓✓':'✓')+'</span>':'';}
function buildMsg(m){
 var me=m.who==='owner',row=document.createElement('div');row.className='hc-m '+(me?'me':'them')+(lastWho!==m.who?' first':'');row.dataset.id=m.id;
 var dk=C.dayKey(m.t),sep=null;if(dk!==lastDay){lastDay=dk;sep=document.createElement('div');sep.className='hc-day';sep.textContent=C.dayLabel(m.t,LB.today,LB.yest);}
 lastWho=m.who;
 var b='';
 if(m.del)b='<div class="tx del">'+C.esc(LB.removed)+'</div>';
 else{if(m.img)b+='<img class="ph" src="?chatimg='+m.id+'" alt="" onload="this.style.width=Math.min(320,this.naturalWidth)+\'px\';var f=document.getElementById(\'hcFeed\');if(f&&f.dataset.stick!==\'0\')f.scrollTop=f.scrollHeight">';if(m.body)b+='<div class="tx">'+C.fmt(m.body)+'</div>';}
 var av=me?'':'<div class="hc-mav" style="background:'+hue(cur)+'">'+C.esc(ini(info))+'</div>';
 row.innerHTML=av+'<div class="hc-bub">'+(m.del?'':'<div class="hc-act"><button type="button" data-a="copy" title="'+C.esc(LB.copy)+'">⧉</button><button type="button" data-a="del" title="'+C.esc(LB.del)+'">🗑</button></div>')+b+'<div class="ft"><span>'+C.hm(m.t)+'</span>'+(m.del?'':tickHtml(m))+'</div></div>';
 row._m=m;return [sep,row];}
function addMsgs(ms){
 var f=$('hcFeed');ms.forEach(function(m){if(seenIds[m.id])return;seenIds[m.id]=1;if(m.id>last)last=m.id;var p=buildMsg(m);if(p[0])f.appendChild(p[0]);f.appendChild(p[1]);});
 if(stick)f.scrollTop=f.scrollHeight;else if(ms.length)$('hcNew').style.display='block';}
function loadMsgs(first){
 if(!cur)return;var tk=cur;
 api('msgs&t='+tk+'&after='+last).then(function(j){if(!j||!j.ok||tk!==cur)return;now=j.now;
  info={name:j.name,call:j.call,email:j.email};
  var nw=j.msgs.filter(function(m){return m.who==='user'&&!seenIds[m.id];}).length;
  addMsgs(j.msgs);
  if(nw&&!first&&(document.hidden||!document.hasFocus()))C.beep();
  j.upd.forEach(function(u){var el=document.querySelector('.hc-m[data-id="'+u.id+'"]');if(!el)return;if(u.del&&!el._m.del){var p=buildMsg(u);/* replace in place */el.innerHTML=p[1].innerHTML;el._m=u;}else if(u.rd&&!el._m.rd){el._m.rd=1;var tk2=el.querySelector('.tk');if(tk2){tk2.className='tk rd';tk2.textContent='✓✓';tk2.title=LB.seen;}}});
  var t={name:j.name,call:j.call};$('hName').textContent=nm(t);$('hAv').style.background=hue(tk);$('hAv').textContent=ini(t);
  $('hSub').className=j.on?'on':'';$('hSub').textContent=(j.on?'● '+LB.online:LB.offline)+(j.email?' · '+j.email:'');
  $('hcTyp').textContent=j.typ?LB.visitor_typing:'';
  $('bPin').classList.toggle('on',!!j.pin);$('bArch').classList.toggle('on',!!j.arch);$('bArch').title=j.arch?LB.unarchive:LB.archive;
  if(document.activeElement!==$('hcNote'))$('hcNote').value=j.note;
  var dl='<dt>'+LB.name+'</dt><dd>'+C.esc(j.name||'—')+'</dd><dt>'+LB.call+'</dt><dd>'+C.esc(j.call||'—')+'</dd><dt>Email</dt><dd>'+(j.email?'<a href="mailto:'+C.esc(j.email)+'">'+C.esc(j.email)+'</a>':'—')+'</dd><dt>'+LB.started+'</dt><dd>'+new Date(j.first*1000).toLocaleString()+'</dd>';
  if(j.inst)dl+='<dt>'+LB.install+'</dt><dd><a href="?p=installs&id='+encodeURIComponent(j.inst)+'">'+LB.open+' →</a></dd>';
  $('hcDl').innerHTML=dl;
  if(first){$('hcFeed').scrollTop=$('hcFeed').scrollHeight;}
 }).catch(function(){});}
/* ---------- sending ---------- */
function setErr(t){$('hcErr').textContent=t||'';}
function clearAtt(){pendingFile=null;$('hcAtt').style.display='none';$('hcFile').value='';}
function setFile(f){
 if(!f)return;if(!/^image\/(jpeg|png|gif|webp)$/.test(f.type)){setErr(LB.errtype);return;}if(f.size>5242880){setErr(LB.errbig);return;}
 setErr('');pendingFile=f;var r=new FileReader();r.onload=function(){$('hcAttImg').src=r.result;};r.readAsDataURL(f);$('hcAttName').textContent=f.name+' · '+Math.round(f.size/1024)+' KB';$('hcAtt').style.display='flex';$('hcTa').focus();}
function send(){
 if(sending||!cur)return;var body=$('hcTa').value.trim();if(!body&&!pendingFile)return;
 sending=true;$('hcSend').disabled=true;setErr('');
 var fd=new FormData();fd.append('csrf',CSRF);fd.append('token',cur);fd.append('body',body);if(pendingFile)fd.append('image',pendingFile,pendingFile.name);
 api('send',fd).then(function(j){sending=false;$('hcSend').disabled=false;
  if(!j||!j.ok){setErr((j&&j.err)||LB.errsend);return;}
  $('hcTa').value='';$('hcTa').style.height='';clearAtt();stick=true;addMsgs([j.msg]);loadList();$('hcTa').focus();
 }).catch(function(){sending=false;$('hcSend').disabled=false;setErr(LB.errsend);});}
/* ---------- events ---------- */
var ta=$('hcTa');
ta.addEventListener('input',function(){this.style.height='44px';this.style.height=Math.min(170,this.scrollHeight)+'px';if(cur&&Date.now()-typSent>2500&&this.value){typSent=Date.now();post('typing',{});}});
ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}
 if((e.ctrlKey||e.metaKey)&&e.key==='b'){e.preventDefault();C.wrap(ta,'**','**');}if((e.ctrlKey||e.metaKey)&&e.key==='i'){e.preventDefault();C.wrap(ta,'*','*');}});
ta.addEventListener('paste',function(e){var it=(e.clipboardData||{}).items||[];for(var i=0;i<it.length;i++)if(it[i].kind==='file'&&/^image\//.test(it[i].type)){setFile(it[i].getAsFile());e.preventDefault();return;}});
$('hcSend').addEventListener('click',send);
$('tB').onclick=function(){C.wrap(ta,'**','**');};$('tI').onclick=function(){C.wrap(ta,'*','*');};$('tS').onclick=function(){C.wrap(ta,'~~','~~');};
$('tC').onclick=function(){var v=ta.value.slice(ta.selectionStart,ta.selectionEnd);if(v.indexOf('\n')>=0)C.wrap(ta,'```\n','\n```');else C.wrap(ta,'`','`');};
$('tE').onclick=function(e){e.stopPropagation();C.picker($('tE'),function(x){C.insert(ta,x);});};
$('tP').onclick=function(){$('hcFile').click();};$('hcFile').onchange=function(){setFile(this.files[0]);};$('hcAttX').onclick=clearAtt;
var fw=$('hcFW');['dragenter','dragover'].forEach(function(ev){fw.addEventListener(ev,function(e){if(e.dataTransfer&&Array.prototype.indexOf.call(e.dataTransfer.types,'Files')>=0){e.preventDefault();fw.classList.add('drag');}});});
['dragleave','drop'].forEach(function(ev){fw.addEventListener(ev,function(e){e.preventDefault();fw.classList.remove('drag');if(ev==='drop'&&e.dataTransfer.files[0])setFile(e.dataTransfer.files[0]);});});
var feed=$('hcFeed');feed.addEventListener('scroll',function(){stick=feed.scrollHeight-feed.scrollTop-feed.clientHeight<60;feed.dataset.stick=stick?'1':'0';if(stick)$('hcNew').style.display='none';});
$('hcNew').onclick=function(){feed.scrollTop=feed.scrollHeight;$('hcNew').style.display='none';};
feed.addEventListener('click',function(e){
 var im=e.target.closest('img.ph');if(im){$('hcLb').querySelector('img').src=im.src;$('hcLb').classList.add('on');return;}
 var bt=e.target.closest('.hc-act button');if(!bt)return;var row=bt.closest('.hc-m'),m=row._m;
 if(bt.dataset.a==='copy'){try{navigator.clipboard.writeText(m.body||'');}catch(x){}}
 if(bt.dataset.a==='del'&&confirm(LB.delmsgq)){post('delmsg',{id:m.id}).then(function(){m.del=1;m.body='';m.img=0;var p=buildMsg(m);row.innerHTML=p[1].innerHTML;row._m=m;});}});
$('hcLb').onclick=function(){this.classList.remove('on');};document.addEventListener('keydown',function(e){if(e.key==='Escape')$('hcLb').classList.remove('on');});
$('bInfo').onclick=function(){$('hcSide').classList.toggle('open');this.classList.toggle('on');};
$('bPin').onclick=function(){post('flag',{k:'pin',v:$('bPin').classList.contains('on')?0:1}).then(function(){loadMsgs();loadList();});};
$('bArch').onclick=function(){var v=$('bArch').classList.contains('on')?0:1;post('flag',{k:'arch',v:v}).then(function(){if(v)closeThread();loadList();});};
$('bDel').onclick=function(){if(confirm(LB.delthreadq)){post('delthread',{}).then(function(){closeThread();loadList();});}};
$('hcBack').onclick=closeThread;
$('hcNote').addEventListener('blur',function(){if(cur)post('note',{note:this.value});});
$('tabA').onclick=function(){arch=0;$('tabA').classList.add('on');$('tabB').classList.remove('on');loadList();};
$('tabB').onclick=function(){arch=1;$('tabB').classList.add('on');$('tabA').classList.remove('on');loadList();};
var qt;$('hcQ').addEventListener('input',function(){clearTimeout(qt);var v=this.value;qt=setTimeout(function(){srch=v.trim();loadList();},250);});
/* ---------- live updates ---------- */
loadList();if(OPEN)openThread(OPEN);
setInterval(function(){loadList();},document.hidden?10000:4000);
setInterval(function(){if(cur&&!document.hidden)loadMsgs();},2500);
setInterval(function(){if(cur&&document.hidden)loadMsgs();},10000);
document.addEventListener('visibilitychange',function(){if(!document.hidden){loadList();loadMsgs();}});
window.addEventListener('focus',function(){loadMsgs();});
})();
</script>

HTMLCHAT;
  $openTok = preg_replace('/[^a-f0-9]/', '', (string)($_GET['t'] ?? '')); if (strlen($openTok) !== 32) $openTok = '';
  echo str_replace(['__CSRF__', '__LBL__', '__TOKEN__'], [json_encode($CSRF), json_encode($LB, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP), json_encode($openTok)], $tpl);
}

/* ===================== ACTIVITY ===================== */
elseif ($p === 'activity') {
  $ev = dc_q("SELECT * FROM dc_events ORDER BY t DESC LIMIT 300")->fetchAll();
  echo '<section class="card"><h2>' . L('Δραστηριότητα','Activity') . ' <small>(' . count($ev) . ')</small></h2>' . activity_rows($ev) . '</section>';
}

/* ===================== SETTINGS ===================== */
elseif ($p === 'settings') {
  echo '<div class="grid2">'
    . '<section class="card"><h2>' . L('Ενημερώσεις','Updates') . '</h2>'
    . '<form class="form" method="post">' . csrf() . '<input type="hidden" name="p" value="settings"><input type="hidden" name="a" value="set_check">'
    . '<label>' . L('Έλεγχος κάθε (λεπτά)','Check every (minutes)') . '<input type="number" name="mins" min="1" value="' . $ceMin . '"></label><button class="btn pri">' . L('Αποθήκευση','Save') . '</button></form>'
    . '<form class="form" method="post" style="margin-top:14px">' . csrf() . '<input type="hidden" name="p" value="settings"><input type="hidden" name="a" value="set_pause">'
    . '<label class="chk"><input type="checkbox" name="paused" value="1"' . ($paused?' checked':'') . '> ' . L('Παύση ενημερώσεων για όλους','Pause updates for everyone') . '</label><button class="btn">' . L('Αποθήκευση','Save') . '</button></form></section>'
    . '<section class="card"><h2>' . L('Άδειες','Licensing') . '</h2>'
    . '<form class="form" method="post">' . csrf() . '<input type="hidden" name="p" value="settings"><input type="hidden" name="a" value="set_gate">'
    . '<label class="chk"><input type="checkbox" name="gate" value="1"' . ($gate==='1'?' checked':'') . '> ' . L('Έλεγχος demo/άδειας ενεργός','Enforce demo/licence gate') . '</label>'
    . '<p class="help">' . L('Αν το ξεκλειδώσεις, το πρόγραμμα είναι δωρεάν για όλους χωρίς demo.','If unchecked, the app is free for everyone with no demo.') . '</p>'
    . '<button class="btn pri">' . L('Αποθήκευση','Save') . '</button></form>'
    . '<form class="form" method="post" style="margin-top:14px">' . csrf() . '<input type="hidden" name="p" value="settings"><input type="hidden" name="a" value="set_lic">'
    . '<label>' . L('Όταν ο server δεν είναι προσβάσιμος','When this server cannot be reached') . '<select name="offline">'
    . '<option value="require"' . ($off['offline']==='require'?' selected':'') . '>' . L('Να απαιτεί πάντα σύνδεση (δεν ξεκινά χωρίς απάντηση)','Always require a connection (does not start without an answer)') . '</option>'
    . '<option value="grace"' . ($off['offline']==='grace'?' selected':'') . '>' . L('Να δουλεύει για Ν ημέρες από τον τελευταίο έλεγχο','Keep working for N days after the last check') . '</option>'
    . '<option value="allow"' . ($off['offline']==='allow'?' selected':'') . '>' . L('Να δουλεύει πάντα· η απενεργοποίηση ισχύει μόλις συνδεθεί','Always keep working; a block applies as soon as it is online again') . '</option></select></label>'
    . '<label>' . L('Ημέρες ανοχής (για την επιλογή «Ν ημέρες»)','Grace days (for the «N days» option)') . '<input type="number" name="offline_days" min="1" value="' . (int)$off['offline_days'] . '"></label>'
    . '<label class="chk"><input type="checkbox" name="reinstall_id" value="1"' . (dc_kv('reinstall_id', '1') === '1' ? ' checked' : '') . '> ' . L('Επανεγκατάσταση: η νέα εγκατάσταση παίρνει αυτόματα την άδεια του ίδιου χρήστη (ίδιο διακριτικό + email) και σου έρχεται ειδοποίηση', 'Reinstall: a new installation automatically takes the licence of the same user (same callsign + e-mail) and you get an alert') . '</label>'
    . '<label class="chk"><input type="checkbox" name="reg_approval" value="1"' . (dc_kv('reg_approval', '0') === '1' ? ' checked' : '') . '> ' . L('Εγγραφές με έγκριση: ο νέος χρήστης περιμένει μέχρι να πατήσεις «Έγκριση» (Εγκαταστάσεις) και σου έρχεται ειδοποίηση', 'Registrations need approval: a new user waits until you press "Approve" (Installations) and you get an alert') . '</label>'
    . '<label class="chk"><input type="checkbox" name="lic_scope" value="1"' . (dc_kv('lic_scope', 'all') === 'major' ? ' checked' : '') . '> ' . L('Άδειες ανά κύρια έκδοση: η μόνιμη άδεια ισχύει για την κύρια έκδοση που ενεργοποιήθηκε (π.χ. 2.x)· η επόμενη (3.0) ζητά νέα άδεια', 'Licences per major version: a permanent licence is for the major version it was activated on (e.g. 2.x); the next one (3.0) needs a new licence') . '</label>'
    . '<label>' . L('Υπάρχουσες άδειες (χωρίς καταγεγραμμένη έκδοση) ισχύουν για την κύρια έκδοση','Existing licences (no recorded version) are valid for major version') . '<input type="number" name="lic_grandfather" min="1" value="' . (int)dc_kv('lic_grandfather', '2') . '"></label>'
    . '<p class="help">' . L('Το demo για νέες εγκαταστάσεις και το κουμπί Donate ορίζονται στις Άδειες / Κωδικοί.','The demo for new installations and the Donate button are set under Licences / Codes.') . '</p>'
    . '<button class="btn pri">' . L('Αποθήκευση','Save') . '</button></form></section></div>';
}

echo '<footer>DigiConnect Control Panel · ' . L('Έκδοση server ','Server version ') . '<b>' . DC_SERVER_VERSION . '</b> · © 2026 <b>SA7SVR</b> · HELLAS Zone Net</footer></main>';
echo '<div class="rail" id="rail">' . rail_html() . '</div>';
echo '<script>(function(){var b=document.getElementById("thm");if(b){function mark(){var t="auto";try{t=localStorage.getItem("dc_theme")||"auto"}catch(e){}b.querySelectorAll("a").forEach(function(a){a.className=a.dataset.t===t?"on":""})}b.addEventListener("click",function(e){var a=e.target.closest("a");if(!a)return;e.preventDefault();var t=a.dataset.t;try{t==="auto"?localStorage.removeItem("dc_theme"):localStorage.setItem("dc_theme",t)}catch(x){}if(t==="auto")document.documentElement.removeAttribute("data-theme");else document.documentElement.setAttribute("data-theme",t);mark()});mark()}var r=document.getElementById("rail");function up(){if(document.hidden)return;fetch("?rail=1",{cache:"no-store",credentials:"same-origin"}).then(function(x){return x.ok?x.text():null}).then(function(t){if(t&&t.indexOf("rail-h")>=0)r.innerHTML=t}).catch(function(){})}setInterval(up,30000);document.addEventListener("visibilitychange",up)})();</script></body></html>';

/* ============================================================= helpers */
function station_cards($rows) {
  if (!$rows) return '<p class="empty">' . L('Καμία εγκατάσταση ακόμη.','No installations yet.') . '</p>';
  $out = '<div class="stns">';
  foreach ($rows as $r) {
    list($st, $lf) = dc_state($r);
    $online = dc_online($r);
    $os = $r['os'] ?: '—';
    $act = trim((string)($r['note'] ?? '')); // app can report current network/TG in note later
    $out .= '<div class="stn ' . ($online ? 'on' : 'off') . '">'
      . '<div class="stn-ic">' . trx_icon($online, $online && (int)$r['ptt'] === 1) . '</div>'
      . '<div class="stn-b"><div class="stn-h"><b>' . h($r['call'] ?: '—') . '</b>'
      . '<span class="pill ' . ($online ? 'ok' : 'dim') . '">' . ($online ? 'Online' : 'Offline') . '</span></div>'
      . ($r['name'] ? '<div class="stn-n">' . h($r['name']) . '</div>' : '')
      . '<div class="stn-s">' . ($online
          ? '<span style="color:var(--rx)">● ' . h($st) . ($lf ? ' · ' . h($lf) : '') . '</span>'
          : '<span class="muted">' . L('Τελευταία φορά: ','Last seen: ') . dc_dt(dc_last($r)) . '</span>') . '</div>'
      . '<div class="stn-m">' . h($os) . ' · v' . h($r['version'] ?: '—') . ' · ' . h(dc_inst_no($r['id'])) . '</div>'
      . '</div></div>';
  }
  return $out . '</div>';
}

/* ---- transceiver icon: off / listening / transmitting ---- */
function trx_icon($on, $tx) {
  $c = $tx ? 'tx' : ($on ? 'on' : 'off');
  $disp = $on
    ? '<g class="wf"><rect x="13" y="19" width="3" height="6" rx="1"/><rect x="18" y="15" width="3" height="10" rx="1"/><rect x="23" y="17" width="3" height="8" rx="1"/><rect x="28" y="13" width="3" height="12" rx="1"/></g>'
    : '<path class="zz" d="M13 22h18"/>';
  return '<svg class="trx ' . $c . '" viewBox="0 0 56 48" role="img" aria-label="' . ($tx ? 'TX' : ($on ? 'online' : 'offline')) . '">'
    . '<path class="an" d="M44 18V5"/><circle class="an-t" cx="44" cy="4.5" r="2"/>'
    . '<rect class="fr" x="4" y="14" width="48" height="29" rx="5"/>'
    . '<rect class="sc ' . ($on ? '' : 'off') . '" x="9" y="18" width="29" height="13" rx="2.5"/>'
    . $disp
    . '<circle class="kn" cx="44" cy="25" r="4.2"/><path class="kn-l" d="M44 21.6v3.4"/>'
    . '<path class="gr" d="M10 37h14M10 40h14M28 37h6M28 40h6"/>'
    . ($tx ? '<text class="txl" x="40.5" y="40.5">TX</text>' : '')
    . '</svg>';
}
function ago($t) { $d = time() - (int)$t; if ($d < 90) return L('μόλις τώρα','just now'); if ($d < 5400) return round($d/60) . L(' λεπτά πριν',' min ago'); if ($d < 172800) return round($d/3600) . L(' ώρες πριν',' h ago'); return round($d/86400) . L(' ημέρες πριν',' days ago'); }
function rail_html() {
  $now = time();
  $rows = dc_q('SELECT rowid AS rno, * FROM dc_installs WHERE MAX(COALESCE(last_ping,0), COALESCE(last_seen,0)) >= CAST(? AS INTEGER) ORDER BY MAX(COALESCE(last_ping,0), COALESCE(last_seen,0)) DESC LIMIT 60', [$now - 7 * 86400])->fetchAll();
  $on = []; $off = [];
  foreach ($rows as $r) { $r['_t'] = dc_last($r); if (dc_online($r)) $on[] = $r; else $off[] = $r; }
  usort($on, fn($a, $b) => strcmp((string)($a['call'] ?: 'zzz'), (string)($b['call'] ?: 'zzz')));
  $card = function ($r, $isOn) {
    $call = $r['call'] ?: '—'; $tx = $isOn && (int)$r['ptt'] === 1;
    if ($isOn) {
      if ($tx) $msg = '🎙 ' . L('Εκπέμπει', 'Transmitting') . ($r['tx'] ? ' → ' . $r['tx'] : '');
      elseif ($r['rx']) $msg = '📡 ' . L('Ακούει ', 'Listening ') . str_replace(',', ', ', $r['rx']);
      elseif ($r['tx']) $msg = L('Έτοιμος για εκπομπή → ', 'Ready to transmit → ') . $r['tx'];
      else $msg = L('Το πρόγραμμα είναι ανοιχτό', 'The program is open');
      $st = '<span class="rs on"><i></i>Online</span>';
    } else { $msg = L('Τελευταία φορά online: ', 'Last online: ') . ago($r['_t']); $st = '<span class="rs"><i></i>Offline</span>'; }
    $osn = ['windows' => 'Windows', 'macos' => 'macOS', 'linux' => 'Linux'][$r['os']] ?? ($r['os'] ?: '?');
    return '<a class="rc ' . ($isOn ? 'on' : 'off') . ($tx ? ' tx' : '') . '" href="?p=installs&q=' . urlencode(sprintf('DC-%05d', $r['rno'])) . '" title="' . h(dc_dt($r['_t'])) . '">'
      . '<div class="pcw">' . trx_icon($isOn, $tx) . '<small>' . h($osn) . '</small></div>'
      . '<div class="rb"><div class="r1"><b>' . h($call) . '</b>' . $st . '</div>'
      . (($r['name'] || $r['grid']) ? '<div class="r2">' . h($r['name']) . ($r['name'] && $r['grid'] ? ' · ' : '') . ($r['grid'] ? '<span class="mono">' . h($r['grid']) . '</span>' : '') . '</div>' : '')
      . '<div class="r3">' . h($msg) . '</div>'
      . ($r['eq'] ? '<div class="r4">' . h($r['eq']) . '</div>' : '')
      . '<div class="r4">' . h($osn) . ($r['version'] ? ' · v' . h($r['version']) : '') . ' · ' . h(sprintf('DC-%05d', $r['rno'])) . '</div></div></a>';
  };
  $o = '<div class="rail-h"><h3>' . L('Σταθμοί', 'Stations') . '</h3><span class="rn on"><i></i>' . count($on) . ' online</span><span class="rn">' . count($off) . ' offline</span></div>';
  $o .= '<div class="rail-s">' . L('Ανανεώνεται μόνο του κάθε 30″', 'Refreshes itself every 30″') . '</div>';
  if (!$on) $o .= '<div class="rail-e">' . L('Κανείς σε σύνδεση αυτή τη στιγμή.', 'Nobody online right now.') . '</div>';
  foreach ($on as $r) $o .= $card($r, true);
  if ($off) { $o .= '<div class="rail-t">' . L('Πρόσφατα (7 ημέρες)', 'Recently (7 days)') . '</div>'; foreach (array_slice($off, 0, 25) as $r) $o .= $card($r, false); }
  return $o;
}

/* ---- licence helpers shared by Installations and Licences (same as HAM Digi) ---- */
function dc_lic_label(array $r): string {
  if ((int)($r['enabled'] ?? 1) === 0 || ($r['state'] ?? '') === 'disabled') return '<span class="pill bad">' . L('Απενεργοποιημένη', 'Disabled') . '</span>';
  list($st, $exp) = dc_lic_effective($r); $x = $exp ? ' → ' . gmdate('Y-m-d H:i', $exp) . ' UTC' : '';
  $m = ['free' => ['ok', L('Δωρεάν', 'Free')], 'full' => ['ok', L('Μόνιμη άδεια', 'Licensed')], 'demo' => ['o', 'Demo'], 'locked' => ['bad', L('Κλειδωμένο', 'Locked')], 'pending' => ['o', L('Αναμονή έγκρισης', 'Waiting for approval')], 'expired' => ['bad', L('Έληξε', 'Expired')]][$st] ?? ['', $st];
  return '<span class="pill ' . $m[0] . '">' . h($m[1]) . '</span>' . ($exp && $st !== 'free' ? ' <small class="muted">' . h($x) . '</small>' : '');
}
function hw_form(array $r, string $back): string {
  $hw = (string)($r['hw'] ?? '');
  if (($r['state'] ?? '') === 'pending')
    return '<form method="post" class="licf" style="margin-top:6px">' . csrf() . '<input type="hidden" name="p" value="' . h($back) . '"><input type="hidden" name="id" value="' . h($r['id']) . '">'
      . '<button class="btn sm pri" name="a" value="reg_approve">' . L('Έγκριση', 'Approve') . '</button> <button class="btn sm danger" name="a" value="reg_reject">' . L('Απόρριψη', 'Reject') . '</button></form>';
  return '<form method="post" class="licf" style="margin-top:6px">' . csrf() . '<input type="hidden" name="p" value="' . h($back) . '"><input type="hidden" name="a" value="hw_free"><input type="hidden" name="id" value="' . h($r['id']) . '">'
    . ((int)($r['lic_major'] ?? 0) > 0 ? '<small class="muted">' . L('Άδεια για έκδοση ', 'Licence for version ') . (int)$r['lic_major'] . '.x · </small>' : '')
    . '<small class="muted">' . L('Υπολογιστής: ', 'Computer: ') . ($hw !== '' ? '<span class="mono">' . h(substr($hw, 0, 8)) . '</span>' . ((int)($r['hw_set'] ?? 0) ? ' · ' . h(dc_dt((int)$r['hw_set'])) : '') : L('δεν δηλώθηκε ακόμη', 'not reported yet')) . '</small> '
    . ($hw !== '' ? '<button class="btn sm">' . L('Ελευθέρωση υπολογιστή', 'Free the computer') . '</button>' : '') . '</form>';
}
function lic_form(array $r, string $back): string {
  $u = function ($sel) { return '<select name="unit"><option value="h">' . L('ώρες', 'hours') . '</option><option value="d"' . ($sel === 'd' ? ' selected' : '') . '>' . L('ημέρες', 'days') . '</option><option value="m">' . L('μήνες', 'months') . '</option><option value="y">' . L('χρόνια', 'years') . '</option></select>'; };
  return '<form method="post" class="licf">' . csrf() . '<input type="hidden" name="p" value="' . h($back) . '"><input type="hidden" name="a" value="lic_one"><input type="hidden" name="id" value="' . h($r['id']) . '">'
    . '<select name="do"><option value="demo">' . L('Demo για', 'Demo for') . '</option><option value="extend">' . L('Παράταση κατά', 'Extend by') . '</option><option value="full_until">' . L('Άδεια για', 'Licence for') . '</option><option value="full">' . L('Μόνιμη άδεια', 'Permanent licence') . '</option><option value="free">' . L('Δωρεάν (χωρίς όριο)', 'Free (no limit)') . '</option><option value="lock">' . L('Κλείδωμα', 'Lock') . '</option><option value="default">' . L('Όπως η προεπιλογή', 'As the default') . '</option></select>'
    . '<input name="n" type="number" min="1" value="6" style="width:70px">' . $u('d') . '<button class="btn sm pri">' . L('Εφαρμογή', 'Apply') . '</button></form>';
}

function activity_rows($rows) {
  if (!$rows) return '<p class="muted">' . L('Τίποτα ακόμη.','Nothing yet.') . '</p>';
  $osn = function ($o, $a = '') { $n = ['windows' => 'Windows', 'macos' => 'macOS', 'linux' => 'Linux'][$o] ?? $o; return trim($n . ' ' . $a); };
  // "DC-00003 · SA7SVR" as a link to the installation; a deleted or unknown id is not shown as a code
  $who = function ($id) {
    $r = dc_one('SELECT rowid AS rno, call FROM dc_installs WHERE id=?', [(string)$id]);
    if (!$r) return '<span class="muted">' . L('(εγκατάσταση που δεν υπάρχει πια)', '(an installation that no longer exists)') . '</span>';
    $no = sprintf('DC-%05d', $r['rno']);
    return '<a class="mono" href="?p=installs&q=' . $no . '"><b>' . $no . '</b></a>' . ($r['call'] ? ' · <b>' . h($r['call']) . '</b>' : '');
  };
  $out = '<ul class="act">';
  foreach ($rows as $e) {
    $d = explode('|', (string)$e['detail']); $k = $e['kind']; $c = '';
    switch ($k) {
      case 'install':   $txt = L('Νέα εγκατάσταση ', 'New installation ') . $who($d[0]) . ' · v' . h($d[1] ?? '') . ' · ' . h($osn($d[2] ?? '', $d[3] ?? '')); $c = 'g'; break;
      case 'demo':      $txt = L('Demo ', 'Demo ') . h($d[1] ?? '') . L(' ημέρες · ', ' days · ') . $who($d[0]); $c = 'b'; break;
      case 'licence':   $txt = L('Άδεια ', 'Licence ') . ($d[0] === 'default' || $d[0] === 'reset' ? '<b>' . h($d[0] === 'reset' ? L('προεπιλογή σε υπάρχουσες', 'default applied to existing') : L('νέα προεπιλογή', 'new default')) . '</b> · ' . h($d[1] ?? '') : $who($d[0]) . ' → <b>' . h($d[1] ?? '') . '</b>' . (!empty($d[2]) ? ' → ' . h($d[2]) : '') . (!empty($d[3]) ? ' · <span class="muted">' . h($d[3]) . '</span>' : '')); $c = 'b'; break;
      case 'inbox':     $txt = '✉ ' . L('Μήνυμα από χρήστη: ', 'Message from a user: ') . '<b>' . h($d[0] ?? '') . '</b> · ' . h($d[2] ?? '') . ' · <a href="?p=inbox">' . L('άνοιγμα', 'open') . '</a>'; $c = 'o'; break;
      case 'inbox_reply': $txt = L('Απάντηση σε χρήστη: ', 'Reply to a user: ') . '<b>' . h($d[0] ?? '') . '</b> · ' . h($d[1] ?? ''); $c = 'b'; break;
      case 'chat_new':  $txt = '💬 ' . L('Νέα συνομιλία από τη σελίδα · ', 'New chat from the website · ') . '<b>' . h($d[0] ?? '') . '</b> · ' . h(mb_substr((string)($d[2] ?? ''), 0, 80)) . ' · <a href="?p=chat&t=' . h($d[1] ?? '') . '">' . L('άνοιγμα', 'open') . '</a>'; $c = 'o'; break;
      case 'chat_msg':  $txt = '💬 ' . L('Μήνυμα στη συνομιλία · ', 'Chat message · ') . h(mb_substr((string)($d[1] ?? ''), 0, 80)) . ' · <a href="?p=chat&t=' . h($d[0] ?? '') . '">' . L('άνοιγμα', 'open') . '</a>'; break;
      case 'chat_reply': $txt = L('Απάντηση στη συνομιλία · ', 'Reply in the chat · ') . h(mb_substr((string)($d[1] ?? ''), 0, 80)); $c = 'b'; break;
      case 'chat_delete': $txt = L('Διαγραφή συνομιλίας', 'Chat deleted'); break;
      case 'reinstall_id': $txt = '⚠ ' . L('Επανεγκατάσταση (ίδιο διακριτικό + email): ', 'Reinstall (same callsign + e-mail): ') . $who($d[0]) . ' ' . L('πήρε αυτόματα την άδεια της ', 'automatically took the licence of ') . '<b>' . h(dc_inst_no($d[1] ?? '')) . '</b>' . (!empty($d[4]) ? ' (' . h($d[4]) . ')' : ''); $c = 'o'; break;
      case 'clone': $txt = '⚠ ' . L('Άδεια σε ΑΛΛΟΝ υπολογιστή: ', 'Licence on ANOTHER computer: ') . $who($d[0]) . (!empty($d[2]) ? ' · ' . h($d[2]) : '') . (!empty($d[3]) ? ' · ' . h($d[3]) : ''); $c = 'bad'; break;
      case 'reg_pending': $txt = '⏳ ' . L('Εγγραφή σε αναμονή έγκρισης: ', 'Registration waiting for approval: ') . '<b>' . h($d[1] ?? '') . '</b> · ' . h($d[2] ?? '') . ' · ' . h($d[3] ?? '') . ' · <a href="?p=installs&q=' . h(dc_inst_no($d[0] ?? '')) . '">' . L('έγκριση', 'approve') . '</a>'; $c = 'o'; break;
      case 'reg_approve': $txt = L('Εγγραφή εγκρίθηκε: ', 'Registration approved: ') . '<b>' . h($d[1] ?? '') . '</b> ' . h($d[2] ?? ''); $c = 'g'; break;
      case 'modes': $txt = L('Modes / πολιτικές: ', 'Modes / policies: ') . '<b>' . h($d[0] === 'all' ? L('όλοι', 'everyone') : $d[0] . L(' εγκαταστάσεις', ' installations')) . '</b> · ' . h($d[1] ?? ''); $c = 'b'; break;
      case 'hw_free': $txt = L('Ελευθερώθηκε ο υπολογιστής της ', 'Computer freed for ') . '<b>' . h($d[1] ?? '') . '</b>'; $c = 'b'; break;
      case 'reinstall': $txt = L('Επανεγκατάσταση: ', 'Reinstalled: ') . $who($d[0]) . ' ' . L('πήρε την κατάσταση της ', 'took the state of ') . '<b>' . h(dc_inst_no($d[1] ?? '')) . '</b>'; $c = 'b'; break;
      case 'payment':   $txt = L('Πληρωμή ', 'Payment ') . '<b>' . h($d[1] ?? '') . '</b> · ' . h($d[2] ?? '') . ' · ' . h($d[3] ?? ''); $c = 'g'; break;
      case 'pay_auto':  $txt = '♥ ' . L('Αυτόματη ενεργοποίηση ', 'Automatic activation ') . $who($d[0]) . ' · ' . h($d[2] ?? '') . ' · <span class="mono">' . h($d[3] ?? '') . '</span>'; $c = 'g'; break;
      case 'pay_unmatched': $txt = '♥ ' . L('Πληρωμή ', 'Payment ') . '<b>' . h($d[1] ?? '') . '</b> ' . L('από ', 'from ') . h($d[2] ?? '') . ' — <a href="?p=payments">' . L('χρειάζεται ενεργοποίηση', 'needs activation') . '</a>'; $c = 'o'; break;
      case 'pay_refund': $txt = '⚠ PayPal ' . h($d[1] ?? '') . ' · ' . h($d[0] ?? '') . (!empty($d[2]) ? ' · ' . $who($d[2]) : ''); $c = 'r'; break;
      case 'pay_invalid': $txt = '⚠ ' . L('Μη έγκυρο μήνυμα PayPal ', 'Invalid PayPal message ') . h($e['detail']); $c = 'r'; break;
      case 'pay_skipped': $txt = L('Πληρωμή του HAM Digi αγνοήθηκε ', 'HAM Digi payment ignored ') . h(implode(' · ', array_slice($d, 0, 2))); break;
      case 'mail':      $txt = 'E-mail ' . h($d[0] ?? '') . ' · ' . h($d[1] ?? '') . ' · ' . h($d[2] ?? ''); $c = ($d[0] ?? '') === 'ok' ? '' : 'r'; break;
      case 'code_reuse': $txt = '⚠ ' . L('Ο κωδικός ', 'Code ') . '<b class="mono">' . h($d[1] ?? '') . '</b>' . L(' (της ', ' (of ') . h(dc_inst_no($d[2] ?? '')) . L(') δοκιμάστηκε σε άλλη εγκατάσταση ', ') was tried on another installation ') . $who($d[0]); $c = 'r'; break;
      case 'activate':  $txt = L('Ενεργοποίηση (full) · ', 'Activated (full) · ') . $who($d[0]); $c = 'g'; break;
      case 'lock':      $txt = L('Κλείδωμα · ', 'Locked · ') . $who($d[0]); $c = 'o'; break;
      case 'enable':    $txt = L('Ενεργοποιήθηκε · ', 'Enabled · ') . $who($d[0]); $c = 'g'; break;
      case 'disable':   $txt = L('Απενεργοποιήθηκε · ', 'Disabled · ') . $who($d[0]); $c = 'r'; break;
      case 'del_inst':  $txt = L('Διαγραφή εγκατάστασης ', 'Installation deleted ') . (preg_match('/^DC-\d+$/', $d[0]) ? '<b class="mono">' . h($d[0]) . '</b>' . (!empty($d[1]) ? ' · <b>' . h($d[1]) . '</b>' : '') : ''); $c = 'r'; break;
      case 'redeem':    $txt = L('Κωδικός ', 'Code ') . '<b class="mono">' . h($d[1] ?? '') . '</b>' . L(' χρησιμοποιήθηκε από ', ' used by ') . $who($d[0]); $c = 'g'; break;
      case 'codes_make': $txt = L('Δημιουργία κωδικών: ', 'Codes created: ') . h($e['detail']); $c = 'b'; break;
      case 'rel_upload': $txt = L('Ανέβασμα έκδοσης ', 'Release uploaded ') . '<b>v' . h($e['detail']) . '</b>'; $c = 'b'; break;
      case 'rel_activate': $txt = L('Ενεργή έκδοση ', 'Active release ') . '<b>v' . h($e['detail']) . '</b>'; $c = 'g'; break;
      case 'rel_forceall': $txt = L('Επιβολή σε όλους ', 'Forced to everyone ') . '<b>v' . h($e['detail']) . '</b>'; $c = 'o'; break;
      case 'dl_pkg':    $txt = L('Λήψη αναβάθμισης v', 'Update downloaded v') . h($d[1] ?? '') . (!empty($d[0]) ? ' · ' . $who($d[0]) : ''); $c = ''; break;
      case 'msg_send':  $txt = L('Μήνυμα προς τους χρήστες: ', 'Message to users: ') . '<b>' . h($e['detail']) . '</b>'; $c = 'b'; break;
      case 'hostsync':  $txt = L('Ανανέωση λιστών servers · ', 'Server lists refreshed · ') . h(preg_replace('/^[^·]*·\s*/u', '', (string)$e['detail'])); $c = ''; break;
      case 'webdl':     $txt = L('Λήψη από τη σελίδα · ', 'Website download · ') . '<b>' . h($d[0] ?? '') . '</b> · ' . h($osn($d[1] ?? '')); $c = 'b'; break;
      case 'admin_login': $txt = L('Είσοδος στο panel', 'Panel sign-in') . ' · <span class="mono">' . h($e['detail']) . '</span>'; break;
      case 'admin_login_failed': $txt = '⚠ ' . L('Αποτυχημένη είσοδος στο panel', 'Failed panel sign-in') . ' · <span class="mono">' . h($e['detail']) . '</span>'; $c = 'r'; break;
      default:          $txt = h($k) . ' ' . h(preg_match('/^[0-9a-f]{24,}$/', (string)$e['detail']) ? '' : $e['detail']);
    }
    $out .= '<li class="' . $c . '"><span class="t">' . dc_dt($e['t']) . '</span><span>' . $txt . '</span></li>';
  }
  return $out . '</ul>';
}

function head($title) {
  global $LANG; ?><!doctype html><html lang="<?= $LANG ?>"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title><?= h($title) ?> · DigiConnect Control Panel</title><meta name="robots" content="noindex"><link rel="icon" type="image/png" href="../assets/hz-emblem.png"><link rel="apple-touch-icon" href="../assets/hz-emblem.png"><script>try{var t=localStorage.getItem("dc_theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}</script><?php css(); ?></head><body><?php }

function login_page($err = '') {
  global $LANG; head('DigiConnect Admin'); ?>
  <div class="loginwrap"><form method="post" class="loginbox">
    <div class="logo-c"><img src="../assets/digiconnect-logo.png" alt="DigiConnect" onerror="this.style.display='none'"><b>DigiConnect <span>Admin</span></b><small>HELLAS Zone Net · <?= L('Πίνακας ελέγχου','Control panel') ?></small></div>
    <?php if ($err) echo '<div class="flash bad">' . h($err) . '</div>'; ?>
    <label><?= L('Χρήστης','User') ?><input name="u" id="lu" autocomplete="username" autofocus></label>
    <label><?= L('Κωδικός','Password') ?><input name="p" id="lp" type="password" autocomplete="current-password"></label>
    <label class="chk"><input type="checkbox" name="remember" value="1" id="lr" checked> <?= L('Να με θυμάται σε αυτόν τον υπολογιστή (180 ημέρες)','Remember me on this computer (180 days)','Kom ihåg mig på den här datorn (180 dagar)') ?></label>
    <script>try{var u=localStorage.getItem("dc_user");if(u){document.getElementById("lu").value=u;document.getElementById("lp").focus()}document.querySelector(".loginbox").addEventListener("submit",function(){try{document.getElementById("lr").checked?localStorage.setItem("dc_user",document.getElementById("lu").value):localStorage.removeItem("dc_user")}catch(e){}})}catch(e){}</script>
    <button class="btn pri" name="login" value="1"><?= L('Είσοδος','Sign in') ?></button>
  </form></div>
  <style>body{display:block}.loginwrap{min-height:100vh;display:grid;place-items:center;padding:20px}.loginbox{width:360px;max-width:92vw;background:var(--card);border:1px solid var(--line2);border-radius:18px;padding:30px 26px;display:flex;flex-direction:column;gap:14px;box-shadow:var(--shadow)}.logo-c{text-align:center;margin-bottom:6px}.logo-c img{height:58px;margin-bottom:10px}.logo-c b{display:block;font-size:22px}.logo-c b span{color:var(--acc)}.logo-c small{color:var(--muted);font-size:13px}</style>
  </body></html><?php
}

function css() { ?><style>.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin:12px 0}.mcard{border:1px solid var(--line2);border-radius:12px;padding:12px;background:var(--bg2);display:flex;flex-direction:column;gap:10px}.mcard.on{border-color:color-mix(in srgb,var(--rx) 55%,transparent)}.mcard.off{opacity:.92}.mcard .mh{display:flex;justify-content:space-between;align-items:center;font-size:16px}.seg{display:flex;gap:4px}.seg button{flex:1;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;border:1px solid var(--line2);background:transparent;color:var(--text);border-radius:8px;padding:7px 4px}.seg button:hover{border-color:var(--acc)}.seg button.sel.on{background:var(--rx);border-color:var(--rx);color:#04140f}.seg button.sel.off{background:var(--bad);border-color:var(--bad);color:#fff}.seg button.sel.beta{background:var(--tx);border-color:var(--tx);color:#1b1200}.mall{display:flex;gap:8px}.mbar{display:flex;flex-wrap:wrap;gap:14px 22px;margin:12px 0}.mbar>div{display:flex;flex-direction:column;gap:6px}.mchk{display:flex;flex-wrap:wrap;gap:4px 12px}.mchk .chk{display:flex;flex-direction:row;gap:5px;align-items:center}.dot{display:inline-block;width:12px;height:12px;border-radius:50%}.dot.on{background:var(--rx)}.dot.off{background:var(--line2)}th.mh2{font-size:11px}

:root{--bg:#070a10;--bg2:#0c111a;--card:#101722;--line:#1f2a3a;--line2:#2b3a50;--text:#e8eef5;--muted:#8d9cb0;--acc:#17c0a8;--acc2:#3cc8ff;--rx:#3ee08b;--tx:#ffad42;--bad:#ff5a6e;--mono:ui-monospace,Menlo,Consolas,monospace;--card2:#131c2a;--shadow:0 1px 0 rgba(255,255,255,.04) inset,0 8px 24px rgba(0,0,0,.35);color-scheme:dark}
@media (prefers-color-scheme:light){:root:not([data-theme=dark]){--bg:#eef2f7;--bg2:#fff;--card:#fff;--line:#d9e1ea;--line2:#c3cfdc;--text:#111a26;--muted:#56677c;--acc:#0e9e8a;--acc2:#0a84c6;--rx:#14894d;--tx:#b96400;--bad:#c22a40;--card2:#f6f8fb;--shadow:0 1px 2px rgba(16,24,40,.06),0 6px 18px rgba(16,24,40,.06);color-scheme:light}}
:root[data-theme=light]{--bg:#eef2f7;--bg2:#fff;--card:#fff;--line:#d9e1ea;--line2:#c3cfdc;--text:#111a26;--muted:#56677c;--acc:#0e9e8a;--acc2:#0a84c6;--rx:#14894d;--tx:#b96400;--bad:#c22a40;--card2:#f6f8fb;--shadow:0 1px 2px rgba(16,24,40,.06),0 6px 18px rgba(16,24,40,.06);color-scheme:light}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 500px at 70% -200px,color-mix(in srgb,var(--acc) 10%,transparent),transparent 70%),var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif;display:grid;grid-template-columns:230px minmax(0,1fr);min-height:100vh}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
aside{background:linear-gradient(180deg,var(--bg2),color-mix(in srgb,var(--bg2) 85%,var(--acc) 15%));border-right:1px solid var(--line2);padding:18px 12px;display:flex;flex-direction:column;gap:18px;position:sticky;top:0;height:100vh}
.logo b{display:block;font-size:22px;letter-spacing:.02em;background:linear-gradient(90deg,var(--text),var(--acc));-webkit-background-clip:text;background-clip:text;color:transparent}.logo small{color:var(--acc);font-weight:600;font-size:12px}
nav{display:flex;flex-direction:column;gap:4px}nav a{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:9px;color:var(--text);border:1px solid transparent;font-weight:600}nav a span{flex:1}nav a:hover{border-color:var(--line2);background:color-mix(in srgb,var(--acc) 7%,transparent);text-decoration:none}nav a.on{border-color:color-mix(in srgb,var(--acc) 55%,transparent);background:color-mix(in srgb,var(--acc) 16%,transparent);color:var(--text);box-shadow:inset 3px 0 0 var(--acc)}
nav svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.nb{min-width:22px;height:22px;padding:0 7px;border-radius:999px;display:inline-grid;place-items:center;font:700 12px var(--mono);color:#fff;background:var(--muted)}.nb.r{background:var(--bad)}.nb.o{background:var(--tx);color:#1b1205}.nb.g{background:var(--rx);color:#062615}
.side-f{margin-top:auto;display:flex;flex-direction:column;gap:10px}.lang{display:flex;gap:4px}.lang a{padding:3px 9px;border:1px solid var(--line2);border-radius:7px;color:var(--muted);font-size:12px}.lang a.on{color:var(--acc);border-color:var(--acc)}.logout{color:var(--muted);font-size:13px}
main{padding:22px 26px 40px;max-width:1280px;width:100%}h1{margin:0;font-size:28px}h2{margin:0 0 12px;font-size:16px}h2 small{color:var(--muted);font-weight:500;font-size:13px}
.ph{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:0 0 18px;padding-bottom:14px;border-bottom:1px solid var(--line)}.ph p{margin:4px 0 0}
.strip{display:flex;flex-wrap:wrap;gap:8px}.st{display:inline-flex;align-items:center;gap:7px;padding:5px 12px;border:1px solid var(--line2);border-radius:999px;font-size:13px;font-weight:600;color:var(--text);background:var(--card);text-decoration:none!important}.st i{width:8px;height:8px;border-radius:50%;background:var(--muted)}.st.ok i{background:var(--rx);box-shadow:0 0 0 3px color-mix(in srgb,var(--rx) 25%,transparent)}.st.bad{border-color:var(--bad)}.st.bad i{background:var(--bad)}a.st:hover{border-color:var(--acc)}
.card{background:var(--card);border:1px solid var(--line2);border-radius:16px;padding:18px 20px;margin-bottom:16px;box-shadow:var(--shadow);min-width:0}.card>h2{display:flex;align-items:center;gap:8px;padding-bottom:10px;margin-bottom:14px;border-bottom:1px solid var(--line)}.card>h2::before{content:'';width:4px;height:18px;border-radius:3px;background:var(--acc)}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:16px}.kpi{position:relative;overflow:hidden;background:var(--card);border:1px solid var(--line2);border-radius:16px;padding:16px;box-shadow:var(--shadow)}.kpi::before{content:'';position:absolute;left:0;top:0;right:0;height:3px;background:var(--acc)}.kpi.g::before{background:var(--rx)}.kpi.o::before{background:var(--tx)}.kpi.r::before{background:var(--bad)}.kpi.r b{color:var(--bad)}.kpi span{display:block;color:var(--muted);font-size:12px}.kpi b{display:block;font-size:30px;line-height:1.2;margin:4px 0;font-variant-numeric:tabular-nums;letter-spacing:-.02em}.kpi.g b{color:var(--rx)}.kpi.o b{color:var(--tx)}.kpi small{color:var(--muted);font-size:12px}
.shares{display:flex;flex-direction:column;gap:8px}.sh{display:grid;grid-template-columns:120px 1fr 50px;gap:10px;align-items:center}.sl{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--mono)}.sb{height:10px;background:var(--line);border-radius:6px;overflow:hidden}.sb i{display:block;height:100%;background:var(--acc);border-radius:6px}.sh.hl .sb i{background:var(--rx)}.sh.hl .sl{color:var(--rx);font-weight:600}.sv{text-align:right;font-variant-numeric:tabular-nums}
.muted{color:var(--muted)}.bad{color:var(--bad)}.mono{font-family:var(--mono)}.more{display:inline-block;margin-top:10px}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;background:var(--line);color:var(--muted)}.pill.ok{background:color-mix(in srgb,var(--rx) 20%,transparent);color:var(--rx)}.pill.o{background:color-mix(in srgb,var(--tx) 20%,transparent);color:var(--tx)}.pill.bad{background:color-mix(in srgb,var(--bad) 20%,transparent);color:var(--bad)}.pill.dim{opacity:.7}.pill.onl{display:inline-flex;align-items:center;gap:6px}.pill.onl i{width:8px;height:8px;border-radius:50%;background:var(--muted)}.pill.onl.ok i{background:var(--rx);box-shadow:0 0 0 3px color-mix(in srgb,var(--rx) 30%,transparent)}
.act{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}.act li{display:grid;grid-template-columns:150px 1fr;gap:10px;padding:7px 0 7px 10px;border-bottom:1px solid var(--line);border-left:3px solid var(--line2)}.act li.g{border-left-color:var(--rx)}.act li.b{border-left-color:var(--acc)}.act li.o{border-left-color:var(--tx)}.act li.r{border-left-color:var(--bad)}.act .t{color:var(--muted);font-size:12.5px}
.form{display:flex;flex-direction:column;gap:12px}.g2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
label{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:13px}label.chk{flex-direction:row;align-items:center;gap:8px;color:var(--text)}
input,select,textarea{font:inherit;color:var(--text);background:var(--bg);border:1px solid var(--line2);border-radius:9px;padding:8px 10px;min-width:0}input[type=file]{padding:6px}input[type=checkbox]{width:17px;height:17px;accent-color:var(--acc)}input:focus,select:focus,textarea:focus{outline:2px solid var(--acc);outline-offset:1px}
.btn{font:inherit;font-weight:600;cursor:pointer;border-radius:9px;padding:8px 16px;border:1px solid var(--line2);background:var(--bg2);color:var(--text);align-self:flex-start}.btn:hover{border-color:var(--acc)}.btn.pri{background:linear-gradient(135deg,var(--acc),var(--acc2));border:0;color:#04140f}.btn.danger{border-color:var(--bad);color:var(--bad)}.btn.danger:hover{background:color-mix(in srgb,var(--bad) 12%,transparent)}.btn.sm{padding:5px 12px;font-size:13px}
.help{background:color-mix(in srgb,var(--acc) 9%,transparent);border:1px solid color-mix(in srgb,var(--acc) 30%,transparent);border-radius:10px;padding:10px 12px;font-size:13px;color:var(--text)}
.flash{border-radius:10px;padding:11px 14px;margin-bottom:16px;border:1px solid}.flash.ok{border-color:var(--rx);color:var(--rx);background:color-mix(in srgb,var(--rx) 10%,transparent)}.flash.bad{border-color:var(--bad);color:var(--bad);background:color-mix(in srgb,var(--bad) 10%,transparent)}
.relrow{border:1px solid var(--line2);border-radius:12px;margin-bottom:10px}.relrow summary{display:flex;align-items:center;gap:12px;padding:10px 14px;cursor:pointer;list-style:none;flex-wrap:wrap}.relrow summary::-webkit-details-marker{display:none}.relrow.active{border-color:var(--rx)}.relrow .ver{font-size:18px;font-family:var(--mono)}.relbody{padding:0 14px 14px}
.acts{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.acts form{margin:0}.ro{display:flex;gap:6px;align-items:center}.ro input{width:70px}
.notes{white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px;font:13px/1.5 system-ui;margin:10px 0 0}
.tw{overflow:auto;max-height:min(640px,72vh)}.tbl{width:100%;border-collapse:collapse;font-size:13.5px}.tbl th{position:sticky;top:0;background:var(--card);text-align:left;color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;padding:7px 10px;border-bottom:1px solid var(--line2)}.tbl td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}.tbl tr:hover td{background:color-mix(in srgb,var(--acc) 5%,transparent)}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}.filters input,.filters select{height:36px}
.licf{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap}.licf label{font-size:12px}
.empty{padding:14px;border:1px dashed var(--line2);border-radius:12px;color:var(--rx);font-weight:600;text-align:center}
.stns{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:10px}
.stn{display:grid;grid-template-columns:46px 1fr;gap:10px;padding:12px;border:1px solid var(--line2);border-radius:14px;background:var(--card2)}
.stn.on{border-color:color-mix(in srgb,var(--rx) 45%,var(--line2))}.stn.off{opacity:.68}
.stn-ic{width:46px;height:46px;border-radius:12px;background:var(--bg);display:grid;place-items:center;font:700 12px var(--mono);color:var(--muted)}.stn.on .stn-ic{color:var(--rx)}
.stn-b{min-width:0}.stn-h{display:flex;align-items:center;gap:8px}.stn-h b{font-size:16px;letter-spacing:.02em}
.stn-n{color:var(--muted);font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stn-s{font-size:12px;margin-top:3px}.stn-m{color:var(--muted);font-size:11px;font-family:var(--mono);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lang.theme a{min-width:34px;text-align:center}
.bars{display:flex;align-items:flex-end;gap:3px;height:140px;padding-top:6px}.bars span{flex:1;height:100%;display:flex;align-items:flex-end;background:color-mix(in srgb,var(--line) 55%,transparent);border-radius:3px}.bars i{display:block;width:100%;background:var(--acc);border-radius:3px 3px 0 0}.bars.o i{background:var(--tx)}.bars.g i{background:var(--rx)}
.act .mono{white-space:nowrap}
.bax{display:flex;justify-content:space-between;color:var(--muted);font:11px var(--mono);margin-top:4px}
.rail{display:none}
@media (min-width:1280px){body{grid-template-columns:230px minmax(0,1280px) 320px;justify-content:start}.rail{display:block;position:sticky;top:0;height:100vh;overflow:auto;padding:18px 12px;border-left:1px solid var(--line2);background:var(--bg2)}}
.rail-h{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.rail-h h3{margin:0 auto 0 0;font-size:16px;color:var(--text);font-weight:700}
.rn{font-size:12px;color:var(--muted);display:inline-flex;align-items:center;gap:5px}.rn i,.rs i{width:8px;height:8px;border-radius:50%;background:var(--muted);display:inline-block}
.rn.on{color:var(--rx);font-weight:600}.rn.on i,.rs.on i{background:var(--rx);animation:rpulse 2s infinite}
@keyframes rpulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--rx) 55%,transparent)}70%{box-shadow:0 0 0 7px transparent}100%{box-shadow:0 0 0 0 transparent}}
.rail-s{font-size:11px;color:var(--muted);margin:2px 0 10px}.rail-e{color:var(--muted);font-size:13px;padding:10px 0}
.rail-t{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:16px 0 6px;padding-top:10px;border-top:1px solid var(--line)}
.rc{display:grid;grid-template-columns:60px minmax(0,1fr);gap:10px;align-items:start;padding:10px;border:1px solid var(--line);border-radius:12px;margin-bottom:8px;color:var(--text);background:var(--card)}
.rc:hover{text-decoration:none;border-color:var(--acc)}.rc.on{border-color:color-mix(in srgb,var(--rx) 45%,var(--line))}.rc.tx{border-color:var(--tx)}.rc.off{opacity:.78}
.rb{min-width:0}.r1{display:flex;align-items:center;gap:8px}.r1 b{font-size:15px;letter-spacing:.02em}
.rs{margin-left:auto;font-size:11px;display:inline-flex;align-items:center;gap:5px;color:var(--muted);border:1px solid var(--line2);border-radius:999px;padding:1px 8px}.rs.on{color:var(--rx);border-color:color-mix(in srgb,var(--rx) 50%,transparent)}
.r2{font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.r3{font-size:12.5px;margin-top:3px}.rc.on .r3{color:var(--rx)}.rc.tx .r3{color:var(--tx);font-weight:600}.rc.off .r3{color:var(--muted)}
.r4{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pcw{display:flex;flex-direction:column;align-items:center;gap:2px}.pcw small{font-size:9.5px;color:var(--muted);letter-spacing:.03em}.rc.on .pcw small{color:var(--acc)}
.trx{width:58px;height:50px}.trx .fr{fill:color-mix(in srgb,var(--muted) 30%,var(--card));stroke:var(--line2);stroke-width:1.2}.trx .an{stroke:var(--muted);stroke-width:1.6;stroke-linecap:round;fill:none}.trx .an-t{fill:var(--muted)}
.trx .sc{fill:#06131c}.trx .sc.off{fill:color-mix(in srgb,var(--muted) 18%,var(--bg))}.trx .kn{fill:color-mix(in srgb,var(--muted) 45%,var(--card));stroke:var(--line2)}.trx .kn-l{stroke:var(--text);stroke-width:1.5;stroke-linecap:round}
.trx .gr,.trx .zz{stroke:var(--muted);stroke-width:1.4;stroke-linecap:round;fill:none}
.trx.on .fr{fill:color-mix(in srgb,var(--acc) 22%,var(--card));stroke:color-mix(in srgb,var(--acc) 55%,var(--line2))}.trx.on .an,.trx.on .an-t{stroke:var(--rx);fill:var(--rx)}.trx.on .an{fill:none}
.trx.tx .fr{fill:color-mix(in srgb,var(--tx) 24%,var(--card));stroke:var(--tx)}.trx.tx .an{stroke:var(--tx);fill:none}.trx.tx .an-t{fill:var(--tx);animation:rwf 1s infinite}
.trx .wf rect{fill:var(--rx);animation:rwf 2.4s ease-in-out infinite}.trx .wf rect:nth-child(2){animation-delay:.6s;fill:var(--acc)}.trx .wf rect:nth-child(3){animation-delay:1.2s}.trx .wf rect:nth-child(4){animation-delay:1.8s;fill:var(--tx)}
.trx.tx .wf rect{fill:var(--tx)!important;animation-duration:.7s}.trx .txl{font:700 8px var(--mono);fill:var(--tx)}
@keyframes rwf{0%,100%{opacity:.25}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){.trx .wf rect,.trx .an-t,.rn.on i,.rs.on i{animation:none}}
@media (max-width:820px){.bars{height:110px}}
footer{color:var(--muted);font-size:12px;margin-top:20px}
@media (max-width:1100px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:820px){body{grid-template-columns:1fr}aside{position:static;height:auto}nav{flex-direction:row;flex-wrap:wrap}.grid2,.g2{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:16px}}
</style><?php }
