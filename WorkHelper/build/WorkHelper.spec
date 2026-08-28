# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

spec_dir = Path(SPECPATH)
project_root = spec_dir.parent

block_cipher = None

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[],
    binaries=[],
    datas=[
        (str(project_root / 'assets'), 'assets'),
        # 사용자 데이터(data/)는 번들하지 않는다 — 초기 샘플은 seed/에서 복사된다.
        (str(project_root / 'seed'), 'seed'),
        (str(project_root / 'version.txt'), '.'),
        (str(project_root / 'icon2.png'), '.'),
    ],
    hiddenimports=[
        'comtypes', 'comtypes.client', 'comtypes.gen', 'comtypes.stream',
        # Windows 내장 OCR (winrt 바인딩은 동적 임포트라 명시가 필요하다)
        'winrt.runtime',
        'winrt.system',
        'winrt.windows.foundation',
        'winrt.windows.foundation.collections',
        'winrt.windows.globalization',
        'winrt.windows.graphics.imaging',
        'winrt.windows.media.ocr',
        'winrt.windows.storage.streams',
        'winrt._winrt',
        'winrt._winrt_windows_foundation',
        'winrt._winrt_windows_foundation_collections',
        'winrt._winrt_windows_globalization',
        'winrt._winrt_windows_graphics_imaging',
        'winrt._winrt_windows_media_ocr',
        'winrt._winrt_windows_storage_streams',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='6PM Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'icons' / 'app.ico'),
)
