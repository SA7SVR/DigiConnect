; *** Inno Setup 6.1.0+ — Greek (Ελληνικά) messages for DigiConnect; messages not translated here keep the English text ***
;
; To download user-contributed translations of this file, go to:
;   https://jrsoftware.org/files/istrans/
;
; Note: When translating this text, do not add periods (.) to the end of
; messages that didn't have them already, because on those messages Inno
; Setup adds the periods automatically (appending a period would result in
; two periods being displayed).

[LangOptions]
; The following three entries are very important. Be sure to read and 
; understand the '[LangOptions] section' topic in the help file.
LanguageName=Ελληνικά
LanguageID=$0408
LanguageCodePage=1253
; If the language you are translating to requires special font faces or
; sizes, uncomment any of the following entries and change them accordingly.
;DialogFontName=
;DialogFontSize=8
;WelcomeFontName=Verdana
;WelcomeFontSize=12
;TitleFontName=Arial
;TitleFontSize=29
;CopyrightFontName=Arial
;CopyrightFontSize=8

[Messages]

; *** Application titles
SetupAppTitle=Εγκατάσταση
SetupWindowTitle=Εγκατάσταση - %1
UninstallAppTitle=Απεγκατάσταση
UninstallAppFullTitle=Απεγκατάσταση %1

; *** Misc. common
InformationTitle=Πληροφορίες
ConfirmTitle=Επιβεβαίωση
ErrorTitle=Σφάλμα

; *** SetupLdr messages
SetupLdrStartupMessage=Θα εγκατασταθεί το %1. Θέλεις να συνεχίσεις;
LdrCannotCreateTemp=Unable to create a temporary file. Setup aborted
LdrCannotExecTemp=Unable to execute file in the temporary directory. Setup aborted
HelpTextNote=

; *** Startup error messages
LastErrorMessage=%1.%n%nError %2: %3
SetupFileMissing=The file %1 is missing from the installation directory. Please correct the problem or obtain a new copy of the program.
SetupFileCorrupt=The setup files are corrupted. Please obtain a new copy of the program.
SetupFileCorruptOrWrongVer=The setup files are corrupted, or are incompatible with this version of Setup. Please correct the problem or obtain a new copy of the program.
InvalidParameter=An invalid parameter was passed on the command line:%n%n%1
SetupAlreadyRunning=Η εγκατάσταση τρέχει ήδη.
WindowsVersionNotSupported=This program does not support the version of Windows your computer is running.
WindowsServicePackRequired=This program requires %1 Service Pack %2 or later.
NotOnThisPlatform=This program will not run on %1.
OnlyOnThisPlatform=This program must be run on %1.
OnlyOnTheseArchitectures=This program can only be installed on versions of Windows designed for the following processor architectures:%n%n%1
WinVersionTooLowError=This program requires %1 version %2 or later.
WinVersionTooHighError=This program cannot be installed on %1 version %2 or later.
AdminPrivilegesRequired=Για την εγκατάσταση χρειάζεσαι δικαιώματα διαχειριστή.
PowerUserPrivilegesRequired=You must be logged in as an administrator or as a member of the Power Users group when installing this program.
SetupAppRunningError=Το %1 τρέχει αυτή τη στιγμή.%n%nΚλείσε το και πάτησε OK για να συνεχίσεις, ή Άκυρο για έξοδο.
UninstallAppRunningError=Το %1 τρέχει αυτή τη στιγμή.%n%nΚλείσε το και πάτησε OK, ή Άκυρο για έξοδο.

; *** Startup questions
PrivilegesRequiredOverrideTitle=Τρόπος εγκατάστασης
PrivilegesRequiredOverrideInstruction=Διάλεξε τρόπο εγκατάστασης
PrivilegesRequiredOverrideText1=Το %1 μπορεί να εγκατασταθεί για όλους τους χρήστες (θέλει δικαιώματα διαχειριστή) ή μόνο για εσένα.
PrivilegesRequiredOverrideText2=Το %1 μπορεί να εγκατασταθεί μόνο για εσένα ή για όλους τους χρήστες (θέλει δικαιώματα διαχειριστή).
PrivilegesRequiredOverrideAllUsers=Για &όλους τους χρήστες
PrivilegesRequiredOverrideAllUsersRecommended=Για &όλους τους χρήστες (προτείνεται)
PrivilegesRequiredOverrideCurrentUser=Μόνο για &εμένα
PrivilegesRequiredOverrideCurrentUserRecommended=Μόνο για &εμένα (προτείνεται)

