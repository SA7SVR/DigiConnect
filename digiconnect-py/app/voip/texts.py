"""Greek texts of the VoIP phone. Every English text that the phone can show, as exact strings or templates ('{}' = a name or number kept as is).
Text without an entry is shown in English, never guessed. reason() also translates the messages that carry a server status code, "Busy (486)"."""
import re
from .. import i18n

EL = {
    # page
    "VoIP phone": "Τηλέφωνο VoIP", "Telephone calls over the Internet with your SIP server.": "Τηλεφωνικές κλήσεις μέσω Internet με τον SIP server σου.",
    "VoIP / SIP phone: sign in to the HELLAS Zone VoIP server (or another SIP server), see who is available and call them.": "Τηλέφωνο VoIP / SIP: συνδέσου στον VoIP server της HELLAS Zone (ή σε άλλον SIP server), δες ποιοι είναι διαθέσιμοι και κάλεσέ τους.",
    "ACCOUNT": "ΛΟΓΑΡΙΑΣΜΟΣ", "PHONE": "ΤΗΛΕΦΩΝΟ", "PEOPLE": "ΑΝΘΡΩΠΟΙ", "RECENT CALLS": "ΠΡΟΣΦΑΤΕΣ ΚΛΗΣΕΙΣ",
    "Server": "Server", "Port": "Port", "Transport": "Μεταφορά", "Username (extension)": "Όνομα χρήστη (εσωτερικό)", "Password": "Κωδικός", "Name shown to the other side": "Όνομα που βλέπει ο άλλος",
    "Remember the password on this computer": "Θυμήσου τον κωδικό σε αυτόν τον υπολογιστή", "Sign in when DigiConnect starts": "Σύνδεση όταν ανοίγει το DigiConnect", "Check the server's certificate (TLS)": "Έλεγχος του πιστοποιητικού του server (TLS)",
    "Sign in": "Σύνδεση", "Sign out": "Αποσύνδεση", "Signed in": "Συνδεδεμένος", "Signing in…": "Σύνδεση…", "Not signed in": "Δεν είσαι συνδεδεμένος",
    "The password is entered here by you and sent only to your server. Use a headset: the program has no echo cancellation, so with open speakers the other side hears itself.":
        "Τον κωδικό τον γράφεις εδώ εσύ και στέλνεται μόνο στον server σου. Χρησιμοποίησε ακουστικά με μικρόφωνο: το πρόγραμμα δεν έχει ακύρωση ηχούς, οπότε με ανοιχτά ηχεία ο άλλος ακούει τον εαυτό του.",
    "No call": "Καμία κλήση", "Sign in to call": "Συνδέσου για να καλέσεις", "Number or extension": "Αριθμός ή εσωτερικό", "Call": "Κλήση", "Hang up": "Κλείσιμο", "Mute": "Σίγαση", "Answer": "Απάντηση", "Decline": "Απόρριψη",
    "Microphone": "Μικρόφωνο", "Speakers": "Ηχεία", "Microphone:": "Μικρόφωνο:", "Speakers:": "Ηχεία:", "From": "Από", "To": "Προς", "Call ended": "Η κλήση τελείωσε",
    "Key pressed by the other side:": "Πλήκτρο που πάτησε ο άλλος:", "Sign in first, then enter a number": "Πρώτα συνδέσου και μετά γράψε αριθμό", "Enter a number": "Γράψε έναν αριθμό",
    "Add": "Προσθήκη", "Edit": "Αλλαγή", "Remove": "Αφαίρεση", "Add a person": "Προσθήκη ατόμου", "Name": "Όνομα", "Callsign": "Διακριτικό",
    "Add the people you call (name and extension). Their state is what the server reports: available, ringing, on a call or offline.":
        "Πρόσθεσε τα άτομα που καλείς (όνομα και εσωτερικό). Η κατάστασή τους είναι αυτή που αναφέρει ο server: διαθέσιμος, κουδουνίζει, σε κλήση ή εκτός.",
    "Double-click a person to call.": "Διπλό κλικ σε άτομο για κλήση.", "Sign in to see who is available.": "Συνδέσου για να δεις ποιοι είναι διαθέσιμοι.", "Incoming call from {}": "Εισερχόμενη κλήση από {}",
    # call states
    "Calling…": "Κλήση…", "Ringing…": "Κουδουνίζει…", "Incoming call": "Εισερχόμενη κλήση", "Connecting…": "Σύνδεση…", "In a call": "Σε κλήση", "On hold": "σε αναμονή", "Ended": "Τελείωσε",
    # person states
    "No such number on the server": "Δεν υπάρχει τέτοιος αριθμός στον server", "On a call": "Σε κλήση", "Ringing": "Κουδουνίζει", "Offline": "Εκτός σύνδεσης", "Available": "Διαθέσιμος",
    "No call (the server does not say if signed in)": "Καμία κλήση (ο server δεν λέει αν είναι συνδεδεμένος)", "Waiting for the server": "Αναμονή απάντησης από τον server",
    "no call": "καμία κλήση", "on a call": "σε κλήση", "ringing": "κουδουνίζει", "empty notification": "κενή ειδοποίηση", "no status in the notification": "η ειδοποίηση δεν έχει κατάσταση", "unreadable notification": "μη αναγνώσιμη ειδοποίηση",
    # registration and calls
    "Enter the server and your username first": "Γράψε πρώτα server και όνομα χρήστη", "Enter your password": "Γράψε τον κωδικό σου",
    "Cannot reach the server {}:{} ({})": "Δεν βρίσκω τον server {}:{} ({})", "Connection lost ({})": "Η σύνδεση χάθηκε ({})", "Connection lost": "Η σύνδεση χάθηκε",
    "The server {} did not answer (no reply in {} s)": "Ο server {} δεν απάντησε (καμία απάντηση σε {} s)", "Registered as {}": "Καταχωρήθηκε ως {}", "The server name could not be found": "Το όνομα του server δεν βρέθηκε",
    "not trying again; check the username and password and press Sign in": "δεν ξαναδοκιμάζω· έλεγξε όνομα χρήστη και κωδικό και πάτα Σύνδεση",
    "The server did not understand the request": "Ο server δεν κατάλαβε το αίτημα", "Wrong username or password": "Λάθος όνομα χρήστη ή κωδικός",
    "The server refused (wrong username or password, or this account may not connect from here)": "Ο server αρνήθηκε (λάθος όνομα χρήστη ή κωδικός, ή ο λογαριασμός δεν επιτρέπεται από εδώ)",
    "No such number": "Δεν υπάρχει τέτοιος αριθμός", "No answer from the server": "Καμία απάντηση από τον server", "Not available right now": "Δεν είναι διαθέσιμος αυτή τη στιγμή", "The number is incomplete": "Ο αριθμός είναι ελλιπής",
    "Busy": "Κατειλημμένο", "Cancelled": "Ακυρώθηκε", "The other side does not accept this audio format": "Ο άλλος δεν δέχεται αυτή τη μορφή ήχου", "Server error": "Σφάλμα του server",
    "Not available right now (the other side is not signed in or the service is busy)": "Δεν είναι διαθέσιμος τώρα (ο άλλος δεν είναι συνδεδεμένος ή η υπηρεσία είναι απασχολημένη)", "Busy everywhere": "Κατειλημμένος παντού", "Declined": "Απορρίφθηκε",
    "Refused": "Απορρίφθηκε από τον server", "Failed": "Απέτυχε", "Not signed in to the server": "Δεν είσαι συνδεδεμένος στον server", "The server's answer had no audio description": "Η απάντηση του server δεν είχε περιγραφή ήχου",
    "No common audio format with the other side": "Δεν υπάρχει κοινή μορφή ήχου με τον άλλον", "Hung up": "Έκλεισες την κλήση", "Missed": "Αναπάντητη", "Missed call": "Αναπάντητη κλήση",
    "No acknowledgement from the other side": "Ο άλλος δεν επιβεβαίωσε την κλήση", "The other side hung up": "Ο άλλος έκλεισε", "Subscription does not exist": "Η συνδρομή δεν υπάρχει",
    # sound
    "Audio is not available ({})": "Ο ήχος δεν είναι διαθέσιμος ({})", "No microphone: {}": "Δεν υπάρχει μικρόφωνο: {}", "No speakers: {}": "Δεν υπάρχουν ηχεία: {}",
    # tabs and settings
    "Account": "Λογαριασμός", "Network": "Δίκτυο", "Audio": "Ήχος", "Calls": "Κλήσεις", "Advanced": "Για προχωρημένους", "Codecs": "Κωδικοποιητές", "Automatic": "Αυτόματο", "Play": "Αναπαραγωγή",
    "Same as the username": "Ίδιο με το όνομα χρήστη", "Same as the server": "Ίδιο με τον server", "Authentication username (if different)": "Όνομα χρήστη ταυτοποίησης (αν διαφέρει)",
    "Domain / realm (if different from the server)": "Domain / realm (αν διαφέρει από τον server)",
    "Outbound proxy (optional; the connection goes there, the account stays on the server)": "Outbound proxy (προαιρετικό· η σύνδεση πηγαίνει εκεί, ο λογαριασμός μένει στον server)",
    "Local SIP port": "Τοπική θύρα SIP", "Registration time": "Χρόνος καταχώρησης", "Keep the NAT router open (keep-alive)": "Κράτα ανοιχτό το router NAT (keep-alive)", "Keep-alive every": "Keep-alive κάθε",
    "STUN server (optional, for audio behind a NAT router)": "Server STUN (προαιρετικό, για ήχο πίσω από router NAT)", "Public IP address (only if the router needs it set by hand)": "Δημόσια διεύθυνση IP (μόνο αν το router θέλει χειροκίνητη ρύθμιση)",
    "Audio ports from": "Θύρες ήχου από", "Only for a server with its own certificate": "Μόνο για server με δικό του πιστοποιητικό", "Certificate file of the server (.pem, optional)": "Αρχείο πιστοποιητικού του server (.pem, προαιρετικό)",
    "Network changes are used the next time you sign in.": "Οι αλλαγές του δικτύου ισχύουν στην επόμενη σύνδεση.",
    "Automatic (25 s UDP, 55 s TCP/TLS)": "Αυτόματο (25 s UDP, 55 s TCP/TLS)", "Refresh the list of devices": "Ανανέωση της λίστας συσκευών",
    "PCMU (G.711 µ-law)": "PCMU (G.711 µ-law)", "PCMA (G.711 A-law)": "PCMA (G.711 A-law)", "Preferred codec": "Προτιμώμενος κωδικοποιητής", "Keypad tones (DTMF) sent as": "Τόνοι πληκτρολογίου (DTMF) στέλνονται ως",
    "RTP events (RFC 4733)": "Γεγονότα RTP (RFC 4733)", "SIP INFO": "SIP INFO", "Sound devices": "Συσκευές ήχου", "Speakers / headset": "Ηχεία / ακουστικά", "Microphone level": "Στάθμη μικροφώνου",
    "Speaker volume": "Ένταση ηχείων", "Ring volume": "Ένταση κουδουνίσματος", "Audio delay (jitter buffer)": "Καθυστέρηση ήχου (jitter buffer)", "As chosen in Settings": "Όπως στις Ρυθμίσεις",
    "The sound devices the system reports (the same list as Settings). The first entry means 'as chosen in Settings'.": "Οι συσκευές ήχου που αναφέρει το σύστημα (ίδια λίστα με τις Ρυθμίσεις). Η πρώτη σημαίνει «όπως στις Ρυθμίσεις».",
    "Ringtone (incoming calls)": "Κουδούνισμα (εισερχόμενες κλήσεις)", "My own sound file (WAV)": "Δικό μου αρχείο ήχου (WAV)", "A WAV file, used when 'My own sound file' is chosen": "Αρχείο WAV, χρησιμοποιείται όταν επιλεγεί «Δικό μου αρχείο ήχου»",
    "Classic telephone (double ring)": "Κλασικό τηλέφωνο (διπλό κουδούνισμα)", "European telephone (double ring)": "Ευρωπαϊκό τηλέφωνο (διπλό κουδούνισμα)", "Old bell": "Παλιό κουδούνι", "Digital beeps": "Ψηφιακά μπιπ", "Soft double beep": "Απαλό διπλό μπιπ", "Trill": "Τρίλια", "Chime": "Καμπανάκι",
    "The ring cannot be played now (a call is in progress, or the speakers are not available).": "Το κουδούνισμα δεν παίζεται τώρα (γίνεται κλήση ή δεν υπάρχουν διαθέσιμα ηχεία).",
    "This file cannot be used as a ringtone:": "Αυτό το αρχείο δεν μπορεί να χρησιμοποιηθεί ως κουδούνισμα:",
    "Devices, codecs and the audio delay are used from the next call. The levels, the ringtone and the ring volume act at once.": "Οι συσκευές, οι κωδικοποιητές και η καθυστέρηση ήχου ισχύουν από την επόμενη κλήση. Οι στάθμες, το κουδούνισμα και η ένταση κουδουνίσματος ισχύουν αμέσως.",
    "Answer incoming calls automatically": "Αυτόματη απάντηση στις εισερχόμενες κλήσεις", "Do not disturb (callers hear busy; the call is listed as missed)": "Μην ενοχλείτε (ο καλών ακούει κατειλημμένο· η κλήση καταγράφεται ως αναπάντητη)",
    "Do not disturb": "Μην ενοχλείτε", "Answer after": "Απάντηση μετά από", "Voicemail number": "Αριθμός τηλεφωνητή", "Call voicemail": "Κλήση τηλεφωνητή", "Enter the voicemail number first": "Γράψε πρώτα τον αριθμό του τηλεφωνητή",
    "These settings act at once.": "Αυτές οι ρυθμίσεις ισχύουν αμέσως.", "User-Agent (how the program introduces itself)": "User-Agent (πώς συστήνεται το πρόγραμμα)",
    "Write every SIP message to Diagnostics (passwords are hidden)": "Γράψε κάθε μήνυμα SIP στα Διαγνωστικά (οι κωδικοί κρύβονται)",
    "Restore the network, audio, call and advanced settings to their defaults": "Επαναφορά των ρυθμίσεων δικτύου, ήχου, κλήσεων και προχωρημένων στις προεπιλογές",
    "The account (server, username, password), the people and the call list are not touched. Used from the next sign-in.": "Ο λογαριασμός (server, όνομα χρήστη, κωδικός), τα άτομα και η λίστα κλήσεων δεν αλλάζουν. Ισχύει από την επόμενη σύνδεση.",
    "The local SIP port {} cannot be used ({})": "Η τοπική θύρα SIP {} δεν μπορεί να χρησιμοποιηθεί ({})", "The server's certificate is not trusted ({})": "Το πιστοποιητικό του server δεν είναι αξιόπιστο ({})",
    "The server closed the connection": "Ο server έκλεισε τη σύνδεση", "The server ended the subscription": "Ο server τερμάτισε την εγγραφή ενημερώσεων",
    # account request
    "I don't have an account: request one": "Δεν έχω λογαριασμό: ζήτα έναν", "Request an account again": "Νέα αίτηση λογαριασμού", "Check the request": "Έλεγχος αίτησης", "Request a VoIP account": "Αίτηση λογαριασμού VoIP",
    "Your request goes to the owner of the HELLAS Zone VoIP server, who creates the account and approves it. When he does, this program receives the extension and the password by itself.":
        "Η αίτησή σου πηγαίνει στον ιδιοκτήτη του VoIP server του HELLAS Zone, που φτιάχνει τον λογαριασμό και τον εγκρίνει. Όταν το κάνει, το πρόγραμμα παίρνει μόνο του το εσωτερικό και τον κωδικό.",
    "Your name": "Το όνομά σου", "Extension you would like (optional)": "Εσωτερικό που θα ήθελες (προαιρετικό)", "Message (optional)": "Μήνυμα (προαιρετικό)",
    "optional": "προαιρετικό", "Send the request": "Αποστολή αίτησης", "Sending…": "Αποστολή…", "Checking…": "Έλεγχος…",
    "I agree that my name and callsign are sent to the HELLAS Zone server only to answer this request": "Συμφωνώ να σταλούν το όνομα και το διακριτικό μου στον server του HELLAS Zone μόνο για να απαντηθεί αυτή η αίτηση",
    "Your request is waiting for the owner of the server. This page checks by itself every few minutes.": "Η αίτησή σου περιμένει τον ιδιοκτήτη του server. Η σελίδα ελέγχει μόνη της κάθε λίγα λεπτά.",
    "This account is blocked by the owner of the server": "Ο λογαριασμός έχει αποκλειστεί από τον ιδιοκτήτη του server",
    "Set by the owner of the server": "Ορίστηκε από τον ιδιοκτήτη του server",
    "Check the account now": "Έλεγχος του λογαριασμού τώρα", "Use another account": "Χρήση άλλου λογαριασμού",
    "This account comes from the owner of the server: the extension and the password are kept up to date by themselves.": "Ο λογαριασμός προέρχεται από τον ιδιοκτήτη του server: το εσωτερικό και ο κωδικός ενημερώνονται μόνοι τους.",
    "The account is no longer kept up to date from the server. You can enter another account.": "Ο λογαριασμός δεν ενημερώνεται πια από τον server. Μπορείς να βάλεις άλλον λογαριασμό.",
    "The owner released this account: the fields are unlocked and you can use any server. The details saved here stay as they are.": "Ο ιδιοκτήτης απελευθέρωσε τον λογαριασμό: τα πεδία ξεκλείδωσαν και μπορείς να χρησιμοποιήσεις όποιον server θέλεις. Τα στοιχεία που έχεις αποθηκευμένα εδώ μένουν ως έχουν.",
    "The server no longer has this request.": "Ο server δεν έχει πια αυτή την αίτηση.",
    "The block was lifted. You can sign in again.": "Ο αποκλεισμός άρθηκε. Μπορείς να συνδεθείς ξανά.",
    "The owner changed the account details; they were updated here.": "Ο ιδιοκτήτης άλλαξε τα στοιχεία του λογαριασμού· ενημερώθηκαν εδώ.",
    "Your request is still waiting for the owner of the server.": "Η αίτησή σου περιμένει ακόμη τον ιδιοκτήτη του server.",
    "The request was sent. You will receive the account here as soon as the owner approves it.": "Η αίτηση στάλθηκε. Θα πάρεις τον λογαριασμό εδώ μόλις την εγκρίνει ο ιδιοκτήτης.",
    "The owner did not approve the request.": "Ο ιδιοκτήτης δεν ενέκρινε την αίτηση.",
    "The account was approved and filled in: extension {}. Press Sign in.": "Ο λογαριασμός εγκρίθηκε και συμπληρώθηκε: εσωτερικό {}. Πάτα Σύνδεση.",
    "The request was approved, but the password was already handed over. Ask the owner for it.": "Η αίτηση εγκρίθηκε, αλλά ο κωδικός έχει ήδη παραδοθεί. Ζήτα τον από τον ιδιοκτήτη.",
    "The server cannot be reached now:": "Ο server δεν είναι προσβάσιμος τώρα:",
    "The server is not accepting account requests now": "Ο server δεν δέχεται αιτήσεις λογαριασμού τώρα", "You must agree before the request is sent": "Πρέπει να συμφωνήσεις πριν σταλεί η αίτηση", "Write your name": "Γράψε το όνομά σου",
    "The callsign does not look right": "Το διακριτικό δεν φαίνεται σωστό",
    "Too many requests from this address today; try again tomorrow": "Πάρα πολλές αιτήσεις από αυτή τη διεύθυνση σήμερα· δοκίμασε αύριο",
    "A request with this callsign is already waiting for the owner": "Υπάρχει ήδη αίτηση με αυτό το διακριτικό που περιμένει τον ιδιοκτήτη",
    "The server does not know this request (it may have been deleted)": "Ο server δεν γνωρίζει αυτή την αίτηση (ίσως διαγράφηκε)", "The server did not understand the request": "Ο server δεν κατάλαβε το αίτημα",
}
i18n.EL.update(EL)

_CODE = re.compile(r"^(.*?) \((\d{3}[^)]*)\)( - .*)?$", re.S)


def reason(text: str) -> str:
    """tr() for a message that may end in a server status code and a hint: 'Wrong username or password (401) - not trying again; ...'."""
    if not text: return text
    m = _CODE.match(text)
    if not m: return i18n.tr(text)
    base, code, tail = m.groups()
    return i18n.tr(base) + f" ({code})" + (" - " + i18n.tr(tail[3:]) if tail else "")
