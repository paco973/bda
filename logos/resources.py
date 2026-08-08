"""
Localisation des fichiers embarqués (`logos/assets/`).

En exécution normale, les assets sont à côté du package. Une fois l'application
gelée par PyInstaller, ils sont extraits dans un dossier temporaire dont le
chemin est exposé par `sys._MEIPASS` : ce module est le **seul** endroit qui
connaît cette différence, les autres modules passent par `asset_path()`.

Aucune dépendance Qt ici : la couche `logos/data/` peut l'importer librement.
"""
import sys
from pathlib import Path

# Racine des assets : dossier extrait par PyInstaller si l'appli est gelée,
# sinon le dossier `assets/` du dépôt.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ASSETS_DIR = Path(sys._MEIPASS) / "logos" / "assets"
else:
    ASSETS_DIR = Path(__file__).parent / "assets"


def asset_path(name: str) -> Path:
    """Chemin d'un fichier embarqué, ex. `asset_path("logo.png")`."""
    return ASSETS_DIR / name
