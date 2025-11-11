# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['random_av_stitcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pydub',
        'tkinter',
        'urllib.request',
        'zipfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'numpy',
        'PIL',
        'matplotlib',
        'scipy',
        'pandas',
        'tensorflow',
        'tensorboard',
        'setuptools',
    ],
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
    name='随机音视频拼接工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='随机音视频拼接工具.app',
    icon='icons/icon.icns',
    bundle_identifier='com.zzf.random-av-stitcher',
    info_plist={
        'CFBundleName': '随机音视频拼接工具',
        'CFBundleDisplayName': '随机音视频拼接工具',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': 'True',
    },
)
