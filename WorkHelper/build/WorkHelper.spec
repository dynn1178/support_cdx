# -*- mode: python ; coding: utf-8 -*-
# updater.exe를 먼저 빌드한 뒤 이 spec을 실행해야 합니다.
# build_release.ps1이 순서를 자동으로 처리합니다.

import os
from pathlib import Path

spec_dir = Path(SPECPATH)
project_root = spec_dir.parent
updater_exe = spec_dir / "_updater_dist" / "updater.exe"

if not updater_exe.exists():
    raise FileNotFoundError(
        f"updater.exe를 찾을 수 없습니다: {updater_exe}\n"
        "build_release.ps1을 통해 빌드하거나, updater.py를 먼저 빌드하세요."
    )

block_cipher = None

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[],
    binaries=[],
    datas=[
        (str(project_root / 'assets'), 'assets'),
        (str(project_root / 'data'), 'data'),
        (str(project_root / 'version.txt'), '.'),
        (str(project_root / 'icon2.png'), '.'),
        (str(updater_exe), '.'),          # updater.exe 번들 포함
    ],
    hiddenimports=[],
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
