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
dc_db()->exec("CREATE TABLE IF NOT EXISTS dc_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, t INT, scope TEXT, target TEXT, title TEXT, body TEXT, active INT DEFAULT 1)");

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
  if ($a === 'demo')     { $d = max(1, (int)($_POST['days'] ?? 7)); dc_q("UPDATE dc_installs SET state='demo', demo_until=?, enabled=1 WHERE id=?", [time() + 86400 * $d, $iid]); dc_event('demo', "$iid|$d"); flash('ok', L("Demo $d ημέρες", "Demo $d days")); }
  if ($a === 'activate') { dc_q("UPDATE dc_installs SET state='full', enabled=1, lic_by='admin', lic_set=? WHERE id=?", [time(), $iid]); dc_event('activate', $iid); flash('ok', L('Ενεργοποιήθηκε (full)', 'Activated (full)')); }
  if ($a === 'lock')     { dc_q("UPDATE dc_installs SET state='locked' WHERE id=?", [$iid]); dc_event('lock', $iid); flash('ok', L('Κλειδώθηκε', 'Locked')); }
  if ($a === 'enable')   { dc_q("UPDATE dc_installs SET enabled=1 WHERE id=?", [$iid]); dc_event('enable', $iid); flash('ok', L('Ενεργό', 'Enabled')); }
  if ($a === 'disable')  { dc_q("UPDATE dc_installs SET enabled=0, state='disabled' WHERE id=?", [$iid]); dc_event('disable', $iid); flash('ok', L('Απενεργοποιήθηκε', 'Disabled')); }
  if ($a === 'note')     { dc_q("UPDATE dc_installs SET note=? WHERE id=?", [$_POST['note'] ?? '', $iid]); flash('ok', L('Σημείωση αποθηκεύτηκε', 'Note saved')); }
  if ($a === 'ident')    { dc_q("UPDATE dc_installs SET call=?, name=?, mail=? WHERE id=?", [strtoupper(trim($_POST['call'] ?? '')), trim($_POST['name'] ?? ''), trim($_POST['mail'] ?? ''), $iid]); flash('ok', L('Στοιχεία ενημερώθηκαν', 'Details updated')); }
  if ($a === 'del_inst') { dc_q("DELETE FROM dc_installs WHERE id=?", [$iid]); dc_event('del_inst', $iid); flash('ok', L('Διαγράφηκε', 'Deleted')); }
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
  // codes
  if ($a === 'codes_make') {
    $kind = ($_POST['kind'] ?? '') === 'full' ? 'full' : 'demo';
    $n = max(1, min(200, (int)($_POST['count'] ?? 1)));
    $made = [];
    for ($i = 0; $i < $n; $i++) {
      $code = strtoupper(bin2hex(random_bytes(2)) . '-' . bin2hex(random_bytes(2)) . '-' . bin2hex(random_bytes(2)));
      dc_q("INSERT INTO dc_codes(code,kind,dur,unit,uses,used,created,note) VALUES(?,?,?,?,?,0,?,?)",
        [$code, $kind, (int)($_POST['dur'] ?? 0), $_POST['unit'] ?? 'days', max(1, (int)($_POST['uses'] ?? 1)), time(), $_POST['note'] ?? '']);
      $made[] = $code;
    }
    dc_event('codes_make', "$kind x$n"); flash('ok', L('Δημιουργήθηκαν κωδικοί: ', 'Codes created: ') . implode(', ', $made));
  }
  if ($a === 'code_del') { dc_q("DELETE FROM dc_codes WHERE code=?", [$_POST['code']]); flash('ok', L('Κωδικός διαγράφηκε', 'Code deleted')); }
  // messages
  if ($a === 'msg_send') {
    dc_q("INSERT INTO dc_messages(t,scope,target,title,body,active) VALUES(?,?,?,?,?,1)",
      [time(), ($_POST['scope'] ?? 'all'), trim($_POST['target'] ?? ''), trim($_POST['title'] ?? ''), trim($_POST['body'] ?? '')]);
    dc_event('msg_send', $_POST['title'] ?? ''); flash('ok', L('Το μήνυμα στάλθηκε', 'Message sent'));
  }
  if ($a === 'msg_off') { dc_q("UPDATE dc_messages SET active=0 WHERE id=?", [(int)$_POST['mid']]); flash('ok', L('Το μήνυμα απενεργοποιήθηκε', 'Message deactivated')); }
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
  if ($a === 'set_pause') { dc_kv_set('paused', ($_POST['paused'] ?? '') === '1' ? '1' : '0'); flash('ok', L('Κατάσταση ενημερώσεων ενημερώθηκε', 'Update pause updated')); }

  if (!$flash) $flash = ['ok', 'OK'];
  $_SESSION['dc_flash'] = $flash;
  header('Location: ?p=' . ($_POST['p'] ?? 'dashboard')); exit;
}
if (!empty($_SESSION['dc_flash'])) { $flash = $_SESSION['dc_flash']; unset($_SESSION['dc_flash']); }

