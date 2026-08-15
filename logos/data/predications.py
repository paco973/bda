"""
Accès aux prédications importées (paragraphes numérotés).

Les prédications sont livrées dans un fichier compressé sous `logos/assets/`
(généré une fois par le script `scripts/scrape_predications.py`) et importées
dans SQLite au premier lancement — l'application reste 100 % hors ligne.

Le corpus se met à jour sans réinstaller : déposer un nouveau
`predications.json.gz` dans `~/.bda/assets/` (voir `logos.resources`) suffit,
le changement d'empreinte déclenchant le réimport au lancement suivant.

`letter` (1re lettre) et `prefix` (2 premières lettres) sont dérivés du titre
français à l'import : le titre est « désaccentué » pour un regroupement A-Z
simple (« Élie » -> lettre E, préfixe « El »).
"""
import gzip
import hashlib
import json
import sys

from logos.data.database import get_connection, get_meta, set_meta
from logos.data.textutils import strip_accents
from logos.resources import asset_path, bundled_asset_path

ASSET_NAME = "predications.json.gz"
PREDICATIONS_ASSET = asset_path(ASSET_NAME)
SOURCE = "branham.fr"


def title_letter(title_fr: str) -> str:
    """1re lettre de classement (A-Z, sans accent) ou « # » si non alphabétique."""
    for char in strip_accents(title_fr):
        if char.isalpha():
            return char.upper()
    return "#"


def title_prefix(title_fr: str) -> str:
    """Préfixe de classement : 2 premières lettres, ex. « Ab », « El »."""
    letters = [c for c in strip_accents(title_fr) if c.isalpha()]
    prefix = "".join(letters[:2])
    return prefix[:1].upper() + prefix[1:].lower()


# --------------------------------------------------------------------------- #
#  Import
# --------------------------------------------------------------------------- #
def is_available() -> bool:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM predications").fetchone()[0]
    conn.close()
    return count > 0


_ASSET_META_KEY = "predications_asset_sha256"


def _asset_fingerprint(asset) -> str:
    return hashlib.sha256(asset.read_bytes()).hexdigest()


def _candidate_assets():
    """Fichiers à essayer, du plus prioritaire au repli : le corpus retenu par
    `logos.resources` (dépôt de l'opérateur s'il existe) puis, si celui-ci est
    illisible, celui livré avec l'application."""
    paths, seen = [], set()
    for path in (PREDICATIONS_ASSET, bundled_asset_path(ASSET_NAME)):
        if path not in seen and path.exists():
            seen.add(path)
            paths.append(path)
    return paths


def _import_asset(asset):
    """Importe `asset`, sauf si son empreinte est déjà celle en base."""
    fingerprint = _asset_fingerprint(asset)
    if is_available() and get_meta(_ASSET_META_KEY) == fingerprint:
        return
    with gzip.open(asset, "rt", encoding="utf-8") as f:
        import_data(json.load(f))
    set_meta(_ASSET_META_KEY, fingerprint)


def ensure_imported():
    """Importe les prédications si absentes de la base **ou** si l'asset a
    changé depuis le dernier import (empreinte stockée dans `meta`) : déposer
    un corpus à jour dans `~/.bda/assets/` suffit donc à le mettre à jour.

    Un fichier déposé illisible ne doit pas empêcher l'application de démarrer :
    on signale le problème et on retombe sur le corpus livré."""
    for asset in _candidate_assets():
        try:
            _import_asset(asset)
            return
        except (OSError, ValueError) as exc:
            print(
                f"BDA : prédications illisibles dans {asset} ({exc}) — "
                "repli sur le corpus livré avec l'application.",
                file=sys.stderr,
            )


def import_data(data: dict):
    """Remplit les tables depuis {predications: [{date_code, title_fr, title_en,
    paragraphs: [texte, ...]}]}. Le n° de paragraphe = position (1-based)."""
    conn = get_connection()
    conn.execute("DELETE FROM predication_paragraphs")
    conn.execute("DELETE FROM predications")
    for pred in data["predications"]:
        title_fr = pred["title_fr"]
        cur = conn.execute(
            """
            INSERT INTO predications (date_code, title_fr, title_en, letter, prefix)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                pred.get("date_code", ""),
                title_fr,
                pred.get("title_en", ""),
                title_letter(title_fr),
                title_prefix(title_fr),
            ),
        )
        pred_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO predication_paragraphs (predication_id, number, text) VALUES (?, ?, ?)",
            (
                (pred_id, i + 1, text.strip())
                for i, text in enumerate(pred["paragraphs"])
            ),
        )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
#  Requêtes
# --------------------------------------------------------------------------- #
def total_count() -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM predications").fetchone()[0]
    conn.close()
    return count


def letters_with_counts():
    """[(lettre, nombre)] pour toutes les lettres A-Z, 0 compris (ordre A-Z)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT letter, COUNT(*) AS n FROM predications GROUP BY letter"
    ).fetchall()
    conn.close()
    counts = {row["letter"]: row["n"] for row in rows}
    return [(chr(c), counts.get(chr(c), 0)) for c in range(ord("A"), ord("Z") + 1)]


def prefixes_with_counts(letter: str):
    """[(préfixe, nombre)] des préfixes 2-lettres d'une lettre donnée (ordre alpha)."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT prefix, COUNT(*) AS n FROM predications
        WHERE letter = ?
        GROUP BY prefix ORDER BY prefix
        """,
        (letter,),
    ).fetchall()
    conn.close()
    return [(row["prefix"], row["n"]) for row in rows]


def list_by_prefix(prefix: str):
    """Prédications d'un préfixe (id, date_code, title_fr, title_en), triées par titre."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, date_code, title_fr, title_en FROM predications
        WHERE prefix = ?
        ORDER BY title_fr, date_code
        """,
        (prefix,),
    ).fetchall()
    conn.close()
    return rows


def search(query: str, limit: int = 200):
    """Recherche par titre FR/EN ou code date (id, date_code, title_fr, title_en)."""
    conn = get_connection()
    like = f"%{query}%"
    rows = conn.execute(
        """
        SELECT id, date_code, title_fr, title_en FROM predications
        WHERE title_fr LIKE ? OR title_en LIKE ? OR date_code LIKE ?
        ORDER BY title_fr, date_code
        LIMIT ?
        """,
        (like, like, like, limit),
    ).fetchall()
    conn.close()
    return rows


def paragraph_count(predication_id: int) -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM predication_paragraphs WHERE predication_id = ?",
        (predication_id,),
    ).fetchone()[0]
    conn.close()
    return count


def get_paragraphs(predication_id: int):
    """Tous les paragraphes (number, text) d'une prédication, dans l'ordre."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT number, text FROM predication_paragraphs
        WHERE predication_id = ?
        ORDER BY number
        """,
        (predication_id,),
    ).fetchall()
    conn.close()
    return rows
