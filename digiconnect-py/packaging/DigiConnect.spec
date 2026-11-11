# PyInstaller spec: python -m PyInstaller packaging/DigiConnect.spec
import sys
block_cipher = None
a = Analysis(['../run.py'], pathex=['..'], datas=[('../assets', 'assets'), ('../LICENSES', 'LICENSES')],
             hiddenimports=['sounddevice', 'numpy'], excludes=['PyQt6', 'tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DigiConnect', console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name='DigiConnect')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='DigiConnect.app', bundle_identifier='org.hellaszone.digiconnect',
                 info_plist={'NSMicrophoneUsageDescription': 'DigiConnect uses the microphone to transmit your voice.',
                             'NSHighResolutionCapable': True})