/* ---- page ---- */
$p = $_GET['p'] ?? 'dashboard';
$PAGES = ['dashboard' => L('Επισκόπηση','Overview','Översikt'), 'stats' => L('Στατιστικά','Statistics','Statistik'), 'releases' => L('Εκδόσεις','Releases','Versioner'),
  'installs' => L('Εγκαταστάσεις','Installations','Installationer'), 'downloads' => L('Λήψεις / Εγγραφές','Downloads / Sign-ups','Nedladdningar'),
  'licenses' => L('Άδειες / Κωδικοί','Licences / Codes','Licenser'), 'servers' => L('Servers / Λίστες','Servers / Host lists','Servrar'), 'messages' => L('Μηνύματα','Messages','Meddelanden'),
  'activity' => L('Δραστηριότητα','Activity','Aktivitet'), 'settings' => L('Ρυθμίσεις','Settings','Inställningar')];
if (!isset($PAGES[$p])) $p = 'dashboard';

if (!$auth) { login_page($login_err ?? ''); exit; }
if (isset($_GET['rail'])) { header('Content-Type: text/html; charset=utf-8'); header('Cache-Control: no-store'); echo rail_html(); exit; }

/* counts for the sidebar badges */
$ceMin = (int)round(((int)dc_kv('check_every', $cfg['check_every'])) / 60);
$gate  = dc_kv('gate', $cfg['gate'] ? '1' : '0');
$paused = dc_kv('paused', '0') === '1';
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
 'servers' => 'M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01',
 'messages' => 'M4 5h16v11H8l-4 4z',
 'activity' => 'M3 12h4l3 7 4-14 3 7h4',
 'settings' => 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z'];
$BADGE = ['installs' => [$onNow, 'g'], 'downloads' => [(int)dc_one("SELECT COUNT(*) c FROM dc_webdl WHERE t>=?", [time() - 7*86400])['c'], 'o']];
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
  'messages' => L('Μήνυμα σε όλους ή σε μία εγκατάσταση — εμφανίζεται μέσα στο πρόγραμμα.','A message to everyone or one installation — it shows inside the program.'),
  'activity' => L('Όλα όσα έγιναν, με τη σειρά.','Everything that happened, in order.'),
  'settings' => L('Ενημερώσεις, έλεγχος άδειας και συντήρηση.','Updates, licence gate and maintenance.')];
