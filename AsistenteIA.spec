# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('data', 'data')],
    datas=[],
    hiddenimports=['selenium', 'webdriver_manager', 'cryptography', 'numpy', 'pandas', 'scikit-learn', 'pyttsx3', 'SpeechRecognition', 'dotenv', 'openai', 'keyboard', 'imap_tools'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'jupyter', 'tkinter', 'qt5', 'sqlite3'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AsistenteIA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    uac_admin=True,
    icon=['assets\\icon.ico'],
)
