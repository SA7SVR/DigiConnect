"""User-interface language. English is the source text; other languages are tables of exact strings and
templates ('{}' = a number or name that is kept as is). Text that has no entry is shown in English, never guessed.

How it works: every label, button, placeholder, tooltip and window title goes through Qt's setText & co. These
setters are wrapped once (install()): the English source is remembered on the widget and the translation is shown.
Changing the language calls retranslate(), which re-applies the remembered sources, so the change is immediate."""
import re
from .qt import QtWidgets as W

LANGS = {"English": "en", "Ελληνικά": "el"}
_lang = "en"

EL: dict[str, str] = {
    # ---- navigation / chrome
    "My favorites": "Αγαπημένα", "New QSO": "Νέο QSO", "QSO log": "Ημερολόγιο QSO", "Log analysis": "Ανάλυση ημερολογίου",
    "Last heard": "Τελευταίοι ακουστοί", "Audio mixer": "Μίξερ ήχου", "Recordings": "Ηχογραφήσεις", "Updates": "Ενημερώσεις", "Help": "Βοήθεια",
    "Settings": "Ρυθμίσεις", "☀  Light": "☀  Φωτεινό", "☾  Dark": "☾  Σκούρο",
    "My favorites   {}": "Αγαπημένα   {}", "Radio workspace": "Χώρος εργασίας", "Radio workspace  {}": "Χώρος εργασίας  {}",
    "All your networks. One radio workspace.": "Όλα τα δίκτυά σου. Ένας χώρος εργασίας.",
    "Choose a station, then Listen. Connect transmission separately to participate.": "Διάλεξε σταθμό και πάτα Ακρόαση. Η εκπομπή συνδέεται ξεχωριστά για να συμμετέχεις.",
    "☆ Add favorite": "☆ Προσθήκη στα αγαπημένα", "☆  Add favorite": "☆  Προσθήκη στα αγαπημένα", "★  Remove favorite": "★  Αφαίρεση από τα αγαπημένα",
    "DigiConnect · HELLAS Zone · Public activity depends on information available from each network. Engine: {}": "DigiConnect · HELLAS Zone · Η δημόσια δραστηριότητα εξαρτάται από τις πληροφορίες κάθε δικτύου. Μηχανή: {}",
    "DigiConnect · HELLAS Zone · Public activity depends on information available from each network. Engine: {} · {} link": "DigiConnect · HELLAS Zone · Η δημόσια δραστηριότητα εξαρτάται από τις πληροφορίες κάθε δικτύου. Μηχανή: {} · {} σύνδεση",
    "DigiConnect · HELLAS Zone · Public activity depends on information available from each network. Engine: {} · {} links": "DigiConnect · HELLAS Zone · Η δημόσια δραστηριότητα εξαρτάται από τις πληροφορίες κάθε δικτύου. Μηχανή: {} · {} συνδέσεις",
    "DigiConnect · HELLAS Zone": "DigiConnect · HELLAS Zone",
    "Last heard appears in the right column of each network page when a station is received.": "Οι τελευταίοι ακουστοί εμφανίζονται στη δεξιά στήλη κάθε δικτύου όταν λαμβάνεται σταθμός.",
    "Recordings: none yet. Recording needs a running receiver (engine step).": "Ηχογραφήσεις: δεν υπάρχουν ακόμη. Η ηχογράφηση χρειάζεται ενεργό δέκτη.",
    "Updates: open the release page for DigiConnect to check for a newer build.": "Ενημερώσεις: άνοιξε τη σελίδα λήψεων του DigiConnect για νεότερη έκδοση.",
    "Help: see docs/SPEC.md (operating rules) in the source package.": "Βοήθεια: δες το docs/SPEC.md (κανόνες λειτουργίας) στο πακέτο πηγαίου κώδικα.",
    # ---- favorites
    "Search favorites…": "Αναζήτηση αγαπημένων…", "All": "Όλα", "Active": "Ενεργά", "Connections": "Συνδέσεις", "Refresh": "Ανανέωση",
    "Single listening": "Μονή ακρόαση", "Multiple listening": "Πολλαπλή ακρόαση", "Display": "Εμφάνιση", "DTMF": "DTMF",
    "No favorites yet. Use the star in a station directory or press Add favorite.": "Δεν υπάρχουν αγαπημένα ακόμη. Χρησιμοποίησε το αστέρι στον κατάλογο ή πάτα Προσθήκη.",
    "Select a station in a network tab and press ☆ Add favorite (or use Manual entry).": "Διάλεξε σταθμό σε καρτέλα δικτύου και πάτα ☆ Προσθήκη στα αγαπημένα (ή Χειροκίνητη εισαγωγή).",
    "Traffic detected": "Εντοπίστηκε κίνηση", "Selection": "Επιλογή", "Listening enabled": "Ακρόαση ενεργή", "Receiving audio": "Λήψη ήχου",
    "Updated {}": "Ενημερώθηκε {}", "•  Activity unavailable": "•  Μη διαθέσιμη δραστηριότητα", "Activity unavailable": "Μη διαθέσιμη δραστηριότητα",
    "Transmit disconnected": "Εκπομπή αποσυνδεδεμένη", "Transmit ready": "Εκπομπή έτοιμη", "Transmit ready · {}": "Εκπομπή έτοιμη · {}", "Transmitting": "Εκπομπή σε εξέλιξη",
    "Rename favorite": "Μετονομασία αγαπημένου", "Display name (1–80 characters):": "Εμφανιζόμενο όνομα (1–80 χαρακτήρες):",
    "A favorite name must be 1 to 80 characters.": "Το όνομα πρέπει να έχει 1 έως 80 χαρακτήρες.",
    "DTMF is sent to the connected EchoLink peer. Sign in and enable Connect (TX) on that peer first.": "Το DTMF στέλνεται στον συνδεδεμένο σταθμό EchoLink. Συνδέσου και ενεργοποίησε πρώτα τη Σύνδεση (TX).",
    "DTMF accepts 1 to 32 characters from 0-9, A-D, * and #.": "Το DTMF δέχεται 1 έως 32 χαρακτήρες από 0-9, A-D, * και #.",
    "Peer {}\nSequence (0-9 A-D * #, up to 32):": "Σταθμός {}\nΑκολουθία (0-9 A-D * #, έως 32):",
    # ---- workspace
    "Manual entry": "Χειροκίνητη εισαγωγή", "TG catalogue": "Κατάλογος TG", "Station directory": "Κατάλογος σταθμών",
    "Search TG, name or callsign…": "Αναζήτηση TG, ονόματος ή διακριτικού…", "Search name or callsign…": "Αναζήτηση ονόματος ή διακριτικού…",
    "Reflector module to link to (REF/XRF default C, DCS/XLX default A)": "Module αντανακλαστή προς σύνδεση (REF/XRF προεπιλογή C, DCS/XLX προεπιλογή A)",
    "Selected station": "Επιλεγμένος σταθμός", "Select a station": "Διάλεξε σταθμό", "Select an entry in the list on the left.": "Διάλεξε μια εγγραφή από τη λίστα αριστερά.",
    "Transmit server (TX)": "Διακομιστής εκπομπής (TX)", "No server configured": "Δεν έχει οριστεί διακομιστής", "Choose DMR server": "Επιλογή διακομιστή DMR",
    "Choose DMR master server": "Επιλογή master διακομιστή DMR", "Search master name, country or host…": "Αναζήτηση master (όνομα, χώρα ή host)…",
    "AUDIO": "ΗΧΟΣ", "Microphone": "Μικρόφωνο", "Speakers": "Ηχεία", "Refresh devices": "Ανανέωση συσκευών", "Test microphone": "Δοκιμή μικροφώνου", "Test speakers": "Δοκιμή ηχείων",
    "RX volume": "Ένταση λήψης", "Last station heard": "Τελευταίος σταθμός", "LAST HEARD": "ΤΕΛΕΥΤΑΙΟΙ ΑΚΟΥΣΤΟΙ", "Waiting for data": "Αναμονή δεδομένων",
    "🎧\nStation details will appear on reception.": "🎧\nΟι λεπτομέρειες του σταθμού θα εμφανιστούν κατά τη λήψη.",
    "Remember password": "Να θυμάται τον κωδικό", "Sign in to account": "Σύνδεση στον λογαριασμό", "Callsign": "Διακριτικό", "Password": "Κωδικός",
    "Sign in with your validated EchoLink account to load the directory and listen. Transmit remains disabled.": "Συνδέσου με τον επικυρωμένο λογαριασμό EchoLink για να φορτωθεί ο κατάλογος και να ακούσεις. Η εκπομπή παραμένει ανενεργή.",
    "EchoLink sign-in needs the EchoLink engine (not connected in this build)": "Η σύνδεση EchoLink χρειάζεται τη μηχανή EchoLink (δεν περιλαμβάνεται σε αυτή την έκδοση)",
    "Connects to the DMR master set in Settings › Radio networks (DMR ID required). Listen and Connect (TX) are separate.": "Συνδέεται στον master DMR των Ρυθμίσεων › Ραδιοδίκτυα (απαιτείται DMR ID). Η Ακρόαση και η Σύνδεση (TX) είναι ξεχωριστές.",
    "Listening requires a validated EchoLink account. Enable TX only to participate.": "Η ακρόαση απαιτεί επικυρωμένο λογαριασμό EchoLink. Ενεργοποίησε το TX μόνο για συμμετοχή.",
    "Listen links for reception only. Connect (TX) is separate and must be enabled to transmit.": "Η Ακρόαση συνδέεται μόνο για λήψη. Η Σύνδεση (TX) είναι ξεχωριστή και πρέπει να ενεργοποιηθεί για εκπομπή.",
    "The DMR master list is not downloaded yet — press Refresh (needs internet).": "Η λίστα master DMR δεν έχει κατέβει ακόμη — πάτα Ανανέωση (χρειάζεται internet).",
    "{} of {} masters": "{} από {} master", "{} masters": "{} master", "DMR master set to {} ({}:{})": "Ο master DMR ορίστηκε σε {} ({}:{})",
    "{} · {} entries": "{} · {} εγγραφές", "{} entries": "{} εγγραφές",
    "{} · worldwide list not downloaded yet — press Refresh (needs internet)": "{} · η παγκόσμια λίστα δεν έχει κατέβει ακόμη — πάτα Ανανέωση (χρειάζεται internet)",
    "EchoLink · 0 entries — the directory appears after signing in": "EchoLink · 0 εγγραφές — ο κατάλογος εμφανίζεται μετά τη σύνδεση",
    "TG number (1–16777215)": "Αριθμός TG (1–16777215)", "Identifier (e.g. REF001 C / 00006)": "Αναγνωριστικό (π.χ. REF001 C / 00006)",
    "A manual TG must be a positive integer no greater than 16777215.": "Το TG πρέπει να είναι θετικός ακέραιος έως 16777215.",
    "Local": "Τοπικό", "Cluster": "Cluster", "Regional": "Περιφερειακό", "World-wide": "Παγκόσμιο", "Europe": "Ευρώπη", "North America": "Βόρεια Αμερική",
    "Asia, Middle East": "Ασία, Μέση Ανατολή", "Australia, New Zealand": "Αυστραλία, Νέα Ζηλανδία", "Greece": "Ελλάδα", "Sweden": "Σουηδία",
    "TG {} · Not specified": "TG {} · Μη καθορισμένο", "Idle": "Αδρανές", "All countries": "Όλες οι χώρες", "Default module": "Προεπιλεγμένο module",
    "HELLAS Zone XLX · module B": "HELLAS Zone XLX · module B",
    "From the worldwide server list": "Από την παγκόσμια λίστα διακομιστών",
    # ---- updates / new modes
    "Update {} is ready. It starts the next time DigiConnect is opened (Updates › Restart now).": "Η ενημέρωση {} είναι έτοιμη. Ξεκινά την επόμενη φορά που θα ανοίξεις το DigiConnect (Ενημερώσεις › Επανεκκίνηση τώρα).",
    "Version {} needs a new full installer (engine change). Download it from the DigiConnect website.": "Η έκδοση {} χρειάζεται νέο πλήρες πρόγραμμα εγκατάστασης (αλλαγή μηχανής). Κατέβασέ το από την ιστοσελίδα του DigiConnect.",
    "Running version {} (program shell {})": "Τρέχουσα έκδοση {} (πυρήνας προγράμματος {})",
    "Updates are downloaded automatically, checked, and started the next time the program opens — no re-install. A bad update is switched off automatically.": "Οι ενημερώσεις κατεβαίνουν αυτόματα, ελέγχονται και ξεκινούν την επόμενη φορά που ανοίγει το πρόγραμμα — χωρίς νέα εγκατάσταση. Μια προβληματική ενημέρωση απενεργοποιείται αυτόματα.",
    "Check now": "Έλεγχος τώρα", "Restart now": "Επανεκκίνηση τώρα", "Checking for updates…": "Έλεγχος για ενημερώσεις…", "DigiConnect is up to date.": "Το DigiConnect είναι ενημερωμένο.",
    "Downloading version {}…": "Λήψη έκδοσης {}…", "Version {} is installed and starts at the next launch.": "Η έκδοση {} εγκαταστάθηκε και ξεκινά στην επόμενη εκκίνηση.",
    "Version {} needs a full installer from the DigiConnect website.": "Η έκδοση {} χρειάζεται πλήρες πρόγραμμα εγκατάστασης από την ιστοσελίδα του DigiConnect.", "Could not update: {}": "Η ενημέρωση απέτυχε: {}",
    "An NXDN ID is required for NXDN (Settings › Radio networks).": "Απαιτείται NXDN ID για το NXDN (Ρυθμίσεις › Ραδιοδίκτυα).",
    "A radio ID is required for P25: enter your DMR ID (Settings › Radio networks).": "Απαιτείται αναγνωριστικό για το P25: βάλε το DMR ID σου (Ρυθμίσεις › Ραδιοδίκτυα).",
    "DMR ID (also used for P25)": "DMR ID (χρησιμοποιείται και για P25)", "NXDN ID": "NXDN ID",
    "Identifier (e.g. REF001 C / 00006 / M17-DEU A)": "Αναγνωριστικό (π.χ. REF001 C / 00006 / M17-DEU A)",
    # ---- controls
    "Listen": "Ακρόαση", "Stop listening": "Διακοπή ακρόασης", "Stop": "Διακοπή", "Connect (TX)": "Σύνδεση (TX)", "Disconnect": "Αποσύνδεση", "Stop all": "Διακοπή όλων",
    "Connect to the selected server and listen (reception only)": "Σύνδεση στον επιλεγμένο διακομιστή και ακρόαση (μόνο λήψη)",
    "Connect your transmit link to the selected server so you can use PTT": "Σύνδεσε τον σύνδεσμο εκπομπής στον επιλεγμένο διακομιστή για να χρησιμοποιήσεις PTT",
    "Hold PTT": "Κράτημα PTT", "Latch PTT": "Μόνιμο PTT", "Stop TX": "Τέλος TX", "Limit": "Όριο", "Record audio": "Ηχογράφηση", "No station selected": "Δεν έχει επιλεγεί σταθμός",
    "RX — · lost — · TX —": "RX — · απώλειες — · TX —", "Hide  ✕": "Απόκρυψη  ✕", "Selected station": "Επιλεγμένος σταθμός", "MIC · —": "MIC · —", "Stop all": "Διακοπή όλων",
    "Up to 4 DMR TGs + 1 receiver on every other network. A click adds a receiver; on the same non-DMR network it replaces the previous one.": "Έως 4 DMR TG + 1 δέκτης σε κάθε άλλο δίκτυο. Ένα κλικ προσθέτει δέκτη· σε δίκτυο εκτός DMR αντικαθιστά τον προηγούμενο.",
    "Audio recording needs a running receiver (engine step)": "Η ηχογράφηση χρειάζεται ενεργό δέκτη", "Reception muted": "Η λήψη σίγασε",
    "Listening stopped": "Η ακρόαση σταμάτησε", "Listening · {} receiver": "Ακρόαση · {} δέκτης", "Listening · {} receivers": "Ακρόαση · {} δέκτες",
    "No TX destination": "Χωρίς προορισμό TX", "Connected": "Συνδέθηκε", "Connected · {}": "Συνδέθηκε · {}",
    "TX ended: time limit reached": "Τέλος TX: έφτασε το χρονικό όριο", "TX stopped: window lost focus": "Το TX σταμάτησε: το παράθυρο έχασε την εστίαση",
    "Listening mode cannot be changed during transmission.": "Ο τρόπος ακρόασης δεν αλλάζει κατά την εκπομπή.",
    "Maximum of 4 DMR receivers reached. Stop one before adding another.": "Έφτασες τους 4 δέκτες DMR. Σταμάτησε έναν πριν προσθέσεις άλλον.",
    # ---- connection / lists
    "Downloading the worldwide server lists…": "Λήψη των παγκόσμιων λιστών διακομιστών…", "Downloading the worldwide server lists, then connecting…": "Λήψη των παγκόσμιων λιστών και μετά σύνδεση…",
    "Choose a DMR master server in the list first (Master server), then press Listen.": "Διάλεξε πρώτα master διακομιστή DMR από τη λίστα και μετά πάτα Ακρόαση.",
    "{} is not in the worldwide server list. Press Refresh in the directory to download the newest lists.": "Το {} δεν υπάρχει στην παγκόσμια λίστα διακομιστών. Πάτα Ανανέωση στον κατάλογο για να κατέβουν οι νεότερες λίστες.",
    "Server lists updated: {}": "Οι λίστες διακομιστών ενημερώθηκαν: {}", "Server lists: {}": "Λίστες διακομιστών: {}", "Server lists: {} — using the saved copy.": "Λίστες διακομιστών: {} — χρήση του αποθηκευμένου αντιγράφου.",
    "No protocol engine connected (UI preview)": "Δεν υπάρχει συνδεδεμένη μηχανή πρωτοκόλλων (προεπισκόπηση)",
    "EchoLink is not available in this build yet.": "Το EchoLink δεν είναι διαθέσιμο ακόμη σε αυτή την έκδοση.",
    "Enter your callsign first (Settings › Station).": "Βάλε πρώτα το διακριτικό σου (Ρυθμίσεις › Ο σταθμός μου).",
    "A DMR ID is required for DMR (Settings › Radio networks).": "Απαιτείται DMR ID για το DMR (Ρυθμίσεις › Ραδιοδίκτυα).",
    "Protocol engine not found.": "Δεν βρέθηκε η μηχανή πρωτοκόλλων.", "The protocol engine stopped unexpectedly.": "Η μηχανή πρωτοκόλλων σταμάτησε απροσδόκητα.",
    "The protocol engine could not be started": "Δεν ήταν δυνατή η εκκίνηση της μηχανής πρωτοκόλλων", "Software vocoder": "Λογισμικό vocoder",
    "Audio devices unavailable ({})": "Οι συσκευές ήχου δεν είναι διαθέσιμες ({})",
    # ---- settings
    "My station": "Ο σταθμός μου", "Radio networks": "Ραδιοδίκτυα", "Audio": "Ήχος", "Callbooks": "Callbooks", "Backup": "Αντίγραφα",
    "Grid locator": "Locator (grid)", "Module": "Module", "Equipment": "Εξοπλισμός", "Radio message": "Μήνυμα ραδιοφώνου", "Language": "Γλώσσα", "Theme": "Θέμα",
    "Dark": "Σκούρο", "Light": "Φωτεινό", "Text size": "Μέγεθος κειμένου", "Maximum PTT duration (s)": "Μέγιστη διάρκεια PTT (δλ)", "Favorites display": "Εμφάνιση αγαπημένων",
    "Full cards": "Πλήρεις κάρτες", "Names only": "Μόνο ονόματα", "PROFILES": "ΠΡΟΦΙΛ", "Load": "Φόρτωση", "Profile name": "Όνομα προφίλ", "Save profile": "Αποθήκευση προφίλ",
    "DMR ID": "DMR ID", "ESSID": "ESSID", "Server": "Διακομιστής", "Port": "Θύρα", "Time slot": "Χρονοθυρίδα", "Color code": "Color code",
    "Passwords are kept for the current session only in this build (not written to disk).": "Οι κωδικοί κρατιούνται μόνο για την τρέχουσα συνεδρία (δεν γράφονται στον δίσκο).",
    "Lower other channels while transmitting": "Χαμήλωμα των άλλων καναλιών κατά την εκπομπή", "RECORDINGS": "ΗΧΟΓΡΑΦΗΣΕΙΣ", "Choose": "Επιλογή",
    "Preferred callbook": "Προτιμώμενο callbook", "Callbook lookups are not connected in this build.": "Η αναζήτηση callbook δεν είναι συνδεδεμένη σε αυτή την έκδοση.",
    "Back up application": "Αντίγραφο ασφαλείας εφαρμογής", "Restore a backup": "Επαναφορά αντιγράφου", "Export diagnostics": "Εξαγωγή διαγνωστικών",
    "Backup is a ZIP of settings, favorites and the journal. Restoring replaces them.": "Το αντίγραφο είναι ένα ZIP με ρυθμίσεις, αγαπημένα και ημερολόγιο. Η επαναφορά τα αντικαθιστά.",
    "Save": "Αποθήκευση", "Close": "Κλείσιμο", "Recordings folder": "Φάκελος ηχογραφήσεων", "Settings saved": "Οι ρυθμίσεις αποθηκεύτηκαν",
    "Profile '{}' saved (passwords are never copied into profiles)": "Το προφίλ '{}' αποθηκεύτηκε (οι κωδικοί δεν αντιγράφονται ποτέ στα προφίλ)",
    "Profile '{}' loaded. Active connections were stopped; check network, devices and credentials.": "Το προφίλ '{}' φορτώθηκε. Οι ενεργές συνδέσεις σταμάτησαν· έλεγξε δίκτυο, συσκευές και διαπιστευτήρια.",
    "Enter a profile name first.": "Βάλε πρώτα όνομα προφίλ.", "Text size must be between 11 and 20 pixels.": "Το μέγεθος κειμένου πρέπει να είναι 11 έως 20 pixel.",
    "Backup written": "Το αντίγραφο γράφτηκε", "Backup restored. Please restart DigiConnect.": "Έγινε επαναφορά. Κάνε επανεκκίνηση του DigiConnect.",
    "Restoring replaces settings, favorites and the journal. Continue?": "Η επαναφορά αντικαθιστά ρυθμίσεις, αγαπημένα και ημερολόγιο. Συνέχεια;", "Restore": "Επαναφορά",
    "Diagnostics exported (no passwords, no log contents)": "Τα διαγνωστικά εξήχθησαν (χωρίς κωδικούς, χωρίς περιεχόμενο ημερολογίου)",
    "{} available microphone": "{} διαθέσιμο μικρόφωνο", "{} available microphones": "{} διαθέσιμα μικρόφωνα", "(none found)": "(δεν βρέθηκε)",
    "Speaker test played. It confirms local output only, not that a radio stream arrives.": "Παίχτηκε ο ήχος δοκιμής. Επιβεβαιώνει μόνο την τοπική έξοδο, όχι ότι φτάνει ροή από ραδιοδίκτυο.",
    "Microphone test: peak level {}%  (does not key a transmitter)": "Δοκιμή μικροφώνου: μέγιστη στάθμη {}%  (δεν ενεργοποιεί πομπό)",
    "Speaker test failed: {}": "Η δοκιμή ηχείων απέτυχε: {}", "Microphone test failed: {}": "Η δοκιμή μικροφώνου απέτυχε: {}",
    # ---- QSO form / log
    "Source: Manual entry\nYour manual corrections are preserved.": "Πηγή: χειροκίνητη εισαγωγή\nΟι χειροκίνητες διορθώσεις σου διατηρούνται.", "Fill from callbook": "Συμπλήρωση από callbook",
    "Contact history": "Ιστορικό επαφών", "Saved drafts…": "Αποθηκευμένα πρόχειρα…", "Resume": "Συνέχεια", "Next contact": "Επόμενη επαφή", "QSO with {} saved": "Το QSO με {} αποθηκεύτηκε",
    "Review the details before saving.": "Έλεγξε τις λεπτομέρειες πριν την αποθήκευση.", "Start UTC": "Έναρξη UTC", "End UTC": "Λήξη UTC", "System": "Σύστημα",
    "TG / reflector / room": "TG / reflector / δωμάτιο", "Name": "Όνομα", "Country": "Χώρα", "QTH / city": "QTH / πόλη", "Band": "Μπάντα", "Frequency MHz": "Συχνότητα MHz",
    "RST sent": "RST που στάλθηκε", "RST received": "RST που λήφθηκε", "Personal notes": "Προσωπικές σημειώσεις", "No earlier contacts.": "Δεν υπάρχουν προηγούμενες επαφές.",
    "Enter a valid callsign before saving.": "Βάλε έγκυρο διακριτικό πριν την αποθήκευση.", "The locator is not a valid Maidenhead locator.": "Το locator δεν είναι έγκυρο Maidenhead.",
    "Callbook lookups are not connected in this build. Enter the details manually; nothing is invented.": "Η αναζήτηση callbook δεν είναι συνδεδεμένη. Βάλε τα στοιχεία χειροκίνητα· τίποτα δεν επινοείται.",
    "Start UTC must look like 2026-11-11T14:30:00.": "Η έναρξη UTC πρέπει να μοιάζει με 2026-11-11T14:30:00.", "End UTC must look like 2026-11-11T14:35:00.": "Η λήξη UTC πρέπει να μοιάζει με 2026-11-11T14:35:00.",
    "End UTC must not precede start UTC.": "Η λήξη UTC δεν μπορεί να είναι πριν την έναρξη.", "Frequency must be a positive value in MHz.": "Η συχνότητα πρέπει να είναι θετική τιμή σε MHz.",
    "Possible duplicate": "Πιθανό διπλότυπο", "{} on {} was already saved within two minutes of this time. Save both entries?": "Το {} στο {} είχε ήδη αποθηκευτεί μέσα σε δύο λεπτά από αυτή την ώρα. Να αποθηκευτούν και οι δύο;",
    "The current entry is not saved. Discard it and prepare the next contact?": "Η τρέχουσα εγγραφή δεν έχει αποθηκευτεί. Απόρριψη και προετοιμασία επόμενης επαφής;", "(no call)": "(χωρίς διακριτικό)",
    "Your contacts, notes and recordings.": "Οι επαφές, οι σημειώσεις και οι ηχογραφήσεις σου.", "Search the log…": "Αναζήτηση στο ημερολόγιο…",
    "from yyyy-mm-dd": "από εεεε-μμ-ηη", "to yyyy-mm-dd": "έως εεεε-μμ-ηη", "Import ADIF": "Εισαγωγή ADIF", "Export ADIF": "Εξαγωγή ADIF", "Export CSV": "Εξαγωγή CSV",
    "Trash": "Κάδος", "Delete": "Διαγραφή", "No QSOs logged": "Δεν υπάρχουν καταγεγραμμένα QSO", "0 QSO · 0–0": "0 QSO · 0–0", "Previous": "Προηγούμενο", "Next": "Επόμενο",
    "{} QSO · {}–{}": "{} QSO · {}–{}", "Export": "Εξαγωγή", "Exported {} contact(s)": "Εξήχθησαν {} επαφές", "Import finished: added {}, skipped {}": "Η εισαγωγή τελείωσε: προστέθηκαν {}, παραλείφθηκαν {}",
    "BY NETWORK": "ΑΝΑ ΔΙΚΤΥΟ", "BY DAY (UTC)": "ΑΝΑ ΗΜΕΡΑ (UTC)", "TOP COUNTRIES (20)": "ΚΟΡΥΦΑΙΕΣ ΧΩΡΕΣ (20)", "MOST WORKED STATIONS (12)": "ΠΙΟ ΣΥΧΝΟΙ ΣΤΑΘΜΟΙ (12)",
    "All networks": "Όλα τα δίκτυα", "{} contact(s) found. Duplicates (same callsign, network and exact UTC time) are skipped. Import?": "Βρέθηκαν {} επαφές. Τα διπλότυπα (ίδιο διακριτικό, δίκτυο και ακριβής ώρα UTC) παραλείπονται. Εισαγωγή;",
    "Contacts: {}   ·   Stations: {}   ·   Countries: {}": "Επαφές: {}   ·   Σταθμοί: {}   ·   Χώρες: {}",
}

