# -*- mode: python ; coding: utf-8 -*-
"""
Recette PyInstaller de BDA (à lancer depuis la racine du dépôt) :

    pyinstaller packaging/bda.spec

Produit un dossier `dist/BDA/` (Windows/Linux) et, sur macOS, `dist/BDA.app`.
Le mode « un dossier » est volontaire : plus rapide à démarrer qu'un fichier
unique et plus simple à dépanner (les assets restent visibles).

Les assets embarqués (`logos/assets/`) sont copiés en conservant l'arborescence
attendue par `logos/resources.py`.
"""
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICONS = Path(SPECPATH) / "icons"

# Bible + logo (+ prédications si l'asset est présent : il n'est pas versionné).
# La destination doit rester `logos/assets` : c'est là que `logos/resources.py`
# va chercher les fichiers une fois l'application gelée.
datas = [(str(ROOT / "logos" / "assets"), "logos/assets")]

# Modules tirés par les dépendances mais inutiles ici : on allège le paquet.
excludes = [
    "tkinter", "unittest", "pydoc", "pytest", "setuptools", "pip",
    "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BDA",
    debug=False,
    strip=False,
    upx=False,
    console=False,           # pas de console : l'appli est purement graphique
    icon=str(ICONS / "bda.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BDA",
)

# macOS : enveloppe le tout dans un vrai bundle .app (double-cliquable).
app = BUNDLE(
    coll,
    name="BDA.app",
    icon=str(ICONS / "bda.icns"),
    bundle_identifier="fr.logostabernacle.bda",
    info_plist={
        "CFBundleName": "BDA",
        "CFBundleDisplayName": "BDA",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
    },
)
