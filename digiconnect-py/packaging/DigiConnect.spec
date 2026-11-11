# PyInstaller spec: python -m PyInstaller packaging/DigiConnect.spec
import sys
block_cipher = None
a = Analysis(['../run.py'], pathex=['..'], datas=[('../assets', 'assets'), ('../LICENSES', 'LICENSES')],
             hiddenimports=['sounddevice', 'numpy', 'certifi', 'bootstrap', 'xml.etree.ElementTree', 'sqlite3', 'csv', 'zipfile', 'gzip', 'base64', 'hashlib', 'ssl', 'http.server', 'http.client', 'email', 'html', 'difflib', 'decimal', 'statistics', 'zoneinfo', 'uuid', 'platform', 'shutil', 'tempfile', 'struct', 'math', 'random', 'secrets', 'textwrap', 'unicodedata', 'ipaddress', 'socket', 'collections', 'itertools', 'functools', 'dataclasses', 'enum', 'typing'], excludes=['PyQt6', 'tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DigiConnect', console=False, icon='../assets/DigiConnect.ico' if sys.platform == 'win32' else None)
coll = COLLECT(exe, a.binaries, a.datas, name='DigiConnect')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='DigiConnect.app', icon='../assets/DigiConnect.icns', bundle_identifier='org.hellaszone.digiconnect',
                 info_plist={'NSMicrophoneUsageDescription': 'DigiConnect uses the microphone to transmit your voice.',
                             'NSHighResolutionCapable': True})
