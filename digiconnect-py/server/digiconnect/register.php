<?php
// DigiConnect — registration from the program's first-run window (POST).
// Fields: id, name, call, dmr_id, mail, consent=1, v, os, arch, shell, lang  ->  {"ok":true,"state":...,"left":...,"msg":...,"donate":...}
// Stores only what the person typed in the window (name, callsign, DMR ID, email) plus the installation facts the update check already sends.
// A reinstall with the same callsign AND the same email gets the earlier demo/licence state back (the trial does not restart).
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$fail = function (string $err) { echo json_encode(['ok' => false, 'err' => $err]); exit; };
$id = preg_replace('/[^0-9A-Za-z_-]/', '', (string)($_REQUEST['id'] ?? ''));
if ($id === '' || strlen($id) > 64) $fail('no id');
$clip = function ($k, $n) { return mb_substr(trim((string)($_REQUEST[$k] ?? '')), 0, $n); };
$name = $clip('name', 80);
$call = strtoupper(preg_replace('/[^0-9A-Za-z\/]/', '', $clip('call', 15)));
$dmr  = preg_replace('/\D/', '', $clip('dmr_id', 12));
$mail = strtolower($clip('mail', 120));
if (((string)($_REQUEST['consent'] ?? '')) !== '1') $fail('consent');
if ($name === '') $fail('name');
if (!preg_match('/^[0-9]?[A-Z]{1,2}[0-9][0-9A-Z]{0,3}[A-Z](\/[0-9A-Z]{1,4})?$/', $call)) $fail('call');
if (!preg_match('/^\d{6,9}$/', $dmr)) $fail('dmr_id');
if (!filter_var($mail, FILTER_VALIDATE_EMAIL)) $fail('mail');
$v = $clip('v', 20); $os = $clip('os', 16); $arch = $clip('arch', 16); $shell = $clip('shell', 20); $lang = $clip('lang', 8);
$now = time(); $cfg = dc_cfg();

$cur = dc_one('SELECT id FROM dc_installs WHERE id=?', [$id]);
if (!$cur) {
  dc_q('INSERT INTO dc_installs(id,first_seen,last_seen,version,shell,os,arch,checks,state,demo_until,ip) VALUES(?,?,?,?,?,?,?,0,?,?,?)',
    [$id, $now, $now, $v, $shell, $os, $arch, 'demo', $now + 86400 * (int)dc_opt('demo_days', $cfg['demo_days']), dc_ip()]);
  dc_event('install', "$id|$v|$os|$arch");
  // reinstall by the same person: take over the earlier state, so a new installation id does not restart the demo
  $old = dc_one("SELECT state, demo_until, enabled, note, lic_by, lic_set FROM dc_installs WHERE call=? AND lower(mail)=? AND id<>? ORDER BY first_seen ASC LIMIT 1", [$call, $mail, $id]);
  if ($old) dc_q('UPDATE dc_installs SET state=?, demo_until=?, enabled=?, note=?, lic_by=?, lic_set=? WHERE id=?',
    [$old['state'], $old['demo_until'], $old['enabled'], $old['note'], $old['lic_by'], $old['lic_set'], $id]);
}
dc_q('UPDATE dc_installs SET name=?, call=?, dmr_id=?, mail=?, lang=?, consent_at=COALESCE(consent_at,?), last_seen=?, ip=? WHERE id=?',
  [$name, $call, $dmr, $mail, $lang, $now, $now, dc_ip(), $id]);
dc_event('register', "$id|$call");

$in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
list($state, $left, $msg) = dc_state($in);
echo json_encode(['ok' => true, 'state' => $state, 'left' => $left, 'msg' => $msg, 'offline' => dc_offline()['offline'], 'offline_days' => dc_offline()['offline_days'], 'donate' => (string)dc_opt('donate_url', $cfg['donate_url'] ?? '')]);
