<?php
// DigiConnect — ONE conversation between a user and the owner (same as HAM Digi).
//   GET  ?chat=poll&id=<install>&after=<n>[&read=1] -> the program asks for new messages of its conversation (and tells the server it is online); read=1 only when the window is open.
//   POST chat=send, id, body                  -> the user writes in the conversation.
//   GET  ?chat=img&id=<install>&m=<n>         -> a picture the owner sent in the conversation.
//   POST body (+ topic, subject, ...)         -> the older programs: the message goes into the same conversation (diagnostics reports stay in the inbox).
//   GET  ?poll&id=<install>                   -> the older programs ask for the owner's replies (now the owner's messages of the conversation).
// The owner reads and writes in the control panel (Chats); a website visitor's chat (talk.php) is the same kind of thread.
require __DIR__ . '/lib.php';
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Cache-Control: no-store');
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') { http_response_code(204); exit; }

function dc_clean($s, $n) { return substr(trim(strip_tags((string)$s)), 0, $n); }

// the installation behind an id (ids of unknown installations never create conversations)
function dc_chat_inst(string $id): array { return $id === '' ? [] : dc_inst_contact($id); }
$cid = substr(preg_replace('/[^A-Za-z0-9_-]/', '', (string)($_REQUEST['id'] ?? $_REQUEST['install'] ?? '')), 0, 64);
$chat = (string)($_REQUEST['chat'] ?? '');

// ---- the program asks for the new messages of its conversation ----
if ($chat === 'poll') {
  header('Content-Type: application/json; charset=utf-8');
  $inst = dc_chat_inst($cid); $now = time();
  if (!$inst) { echo json_encode(['ok' => 1, 'msgs' => [], 'on' => 0, 'typ' => 0, 'now' => $now]); exit; }
  $tok = dc_inst_token($cid); $after = max(0, (int)($_GET['after'] ?? 0)); $out = [];
  dc_upsert('dc_chat_th', ['token' => $tok], ['seen_u' => $now, 'inst' => $cid]);               // "online in the chat" for the panel
  foreach (dc_q('SELECT * FROM dc_chat WHERE token=? AND id>? ORDER BY id ASC LIMIT 100', [$tok, $after])->fetchAll() as $r) $out[] = dc_chat_row_out($r);
  $upd = []; foreach (dc_q("SELECT * FROM dc_chat WHERE token=? AND id<=? AND ((who='user' AND read_owner=1) OR del=1) ORDER BY id DESC LIMIT 60", [$tok, $after])->fetchAll() as $r) $upd[] = dc_chat_row_out($r);
  if (!empty($_GET['read'])) dc_q("UPDATE dc_chat SET read_user=1 WHERE token=? AND who='owner' AND read_user=0 AND id<=?", [$tok, max($after, $out ? (int)end($out)['id'] : 0)]);   // only the open conversation window marks messages as read; the background check just counts
  $typ = (int)dc_scalar('SELECT typ_o FROM dc_chat_th WHERE token=?', [$tok]) > $now - 4 ? 1 : 0;
  echo json_encode(['ok' => 1, 'msgs' => $out, 'upd' => $upd, 'on' => (int)dc_kv('chat_owner_seen', 0) > $now - 25 ? 1 : 0, 'typ' => $typ, 'now' => $now], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
  exit;
}
// ---- a picture the owner sent (only to this installation) ----
if ($chat === 'img') {
  if (!dc_chat_inst($cid)) { http_response_code(404); exit; }
  dc_chat_serve_image((int)($_GET['m'] ?? 0), dc_inst_token($cid));
}
// ---- the older programs poll for the owner's replies ----
if (isset($_GET['poll'])) {
  header('Content-Type: application/json; charset=utf-8');
  $out = [];
  if ($cid !== '' && dc_chat_inst($cid))
    foreach (dc_q("SELECT id,body,t FROM dc_chat WHERE token=? AND who='owner' AND del=0 AND body<>'' ORDER BY id DESC LIMIT 20", [dc_inst_token($cid)])->fetchAll() as $r)
      $out[] = ['id' => 'r' . $r['id'], 't' => (int)$r['t'], 'subject' => '', 'reply' => $r['body']];
  echo json_encode(['ok' => 1, 'replies' => $out], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
  exit;
}

// ---- a user sends a message to the owner ----
header('Content-Type: application/json; charset=utf-8');
$raw = file_get_contents('php://input');
$in = json_decode((string)$raw, true);
if (!is_array($in)) $in = $_POST;

$topic = dc_clean($in['topic'] ?? '', 30);               // e.g. "reinstall" (lost installer), "activation", "bug", "other", "diagnostics"
$isDiag = $topic === 'diagnostics';
$body = dc_clean($in['body'] ?? '', $isDiag ? 60000 : 4000);      // a diagnostics report (log end) is longer than a message
if ($body === '') { http_response_code(400); echo json_encode(['ok' => 0, 'error' => 'empty']); exit; }

$ip = dc_ip();
$call = strtoupper(preg_replace('/[^A-Za-z0-9\/]/', '', dc_clean($in['call'] ?? '', 16)));
$install = substr(preg_replace('/[^A-Za-z0-9_-]/', '', (string)($in['install'] ?? $in['id'] ?? '')), 0, 64);
$subject = dc_clean($in['subject'] ?? '', 120);
if ($subject === '') $subject = $topic ?: 'Message';

// a message written inside the program, or by an older program: it goes into the conversation of that installation
if (!$isDiag && $install !== '' && dc_chat_inst($install)) {
  if ((int)dc_scalar("SELECT COUNT(*) FROM dc_chat WHERE ip=? AND who='user' AND t>?", [$ip, time() - 3600]) >= 40) { http_response_code(429); echo json_encode(['ok' => 0, 'error' => 'too_many']); exit; }
  $text = ($chat !== 'send' && $subject !== '' && $subject !== 'Message' && $subject !== $topic && $subject !== 'app' ? $subject . "\n\n" : '') . $body;
  $mid = dc_chat_user_post($install, $text, $ip, ['call' => $call, 'email' => dc_clean($in['email'] ?? '', 120), 'name' => dc_clean($in['name'] ?? '', 80)]);
  echo json_encode(['ok' => 1, 'id' => $mid], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
  exit;
}
// light flood guard: at most 6 messages per IP per hour
if ((int)dc_scalar('SELECT COUNT(*) FROM dc_inbox WHERE ip=? AND t>?', [$ip, time() - 3600]) >= 6) { http_response_code(429); echo json_encode(['ok' => 0, 'error' => 'too_many']); exit; }

// reports (diagnostics) and messages without a known installation (a form on the website) stay in the inbox
dc_q('INSERT INTO dc_inbox(t,install,call,email,name,os,version,topic,subject,body,ip,lang,src,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', [
  time(), $install, $call, dc_clean($in['email'] ?? '', 120), dc_clean($in['name'] ?? '', 80), dc_clean($in['os'] ?? '', 10), dc_clean($in['version'] ?? '', 20),
  $topic, $subject, $body, $ip, dc_clean($in['lang'] ?? 'el', 6), ($in['src'] ?? '') === 'web' ? 'web' : 'app', 'new',
]);
$mid = (int)dc_scalar('SELECT last_insert_rowid()');
dc_event('inbox', ($call ?: 'web') . '|' . ($topic ?: 'msg') . '|' . $subject);
echo json_encode(['ok' => 1, 'id' => $mid], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
