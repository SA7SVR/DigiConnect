<?php
// DigiConnect — "I am online" signal from the program (about once a minute while it runs).
// GET: id, v, os, arch, call, grid, eq, rx, tx, ptt  ->  {"ok":true}
// Only updates the row of an installation that already exists or creates it as demo; stores no audio, no passwords.
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$id = preg_replace('/[^0-9A-Za-z_-]/', '', (string)($_REQUEST['id'] ?? ''));
if ($id === '' || strlen($id) > 64) { echo json_encode(['ok' => false, 'err' => 'no id']); exit; }
$clip = function ($k, $n) { return mb_substr(trim((string)($_REQUEST[$k] ?? '')), 0, $n); };
$call = strtoupper(preg_replace('/[^0-9A-Za-z\/]/', '', $clip('call', 15)));
$v = $clip('v', 20); $os = $clip('os', 16); $arch = $clip('arch', 16);
$grid = strtoupper(preg_replace('/[^0-9A-Za-z]/', '', $clip('grid', 8)));
$eq = $clip('eq', 40); $rx = $clip('rx', 120); $tx = $clip('tx', 60); $ptt = ((string)($_REQUEST['ptt'] ?? '0') === '1') ? 1 : 0;
$now = time(); $cfg = dc_cfg();

$cur = dc_one('SELECT id, call FROM dc_installs WHERE id=?', [$id]);
if (!$cur) {
  dc_q('INSERT INTO dc_installs(id,first_seen,last_seen,version,os,arch,checks,state,demo_until,ip,call,grid,eq,rx,tx,ptt,last_ping) VALUES(?,?,?,?,?,?,0,?,?,?,?,?,?,?,?,?,?)',
    [$id, $now, $now, $v, $os, $arch, 'demo', $now + 86400 * (int)dc_opt('demo_days', $cfg['demo_days']), dc_ip(), $call, $grid, $eq, $rx, $tx, $ptt, $now]);
  dc_event('install', "$id|$v|$os|$arch");
} else {
  // the callsign typed in the program fills the row; one that the admin has set by hand is not overwritten by an empty value
  dc_q('UPDATE dc_installs SET last_ping=?, version=COALESCE(NULLIF(?,\'\'),version), os=COALESCE(NULLIF(?,\'\'),os), arch=COALESCE(NULLIF(?,\'\'),arch),
        call=CASE WHEN ?<>\'\' THEN ? ELSE call END, grid=?, eq=?, rx=?, tx=?, ptt=?, ip=? WHERE id=?',
    [$now, $v, $os, $arch, $call, $call, $grid, $eq, $rx, $tx, $ptt, dc_ip(), $id]);
}
echo json_encode(['ok' => true, 't' => $now]);