TABLES = {"el": EL}
_patterns: list[tuple[re.Pattern, str]] = []


def _compile(lang: str):
    global _patterns
    _patterns = []
    for src, dst in TABLES.get(lang, {}).items():
        if "{}" in src:
            rx = "^" + "(.+?)".join(re.escape(p) for p in src.split("{}")) + "$"
            _patterns.append((re.compile(rx, re.S), dst))
    _patterns.sort(key=lambda p: -len(p[0].pattern))


def code() -> str: return _lang


def set_language(name: str) -> str:
    """name: 'English' | 'Ελληνικά' (or a code). Returns the active code."""
    global _lang
    c = LANGS.get(name, name if name in TABLES else "en"); _lang = c if (c == "en" or c in TABLES) else "en"; _compile(_lang); return _lang


def tr(s: str) -> str:
    if _lang == "en" or not s: return s
    t = TABLES[_lang]
    if s in t: return t[s]
    for rx, dst in _patterns:
        m = rx.match(s)
        if m:
            parts = [tr(g) if g in t else g for g in m.groups()]
            out = dst
            for p in parts: out = out.replace("{}", p, 1)
            return out
    return s


# ---- Qt hooks ---------------------------------------------------------------
_orig: dict[tuple, object] = {}


def _wrap(cls, name, kind):
    f = getattr(cls, name)
    _orig[(cls, name)] = f
    def w(self, text, *a, **k):
        try: self.__dict__.setdefault("_i18n", {})[kind] = text
        except Exception: pass
        return f(self, tr(text) if isinstance(text, str) else text, *a, **k)
    setattr(cls, name, w)


