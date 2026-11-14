<?php
/* DigiConnect — host-file auto-refresh.
   Downloads the full server lists for every mode from the canonical upstreams,
   prepends your HELLAS Zone reflectors (hosts/custom/<file>), and publishes them
   to hosts/pub/<file> for the app to fetch. Keeps the last good copy on failure.

   Run from cron (continuous auto-update), e.g. every 30 minutes:
     star/30 * * * * php /path/to/digiconnect/hosts/refresh.php >/dev/null 2>&1
   Or trigger once from the admin panel (Servers → Refresh now).

   CLI:  php refresh.php            # refresh all
         php refresh.php YSFHosts   # refresh one file (name may omit .txt) */

require_once __DIR__ . '/../lib.php';
$SOURCES = require __DIR__ . '/sources.php';
$PUB  = __DIR__ . '/pub';
$CUST = __DIR__ . '/custom';
@mkdir($PUB, 0775, true); @mkdir($CUST, 0775, true);

$only = null;
if (PHP_SAPI === 'cli' && !empty($argv[1])) { $only = $argv[1]; if (strpos($only, '.') === false) $only .= (strpos($only,'Hosts')!==false||strpos($only,'IDs')!==false) ? '.txt' : '.txt'; }

require_once __DIR__ . '/functions.php';

if (!isset($PUB_DIRS)) $PUB_DIRS = hosts_store_dirs();

$report = [];
$rcTok = refcheck_token();
foreach ($SOURCES as $file => $urls) {
  if ($only && $file !== $only) continue;
  $data = null; $src = ''; $errs = [];
  // RefCheck allows one request per list per hour: inside that time the copy we have is kept (no request at all)
  $hasRc = false; foreach ($urls as $u) if (is_refcheck($u)) $hasRc = true;
  $mine = hosts_find($file);
  if ($hasRc && $rcTok !== '' && $mine && time() - (int)dc_kv("refcheck_try_$file", 0) < RC_GAP) {
    $report[$file] = ['ok'=>true, 'src'=>'refcheck.radio', 'lines'=>hosts_count_lines($mine), 'kept'=>true, 'err'=>'']; continue;
  }
  // with a token the official RefCheck list is the ONLY source of these lists: a failure keeps the last good copy, it never swaps in another mirror's data
  if ($hasRc && $rcTok !== '') $urls = array_values(array_filter($urls, 'is_refcheck'));
  foreach ($urls as $u) {
    $rc = is_refcheck($u);
    if ($rc && $rcTok === '') { $errs[] = 'RefCheck: no token entered (panel > Servers)'; continue; }   // without a token the .txt lists come from the older mirrors
    if ($rc) dc_kv_set("refcheck_try_$file", time());
    $why = ''; $body = fetch_url($u, 25, $why, $rc ? ['Authorization: Token ' . $rcTok] : []);
    if ($body !== null && !hosts_valid($body, $why)) $body = null;
    if ($body !== null && $rc && !hosts_shape_ok($file, $body, $why)) $body = null;
    if ($body !== null && $rc && $mine) {                                  // a download that lost more than half of the entries is a broken one, not a real change
      $new = 0; foreach (preg_split('/\r?\n/', $body) as $ln) { $ln = trim($ln); if ($ln !== '' && $ln[0] !== '#') $new++; }
      $old = hosts_count_lines($mine); if ($old >= 10 && $new < $old * 0.5) { $why = "list shrank from $old to $new entries - not used"; $body = null; }
    }
    if ($body !== null) { $data = $body; $src = $u; break; }
    $errs[] = parse_url($u, PHP_URL_HOST) . ': ' . $why;
  }
  $have = hosts_find($file);
  if ($data === null) {
    // upstream down → keep the last good copy, record the real reason
    $msg = gmdate('Y-m-d H:i') . ' UTC · ' . implode(' | ', $errs);
    $report[$file] = ['ok'=>false, 'src'=>'', 'lines'=>$have ? hosts_count_lines($have) : 0, 'kept'=>(bool)$have, 'err'=>$msg];
    dc_kv_set("hostsync_err_$file", $msg);
    continue;
  }
  $isJson = substr($file, -5) === '.json';
  // prepend your own reflectors, if any, so they appear first
  $custPath = "$CUST/$file";
  $prepend = (!$isJson && is_file($custPath) ? rtrim(file_get_contents($custPath)) . "\n" : '');
  if ($prepend !== '') {
    $keys = [];
    foreach (preg_split('/\r?\n/', trim($prepend)) as $ln) { $ln = trim($ln); if ($ln==='' || $ln[0]==='#') continue; $keys[strtok($ln, " \t;")] = 1; }
    $kept = [];
    foreach (preg_split('/\r?\n/', $data) as $ln) { $t = trim($ln); if ($t!=='' && $t[0]!=='#' && isset($keys[strtok($t, " \t;")])) continue; $kept[] = $ln; }
    $data = implode("\n", $kept);
  }
  if ($isJson) $out = $data; else
  $out = "# DigiConnect · HELLAS Zone Net — " . $file . "\n# auto-updated " . gmdate('Y-m-d H:i:s') . " UTC from " . parse_url($src, PHP_URL_HOST) . "\n"
       . ($prepend !== '' ? "# --- HELLAS Zone reflectors ---\n$prepend# --- network ---\n" : '')
       . ltrim($data) . "\n";
  // write to every store; success = at least one verified write. Each failure is reported with its reason.
  $okDirs = []; $wErr = [];
  foreach ($PUB_DIRS as $d) { $why = ''; if (hosts_write_atomic("$d/$file", $out, $why)) $okDirs[] = $d; else $wErr[] = $why; }
  if (!$okDirs) {
    $msg = gmdate('Y-m-d H:i') . ' UTC · ' . implode(' | ', $wErr);
    $report[$file] = ['ok'=>false, 'src'=>parse_url($src, PHP_URL_HOST), 'lines'=>0, 'kept'=>false, 'err'=>$msg];
    dc_kv_set("hostsync_err_$file", $msg);
    continue;
  }
  $lines = hosts_count_lines("{$okDirs[0]}/$file");
  $note = $wErr ? ' · ⚠ ' . implode(' | ', $wErr) : '';
  $report[$file] = ['ok'=>true, 'src'=>parse_url($src, PHP_URL_HOST), 'lines'=>$lines, 'kept'=>true, 'err'=>$note];
  dc_kv_set("hostsync_ok_$file", gmdate('Y-m-d H:i') . ' UTC · ' . $lines . ' lines · ' . parse_url($src, PHP_URL_HOST));
  dc_kv_set("hostsync_err_$file", $note);
}
dc_kv_set('hostsync_last', gmdate('Y-m-d H:i') . ' UTC');
dc_event('hostsync', ($only ?: 'all') . ' · ' . count(array_filter($report, fn($r)=>$r['ok'])) . '/' . count($report) . ' ok');

if (PHP_SAPI === 'cli') {
  foreach ($report as $f => $r) printf("%-16s %s  %5d lines  %s %s\n", $f, $r['ok']?'OK  ':'FAIL', $r['lines'], $r['src'], $r['err'] ?? '');
}
return $report;
