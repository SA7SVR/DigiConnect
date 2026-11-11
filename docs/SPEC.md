# DigiConnect — προδιαγραφή λειτουργίας και UI

Πηγές: manual HORIZON DIGI CONNECT 1.0.11 (30 σελ.) και 7 screenshots. Η εφαρμογή μας υλοποιεί την **ίδια δομή και λειτουργικότητα** με **δικό μας κώδικα, δικό μας branding (HELLAS Zone)** και δικά μας κείμενα. Δεν αντιγράφεται κώδικας, λογότυπο ή κείμενα του πρωτότυπου.

Τεχνολογία: Qt6/QML + κινητήρας DroidStar (GPL-3, διατηρείται η αναφορά). Τρέχει Windows / macOS / Linux.

## 1. Στοιχεία UI (από screenshots)

### Πλαίσιο παραθύρου
| Περιοχή | Περιεχόμενο |
|---|---|
| Αριστερή μπάρα (rail) | Λογότυπο · My favorites · New QSO · QSO log · Analysis · Last heard · Audio mixer (ακουστικά) · Recordings · Updates · Help · Settings · avatar |
| Επάνω μπάρα | Λογότυπο · ώρα UTC + τοπική · callsign · κουμπί Settings |
| Tabs δικτύων | My favorites (πλήθος) · DMR · D-Star · EchoLink · C4FM (χρωματιστές κουκίδες: DMR βιολετί, D-Star κεχριμπάρι, EchoLink μπλε, C4FM ροζ) |
| Κάτω μπάρα (dock) | Επιλεγμένος σταθμός · κατάσταση TX · μετρητής MIC · Listen/Stop listening · Connect (TX)/Disconnect · Record audio · Hold PTT · Latch PTT · Stop · Limit · στόχος TX |
| Οριζόντιο mixer | Single/Multiple listening · Hide · sliders+mute ανά δίκτυο (DMR, D-Star, EchoLink, C4FM) · sliders ανά DMR receiver |
| Footer | Σημείωση για δημόσια δραστηριότητα · επιλογέας γλώσσας |

### Σελίδα καταλόγου δικτύου (DMR / D-Star / C4FM / EchoLink)
- Αριστερά: segmented «Κατάλογος | Αγαπημένα», Refresh, αναζήτηση, φίλτρο χώρας, Manual entry, μετρητής εγγραφών, λίστα (όνομα / TG ή reflector / δραστηριότητα / αστέρι), σελιδοποίηση (1–100 / N, Previous/Next).
- Κέντρο (επιλεγμένος σταθμός): κάρτα Transmit server (TX) με επιλογή server, Add favorite, ενότητα AUDIO (μικρόφωνο/ηχεία, Refresh devices, Test microphone, Test speakers, μπάρα στάθμης, RX volume + mute), κατάσταση ακρόασης, Connect (TX), Stop all, Hold PTT, Latch PTT, Limit 60/120/180 + αντίστροφη μέτρηση, στόχος TX, Record audio, New QSO, γραμμή RX/lost/TX.
- Δεξιά: Last station heard (callsign, DMR ID, όνομα, QTH, χώρα, locator, φωτογραφία, μικρός χάρτης, πηγή δεδομένων) + ιστορικό Last heard με «+» ανά γεγονός.
- EchoLink: πρώτα σύνδεση λογαριασμού (callsign, password, Remember, Sign in) · DTMF keypad.

### My favorites
Κάρτες (δίκτυο, όνομα, TG/reflector, δραστηριότητα, κατάσταση TX, επεξεργασία) · φίλτρα All / Active / Connections · Single/Multiple · Display (Full cards / Names only, μέγεθος κειμένου 11–20) · DTMF · υπόμνημα χρωμάτων · drag & drop, Alt+βέλος, F2 / δεξί κλικ μετονομασία (1–80 χαρ.).

### QSO log
Αναζήτηση, φίλτρα (δίκτυο, ημερομηνίες, χώρα), Refresh · Import ADIF (.adi .adif .adx) · Export ADIF/CSV (με ερωτηματικό, με βάση τα φίλτρα) · Trash/Delete/Undo · πίνακας Callsign / UTC / System / TG-reflector-room / Name / Country / Locator · σελιδοποίηση · Log analysis (ξεχωριστό παράθυρο, PDF) · πλαϊνή φόρμα New QSO (callsign, start/end UTC, system, destination, name, country, QTH, locator, band, MHz, equipment, RST, notes, audio, Fill from callbook, Contact history, Save / Next contact, Saved drafts / Resume).

### Settings (drawer)
My station (callsign, locator, module, equipment, radio message, γλώσσα EN/FR/IT/DE + ελληνικά, μέγεθος κειμένου, max PTT 60/120/180, προβολή αγαπημένων, profiles Save/Load) · Radio networks (DMR ID, ESSID, server, port, time slot, color code, password, EchoLink, D-Star/C4FM, alerts, watched callsigns, reconnect) · Audio (συσκευές, tests, ducking, φάκελος Recordings) · Callbooks (QRZ, QRZCQ, RadioID, Save and test, Forget credentials) · Backup (ZIP backup/restore, Export diagnostics).

