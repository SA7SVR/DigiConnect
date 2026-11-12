<?php
// DigiConnect — public website (presentation + download with registration). Self-contained.
require __DIR__ . '/lib.php';
$cfg = dc_cfg();
if (isset($_GET['lang'])) $_SESSION['dc_wlang'] = in_array($_GET['lang'], ['el','en','sv','it'], true) ? $_GET['lang'] : 'el';
$al = $_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? 'el';
$LANG = $_SESSION['dc_wlang'] ?? (preg_match('/^el/i',$al)?'el':(preg_match('/^sv/i',$al)?'sv':(preg_match('/^it/i',$al)?'it':'en')));
$LANGS = ['el'=>'Ελληνικά','en'=>'English','sv'=>'Svenska','it'=>'Italiano'];
function T($el,$en,$sv=null,$it=null){ global $LANG; return $LANG==='en'?$en:($LANG==='sv'?($sv??$en):($LANG==='it'?($it??$en):$el)); }
function h($s){ return dc_h($s); }

// ---- download registration ----
$dlmsg=''; $dlok=false;
if ($_SERVER['REQUEST_METHOD']==='POST' && ($_POST['do']??'')==='dl') {
  $name=trim($_POST['name']??''); $call=strtoupper(trim($_POST['call']??'')); $mail=trim($_POST['mail']??''); $os=$_POST['os']??'mac';
  if (($_POST['agree']??'')!=='1') {
    $dlmsg=T('Για τη λήψη πρέπει να συμφωνήσεις με την επεξεργασία των στοιχείων σου (πολιτική απορρήτου).','To download you must agree to the processing of your details (privacy policy).','För att ladda ner måste du godkänna behandlingen av dina uppgifter (integritetspolicy).','Per scaricare devi accettare il trattamento dei tuoi dati (informativa sulla privacy).');
  } elseif ($name==''||$call==''||!filter_var($mail,FILTER_VALIDATE_EMAIL)) {
    $dlmsg=T('Συμπλήρωσε ονοματεπώνυμο, διακριτικό και έγκυρο email — και τα τρία.','Fill in full name, callsign and a valid e-mail — all three.','Fyll i namn, anropssignal och en giltig e-post.','Inserisci nome, nominativo e un\'e-mail valida.');
  } else {
    $kc='c:'.$call; $km='m:'.strtolower($mail);
    $seen = dc_one('SELECT k FROM dc_dl_allow WHERE k=? OR k=?',[$kc,$km]);
    if ($seen) {
      $dlmsg=T('Έχει ήδη γίνει λήψη με αυτό το διακριτικό ή email. Για νέα λήψη επικοινώνησε με τον SA7SVR. (Οι αναβαθμίσεις έρχονται αυτόματα μέσα στην εφαρμογή.)',
               'A download already exists for this callsign or e-mail. For a new one contact SA7SVR. (Updates arrive automatically inside the app.)',
               'En nedladdning finns redan för denna signal eller e-post. Kontakta SA7SVR.',
               'Esiste già un download per questo nominativo o e-mail. Contatta SA7SVR.');
    } else {
      dc_q('INSERT INTO dc_webdl(t,call,email,name,os,ip,ua,lang) VALUES(?,?,?,?,?,?,?,?)',[time(),$call,$mail,$name,$os,dc_ip(),$_SERVER['HTTP_USER_AGENT']??'',$LANG]);
      dc_q('INSERT OR IGNORE INTO dc_dl_allow(k,n,t) VALUES(?,?,?)',[$kc,1,time()]);
      dc_q('INSERT OR IGNORE INTO dc_dl_allow(k,n,t) VALUES(?,?,?)',[$km,1,time()]);
      dc_event('webdl',"$call|$os"); $dlok=true;
      $dlmsg=T('Ευχαριστούμε! Η λήψη ξεκινά παρακάτω.','Thanks! Your download is below.','Tack! Din nedladdning finns nedan.','Grazie! Il download è qui sotto.');
    }
  }
}
// files that exist to offer
$files = [];
// first existing name wins: the new builds (GitHub: DMG / Setup.exe / tar.gz) before the old zip names
foreach (['mac-intel'=>['DigiConnect-macOS-Intel.dmg','DigiConnect-Mac-Intel.zip'],'mac-apple'=>['DigiConnect-macOS-AppleSilicon.dmg','DigiConnect-Mac-AppleSilicon.zip'],'win'=>['DigiConnect-Setup.exe','DigiConnect-Windows.zip'],'linux'=>['DigiConnect-Linux-x86_64.tar.gz','DigiConnect-Linux.tar.gz']] as $k=>$cands) foreach ($cands as $fn) if (is_file(__DIR__.'/pkg/'.$fn)) { $files[$k]=$fn; break; }
?><!doctype html>
<html lang="<?= $LANG ?>" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script>(function(){try{var t=localStorage.getItem('dc_theme')||'dark';document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();</script>
<title>DigiConnect — <?= T('ψηφιακή φωνή για ραδιοερασιτέχνες','digital voice for radio amateurs','digital röst','voce digitale') ?></title>
<link rel="icon" href="assets/hz-emblem.png">
<style>
:root{--bg:#070b12;--bg2:#0b111b;--card:#121c2b;--line:#223044;--line2:#2d3f58;--text:#eaf1f9;--text2:#c2d0e0;--muted:#8295ab;--acc:#17c0a8;--acc2:#3cc8ff;--head:rgba(8,12,19,.82);--btnh:rgba(23,192,168,.12)}
:root[data-theme="light"]{--bg:#eef2f7;--bg2:#e4eaf2;--card:#fff;--line:#d4ddea;--line2:#c0ccde;--text:#13202f;--text2:#30425a;--muted:#5d6f85;--acc:#0e9e8a;--acc2:#0a84c6;--head:rgba(255,255,255,.9);--btnh:rgba(14,158,138,.1)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1160px;margin:0 auto;padding:0 20px}
a{color:var(--acc2)}
header.top{position:sticky;top:0;z-index:30;background:transparent;padding:10px 0}
header.top .bar{display:flex;align-items:center;gap:10px 14px;min-height:58px;padding:6px 14px;background:var(--head);backdrop-filter:blur(10px);border:1px solid var(--line2);border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.2)}
.brand img{height:34px;display:block}
nav{margin-left:auto;display:flex;gap:6px;align-items:center}
nav a.mi{color:var(--text2);text-decoration:none;padding:6px 12px;border:1px solid var(--line2);border-radius:999px;font-size:13.5px;font-weight:600;white-space:nowrap}
nav a.mi:hover{color:var(--acc);border-color:var(--acc);background:var(--btnh)}
.hc{display:inline-flex;align-items:center;justify-content:center;height:36px;min-width:36px;padding:0 10px;border:1px solid var(--line2);border-radius:10px;background:transparent;color:var(--text);font:600 14px inherit;cursor:pointer}
.langpick{position:relative}.langpick>summary{list-style:none;display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 11px;border:1px solid var(--line2);border-radius:10px;cursor:pointer;font-weight:600}.langpick>summary::-webkit-details-marker{display:none}
.langpick .menu{position:absolute;right:0;top:44px;min-width:170px;background:var(--card);border:1px solid var(--line2);border-radius:12px;padding:6px;box-shadow:0 18px 44px rgba(0,0,0,.35);z-index:40}
.langpick .menu a{display:block;padding:9px 11px;border-radius:8px;text-decoration:none;color:var(--text)}.langpick .menu a:hover{background:var(--btnh)}.langpick .menu a.on{color:var(--acc);font-weight:700}
.navtog{display:none}
@media(max-width:860px){nav{position:absolute;left:0;right:0;top:100%;margin:6px 0 0;flex-direction:column;align-items:stretch;background:var(--card);border:1px solid var(--line2);border-radius:14px;padding:10px;transform:translateY(-8px);opacity:0;visibility:hidden;transition:.18s}nav.open{transform:none;opacity:1;visibility:visible}.navtog{display:inline-flex;align-items:center;justify-content:center;width:40px;height:36px;border:1px solid var(--line2);border-radius:10px;background:transparent;color:var(--text);font-size:18px;cursor:pointer}}
.hero{text-align:center;padding:50px 0 24px}
.hero img.logo{max-width:520px;width:88%;height:auto;filter:drop-shadow(0 20px 50px rgba(0,0,0,.5))}
.hero h1{font-size:30px;margin:18px 0 6px}.hero p{color:var(--text2);font-size:18px;max-width:680px;margin:0 auto}
.cta{display:flex;gap:12px;justify-content:center;margin:22px 0;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:8px;padding:12px 20px;border:1px solid var(--line2);border-radius:12px;background:var(--card);color:var(--text);text-decoration:none;font-weight:800}
.btn.pri{background:linear-gradient(135deg,var(--acc),var(--acc2));border:0;color:#04140f}
section{padding:34px 0}
h2{font-size:24px;margin:0 0 6px}.sub{color:var(--muted);margin:0 0 22px}
.feats{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.feat{border:1px solid var(--line2);border-radius:14px;background:var(--card);padding:16px}
.feat h3{margin:0 0 6px;font-size:16px}.feat p{margin:0;color:var(--text2);font-size:14px}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.shots img{width:100%;border:1px solid var(--line2);border-radius:14px;display:block}
@media(max-width:760px){.shots{grid-template-columns:1fr}}
.dl{border:1px solid var(--line2);border-radius:16px;background:var(--card);padding:22px;max-width:640px;margin:0 auto}
.dl .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.dl label{font-size:12px;color:var(--muted);display:block;margin-bottom:3px}
.dl input,.dl select{width:100%;height:40px;border:1px solid var(--line2);border-radius:10px;background:var(--bg2);color:var(--text);padding:0 11px;font:inherit}
.msg{padding:11px 14px;border-radius:10px;margin-bottom:14px;font-weight:600}
.msg.ok{background:var(--btnh);border:1px solid var(--acc);color:var(--acc)}
.msg.no{background:rgba(255,90,110,.14);border:1px solid #ff5a6e;color:#ff5a6e}
footer{border-top:1px solid var(--line);color:var(--muted);padding:26px 0;text-align:center;font-size:13px}
.note{color:var(--muted);font-size:12.5px;margin-top:12px}
</style></head><body id="top">
<header class="top"><div class="wrap"><div class="bar">
  <a class="brand" href="?lang=<?= $LANG ?>#top"><img src="assets/digiconnect-logo.png" alt="DigiConnect"></a>
  <nav id="navm">
    <a class="mi" href="#features"><?= T('Λειτουργίες','Features','Funktioner','Funzioni') ?></a>
    <a class="mi" href="#shots"><?= T('Εικόνες','Screens','Bilder','Immagini') ?></a>
    <a class="mi" href="#download"><?= T('Λήψη','Download','Hämta','Scarica') ?></a>
    <a class="mi" href="../hamdigi/?lang=<?= $LANG ?>">HAM Digi</a>
  </nav>
  <button class="hc" id="themebtn" type="button">🌙</button>
  <details class="langpick" id="langpick"><summary>🌐 <?= h($LANGS[$LANG]) ?> ▾</summary><div class="menu"><?php foreach($LANGS as $c=>$l) echo '<a href="?lang='.$c.'#top" class="'.($LANG===$c?'on':'').'">'.h($l).'</a>'; ?></div></details>
  <button class="navtog" id="navtog" type="button">☰</button>
</div></div></header>

<div class="wrap">
  <section class="hero">
    <img class="logo" src="assets/digiconnect-logo.png" alt="DigiConnect">
    <h1><?= T('Ψηφιακή φωνή, όλα τα δίκτυα, ένας χώρος εργασίας.','Digital voice, all networks, one workspace.','Digital röst, alla nätverk.','Voce digitale, tutte le reti.') ?></h1>
    <p><?= T('DMR, D-Star, C4FM/YSF και EchoLink μαζί — αγαπημένα, πολλαπλή ακρόαση, μείκτης ήχου, QSO log και PTT. Για Windows, Mac και Linux.','DMR, D-Star, C4FM/YSF and EchoLink together — favorites, multiple listening, audio mixer, QSO log and PTT. For Windows, Mac and Linux.','DMR, D-Star, C4FM/YSF och EchoLink tillsammans.','DMR, D-Star, C4FM/YSF ed EchoLink insieme.') ?></p>
    <div class="cta">
      <a class="btn pri" href="#download">⬇ <?= T('Δωρεάν λήψη','Free download','Ladda ner','Scarica') ?></a>
      <a class="btn" href="../hamdigi/?lang=<?= $LANG ?>">HAM Digi</a>
    </div>
    <div class="note"><?= T('Αυτόματες αναβαθμίσεις μέσα στην εφαρμογή.','Automatic updates inside the app.','Automatiska uppdateringar.','Aggiornamenti automatici.') ?></div>
  </section>

  <section id="features"><h2><?= T('Τι κάνει','What it does','Vad den gör','Cosa fa') ?></h2><p class="sub"><?= T('Όλα τα ψηφιακά σου δίκτυα σε μία εφαρμογή.','All your digital networks in one app.','Alla dina nätverk i en app.','Tutte le tue reti in un\'app.') ?></p>
    <div class="feats">
      <div class="feat"><h3><?= T('Όλα τα δίκτυα','All networks','Alla nätverk','Tutte le reti') ?></h3><p>DMR · D-Star · C4FM/YSF · EchoLink</p></div>
      <div class="feat"><h3><?= T('Αγαπημένα','Favorites','Favoriter','Preferiti') ?></h3><p><?= T('Κάρτες ανά δίκτυο, αστέρι, γρήγορη σύνδεση.','Cards per network, star, quick connect.','Kort per nätverk.','Schede per rete.') ?></p></div>
      <div class="feat"><h3><?= T('Πολλαπλή ακρόαση','Multiple listening','Flera lyssningar','Ascolto multiplo') ?></h3><p><?= T('Μείκτης ήχου ανά δίκτυο.','Audio mixer per network.','Ljudmixer per nätverk.','Mixer audio per rete.') ?></p></div>
      <div class="feat"><h3>PTT</h3><p><?= T('Listen / Connect / Hold / Latch, πλήκτρο Space.','Listen / Connect / Hold / Latch, Space key.','Lyssna / Anslut / Håll / Lås.','Ascolta / Connetti / Tieni / Blocca.') ?></p></div>
      <div class="feat"><h3>QSO log</h3><p><?= T('Επαφές, Export ADIF/CSV, ανάλυση.','Contacts, Export ADIF/CSV, analysis.','Kontakter, export ADIF/CSV.','Contatti, export ADIF/CSV.') ?></p></div>
      <div class="feat"><h3><?= T('Σκούρο & φωτεινό','Dark & light','Mörkt & ljust','Scuro e chiaro') ?></h3><p><?= T('Θέμα με διακόπτη, 4 γλώσσες.','Theme toggle, 4 languages.','Tema, 4 språk.','Tema, 4 lingue.') ?></p></div>
    </div>
  </section>

  <?php if (is_file(__DIR__.'/assets/shot-main.jpg')): ?>
  <section id="shots"><h2><?= T('Εικόνες','Screenshots','Bilder','Immagini') ?></h2><p class="sub"><?= T('Σκούρο και φωτεινό θέμα.','Dark and light theme.','Mörkt och ljust.','Tema scuro e chiaro.') ?></p>
    <div class="shots"><img src="assets/shot-main.jpg" alt="DigiConnect" loading="lazy"><img src="assets/shot-light.jpg" alt="DigiConnect light" loading="lazy"></div>
  </section>
  <?php endif; ?>

  <section id="download"><h2><?= T('Λήψη','Download','Hämta','Scarica') ?></h2><p class="sub"><?= T('Συμπλήρωσε τα στοιχεία σου — μία λήψη ανά διακριτικό.','Fill in your details — one download per callsign.','Fyll i dina uppgifter.','Inserisci i tuoi dati.') ?></p>
    <div class="dl">
      <?php if($dlmsg) echo '<div class="msg '.($dlok?'ok':'no').'">'.h($dlmsg).'</div>'; ?>
      <?php if($dlok && $files): ?>
        <p style="font-weight:700;margin-top:0"><?= T('Διάλεξε για το σύστημά σου:','Choose for your system:','Välj för ditt system:','Scegli per il tuo sistema:') ?></p>
        <?php foreach(['mac-intel'=>'macOS (Intel)','mac-apple'=>'macOS (Apple Silicon)','win'=>'Windows','linux'=>'Linux'] as $k=>$lbl) if(isset($files[$k])) echo '<a class="btn pri" style="margin:4px" href="pkg/'.h($files[$k]).'">⬇ '.$lbl.'</a>'; ?>
      <?php else: ?>
        <form method="post">
          <input type="hidden" name="do" value="dl">
          <div class="row">
            <div><label><?= T('Ονοματεπώνυμο','Full name','Namn','Nome') ?></label><input name="name" required></div>
            <div><label><?= T('Διακριτικό','Callsign','Anropssignal','Nominativo') ?></label><input name="call" required></div>
          </div>
          <div class="row" style="margin-top:12px">
            <div><label>Email</label><input name="mail" type="email" required></div>
            <div><label><?= T('Σύστημα','System','System','Sistema') ?></label><select name="os"><option value="mac">macOS</option><option value="win">Windows</option><option value="linux">Linux</option></select></div>
          </div>
          <label style="display:flex;gap:8px;align-items:flex-start;margin-top:14px;font-weight:400"><input type="checkbox" name="agree" value="1" required style="width:auto;height:auto;margin-top:4px"><span><?= T('Συμφωνώ να αποθηκευτούν τα στοιχεία μου όπως περιγράφει η','I agree that my details are stored as described in the','Jag godkänner att mina uppgifter lagras enligt','Accetto che i miei dati siano conservati come descritto nell\'') ?> <a href="privacy.php?lang=<?= $LANG ?>" target="_blank"><?= T('πολιτική απορρήτου','privacy policy','integritetspolicyn','informativa sulla privacy') ?></a>.</span></label>
          <button class="btn pri" style="margin-top:16px"><?= T('Λήψη','Download','Hämta','Scarica') ?></button>
          <div class="note"><?= T('Καταγράφονται ονοματεπώνυμο, διακριτικό, email και IP για την άδεια. Δεν κοινοποιούνται ποτέ. Το πρόγραμμα έχει δοκιμαστική περίοδο (demo) και επιλογή Donate.','Your full name, callsign, e-mail and IP are recorded for the licence. Never shared. The program has a trial (demo) period and a Donate option.','Namn, anropssignal, e-post och IP sparas för licensen och delas aldrig. Programmet har en demoperiod och ett Donate-alternativ.','Nome, nominativo, e-mail e IP sono registrati per la licenza e mai condivisi. Il programma ha un periodo demo e l\'opzione Donate.') ?></div>
        </form>
      <?php endif; ?>
    </div>
  </section>
</div>

<footer><div class="wrap">DigiConnect · © 2026 SA7SVR · HELLAS Zone Net · <a href="../hamdigi/?lang=<?= $LANG ?>">HAM Digi</a> · <a href="privacy.php?lang=<?= $LANG ?>"><?= T('Απόρρητο','Privacy','Integritet','Privacy') ?></a></div></footer>
<script>
(function(){var root=document.documentElement,tb=document.getElementById('themebtn');function paint(){tb.textContent=root.getAttribute('data-theme')==='light'?'☀️':'🌙';}paint();
tb.onclick=function(){var nx=root.getAttribute('data-theme')==='light'?'dark':'light';root.setAttribute('data-theme',nx);try{localStorage.setItem('dc_theme',nx);}catch(e){}paint();};
var nt=document.getElementById('navtog'),nav=document.getElementById('navm');if(nt&&nav){nt.onclick=function(){nav.classList.toggle('open');};}
var lp=document.getElementById('langpick');document.addEventListener('click',function(e){if(lp&&lp.open&&!lp.contains(e.target))lp.open=false;});})();
</script>
</body></html>
