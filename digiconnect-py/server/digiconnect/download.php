<?php
// DigiConnect — serve the renderer package (.dcpkg) for the shell auto-update, and installers for the web.
require __DIR__ . '/lib.php';
$f = $_GET['f'] ?? ''; $v = $_GET['v'] ?? ''; $id = $_GET['id'] ?? '';
$cfg = dc_cfg();

if ($f === 'pkg') {
  $rel = $v ? dc_one('SELECT * FROM dc_releases WHERE version=?', [$v]) : dc_active_release($id ?: null);
  if (!$rel) { http_response_code(404); echo 'no release'; exit; }
  $path = $cfg['pkg_dir'] . '/' . basename($rel['pkg']);
  if (!is_file($path)) { http_response_code(404); echo 'missing package'; exit; }
  dc_event('dl_pkg', ($id ?: '') . '|' . $rel['version']);
  header('Content-Type: application/octet-stream');
  header('Content-Disposition: attachment; filename="' . basename($rel['pkg']) . '"');
  header('Content-Length: ' . filesize($path));
  readfile($path); exit;
}
http_response_code(400); echo 'bad request';
