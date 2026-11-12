<?php
// DigiConnect server — shared library. Self-contained (own SQLite DB), so it never touches HAM Digi data.
// (c) 2026 SA7SVR (Panagiotis Tsekouras).
declare(strict_types=1);
const DC_SERVER_VERSION = '2.2.0';   // server package number (panel footer); same number as the program in the package
if (session_status() === PHP_SESSION_NONE) @session_start();

function dc_cfg(): array {
  static $c = null;
  if ($c === null) {
    $f = __DIR__ . '/config.php';
    $c = is_file($f) ? (include $f) : [];
    $c += [
      'db'        => __DIR__ . '/data/digiconnect.db',
      'pkg_dir'   => __DIR__ . '/pkg',
      'admin_user'=> 'admin',
      'admin_pass'=> 'change-me',        // change in config.php
      'demo_days' => 14,                 // default demo length for a new install
      'donate_url'=> '',                 // the Donate button of the program opens this address (set in config.php)
      'check_every'=> 3600,             // app update-check interval (seconds); min 60
      'gate'      => true,              // true = enforce demo/licence; false = everyone allowed
      'offline'   => 'require',         // require | grace | allow  (what the program does when it cannot reach this server)
      'offline_days' => 7               // days the program keeps working offline when offline = grace
    ];
  }
  return $c;
}

