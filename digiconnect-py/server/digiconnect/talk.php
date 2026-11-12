<?php
// Direct, private chat between a website visitor and the owner (SA7SVR) — no e-mail needed.
// Each visitor gets their OWN secret thread (a random token kept in a cookie + a shareable link).
// A visitor only ever sees their own conversation; nobody can see anyone else's. The owner reads
// and replies from the control panel (Συνομιλίες). Messages are kept, nothing is lost.
// Pictures (JPG/PNG/GIF/WebP, max 5 MB) are stored in data/chat/ and are only served to the two people of that chat.
require __DIR__ . '/lib.php';

function clean($s, $n) { return substr(trim(strip_tags((string)$s)), 0, $n); }
function newtok() { return bin2hex(random_bytes(16)); }

$lang = preg_match('/^(el|en|sv|it)$/', $_GET['lang'] ?? '') ? $_GET['lang'] : (strpos($_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '', 'sv') !== false ? 'sv' : (strpos($_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '', 'it') !== false ? 'it' : (strpos($_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '', 'el') !== false ? 'el' : 'en')));
$IT_TALK = [
  'Callsign' => 'Nominativo',
  'Contact' => 'Contatto',
  'Copy' => 'Copia',
  'Demo & Donate' => 'Demo & Donate',
  'Download' => 'Scarica',
  'Drop the picture here' => 'Rilascia qui l’immagine',
  'Enter = send · Shift+Enter = new line' => 'Invio = invia · Maiusc+Invio = nuova riga',
  'Features' => 'Funzioni',
  'Home' => 'Home',
  'Light / dark theme' => 'Tema chiaro / scuro',
  'Live chat' => 'Chat dal vivo',
  'Message…' => 'Messaggio…',
  'Name' => 'Nome',
  'Not sent — please try again.' => 'Non inviato — riprova.',
  'Only JPG, PNG, GIF or WebP pictures.' => 'Solo immagini JPG, PNG, GIF o WebP.',
  'Picture' => 'Immagine',
  'Private conversation — only you and I can see it.' => 'Conversazione privata — solo tu e io possiamo vederla.',
  'Read' => 'Letto',
  'SA7SVR is in the panel — a reply should come soon' => 'SA7SVR è nel pannello — la risposta arriverà presto',
  'SA7SVR is typing…' => 'SA7SVR sta scrivendo…',
  'Screens' => 'Immagini',
  'Send' => 'Invia',
  'Sent' => 'Inviato',
  'The picture is too big (max 5 MB).' => 'L’immagine è troppo grande (max 5 MB).',
  'Theme' => 'Tema',
  'This message was removed' => 'Questo messaggio è stato rimosso',
  'Today' => 'Oggi',
  'Too many messages, try later.' => 'Troppi messaggi, riprova più tardi.',
  'Too many pictures, try later.' => 'Troppe immagini, riprova più tardi.',
  'Write your message below (you can send a picture too). You will get a reply right here on this page — no e-mail needed. Keep the link to see the answer.' => 'Scrivi il tuo messaggio qui sotto (puoi inviare anche un’immagine). Riceverai la risposta qui, in questa pagina — non serve l’e-mail. Conserva il link per vedere la risposta.',
  'Yesterday' => 'Ieri',
  'You' => 'Tu',
  'You will see the answer here as soon as I reply.' => 'Vedrai la risposta qui non appena risponderò.',
  'min' => 'min',
  'new messages' => 'nuovi messaggi',
  'now' => 'ora'
];
function T($el, $en, $sv) { global $lang, $IT_TALK; return $lang === 'el' ? $el : ($lang === 'sv' ? $sv : ($lang === 'it' ? ($IT_TALK[$en] ?? $en) : $en)); }
$LANGS = ['el' => 'Ελληνικά', 'en' => 'English', 'sv' => 'Svenska', 'it' => 'Italiano'];
if (!isset($_GET['api']) && !isset($_GET['img'])) dc_track_visit('chat', $lang);   // page views only, not the polling

$tok = preg_replace('/[^a-f0-9]/', '', $_GET['t'] ?? ($_COOKIE['dc_talk'] ?? ''));
if (strlen($tok) !== 32) $tok = '';
$api = (string)($_GET['api'] ?? '');

// ---------------- a picture of this chat ----------------
if (isset($_GET['img'])) { if (!$tok) { http_response_code(404); exit; } dc_chat_serve_image((int)$_GET['img'], $tok); }

