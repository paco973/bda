"""
Vérification (optionnelle) de l'existence d'une nouvelle version de BDA, et
téléchargement **vérifié** de l'archive correspondante.

Avec `logos/data/scrape.py`, c'est l'un des deux seuls modules qui accèdent
au réseau, et l'application reste utilisable sans lui : la vérification est
facultative, se fait en tâche de fond et échoue en silence. Le téléchargement
n'a lieu que sur un clic explicite de l'opérateur ; l'installation proprement
dite (échange des dossiers, redémarrage) vit dans `logos/selfupdate.py`.

Manifeste attendu à `MANIFEST_URL` (JSON, servi en HTTPS) :

    {"version": "1.1.0",
     "url": "https://github.com/<compte>/<depot>/releases/latest",
     "notes": "Corrections d'affichage.",
     "assets": {
       "macos":   {"url": "https://…/BDA-1.1.0-macos.zip",
                   "sha256": "…", "size": 39378728},
       "windows": {"url": "https://…/BDA-1.1.0-windows.zip",
                   "sha256": "…", "size": 41234567}}}

`url` reste la page de téléchargement (repli pour le navigateur) ; `assets`
porte, par plateforme, l'archive que l'application peut installer elle-même.
Un manifeste sans `assets` (ancien format) reste valide : le bandeau propose
alors seulement d'ouvrir la page.

Le contenu récupéré est **non fiable** par nature : le schéma HTTPS est imposé
(manifeste et liens), la taille des réponses est bornée, les champs texte sont
tronqués, et une archive n'est acceptée que si sa taille **et** son empreinte
SHA-256 sont exactement celles annoncées. Sans signature de code, ce couple
HTTPS + empreinte est la seule garantie d'intégrité : il n'est pas négociable.
Les textes ne sont jamais interprétés comme du HTML côté interface
(cf. `logos/ui/update_banner.py`).

Aucune dépendance Qt ici, pour que la logique reste testable telle quelle.
"""
import hashlib
import json
import platform
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from logos.tls import ssl_context
from logos.version import __version__

# URL du manifeste de version. Vide → fonctionnalité dormante (aucun accès
# réseau, et le menu « Rechercher les mises à jour » le dit clairement).
# L'adresse `releases/latest/download/<fichier>` de GitHub suit toujours la
# dernière release : aucun hébergement à part.
MANIFEST_URL = "https://github.com/paco973/bda/releases/latest/download/latest.json"

TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 64 * 1024
MAX_NOTES_CHARS = 500

# Téléchargement d'une archive : lecture par blocs, avec un délai plus large
# que pour le manifeste (une connexion lente entre deux blocs n'est pas une
# panne) et une taille plafond au-delà de laquelle ce n'est pas notre archive.
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_CHUNK_BYTES = 256 * 1024
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024

# Issues possibles d'une vérification.
DISABLED = "disabled"              # aucune URL configurée : rien n'a été tenté
ERROR = "error"                    # réseau injoignable ou réponse illisible
NOT_PUBLISHED = "not_published"    # serveur joignable, mais rien à cette adresse
UP_TO_DATE = "up_to_date"          # cette version est la plus récente publiée
AVAILABLE = "available"            # une version plus récente existe


class _NotFound(Exception):
    """Le serveur a répondu 404 : aucune version publiée, ou adresse erronée.
    C'est un cas distinct d'une panne réseau — il mérite son propre message."""


class DownloadError(Exception):
    """Téléchargement impossible ou archive non conforme : le message est
    destiné à l'opérateur (français, sans détail technique inutile)."""


@dataclass(frozen=True)
class Asset:
    """Archive installable pour une plateforme : lien, empreinte, taille."""
    url: str
    sha256: str
    size: int

    @property
    def filename(self) -> str:
        name = Path(urlparse(self.url).path).name
        return name if name.endswith(".zip") else "BDA-update.zip"


@dataclass(frozen=True)
class Release:
    """Une version publiée : son numéro, sa page de téléchargement, ses notes,
    et l'archive de **cette** plateforme si le manifeste en annonce une."""
    version: str
    url: str
    notes: str = ""
    asset: Asset | None = None


@dataclass(frozen=True)
class CheckResult:
    """Issue d'une vérification (`release` n'est rempli que pour AVAILABLE)."""
    status: str
    release: Release | None = None


def platform_tag(system=None) -> str:
    """Clé de plateforme du manifeste — même convention que `packaging/package.py`
    pour nommer les archives (`BDA-<version>-<plateforme>.zip`)."""
    system = platform.system() if system is None else system
    return {"Darwin": "macos", "Windows": "windows"}.get(system, "linux")


def parse_version(text) -> tuple:
    """« 1.2.0 » -> (1, 2, 0). S'arrête au premier champ non numérique, ce qui
    donne un tuple vide pour une chaîne inexploitable (donc jamais « plus
    récente », cf. `is_newer`)."""
    parts = []
    for chunk in str(text).strip().lstrip("vV").split("."):
        digits = ""
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_newer(candidate, current) -> bool:
    """Vrai si `candidate` est strictement postérieure à `current`. Les tuples
    sont complétés par des zéros pour comparer « 1.2 » et « 1.2.0 » à égalité."""
    new, old = parse_version(candidate), parse_version(current)
    if not new:
        return False
    length = max(len(new), len(old))
    new += (0,) * (length - len(new))
    old += (0,) * (length - len(old))
    return new > old


