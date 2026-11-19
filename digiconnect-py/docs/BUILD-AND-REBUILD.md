# DigiConnect — πώς χτίζεται από το μηδέν / How to rebuild everything

Αυτό το αρχείο λέει **τι χρειάζεται για να ξαναστηθεί όλο το DigiConnect** (πρόγραμμα, μηχανή, installers, server) αν χαθεί ο υπολογιστής ή το GitHub.
Ο κώδικας σε αυτό το πακέτο (`3-SOURCE`) είναι **ολόκληρο το αποθετήριο**: τίποτα δεν λείπει εκτός από τα 4 πράγματα της ενότητας 6, που ζουν σε δικά σου μέρη και δεν μπαίνουν ποτέ σε δημόσιο πακέτο.

## 1. Τι είναι τι (φάκελοι του αποθετηρίου)
| Φάκελος | Τι είναι |
|---|---|
| `digiconnect-py/app/` | Το πρόγραμμα (Python, PySide6): σελίδες, άδειες, ενημερώσεις, γλώσσες (`i18n.py`) |
| `digiconnect-py/engine/` | Η μηχανή `dcengine` (C++/Qt 6): DMR, D-STAR, YSF, NXDN, P25, M17, EchoLink, AllStar. Περιέχει μέσα της τα codec2, imbe, mbe, gsm — δεν κατεβάζει τίποτα |
| `digiconnect-py/packaging/` | **Το «κέλυφος»**: `DigiConnect.spec` (PyInstaller), `DigiConnect.iss` + `installer/` (installer Windows: Inno Setup, εικόνες, κείμενα EL/EN), `package/` (το ΔΙΑΒΑΣΕ-ΠΡΩΤΑ του πακέτου), `build-pins.txt` (ακριβείς εκδόσεις) |
| `digiconnect-py/server/digiconnect/` | Ο server (PHP) για το hellaszone.com: άδειες, εγγραφές, πληρωμές IPN, panel (`admin/`) |
| `digiconnect-py/tools/` | `build_dcpkg.py` (αρχείο αυτόματης αναβάθμισης), `selftest_built.sh` (τεστ του χτισμένου προγράμματος), `make_license_key.php` (νέο κλειδί αδειών) |
| `digiconnect-py/tests/`, `engine/tests/` | Όλα τα αυτόματα τεστ |
| `digiconnect-py/assets/`, `LICENSES/` | Εικονίδια/λογότυπο, άδειες χρήσης τρίτων |
| `.github/workflows/digiconnect-py.yml` | **Η συνταγή χτισίματος**: χτίζει Windows, Linux, Mac Intel, Mac Apple Silicon και συναρμολογεί το πακέτο |
| `digiconnect-py/docs/` | Σημειώσεις εκδόσεων, `SPEC.md`, `UPDATES.md` |

## 2. Ο εύκολος τρόπος: GitHub (αυτός που χρησιμοποιούμε)
Αποθετήριο: `https://github.com/SA7SVR/DigiConnect`. Το χτίσιμο ξεκινά όταν γίνει push στον κλάδο **`digiconnect-py`** (αλλαγές μέσα στο `digiconnect-py/` ή στο workflow), ή χειροκίνητα από Actions › «Build DigiConnect» › Run workflow.
Το αποτέλεσμα (όταν περάσουν ΟΛΑ τα jobs) είναι το artifact **DigiConnect-PACKAGE** στη σελίδα του run: ένα zip με πρόγραμμα, server, source και αυτό το έγγραφο.
Αν χαθεί το GitHub: φτιάξε νέο αποθετήριο, ανέβασε τον κώδικα του `3-SOURCE` (φάκελος `DigiConnect-source-<έκδοση>/`), κάνε τον κλάδο `digiconnect-py` και πάτα Run workflow.

## 3. Εκδόσεις εργαλείων (για χτίσιμο στο χέρι ή αν σπάσει το CI)
Τα ακριβή πακέτα Python είναι στο `packaging/build-pins.txt` (`python -m pip install -r packaging/build-pins.txt`). Περίληψη:
Python 3.12 · PySide6 6.12.0 · PyInstaller 6.22.3 · numpy 2.5.5 · sounddevice 0.5.6 · pytest 9.2.0 ·
Qt 6.8.1 (Windows με MinGW 13.1.0 `tools_mingw1310`, και Linux) · Qt 6.9.3 (macOS, `MACOSX_DEPLOYMENT_TARGET=12.0`) με τα modules `qtmultimedia qtserialport` · CMake · Ninja (Linux) · Inno Setup 6 (Windows) · linuxdeploy + linuxdeploy-plugin-qt (Linux).
Μην ανακατεύεις το Qt της μηχανής με το Qt του PySide6: στα βήματα «Build app» το CI βγάζει το Qt του από το PATH.

