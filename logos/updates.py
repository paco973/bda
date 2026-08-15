"""
Vérification (optionnelle) de l'existence d'une nouvelle version de BDA.

C'est le **seul** module qui accède au réseau, et l'application reste utilisable
sans lui : la vérification est facultative, se fait en tâche de fond, échoue en
silence et ne télécharge ni n'installe jamais rien — elle se contente de dire
qu'une version plus récente existe, l'opérateur restant maître du remplacement.

Manifeste attendu à `MANIFEST_URL` (JSON, servi en HTTPS) :

    {"version": "1.1.0",
     "url": "https://example.org/telecharger/BDA-1.1.0.zip",
     "notes": "Corrections d'affichage."}

Le contenu récupéré est **non fiable** par nature : le schéma HTTPS est imposé
(manifeste et lien de téléchargement), la taille de la réponse est bornée, et
les champs texte sont tronqués. Ils ne sont jamais interprétés comme du HTML
côté interface (cf. `logos/ui/update_banner.py`).

Aucune dépendance Qt ici, pour que la logique reste testable telle quelle.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from logos.version import __version__

# URL du manifeste de version. **Vide par défaut** : tant qu'elle n'est pas
# renseignée, la fonctionnalité reste dormante (aucun accès réseau, et le menu
# « Rechercher les mises à jour » le dit clairement). À remplir par le
# mainteneur quand un emplacement de publication existe — par exemple
# https://raw.githubusercontent.com/<compte>/<depot>/main/latest.json
MANIFEST_URL = "https://github.com/paco973/bda/releases/latest/download/latest.json"

TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 64 * 1024
MAX_NOTES_CHARS = 500

# Issues possibles d'une vérification.
DISABLED = "disabled"              # aucune URL configurée : rien n'a été tenté
ERROR = "error"                    # réseau injoignable ou réponse illisible
NOT_PUBLISHED = "not_published"    # serveur joignable, mais rien à cette adresse
UP_TO_DATE = "up_to_date"          # cette version est la plus récente publiée
AVAILABLE = "available"            # une version plus récente existe


class _NotFound(Exception):
    """Le serveur a répondu 404 : aucune version publiée, ou adresse erronée.
    C'est un cas distinct d'une panne réseau — il mérite son propre message."""


@dataclass(frozen=True)
class Release:
    """Une version publiée : son numéro, son lien de téléchargement, ses notes."""
    version: str
    url: str
    notes: str = ""


@dataclass(frozen=True)
class CheckResult:
    """Issue d'une vérification (`release` n'est rempli que pour AVAILABLE)."""
    status: str
    release: Release | None = None


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
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
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


def check_for_update(manifest_url=None, current_version=__version__) -> CheckResult:
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
    return CheckResult(AVAILABLE, Release(version, download_url, notes))