_done = False


def install():
    """Wraps the text setters once. After this every setText/setToolTip/... shows the translation of its English source."""
    global _done
    if _done: return
    _done = True
    for cls, name, kind in ((W.QLabel, "setText", "text"), (W.QAbstractButton, "setText", "text"), (W.QLineEdit, "setPlaceholderText", "ph"),
                            (W.QWidget, "setToolTip", "tip"), (W.QWidget, "setWindowTitle", "title"), (W.QGroupBox, "setTitle", "gtitle")):
        _wrap(cls, name, kind)


_SET = {"text": "setText", "ph": "setPlaceholderText", "tip": "setToolTip", "title": "setWindowTitle", "gtitle": "setTitle"}


def retranslate():
    for w in W.QApplication.allWidgets():
        d = w.__dict__.get("_i18n") if hasattr(w, "__dict__") else None
        if d:
            for kind, src in list(d.items()):
                for cls in type(w).__mro__:
                    f = _orig.get((cls, _SET[kind]))
                    if f is not None and isinstance(w, cls): f(w, tr(src)); break
        c0 = w.__dict__.get("_i18n_items") if hasattr(w, "__dict__") else None
        if c0:
            for i, src in c0.items():
                if i < w.count(): w.setItemText(i, tr(src))


def combo_item(combo: W.QComboBox, index: int, src: str):
    """Marks combo item `index` as translatable (its position, not its text, carries the meaning)."""
    combo.__dict__.setdefault("_i18n_items", {})[index] = src
    if index < combo.count(): combo.setItemText(index, tr(src))