echo '<header class="ph"><div><h1>' . h($PAGES[$p]) . '</h1><p class="muted">' . h($SUB[$p] ?? '') . '</p></div><div class="strip">'
  . '<span class="st ' . ($paused ? 'bad' : ($act ? 'ok' : '')) . '"><i></i>' . ($paused ? L('σε παύση','paused') : ($act ? 'v' . h($act['version']) . ' ' . L('ενεργή','active') : L('καμία έκδοση','no release'))) . '</span>'
  . '<span class="st ' . ($onNow ? 'ok' : '') . '"><i></i>' . $onNow . L(' σε σύνδεση',' online') . '</span>'
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
  echo '<div class="kpis">'
    . $kpi(L('Εγκαταστάσεις','Installations'), $total, L('συνολικά','total'))
    . $kpi(L('Σε σύνδεση','Online'), $onNow, L('στέλνουν σήμα τώρα','sending a signal now'), 'g')
    . $kpi(L('Demo','Demo'), $demo, '', 'o')
    . $kpi(L('Ενεργές','Licensed'), $full, 'full', 'g')
    . $kpi(L('Κλειδωμένες','Locked'), $lock, '', $lock?'r':'')
    . $kpi(L('Λήψεις 7 ημ.','Downloads 7d'), $dl7, L('από τη σελίδα','from website'))
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
  $stn = dc_q("SELECT * FROM dc_installs ORDER BY (COALESCE(last_ping,0)>=" . (time()-DC_ONLINE_S) . ") DESC, MAX(COALESCE(last_ping,0),COALESCE(last_seen,0)) DESC LIMIT 60")->fetchAll();
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
  if ($qf !== '') { $w[] = '(call LIKE ? OR id LIKE ? OR name LIKE ? OR mail LIKE ?)'; array_push($args, "%$qf%", "%$qf%", "%$qf%", "%$qf%"); }
  if (in_array($sf, ['demo','full','locked','disabled'], true)) { $w[] = 'state=?'; $args[] = $sf; }
  $where = $w ? ('WHERE ' . implode(' AND ', $w)) : '';
  $rows = dc_q("SELECT * FROM dc_installs $where ORDER BY last_seen DESC LIMIT 500", $args)->fetchAll();
  echo '<section class="card"><h2>' . L('Εγκαταστάσεις','Installations') . ' <small>(' . count($rows) . ')</small></h2>'
    . '<form class="filters" method="get"><input type="hidden" name="p" value="installs"><input name="q" value="' . h($qf) . '" placeholder="' . L('callsign, ID, email…','callsign, ID, email…') . '">'
    . '<select name="st"><option value="">' . L('όλες','all') . '</option>'
    . '<option value="demo"' . ($sf==='demo'?' selected':'') . '>demo</option><option value="full"' . ($sf==='full'?' selected':'') . '>full</option><option value="locked"' . ($sf==='locked'?' selected':'') . '>locked</option><option value="disabled"' . ($sf==='disabled'?' selected':'') . '>disabled</option></select>'
    . '<button class="btn sm">' . L('Φίλτρο','Filter') . '</button></form>'
    . '<div class="tw"><table class="tbl"><tr><th>' . L('Διακριτικό / ID','Callsign / ID') . '</th><th>' . L('Έκδοση','Version') . '</th><th>OS</th><th>' . L('Κατάσταση','State') . '</th><th>' . L('Τελευταία','Last seen') . '</th><th style="width:38%">' . L('Ενέργειες','Actions') . '</th></tr>';
  foreach ($rows as $r) {
    list($st, $lf) = dc_state($r);
    $online = dc_online($r);
    echo '<tr><td><b>' . h($r['call'] ?: '—') . '</b><br><span class="muted mono" style="font-size:11px">' . h(substr($r['id'], 0, 16)) . '</span>'
       . ($r['name'] ? '<br><span class="muted" style="font-size:11px">' . h($r['name']) . '</span>' : '') . '</td>'
       . '<td>' . h($r['version'] ?: '—') . '</td><td>' . h($r['os'] ?: '—') . '</td>'
       . '<td><span class="pill onl ' . ($online?'ok':'') . '"><i></i>' . h($st) . ($lf ? ' · ' . h($lf) : '') . '</span></td>'
       . '<td class="muted">' . dc_dt(dc_last($r)) . '</td><td><div class="acts">'
       . '<form method="post" class="ro">' . csrf() . '<input type="hidden" name="p" value="installs"><input type="hidden" name="iid" value="' . h($r['id']) . '"><input type="number" name="days" value="7" title="days"><button class="btn sm" name="a" value="demo">Demo</button></form>'
       . '<form method="post">' . csrf() . '<input type="hidden" name="p" value="installs"><input type="hidden" name="iid" value="' . h($r['id']) . '"><button class="btn sm" name="a" value="activate">' . L('Ενεργ.','Activate') . '</button></form>'
       . '<form method="post">' . csrf() . '<input type="hidden" name="p" value="installs"><input type="hidden" name="iid" value="' . h($r['id']) . '"><button class="btn sm" name="a" value="lock">' . L('Κλείδ.','Lock') . '</button></form>'
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

/* ===================== LICENCES / CODES ===================== */
elseif ($p === 'licenses') {
  echo '<section class="card"><h2>' . L('Δημιουργία κωδικών','Create codes') . '</h2>'
    . '<form class="licf" method="post">' . csrf() . '<input type="hidden" name="p" value="licenses"><input type="hidden" name="a" value="codes_make">'
    . '<label>' . L('Τύπος','Type') . '<select name="kind"><option value="full">full</option><option value="demo">demo</option></select></label>'
    . '<label>' . L('Διάρκεια','Duration') . '<input type="number" name="dur" value="0" style="width:70px"></label>'
    . '<label>' . L('Μονάδα','Unit') . '<select name="unit"><option value="days">days</option><option value="months">months</option></select></label>'
    . '<label>' . L('Χρήσεις','Uses') . '<input type="number" name="uses" value="1" style="width:60px"></label>'
    . '<label>' . L('Πλήθος','Count') . '<input type="number" name="count" value="1" style="width:60px"></label>'
    . '<button class="btn pri">' . L('Δημιουργία','Create') . '</button></form></section>';
  $codes = dc_q("SELECT * FROM dc_codes ORDER BY created DESC LIMIT 500")->fetchAll();
  echo '<section class="card"><h2>' . L('Κωδικοί','Codes') . ' <small>(' . count($codes) . ')</small></h2><div class="tw"><table class="tbl"><tr><th>' . L('Κωδικός','Code') . '</th><th>' . L('Τύπος','Type') . '</th><th>' . L('Διάρκεια','Duration') . '</th><th>' . L('Χρήσεις','Uses') . '</th><th>' . L('Δημιουργία','Created') . '</th><th></th></tr>';
  foreach ($codes as $c)
    echo '<tr><td class="mono"><b>' . h($c['code']) . '</b></td><td><span class="pill ' . ($c['kind']==='full'?'ok':'o') . '">' . h($c['kind']) . '</span></td><td>' . (int)$c['dur'] . ' ' . h($c['unit']) . '</td><td>' . (int)$c['used'] . '/' . (int)$c['uses'] . '</td><td class="muted">' . dc_dt($c['created']) . '</td>'
       . '<td><form method="post" onsubmit="return confirm(\'Delete?\')">' . csrf() . '<input type="hidden" name="p" value="licenses"><input type="hidden" name="code" value="' . h($c['code']) . '"><button class="btn sm danger" name="a" value="code_del">×</button></form></td></tr>';
  echo '</table></div>';
  if (!$codes) echo '<p class="empty">' . L('Κανένας κωδικός ακόμη.','No codes yet.') . '</p>';
  echo '</section>';
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
  echo '<section class="card"><h2>' . L('Νέο μήνυμα','New message') . '</h2>'
    . '<form class="form" method="post">' . csrf() . '<input type="hidden" name="p" value="messages"><input type="hidden" name="a" value="msg_send">'
    . '<div class="g2"><label>' . L('Παραλήπτης','Recipient') . '<select name="scope"><option value="all">' . L('Όλοι','Everyone') . '</option><option value="one">' . L('Μία εγκατάσταση','One installation') . '</option></select></label>'
    . '<label>' . L('ID / Callsign (αν «μία»)','ID / Callsign (if one)') . '<input name="target"></label></div>'
    . '<label>' . L('Τίτλος','Title') . '<input name="title" required></label>'
    . '<label>' . L('Κείμενο','Body') . '<textarea name="body" rows="3" required></textarea></label>'
    . '<button class="btn pri">' . L('Αποστολή','Send') . '</button></form></section>';
  $msgs = dc_q("SELECT * FROM dc_messages ORDER BY t DESC LIMIT 100")->fetchAll();
  echo '<section class="card"><h2>' . L('Σταλμένα','Sent') . ' <small>(' . count($msgs) . ')</small></h2><div class="tw"><table class="tbl"><tr><th>' . L('Πότε','When') . '</th><th>' . L('Προς','To') . '</th><th>' . L('Τίτλος','Title') . '</th><th></th><th></th></tr>';
  foreach ($msgs as $m)
    echo '<tr><td class="muted">' . dc_dt($m['t']) . '</td><td>' . ($m['scope']==='all'?L('Όλοι','Everyone'):h($m['target'])) . '</td><td><b>' . h($m['title']) . '</b><br><span class="muted">' . h(mb_substr($m['body'],0,80)) . '</span></td><td>' . ((int)$m['active']?'<span class="pill ok">' . L('ενεργό','active') . '</span>':'<span class="pill dim">off</span>') . '</td>'
       . '<td>' . ((int)$m['active'] ? '<form method="post">' . csrf() . '<input type="hidden" name="p" value="messages"><input type="hidden" name="mid" value="' . (int)$m['id'] . '"><button class="btn sm" name="a" value="msg_off">' . L('Απόσυρση','Retire') . '</button></form>' : '') . '</td></tr>';
  echo '</table></div>';
  if (!$msgs) echo '<p class="empty">' . L('Κανένα μήνυμα ακόμη.','No messages yet.') . '</p>';
  echo '</section>';
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
      . '<div class="stn-m">' . h($os) . ' · v' . h($r['version'] ?: '—') . ' · ' . h(substr($r['id'], 0, 10)) . '</div>'
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
    return '<a class="rc ' . ($isOn ? 'on' : 'off') . ($tx ? ' tx' : '') . '" href="?p=installs&q=' . urlencode($r['id']) . '" title="' . h(dc_dt($r['_t'])) . '">'
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

function activity_rows($rows) {
  if (!$rows) return '<p class="muted">' . L('Τίποτα ακόμη.','Nothing yet.') . '</p>';
  $cls = ['activate'=>'g','demo'=>'b','lock'=>'o','disable'=>'r','del_inst'=>'r','rel_activate'=>'g','rel_forceall'=>'o','rel_upload'=>'b','admin_login'=>'','msg_send'=>'b'];
  $out = '<ul class="act">';
  foreach ($rows as $r) {
    $c = $cls[$r['kind']] ?? '';
    $out .= '<li class="' . $c . '"><span class="t">' . dc_dt($r['t']) . '</span><span><b>' . h($r['kind']) . '</b> ' . h($r['detail']) . '</span></li>';
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