; *** Misc. errors
ErrorCreatingDir=Setup was unable to create the directory "%1"
ErrorTooManyFilesInDir=Unable to create a file in the directory "%1" because it contains too many files

; *** Setup common messages
ExitSetupTitle=Έξοδος
ExitSetupMessage=Η εγκατάσταση δεν ολοκληρώθηκε. Αν βγεις τώρα, το πρόγραμμα δεν θα εγκατασταθεί.%n%nΜπορείς να την ξανατρέξεις όποτε θέλεις.%n%nΈξοδος;
AboutSetupMenuItem=&Σχετικά με την εγκατάσταση...
AboutSetupTitle=Σχετικά με την εγκατάσταση
AboutSetupMessage=%1 version %2%n%3%n%n%1 home page:%n%4
AboutSetupNote=
TranslatorNote=

; *** Buttons
ButtonBack=< &Πίσω
ButtonNext=&Επόμενο >
ButtonInstall=&Εγκατάσταση
ButtonOK=OK
ButtonCancel=Άκυρο
ButtonYes=&Ναι
ButtonYesToAll=Ναι σε &όλα
ButtonNo=&Όχι
ButtonNoToAll=Ό&χι σε όλα
ButtonFinish=&Τέλος
ButtonBrowse=&Αναζήτηση...
ButtonWizardBrowse=Ανα&ζήτηση...
ButtonNewFolder=&Νέος φάκελος

; *** "Select Language" dialog messages
SelectLanguageTitle=Γλώσσα εγκατάστασης
SelectLanguageLabel=Διάλεξε τη γλώσσα της εγκατάστασης.

; *** Common wizard text
ClickNext=Πάτησε Επόμενο για να συνεχίσεις ή Άκυρο για έξοδο.
BeveledLabel=
BrowseDialogTitle=Επιλογή φακέλου
BrowseDialogLabel=Διάλεξε έναν φάκελο από τη λίστα και πάτησε OK.
NewFolderName=Νέος φάκελος

; *** "Welcome" wizard page
WelcomeLabel1=Καλώς ήρθες στην εγκατάσταση του [name]
WelcomeLabel2=Θα εγκατασταθεί το [name/ver] στον υπολογιστή σου.%n%nΠροτείνεται να κλείσεις τις άλλες εφαρμογές πριν συνεχίσεις.

; *** "Password" wizard page
WizardPassword=Password
PasswordLabel1=This installation is password protected.
PasswordLabel3=Please provide the password, then click Next to continue. Passwords are case-sensitive.
PasswordEditLabel=&Password:
IncorrectPassword=The password you entered is not correct. Please try again.

; *** "License Agreement" wizard page
WizardLicense=Άδεια χρήσης
LicenseLabel=Διάβασε τις παρακάτω σημαντικές πληροφορίες πριν συνεχίσεις.
LicenseLabel3=Διάβασε την άδεια χρήσης. Πρέπει να αποδεχτείς τους όρους για να συνεχίσεις.
LicenseAccepted=&Αποδέχομαι τους όρους
LicenseNotAccepted=&Δεν αποδέχομαι τους όρους

; *** "Information" wizard pages
WizardInfoBefore=Πληροφορίες
InfoBeforeLabel=Διάβασε τις παρακάτω σημαντικές πληροφορίες πριν συνεχίσεις.
InfoBeforeClickLabel=Όταν είσαι έτοιμος, πάτησε Επόμενο.
WizardInfoAfter=Πληροφορίες
InfoAfterLabel=Διάβασε τις παρακάτω σημαντικές πληροφορίες.
InfoAfterClickLabel=Όταν είσαι έτοιμος, πάτησε Επόμενο.