## 4. Χτίσιμο στο χέρι (οι εντολές είναι αυτές του workflow — δες το αρχείο για τις λεπτομέρειες ανά σύστημα)
Μηχανή (από τον φάκελο `digiconnect-py`):
```
cmake -S engine -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=<φάκελος του Qt>
cmake --build build --parallel
```
Windows: `-G "MinGW Makefiles"` με MinGW (ο codec2 θέλει C99), μετά `windeployqt --release --no-translations` στο `dcengine.exe`. macOS: `-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0`, μετά `macdeployqt build/dcengine.app`. Linux: `-G Ninja`, μετά linuxdeploy με το plugin Qt.
Πρόγραμμα:
```
pip install -r packaging/build-pins.txt
python -m pytest -q tests          # με DC_ENGINE=<διαδρομή του dcengine> και QT_QPA_PLATFORM=offscreen
python -m PyInstaller --noconfirm packaging/DigiConnect.spec
```
Μετά η μηχανή αντιγράφεται στο `dist/DigiConnect/engine/` (Windows/Linux) ή στο `DigiConnect.app/Contents/Resources/` (macOS). Δοκιμή του χτισμένου: `bash tools/selftest_built.sh <διαδρομή του προγράμματος>`.
Windows installer: `ISCC.exe /DAppVer=<έκδοση> packaging\DigiConnect.iss` → `installer_out\DigiConnect-Setup.exe`. macOS: `hdiutil create -volname DigiConnect -srcfolder dist/DigiConnect.app -format UDZO DigiConnect-macOS-<Intel|AppleSilicon>.dmg`.
Αρχείο αυτόματης αναβάθμισης: `python tools/build_dcpkg.py <έκδοση> --out update_pkg` → `DigiConnect-<έκδοση>.dcpkg`.

## 5. Νέα έκδοση: τι αλλάζει
Ο αριθμός έκδοσης πρέπει να είναι **ο ίδιος παντού** (το CI το ελέγχει): `app/version.py` (`APP_VERSION`), `bootstrap.py`, `server/digiconnect/lib.php` (`DC_SERVER_VERSION`), και τα κείμενα `packaging/installer/info_before_*.txt`, `docs/RELEASE-NOTES-<έκδοση>.txt`.
**Η μηχανή (`engine/`, C++) και η αυτόματη αναβάθμιση (από 2.4.0):** η μηχανή αναβαθμίζεται πια μέσα από την αυτόματη ενημέρωση, με δικό της πακέτο `.dceng` ανά σύστημα (Windows x64, Linux x64, macOS Intel, macOS Apple Silicon). Δεν χρειάζεται νέο Setup.
Κανόνες όταν αλλάζει κάτι στο `engine/`:
1. Ανέβασε το `ENGINE_VERSION` στο `bootstrap.py` στον αριθμό της νέας έκδοσης (π.χ. `"2.5.0"`) και τρέξε `python3 tools/engine_src_hash.py --write` (ανανεώνει το `tests/engine_src.sha256`). Ένα τεστ (`tests/test_engine_update.py::test_the_engine_sources_and_ENGINE_VERSION_move_together`) αποτυγχάνει αν ξεχαστεί.
2. Το CI φτιάχνει μόνο του τα 4 `.dceng` (`tools/build_engine_pkg.py`), τα δοκιμάζει εγκατεστημένα σε κάθε σύστημα (`tools/test_engine_pkg.py`: ξεπακετάρισμα, υπογραφή στο Mac, πραγματικό `hello`) και τα βάζει στο πακέτο: `1-PROGRAM/Αναβάθμιση/engine-packages/`.
3. Το `.dcpkg` της έκδοσης βγαίνει πάντα με `--min-engine <ENGINE_VERSION>`: ο νέος κώδικας Python δεν ενεργοποιείται αν δεν υπάρχει η μηχανή που χρειάζεται (το πρόγραμμα κατεβάζει πρώτα τη μηχανή· αλλιώς δεν αλλάζει τίποτα).
4. Στο panel (Εκδόσεις › Πακέτα μηχανής) ανεβάζεις τα 4 `.dceng` ΜΟΝΟ αν η έκδοση δείχνει «✗ λείπουν πακέτα μηχανής». Πρώτα τα πακέτα, μετά «Ενεργοποίηση» της έκδοσης. Αν η μηχανή δεν άλλαξε, το panel δείχνει ✓ και δεν ανεβάζεις τίποτα.
Στο χέρι: `python3 tools/build_engine_pkg.py <φάκελος μηχανής> <ENGINE_VERSION> <windows|macos|linux> <x64|arm64> --out <φάκελος>` και δοκιμή: `python3 tools/test_engine_pkg.py <αρχείο.dceng>`. Στο Mac η μηχανή (`dcengine.app`) πρέπει να έχει υπογραφεί ad-hoc (`codesign --force --deep --sign -`) πριν πακεταριστεί (το κάνει το CI).