## 2. Κανόνες λειτουργίας (manual → κώδικας)
Υλοποιούνται στο `core/session_rules.{h,cpp}` (χωρίς εξάρτηση από Qt, με tests στο `tests/`).

| Κανόνας | Κεφ. | Κατάσταση |
|---|---|---|
| Η επιλογή γραμμής καταλόγου δεν ξεκινά ακρόαση ούτε αποθηκεύει αγαπημένο | 3, 10 | ✅ κανόνας + test |
| Listen και Connect (TX) είναι ξεχωριστά. Το PTT δουλεύει μόνο για τον επιλεγμένο και συνδεδεμένο στόχο | 13 | ✅ |
| Single: ο νέος receiver αντικαθιστά τον προηγούμενο σε όλα τα δίκτυα | 11 | ✅ |
| Multiple: έως 4 DMR TG + 1 D-Star + 1 C4FM + 1 EchoLink. Ο πέμπτος DMR απορρίπτεται και οι τέσσερις μένουν | 11 | ✅ |
| Ίδιος στόχος ξανά: εστίαση, όχι διπλότυπο | 10, 11 | ✅ |
| Επιστροφή σε Single: μένει ο εστιασμένος receiver | 11 | ✅ |
| Αλλαγή mode αδύνατη κατά το TX | 11 | ✅ |
| Hold PTT / Latch PTT (δεύτερο πάτημα = Stop TX) | 13 | ✅ |
| Limit 60/120/180 (προεπιλογή 120), κόκκινο τα τελευταία 15 s, στο 0 τέλος TX, αλλαγή αδύνατη κατά το TX | 13 | ✅ |
| Στόχος σταθερός κατά το TX | 13 | ✅ |
| Αυτόματο σταμάτημα TX: απώλεια focus, Stop all, αποσύνδεση | 13 | ✅ (στο UI πρέπει να συνδεθεί το focus event) |
| Ducking ανά TX + σίγαση του ίδιου DMR RX κατά το TX | 11 | ✅ |
| Χρώματα καρτών: ροζ = ακρόαση, κεχριμπάρι (μόνο Multiple, μόνο πραγματική κίνηση, όχι muted/blocked) | 12 | ✅ |
| Έλεγχοι: TG 1–16777215 · DTMF 1–32 χαρ. 0-9 A-D * # · όνομα αγαπημένου 1–80 · μέγεθος κειμένου 11–20 | 4, 10, 14 | ✅ |
| Συντομεύσεις: Space PTT, F2 New QSO / μετονομασία, F4 mute όλων | 4, 27 | ⏳ UI |
| Προφίλ, backup ZIP, diagnostics JSON | 4, 23, 24 | ⏳ |
| QSO log: trash, διπλότυπα (~2 λεπτά χειροκίνητα, ακριβής ώρα στο import), drafts, ADIF/CSV | 17–20 | ⏳ |
| Ηχογράφηση (WebM/Opus στο πρωτότυπο) + «Listen before saving» | 22 | ⏳ (εμείς: Opus/WAV, θα αποφασιστεί) |

## 3. Τι δεν είναι ακόμα αληθινό (ειλικρινά)
1. **Ο κινητήρας DroidStar δουλεύει με ένα δίκτυο τη φορά.** Για Multiple listening χρειάζεται πολλαπλός receiver στον C++ κινητήρα (Φάση 2). Μέχρι τότε το UI μπορεί να δείξει Multiple, αλλά ο ήχος θα είναι ένας.
2. **DMR ακρόαση χωρίς ID/password** στο πρωτότυπο γίνεται από το δημόσιο BrandMeister Hoseline stream. Το αν και πώς προσεγγίζεται από native εφαρμογή δεν έχει επαληθευτεί από εμάς. Χρειάζεται έρευνα πριν υποσχεθούμε το χαρακτηριστικό. Εναλλακτικά: ακρόαση μέσω της σύνδεσης Homebrew.
3. **Φάση 0 (πραγματικός ήχος RX/TX σε μία σύνδεση)** περιμένει τα αποτελέσματα δοκιμής σου: ακούς εισερχόμενο ήχο; εμφανίζεσαι στο dashboard του reflector με Hold PTT;
4. Οι servers HELLAS Zone μπαίνουν πρώτοι σε κάθε mode μόλις επιβεβαιωθούν τα ακριβή endpoints ανά mode.

## 4. Σειρά υλοποίησης
0. Πραγματικός RX/TX σε μία σύνδεση (διάγνωση)
1. ✅ Εμφάνιση workspace (έγινε)
2. Σύνδεση `SessionRules` με το QML (Listen/Connect/PTT/Limit/Latch αληθινά)
3. HELLAS Zone servers πρώτοι
4. Πολλαπλός receiver στον κινητήρα + mixer ανά δίκτυο
5. QSO log, ADIF/CSV, drafts, callbooks, ηχογράφηση, backup, γλώσσες, light/dark
6. Τελικά builds Win/Mac/Linux + πλήρες source zip