; *** "User Information" wizard page
WizardUserInfo=User Information
UserInfoDesc=Please enter your information.
UserInfoName=&User Name:
UserInfoOrg=&Organization:
UserInfoSerial=&Serial Number:
UserInfoNameRequired=You must enter a name.

; *** "Select Destination Location" wizard page
WizardSelectDir=Φάκελος εγκατάστασης
SelectDirDesc=Πού να εγκατασταθεί το [name];
SelectDirLabel3=Το [name] θα εγκατασταθεί στον παρακάτω φάκελο.
SelectDirBrowseLabel=Για να συνεχίσεις πάτησε Επόμενο. Για άλλο φάκελο πάτησε Αναζήτηση.
DiskSpaceGBLabel=Χρειάζονται τουλάχιστον [gb] GB ελεύθερου χώρου.
DiskSpaceMBLabel=Χρειάζονται τουλάχιστον [mb] MB ελεύθερου χώρου.
CannotInstallToNetworkDrive=Setup cannot install to a network drive.
CannotInstallToUNCPath=Setup cannot install to a UNC path.
InvalidPath=You must enter a full path with drive letter; for example:%n%nC:\APP%n%nor a UNC path in the form:%n%n\\server\share
InvalidDrive=The drive or UNC share you selected does not exist or is not accessible. Please select another.
DiskSpaceWarningTitle=Δεν υπάρχει αρκετός χώρος
DiskSpaceWarning=Η εγκατάσταση χρειάζεται τουλάχιστον %1 KB, αλλά ο δίσκος έχει μόνο %2 KB.%n%nΘέλεις να συνεχίσεις;
DirNameTooLong=The folder name or path is too long.
InvalidDirName=The folder name is not valid.
BadDirName32=Folder names cannot include any of the following characters:%n%n%1
DirExistsTitle=Ο φάκελος υπάρχει
DirExists=Ο φάκελος:%n%n%1%n%nυπάρχει ήδη. Θέλεις να γίνει εγκατάσταση σε αυτόν;
DirDoesntExistTitle=Ο φάκελος δεν υπάρχει
DirDoesntExist=Ο φάκελος:%n%n%1%n%nδεν υπάρχει. Θέλεις να δημιουργηθεί;

; *** "Select Components" wizard page
WizardSelectComponents=Select Components
SelectComponentsDesc=Which components should be installed?
SelectComponentsLabel2=Select the components you want to install; clear the components you do not want to install. Click Next when you are ready to continue.
FullInstallation=Full installation
; if possible don't translate 'Compact' as 'Minimal' (I mean 'Minimal' in your language)
CompactInstallation=Compact installation
CustomInstallation=Custom installation
NoUninstallWarningTitle=Components Exist
NoUninstallWarning=Setup has detected that the following components are already installed on your computer:%n%n%1%n%nDeselecting these components will not uninstall them.%n%nWould you like to continue anyway?
ComponentSize1=%1 KB
ComponentSize2=%1 MB
ComponentsDiskSpaceGBLabel=Current selection requires at least [gb] GB of disk space.
ComponentsDiskSpaceMBLabel=Current selection requires at least [mb] MB of disk space.

; *** "Select Additional Tasks" wizard page
WizardSelectTasks=Πρόσθετες ενέργειες
SelectTasksDesc=Ποιες πρόσθετες ενέργειες να γίνουν;
SelectTasksLabel2=Διάλεξε τι θέλεις να γίνει κατά την εγκατάσταση του [name] και πάτησε Επόμενο.

; *** "Select Start Menu Folder" wizard page
WizardSelectProgramGroup=Φάκελος στο μενού Έναρξη
SelectStartMenuFolderDesc=Πού να μπουν οι συντομεύσεις του προγράμματος;
SelectStartMenuFolderLabel3=Οι συντομεύσεις θα δημιουργηθούν στον παρακάτω φάκελο του μενού Έναρξη.
SelectStartMenuFolderBrowseLabel=Για να συνεχίσεις πάτησε Επόμενο. Για άλλο φάκελο πάτησε Αναζήτηση.
MustEnterGroupName=You must enter a folder name.
GroupNameTooLong=The folder name or path is too long.
InvalidGroupName=The folder name is not valid.
BadGroupName=The folder name cannot include any of the following characters:%n%n%1
NoProgramGroupCheck2=&Να μη δημιουργηθεί φάκελος στο μενού Έναρξη

