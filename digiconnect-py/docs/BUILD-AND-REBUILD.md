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
Αν αλλάξει η **μηχανή** (`engine/`) χρειάζεται ο πλήρης installer· η αυτόματη αναβάθμιση (`.dcpkg`) δεν αντικαθιστά τη μηχανή.

## 6. Τι ΔΕΝ είναι στον κώδικα και πρέπει να έχεις εσύ
1. **`license-key.php`** — το ιδιωτικό κλειδί υπογραφής των αδειών. Είναι στον server (και αντίγραφο στο `data/license-key.bak.php`). Κράτα και δικό σου αντίγραφο σε ασφαλές μέρος. Η αντίστοιχη δημόσια τιμή είναι μέσα στο πρόγραμμα: `app/license.py`, λίστα `PUBKEYS`. Αν χαθεί παντού: `php tools/make_license_key.php` φτιάχνει νέο ζεύγος, τυπώνει το δημόσιο κλειδί· **πρόσθεσέ το** στη λίστα `PUBKEYS` (μην σβήσεις το παλιό) και βγάλε νέα έκδοση — τα παλιά προγράμματα δεν θα αναγνωρίζουν τις νέες απαντήσεις μέχρι να ενημερωθούν.
2. **`config.php`** του server (κωδικός panel κ.ά.) — μόνο σε σένα. Υπόδειγμα: `server/digiconnect/config.sample.php`.
3. **Η βάση και τα δεδομένα του server** (`data/`, `pkg/`): χρήστες, άδειες, πληρωμές. Το panel έχει αντίγραφα ασφαλείας· κατέβαζέ τα.
4. **Ρυθμίσεις έξω από το αποθετήριο**: ο λογαριασμός PayPal και το IPN (βλ. `server/digiconnect/ΔΙΑΒΑΣΕ-ΜΕ.txt`), ο λογαριασμός GitHub, το hosting του hellaszone.com.

## 7. Τι δεν έχει δοκιμαστεί (για να μην σε εκπλήξει)
Το εικονίδιο μέσα στο .exe και η εγκατάσταση σε πραγματικά Windows ελέγχονται από το CI σε εικονικό Windows, όχι σε δικό σου υπολογιστή. Ήχος/πομποδέκτης, EchoLink με πραγματικό λογαριασμό και πραγματική πληρωμή PayPal δεν δοκιμάζονται αυτόματα.
