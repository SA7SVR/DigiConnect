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
if ($f === 'engine') {                                   // 2.4.0: the protocol engine package (.dceng) for one system
  $os = (string)($_GET['os'] ?? ''); $arch = (string)($_GET['arch'] ?? '');
  if (!preg_match('/^\d+(\.\d+)*$/', $v) || !in_array($os, ['windows', 'macos', 'linux'], true) || !in_array($arch, ['x64', 'arm64'], true)) { http_response_code(400); echo 'bad request'; exit; }
  $e = dc_one('SELECT * FROM dc_engines WHERE version=? AND os=? AND arch=?', [$v, $os, $arch]);
  if (!$e) { http_response_code(404); echo 'no engine'; exit; }
  $path = $cfg['pkg_dir'] . '/' . basename($e['file']);
  if (!is_file($path)) { http_response_code(404); echo 'missing engine package'; exit; }
  dc_event('dl_engine', ($id ?: '') . '|' . $v . '|' . $os . '|' . $arch);
  header('Content-Type: application/octet-stream');
  header('Content-Disposition: attachment; filename="' . basename($e['file']) . '"');
  header('Content-Length: ' . filesize($path));
  readfile($path); exit;
}
http_response_code(400); echo 'bad request';
