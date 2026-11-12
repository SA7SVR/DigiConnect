<?php
// DigiConnect — licence/demo API the shell proxies for window.hz.licCheck / redeem.
// POST/GET: action=state|redeem, id, code
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$a  = $_REQUEST['action'] ?? 'state';
$id = $_REQUEST['id'] ?? '';
$hw = dc_hw_clean($_REQUEST['hw'] ?? '');
if (!$id) { echo json_encode(['ok' => false, 'err' => 'no id']); exit; }

$in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
if (!$in) {
  // first contact outside manifest: create it; the default policy (panel › Licences) is applied by dc_state below
  $now = time();
  dc_q('INSERT INTO dc_installs(id,first_seen,last_seen,state,demo_until,ip) VALUES(?,?,?,?,?,?)', [$id, $now, $now, '', 0, dc_ip()]);
  $in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
}

if ($hw !== '') dc_hw_bind($id, $hw, (string)($_REQUEST['os'] ?? ''));
if ($a === 'redeem') {
  // same rules as HAM Digi: the code can have an end date (valid_until) and a number of computers (uses, 0 = unlimited);
  // the duration counts from the moment the code is entered; entering it again on the same installation does not use it up
  $code = strtoupper(preg_replace('/[^A-Za-z0-9-]/', '', (string)($_REQUEST['code'] ?? '')));
  $c = $code !== '' ? dc_one('SELECT * FROM dc_codes WHERE code=?', [$code]) : null;
  $now = time(); $err = '';
  if (!$c) $err = 'bad_code';
  elseif ((int)($c['valid_until'] ?? 0) > 0 && (int)$c['valid_until'] < $now) $err = 'expired';
  elseif ((int)$c['uses'] > 0 && (int)$c['used'] >= (int)$c['uses'] && $c['last_install'] !== $id) {
    $err = 'used';
    dc_alert('code_reuse', "$id|$code|" . (string)$c['last_install'], "Ο κωδικός $code (χρησιμοποιήθηκε από " . dc_inst_no((string)$c['last_install']) . ") δοκιμάστηκε σε άλλη εγκατάσταση: " . dc_inst_no($id) . ".\nThe code $code (used by " . dc_inst_no((string)$c['last_install']) . ") was tried on another installation: " . dc_inst_no($id) . ".");
  }
  if ($err) { echo json_encode(['ok' => false, 'err' => $err]); exit; }
  $exp = $c['kind'] === 'full' && !(int)$c['dur'] ? 0 : dc_lic_add($now, max(1, (int)$c['dur']), dc_unit((string)$c['unit']));
  dc_lic_set($id, $c['kind'] === 'full' ? 'full' : 'demo', $exp, 'code ' . $code, $code);
  if ($c['last_install'] !== $id) dc_q('UPDATE dc_codes SET used=used+1, last_used=?, last_install=? WHERE code=?', [$now, $id, $code]);
  dc_event('redeem', "$id|$code");
  $in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
}

echo json_encode(dc_lic_answer($id, $hw, ['os' => (string)($_REQUEST['os'] ?? '')]) + ['version' => $in['version']]);
