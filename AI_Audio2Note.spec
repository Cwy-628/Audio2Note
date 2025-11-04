# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['start_native.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['ai_audio2note.backend.services.audio_downloader', 'ai_audio2note.backend.services.process_service'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI_Audio2Note',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI_Audio2Note',
)
app = BUNDLE(
    coll,
    name='AI_Audio2Note.app',
    icon=None,
    bundle_identifier=None,
)
