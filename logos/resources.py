"""
Localisation des fichiers embarqués (`logos/assets/`) et du dossier utilisateur.

Trois emplacements, dans cet ordre de priorité :

1. `~/.bda/assets/<nom>` — dépôt de l'opérateur, s'il existe. C'est le
   mécanisme de **mise à jour du contenu** : remplacer un corpus (prédications,
   Bible) ou le logo ne demande ni réinstallation ni accès réseau, seulement de
   déposer le fichier ici. Il est repris au lancement suivant, l'empreinte
   SHA-256 stockée en base déclenchant automatiquement le réimport.
2. `sys._MEIPASS/logos/assets/` — assets extraits quand l'appli est gelée par
   PyInstaller.
3. `logos/assets/` — exécution depuis le dépôt.

Ce module est le **seul** à connaître ces emplacements ; ailleurs, on passe par
`asset_path()`. Aucune dépendance Qt : la couche `logos/data/` peut l'importer.
"""
import sys
from pathlib import Path

# Dossier de données de l'utilisateur (base SQLite, assets déposés à la main).
USER_DIR = Path.home() / ".bda"
USER_ASSETS_DIR = USER_DIR / "assets"

# Racine des assets livrés : dossier extrait par PyInstaller si l'appli est
# gelée, sinon le dossier `assets/` du dépôt.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLED_ASSETS_DIR = Path(sys._MEIPASS) / "logos" / "assets"
else:
    BUNDLED_ASSETS_DIR = Path(__file__).parent / "assets"


def ensure_user_dirs():
    """Crée `~/.bda/assets/` au lancement : sans ça, l'opérateur devrait deviner
    le nom du dossier où déposer un corpus à jour."""
    USER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def bundled_asset_path(name: str) -> Path:
    """Chemin de l'asset **livré avec l'application**, en ignorant tout dépôt
    de l'opérateur — utilisé comme repli si le fichier déposé est illisible."""
    return BUNDLED_ASSETS_DIR / name


def asset_path(name: str) -> Path:
    """Chemin du fichier à utiliser pour `name`, ex. `asset_path("logo.png")` :
    la version déposée dans `~/.bda/assets/` si elle existe, sinon celle livrée
    avec l'application."""
    override = USER_ASSETS_DIR / name
    if override.is_file():
        return override
    return bundled_asset_path(name)
