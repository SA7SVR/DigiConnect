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
dc_track_visit('home', $LANG);          // visit statistics (panel › Statistics); robots and the owner's own IP are left out

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
section{padding:46px 0}section+section{border-top:1px solid var(--line)}
section>h2{font-size:28px;line-height:1.2;margin:0 0 8px;text-align:center;letter-spacing:-.01em}
section>h2::after{content:"";display:block;width:44px;height:3px;margin:12px auto 0;border-radius:3px;background:linear-gradient(90deg,var(--acc),var(--acc2))}
.sub{color:var(--muted);margin:14px auto 30px;text-align:center;max-width:620px}
.feats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.feat{display:flex;flex-direction:column;border:1px solid var(--line2);border-radius:16px;background:var(--card);padding:20px 22px 22px;position:relative;overflow:hidden;transition:border-color .15s,transform .15s}
.feat::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(180deg,var(--acc),var(--acc2));opacity:.85}
.feat:hover{border-color:var(--acc);transform:translateY(-2px)}
.feat h3{margin:0 0 8px;font-size:16px;line-height:1.3}.feat p{margin:0;color:var(--text2);font-size:14px;line-height:1.6}
@media(max-width:980px){.feats{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.feats{grid-template-columns:1fr}section{padding:34px 0}section>h2{font-size:24px}}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.shots img{width:100%;border:1px solid var(--line2);border-radius:14px;display:block}
@media(max-width:760px){.shots{grid-template-columns:1fr}}
.split{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:20px;align-items:stretch}
.info{border:1px solid var(--line2);border-radius:18px;padding:26px 26px 24px;background:linear-gradient(160deg,color-mix(in srgb,var(--acc) 14%,var(--card)),var(--card) 70%);display:flex;flex-direction:column}
.info h3{margin:0 0 14px;font-size:18px}
.info ul{list-style:none;margin:0 0 18px;padding:0;display:flex;flex-direction:column;gap:12px}
.info li{display:flex;gap:11px;align-items:flex-start;color:var(--text2);font-size:14.5px;line-height:1.5}
.info li::before{content:"✓";flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:12px;font-weight:800;color:#04140f;background:linear-gradient(135deg,var(--acc),var(--acc2));margin-top:1px}
.info .btn{align-self:flex-start;margin-top:auto}
.dl,.ctf{border:1px solid var(--line2);border-radius:18px;background:var(--card);padding:26px}
.dl .row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.dl label,.ctf label{font-size:12.5px;font-weight:600;color:var(--muted);display:block;margin-bottom:5px;letter-spacing:.01em}
.dl input:not([type=checkbox]),.dl select,.ctf input,.ctf select,.ctf textarea{width:100%;min-width:0;border:1px solid var(--line2);border-radius:10px;background:var(--bg2);color:var(--text);padding:0 12px;font:inherit}
.dl input:not([type=checkbox]),.dl select,.ctf input,.ctf select{height:42px}
.ctf textarea{padding:10px 12px;resize:vertical;min-height:130px}
.dl input:focus,.dl select:focus,.ctf input:focus,.ctf select:focus,.ctf textarea:focus{outline:2px solid color-mix(in srgb,var(--acc) 55%,transparent);outline-offset:1px;border-color:var(--acc)}
.dl .btn.pri,.ctf .btn.pri{width:100%;justify-content:center;margin-top:6px}
.ctf{display:flex;flex-direction:column;gap:14px}.ctrow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.ctrow2{display:flex;align-items:center;gap:12px}.ctrow2 .btn{width:auto!important;padding:12px 28px}.ctrow2 .sub{margin:0;text-align:left;max-width:none;font-size:13.5px}
@media(max-width:900px){.split{grid-template-columns:1fr}}
@media(max-width:640px){.dl .row,.ctrow{grid-template-columns:1fr}}
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
    <a class="mi" href="#licence"><?= T('Demo & Donate','Demo & Donate','Demo & Donate','Demo & Donate') ?></a>
    <a class="mi" href="#download"><?= T('Λήψη','Download','Hämta','Scarica') ?></a>
    <a class="mi" href="#contact"><?= T('Επικοινωνία','Contact','Kontakt','Contatti') ?></a>
    <a class="mi cta" href="talk.php?lang=<?= $LANG ?>">💬 <?= T('Ζωντανή συνομιλία','Live chat','Livechatt','Chat dal vivo') ?></a>
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
    <p><?= T('DMR, D-STAR, C4FM/YSF, NXDN, P25, M17 και AllStarLink μαζί — αγαπημένα, πολλαπλή ακρόαση, μείκτης ήχου, QSO log και PTT. Για Windows, Mac και Linux.','DMR, D-STAR, C4FM/YSF, NXDN, P25, M17 and AllStarLink together — favorites, multiple listening, audio mixer, QSO log and PTT. For Windows, Mac and Linux.','DMR, D-STAR, C4FM/YSF, NXDN, P25, M17 och AllStarLink tillsammans — favoriter, flera lyssningar, ljudmixer, QSO-logg och PTT. För Windows, Mac och Linux.','DMR, D-STAR, C4FM/YSF, NXDN, P25, M17 e AllStarLink insieme — preferiti, ascolto multiplo, mixer audio, QSO log e PTT. Per Windows, Mac e Linux.') ?></p>
    <div class="cta">
      <a class="btn pri" href="#download">⬇ <?= T('Δωρεάν λήψη','Free download','Ladda ner','Scarica') ?></a>
      <a class="btn" href="../hamdigi/?lang=<?= $LANG ?>">HAM Digi</a>
    </div>
    <div class="note"><?= T('Αυτόματες αναβαθμίσεις μέσα στην εφαρμογή.','Automatic updates inside the app.','Automatiska uppdateringar.','Aggiornamenti automatici.') ?></div>
  </section>

  <section id="features"><h2><?= T('Τι κάνει','What it does','Vad den gör','Cosa fa') ?></h2><p class="sub"><?= T('Όλα τα ψηφιακά σου δίκτυα σε μία εφαρμογή.','All your digital networks in one app.','Alla dina nätverk i en app.','Tutte le tue reti in un\'app.') ?></p>
    <div class="feats">
      <div class="feat"><h3><?= T('Όλα τα δίκτυα','All networks','Alla nätverk','Tutte le reti') ?></h3><p>DMR · D-STAR · C4FM/YSF · NXDN · P25 · M17 · AllStarLink<br><small><?= T('EchoLink: προετοιμασμένο, η σύνδεση έρχεται.','EchoLink: prepared, the connection is coming.','EchoLink: förberat, anslutningen kommer.','EchoLink: predisposto, la connessione arriverà.') ?></small></p></div>
      <div class="feat"><h3><?= T('Αγαπημένα','Favorites','Favoriter','Preferiti') ?></h3><p><?= T('Κάρτες ανά δίκτυο, αστέρι, γρήγορη σύνδεση.','Cards per network, star, quick connect.','Kort per nätverk.','Schede per rete.') ?></p></div>
      <div class="feat"><h3><?= T('Πολλαπλή ακρόαση','Multiple listening','Flera lyssningar','Ascolto multiplo') ?></h3><p><?= T('Μείκτης ήχου ανά δίκτυο.','Audio mixer per network.','Ljudmixer per nätverk.','Mixer audio per rete.') ?></p></div>
      <div class="feat"><h3>PTT</h3><p><?= T('Listen / Connect / Hold / Latch, πλήκτρο Space.','Listen / Connect / Hold / Latch, Space key.','Lyssna / Anslut / Håll / Lås.','Ascolta / Connetti / Tieni / Blocca.') ?></p></div>
      <div class="feat"><h3>QSO log</h3><p><?= T('Επαφές, Export ADIF/CSV, ανάλυση.','Contacts, Export ADIF/CSV, analysis.','Kontakter, export ADIF/CSV.','Contatti, export ADIF/CSV.') ?></p></div>
      <div class="feat"><h3><?= T('Servers από δημόσιες λίστες','Servers from public lists','Servrar från publika listor','Server da liste pubbliche') ?></h3><p><?= T('Δεν είσαι δεμένος σε έναν διακομιστή· οι λίστες ανανεώνονται από τον server μας.','You are not tied to one server; the lists are refreshed by our server.','Du är inte bunden till en server; listorna uppdateras av vår server.','Non sei legato a un solo server; le liste sono aggiornate dal nostro server.') ?></p></div>
      <div class="feat"><h3><?= T('Διακοπή όλων','Stop all','Stoppa allt','Ferma tutto') ?></h3><p><?= T('Ένα κουμπί που σταματά κάθε ακρόαση και εκπομπή, πάντα ορατό.','One button that stops all listening and transmitting, always in reach.','En knapp som stoppar all lyssning och sändning, alltid synlig.','Un pulsante che ferma ogni ascolto e trasmissione, sempre visibile.') ?></p></div>
      <div class="feat"><h3><?= T('Αυτόματες αναβαθμίσεις','Automatic updates','Automatiska uppdateringar','Aggiornamenti automatici') ?></h3><p><?= T('Νέες εκδόσεις μέσα από την εφαρμογή, χωρίς νέα εγκατάσταση.','New versions from inside the app, no reinstall.','Nya versioner inifrån appen, utan ominstallation.','Nuove versioni dall\'interno dell\'app, senza reinstallare.') ?></p></div>
      <div class="feat"><h3><?= T('Σκούρο & φωτεινό','Dark & light','Mörkt & ljust','Scuro e chiaro') ?></h3><p><?= T('Θέμα με διακόπτη, 4 γλώσσες.','Theme toggle, 4 languages.','Tema, 4 språk.','Tema, 4 lingue.') ?></p></div>
    </div>
  </section>

  <?php if (is_file(__DIR__.'/assets/shot-main.jpg')): ?>
  <section id="shots"><h2><?= T('Εικόνες','Screenshots','Bilder','Immagini') ?></h2><p class="sub"><?= T('Σκούρο και φωτεινό θέμα.','Dark and light theme.','Mörkt och ljust.','Tema scuro e chiaro.') ?></p>
    <?php $sv1 = "?v=" . (int)@filemtime(__DIR__."/assets/shot-main.jpg"); $sv2 = "?v=" . (int)@filemtime(__DIR__."/assets/shot-light.jpg"); ?>
    <div class="shots"><a href="assets/shot-main.jpg<?= $sv1 ?>" target="_blank" rel="noopener"><img src="assets/shot-main.jpg<?= $sv1 ?>" alt="DigiConnect" loading="lazy"></a><a href="assets/shot-light.jpg<?= $sv2 ?>" target="_blank" rel="noopener"><img src="assets/shot-light.jpg<?= $sv2 ?>" alt="DigiConnect light" loading="lazy"></a></div>
    <p class="note" style="text-align:center"><?= T('Πάτησε μια εικόνα για να τη δεις μεγάλη.','Click a picture to see it full size.','Klicka på en bild för att se den i full storlek.','Clicca su un’immagine per vederla a grandezza intera.') ?></p>
  </section>
  <?php endif; ?>

  <section id="licence"><h2><?= T('Demo, άδεια και Donate','Demo, licence and Donate','Demo, licens och Donate','Demo, licenza e Donate') ?></h2><p class="sub"><?= T('Δοκίμασέ το πρώτα· αν σου αρέσει, στήριξε το project.','Try it first; if you like it, support the project.','Prova först; gillar du det, stöd projektet.','Provalo prima; se ti piace, sostieni il progetto.') ?></p>
    <div class="feats">
      <div class="feat"><h3><?= T('Δοκιμαστική περίοδος (demo)','Trial period (demo)','Demoperiod','Periodo di prova (demo)') ?></h3><p><?= T('Κάθε νέα εγκατάσταση ξεκινά με demo. Η εφαρμογή δείχνει πόσος χρόνος απομένει και, όταν λήξει, ζητά ενεργοποίηση.','Every new installation starts with a demo. The app shows how much time is left and asks for activation when it ends.','Varje ny installation börjar med en demo. Appen visar hur lång tid som återstår och ber om aktivering när den tar slut.','Ogni nuova installazione parte con una demo. L\'app mostra il tempo rimasto e chiede l\'attivazione alla scadenza.') ?></p></div>
      <div class="feat"><h3><?= T('Εγγραφή στην πρώτη εκκίνηση','Registration at first start','Registrering vid första start','Registrazione al primo avvio') ?></h3><p><?= T('Όνομα, διακριτικό, DMR ID και email — με ρητή συγκατάθεση και σύνδεσμο στην πολιτική απορρήτου. Η πρώτη εκκίνηση χρειάζεται σύνδεση στο internet.','Name, callsign, DMR ID and e-mail, with explicit consent and a link to the privacy policy. The first start needs an internet connection.','Namn, anropssignal, DMR ID och e-post, med uttryckligt samtycke och länk till integritetspolicyn. Första starten kräver internet.','Nome, nominativo, DMR ID ed e-mail, con consenso esplicito e link all\'informativa sulla privacy. Il primo avvio richiede internet.') ?></p></div>
      <div class="feat"><h3><?= T('Donate (PayPal)','Donate (PayPal)','Donate (PayPal)','Donate (PayPal)') ?></h3><p><?= T('Το κουμπί «♥ Δωρεά» είναι πάντα στην εφαρμογή. Μετά τη δωρεά η άδεια γίνεται μόνιμη· συνήθως αυτόματα, αλλιώς την ενεργοποιεί ο συγγραφέας.','The “♥ Donate” button is always in the app. After a donation the licence becomes permanent: usually automatically, otherwise the author activates it.','Knappen “♥ Donera” finns alltid i appen. Efter en donation blir licensen permanent: oftast automatiskt, annars aktiverar upphovsmannen den.','Il pulsante “♥ Dona” è sempre nell\'app. Dopo una donazione la licenza diventa permanente: di solito in automatico, altrimenti la attiva l\'autore.') ?></p></div>
      <div class="feat"><h3><?= T('Ευρώ και κορώνες','Euro and kronor','Euro och kronor','Euro e corone') ?></h3><p><?= T('Δωρεές μέσω PayPal σε EUR ή SEK· μπορείς να γράψεις το διακριτικό ή το email εγγραφής σου στη σημείωση ώστε να βρεθεί η εγκατάστασή σου.','PayPal donations in EUR or SEK; put your callsign or registration e-mail in the note so your installation can be found.','PayPal-donationer i EUR eller SEK; skriv din anropssignal eller registrerings-e-post i meddelandet så att din installation kan hittas.','Donazioni PayPal in EUR o SEK; scrivi nominativo o e-mail di registrazione nella nota per trovare la tua installazione.') ?></p></div>
      <div class="feat"><h3><?= T('Σύνδεση με τον server','Connection to the server','Anslutning till servern','Connessione al server') ?></h3><p><?= T('Η κατάσταση της άδειας ελέγχεται από τον server του HELLAS Zone. Ο συγγραφέας ορίζει αν το πρόγραμμα απαιτεί πάντα σύνδεση ή δουλεύει για λίγες μέρες χωρίς.','The licence state is checked by the HELLAS Zone server. The author decides whether the app always needs a connection or works for a few days without.','Licensen kontrolleras av HELLAS Zone-servern. Upphovsmannen bestämmer om appen alltid kräver anslutning eller fungerar några dagar utan.','Lo stato della licenza è verificato dal server HELLAS Zone. L\'autore decide se l\'app richiede sempre la connessione o funziona alcuni giorni senza.') ?></p></div>
      <div class="feat"><h3><?= T('Απόρρητο (GDPR)','Privacy (GDPR)','Integritet (GDPR)','Privacy (GDPR)') ?></h3><p><?= T('Αποθηκεύονται μόνο όσα δίνεις και τα τεχνικά στοιχεία της εγκατάστασης. Δεν κοινοποιούνται. Αίτημα διαγραφής: στον συγγραφέα.','Only what you enter and the technical facts of the installation are stored. Never shared. Deletion on request to the author.','Bara det du anger och installationens tekniska uppgifter lagras. De delas aldrig. Radering på begäran hos upphovsmannen.','Si conserva solo ciò che inserisci e i dati tecnici dell\'installazione. Mai condivisi. Cancellazione su richiesta all\'autore.') ?> <a href="privacy.php?lang=<?= $LANG ?>"><?= T('Πολιτική απορρήτου','Privacy policy','Integritetspolicy','Informativa privacy') ?></a></p></div>
    </div>
  </section>

  <section id="download"><h2><?= T('Λήψη','Download','Hämta','Scarica') ?></h2><p class="sub"><?= T('Συμπλήρωσε τα στοιχεία σου — μία λήψη ανά διακριτικό.','Fill in your details — one download per callsign.','Fyll i dina uppgifter.','Inserisci i tuoi dati.') ?></p>
    <div class="split">
    <aside class="info">
      <h3><?= T('Τι παίρνεις','What you get','Vad du får','Cosa ottieni') ?></h3>
      <ul>
        <li><?= T('Windows, macOS (Intel και Apple Silicon) και Linux','Windows, macOS (Intel and Apple Silicon) and Linux','Windows, macOS (Intel och Apple Silicon) och Linux','Windows, macOS (Intel e Apple Silicon) e Linux') ?></li>
        <li><?= T('Δοκιμαστική περίοδος (demo) από την πρώτη εκκίνηση','A trial period (demo) from the first start','Demoperiod från första start','Un periodo di prova (demo) dal primo avvio') ?></li>
        <li><?= T('Αυτόματες αναβαθμίσεις μέσα στην εφαρμογή','Automatic updates inside the app','Automatiska uppdateringar i appen','Aggiornamenti automatici nell’app') ?></li>
        <li><?= T('Μία λήψη ανά διακριτικό / email','One download per callsign / e-mail','En nedladdning per anropssignal / e-post','Un download per nominativo / e-mail') ?></li>
      </ul>
      <div class="note" style="margin-top:auto"><?= T('Τα στοιχεία χρησιμοποιούνται μόνο για την άδεια — δες την πολιτική απορρήτου.','Your details are used only for the licence — see the privacy policy.','Uppgifterna används bara för licensen — se integritetspolicyn.','I dati servono solo per la licenza — vedi la privacy policy.') ?></div>
    </aside>
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
    </div>
  </section>

<section id="contact"><h2><?= T('Επικοινωνία με τον διαχειριστή','Contact the administrator','Kontakta administratören','Contatta l’amministratore') ?></h2>
  <p class="sub"><?= T('Έχασες το installer, δεν ενεργοποιείται η άδεια ή βρήκες πρόβλημα; Στείλε μήνυμα απευθείας στον SA7SVR.','Lost the installer, a licence will not activate, or found a problem? Send a message straight to SA7SVR.','Förlorat installationsfilen, licensen aktiveras inte eller hittat ett fel? Skicka ett meddelande direkt till SA7SVR.','Hai perso l’installer, la licenza non si attiva o hai trovato un problema? Scrivi direttamente a SA7SVR.') ?></p>
  <div class="split">
    <aside class="info">
      <h3>💬 <?= T('Ζωντανή συνομιλία','Live chat','Livechatt','Chat dal vivo') ?></h3>
      <ul>
        <li><?= T('Η απάντηση εμφανίζεται εδώ, στην ίδια σελίδα — χωρίς email','The reply appears right here on the page — no e-mail','Svaret visas här på sidan — ingen e-post','La risposta appare qui, nella stessa pagina — senza e-mail') ?></li>
        <li><?= T('Ιδιωτική συνομιλία: τη βλέπεις μόνο εσύ και ο SA7SVR','Private conversation: only you and SA7SVR can see it','Privat konversation: bara du och SA7SVR ser den','Conversazione privata: solo tu e SA7SVR potete vederla') ?></li>
        <li><?= T('Μπορείς να στείλεις και φωτογραφία (π.χ. στιγμιότυπο οθόνης)','You can send a picture too (e.g. a screenshot)','Du kan skicka en bild (t.ex. en skärmdump)','Puoi inviare anche un’immagine (es. uno screenshot)') ?></li>
      </ul>
      <a class="btn pri" href="talk.php?lang=<?= $LANG ?>">💬 <?= T('Άνοιγμα συνομιλίας','Open the chat','Öppna chatten','Apri la chat') ?></a>
    </aside>
    <form id="ctf" class="ctf" onsubmit="return false">
      <div class="ctrow">
        <div><label for="ct_topic"><?= T('Θέμα','Topic','Ämne','Argomento') ?></label>
          <select id="ct_topic" name="topic"><option value=""><?= T('— Επίλεξε —','— Choose —','— Välj —','— Scegli —') ?></option>
            <option value="reinstall"><?= T('Επανεγκατάσταση / χάθηκε το installer','Reinstall / lost installer','Ominstallation / förlorad installerare','Reinstallazione / installer perso') ?></option>
            <option value="activation"><?= T('Ενεργοποίηση άδειας','Licence activation','Licensaktivering','Attivazione licenza') ?></option>
            <option value="bug"><?= T('Πρόβλημα / σφάλμα','Problem / bug','Problem / fel','Problema / errore') ?></option>
            <option value="other"><?= T('Άλλο','Other','Annat','Altro') ?></option></select></div>
        <div><label for="ct_call"><?= T('Διακριτικό','Callsign','Anropssignal','Nominativo') ?></label><input id="ct_call" name="call" style="text-transform:uppercase" maxlength="16"></div>
        <div><label for="ct_mail">Email</label><input id="ct_mail" name="email" type="email" maxlength="120" placeholder="you@example.com"></div>
      </div>
      <div><label for="ct_body"><?= T('Μήνυμα','Message','Meddelande','Messaggio') ?></label><textarea id="ct_body" name="body" rows="5" maxlength="4000" required></textarea></div>
      <div class="ctrow2"><button class="btn pri" id="ctsend" type="submit"><?= T('Αποστολή','Send','Skicka','Invia') ?></button><span id="ctmsg" class="sub"></span></div>
    </form>
  </div>
</section>
<script>
(function(){var f=document.getElementById('ctf');if(!f)return;var b=document.getElementById('ctsend'),m=document.getElementById('ctmsg');
f.addEventListener('submit',function(){var body=f.body.value.trim();if(!body){m.textContent='<?= T('Γράψε μήνυμα','Write a message','Skriv ett meddelande','Scrivi un messaggio') ?>';return;}
b.disabled=true;m.textContent='<?= T('Αποστολή…','Sending…','Skickar…','Invio…') ?>';
fetch('inbox.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({src:'web',lang:'<?= $LANG ?>',topic:f.topic.value,call:f.call.value.trim(),email:f.email.value.trim(),body:body,subject:(f.topic.options[f.topic.selectedIndex]||{}).text||'Message'})})
.then(function(r){return r.json();}).then(function(j){b.disabled=false;if(j&&j.ok){f.reset();m.textContent='<?= T('✓ Στάλθηκε — θα απαντήσουμε σύντομα.','✓ Sent — we will reply soon.','✓ Skickat — vi svarar snart.','✓ Inviato — risponderemo presto.') ?>';}else m.textContent=(j&&j.error==='too_many')?'<?= T('Πολλά μηνύματα — δοκίμασε αργότερα.','Too many messages — try later.','För många meddelanden — försök senare.','Troppi messaggi — riprova più tardi.') ?>':'<?= T('Δεν στάλθηκε.','Not sent.','Skickades inte.','Non inviato.') ?>';})
.catch(function(){b.disabled=false;m.textContent='<?= T('Σφάλμα σύνδεσης.','Connection error.','Anslutningsfel.','Errore di connessione.') ?>';});});})();
</script>

<footer><div class="wrap">DigiConnect · © 2026 SA7SVR · HELLAS Zone Net · <a href="../hamdigi/?lang=<?= $LANG ?>">HAM Digi</a> · <a href="privacy.php?lang=<?= $LANG ?>"><?= T('Απόρρητο','Privacy','Integritet','Privacy') ?></a></div></footer>
<script>
(function(){var root=document.documentElement,tb=document.getElementById('themebtn');function paint(){tb.textContent=root.getAttribute('data-theme')==='light'?'☀️':'🌙';}paint();
tb.onclick=function(){var nx=root.getAttribute('data-theme')==='light'?'dark':'light';root.setAttribute('data-theme',nx);try{localStorage.setItem('dc_theme',nx);}catch(e){}paint();};
var nt=document.getElementById('navtog'),nav=document.getElementById('navm');if(nt&&nav){nt.onclick=function(){nav.classList.toggle('open');};}
var lp=document.getElementById('langpick');document.addEventListener('click',function(e){if(lp&&lp.open&&!lp.contains(e.target))lp.open=false;});})();
</script>
</body></html>