// ---------------- API: live updates (also marks the owner's replies as read) ----------------
if ($api === 'poll') {
  $after = (int)($_GET['after'] ?? 0); $out = []; $upd = []; $typ = 0; $now = time();
  if ($tok) {
    dc_upsert('dc_chat_th', ['token' => $tok], ['seen_u' => $now]);
    foreach (dc_q('SELECT * FROM dc_chat WHERE token=? AND id>? ORDER BY id ASC LIMIT 100', [$tok, $after]) as $r) $out[] = dc_chat_row_out($r);
    foreach (dc_q("SELECT * FROM dc_chat WHERE token=? AND id<=? AND ((who='user' AND read_owner=1) OR del=1) ORDER BY id DESC LIMIT 60", [$tok, $after]) as $r) $upd[] = dc_chat_row_out($r);
    dc_q("UPDATE dc_chat SET read_user=1 WHERE token=? AND who='owner' AND read_user=0", [$tok]);
    $typ = (int)dc_scalar('SELECT typ_o FROM dc_chat_th WHERE token=?', [$tok]) > $now - 4 ? 1 : 0;
  }
  dc_chat_json(['ok' => 1, 'msgs' => $out, 'upd' => $upd, 'typ' => $typ, 'on' => (int)dc_kv('chat_owner_seen', 0) > $now - 25 ? 1 : 0, 'now' => $now]);
}
if ($api === 'typing' && ($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') { if ($tok) dc_upsert('dc_chat_th', ['token' => $tok], ['typ_u' => time()]); dc_chat_json(['ok' => 1]); }

// ---------------- POST: start a thread or send a message (with JS: JSON answer; without JS: redirect) ----------------
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
  $wantJson = $api === 'send';
  $fail = function ($msg, $code = 400) use ($wantJson, $tok, $lang) { if ($wantJson) { http_response_code($code); dc_chat_json(['ok' => 0, 'err' => $msg]); } http_response_code($code); exit($msg); };
  $ip = dc_ip();
  if ((int)dc_scalar('SELECT COUNT(*) FROM dc_chat WHERE ip=? AND t>?', [$ip, time() - 3600]) >= 40) $fail(T('Πολλά μηνύματα, δοκίμασε αργότερα.', 'Too many messages, try later.', 'För många meddelanden, försök senare.'), 429);
  $body = trim((string)($_POST['body'] ?? '')); $body = function_exists('mb_substr') ? mb_substr($body, 0, 4000) : substr($body, 0, 4000);
  $img = '';
  if (!empty($_FILES['image']['name'])) {
    if ((int)dc_scalar("SELECT COUNT(*) FROM dc_chat WHERE ip=? AND img<>'' AND t>?", [$ip, time() - 3600]) >= 12) $fail(T('Πολλές φωτογραφίες, δοκίμασε αργότερα.', 'Too many pictures, try later.', 'För många bilder, försök senare.'), 429);
    try { $img = dc_chat_save_image('image'); } catch (Exception $e) { $fail(dc_chat_img_error($e->getMessage(), $lang)); }
  }
  if ($body !== '' || $img !== '') {
    if (!$tok) { $tok = newtok(); setcookie('dc_talk', $tok, time() + 86400 * 365, rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/') . '/'); } // first message → create a private thread
    $first = (int)dc_scalar('SELECT COUNT(*) FROM dc_chat WHERE token=?', [$tok]) === 0;
    dc_q('INSERT INTO dc_chat(token,t,who,body,img,"call",email,name,ip,read_owner) VALUES(?,?,?,?,?,?,?,?,?,0)', [
      $tok, time(), 'user', $body, $img,
      strtoupper(preg_replace('/[^A-Za-z0-9\/]/', '', clean($_POST['call'] ?? '', 16))),
      clean($_POST['email'] ?? '', 120), clean($_POST['name'] ?? '', 80), $ip,
    ]);
    $id = (int)dc_db()->lastInsertId();
    $prev = $body !== '' ? mb_substr($body, 0, 60) : '[photo]';
    if ($first) dc_event('chat_new', (clean($_POST['call'] ?? '', 16) ?: 'web') . '|' . $tok . '|' . $prev);
    else dc_event('chat_msg', $tok . '|' . $prev);
    dc_q('UPDATE dc_chat_th SET typ_u=0 WHERE token=?', [$tok]);
    if ($wantJson) dc_chat_json(['ok' => 1, 'token' => $tok, 'msg' => dc_chat_row_out(dc_q('SELECT * FROM dc_chat WHERE id=?', [$id])->fetch())]);
  } elseif ($wantJson) dc_chat_json(['ok' => 0]);
  header('Location: talk.php?t=' . $tok . '&lang=' . $lang); exit;
}

// ---------------- render the chat page ----------------
$msgs = []; $lastId = 0;
if ($tok) { foreach (dc_q('SELECT * FROM dc_chat WHERE token=? ORDER BY id ASC LIMIT 500', [$tok]) as $r) $msgs[] = dc_chat_row_out($r); if ($msgs) $lastId = (int)end($msgs)['id']; dc_q("UPDATE dc_chat SET read_user=1 WHERE token=? AND who='owner'", [$tok]); dc_upsert('dc_chat_th', ['token' => $tok], ['seen_u' => time()]); }
$LB = ['you' => T('Εσύ', 'You', 'Du'), 'owner' => 'SA7SVR', 'today' => T('Σήμερα', 'Today', 'Idag'), 'yest' => T('Χθες', 'Yesterday', 'Igår'), 'removed' => T('Το μήνυμα αφαιρέθηκε', 'This message was removed', 'Meddelandet togs bort'),
  'seen' => T('Διαβάστηκε', 'Read', 'Läst'), 'sent' => T('Στάλθηκε', 'Sent', 'Skickat'), 'typing' => T('Ο SA7SVR γράφει…', 'SA7SVR is typing…', 'SA7SVR skriver…'), 'on' => T('Ο SA7SVR είναι στο πάνελ — θα απαντήσει σύντομα', 'SA7SVR is in the panel — a reply should come soon', 'SA7SVR är i panelen — svar kommer snart'),
  'off' => T('Θα δεις την απάντηση εδώ μόλις απαντήσω.', 'You will see the answer here as soon as I reply.', 'Du ser svaret här så fort jag svarar.'), 'errtype' => T('Μόνο εικόνες JPG, PNG, GIF ή WebP.', 'Only JPG, PNG, GIF or WebP pictures.', 'Endast JPG-, PNG-, GIF- eller WebP-bilder.'),
  'errbig' => T('Η φωτογραφία είναι πολύ μεγάλη (μέχρι 5 MB).', 'The picture is too big (max 5 MB).', 'Bilden är för stor (max 5 MB).'), 'errsend' => T('Δεν στάλθηκε — ξαναδοκίμασε.', 'Not sent — please try again.', 'Inte skickat — försök igen.'),
  'new' => T('νέα μηνύματα', 'new messages', 'nya meddelanden'), 'now' => T('τώρα', 'now', 'nu'), 'min' => T('λ.', 'min', 'min'), 'drop' => T('Άφησε τη φωτογραφία εδώ', 'Drop the picture here', 'Släpp bilden här'), 'copy' => T('Αντιγραφή', 'Copy', 'Kopiera')];
header('Content-Type: text/html; charset=utf-8');
?><!doctype html>
<html lang="<?= $lang ?>"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<script>(function(){try{var t=localStorage.getItem('dc_theme')||'dark';document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();</script>
<title>DigiConnect · <?= T('Επικοινωνία', 'Contact', 'Kontakt') ?></title>
<style>
  :root{--bg:#0a1026;--bg2:#0c1430;--card:#121a39;--line:#263257;--line2:#34466a;--fg:#e8eefc;--mut:#8fa0c8;--me:#1f6feb;--own:#1d7a4d;--acc:#49b0ff;--head:rgba(10,16,38,.86);--btn-h:rgba(73,176,255,.14)}
  :root[data-theme="light"]{--bg:#f4f7fb;--bg2:#ffffff;--card:#ffffff;--line:#d3dced;--line2:#bcc9dd;--fg:#10202f;--mut:#5a6b7e;--me:#1f6feb;--own:#1f9d55;--acc:#0a84c6;--head:rgba(255,255,255,.9);--btn-h:rgba(10,132,198,.1)}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif;min-height:100vh;display:flex;flex-direction:column}
  .wrap{max-width:720px;width:100%;margin:0 auto;flex:1;display:flex;flex-direction:column}
  header.top{position:sticky;top:0;z-index:5;background:transparent;padding:10px 16px}
  header.top .bar{position:relative;max-width:1040px;margin:0 auto;display:flex;align-items:center;gap:10px 14px;min-height:54px;padding:6px 14px;background:var(--head);backdrop-filter:blur(10px);border:1px solid var(--line2);border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.18)}
  .brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--fg);flex:0 0 auto}
  .brand img{height:34px;width:34px;border-radius:8px}.brand b{font-size:17px;white-space:nowrap}
  nav.mnav{margin-left:auto;display:flex;gap:6px;align-items:center}
  nav.mnav a{color:var(--fg);text-decoration:none;padding:6px 12px;border:1px solid var(--line2);border-radius:999px;font-size:13.5px;font-weight:600;white-space:nowrap;transition:color .15s,border-color .15s,background .15s}
  nav.mnav a:hover{color:var(--acc);border-color:var(--acc);background:var(--btn-h)}
  nav.mnav a.on{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 45%,transparent)}
  .hrow{display:flex;align-items:center;gap:8px}
  .hc{display:inline-flex;align-items:center;justify-content:center;height:34px;min-width:34px;padding:0 10px;border:1px solid var(--line2);border-radius:10px;background:transparent;color:var(--fg);font:600 14px inherit;cursor:pointer}
  .hc:hover{border-color:var(--acc)}
  .langpick{position:relative}
  .langpick>summary{list-style:none;display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 10px;border:1px solid var(--line2);border-radius:10px;cursor:pointer;color:var(--fg);font-size:14px;font-weight:600;white-space:nowrap}
  .langpick>summary::-webkit-details-marker{display:none}
  .langpick>summary .car{color:var(--mut);font-size:11px}
  .langpick>summary:hover,.langpick[open]>summary{border-color:var(--acc)}
  .langpick .menu{position:absolute;right:0;top:42px;min-width:170px;background:var(--card);border:1px solid var(--line2);border-radius:12px;padding:6px;box-shadow:0 18px 44px rgba(0,0,0,.35);z-index:9}
  .langpick .menu a{display:flex;align-items:center;gap:9px;padding:9px 11px;border-radius:8px;text-decoration:none;color:var(--fg);font-size:14px}
  .langpick .menu a:hover{background:var(--btn-h)}.langpick .menu a.on{color:var(--acc);font-weight:700}
  .langpick .menu a .ck{margin-left:auto}
  .navtog{display:none}
  @media(max-width:760px){
   nav.mnav{position:absolute;left:0;right:0;top:100%;margin:6px 0 0;flex-direction:column;align-items:stretch;gap:2px;background:var(--card);border:1px solid var(--line2);border-radius:14px;padding:10px;box-shadow:0 18px 40px rgba(0,0,0,.35);transform:translateY(-8px);opacity:0;visibility:hidden;transition:.18s}
   nav.mnav.open{transform:none;opacity:1;visibility:visible}
   nav.mnav a{padding:11px 10px;font-size:16px}
   .navtog{display:inline-flex;align-items:center;justify-content:center;width:38px;height:34px;border:1px solid var(--line2);border-radius:10px;background:transparent;color:var(--fg);font-size:18px;cursor:pointer}
  }
  html,body{height:100%}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif;display:flex;flex-direction:column;height:100vh;height:100dvh;overflow:hidden}
  .wrap{max-width:780px;width:100%;margin:0 auto;flex:1;display:flex;flex-direction:column;min-height:0;padding:0 12px 10px}
  header.top{position:relative;z-index:5;background:transparent;padding:10px 16px;flex:0 0 auto}
  .card{flex:1;display:flex;flex-direction:column;min-height:0;background:var(--card);border:1px solid var(--line2);border-radius:18px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.18)}
  .ch{display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line);background:var(--bg2)}
  .ch .av{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#1f6feb,#49b0ff);display:grid;place-items:center;color:#fff;font-weight:800;font-size:14px;flex:0 0 auto}
  .ch b{display:block;font-size:15px}.ch small{display:block;color:var(--mut);font-size:12.5px}.ch small.on{color:#3ee08b}
  .fields{display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px 0}
  .fields input{flex:1;min-width:120px}
  input,textarea{background:var(--bg);border:1px solid var(--line);color:var(--fg);border-radius:10px;padding:10px 12px;font:inherit}
  .feedw{flex:1;position:relative;min-height:0;display:flex;flex-direction:column}
  .feed{flex:1;padding:14px 16px;display:flex;flex-direction:column;gap:3px;overflow-y:auto;overscroll-behavior:contain;min-height:0}
  .day{align-self:center;margin:12px 0 6px;font-size:12px;color:var(--mut);background:var(--bg2);border:1px solid var(--line);border-radius:999px;padding:2px 12px}
  .m{display:flex;max-width:82%}.m.user{align-self:flex-end}.m.owner{align-self:flex-start}.m.first{margin-top:8px}
  .bub{position:relative;padding:7px 11px 5px;border-radius:16px;line-height:1.45;word-wrap:break-word;overflow-wrap:anywhere;min-width:64px}
  .m.user .bub{background:var(--me);color:#fff;border-bottom-right-radius:5px}.m.user .bub a{color:#fff;text-decoration:underline}
  .m.owner .bub{background:var(--own);color:#fff;border-bottom-left-radius:5px}.m.owner .bub a{color:#fff;text-decoration:underline}
  .bub code{font:12.5px ui-monospace,Menlo,Consolas,monospace;background:rgba(0,0,0,.28);border-radius:5px;padding:1px 5px}
  .bub pre{margin:6px 0;padding:8px 10px;background:rgba(0,0,0,.35);border-radius:9px;font:12.5px/1.45 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap;overflow-x:auto}
  .bub img.ph{display:block;width:240px;max-width:100%;height:auto;border-radius:11px;margin:2px 0 4px;cursor:zoom-in;background:rgba(0,0,0,.2)}
  .bub .ft{display:flex;gap:5px;justify-content:flex-end;align-items:center;font-size:11px;opacity:.75;margin-top:1px;white-space:nowrap}
  .bub .tk{font-size:12px;letter-spacing:-3px}.bub .tk.rd{color:#9ff5c2;opacity:1}.bub .del{font-style:italic;opacity:.7}
  .intro{color:var(--mut);text-align:center;padding:20px;border:1px dashed var(--line);border-radius:12px;margin:8px 16px}
  .typ{height:22px;padding:0 18px;color:#3ee08b;font-size:12.5px;font-style:italic}
  .newb{position:absolute;right:16px;bottom:8px;border:0;background:var(--acc);color:#04142e;font-weight:700;border-radius:999px;padding:6px 14px;box-shadow:0 6px 18px rgba(0,0,0,.4);display:none;cursor:pointer}
  .comp{border-top:1px solid var(--line);background:var(--bg2);padding:8px 14px 10px}
  .tool{display:flex;gap:2px;margin-bottom:6px;align-items:center;position:relative}
  .tool button{border:0;background:transparent;border-radius:8px;min-width:32px;height:30px;color:var(--mut);font-size:14px;padding:0 6px;cursor:pointer}
  .tool button:hover{background:var(--btn-h);color:var(--fg)}.tool .sp{flex:1}.tool small{color:var(--mut);font-size:11.5px}
  .row{display:flex;gap:10px;align-items:flex-end}
  textarea{flex:1;resize:none;min-height:44px;max-height:150px;border-radius:12px;padding:11px 13px;line-height:1.4}
  .sendb{border:0;background:var(--acc);color:#04142e;font:700 15px inherit;border-radius:12px;height:44px;padding:0 20px;cursor:pointer;display:flex;align-items:center;gap:7px}
  .sendb:disabled{opacity:.45;cursor:default}.sendb svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
  .att{display:none;margin:0 0 8px;align-items:center;gap:10px;background:var(--bg);border:1px solid var(--line2);border-radius:11px;padding:6px 10px}
  .att img{height:54px;border-radius:8px}.att span{flex:1;font-size:12.5px;color:var(--mut);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.att button{border:0;background:var(--line);color:var(--fg);border-radius:50%;width:26px;height:26px;cursor:pointer}
  .err{color:#ff6b7d;font-size:12.5px;margin-bottom:4px}
  .note{color:var(--mut);font-size:12px;text-align:center;padding:6px 6px 0}
  .lb{position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:100;display:none;align-items:center;justify-content:center;cursor:zoom-out;padding:20px}.lb.on{display:flex}.lb img{max-width:100%;max-height:100%;border-radius:8px}
  .dropz{position:absolute;inset:0;background:rgba(73,176,255,.2);border:3px dashed var(--acc);border-radius:14px;display:none;place-items:center;font-weight:700;font-size:18px;z-index:5;pointer-events:none}.feedw.drag .dropz{display:grid}
  @media(max-width:600px){.wrap{padding:0 6px 6px}.m{max-width:92%}}
</style></head>
<body>
  <header class="top"><div class="bar">

    <a class="brand" href="./?lang=<?= $lang ?>"><img src="assets/hz-emblem.png" alt="HELLAS Zone Net"><b>DigiConnect</b></a>
    <nav class="mnav" id="navm">
      <a href="./?lang=<?= $lang ?>"><?= T('Αρχική', 'Home', 'Hem') ?></a>
      <a href="./?lang=<?= $lang ?>#features"><?= T('Λειτουργίες', 'Features', 'Funktioner') ?></a>
      <a href="./?lang=<?= $lang ?>#shots"><?= T('Εικόνες', 'Screens', 'Bilder') ?></a>
      <a href="./?lang=<?= $lang ?>#download"><?= T('Λήψη', 'Download', 'Hämta') ?></a>
      <a href="./?lang=<?= $lang ?>#licence"><?= T('Demo & Donate', 'Demo & Donate', 'Demo & Donate') ?></a>
      <a class="on" href="?t=<?= $tok ?>&lang=<?= $lang ?>">💬 <?= T('Ζωντανή συνομιλία', 'Live chat', 'Livechatt') ?></a>
    </nav>
    <div class="hrow">
      <button class="hc" id="themebtn" type="button" title="<?= T('Φωτεινό / σκούρο θέμα', 'Light / dark theme', 'Ljust / mörkt tema') ?>" aria-label="<?= T('Θέμα','Theme','Tema') ?>"></button>
      <details class="langpick" id="langpick"><summary>🌐 <span><?= htmlspecialchars($LANGS[$lang] ?? 'English') ?></span> <span class="car">▾</span></summary>
        <div class="menu"><?php foreach ($LANGS as $code => $label) echo '<a href="?t=' . $tok . '&lang=' . $code . '" class="' . ($lang === $code ? 'on' : '') . '">' . htmlspecialchars($label) . ($lang === $code ? '<span class="ck">✓</span>' : '') . '</a>'; ?></div>
      </details>
      <button class="navtog" id="navtog" type="button" aria-label="Menu" aria-expanded="false">☰</button>
    </div>
  </div></header>

  <div class="wrap">
  <div class="card" id="card">
    <div class="ch"><div class="av">SA</div><div><b>SA7SVR · DigiConnect</b><small id="ost"></small></div></div>
  <?php if (!$tok): ?>
    <div class="fields" id="fields">
      <input id="f-name" placeholder="<?= T('Όνομα','Name','Namn') ?>" maxlength="80">
      <input id="f-call" placeholder="<?= T('Διακριτικό','Callsign','Signal') ?>" maxlength="16">
      <input id="f-email" placeholder="Email" type="email" maxlength="120">
    </div>
    <div class="intro" id="intro"><?= T('Γράψε το μήνυμά σου πιο κάτω (μπορείς να στείλεις και φωτογραφία). Θα πάρεις απάντηση εδώ, σε αυτή τη σελίδα — δεν χρειάζεται email. Κράτα τον σύνδεσμο για να δεις την απάντηση.', 'Write your message below (you can send a picture too). You will get a reply right here on this page — no e-mail needed. Keep the link to see the answer.', 'Skriv ditt meddelande nedan (du kan även skicka en bild). Du får svar här på sidan — ingen e-post behövs. Spara länken för att se svaret.') ?></div>
  <?php endif; ?>
    <div class="feedw" id="feedw"><div class="feed" id="feed"></div><div class="typ" id="typ"></div><button class="newb" id="newb" type="button"></button><div class="dropz" id="dropz"></div></div>
    <form class="comp" id="form" method="post" action="talk.php?lang=<?= $lang ?>" enctype="multipart/form-data">
      <div class="err" id="err"></div>
      <div class="att" id="att"><img id="attimg" alt=""><span id="attname"></span><button type="button" id="attx">✕</button></div>
      <div class="tool">
        <button type="button" id="tB"><b>B</b></button><button type="button" id="tI"><i>I</i></button><button type="button" id="tS"><s>S</s></button><button type="button" id="tC" style="font-family:monospace">&lt;/&gt;</button>
        <button type="button" id="tE">😀</button><button type="button" id="tP" title="<?= T('Φωτογραφία','Picture','Bild') ?>">📎</button>
        <span class="sp"></span><small><?= T('Enter = αποστολή · Shift+Enter = νέα γραμμή','Enter = send · Shift+Enter = new line','Enter = skicka · Shift+Enter = ny rad') ?></small>
      </div>
      <div class="row">
        <textarea name="body" id="body" rows="1" placeholder="<?= T('Μήνυμα…','Message…','Meddelande…') ?>"></textarea>
        <input type="hidden" name="name" id="h-name"><input type="hidden" name="call" id="h-call"><input type="hidden" name="email" id="h-email">
        <input type="file" name="image" id="file" accept="image/jpeg,image/png,image/gif,image/webp" style="display:none">
        <button class="sendb" id="sendb" type="submit"><span><?= T('Αποστολή','Send','Skicka') ?></span><svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></svg></button>
      </div>
    </form>
    <div class="note"><?= T('Ιδιωτική συνομιλία — μόνο εσύ κι εγώ τη βλέπουμε.','Private conversation — only you and I can see it.','Privat konversation — bara du och jag ser den.') ?></div>
  </div>
  </div>
  <div class="lb" id="lb"><img alt=""></div>

<script src="chat.js"></script>
<script>
(function(){
var C=window.DCChat,LB=<?= json_encode($LB, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP) ?>,TOK=<?= json_encode($tok) ?>,LANG=<?= json_encode($lang) ?>,last=<?= (int)$lastId ?>,INIT=<?= json_encode($msgs, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP) ?>;
var $=function(i){return document.getElementById(i);},feed=$('feed'),stick=true,lastDay='',lastWho='',seen={},file=null,sending=false,typSent=0,now=Math.floor(Date.now()/1000),firstSent=!!TOK;
function setErr(t){$('err').textContent=t||'';}
function tick(m){return m.who==='user'?'<span class="tk'+(m.rd?' rd':'')+'" title="'+C.esc(m.rd?LB.seen:LB.sent)+'">'+(m.rd?'✓✓':'✓')+'</span>':'';}
function build(m){
 var row=document.createElement('div');row.className='m '+(m.who==='owner'?'owner':'user')+(lastWho!==m.who?' first':'');row.dataset.id=m.id;row._m=m;lastWho=m.who;
 var sep=null,dk=C.dayKey(m.t);if(dk!==lastDay){lastDay=dk;sep=document.createElement('div');sep.className='day';sep.textContent=C.dayLabel(m.t,LB.today,LB.yest);}
 var b='';if(m.del)b='<div class="del">'+C.esc(LB.removed)+'</div>';else{if(m.img)b+='<img class="ph" src="talk.php?img='+m.id+'&t='+TOK+'" alt="" onload="this.style.width=Math.min(320,this.naturalWidth)+\'px\';var f=document.getElementById(\'feed\');if(f&&f.dataset.stick!==\'0\')f.scrollTop=f.scrollHeight">';if(m.body)b+='<div>'+C.fmt(m.body)+'</div>';}
 row.innerHTML='<div class="bub">'+b+'<div class="ft"><span>'+C.hm(m.t)+'</span>'+(m.del?'':tick(m))+'</div></div>';return [sep,row];}
function add(ms){ms.forEach(function(m){if(seen[m.id])return;seen[m.id]=1;if(m.id>last)last=m.id;var p=build(m);if(p[0])feed.appendChild(p[0]);feed.appendChild(p[1]);});
 if(stick)feed.scrollTop=feed.scrollHeight;else if(ms.length)$('newb').style.display='block';}
function owner(on){var s=$('ost');s.className=on?'on':'';s.textContent=on?'● '+LB.on:LB.off;}
owner(false);$('newb').textContent='↓ '+LB['new'];$('dropz').textContent=LB.drop;
add(INIT);feed.scrollTop=feed.scrollHeight;
feed.addEventListener('scroll',function(){stick=feed.scrollHeight-feed.scrollTop-feed.clientHeight<60;feed.dataset.stick=stick?'1':'0';if(stick)$('newb').style.display='none';});
$('newb').onclick=function(){feed.scrollTop=feed.scrollHeight;};
feed.addEventListener('click',function(e){var im=e.target.closest('img.ph');if(im){$('lb').querySelector('img').src=im.src;$('lb').classList.add('on');}});
$('lb').onclick=function(){this.classList.remove('on');};document.addEventListener('keydown',function(e){if(e.key==='Escape')$('lb').classList.remove('on');});
/* composer */
var ta=$('body');
function clearFile(){file=null;$('att').style.display='none';$('file').value='';}
function setFile(f){if(!f)return;if(!/^image\/(jpeg|png|gif|webp)$/.test(f.type)){setErr(LB.errtype);return;}if(f.size>5242880){setErr(LB.errbig);return;}
 setErr('');file=f;var r=new FileReader();r.onload=function(){$('attimg').src=r.result;};r.readAsDataURL(f);$('attname').textContent=f.name+' · '+Math.round(f.size/1024)+' KB';$('att').style.display='flex';ta.focus();}
ta.addEventListener('input',function(){this.style.height='44px';this.style.height=Math.min(150,this.scrollHeight)+'px';if(TOK&&this.value&&Date.now()-typSent>2500){typSent=Date.now();var fd=new FormData();fetch('talk.php?api=typing&t='+TOK,{method:'POST',body:fd}).catch(function(){});}});
ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('form').requestSubmit();}if((e.ctrlKey||e.metaKey)&&e.key==='b'){e.preventDefault();C.wrap(ta,'**','**');}if((e.ctrlKey||e.metaKey)&&e.key==='i'){e.preventDefault();C.wrap(ta,'*','*');}});
ta.addEventListener('paste',function(e){var it=(e.clipboardData||{}).items||[];for(var i=0;i<it.length;i++)if(it[i].kind==='file'&&/^image\//.test(it[i].type)){setFile(it[i].getAsFile());e.preventDefault();return;}});
$('tB').onclick=function(){C.wrap(ta,'**','**');};$('tI').onclick=function(){C.wrap(ta,'*','*');};$('tS').onclick=function(){C.wrap(ta,'~~','~~');};
$('tC').onclick=function(){var v=ta.value.slice(ta.selectionStart,ta.selectionEnd);if(v.indexOf('\n')>=0)C.wrap(ta,'```\n','\n```');else C.wrap(ta,'`','`');};
$('tE').onclick=function(e){e.stopPropagation();C.picker($('tE'),function(x){C.insert(ta,x);});};
$('tP').onclick=function(){$('file').click();};$('file').onchange=function(){setFile(this.files[0]);};$('attx').onclick=clearFile;
var fw=$('feedw');['dragenter','dragover'].forEach(function(ev){fw.addEventListener(ev,function(e){if(e.dataTransfer&&Array.prototype.indexOf.call(e.dataTransfer.types,'Files')>=0){e.preventDefault();fw.classList.add('drag');}});});
['dragleave','drop'].forEach(function(ev){fw.addEventListener(ev,function(e){e.preventDefault();fw.classList.remove('drag');if(ev==='drop'&&e.dataTransfer.files[0])setFile(e.dataTransfer.files[0]);});});
$('form').addEventListener('submit',function(e){
 e.preventDefault();if(sending)return;var body=ta.value.trim();if(!body&&!file)return;
 sending=true;$('sendb').disabled=true;setErr('');
 var fd=new FormData();fd.append('body',body);if(file)fd.append('image',file,file.name);
 var n=$('f-name'),c=$('f-call'),em=$('f-email');if(n)fd.append('name',n.value);if(c)fd.append('call',c.value);if(em)fd.append('email',em.value);
 fetch('talk.php?api=send&lang='+LANG+(TOK?'&t='+TOK:''),{method:'POST',body:fd,credentials:'same-origin'}).then(function(r){return r.json();}).then(function(j){
  sending=false;$('sendb').disabled=false;if(!j||!j.ok){setErr((j&&j.err)||LB.errsend);return;}
  if(!TOK){TOK=j.token;var f=$('fields'),i=$('intro');if(f)f.remove();if(i)i.remove();try{history.replaceState(null,'','talk.php?t='+TOK+'&lang='+LANG);}catch(x){}startPoll();}
  ta.value='';ta.style.height='';clearFile();stick=true;add([j.msg]);ta.focus();
 }).catch(function(){sending=false;$('sendb').disabled=false;setErr(LB.errsend);});});
/* live updates */
function poll(){if(!TOK)return;fetch('talk.php?api=poll&t='+TOK+'&after='+last,{credentials:'same-origin'}).then(function(r){return r.json();}).then(function(j){if(!j||!j.ok)return;
 var fresh=j.msgs.filter(function(m){return m.who==='owner'&&!seen[m.id];}).length;add(j.msgs);if(fresh&&(document.hidden||!document.hasFocus())){C.beep();document.title='💬 '+document.title.replace(/^💬 /,'');}
 j.upd.forEach(function(u){var el=document.querySelector('.m[data-id="'+u.id+'"]');if(!el)return;if(u.del&&!el._m.del){el._m=u;var p=build(u);el.innerHTML=p[1].innerHTML;}else if(u.rd&&!el._m.rd){el._m.rd=1;var k=el.querySelector('.tk');if(k){k.className='tk rd';k.textContent='✓✓';}}});
 $('typ').textContent=j.typ?LB.typing:'';owner(!!j.on);}).catch(function(){});}
var pt=null;function startPoll(){if(pt)return;poll();pt=setInterval(function(){if(!document.hidden||Math.random()<.2)poll();},3000);}
if(TOK)startPoll();
window.addEventListener('focus',function(){document.title=document.title.replace(/^💬 /,'');poll();});

 (function(){var root=document.documentElement,tb=document.getElementById('themebtn');
   function paint(){tb.textContent=root.getAttribute('data-theme')!=='light'?'🌙':'☀️';}paint();
   tb.addEventListener('click',function(){var nx=root.getAttribute('data-theme')==='light'?'dark':'light';root.setAttribute('data-theme',nx);try{localStorage.setItem('dc_theme',nx);}catch(e){}paint();});
   var nt=document.getElementById('navtog'),nav=document.getElementById('navm');
   if(nt&&nav){nt.addEventListener('click',function(){var o=nav.classList.toggle('open');nt.setAttribute('aria-expanded',o?'true':'false');});nav.addEventListener('click',function(e){if(e.target.closest('a'))nav.classList.remove('open');});}
   var lp=document.getElementById('langpick');document.addEventListener('click',function(e){if(lp&&lp.open&&!lp.contains(e.target))lp.open=false;});})();
})();
</script>
</body></html>
