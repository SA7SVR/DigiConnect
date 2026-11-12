<?php
// DigiConnect — two-way messaging between a user and the owner (same as HAM Digi).
//   POST  -> a user sends a message to the owner (from inside the program, or from the website).
//   GET ?poll&id=<install>  -> the program asks for the owner's replies to this installation.
// The owner reads everything and replies in the control panel (Messages from users). A reply is delivered two ways: through the
// update check (msgs) and through this poll, so it always arrives.
require __DIR__ . '/lib.php';
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Cache-Control: no-store');
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') { http_response_code(204); exit; }

function dc_clean($s, $n) { return substr(trim(strip_tags((string)$s)), 0, $n); }

// ---- the program polls for owner replies to this installation ----
if (isset($_GET['poll'])) {
  header('Content-Type: application/json; charset=utf-8');
  $id = substr(preg_replace('/[^A-Za-z0-9_-]/', '', $_GET['id'] ?? ''), 0, 64);
  if (!$id) { echo json_encode(['ok' => 1, 'replies' => []]); exit; }
  $out = [];
  foreach (dc_q("SELECT id,subject,reply,reply_t FROM dc_inbox WHERE install=? AND reply IS NOT NULL AND reply<>'' ORDER BY reply_t DESC LIMIT 20", [$id])->fetchAll() as $r)
    $out[] = ['id' => 'r' . $r['id'], 't' => (int)$r['reply_t'], 'subject' => $r['subject'], 'reply' => $r['reply']];
  echo json_encode(['ok' => 1, 'replies' => $out], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
  exit;
}

// ---- a user sends a message to the owner ----
header('Content-Type: application/json; charset=utf-8');
$raw = file_get_contents('php://input');
$in = json_decode((string)$raw, true);
if (!is_array($in)) $in = $_POST;

$body = dc_clean($in['body'] ?? '', 4000);
if ($body === '') { http_response_code(400); echo json_encode(['ok' => 0, 'error' => 'empty']); exit; }

$ip = dc_ip();
// light flood guard: at most 6 messages per IP per hour
if ((int)dc_scalar('SELECT COUNT(*) FROM dc_inbox WHERE ip=? AND t>?', [$ip, time() - 3600]) >= 6) { http_response_code(429); echo json_encode(['ok' => 0, 'error' => 'too_many']); exit; }

$call = strtoupper(preg_replace('/[^A-Za-z0-9\/]/', '', dc_clean($in['call'] ?? '', 16)));
$install = substr(preg_replace('/[^A-Za-z0-9_-]/', '', (string)($in['install'] ?? $in['id'] ?? '')), 0, 64);
$topic = dc_clean($in['topic'] ?? '', 30);               // e.g. "reinstall" (lost installer), "activation", "bug", "other"
$subject = dc_clean($in['subject'] ?? '', 120);
if ($subject === '') $subject = $topic ?: 'Message';

dc_q('INSERT INTO dc_inbox(t,install,call,email,name,os,version,topic,subject,body,ip,lang,src,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', [
  time(), $install, $call, dc_clean($in['email'] ?? '', 120), dc_clean($in['name'] ?? '', 80), dc_clean($in['os'] ?? '', 10), dc_clean($in['version'] ?? '', 20),
  $topic, $subject, $body, $ip, dc_clean($in['lang'] ?? 'el', 6), ($in['src'] ?? '') === 'web' ? 'web' : 'app', 'new',
]);
$mid = (int)dc_scalar('SELECT last_insert_rowid()');
dc_event('inbox', ($call ?: 'web') . '|' . ($topic ?: 'msg') . '|' . $subject);
echo json_encode(['ok' => 1, 'id' => $mid], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
