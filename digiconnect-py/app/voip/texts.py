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
