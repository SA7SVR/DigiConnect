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

  if (!$flash) $flash = ['ok', 'OK'];
  $_SESSION['dc_flash'] = $flash;
  header('Location: ?p=' . ($_POST['p'] ?? 'dashboard')); exit;
}
if (!empty($_SESSION['dc_flash'])) { $flash = $_SESSION['dc_flash']; unset($_SESSION['dc_flash']); }

/* ---- page ---- */
$p = $_GET['p'] ?? 'dashboard';
$PAGES = ['dashboard' => L('Επισκόπηση','Overview','Översikt'), 'stats' => L('Στατιστικά','Statistics','Statistik'), 'releases' => L('Εκδόσεις','Releases','Versioner'),
  'installs' => L('Εγκαταστάσεις','Installations','Installationer'), 'downloads' => L('Λήψεις / Εγγραφές','Downloads / Sign-ups','Nedladdningar'),
  'licenses' => L('Άδειες / Κωδικοί','Licences / Codes','Licenser'), 'payments' => L('Πληρωμές','Payments','Betalningar'), 'servers' => L('Servers / Λίστες','Servers / Host lists','Servrar'), 'messages' => L('Μηνύματα','Messages','Meddelanden'),
  'activity' => L('Δραστηριότητα','Activity','Aktivitet'), 'settings' => L('Ρυθμίσεις','Settings','Inställningar')];
if (!isset($PAGES[$p])) $p = 'dashboard';

if (!$auth) { login_page($login_err ?? ''); exit; }
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
 'payments' => 'M3 6h18v12H3zM3 10h18M7 15h3',
 'servers' => 'M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01',
 'messages' => 'M4 5h16v11H8l-4 4z',
 'activity' => 'M3 12h4l3 7 4-14 3 7h4',
 'settings' => 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z'];
$seenA = (int)dc_kv('alerts_seen', 0); $phA = implode(',', array_fill(0, count(DC_ALERTS), '?'));
$BADGE = ['dashboard' => [(int)dc_one("SELECT COUNT(*) c FROM dc_events WHERE kind IN ($phA) AND t>?", array_merge(DC_ALERTS, [$seenA]))['c'], 'o'],
  'payments' => [(int)dc_one("SELECT COUNT(*) c FROM dc_payments WHERE status='Completed' AND (install IS NULL OR install='')")['c'], 'o'],
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
  'payments' => L('Δωρεές PayPal, ποιος πληρώνει και πόσα (€ και SEK ξεχωριστά) και αυτόματη ενεργοποίηση.','PayPal donations, who pays and how much (EUR and SEK separately) and automatic activation.'),
  'messages' => L('Μήνυμα σε όλους ή σε μία εγκατάσταση — εμφανίζεται μέσα στο πρόγραμμα.','A message to everyone or one installation — it shows inside the program.'),
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
       . lic_form($r, 'installs')
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
  $m = ['free' => ['ok', L('Δωρεάν', 'Free')], 'full' => ['ok', L('Μόνιμη άδεια', 'Licensed')], 'demo' => ['o', 'Demo'], 'locked' => ['bad', L('Κλειδωμένο', 'Locked')], 'expired' => ['bad', L('Έληξε', 'Expired')]][$st] ?? ['', $st];
  return '<span class="pill ' . $m[0] . '">' . h($m[1]) . '</span>' . ($exp && $st !== 'free' ? ' <small class="muted">' . h($x) . '</small>' : '');
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

function css() { ?><style>
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