; *** "Ready to Install" wizard page
WizardReady=Έτοιμο για εγκατάσταση
ReadyLabel1=Όλα είναι έτοιμα για την εγκατάσταση του [name] στον υπολογιστή σου.
ReadyLabel2a=Πάτησε Εγκατάσταση για να συνεχίσεις ή Πίσω για να αλλάξεις κάτι.
ReadyLabel2b=Πάτησε Εγκατάσταση για να συνεχίσεις.
ReadyMemoUserInfo=User information:
ReadyMemoDir=Φάκελος εγκατάστασης:
ReadyMemoType=Setup type:
ReadyMemoComponents=Selected components:
ReadyMemoGroup=Φάκελος μενού Έναρξη:
ReadyMemoTasks=Πρόσθετες ενέργειες:

; *** TDownloadWizardPage wizard page and DownloadTemporaryFile
DownloadingLabel=Downloading additional files...
ButtonStopDownload=&Stop download
StopDownload=Are you sure you want to stop the download?
ErrorDownloadAborted=Download aborted
ErrorDownloadFailed=Download failed: %1 %2
ErrorDownloadSizeFailed=Getting size failed: %1 %2
ErrorFileHash1=File hash failed: %1
ErrorFileHash2=Invalid file hash: expected %1, found %2
ErrorProgress=Invalid progress: %1 of %2
ErrorFileSize=Invalid file size: expected %1, found %2

; *** "Preparing to Install" wizard page
WizardPreparing=Προετοιμασία
PreparingDesc=Γίνεται προετοιμασία για την εγκατάσταση του [name].
PreviousInstallNotCompleted=The installation/removal of a previous program was not completed. You will need to restart your computer to complete that installation.%n%nAfter restarting your computer, run Setup again to complete the installation of [name].
CannotContinue=Setup cannot continue. Please click Cancel to exit.
ApplicationsFound=Οι παρακάτω εφαρμογές χρησιμοποιούν αρχεία που πρέπει να ενημερωθούν. Προτείνεται να τις κλείσει η εγκατάσταση αυτόματα.
ApplicationsFound2=Οι παρακάτω εφαρμογές χρησιμοποιούν αρχεία που πρέπει να ενημερωθούν. Προτείνεται να τις κλείσει η εγκατάσταση αυτόματα. Μετά την εγκατάσταση θα προσπαθήσει να τις ξανανοίξει.
CloseApplications=&Αυτόματο κλείσιμο των εφαρμογών
DontCloseApplications=&Να μην κλείσουν οι εφαρμογές
ErrorCloseApplications=Setup was unable to automatically close all applications. It is recommended that you close all applications using files that need to be updated by Setup before continuing.
PrepareToInstallNeedsRestart=Setup must restart your computer. After restarting your computer, run Setup again to complete the installation of [name].%n%nWould you like to restart now?

; *** "Installing" wizard page
WizardInstalling=Εγκατάσταση
InstallingLabel=Περίμενε όσο εγκαθίσταται το [name].

; *** "Setup Completed" wizard page
FinishedHeadingLabel=Ολοκληρώθηκε η εγκατάσταση του [name]
FinishedLabelNoIcons=Το [name] εγκαταστάθηκε στον υπολογιστή σου.
FinishedLabel=Το [name] εγκαταστάθηκε. Μπορείς να το ανοίξεις από τις συντομεύσεις.
ClickFinish=Πάτησε Τέλος για να κλείσει η εγκατάσταση.
FinishedRestartLabel=Για να ολοκληρωθεί η εγκατάσταση του [name], πρέπει να γίνει επανεκκίνηση. Θέλεις να γίνει τώρα;
FinishedRestartMessage=To complete the installation of [name], Setup must restart your computer.%n%nWould you like to restart now?
ShowReadmeCheck=Yes, I would like to view the README file
YesRadio=&Ναι, επανεκκίνηση τώρα
NoRadio=&Όχι, θα κάνω επανεκκίνηση αργότερα
; used for example as 'Run MyProg.exe'
RunEntryExec=Εκκίνηση %1
; used for example as 'View Readme.txt'
RunEntryShellExec=View %1

