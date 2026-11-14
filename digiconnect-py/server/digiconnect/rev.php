<?php
// DigiConnect — "did anything change for me?" (the program asks about every 5 seconds while it runs, whatever the "show me online" setting is).
// GET: id  ->  {"ok":true,"rev":"<stamp>"}   The stamp covers state, expiry, modes/policy, messages and owner replies of that installation
// (see dc_rev in lib.php). It only reads: no row is created or changed, nothing is shown as "online". When the stamp differs from the one the
// program holds, the program asks for the full SIGNED licence answer at once and applies it without a restart.
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$id = preg_replace('/[^0-9A-Za-z_-]/', '', (string)($_REQUEST['id'] ?? ''));
if ($id === '' || strlen($id) > 64) { echo json_encode(['ok' => false, 'err' => 'no id']); exit; }
echo json_encode(['ok' => true, 'rev' => dc_rev($id)]);
