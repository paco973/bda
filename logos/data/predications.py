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
import re
import sqlite3
import sys

from logos import resources
from logos.data.database import (
    get_connection,
    get_meta,
    has_paragraph_search,
    set_meta,
)
from logos.data.textutils import search_key, strip_accents
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


def save_user_corpus(data: dict):
    """Écrit un corpus (téléchargé depuis l'application) dans le dépôt de
    l'opérateur (`~/.bda/assets/`) puis l'importe immédiatement. Le fichier
    déposé étant prioritaire sur l'asset livré, il survivra aux mises à jour
    de l'application. Retourne le chemin écrit."""
    resources.ensure_user_dirs()
    target = resources.USER_ASSETS_DIR / ASSET_NAME
    with gzip.open(target, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    _import_asset(target)
    return target


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
    # Les rowid ont changé (DELETE + INSERT) : l'index externe doit suivre.
    rebuild_search_index()


# --------------------------------------------------------------------------- #
#  Recherche plein texte dans les paragraphes
# --------------------------------------------------------------------------- #
# Nombre de paragraphes présents dans l'index, retenu dans `meta`. Un index à
# contenu externe ne peut pas être interrogé sur son propre remplissage (lire
# ses colonnes ou ses rowid renvoie ceux de la table source, même s'il est vide) :
# ce compteur est la seule façon fiable de savoir s'il est à jour.
_INDEX_ROWS_KEY = "paragraph_index_rows"


def _paragraph_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM predication_paragraphs").fetchone()[0]


def rebuild_search_index():
    """(Re)construit l'index plein texte des paragraphes (~3 s sur le corpus
    complet). L'index est *externe* : il pointe vers les `rowid` de
    `predication_paragraphs`, qu'un import renumérote entièrement."""
    if not has_paragraph_search():
        return
    conn = get_connection()
    try:
        conn.execute("INSERT INTO paragraph_search(paragraph_search) VALUES('delete-all')")
        conn.execute(
            "INSERT INTO paragraph_search(rowid, text) SELECT rowid, text"
            " FROM predication_paragraphs"
        )
        conn.commit()
        total = _paragraph_count(conn)
    except sqlite3.OperationalError as exc:
        print(f"BDA : index plein texte non reconstruit ({exc}).", file=sys.stderr)
        return
    finally:
        conn.close()
    set_meta(_INDEX_ROWS_KEY, str(total))


def _search_index_ready() -> bool:
    """L'index est-il utilisable ? Le construit s'il est vide alors que des
    paragraphes existent — cas d'un poste dont la base date d'avant cette
    fonctionnalité : le corpus n'a pas changé, donc rien ne déclencherait de
    réimport, et la recherche resterait muette."""
    if not has_paragraph_search():
        return False
    conn = get_connection()
    try:
        total = _paragraph_count(conn)
    finally:
        conn.close()
    if not total:
        return False        # corpus absent : rien à indexer
    if get_meta(_INDEX_ROWS_KEY) == str(total):
        return True
    rebuild_search_index()  # première recherche sur une base d'avant : ~3 s
    return get_meta(_INDEX_ROWS_KEY) == str(total)


# Mots de la requête : on ne reprend que les suites de lettres et de chiffres.
# La saisie de l'opérateur ne doit jamais être interprétée comme de la syntaxe
# FTS5 (guillemets, `*`, `NEAR`, `OR`…) : elle est retokenisée puis remise entre
# guillemets, ce qui en fait une recherche d'expression exacte.
_WORDS = re.compile(r"\w+", re.UNICODE)


def search_paragraphs(query: str, limit: int = 50):
    """Paragraphes contenant l'expression `query` (accents et casse ignorés).

    Retourne au plus `limit` dicts {predication_id, date_code, title_fr, letter,
    prefix, number, text}, dans l'ordre du corpus — `letter` et `prefix`
    permettent au panneau de rejoindre la prédication sans requête de plus. Liste vide sous 3 caractères utiles, comme la
    recherche dans les versets, et si l'index n'est pas disponible.
    """
    mots = _WORDS.findall(query or "")
    if not mots or len("".join(mots)) < 3:
        return []
    expression = '"' + " ".join(mots) + '"'
    if not _search_index_ready():
        return []
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.predication_id AS predication_id, p.number AS number,
                   p.text AS text, d.date_code AS date_code, d.title_fr AS title_fr,
                   d.letter AS letter, d.prefix AS prefix
            FROM paragraph_search s
            JOIN predication_paragraphs p ON p.rowid = s.rowid
            JOIN predications d ON d.id = p.predication_id
            WHERE paragraph_search MATCH ?
            ORDER BY s.rowid
            LIMIT ?
            """,
            (expression, limit),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"BDA : recherche plein texte impossible ({exc}).", file=sys.stderr)
        return []
    finally:
        conn.close()
    return [dict(row) for row in rows]


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
    """Recherche par titre FR/EN ou code date (id, date_code, title_fr, title_en).

    Accents, casse et apostrophes ignorés (« l'adoption » trouve « L’Adoption »,
    « predestination » trouve « Prédestination ») ; comparaison en Python car
    le LIKE de SQLite est sensible aux accents. Le corpus reste petit
    (~2 000 titres), la passe est immédiate."""
    needle = search_key(query.strip())
    if not needle:
        return []
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, date_code, title_fr, title_en FROM predications
        ORDER BY title_fr, date_code
        """
    ).fetchall()
    conn.close()
    results = [
        row for row in rows
        if needle in search_key(row["title_fr"])
        or needle in search_key(row["title_en"])
        or needle in search_key(row["date_code"])
    ]
    return results[:limit]


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
