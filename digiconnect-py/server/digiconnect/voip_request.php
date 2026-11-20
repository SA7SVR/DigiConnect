<?php
// DigiConnect — VoIP account request from the program's VoIP page (POST). No e-mail is asked for or sent: everything goes directly between this server and the program.
//   action=info                                                              ->  {"ok":true,"open":bool}
//   action=submit : name, call, want (optional extension), msg, lang, inst (installation id), website (must stay empty), consent=1  ->  {"ok":true,"id":N,"token":"..."} | {"ok":false,"err":code}
//   action=status : id, token   ->  new | rejected | approved: ext, password, server, port, transport, domain, blocked, block_until, block_reason
//   action=recover: inst, call  ->  a new token for the account that was given to this installation (the program lost its local data)  ->  {"ok":true,"id":N,"token":"..."}
// The person's name and callsign are stored only to run the account. The token is shown to the program; only its hash is kept.
// The password of an approved account is typed by the administrator in the panel and STAYS with the account: the program asks again whenever it signs in, so a new password set in the panel
// reaches the program by itself and nobody has to type it. It is sent only to the holder of the token.
require __DIR__ . '/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$out = function (array $a) { echo json_encode($a, JSON_UNESCAPED_UNICODE); exit; };
$fail = function (string $err) use ($out) { $out(['ok' => false, 'err' => $err]); };
$S = dc_voip_settings();
$clip = function ($k, $n) { return mb_substr(trim((string)($_REQUEST[$k] ?? '')), 0, $n); };
$act = (string)($_REQUEST['action'] ?? 'submit');
$inst = preg_replace('/[^0-9A-Za-z_-]/', '', $clip('inst', 64));

if ($act === 'info') $out(['ok' => true, 'open' => $S['on']]);                                  // lets the program know whether requests are accepted before it shows the form

if ($act === 'submit') {
  if (!$S['on']) $fail('closed');
  if ($clip('website', 200) !== '') $out(['ok' => true, 'id' => 0, 'token' => bin2hex(random_bytes(16))]);       // a robot filled the hidden field: pretend, store nothing
  if (((string)($_REQUEST['consent'] ?? '')) !== '1') $fail('consent');
  $name = $clip('name', 80); $call = strtoupper(preg_replace('/[^0-9A-Za-z\/]/', '', $clip('call', 15)));
  $want = preg_replace('/[^0-9A-Za-z*#_.-]/', '', $clip('want', 20)); $msg = $clip('msg', 1000); $lang = $clip('lang', 8);
  if ($name === '') $fail('name');
  if (!preg_match('/^[0-9]?[A-Z]{1,2}[0-9][0-9A-Z]{0,3}[A-Z](\/[0-9A-Z]{1,4})?$/', $call)) $fail('call');
  $ip = dc_ip();
  if ((int)dc_scalar('SELECT COUNT(*) FROM dc_voip_req WHERE ip=? AND t>?', [$ip, time() - 86400]) >= $S['per_ip']) $fail('too_many');
  if (dc_one("SELECT id FROM dc_voip_req WHERE status='new' AND call=?", [$call])) $fail('pending');
  $tok = bin2hex(random_bytes(16));
  dc_q('INSERT INTO dc_voip_req(t,tok,name,call,want,body,ip,lang,inst) VALUES(?,?,?,?,?,?,?,?,?)', [time(), hash('sha256', $tok), $name, $call, $want, $msg, $ip, $lang, $inst]);
  $id = (int)dc_db()->lastInsertId();
  dc_alert('voip_req', "$call|$name");                                                            // shown in the panel (dashboard alerts + activity); nothing is e-mailed
  $out(['ok' => true, 'id' => $id, 'token' => $tok]);
}

if ($act === 'recover') {                                                                         // the program lost its token (new install on the same installation id, wiped settings)
  $call = strtoupper(preg_replace('/[^0-9A-Za-z\/]/', '', $clip('call', 15))); $ip = dc_ip();
  if ($inst === '' || $call === '') $fail('unknown');
  if ((int)dc_scalar("SELECT COUNT(*) FROM dc_events WHERE kind='voip_rec' AND t>? AND detail LIKE ?", [time() - 3600, '%|' . $ip]) >= 10) $fail('too_many');
  dc_event('voip_rec', "$call|$ip");
  $r = dc_one("SELECT id FROM dc_voip_req WHERE status='approved' AND inst=? AND call=? ORDER BY decided_t DESC", [$inst, $call]);
  if (!$r) $fail('unknown');
  $tok = bin2hex(random_bytes(16)); dc_q('UPDATE dc_voip_req SET tok=? WHERE id=?', [hash('sha256', $tok), (int)$r['id']]);
  $out(['ok' => true, 'id' => (int)$r['id'], 'token' => $tok]);
}

// status: the person proves it is theirs with the token
$id = (int)($_REQUEST['id'] ?? 0); $tok = $clip('token', 64);
$r = $id > 0 && $tok !== '' ? dc_one('SELECT * FROM dc_voip_req WHERE id=?', [$id]) : null;
if (!$r || !hash_equals((string)$r['tok'], hash('sha256', $tok))) $fail('unknown');
if ($act !== 'status') $fail('action');
if ($r['status'] === 'approved') {
  [$bl, $bu, $br] = dc_voip_blocked($r);
  dc_q('UPDATE dc_voip_req SET delivered_t=? WHERE id=?', [time(), $id]);                         // "the program fetched it" - shown in the panel
  if ($inst !== '' && (string)($r['inst'] ?? '') === '') dc_q('UPDATE dc_voip_req SET inst=? WHERE id=?', [$inst, $id]);
  $out(['ok' => true, 'status' => 'approved', 'ext' => (string)$r['ext'], 'password' => (string)$r['pw'], 'server' => $S['server'], 'port' => $S['port'], 'transport' => $S['transport'], 'domain' => $S['domain'],
        'blocked' => $bl, 'block_until' => $bu, 'block_reason' => $br]);
}
$out(['ok' => true, 'status' => (string)$r['status'], 'reason' => $r['status'] === 'rejected' ? (string)$r['reason'] : '']);