; *** "Setup Needs the Next Disk" stuff
ChangeDiskTitle=Setup Needs the Next Disk
SelectDiskLabel2=Please insert Disk %1 and click OK.%n%nIf the files on this disk can be found in a folder other than the one displayed below, enter the correct path or click Browse.
PathLabel=&Path:
FileNotInDir2=The file "%1" could not be located in "%2". Please insert the correct disk or select another folder.
SelectDirectoryLabel=Please specify the location of the next disk.

; *** Installation phase messages
SetupAborted=Η εγκατάσταση δεν ολοκληρώθηκε.%n%nΔιόρθωσε το πρόβλημα και τρέξε την ξανά.
AbortRetryIgnoreSelectAction=Select action
AbortRetryIgnoreRetry=&Try again
AbortRetryIgnoreIgnore=&Ignore the error and continue
AbortRetryIgnoreCancel=Cancel installation

; *** Installation status messages
StatusClosingApplications=Κλείσιμο εφαρμογών...
StatusCreateDirs=Δημιουργία φακέλων...
StatusExtractFiles=Αποσυμπίεση αρχείων...
StatusCreateIcons=Δημιουργία συντομεύσεων...
StatusCreateIniEntries=Creating INI entries...
StatusCreateRegistryEntries=Εγγραφές μητρώου...
StatusRegisterFiles=Registering files...
StatusSavingUninstall=Αποθήκευση στοιχείων απεγκατάστασης...
StatusRunProgram=Ολοκλήρωση εγκατάστασης...
StatusRestartingApplications=Επανεκκίνηση εφαρμογών...
StatusRollback=Ακύρωση αλλαγών...

; *** Misc. errors
ErrorInternal2=Internal error: %1
ErrorFunctionFailedNoCode=%1 failed
ErrorFunctionFailed=%1 failed; code %2
ErrorFunctionFailedWithMessage=%1 failed; code %2.%n%3
ErrorExecutingProgram=Unable to execute file:%n%1

; *** Registry errors
ErrorRegOpenKey=Error opening registry key:%n%1\%2
ErrorRegCreateKey=Error creating registry key:%n%1\%2
ErrorRegWriteKey=Error writing to registry key:%n%1\%2

; *** INI errors
ErrorIniEntry=Error creating INI entry in file "%1".

; *** File copying errors
FileAbortRetryIgnoreSkipNotRecommended=&Skip this file (not recommended)
FileAbortRetryIgnoreIgnoreNotRecommended=&Ignore the error and continue (not recommended)
SourceIsCorrupted=The source file is corrupted
SourceDoesntExist=The source file "%1" does not exist
ExistingFileReadOnly2=The existing file could not be replaced because it is marked read-only.
ExistingFileReadOnlyRetry=&Remove the read-only attribute and try again
ExistingFileReadOnlyKeepExisting=&Keep the existing file
ErrorReadingExistingDest=An error occurred while trying to read the existing file:
FileExistsSelectAction=Select action
FileExists2=The file already exists.
FileExistsOverwriteExisting=&Overwrite the existing file
FileExistsKeepExisting=&Keep the existing file
FileExistsOverwriteOrKeepAll=&Do this for the next conflicts
ExistingFileNewerSelectAction=Select action
ExistingFileNewer2=The existing file is newer than the one Setup is trying to install.
ExistingFileNewerOverwriteExisting=&Overwrite the existing file
ExistingFileNewerKeepExisting=&Keep the existing file (recommended)
ExistingFileNewerOverwriteOrKeepAll=&Do this for the next conflicts
ErrorChangingAttr=An error occurred while trying to change the attributes of the existing file:
ErrorCreatingTemp=An error occurred while trying to create a file in the destination directory:
ErrorReadingSource=An error occurred while trying to read the source file:
ErrorCopying=An error occurred while trying to copy a file:
ErrorReplacingExistingFile=An error occurred while trying to replace the existing file:
ErrorRestartReplace=RestartReplace failed:
ErrorRenamingTemp=An error occurred while trying to rename a file in the destination directory:
ErrorRegisterServer=Unable to register the DLL/OCX: %1
ErrorRegSvr32Failed=RegSvr32 failed with exit code %1
ErrorRegisterTypeLib=Unable to register the type library: %1

