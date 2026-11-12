<?php
// DigiConnect — update manifest + install ping. The shell calls this on its check interval.
// GET/POST: id, v (version), os, arch, shell  ->  JSON {state, update, version, pkg, sha256, size, checkEvery, notes}
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$id    = $_REQUEST['id'] ?? '';
$v     = $_REQUEST['v'] ?? '';
$os    = $_REQUEST['os'] ?? '';
$arch  = $_REQUEST['arch'] ?? '';
$shell = $_REQUEST['shell'] ?? '';
$hw    = dc_hw_clean($_REQUEST['hw'] ?? '');
$now   = time();
$cfg   = dc_cfg();

if ($id) {
  $cur = dc_one('SELECT id FROM dc_installs WHERE id=?', [$id]);
  if (!$cur) {
    dc_q('INSERT INTO dc_installs(id,first_seen,last_seen,version,shell,os,arch,checks,state,demo_until,ip) VALUES(?,?,?,?,?,?,?,1,?,?,?)',
      [$id, $now, $now, $v, $shell, $os, $arch, '', 0, dc_ip()]);          // '' = follows the default policy (panel › Licences); resolved just below
    dc_event('install', "$id|$v|$os|$arch");
  } else {
    dc_q('UPDATE dc_installs SET last_seen=?, version=?, os=?, arch=?, shell=?, checks=checks+1, ip=? WHERE id=?',
      [$now, $v, $os, $arch, $shell, dc_ip(), $id]);
  }
}

if ($id) dc_daily_mark($id, $v, $os);
$in = $id ? dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]) : null;
$ans = $id ? dc_lic_answer($id, $hw, ['os' => $os]) : ['state' => 'full', 'left' => '', 'msg' => ''] + dc_lic_public();

$out = ['ok' => true, 'checkEvery' => max(60, (int)dc_opt('check_every', $cfg['check_every']))] + $ans;

$out['msgs'] = $in ? dc_messages_for($id, (int)$in['first_seen']) : [];

$rel = dc_opt('paused', '0') === '1' ? null : dc_active_release($id ?: null);
if ($rel) {
  $base = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? '') . rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? ''), '/');
  $newer = ($v === '' || version_compare($rel['version'], $v, '>'));
  $out['latest'] = $rel['version'];
  $out['update'] = $newer ? 'available' : 'uptodate';
  if ($newer) {
    $out['version']   = $rel['version'];
    $out['min_shell'] = $rel['min_shell'];
    $out['pkg']       = $base . '/download.php?f=pkg&v=' . rawurlencode($rel['version']) . ($id ? '&id=' . rawurlencode($id) : '');
    $out['sha256']    = $rel['sha256'];
    $out['size']      = (int)$rel['size'];
    $out['notes']     = ['el' => $rel['notes_el'], 'en' => $rel['notes_en'], 'sv' => $rel['notes_sv'], 'it' => $rel['notes_it']];
  }
} else {
  $out['update'] = 'none';
}
echo json_encode($out);
