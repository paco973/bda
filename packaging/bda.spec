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
import os
import re
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICONS = Path(SPECPATH) / "icons"

# Version lue dans `logos/version.py` (source unique) : on la relit par regex
# plutôt que d'importer le paquet, pour ne rien exécuter au moment du build.
VERSION = re.search(
    r'__version__\s*=\s*"([^"]+)"',
    (ROOT / "logos" / "version.py").read_text(encoding="utf-8"),
).group(1)

# Assets embarqués. La destination doit rester `logos/assets` : c'est là que
# `logos/resources.py` va chercher les fichiers une fois l'application gelée.
#
# Le corpus de prédications est sous copyright (branham.fr / VGR) : il n'est
# embarqué **que sur demande explicite**, pour qu'un paquet destiné à une
# diffusion publique ne le contienne jamais par inadvertance. Pour un build
# interne à l'église, exporter BDA_BUNDLE_PREDICATIONS=1 avant de lancer
# pyinstaller. Sans lui, l'appli démarre et le mode Prédications affiche
# « non disponible » — le corpus peut être déposé ensuite dans ~/.bda/assets/.
BUNDLE_PREDICATIONS = os.environ.get("BDA_BUNDLE_PREDICATIONS") == "1"
RESTRICTED_ASSETS = {"predications.json.gz"}

datas = []
for asset in sorted((ROOT / "logos" / "assets").iterdir()):
    if not asset.is_file():
        continue
    if asset.name in RESTRICTED_ASSETS and not BUNDLE_PREDICATIONS:
        print(f"bda.spec : {asset.name} exclu du paquet (copyright) — "
              "BDA_BUNDLE_PREDICATIONS=1 pour l'inclure.")
        continue
    datas.append((str(asset), "logos/assets"))

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
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
    },
)