; *** Uninstall display name markings
; used for example as 'My Program (32-bit)'
UninstallDisplayNameMark=%1 (%2)
; used for example as 'My Program (32-bit, All users)'
UninstallDisplayNameMarks=%1 (%2, %3)
UninstallDisplayNameMark32Bit=32-bit
UninstallDisplayNameMark64Bit=64-bit
UninstallDisplayNameMarkAllUsers=All users
UninstallDisplayNameMarkCurrentUser=Current user

; *** Post-installation errors
ErrorOpeningReadme=An error occurred while trying to open the README file.
ErrorRestartingComputer=Setup was unable to restart the computer. Please do this manually.

; *** Uninstaller messages
UninstallNotFound=File "%1" does not exist. Cannot uninstall.
UninstallOpenError=File "%1" could not be opened. Cannot uninstall
UninstallUnsupportedVer=The uninstall log file "%1" is in a format not recognized by this version of the uninstaller. Cannot uninstall
UninstallUnknownEntry=An unknown entry (%1) was encountered in the uninstall log
ConfirmUninstall=Σίγουρα θέλεις να αφαιρέσεις το %1 και όλα τα μέρη του;
UninstallOnlyOnWin64=This installation can only be uninstalled on 64-bit Windows.
OnlyAdminCanUninstall=This installation can only be uninstalled by a user with administrative privileges.
UninstallStatusLabel=Περίμενε όσο αφαιρείται το %1 από τον υπολογιστή σου.
UninstalledAll=Το %1 αφαιρέθηκε από τον υπολογιστή σου.
UninstalledMost=Η απεγκατάσταση του %1 ολοκληρώθηκε.%n%nΜερικά στοιχεία δεν αφαιρέθηκαν και μπορείς να τα σβήσεις εσύ.
UninstalledAndNeedsRestart=To complete the uninstallation of %1, your computer must be restarted.%n%nWould you like to restart now?
UninstallDataCorrupted="%1" file is corrupted. Cannot uninstall

; *** Uninstallation phase messages
ConfirmDeleteSharedFileTitle=Remove Shared File?
ConfirmDeleteSharedFile2=The system indicates that the following shared file is no longer in use by any programs. Would you like for Uninstall to remove this shared file?%n%nIf any programs are still using this file and it is removed, those programs may not function properly. If you are unsure, choose No. Leaving the file on your system will not cause any harm.
SharedFileNameLabel=File name:
SharedFileLocationLabel=Location:
WizardUninstalling=Κατάσταση απεγκατάστασης
StatusUninstalling=Αφαίρεση του %1...

; *** Shutdown block reasons
ShutdownBlockReasonInstallingApp=Installing %1.
ShutdownBlockReasonUninstallingApp=Uninstalling %1.

; The custom messages below aren't used by Setup itself, but if you make
; use of them in your scripts, you'll want to translate them.

[CustomMessages]

NameAndVersion=%1 version %2
AdditionalIcons=Additional shortcuts:
CreateDesktopIcon=Create a &desktop shortcut
CreateQuickLaunchIcon=Create a &Quick Launch shortcut
ProgramOnTheWeb=%1 on the Web
UninstallProgram=Uninstall %1
LaunchProgram=Launch %1
AssocFileExtension=&Associate %1 with the %2 file extension
AssocingFileExtension=Associating %1 with the %2 file extension...
AutoStartProgramGroupDescription=Startup:
AutoStartProgram=Automatically start %1
AddonHostProgramNotFound=%1 could not be located in the folder you selected.%n%nDo you want to continue anyway?
