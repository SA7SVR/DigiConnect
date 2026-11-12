<?php
// DigiConnect server — shared library. Self-contained (own SQLite DB), so it never touches HAM Digi data.
// (c) 2026 SA7SVR (Panagiotis Tsekouras).
declare(strict_types=1);
const DC_SERVER_VERSION = '2.0.5';   // server package number (panel footer); same number as the program in the package
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
      'demo_days' => 7,                  // default demo length for a new install
      'check_every'=> 3600,             // app update-check interval (seconds); min 60
      'gate'      => true               // true = enforce demo/licence; false = everyone allowed
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
    CREATE INDEX IF NOT EXISTS i_dc_inst_last ON dc_installs(last_seen);
    CREATE INDEX IF NOT EXISTS i_dc_inst_call ON dc_installs(call);
  ");
  // additive migration: presence columns (what the station reports with ping.php)
  $have = array_column($pdo->query('PRAGMA table_info(dc_installs)')->fetchAll(), 'name');
  foreach (['grid' => 'TEXT', 'eq' => 'TEXT', 'rx' => 'TEXT', 'tx' => 'TEXT', 'ptt' => 'INT DEFAULT 0', 'last_ping' => 'INT'] as $c => $t)
    if (!in_array($c, $have, true)) $pdo->exec("ALTER TABLE dc_installs ADD COLUMN $c $t");
  return $pdo;
}

function dc_q(string $sql, array $a = []): PDOStatement { $st = dc_db()->prepare($sql); $st->execute($a); return $st; }
function dc_one(string $sql, array $a = []) { return dc_q($sql, $a)->fetch(); }
function dc_kv(string $k, $d = null) { $r = dc_one('SELECT v FROM dc_kv WHERE k=?', [$k]); return $r ? $r['v'] : $d; }
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

// evaluate the licence/demo state for an install row; returns [state, left_text, msg]
function dc_state(array $in): array {
  $cfg = dc_cfg();
  if (!$cfg['gate']) return ['full', '', ''];
  if ((int)($in['enabled'] ?? 1) === 0 || ($in['state'] ?? '') === 'disabled')
    return ['locked', '', 'This installation is disabled. Contact SA7SVR.'];
  if (($in['state'] ?? '') === 'full') return ['full', '', ''];
  if (($in['state'] ?? '') === 'locked') return ['locked', '', $in['note'] ?: 'This installation needs activation. Contact SA7SVR.'];
  // demo
  $until = (int)($in['demo_until'] ?? 0);
  if ($until <= 0) { $until = time() + 86400 * (int)$cfg['demo_days']; dc_q('UPDATE dc_installs SET demo_until=? WHERE id=?', [$until, $in['id']]); }
  $left = $until - time();
  if ($left <= 0) return ['locked', '', 'Your demo period has ended. Contact SA7SVR to activate.'];
  $d = (int)ceil($left / 86400);
  return ['demo', $d . ' day' . ($d === 1 ? '' : 's') . ' left', ''];
}

// ---- presence: a station counts as online while its program keeps sending ping.php (every ~60 s) ----
const DC_ONLINE_S = 180;
function dc_last($r): int { return max((int)($r['last_ping'] ?? 0), (int)($r['last_seen'] ?? 0)); }
function dc_online($r): bool { return (int)($r['last_ping'] ?? 0) >= time() - DC_ONLINE_S; }

// installation number shown everywhere instead of the long id: DC-00001 (row number of the installation)
function dc_inst_no($id): string { $n = (int)(dc_one('SELECT rowid n FROM dc_installs WHERE id=?', [(string)$id])['n'] ?? 0); return $n ? sprintf('DC-%05d', $n) : ''; }
function dc_no_filter(string $q): ?int { return preg_match('/^\s*(?:DC-?)?0*(\d{1,6})\s*$/i', $q, $m) ? (int)$m[1] : null; }
