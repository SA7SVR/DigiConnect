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
$hw = dc_hw_clean($_REQUEST['hw'] ?? '');
$v = $clip('v', 20); $os = $clip('os', 16); $arch = $clip('arch', 16); $shell = $clip('shell', 20); $lang = $clip('lang', 8);
$now = time(); $cfg = dc_cfg();

$cur = dc_one('SELECT id, consent_at, lic_by FROM dc_installs WHERE id=?', [$id]);
$firstReg = !$cur || empty($cur['consent_at']);                                       // first registration of this installation (for "registration with approval")
$byBefore = $cur ? (string)($cur['lic_by'] ?? '') : '';
if (!$cur) {
  dc_q('INSERT INTO dc_installs(id,first_seen,last_seen,version,shell,os,arch,checks,state,demo_until,ip) VALUES(?,?,?,?,?,?,?,0,?,?,?)',
    [$id, $now, $now, $v, $shell, $os, $arch, '', 0, dc_ip()]);
  dc_event('install', "$id|$v|$os|$arch");
  if ($hw !== '') dc_hw_bind($id, $hw, $os, $call);          // same computer as an earlier installation -> takes over its state (dc_inherit_hw)
  // reinstall by the same person (same callsign + e-mail): take over the earlier state, so a new installation id does not restart the demo
  // and a paid licence is not lost. Panel setting "reinstall_id" (Licences) switches this off; a taken-over FULL licence raises an alert in the panel.
  $old = dc_kv('reinstall_id', '1') === '1' ? dc_one("SELECT id, state, demo_until, enabled, note, lic_by, lic_set, owner, lic_code, lic_since, lic_major FROM dc_installs WHERE call=? AND lower(mail)=? AND id<>? ORDER BY first_seen ASC LIMIT 1", [$call, $mail, $id]) : null;
  $cur2 = dc_one('SELECT state FROM dc_installs WHERE id=?', [$id]);
  if ($old && (string)($cur2['state'] ?? '') !== '') $old = null;                      // already inherited by computer
  // a FULL licence is bound to its computer: another computer with the same callsign+e-mail does NOT take it over
  if ($old && $old['state'] === 'full' && $hw !== '') {
    $oh = (string)dc_scalar('SELECT hw FROM dc_installs WHERE id=?', [$old['id']]);
    if ($oh !== '' && $oh !== $hw) {
      dc_alert('clone', "$id|$hw|$os|$call", "Νέος υπολογιστής ($os) με ίδιο διακριτικό/email ($call) ζήτησε την άδεια της " . dc_inst_no($old['id']) . ". ΔΕΝ δόθηκε. Αν είναι ο ίδιος χρήστης, πάτα «Ελευθέρωση υπολογιστή» στην παλιά εγκατάσταση.\nA new computer ($os) with the same callsign/e-mail ($call) asked for the licence of " . dc_inst_no($old['id']) . ". It was NOT given. If it is the same user, press \"Free the computer\" on the old installation.");
      $old = null;
    }
  }
  if ($old) {
    dc_q('UPDATE dc_installs SET state=?, demo_until=?, enabled=?, note=?, lic_by=?, lic_set=?, owner=?, lic_code=?, lic_since=? WHERE id=?',
      [$old['state'], $old['demo_until'], $old['enabled'], $old['note'], $old['lic_by'], $old['lic_set'], $old['owner'], $old['lic_code'], $old['lic_since'], $id]);
    if (isset($old['lic_major'])) dc_q('UPDATE dc_installs SET lic_major=? WHERE id=?', [$old['lic_major'], $id]);
    if ($old['state'] === 'full') {
      $who = trim(dc_inst_no($id) . ' ' . $call . ' ' . $name);
      dc_alert('reinstall_id', "$id|{$old['id']}|" . dc_inst_no($old['id']) . "|full|$call",
        "Νέα εγκατάσταση $who (ίδιο διακριτικό και email) πήρε αυτόματα την άδεια της " . dc_inst_no($old['id']) . ". Αν δεν είναι ο ίδιος χρήστης, κλείδωσε την στο panel.\nNew installation $who (same callsign and e-mail) automatically took the licence of " . dc_inst_no($old['id']) . ". If it is not the same user, lock it in the panel.");
    } else dc_event('reinstall', "$id|{$old['id']}|" . dc_inst_no($old['id']) . "|{$old['state']}");
  }
}
dc_q('UPDATE dc_installs SET name=?, call=?, dmr_id=?, mail=?, lang=?, consent_at=COALESCE(consent_at,?), last_seen=?, ip=? WHERE id=?',
  [$name, $call, $dmr, $mail, $lang, $now, $now, dc_ip(), $id]);
dc_event('register', "$id|$call");
// "Registrations need approval" (panel › Settings): a NEW installation that only has the default state waits until the administrator approves it
if (dc_kv('reg_approval', '0') === '1' && $firstReg) {
  $row = dc_one('SELECT state, lic_by FROM dc_installs WHERE id=?', [$id]); $by = (string)($row['lic_by'] ?? '');
  if (($by === '' || $by === 'default' || $byBefore === 'default' || $byBefore === '') && !preg_match('/^(reinstall|payment|code|panel)/', $by) && (string)$row['state'] !== 'full') {
    dc_q("UPDATE dc_installs SET state='pending', demo_until=0, lic_by='pending', lic_set=? WHERE id=?", [$now, $id]);
    dc_alert('reg_pending', "$id|$call|$name|$mail",
      "Νέα εγγραφή περιμένει έγκριση: $call · $name · $mail (" . dc_inst_no($id) . "). Έγκριση: panel › Εγκαταστάσεις.\nNew registration waiting for approval: $call · $name · $mail (" . dc_inst_no($id) . "). Approve in panel › Installations.");
  }
}

$in = dc_one('SELECT * FROM dc_installs WHERE id=?', [$id]);
echo json_encode(dc_lic_answer($id, $hw, ['os' => $os, 'call' => $call]));
