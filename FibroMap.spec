# -*- mode: python ; coding: utf-8 -*-
# FibroMap.spec — Configuration PyInstaller pour FibroMap

block_cipher = None

# Chemin local vers les binaires Poppler (relatif à ce .spec)
POPPLER_BIN  = 'poppler/poppler-25.12.0/Library/bin'
POPPLER_SHARE = 'poppler/poppler-25.12.0/Library/share'

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        # Embarque tous les .exe et .dll de Poppler dans poppler/bin/
        (POPPLER_BIN + '/*.exe', 'poppler/bin'),
        (POPPLER_BIN + '/*.dll', 'poppler/bin'),
    ],
    datas=[
        # Données Poppler (encodages, polices, etc.)
        (POPPLER_SHARE, 'poppler/share'),
    ],
    hiddenimports=[
        'openpyxl',
        'openpyxl.cell._writer',
        'openpyxl.styles.stylesheet',
        'reportlab',
        'reportlab.pdfbase.pdfdoc',
        'reportlab.pdfbase._fontdata',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.lib.pagesizes',
        'PIL',
        'PIL.Image',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        'pdf2image',
        'pdf2image.pdf2image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
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
    [],
    exclude_binaries=True,
    name='FibroMap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX désactivé : évite les faux positifs antivirus
    console=False,       # Pas de fenêtre console noire
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # Remplace None par 'fibromap.ico' si tu as une icône
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FibroMap',
)
