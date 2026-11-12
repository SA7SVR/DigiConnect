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
    "Downloading": "Λήψη", "Checking size and SHA-256": "Έλεγχος μεγέθους και SHA-256", "Unpacking and testing the code": "Αποσυσκευασία και δοκιμή του κώδικα", "Ready for the next start": "Έτοιμο για την επόμενη εκκίνηση",
    "New version {}": "Νέα έκδοση {}", "New version": "Νέα έκδοση", "What is new in this version": "Τι νέο υπάρχει σε αυτή την έκδοση",
    "Checking version {}…": "Έλεγχος έκδοσης {}…", "Installing version {}…": "Εγκατάσταση έκδοσης {}…",
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
    "Audio recording needs a running receiver (engine step)": "Η ηχογράφηση χρειάζεται ενεργό δέκτη", "Reception muted": "Η λήψη σίγασε", "Muted - click to turn the sound on": "Σε σίγαση - πάτα για να ανοίξει ο ήχος", "Sound on - click to mute": "Ο ήχος είναι ανοιχτός - πάτα για σίγαση",
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
    "BrandMeister needs your personal hotspot password: enter it in the Password field of the DMR server card (BrandMeister SelfCare › Hotspot Security), then connect again.": "Το BrandMeister θέλει τον προσωπικό σου κωδικό hotspot: γράψ' τον στο πεδίο Κωδικός της κάρτας του DMR server (BrandMeister SelfCare › Hotspot Security) και ξανασυνδέσου.",
    "Connection refused or no answer from the server": "Ο server αρνήθηκε τη σύνδεση ή δεν απάντησε",
    "The DMR master did not accept your DMR ID. Check the DMR ID in Settings › Radio networks (your own ID from RadioID.net, digits only) and the ESSID (leave it empty if unsure).": "Ο DMR master δεν δέχτηκε το DMR ID σου. Έλεγξε το DMR ID στις Ρυθμίσεις › Ραδιοδίκτυα (το δικό σου ID από το RadioID.net, μόνο ψηφία) και το ESSID (άφησέ το κενό αν δεν είσαι σίγουρος).",
    "The DMR master refused the password. On BrandMeister use your hotspot password (SelfCare › Hotspot Security), not your login password.": "Ο DMR master απέρριψε τον κωδικό. Στο BrandMeister βάλε τον κωδικό hotspot (SelfCare › Hotspot Security), όχι τον κωδικό εισόδου του λογαριασμού σου.",
    "The DMR master refused the connection settings after the password was accepted.": "Ο DMR master απέρριψε τις ρυθμίσεις σύνδεσης αφού είχε δεχτεί τον κωδικό.",
    "The DMR master's address could not be found (DNS). Check the internet connection and the master server in the DMR server card.": "Η διεύθυνση του DMR master δεν βρέθηκε (DNS). Έλεγξε τη σύνδεση στο internet και τον master server στην κάρτα DMR.",
    "All networks": "Όλα τα δίκτυα", "DMR network (BrandMeister, DMR+, FreeDMR …)": "Δίκτυο DMR (BrandMeister, DMR+, FreeDMR …)",
    "CONNECTED TO THIS NODE": "ΣΥΝΔΕΔΕΜΕΝΟΙ ΣΕ ΑΥΤΟΝ ΤΟΝ ΚΟΜΒΟ", "Connect to a node to see who is connected to it.": "Συνδέσου σε έναν κόμβο για να δεις ποιοι είναι συνδεδεμένοι σε αυτόν.",
    "Reading the connections of node {} …": "Ανάγνωση των συνδέσεων του κόμβου {} …", "Node {} · {} connected": "Κόμβος {} · {} συνδεδεμένοι", "● transmitting now": "● εκπέμπει τώρα",
    "transceive": "εκπομπή και λήψη", "receive only": "μόνο λήψη", "connecting": "γίνεται σύνδεση", "Not a valid node number.": "Μη έγκυρος αριθμός κόμβου.",
    "No answer from the server within 15 seconds - check the address and port, and that the network does not block UDP": "Ο server δεν απάντησε μέσα σε 15 δευτερόλεπτα - έλεγξε τη διεύθυνση και τη θύρα και ότι το δίκτυο δεν μπλοκάρει το UDP",
    "Welcome to DigiConnect": "Καλώς ήρθες στο DigiConnect", "Please enter your details once. All four are required.": "Συμπλήρωσε τα στοιχεία σου μία φορά. Και τα τέσσερα είναι υποχρεωτικά.",
    "Name": "Όνομα", "Callsign": "Διακριτικό (call sign)", "DMR ID": "DMR ID", "Email": "Email", "Quit": "Έξοδος", "Register": "Εγγραφή", "Registering…": "Γίνεται εγγραφή…",
    "I agree that these details are stored on the HELLAS Zone server for this purpose.": "Συμφωνώ τα στοιχεία αυτά να αποθηκεύονται στον server του HELLAS Zone για τον σκοπό αυτό.",
    "Controller: Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net. Data: name, callsign, DMR ID, email, plus installation ID, program version, operating system, language and IP address. Purpose: licensing (demo period, switching a copy on or off). Legal basis: your consent and providing the program. Not shared with anyone, not used for advertising; kept while you use the program or until you ask for erasure. You have the right to access, correct or erase your data and to withdraw your consent at any time, and to complain to your data protection authority.": "Υπεύθυνος επεξεργασίας: Panagiotis Tsekouras (SA7SVR), HELLAS Zone Net. Δεδομένα: ονοματεπώνυμο, διακριτικό, DMR ID, email, καθώς και αναγνωριστικό εγκατάστασης, έκδοση προγράμματος, λειτουργικό σύστημα, γλώσσα και διεύθυνση IP. Σκοπός: άδεια χρήσης (demo, ενεργοποίηση ή απενεργοποίηση αντιγράφου). Νομική βάση: η συγκατάθεσή σου και η παροχή του προγράμματος. Δεν κοινοποιούνται σε κανέναν και δεν χρησιμοποιούνται για διαφήμιση· διατηρούνται όσο χρησιμοποιείς το πρόγραμμα ή μέχρι να ζητήσεις διαγραφή. Έχεις δικαίωμα πρόσβασης, διόρθωσης ή διαγραφής των δεδομένων σου και ανάκλησης της συγκατάθεσης οποιαδήποτε στιγμή, καθώς και καταγγελίας στην αρχή προστασίας δεδομένων.",
    "Privacy policy": "Πολιτική απορρήτου",
    "Enter your name.": "Γράψε το όνομά σου.", "Enter a valid callsign (for example SA7SVR).": "Γράψε έγκυρο διακριτικό (π.χ. SA7SVR).", "Enter your DMR ID: 6 to 9 digits.": "Γράψε το DMR ID σου: 6 έως 9 ψηφία.",
    "Enter a valid email address.": "Γράψε έγκυρη διεύθυνση email.", "Please tick the box to agree.": "Τσέκαρε το κουτάκι για να συμφωνήσεις.",
    "The server could not be reached ({}). Check the internet connection and try again.": "Δεν έγινε σύνδεση με τον server ({}). Έλεγξε το internet και ξαναδοκίμασε.",
    "DigiConnect cannot continue": "Το DigiConnect δεν μπορεί να συνεχίσει", "DigiConnect is not active": "Το DigiConnect δεν είναι ενεργό", "Try again": "Ξαναδοκίμασε", "Checking…": "Έλεγχος…",
    "Donate": "Δωρεά", "Support the development of DigiConnect": "Στήριξε την ανάπτυξη του DigiConnect", "Demo": "Demo",
    "{} days left": "απομένουν {} ημέρες", "{} day left": "απομένει {} ημέρα",
    "This installation needs activation.": "Αυτή η εγκατάσταση χρειάζεται ενεργοποίηση.",
    "Your demo period has ended. Contact SA7SVR to activate.": "Η περίοδος demo έληξε. Επικοινώνησε με τον SA7SVR για ενεργοποίηση.",
    "This installation is disabled. Contact SA7SVR.": "Αυτή η εγκατάσταση έχει απενεργοποιηθεί. Επικοινώνησε με τον SA7SVR.",
    "This installation needs activation. Contact SA7SVR.": "Αυτή η εγκατάσταση χρειάζεται ενεργοποίηση. Επικοινώνησε με τον SA7SVR.",
    "The licence server cannot be reached. The first start needs a connection to register this program.": "Δεν γίνεται σύνδεση με τον server αδειών. Η πρώτη εκκίνηση χρειάζεται σύνδεση για να εγγραφεί το πρόγραμμα.",
    "The licence server cannot be reached. This program must be able to reach the HELLAS Zone server to run.": "Δεν γίνεται σύνδεση με τον server αδειών. Το πρόγραμμα πρέπει να φτάνει τον server του HELLAS Zone για να λειτουργήσει.",
    "✓ Password saved on this computer": "✓ Ο κωδικός αποθηκεύτηκε σε αυτόν τον υπολογιστή",
    "Password kept only until you close the program (\"Remember\" is off)": "Ο κωδικός θα μείνει μόνο μέχρι να κλείσεις το πρόγραμμα (το «Απομνημόνευση» είναι ανενεργό)",
    "No password entered yet": "Δεν έχει δοθεί ακόμη κωδικός",
    " — DMR: check the master address, your DMR ID and your personal hotspot password (BrandMeister SelfCare › Hotspot Security).": " — DMR: έλεγξε τη διεύθυνση του master, το DMR ID σου και τον προσωπικό κωδικό hotspot (BrandMeister SelfCare › Hotspot Security).",
    "A DMR ID is required for DMR (Settings › Radio networks).": "Απαιτείται DMR ID για το DMR (Ρυθμίσεις › Ραδιοδίκτυα).",
    "Protocol engine not found.": "Δεν βρέθηκε η μηχανή πρωτοκόλλων.", "The protocol engine stopped unexpectedly.": "Η μηχανή πρωτοκόλλων σταμάτησε απροσδόκητα.",
    "The protocol engine could not be started": "Δεν ήταν δυνατή η εκκίνηση της μηχανής πρωτοκόλλων", "Software vocoder": "Λογισμικό vocoder",
    "Audio devices unavailable ({})": "Οι συσκευές ήχου δεν είναι διαθέσιμες ({})",
    # ---- settings
    "My station": "Ο σταθμός μου", "Radio networks": "Ραδιοδίκτυα", "Audio": "Ήχος", "Callbooks": "Βιβλία κλήσεων", "Backup": "Αντίγραφα",
    "Grid locator": "Τοποθεσία (grid)", "Module": "Μονάδα (module)", "Equipment": "Εξοπλισμός", "Radio message": "Μήνυμα ραδιοφώνου", "Language": "Γλώσσα", "Theme": "Θέμα",
    "Dark": "Σκούρο", "Light": "Φωτεινό", "Text size": "Μέγεθος κειμένου", "Maximum PTT duration (s)": "Μέγιστη διάρκεια PTT (δλ)", "Favorites display": "Εμφάνιση αγαπημένων",
    "Full cards": "Πλήρεις κάρτες", "Names only": "Μόνο ονόματα", "PROFILES": "ΠΡΟΦΙΛ", "Load": "Φόρτωση", "Profile name": "Όνομα προφίλ", "Save profile": "Αποθήκευση προφίλ",
    "DMR ID": "DMR ID", "ESSID": "ESSID", "Server": "Διακομιστής", "Port": "Θύρα", "Time slot": "Χρονοθυρίδα", "Color code": "Color code",
    "Passwords are kept for the current session only in this build (not written to disk).": "Οι κωδικοί κρατιούνται μόνο για την τρέχουσα συνεδρία (δεν γράφονται στον δίσκο).",
    "Show my station as online on the HELLAS Zone server": "Εμφάνιση του σταθμού μου ως online στον server του HELLAS Zone", "Sends only: callsign, locator, program version, system and what you are listening to. No audio.": "Στέλνει μόνο: διακριτικό, locator, έκδοση προγράμματος, σύστημα και τι ακούς. Καθόλου ήχο.",
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
    # ---- audio block (v2.0.2)
    "System default": "Προεπιλογή συστήματος", "Microphone volume": "Ένταση μικροφώνου",
    "100% = the microphone level. Raise it above 100% if the other stations hear you too quietly.": "100% = η στάθμη του μικροφώνου. Ανέβασέ την πάνω από 100% αν οι άλλοι σταθμοί σε ακούν πολύ χαμηλά.",
    "Devices refreshed: {} microphone(s), {} speaker(s) found.": "Οι συσκευές ανανεώθηκαν: βρέθηκαν {} μικρόφωνα, {} ηχεία.",
    "Audio devices are used from the next connection on.": "Οι συσκευές ήχου χρησιμοποιούνται από την επόμενη σύνδεση.",
    "Testing the microphone… speak now.": "Δοκιμή μικροφώνου… μίλα τώρα.", "Playing the test tone…": "Παίζει ο ήχος δοκιμής…",
    "Speaker test played — you should have heard a tone.": "Η δοκιμή ηχείων έπαιξε — έπρεπε να ακούσεις έναν τόνο.",
    "Speaker test failed: the output could not be opened.": "Η δοκιμή ηχείων απέτυχε: η έξοδος δεν άνοιξε.",
    "Microphone test: peak level {}% — OK.": "Δοκιμή μικροφώνου: μέγιστη στάθμη {}% — εντάξει.",
    "Microphone test: peak level {}% — very low, raise the microphone volume.": "Δοκιμή μικροφώνου: μέγιστη στάθμη {}% — πολύ χαμηλή, ανέβασε την ένταση μικροφώνου.",
    "Microphone test: no signal (peak {}%) — speak while testing, choose another microphone, or check that it is not muted.": "Δοκιμή μικροφώνου: κανένα σήμα (μέγιστο {}%) — μίλα κατά τη δοκιμή, διάλεξε άλλο μικρόφωνο ή έλεγξε ότι δεν είναι σε σίγαση.",
    "Microphone test failed: no sound received — choose another microphone or allow microphone access in Windows Settings › Privacy › Microphone.": "Η δοκιμή μικροφώνου απέτυχε: δεν ήρθε ήχος — διάλεξε άλλο μικρόφωνο ή επίτρεψε την πρόσβαση στο μικρόφωνο στις Ρυθμίσεις των Windows › Απόρρητο › Μικρόφωνο.",
    # ---- server card (v2.0.2)
    "DMR master server (host)": "Διακομιστής DMR master (host)", "DMR master port": "Θύρα DMR master",
    "These fields are for the DMR master only. Every other station shows its own server and port on its page (Selected station › Server).": "Αυτά τα πεδία αφορούν μόνο τον DMR master. Κάθε άλλος σταθμός δείχνει τον δικό του διακομιστή και θύρα στη σελίδα του (Επιλεγμένος σταθμός › Διακομιστής).",
    "Server used for this station": "Διακομιστής που χρησιμοποιείται για αυτόν τον σταθμό", "Server (host / IP)": "Διακομιστής (host / IP)",
    "host name or IP address": "όνομα host ή διεύθυνση IP", "port": "θύρα", "Use this address": "Χρήση αυτής της διεύθυνσης", "Back to the list value": "Επιστροφή στην τιμή της λίστας",
    "Select a station to see its server address.": "Διάλεξε σταθμό για να δεις τη διεύθυνση του διακομιστή του.",
    "Source: your own address (used instead of the list).": "Πηγή: η δική σου διεύθυνση (χρησιμοποιείται αντί της λίστας).", "Source: built into DigiConnect.": "Πηγή: ενσωματωμένη στο DigiConnect.",
    "Source: the DMR master you chose. Press «Choose DMR server» to change it.": "Πηγή: ο DMR master που διάλεξες. Πάτα «Επιλογή διακομιστή DMR» για αλλαγή.",
    "Source: the downloaded worldwide server list.": "Πηγή: η κατεβασμένη παγκόσμια λίστα διακομιστών.",
    "Not in the downloaded lists yet — press Refresh, or type the address here.": "Δεν υπάρχει ακόμη στις κατεβασμένες λίστες — πάτα Ανανέωση ή γράψε εδώ τη διεύθυνση.",
    "Enter a host name or IP address, and a port between 1 and 65535.": "Βάλε όνομα host ή διεύθυνση IP και θύρα από 1 έως 65535.",
    "Server address saved: {}. It is used the next time you connect.": "Η διεύθυνση διακομιστή αποθηκεύτηκε: {}. Χρησιμοποιείται στην επόμενη σύνδεση.",
    "The list value is used again.": "Χρησιμοποιείται ξανά η τιμή της λίστας.",
    "Typed talkgroup number": "Αριθμός ομάδας που πληκτρολογήθηκε",
    # ---- v2.0.2: directory rows, Last heard page, remaining English
    "Local": "Τοπικό", "Cluster": "Cluster", "Regional": "Περιφερειακό", "World-wide": "Παγκόσμιο", "Europe": "Ευρώπη", "North America": "Βόρεια Αμερική",
    "Asia, Middle East": "Ασία, Μέση Ανατολή", "Australia, New Zealand": "Αυστραλία, Νέα Ζηλανδία", "Greece": "Ελλάδα", "Sweden": "Σουηδία",
    "From the worldwide server list": "Από την παγκόσμια λίστα διακομιστών", "{} · module {} · {}": "{} · μονάδα {} · {}", "TG {} · typed number": "TG {} · αριθμός που πληκτρολογήθηκε",
    "Color code": "Κωδικός χρώματος", "hostname": "όνομα host", "Last heard": "Τελευταίοι ακουστοί",
    "Time (UTC)": "Ώρα (UTC)", "Callsign": "Διακριτικό", "To": "Προς", "Network": "Δίκτυο", "Gateway": "Gateway", "Clear list": "Καθαρισμός λίστας",
    "Every station received on the links you are listening to appears here as it is heard.": "Κάθε σταθμός που λαμβάνεται στις συνδέσεις που ακούς εμφανίζεται εδώ μόλις ακουστεί.",
    "Diagnostics exported (no passwords)": "Τα διαγνωστικά εξήχθησαν (χωρίς κωδικούς)", "MIC · —": "ΜΙΚΡ · —",
    "(you)": "(εσύ)", "you": "εσύ", "Duration": "Διάρκεια",
    "SERVER LISTS": "ΛΙΣΤΕΣ ΔΙΑΚΟΜΙΣΤΩΝ", "Download the server lists now": "Κατέβασμα των λιστών διακομιστών τώρα",
    "YSF reflectors": "Reflectors YSF", "D-Star REF (DPlus)": "D-Star REF (DPlus)", "DMR masters": "DMR masters", "DMR talkgroups": "Ομάδες DMR (TG)",
    "NXDN talkgroups": "Ομάδες NXDN", "P25 talkgroups": "Ομάδες P25", "M17 reflectors": "Reflectors M17",
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
    # ---- AllStarLink
    "AllStar": "AllStar", "Search node number, callsign or description…": "Αναζήτηση αριθμού κόμβου, διακριτικού ή περιγραφής…",
    "Sign in with your own AllStarLink portal account, then pick a node. Experimental: only nodes that accept AllStarLink app connections can be reached.": "Συνδέσου με τον δικό σου λογαριασμό της πύλης AllStarLink και διάλεξε κόμβο. Πειραματικό: προσεγγίζονται μόνο κόμβοι που δέχονται συνδέσεις εφαρμογών AllStarLink.",
    "AllStarLink username (callsign)": "Όνομα χρήστη AllStarLink (διακριτικό)", "AllStarLink password": "Κωδικός AllStarLink",
    "Remember on this computer (enter it only once)": "Απομνημόνευση σε αυτόν τον υπολογιστή (τα βάζεις μία φορά)",
    "When ticked, the password is kept in this program's settings file on this computer (not encrypted). Untick it to keep it only in memory.": "Όταν είναι τσεκαρισμένο, ο κωδικός μένει στο αρχείο ρυθμίσεων του προγράμματος σε αυτόν τον υπολογιστή (όχι κρυπτογραφημένος). Ξετσέκαρέ το για να μένει μόνο στη μνήμη.",
    "Connects to the chosen AllStarLink node with your portal account. Listen and Connect (TX) are separate; the node must allow app connections.": "Συνδέεται στον κόμβο AllStarLink που διάλεξες με τον λογαριασμό σου. Η Ακρόαση και η Σύνδεση (TX) είναι ξεχωριστές· ο κόμβος πρέπει να επιτρέπει συνδέσεις εφαρμογών.",
    "AllStarLink node number (digits)": "Αριθμός κόμβου AllStarLink (ψηφία)", "An AllStarLink node number has 3 to 8 digits.": "Ο αριθμός κόμβου AllStarLink έχει 3 έως 8 ψηφία.",
    "AllStarLink · {} nodes": "AllStarLink · {} κόμβοι", "AllStarLink · node list not downloaded yet — press Refresh (needs internet), or type a node number": "AllStarLink · η λίστα κόμβων δεν έχει κατέβει ακόμη — πάτα Ανανέωση (θέλει internet) ή γράψε έναν αριθμό κόμβου",
    "Downloading the AllStarLink node list…": "Λήψη της λίστας κόμβων AllStarLink…", "AllStarLink node list updated: {} nodes": "Η λίστα κόμβων AllStarLink ενημερώθηκε: {} κόμβοι",
    "The AllStarLink node list is up to date (it is renewed at most every 15 minutes).": "Η λίστα κόμβων AllStarLink είναι ενημερωμένη (ανανεώνεται το πολύ κάθε 15 λεπτά).",
    "Source: AllStarLink node address (looked up when you connect).": "Πηγή: διεύθυνση του κόμβου από το AllStarLink (αναζητείται κατά τη σύνδεση).",
    "DTMF is sent to the connected AllStarLink node. Select the node and connect first.": "Το DTMF στέλνεται στον συνδεδεμένο κόμβο AllStarLink. Διάλεξε τον κόμβο και συνδέσου πρώτα.",
    "DTMF can only be sent while the connection to that node is up.": "Το DTMF στέλνεται μόνο όσο η σύνδεση με τον κόμβο είναι ενεργή.", "DTMF is available for AllStarLink nodes.": "Το DTMF είναι διαθέσιμο για κόμβους AllStarLink.",
    "DTMF sent: {}": "Στάλθηκε DTMF: {}", "Node {}\nSequence (0-9 A-D * #, up to 32):": "Κόμβος {}\nΑκολουθία (0-9 A-D * #, έως 32):",
    "Send DTMF digits to the connected AllStarLink node (control codes of the node)": "Στείλε ψηφία DTMF στον συνδεδεμένο κόμβο AllStarLink (κωδικοί ελέγχου του κόμβου)",
    "Listening": "Ακρόαση", "Listening · traffic": "Ακρόαση · κίνηση",
    "Password (your BrandMeister hotspot password)": "Κωδικός (ο κωδικός hotspot σου στο BrandMeister)",
    "Needed to connect to a DMR master. When ticked, it is kept in this program's settings file on this computer (not encrypted).": "Χρειάζεται για σύνδεση σε DMR master. Όταν είναι τσεκαρισμένο, μένει στο αρχείο ρυθμίσεων του προγράμματος σε αυτόν τον υπολογιστή (όχι κρυπτογραφημένος).",
    "The server and the password are also on the DMR page. Every other station shows its own server and port on its page.": "Ο server και ο κωδικός υπάρχουν και στη σελίδα DMR. Κάθε άλλος σταθμός δείχνει τον δικό του server και θύρα στη σελίδα του.",
    "P25 uses your DMR ID. The talkgroup server is on the P25 page.": "Το P25 χρησιμοποιεί το DMR ID σου. Ο server των talkgroup είναι στη σελίδα P25.", "Radio ID (your DMR ID)": "Radio ID (το DMR ID σου)",
    "The NXDN talkgroup server is on the NXDN page.": "Ο server των talkgroup NXDN είναι στη σελίδα NXDN.",
    "No extra settings: D-Star uses your callsign. The reflector and its module are chosen on the D-Star page.": "Καμία πρόσθετη ρύθμιση: το D-Star χρησιμοποιεί το διακριτικό σου. Ο reflector και το module επιλέγονται στη σελίδα D-Star.",
    "No extra settings: C4FM uses your callsign. The reflector address is on the C4FM page.": "Καμία πρόσθετη ρύθμιση: το C4FM χρησιμοποιεί το διακριτικό σου. Η διεύθυνση του reflector είναι στη σελίδα C4FM.",
    "No extra settings: M17 uses your callsign. The reflector and its module are on the M17 page.": "Καμία πρόσθετη ρύθμιση: το M17 χρησιμοποιεί το διακριτικό σου. Ο reflector και το module είναι στη σελίδα M17.",
    "Sign in with your AllStarLink portal account on the AllStar page (username, password).": "Συνδέσου με τον λογαριασμό σου στην πύλη AllStarLink στη σελίδα AllStar (όνομα χρήστη, κωδικός).", "AllStarLink": "AllStarLink", "C4FM / YSF": "C4FM / YSF",
    "DMR · {} entries — {} — press Refresh": "DMR · {} εγγραφές — {} — πάτα Ανανέωση",
    "TG list: {}": "Λίστα TG: {}", "DMR master list: {}": "Λίστα DMR master: {}",
    "not downloaded yet": "δεν έχει κατέβει ακόμη",
    "Signing in to AllStarLink…": "Σύνδεση στο AllStarLink…",
    "Enter a valid AllStarLink node number (digits only).": "Βάλε έγκυρο αριθμό κόμβου AllStarLink (μόνο ψηφία).",
    "Enter your AllStarLink portal username on the AllStar page (your callsign).": "Βάλε το όνομα χρήστη της πύλης AllStarLink στη σελίδα AllStar (το διακριτικό σου).",
    "Enter your AllStarLink portal password on the AllStar page.": "Βάλε τον κωδικό της πύλης AllStarLink στη σελίδα AllStar.",
    "Enter your AllStarLink portal username (your callsign, letters and digits only).": "Βάλε το όνομα χρήστη της πύλης AllStarLink (το διακριτικό σου, μόνο γράμματα και ψηφία).",
    "Enter your AllStarLink portal password.": "Βάλε τον κωδικό της πύλης AllStarLink.",
    "AllStarLink says: too many sign-in requests. Wait a minute and try again.": "Το AllStarLink λέει: πολλά αιτήματα σύνδεσης. Περίμενε ένα λεπτό και ξαναδοκίμασε.",
    "AllStarLink sign-in refused (HTTP {}).": "Το AllStarLink αρνήθηκε τη σύνδεση (HTTP {}).", "AllStarLink sign-in failed.": "Η σύνδεση στο AllStarLink απέτυχε.",
    "Cannot reach AllStarLink sign-in ({}).": "Δεν είναι δυνατή η επικοινωνία με τη σύνδεση του AllStarLink ({}).",
    "AllStarLink sign-in gave an unreadable answer.": "Η σύνδεση στο AllStarLink έδωσε μη αναγνώσιμη απάντηση.",
    "AllStarLink did not accept this callsign / password (the portal account must be active and its callsign validated).": "Το AllStarLink δεν δέχτηκε αυτό το διακριτικό / κωδικό (ο λογαριασμός στην πύλη πρέπει να είναι ενεργός και το διακριτικό επικυρωμένο).",
    "AllStarLink node list: {}": "Λίστα κόμβων AllStarLink: {}",
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