def _is_https(url) -> bool:
    """N'accepter que HTTPS : ni http en clair, ni file://, ni schéma exotique
    que l'on ouvrirait ensuite dans le navigateur de l'opérateur."""
    try:
        return urlparse(str(url)).scheme == "https"
    except ValueError:
        return False


def is_configured(manifest_url=None) -> bool:
    """Vrai si une URL de manifeste exploitable est configurée."""
    return _is_https(MANIFEST_URL if manifest_url is None else manifest_url)


def _fetch(url):
    """Le manifeste décodé, ou None si la réponse est inutilisable.

    Lève `_NotFound` sur un 404, seul cas où l'on sait que le serveur va bien
    et que c'est le manifeste qui manque (release pas encore publiée)."""
    try:
        with urllib.request.urlopen(
            url, timeout=TIMEOUT_SECONDS, context=ssl_context()
        ) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:  # sous-classe d'URLError : à tester avant
        if exc.code == 404:
            raise _NotFound from exc
        return None
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if len(raw) > MAX_RESPONSE_BYTES:
        return None  # réponse anormalement grosse : ce n'est pas notre manifeste
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_asset(entry) -> Asset | None:
    """L'archive annoncée pour une plateforme, ou None si l'entrée est
    inexploitable — un manifeste mal formé dégrade vers « ouvrir la page »,
    il ne bloque pas la simple annonce de la version."""
    if not isinstance(entry, dict):
        return None
    url = str(entry.get("url", "")).strip()
    sha256 = str(entry.get("sha256", "")).strip().lower()
    size = entry.get("size")
    if not _is_https(url):
        return None
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        return None
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_ARCHIVE_BYTES:
        return None
    return Asset(url, sha256, size)


def check_for_update(manifest_url=None, current_version=__version__, system=None) -> CheckResult:
    """Interroge le manifeste et compare à la version courante.

    Ne lève jamais : toute anomalie (réseau, JSON, champs manquants ou lien non
    HTTPS) donne ERROR, pour que l'appel puisse être lancé au démarrage sans
    risquer d'empêcher l'application de s'ouvrir."""
    url = MANIFEST_URL if manifest_url is None else manifest_url
    if not _is_https(url):
        return CheckResult(DISABLED)
    try:
        payload = _fetch(url)
    except _NotFound:
        return CheckResult(NOT_PUBLISHED)
    if payload is None:
        return CheckResult(ERROR)

    version = str(payload.get("version", "")).strip()[:20]
    download_url = str(payload.get("url", "")).strip()
    notes = str(payload.get("notes", "")).strip()[:MAX_NOTES_CHARS]
    if not parse_version(version):
        return CheckResult(ERROR)
    if not is_newer(version, current_version):
        return CheckResult(UP_TO_DATE)
    if not _is_https(download_url):
        return CheckResult(ERROR)  # version annoncée, mais lien inutilisable
    assets = payload.get("assets")
    asset = _parse_asset(assets.get(platform_tag(system))) if isinstance(assets, dict) else None
    return CheckResult(AVAILABLE, Release(version, download_url, notes, asset))


def download_asset(asset: Asset, dest_dir, on_progress=None, should_stop=None) -> Path | None:
    """Télécharge l'archive dans `dest_dir` et ne la conserve que si sa taille
    et son empreinte SHA-256 sont celles annoncées.

    Renvoie le chemin de l'archive, ou None si `should_stop()` a demandé
    l'arrêt ; lève `DownloadError` sinon. `on_progress(received, total)` est
    appelé à chaque bloc. Le fichier s'écrit sous un nom temporaire (`.part`)
    et n'est renommé qu'une fois vérifié : une archive présente sur le disque
    est donc toujours une archive conforme."""
    if not _is_https(asset.url):
        raise DownloadError("le lien de téléchargement n'est pas en HTTPS")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / asset.filename
    partial = target.with_name(target.name + ".part")
    target.unlink(missing_ok=True)

    digest = hashlib.sha256()
    received = 0
    cancelled = False
    # Le fichier partiel n'est supprimé qu'une fois **refermé** : sous Windows,
    # supprimer un fichier encore ouvert échoue (« utilisé par un autre
    # processus »), et l'annulation se transformait en erreur.
    try:
        with urllib.request.urlopen(
            asset.url, timeout=DOWNLOAD_TIMEOUT_SECONDS, context=ssl_context()
        ) as response, open(partial, "wb") as out:
            while True:
                if should_stop is not None and should_stop():
                    cancelled = True
                    break
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                received += len(chunk)
                if received > asset.size:
                    raise DownloadError("l'archive reçue est plus grosse qu'annoncé")
                digest.update(chunk)
                out.write(chunk)
                if on_progress is not None:
                    on_progress(received, asset.size)
    except DownloadError:
        partial.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        partial.unlink(missing_ok=True)
        raise DownloadError(f"téléchargement interrompu ({exc})") from exc

    if cancelled:
        partial.unlink(missing_ok=True)
        return None
    if received != asset.size:
        partial.unlink(missing_ok=True)
        raise DownloadError("l'archive reçue est incomplète")
    if digest.hexdigest() != asset.sha256:
        partial.unlink(missing_ok=True)
        raise DownloadError(
            "l'empreinte de l'archive ne correspond pas à celle annoncée : "
            "fichier corrompu ou altéré, il a été supprimé"
        )
    partial.replace(target)
    return target
