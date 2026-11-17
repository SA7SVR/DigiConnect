<?php
// DigiConnect — the stations that are online now (for the Map page of the program).
// GET -> {"ok":true,"t":<time>,"stations":[{"call":"SA7SVR","grid":"JO89","rx":"DMR:24015","tx":"","ptt":0}, ...]}
// Only the public parts of a row: call sign, grid square, what it listens to, what it sends to and whether it is transmitting.
// No ids, no e-mail, no IP address, no licence data. A station counts as online while its last 'I am online' is recent.
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$now = time();
$rows = dc_q('SELECT "call", grid, rx, tx, ptt FROM dc_installs WHERE last_ping >= ? AND "call" <> \'\' ORDER BY last_ping DESC LIMIT 300', [$now - DC_ONLINE_S])->fetchAll();
$out = [];
foreach ($rows as $r) {
  $call = strtoupper(preg_replace('/[^0-9A-Z\/]/', '', (string)$r['call']));
  if ($call === '' || strlen($call) > 15) continue;
  $grid = strtoupper(preg_replace('/[^0-9A-Z]/', '', (string)($r['grid'] ?? '')));
  $out[] = ['call' => $call, 'grid' => substr($grid, 0, 8), 'rx' => mb_substr((string)($r['rx'] ?? ''), 0, 120), 'tx' => mb_substr((string)($r['tx'] ?? ''), 0, 60), 'ptt' => (int)($r['ptt'] ?? 0) ? 1 : 0];
}
echo json_encode(['ok' => true, 't' => $now, 'stations' => $out], JSON_UNESCAPED_UNICODE);
