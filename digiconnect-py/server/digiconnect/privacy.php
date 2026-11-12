<?php
// DigiConnect — privacy policy (GDPR). Self-contained page; texts in el / en / sv / it.
// Optional in config.php:  'contact_mail' => 'you@example.com'  (shown as the contact for privacy requests)
require __DIR__ . '/lib.php';
$cfg = dc_cfg();
if (isset($_GET['lang'])) $_SESSION['dc_wlang'] = in_array($_GET['lang'], ['el','en','sv','it'], true) ? $_GET['lang'] : 'el';
$al = $_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? 'el';
$LANG = $_SESSION['dc_wlang'] ?? (preg_match('/^el/i',$al)?'el':(preg_match('/^sv/i',$al)?'sv':(preg_match('/^it/i',$al)?'it':'en')));
function T($el,$en,$sv,$it){ global $LANG; return $LANG==='en'?$en:($LANG==='sv'?$sv:($LANG==='it'?$it:$el)); }
$mail = trim((string)($cfg['contact_mail'] ?? ''));
$contact = $mail !== '' ? '<a href="mailto:'.dc_h($mail).'">'.dc_h($mail).'</a>' : T('μέσω του hellaszone.com','through hellaszone.com','via hellaszone.com','tramite hellaszone.com');
?><!doctype html>
<html lang="<?= $LANG ?>"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= T('Πολιτική απορρήτου','Privacy policy','Integritetspolicy','Informativa sulla privacy') ?> · DigiConnect</title>
<style>
:root{--bg:#eef2f7;--card:#fff;--line:#d4ddea;--text:#13202f;--muted:#5d6f85;--acc:#0e9e8a;--link:#0a84c6}
@media (prefers-color-scheme:dark){:root{--bg:#070b12;--card:#121c2b;--line:#223044;--text:#eaf1f9;--muted:#8295ab;--acc:#17c0a8;--link:#3cc8ff}}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:28px 16px 60px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 26px}
h1{margin:0 0 4px;font-size:26px}h2{font-size:18px;margin:26px 0 6px;color:var(--acc)}p,li{margin:6px 0}a{color:var(--link)}
.muted{color:var(--muted);font-size:14px}.langs a{margin-right:12px}
table{border-collapse:collapse;width:100%;font-size:15px}td,th{border-top:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
</style></head><body><div class="wrap">
<p class="langs muted"><a href="./?lang=<?= $LANG ?>">← DigiConnect</a>
<?php foreach (['el'=>'Ελληνικά','en'=>'English','sv'=>'Svenska','it'=>'Italiano'] as $k=>$n) echo '<a href="?lang='.$k.'">'.($k===$LANG?'<b>'.$n.'</b>':$n).'</a>'; ?></p>
<div class="card">
<h1><?= T('Πολιτική απορρήτου','Privacy policy','Integritetspolicy','Informativa sulla privacy') ?></h1>
<p class="muted"><?= T('Ισχύει για το πρόγραμμα DigiConnect και τον ιστότοπό του. Τελευταία ενημέρωση: Νοέμβριος 2026.','Applies to the DigiConnect program and its website. Last updated: November 2026.','Gäller programmet DigiConnect och dess webbplats. Senast uppdaterad: november 2026.','Vale per il programma DigiConnect e il suo sito. Ultimo aggiornamento: novembre 2026.') ?></p>

<h2><?= T('1. Ποιος είναι ο υπεύθυνος επεξεργασίας','1. Who is responsible','1. Personuppgiftsansvarig','1. Titolare del trattamento') ?></h2>
<p><?= T('Ο Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net, ο οποίος διατηρεί τον ιστότοπο hellaszone.com.','Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net, who runs the website hellaszone.com.','Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net, som driver webbplatsen hellaszone.com.','Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net, che gestisce il sito hellaszone.com.') ?>
 <?= T('Επικοινωνία για θέματα απορρήτου: ','Contact for privacy matters: ','Kontakt i integritetsfrågor: ','Contatto per la privacy: ') ?><?= $contact ?>.</p>

<h2><?= T('2. Ποια δεδομένα συλλέγουμε','2. What we collect','2. Vilka uppgifter vi samlar in','2. Quali dati raccogliamo') ?></h2>
<table>
<tr><td><b><?= T('Όσα συμπληρώνεις','What you enter','Det du fyller i','Ciò che inserisci') ?></b></td><td><?= T('Ονοματεπώνυμο, διακριτικό (call sign), DMR ID, email.','Full name, callsign, DMR ID, e-mail address.','Namn, anropssignal, DMR-ID, e-postadress.','Nome, nominativo, DMR ID, indirizzo e-mail.') ?></td></tr>
<tr><td><b><?= T('Τεχνικά στοιχεία','Technical data','Tekniska uppgifter','Dati tecnici') ?></b></td><td><?= T('Αναγνωριστικό εγκατάστασης, έκδοση προγράμματος, λειτουργικό σύστημα, γλώσσα, διεύθυνση IP, ώρα πρώτης και τελευταίας επικοινωνίας.','Installation ID, program version, operating system, language, IP address, time of first and last contact.','Installations-ID, programversion, operativsystem, språk, IP-adress, tid för första och senaste kontakt.','ID di installazione, versione del programma, sistema operativo, lingua, indirizzo IP, data del primo e dell\'ultimo contatto.') ?></td></tr>
<tr><td><b><?= T('Λήψη από τον ιστότοπο','Website download','Nedladdning från webbplatsen','Download dal sito') ?></b></td><td><?= T('Ονοματεπώνυμο, call sign, email, IP και πρόγραμμα περιήγησης κατά τη λήψη.','Full name, callsign, e-mail, IP address and browser when you download.','Namn, anropssignal, e-post, IP-adress och webbläsare vid nedladdning.','Nome, nominativo, e-mail, IP e browser al momento del download.') ?></td></tr>
</table>
<p><?= T('Δεν συλλέγουμε ήχο, επικοινωνίες, κωδικούς πρόσβασης δικτύων (π.χ. DMR) ούτε περιεχόμενο των QSO σου. Αυτά μένουν στον υπολογιστή σου.','We do not collect audio, your communications, network passwords (such as DMR) or the content of your QSOs. Those stay on your computer.','Vi samlar inte in ljud, dina kommunikationer, nätverkslösenord (t.ex. DMR) eller innehållet i dina QSO. Det stannar på din dator.','Non raccogliamo audio, comunicazioni, password delle reti (ad es. DMR) né il contenuto dei tuoi QSO. Restano sul tuo computer.') ?></p>

<h2><?= T('3. Σκοπός και νομική βάση','3. Purpose and legal basis','3. Ändamål och rättslig grund','3. Finalità e base giuridica') ?></h2>
<ul>
<li><?= T('Να ξέρουμε ποιοι ραδιοερασιτέχνες χρησιμοποιούν το πρόγραμμα, να προσφέρουμε την περίοδο demo και να ενεργοποιούμε ή απενεργοποιούμε ένα αντίγραφο (άδεια χρήσης). Βάση: η συγκατάθεσή σου (άρθρο 6(1)(α) ΓΚΠΔ) και η εκτέλεση της χρήσης του προγράμματος (6(1)(β)).','To know which radio amateurs use the program, offer the demo period and switch a copy on or off (licensing). Basis: your consent (GDPR Art. 6(1)(a)) and providing the program to you (6(1)(b)).','Att veta vilka radioamatörer som använder programmet, erbjuda demoperioden och slå på eller av en kopia (licens). Grund: ditt samtycke (GDPR art. 6.1 a) och att tillhandahålla programmet (6.1 b).','Sapere quali radioamatori usano il programma, offrire il periodo demo e attivare o disattivare una copia (licenza). Base: il tuo consenso (GDPR art. 6(1)(a)) e la fornitura del programma (6(1)(b)).') ?></li>
<li><?= T('Ασφάλεια και αποτροπή κατάχρησης (IP, τεχνικά στοιχεία). Βάση: έννομο συμφέρον (6(1)(στ)).','Security and preventing abuse (IP, technical data). Basis: legitimate interest (6(1)(f)).','Säkerhet och skydd mot missbruk (IP, tekniska uppgifter). Grund: berättigat intresse (6.1 f).','Sicurezza e prevenzione degli abusi (IP, dati tecnici). Base: legittimo interesse (6(1)(f)).') ?></li>
</ul>

<h2><?= T('4. Με ποιον μοιραζόμαστε τα δεδομένα','4. Who receives the data','4. Vem som tar emot uppgifterna','4. Con chi condividiamo i dati') ?></h2>
<p><?= T('Με κανέναν. Δεν πωλούνται, δεν ενοικιάζονται και δεν χρησιμοποιούνται για διαφήμιση. Αποθηκεύονται στον διακομιστή του hellaszone.com και τα βλέπει μόνο ο διαχειριστής.','With nobody. They are not sold, rented or used for advertising. They are stored on the hellaszone.com server and only the administrator can see them.','Med ingen. De säljs, hyrs ut eller används inte för reklam. De lagras på servern hellaszone.com och endast administratören kan se dem.','Con nessuno. Non vengono venduti, ceduti né usati per pubblicità. Sono conservati sul server hellaszone.com e li vede solo l\'amministratore.') ?>
 <?= T('Η δωρεά (Donate) γίνεται στο PayPal, με δική τους πολιτική απορρήτου· εμείς δεν λαμβάνουμε στοιχεία κάρτας.','Donations go through PayPal under its own privacy policy; we do not receive your card details.','Donationer går via PayPal med deras egen integritetspolicy; vi får inga kortuppgifter.','Le donazioni passano da PayPal, con la sua informativa; noi non riceviamo i dati della carta.') ?></p>

<h2><?= T('5. Πόσο διατηρούνται','5. How long we keep it','5. Hur länge vi sparar','5. Per quanto tempo conserviamo') ?></h2>
<p><?= T('Όσο χρησιμοποιείς το πρόγραμμα και όσο χρειάζεται για την άδεια, ή μέχρι να ζητήσεις διαγραφή.','For as long as you use the program and as needed for the licence, or until you ask for erasure.','Så länge du använder programmet och så länge licensen kräver, eller tills du begär radering.','Finché usi il programma e quanto serve per la licenza, o finché non chiedi la cancellazione.') ?></p>

<h2><?= T('6. Τα δικαιώματά σου','6. Your rights','6. Dina rättigheter','6. I tuoi diritti') ?></h2>
<p><?= T('Έχεις δικαίωμα πρόσβασης, διόρθωσης, διαγραφής, περιορισμού, φορητότητας και εναντίωσης, καθώς και ανάκλησης της συγκατάθεσής σου οποιαδήποτε στιγμή (χωρίς να επηρεάζεται η προηγούμενη επεξεργασία). Στείλε αίτημα στη διεύθυνση επικοινωνίας παραπάνω. Αν θεωρείς ότι παραβιάζονται τα δικαιώματά σου, μπορείς να υποβάλεις καταγγελία στην εποπτική αρχή της χώρας σου (π.χ. Αρχή Προστασίας Δεδομένων στην Ελλάδα, IMY στη Σουηδία).','You have the right to access, rectify, erase, restrict, port and object, and to withdraw your consent at any time (without affecting earlier processing). Send a request to the contact above. If you think your rights are violated you may complain to the supervisory authority in your country (e.g. IMY in Sweden, the Hellenic Data Protection Authority in Greece).','Du har rätt till tillgång, rättelse, radering, begränsning, dataportabilitet och att invända, samt att när som helst återkalla ditt samtycke (utan att tidigare behandling påverkas). Skicka en begäran till kontaktadressen ovan. Anser du att dina rättigheter kränks kan du klaga hos tillsynsmyndigheten i ditt land (t.ex. IMY i Sverige).','Hai diritto di accesso, rettifica, cancellazione, limitazione, portabilità e opposizione, e di revocare il consenso in qualsiasi momento (senza effetto sul trattamento precedente). Invia una richiesta al contatto sopra. Se ritieni che i tuoi diritti siano violati puoi presentare reclamo all\'autorità di controllo del tuo paese (ad es. il Garante in Italia, IMY in Svezia).') ?></p>

<h2><?= T('7. Εγγραφή και υποχρεωτικά στοιχεία','7. Registration and required details','7. Registrering och obligatoriska uppgifter','7. Registrazione e dati obbligatori') ?></h2>
<p><?= T('Τα τέσσερα στοιχεία της εγγραφής είναι απαραίτητα για τη χρήση του προγράμματος, επειδή η άδεια συνδέεται με τον ραδιοερασιτέχνη. Χωρίς αυτά δεν μπορεί να ολοκληρωθεί η εγγραφή.','The four registration details are required to use the program, because the licence is tied to the radio amateur. Without them registration cannot be completed.','De fyra registreringsuppgifterna krävs för att använda programmet eftersom licensen är knuten till radioamatören. Utan dem kan registreringen inte slutföras.','I quattro dati di registrazione sono necessari per usare il programma, perché la licenza è legata al radioamatore. Senza di essi la registrazione non può essere completata.') ?></p>

<p class="muted" style="margin-top:26px">DigiConnect · © 2026 SA7SVR · HELLAS Zone Net</p>
</div></div></body></html>