**Πότε χρειάζεται ακόμα νέο Setup (ανεβαίνει το `SHELL_VERSION` στο `bootstrap.py` και το `.dcpkg` βγαίνει με `--min-shell <νέο SHELL_VERSION>`):** μόνο όταν αλλάζει κάτι που η αναβάθμιση δεν μπορεί να αντικαταστήσει — η Qt ή η Python (PySide6/PyInstaller), τα αρχεία του κελύφους (`bootstrap.py`, `run.py`) ή ο installer. Τότε τα προγράμματα με παλιό Setup δείχνουν «Η έκδοση Χ χρειάζεται νέο πλήρες πρόγραμμα εγκατάστασης» (`app/updater.py`, κατάσταση `needs_installer`) αντί να πάρουν μισή αναβάθμιση. Αλλαγές μόνο σε Python/εικόνες/κείμενα ή μόνο στη μηχανή **δεν** αλλάζουν το `SHELL_VERSION`. Σημείωση: το CI τώρα καλεί το `build_dcpkg.py` με `--min-engine` αλλά χωρίς `--min-shell` (προεπιλογή 2.2.0)· πρέπει να προσαρμοστεί στο ίδιο βήμα την πρώτη φορά που θα ανέβει το `SHELL_VERSION`.

## 6. Τι ΔΕΝ είναι στον κώδικα και πρέπει να έχεις εσύ
1. **`license-key.php`** — το ιδιωτικό κλειδί υπογραφής των αδειών. Είναι στον server (και αντίγραφο στο `data/license-key.bak.php`). Κράτα και δικό σου αντίγραφο σε ασφαλές μέρος. Η αντίστοιχη δημόσια τιμή είναι μέσα στο πρόγραμμα: `app/license.py`, λίστα `PUBKEYS`. Αν χαθεί παντού: `php tools/make_license_key.php` φτιάχνει νέο ζεύγος, τυπώνει το δημόσιο κλειδί· **πρόσθεσέ το** στη λίστα `PUBKEYS` (μην σβήσεις το παλιό) και βγάλε νέα έκδοση — τα παλιά προγράμματα δεν θα αναγνωρίζουν τις νέες απαντήσεις μέχρι να ενημερωθούν.
2. **`config.php`** του server (κωδικός panel κ.ά.) — μόνο σε σένα. Υπόδειγμα: `server/digiconnect/config.sample.php`.
3. **Η βάση και τα δεδομένα του server** (`data/`, `pkg/`): χρήστες, άδειες, πληρωμές. Το panel έχει αντίγραφα ασφαλείας· κατέβαζέ τα.
4. **Ρυθμίσεις έξω από το αποθετήριο**: ο λογαριασμός PayPal και το IPN (βλ. `server/digiconnect/ΔΙΑΒΑΣΕ-ΜΕ.txt`), ο λογαριασμός GitHub, το hosting του hellaszone.com.

## 7. Τι δεν έχει δοκιμαστεί (για να μην σε εκπλήξει)
Το εικονίδιο μέσα στο .exe και η εγκατάσταση σε πραγματικά Windows ελέγχονται από το CI σε εικονικό Windows, όχι σε δικό σου υπολογιστή. Ήχος/πομποδέκτης, EchoLink με πραγματικό λογαριασμό και πραγματική πληρωμή PayPal δεν δοκιμάζονται αυτόματα.

Αναβάθμιση της μηχανής (2.4.0): το CI δοκιμάζει σε κάθε σύστημα ότι το πακέτο `.dceng` ξεπακετάρεται, ότι η υπογραφή (Mac) είναι έγκυρη και ότι η εγκατεστημένη μηχανή απαντά `hello`. ΔΕΝ έχει δοκιμαστεί σε πραγματικούς υπολογιστές: (α) αν το macOS (Gatekeeper) αφήνει να τρέξει μηχανή που έγραψε το ίδιο το πρόγραμμα με ad-hoc υπογραφή — οι πηγές λένε ότι αρχεία που γράφει μια εφαρμογή δεν παίρνουν σήμα καραντίνας, δεν έχει ελεγχθεί σε Mac· (β) αν κάποιο antivirus των Windows ενοχλείται από νέο .exe στον φάκελο του χρήστη. Αν συμβεί, το πρόγραμμα γυρίζει αυτόματα στη μηχανή του Setup και το γράφει στα διαγνωστικά (`updated engine … could not be started`).