function dc_db(): PDO {
  static $pdo = null;
  if ($pdo) return $pdo;
  $cfg = dc_cfg();
  @mkdir(dirname($cfg['db']), 0775, true);
  $pdo = new PDO('sqlite:' . $cfg['db']);
  $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
  $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
  $pdo->exec('PRAGMA busy_timeout=4000;');
  try { $pdo->exec('PRAGMA journal_mode=WAL;'); } catch (Exception $e) {}
  $pdo->exec("
    CREATE TABLE IF NOT EXISTS dc_installs (
      id TEXT PRIMARY KEY, first_seen INT, last_seen INT, version TEXT, shell TEXT, os TEXT, arch TEXT,
      checks INT DEFAULT 0, prev_version TEXT, updated_at INT,
      call TEXT, name TEXT, mail TEXT, ip TEXT, lang TEXT,
      state TEXT DEFAULT 'demo',        -- demo | full | locked | disabled
      demo_until INT, lic_by TEXT, lic_set INT, note TEXT, enabled INT DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS dc_releases (
      id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT UNIQUE, min_shell TEXT, pkg TEXT, sha256 TEXT, size INT, files INT,
      notes_el TEXT, notes_en TEXT, notes_sv TEXT, notes_it TEXT,
      status TEXT DEFAULT 'draft', rollout INT DEFAULT 100, published INT
    );
    CREATE TABLE IF NOT EXISTS dc_codes (
      code TEXT PRIMARY KEY, kind TEXT, dur INT, unit TEXT, uses INT DEFAULT 1, used INT DEFAULT 0,
      created INT, note TEXT, last_used INT, last_install TEXT
    );
    CREATE TABLE IF NOT EXISTS dc_webdl (id INTEGER PRIMARY KEY AUTOINCREMENT, t INT, call TEXT, email TEXT, name TEXT, os TEXT, version TEXT, ip TEXT, ua TEXT, lang TEXT);
    CREATE TABLE IF NOT EXISTS dc_dl_allow (k TEXT PRIMARY KEY, n INT DEFAULT 0, t INT);
    CREATE TABLE IF NOT EXISTS dc_events (id INTEGER PRIMARY KEY AUTOINCREMENT, t INT, kind TEXT, detail TEXT);
    CREATE TABLE IF NOT EXISTS dc_kv (k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS dc_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, t INT, txn TEXT UNIQUE, status TEXT, amount REAL, currency TEXT, payer_email TEXT, payer_name TEXT, memo TEXT, custom TEXT, install TEXT, code TEXT, matched_by TEXT, note TEXT, raw TEXT);
    CREATE INDEX IF NOT EXISTS i_dc_pay_t ON dc_payments(t);
    CREATE INDEX IF NOT EXISTS i_dc_inst_last ON dc_installs(last_seen);
    CREATE INDEX IF NOT EXISTS i_dc_inst_call ON dc_installs(call);
  ");
  // additive migration: presence columns (what the station reports with ping.php)
  $have = array_column($pdo->query('PRAGMA table_info(dc_installs)')->fetchAll(), 'name');
  foreach (['grid' => 'TEXT', 'eq' => 'TEXT', 'rx' => 'TEXT', 'tx' => 'TEXT', 'ptt' => 'INT DEFAULT 0', 'last_ping' => 'INT', 'dmr_id' => 'TEXT', 'consent_at' => 'INT', 'owner' => 'TEXT', 'lic_code' => 'TEXT', 'lic_since' => 'INT'] as $c => $t)
    if (!in_array($c, $have, true)) $pdo->exec("ALTER TABLE dc_installs ADD COLUMN $c $t");
  // messages to the users as in HAM Digi: Greek + English title and text, link, end date, to everyone or to one installation (target = installation id)
  $mc = array_column($pdo->query('PRAGMA table_info(dc_messages)')->fetchAll(), 'name');
  if (!$mc) { $pdo->exec('CREATE TABLE IF NOT EXISTS dc_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, t INT, scope TEXT, target TEXT, title TEXT, body TEXT, active INT DEFAULT 1)'); $mc = ['id']; }
  foreach (['title_el' => 'TEXT', 'title_en' => 'TEXT', 'body_el' => 'TEXT', 'body_en' => 'TEXT', 'link' => 'TEXT', 'until' => 'INT DEFAULT 0'] as $c => $t)
    if (!in_array($c, $mc, true)) $pdo->exec("ALTER TABLE dc_messages ADD COLUMN \"$c\" $t");
  // activation codes as in HAM Digi: the code itself can expire (valid_until); uses = 0 means unlimited
  $hc = array_column($pdo->query('PRAGMA table_info(dc_codes)')->fetchAll(), 'name');
  if (!in_array('valid_until', $hc, true)) $pdo->exec('ALTER TABLE dc_codes ADD COLUMN valid_until INT DEFAULT 0');
  return $pdo;
}

function dc_q(string $sql, array $a = []): PDOStatement { $st = dc_db()->prepare($sql); $st->execute($a); return $st; }
function dc_one(string $sql, array $a = []) { return dc_q($sql, $a)->fetch(); }
function dc_kv(string $k, $d = null) { $r = dc_one('SELECT v FROM dc_kv WHERE k=?', [$k]); return $r ? $r['v'] : $d; }
// a value set in the admin panel (Settings) wins over config.php
function dc_opt(string $k, $default = null) { $v = dc_kv($k, null); return $v === null ? $default : $v; }
function dc_kv_set(string $k, $v): void { dc_q('INSERT INTO dc_kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', [$k, (string)$v]); }
function dc_event(string $kind, string $detail = ''): void { dc_q('INSERT INTO dc_events(t,kind,detail) VALUES(?,?,?)', [time(), $kind, $detail]); }
function dc_ip(): string { foreach (['HTTP_CF_CONNECTING_IP','HTTP_X_FORWARDED_FOR','REMOTE_ADDR'] as $h) if (!empty($_SERVER[$h])) return trim(explode(',', $_SERVER[$h])[0]); return ''; }
function dc_dt($t): string { return $t ? gmdate('Y-m-d H:i', (int)$t) . ' UTC' : '—'; }
function dc_h($s): string { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function dc_csrf(): string { if (empty($_SESSION['dc_csrf'])) $_SESSION['dc_csrf'] = bin2hex(random_bytes(16)); return $_SESSION['dc_csrf']; }
function dc_csrf_ok(): bool { return isset($_POST['csrf']) && hash_equals($_SESSION['dc_csrf'] ?? '', $_POST['csrf']); }

// active release for new update checks (honours rollout by a stable hash of the install id)
function dc_active_release(?string $installId = null): ?array {
  $r = dc_one("SELECT * FROM dc_releases WHERE status='active' ORDER BY published DESC LIMIT 1");
  if (!$r) return null;
  $roll = (int)($r['rollout'] ?? 100);
  if ($installId !== null && $roll < 100) { $h = hexdec(substr(md5($installId . '|' . $r['version']), 0, 4)) % 100; if ($h >= $roll) return null; }
  return $r;
}

// ---- licence model (same as HAM Digi): state '' = follows the default policy, free | demo | full | locked, demo_until = end of a demo / of a time-limited licence ----
function dc_lic_settings(): array {
  $cfg = dc_cfg(); $d = json_decode((string)dc_kv('lic_default', ''), true);
  return array_merge(['mode' => 'demo', 'n' => max(1, (int)dc_opt('demo_days', $cfg['demo_days'])), 'unit' => 'd', 'msg_el' => '', 'msg_en' => '', 'offer' => 'donate', 'amount' => '', 'link' => ''], is_array($d) ? $d : []);
}
// add n hours / days / months / years to a time (calendar months and years)
function dc_lic_add(int $t, $n, string $unit): int {
  $n = max(0, (int)$n); $u = ['h' => 'hour', 'd' => 'day', 'm' => 'month', 'y' => 'year'][$unit] ?? 'day';
  if ($u === 'hour') return $t + $n * 3600;
  $dt = new DateTime('@' . $t); $dt->modify("+$n $u"); return $dt->getTimestamp();
}
// codes made before this version stored days/months/years/hours
function dc_unit(string $u): string { return ['hours' => 'h', 'days' => 'd', 'months' => 'm', 'years' => 'y'][$u] ?? (in_array($u, ['h', 'd', 'm', 'y'], true) ? $u : 'd'); }
function dc_unit_name(string $u, $n): array { $u = dc_unit($u); $el = ['h' => 'ώρες', 'd' => 'ημέρες', 'm' => 'μήνες', 'y' => 'χρόνια']; $en = ['h' => 'hours', 'd' => 'days', 'm' => 'months', 'y' => 'years']; return [$n . ' ' . $el[$u], $n . ' ' . $en[$u]]; }
// the address of the Donate button (default settings first, then the older "donate_url" setting / config.php)
function dc_donate(): string {
  $l = trim((string)dc_lic_settings()['link']);
  return preg_match('~^https://~i', $l) ? $l : (string)dc_opt('donate_url', dc_cfg()['donate_url'] ?? '');
}
// what the program may show about buying/donating (the program uses "donate"; "offer" and "amount" are sent along for it to use)
function dc_lic_public(): array { $S = dc_lic_settings(); return ['donate' => dc_donate(), 'offer' => (string)$S['offer'], 'amount' => (string)$S['amount']]; }
function dc_lic_msg(array $in, string $base = ''): string {
  $S = dc_lic_settings(); $el = ($in['lang'] ?? '') === 'el' || ($in['lang'] ?? '') === '';
  $m = trim($el ? ($S['msg_el'] ?: $S['msg_en']) : ($S['msg_en'] ?: $S['msg_el']));
  return $base . ($base !== '' && $m !== '' ? "\n\n" : '') . $m;
}
// change the licence of one installation (panel, code, payment); every change is written to the activity log
function dc_lic_set(string $id, string $st, int $exp, string $by, ?string $code = null): void {
  dc_q('UPDATE dc_installs SET state=?, demo_until=?, lic_set=?, lic_by=? WHERE id=?', [$st, $exp, time(), $by, $id]);
  if ($st !== 'locked') dc_q('UPDATE dc_installs SET enabled=1 WHERE id=?', [$id]);
  if ($st === 'full') dc_q('UPDATE dc_installs SET lic_since=COALESCE(NULLIF(lic_since,0),?) WHERE id=?', [time(), $id]);
  if ($code !== null) dc_q('UPDATE dc_installs SET lic_code=? WHERE id=?', [$code, $id]);
  dc_event('licence', "$id|$st|" . ($exp ? gmdate('Y-m-d H:i', $exp) : '') . "|$by");
}
// effective licence of one installation row (applies the default policy the first time it asks): [state, exp]
function dc_lic_effective(array $in): array {
  $st = (string)($in['state'] ?? ''); $exp = (int)($in['demo_until'] ?? 0); $now = time();
  if ($st === '') {
    $S = dc_lic_settings(); $st = $S['mode'] === 'demo' ? 'demo' : ($S['mode'] === 'locked' ? 'locked' : 'free');
    $exp = $st === 'demo' ? dc_lic_add($now, $S['n'], $S['unit']) : 0;
    if (!empty($in['id'])) dc_q("UPDATE dc_installs SET state=?, demo_until=?, lic_by='default', lic_set=? WHERE id=?", [$st, $exp, $now, $in['id']]);
  }
  if (($st === 'demo' || $st === 'full') && $exp && $exp <= $now) return ['expired', $exp, $st];
  return [$st, $exp, $st];
}

// evaluate the licence/demo state for an install row; returns [state, left_text, msg]
function dc_state(array $in): array {
  $cfg = dc_cfg();
  if (dc_opt('gate', $cfg['gate'] ? '1' : '0') !== '1') return ['full', '', ''];
  if ((int)($in['enabled'] ?? 1) === 0 || ($in['state'] ?? '') === 'disabled')
    return ['locked', '', 'This installation is disabled. Contact SA7SVR.'];
  list($st, $exp, $was) = dc_lic_effective($in); $now = time();
  if ($st === 'free' || $st === 'full') return ['full', '', ''];
  if ($st === 'locked') return ['locked', '', dc_lic_msg($in, trim((string)($in['note'] ?? '')) ?: 'This installation needs activation. Contact SA7SVR.')];
  if ($st === 'expired') return ['locked', '', dc_lic_msg($in, $was === 'full' ? 'Your licence has ended. Contact SA7SVR.' : 'Your demo period has ended. Contact SA7SVR to activate.')];
  // demo
  $left = $exp - $now;
  if ($left < 48 * 3600) { $h = max(1, (int)ceil($left / 3600)); return ['demo', $h . ' hour' . ($h === 1 ? '' : 's') . ' left', '']; }
  $d = (int)ceil($left / 86400);
  return ['demo', $d . ' day' . ($d === 1 ? '' : 's') . ' left', ''];
}

// what the program does when it cannot reach this server: require = never start without an answer, grace = keep working for
// offline_days after the last good answer, allow = keep working (a block set here is applied as soon as the program is online again)
function dc_offline(): array {
  $cfg = dc_cfg(); $m = (string)dc_opt('offline', $cfg['offline'] ?? 'require');
  if (!in_array($m, ['require', 'grace', 'allow'], true)) $m = 'require';
  return ['offline' => $m, 'offline_days' => max(1, (int)dc_opt('offline_days', $cfg['offline_days'] ?? 7))];
}

// ---- presence: a station counts as online while its program keeps sending ping.php (every ~60 s) ----
const DC_ONLINE_S = 180;
function dc_last($r): int { return max((int)($r['last_ping'] ?? 0), (int)($r['last_seen'] ?? 0)); }
function dc_online($r): bool { return (int)($r['last_ping'] ?? 0) >= time() - DC_ONLINE_S; }

// installation number shown everywhere instead of the long id: DC-00001 (row number of the installation)
function dc_inst_no($id): string { $n = (int)(dc_one('SELECT rowid n FROM dc_installs WHERE id=?', [(string)$id])['n'] ?? 0); return $n ? sprintf('DC-%05d', $n) : ''; }
function dc_no_filter(string $q): ?int { return preg_match('/^\s*(?:DC-?)?0*(\d{1,6})\s*$/i', $q, $m) ? (int)$m[1] : null; }

// ---- e-mail + alerts (same as HAM Digi): this server sends no e-mail unless "mail_on" is switched on ----
const DC_ALERTS = ['pay_unmatched', 'pay_refund', 'pay_auto', 'code_reuse'];
function dc_base_url(): string {
  $s = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https') ? 'https' : 'http';
  $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
  if (basename($dir) === 'admin') $dir = dirname($dir);
  return $s . '://' . ($_SERVER['HTTP_HOST'] ?? 'localhost') . rtrim($dir, '/') . '/';
}
function dc_mail(string $to, string $subject, string $body): bool {
  if (dc_kv('mail_on', '0') !== '1') return false;                  // the e-mail address is then only kept as information
  if (!function_exists('mail') || !filter_var($to, FILTER_VALIDATE_EMAIL)) return false;
  $from = trim((string)dc_kv('mail_from', '')) ?: 'noreply@' . preg_replace('/^www\./', '', $_SERVER['HTTP_HOST'] ?? 'hellaszone.com');
  $h = "From: DigiConnect <$from>\r\nReply-To: " . (trim((string)dc_kv('admin_mail', '')) ?: $from) . "\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: 8bit";
  $ok = @mail($to, '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, $h, '-f' . $from);
  dc_event('mail', ($ok ? 'ok' : 'fail') . "|$to|$subject"); return $ok;
}
// events that need your attention: shown at the top of the panel and (optionally) e-mailed to you
function dc_alert(string $kind, string $detail, string $mailText = ''): void {
  dc_event($kind, $detail);
  $to = trim((string)dc_kv('admin_mail', ''));
  if ($to && $mailText && dc_kv('alert_mail', '1') === '1') dc_mail($to, 'DigiConnect: ' . $kind, $mailText);
}

// ---------------------------------------------------------------- payments (PayPal donations / purchases) — same flow as HAM Digi
function dc_pay_settings(): array {
  return ['auto' => dc_kv('pay_auto', '1') === '1', 'min' => (float)str_replace(',', '.', (string)dc_kv('pay_min', '0')), 'receiver' => strtolower(trim((string)dc_kv('pay_receiver', ''))),
          'sandbox' => dc_kv('pay_sandbox', '0') === '1', 'skip_hd' => dc_kv('pay_skip_hd', '1') === '1'];
}
function dc_base_call(string $c): string { $best = ''; foreach (explode('/', strtoupper(preg_replace('/[^A-Za-z0-9\/]/', '', $c))) as $p) if (strlen($p) > strlen($best) && preg_match('/\d/', $p)) $best = $p; return $best; }
// the PayPal account is shared with HAM Digi: a payment that carries a HAM Digi number (HD-00012) and no DigiConnect number belongs to HAM Digi
function dc_pay_is_hamdigi(array $p): bool {
  $dc = $hd = false;
  foreach (['custom', 'item_number', 'memo', 'item_name', 'invoice'] as $k) { $v = (string)($p[$k] ?? ''); if (preg_match('/\bDC[-\s]?0*\d{1,7}/i', $v)) $dc = true; if (preg_match('/\bHD[-\s]?0*\d{1,7}/i', $v)) $hd = true; }
  return $hd && !$dc;
}
// find the installation a payment belongs to: DC number in the PayPal fields or the note, else the payer's e-mail, else an e-mail / callsign written in the note
function dc_pay_match(array $p): array {
  foreach (['custom', 'item_number', 'memo', 'item_name', 'invoice'] as $k) if (!empty($p[$k]) && preg_match('/\bDC[-\s]?0*(\d{1,7})/i', (string)$p[$k], $m)) {
    $r = dc_one('SELECT id FROM dc_installs WHERE rowid=?', [(int)$m[1]]); if ($r) return [$r['id'], 'DC ' . $k];
  }
  $mail = strtolower(trim((string)($p['payer_email'] ?? '')));
  if ($mail) { $r = dc_one('SELECT id FROM dc_installs WHERE lower(mail)=? ORDER BY last_seen DESC LIMIT 1', [$mail]); if ($r) return [$r['id'], 'email']; }
  $note = (string)($p['memo'] ?? '') . ' ' . (string)($p['custom'] ?? '') . ' ' . (string)($p['item_name'] ?? '');
  if (preg_match_all('/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i', $note, $mm)) foreach ($mm[0] as $e) { $r = dc_one('SELECT id FROM dc_installs WHERE lower(mail)=? ORDER BY last_seen DESC LIMIT 1', [strtolower($e)]); if ($r) return [$r['id'], 'email in note']; }
  if (preg_match_all('/\b[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z](?:\/[A-Z0-9]+)?\b/i', strtoupper($note), $mc)) foreach ($mc[0] as $c) {
    $b = dc_base_call($c); if ($b === '') continue;
    $ids = dc_q('SELECT id FROM dc_installs WHERE "call"=? ORDER BY last_seen DESC', [$b])->fetchAll();
    if (count($ids) === 1) return [$ids[0]['id'], 'callsign in note'];
  }
  return [null, ''];
}
function dc_new_code(): string { $raw = strtoupper(bin2hex(random_bytes(6))); return 'HZD-' . substr($raw, 0, 4) . '-' . substr($raw, 4, 4) . '-' . substr($raw, 8, 4); }
// give the full licence for a payment: a new code (kept as proof), the licence on the installation, an e-mail to the payer
function dc_pay_activate(int $payId, string $installId, string $by): string {
  $p = dc_one('SELECT * FROM dc_payments WHERE id=?', [$payId]); if (!$p) throw new Exception('payment');
  $r = dc_one('SELECT * FROM dc_installs WHERE id=?', [$installId]); if (!$r) throw new Exception('Δεν βρέθηκε η εγκατάσταση / installation not found');
  $code = dc_new_code();
  dc_q('INSERT INTO dc_codes(code,kind,dur,unit,uses,used,created,valid_until,note,last_used,last_install) VALUES(?,?,?,?,?,?,?,?,?,?,?)', [$code, 'full', 0, 'd', 1, 1, time(), 0, 'PayPal ' . $p['txn'] . ' ' . $p['amount'] . ' ' . $p['currency'], time(), $installId]);
  dc_lic_set($installId, 'full', 0, 'payment ' . $p['txn'], $code);
  if (!$r['owner'] && $p['payer_name']) dc_q('UPDATE dc_installs SET owner=? WHERE id=?', [$p['payer_name'], $installId]);
  if (!$r['mail'] && $p['payer_email']) dc_q('UPDATE dc_installs SET mail=? WHERE id=?', [strtolower($p['payer_email']), $installId]);
  dc_q('UPDATE dc_payments SET install=?, code=?, matched_by=? WHERE id=?', [$installId, $code, $by, $payId]);
  $no = dc_inst_no($installId); $to = $p['payer_email'] ?: $r['mail'];
  $tpl_el = (string)dc_kv('pay_mail_el', "Ευχαριστώ πολύ για τη στήριξη του DigiConnect!\n\nΤο πρόγραμμά σου ({no}) ενεργοποιήθηκε αυτόματα.\nΚωδικός ενεργοποίησης: {code}\n\nΤο πρόγραμμα το βλέπει μόνο του την επόμενη φορά που θα συνδεθεί· κράτησε τον κωδικό ως απόδειξη.\n\n73 de SA7SVR");
  $tpl_en = (string)dc_kv('pay_mail_en', "Thank you very much for supporting DigiConnect!\n\nYour program ({no}) has been activated automatically.\nActivation code: {code}\n\nThe program sees it by itself the next time it connects; keep the code as proof.\n\n73 de SA7SVR");
  $rep = ['{no}' => $no, '{code}' => $code, '{name}' => (string)$p['payer_name'], '{call}' => (string)$r['call'], '{amount}' => $p['amount'] . ' ' . $p['currency']];
  if ($to) dc_mail($to, 'DigiConnect — ' . (($r['lang'] ?? '') === 'en' ? 'activation' : 'ενεργοποίηση') . ' ' . $no, strtr(($r['lang'] ?? '') === 'en' ? $tpl_en : $tpl_el . "\n\n— — —\n\n" . $tpl_en, $rep));
  return $code;
}
// the checked PayPal message → payment row → automatic activation (separate from ipn.php so it can be tested)
function dc_ipn_process(array $p, string $raw, array $S): string {
  $txn = substr((string)($p['txn_id'] ?? ''), 0, 40); if ($txn === '') return 'no txn';
  $status = (string)($p['payment_status'] ?? ''); $amount = (float)($p['mc_gross'] ?? 0); $cur = strtoupper((string)($p['mc_currency'] ?? ''));
  $recv = strtolower((string)($p['receiver_email'] ?? $p['business'] ?? ''));
  if ($S['receiver'] && $recv && $recv !== $S['receiver']) { dc_event('pay_invalid', "receiver $recv|$txn"); return 'receiver'; }
  if ($S['skip_hd'] && dc_pay_is_hamdigi($p)) { dc_event('pay_skipped', "$txn|$amount $cur|HAM Digi"); return 'hamdigi'; }
  $name = trim(($p['first_name'] ?? '') . ' ' . ($p['last_name'] ?? ''));
  $memo = trim((string)($p['memo'] ?? '') . ' ' . (string)($p['custom'] ?? '') . ' ' . (string)($p['item_number'] ?? ''));
  // refunds / reversals point to the original payment (parent_txn_id)
  if (in_array($status, ['Refunded', 'Reversed', 'Canceled_Reversal'], true)) {
    $par = (string)($p['parent_txn_id'] ?? '');
    $pr = dc_one('SELECT * FROM dc_payments WHERE txn=?', [$par]);
    if (!$pr) return 'other';                                          // a refund of a payment this server never recorded (e.g. HAM Digi's)
    dc_q('UPDATE dc_payments SET status=? WHERE txn=?', [$status, $par]);
    dc_alert('pay_refund', "$par|$status|" . ($pr['install'] ?? ''), "PayPal: $status για την πληρωμή $par (" . $pr['amount'] . ' ' . $pr['currency'] . ', ' . dc_inst_no((string)$pr['install']) . "). Η άδεια ΔΕΝ αλλάζει αυτόματα — αποφάσισε εσύ στο panel.\nPayPal: $status for payment $par. The licence is NOT changed automatically — decide in the panel.");
    return 'ok';
  }
  $ex = dc_one('SELECT * FROM dc_payments WHERE txn=?', [$txn]);
  if ($ex) { if ($ex['status'] !== 'Ignored') dc_q('UPDATE dc_payments SET status=? WHERE id=?', [$status, $ex['id']]); $pid = (int)$ex['id']; }   // a payment you ignored stays ignored
  else {
    dc_q('INSERT INTO dc_payments(t,txn,status,amount,currency,payer_email,payer_name,memo,custom,raw) VALUES(?,?,?,?,?,?,?,?,?,?)', [time(), $txn, $status, $amount, $cur, strtolower((string)($p['payer_email'] ?? '')), $name, substr($memo, 0, 500), substr((string)($p['custom'] ?? ''), 0, 120), substr($raw, 0, 6000)]);
    $pid = (int)dc_db()->lastInsertId(); dc_event('payment', "$txn|$amount $cur|$name|" . ($p['payer_email'] ?? ''));
  }
  $pr = dc_one('SELECT * FROM dc_payments WHERE id=?', [$pid]);
  if ($status === 'Completed' && !$pr['install'] && $pr['status'] === 'Completed') {
    list($iid, $how) = dc_pay_match($p);
    if ($iid && $S['auto'] && $amount >= $S['min']) {
      $code = dc_pay_activate($pid, $iid, 'auto: ' . $how);
      dc_alert('pay_auto', "$iid|$txn|$amount $cur|$code", "Νέα πληρωμή $amount $cur από $name — ενεργοποιήθηκε αυτόματα " . dc_inst_no($iid) . " (κωδικός $code).\nNew payment $amount $cur from $name — " . dc_inst_no($iid) . " activated automatically (code $code).");
    } else dc_alert('pay_unmatched', "$txn|$amount $cur|$name|" . ($iid ?: ''), "Νέα πληρωμή $amount $cur από $name (" . ($p['payer_email'] ?? '') . ")" . ($iid ? ' — πιθανή εγκατάσταση ' . dc_inst_no($iid) : ' — δεν βρέθηκε εγκατάσταση') . ". Ενεργοποίησέ την στο panel › Πληρωμές.\nNew payment $amount $cur from $name. Activate it in the panel › Payments.\n\n" . dc_base_url() . 'admin/?p=payments');
  }
  return 'ok';
}
// totals per currency (EUR and SEK are never added together); only completed, not ignored payments
function dc_pay_totals(): array {
  $out = ['EUR' => ['total' => 0.0, 'n' => 0, 'month' => 0.0, 'year' => 0.0], 'SEK' => ['total' => 0.0, 'n' => 0, 'month' => 0.0, 'year' => 0.0]];
  $m0 = strtotime(gmdate('Y-m-01 00:00:00') . ' UTC'); $y0 = strtotime(gmdate('Y-01-01 00:00:00') . ' UTC');
  foreach (dc_q("SELECT currency c, t, amount FROM dc_payments WHERE status='Completed'")->fetchAll() as $x) {
    $c = strtoupper(trim((string)$x['c'])) ?: '?'; if (!isset($out[$c])) $out[$c] = ['total' => 0.0, 'n' => 0, 'month' => 0.0, 'year' => 0.0];
    $out[$c]['total'] += (float)$x['amount']; $out[$c]['n']++;
    if ((int)$x['t'] >= $m0) $out[$c]['month'] += (float)$x['amount'];
    if ((int)$x['t'] >= $y0) $out[$c]['year'] += (float)$x['amount'];
  }
  return $out;
}

// the messages one installation should see (HAM Digi: to everyone or to this installation, not ended, not older than its first contact - 30 days)
function dc_messages_for(string $id, int $firstSeen): array {
  $out = [];
  foreach (dc_q("SELECT * FROM dc_messages WHERE active=1 AND (target IS NULL OR target='' OR target=?) AND (COALESCE(until,0)=0 OR until>?) AND t>=? ORDER BY t DESC LIMIT 10", [$id, time(), $firstSeen - 86400 * 30])->fetchAll() as $m) {
    $el = (string)($m['body_el'] ?? '') !== '' ? $m['body_el'] : (string)($m['body'] ?? ''); $en = (string)($m['body_en'] ?? '') !== '' ? $m['body_en'] : (string)($m['body'] ?? '');
    $out[] = ['id' => 'm' . $m['id'], 't' => (int)$m['t'], 'title_el' => (string)($m['title_el'] ?: $m['title']), 'title_en' => (string)($m['title_en'] ?: $m['title']), 'el' => (string)$el, 'en' => (string)$en, 'link' => (string)($m['link'] ?? '')];
  }
  return $out;
}
