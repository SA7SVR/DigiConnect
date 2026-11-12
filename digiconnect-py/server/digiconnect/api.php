<?php
// DigiConnect — licence/demo API the shell proxies for window.hz.licCheck / redeem.
// POST/GET: action=state|redeem, id, code
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$a  = $_REQUEST['action'] ?? 'state';
$id = $_REQUEST['id'] ?? '';
if (!$id) { echo json_encode(['ok' => false, 'err' => 'no id']); exit; }

$in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
if (!$in) {
  // first contact outside manifest: create as demo
  $cfg = dc_cfg(); $now = time();
  dc_q('INSERT INTO dc_installs(id,first_seen,last_seen,state,demo_until,ip) VALUES(?,?,?,?,?,?)',
    [$id, $now, $now, 'demo', $now + 86400 * (int)dc_opt('demo_days', $cfg['demo_days']), dc_ip()]);
  $in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
}

if ($a === 'redeem') {
  $code = strtoupper(trim($_REQUEST['code'] ?? ''));
  $c = $code ? dc_one('SELECT * FROM dc_codes WHERE code=?', [$code]) : null;
  if (!$c || (int)$c['used'] >= (int)$c['uses']) { echo json_encode(['ok' => false, 'err' => 'bad_code']); exit; }
  if ($c['kind'] === 'full') {
    dc_q("UPDATE dc_installs SET state='full', lic_by=?, lic_set=? WHERE id=?", ['code ' . $code, time(), $id]);
  } else { // extend demo by dur/unit
    $mul = $c['unit'] === 'months' ? 2592000 : ($c['unit'] === 'years' ? 31536000 : ($c['unit'] === 'hours' ? 3600 : 86400));
    $until = max(time(), (int)$in['demo_until']) + (int)$c['dur'] * $mul;
    dc_q("UPDATE dc_installs SET state='demo', demo_until=? WHERE id=?", [$until, $id]);
  }
  dc_q('UPDATE dc_codes SET used=used+1, last_used=?, last_install=? WHERE code=?', [time(), $id, $code]);
  dc_event('redeem', "$id|$code");
  $in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
}

list($state, $left, $msg) = dc_state($in);
echo json_encode(['ok' => true, 'state' => $state, 'left' => $left, 'msg' => $msg, 'version' => $in['version']]);
