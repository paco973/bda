"""
Accès à la Bible embarquée (Louis Segond 1910, domaine public).
Le texte est livré compressé dans logos/assets/ et importé dans SQLite
au premier lancement — l'application reste 100 % hors ligne.

Comme les prédications, le texte peut être remplacé sans réinstaller en
déposant un fichier dans `~/.bda/assets/` (voir `logos.resources`).
"""
import gzip
import hashlib
import json
import re
import sys

from logos.data import database
from logos.data.database import get_connection, get_meta, set_meta
from logos.data.textutils import search_key, strip_accents
from logos.resources import asset_path, bundled_asset_path

ASSET_NAME = "bible_ls1910.json.gz"
BIBLE_ASSET = asset_path(ASSET_NAME)
TRANSLATION = "Louis Segond (1910)"
TRANSLATION_CODE = "LSG"

# Nombre de livres de l'Ancien Testament (les 39 premiers dans l'ordre canonique).
OLD_TESTAMENT_COUNT = 39

# Abréviations d'affichage des 66 livres, dans l'ordre canonique (id 1..66),
# telles qu'attendues par la navigation Bible (colonnes de la grille des livres).
BOOK_ABBREVIATIONS = {
    1: "Gn", 2: "Ex", 3: "Lv", 4: "Nm", 5: "Dt",
    6: "Js", 7: "Jg", 8: "Rt", 9: "1Sa", 10: "2Sa",
    11: "1Ro", 12: "2Ro", 13: "1Ch", 14: "2Ch", 15: "Esd",
    16: "Ne", 17: "Est", 18: "Job", 19: "Psa", 20: "Pro",
    21: "Ecc", 22: "Can", 23: "Esa", 24: "Jer", 25: "Lam",
    26: "Eze", 27: "Dn", 28: "Ose", 29: "Joe", 30: "Amo",
    31: "Abd", 32: "Jon", 33: "Mic", 34: "Nah", 35: "Hb",
    36: "Sop", 37: "Agg", 38: "Zac", 39: "Mal",
    40: "Mat", 41: "Mar", 42: "Luc", 43: "Jea", 44: "Act",
    45: "Rom", 46: "1Co", 47: "2Co", 48: "Gal", 49: "Eph",
    50: "Phi", 51: "Col", 52: "1Th", 53: "2Th", 54: "1Ti",
    55: "2Ti", 56: "Tit", 57: "Phm", 58: "He", 59: "Jac",
    60: "1Pi", 61: "2Pi", 62: "1Jn", 63: "2Jn", 64: "3Jn",
    65: "Jud", 66: "Apo",
}


def book_abbreviation(book_id: int) -> str:
    """Abréviation courte d'un livre (chaîne vide si l'id est inconnu)."""
    return BOOK_ABBREVIATIONS.get(book_id, "")


def testament(book_id: int) -> str:
    """« Ancien Testament » (livres 1 à 39) ou « Nouveau Testament » (40 à 66)."""
    return "Ancien Testament" if book_id <= OLD_TESTAMENT_COUNT else "Nouveau Testament"


# Groupes canoniques des livres : (dernier id du groupe, clé du groupe).
# Sert au code couleur de la grille des livres (couleurs dans logos/ui/theme.py).
_BOOK_GROUPS = (
    (5, "pentateuque"),     # Genèse -> Deutéronome
    (17, "historiques"),    # Josué -> Esther
    (22, "poetiques"),      # Job -> Cantique des cantiques
    (39, "prophetes"),      # Ésaïe -> Malachie
    (43, "evangiles"),      # Matthieu -> Jean
    (44, "actes"),          # Actes
    (65, "epitres"),        # Romains -> Jude
    (66, "apocalypse"),     # Apocalypse
)


def book_group(book_id: int) -> str:
    """Clé du groupe canonique d'un livre (« pentateuque », « epitres », …)."""
    for last_id, group in _BOOK_GROUPS:
        if book_id <= last_id:
            return group
    return "apocalypse"


# « Jean 3:16 », « jean 3 16 », « 1 co 13 »… : livre (éventuellement précédé
# d'un ordinal), puis chapitre et verset optionnels.
_REFERENCE = re.compile(
    r"^\s*(?P<book>[0-9]?\s*[^\d:.,;]+?)\s*"
    r"(?:(?P<chapter>\d+)\s*(?:[:.,;\s]\s*(?P<verse>\d+))?)?\s*$"
)


def _normalize(text: str) -> str:
    """Clé de comparaison d'un nom de livre : sans accents, casse ni ponctuation."""
    return "".join(c for c in strip_accents(text).lower() if c.isalnum())


def parse_reference(query: str):
    """Analyse une référence tapée : « Jean 3:16 » -> (43, 3, 16).

    Le livre est reconnu par nom exact, abréviation canonique ou début de nom
    (2 lettres minimum), accents/casse ignorés. Chapitre et verset sont
    optionnels (None si absents) et ne sont pas bornés ici. Retourne None si la
    requête ne ressemble pas à une référence ou si aucun livre ne correspond.
    """
    match = _REFERENCE.match(query or "")
    if match is None:
        return None
    key = _normalize(match.group("book"))
    if not any(c.isalpha() for c in key):
        return None

    book_id = next(
        (bid for bid, abbr in BOOK_ABBREVIATIONS.items() if _normalize(abbr) == key),
        None,
    )
    if book_id is None:
        names = _normalized_book_names()
        book_id = next((bid for bid, name in names if name == key), None)
        if book_id is None and len(key) >= 2:
            book_id = next((bid for bid, name in names if name.startswith(key)), None)
    if book_id is None:
        return None

    chapter = int(match.group("chapter")) if match.group("chapter") else None
    verse = int(match.group("verse")) if match.group("verse") else None
    return book_id, chapter, verse


# Caches mémoire dérivés du contenu de la base. Ils sont invalidés par
# `import_data()` **et** par un changement de base : `DB_PATH` est monkeypatché
# d'un test à l'autre, et un cache survivant à ce changement décrirait un corpus
# qui n'est plus celui interrogé.
_cached_db = None
_book_names_cache = None


def _check_db_changed():
    """Vide les caches si la base ouverte n'est plus la même qu'au remplissage."""
    global _cached_db, _search_cache, _book_names_cache
    # `database.DB_PATH` et non une copie importée : les tests le remplacent
    # à l'exécution, et une copie figée à l'import ne verrait rien.
    if _cached_db != database.DB_PATH:
        _cached_db = database.DB_PATH
        _search_cache = None
        _book_names_cache = None


def _normalized_book_names():
    """Noms de livres normalisés — la barre de recherche appelle
    `parse_reference` à chaque frappe, et sans ce cache chaque touche rouvrirait
    la base pour relire et normaliser les 66 livres."""
    global _book_names_cache
    _check_db_changed()
    if _book_names_cache is None:
        _book_names_cache = [
            (row["id"], _normalize(row["name"])) for row in get_books()
        ]
    return _book_names_cache


def is_available() -> bool:
    """La Bible a-t-elle déjà été importée dans la base ?"""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM bible_books").fetchone()[0]
    conn.close()
    return count > 0


_ASSET_META_KEY = "bible_asset_sha256"


def _asset_fingerprint(asset) -> str:
    return hashlib.sha256(asset.read_bytes()).hexdigest()


def _candidate_assets():
    """Fichiers à essayer, du plus prioritaire au repli : le texte retenu par
    `logos.resources` (dépôt de l'opérateur s'il existe) puis, si celui-ci est
    illisible, celui livré avec l'application."""
    paths, seen = [], set()
    for path in (BIBLE_ASSET, bundled_asset_path(ASSET_NAME)):
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
    """Importe la Bible si absente de la base **ou** si l'asset a changé depuis
    le dernier import (empreinte stockée dans `meta`) — même mécanique que les
    prédications. L'import initial prend quelques secondes.

    Un texte déposé illisible ne doit pas empêcher l'application de démarrer :
    on signale le problème et on retombe sur celui livré."""
    for asset in _candidate_assets():
        try:
            _import_asset(asset)
            return
        except (OSError, ValueError) as exc:
            print(
                f"BDA : Bible illisible dans {asset} ({exc}) — "
                "repli sur le texte livré avec l'application.",
                file=sys.stderr,
            )


def import_data(data: dict):
    """Remplit les tables bible_* depuis le format {books: [{nr, name, chapters}]}."""
    global _search_cache, _book_names_cache
    # Le corpus change : les caches mémoire dérivés sont périmés.
    _search_cache = None
    _book_names_cache = None
    conn = get_connection()
    conn.execute("DELETE FROM bible_verses")
    conn.execute("DELETE FROM bible_books")
    for book in data["books"]:
        conn.execute(
            "INSERT INTO bible_books (id, name, chapters) VALUES (?, ?, ?)",
            (book["nr"], book["name"], len(book["chapters"])),
        )
        conn.executemany(
            "INSERT INTO bible_verses (book_id, chapter, verse, text) VALUES (?, ?, ?, ?)",
            (
                (book["nr"], chapter["chapter"], verse["verse"], verse["text"].strip())
                for chapter in book["chapters"]
                for verse in chapter["verses"]
            ),
        )
    conn.commit()
    conn.close()


def get_books():
    """Liste des livres (id, name, chapters) dans l'ordre canonique."""
    conn = get_connection()
    rows = conn.execute("SELECT id, name, chapters FROM bible_books ORDER BY id").fetchall()
    conn.close()
    return rows


def get_chapter(book_id: int, chapter: int):
    """Tous les versets (verse, text) d'un chapitre, dans l'ordre."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT verse, text FROM bible_verses WHERE book_id = ? AND chapter = ? ORDER BY verse",
        (book_id, chapter),
    ).fetchall()
    conn.close()
    return rows


# Versets normalisés, chargés en mémoire à la première recherche (normaliser
# les ~31 000 versets à chaque requête coûterait ~300 ms ; ainsi la recherche
# reste instantanée). Invalidé par import_data().
_search_cache = None


def _search_rows():
    global _search_cache
    _check_db_changed()
    if _search_cache is None:
        conn = get_connection()
        rows = conn.execute(
            "SELECT book_id, chapter, verse, text FROM bible_verses"
            " ORDER BY book_id, chapter, verse"
        ).fetchall()
        conn.close()
        _search_cache = [
            (r["book_id"], r["chapter"], r["verse"], r["text"], search_key(r["text"]))
            for r in rows
        ]
    return _search_cache


def warm_search_cache():
    """Précharge le cache de recherche (~300 ms) — à appeler au lancement,
    hors du chemin critique, pour que la première recherche soit instantanée."""
    _search_rows()


def search_verses(query: str, limit: int = 50):
    """Versets dont le texte contient `query` (accents et casse ignorés).

    Retourne au plus `limit` dicts {book_id, chapter, verse, text} dans
    l'ordre canonique ; liste vide sous 3 caractères utiles (trop de bruit).
    """
    needle = search_key(query.strip())
    if len(needle) < 3:
        return []
    results = []
    for book_id, chapter, verse, text, key in _search_rows():
        if needle in key:
            results.append(
                {"book_id": book_id, "chapter": chapter, "verse": verse, "text": text}
            )
            if len(results) >= limit:
                break
    return results


def get_passage(book_id: int, chapter: int, verse_start: int, verse_end: int):
    """Versets (verse, text) du passage demandé, bornes incluses."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT verse, text FROM bible_verses
        WHERE book_id = ? AND chapter = ? AND verse BETWEEN ? AND ?
        ORDER BY verse
        """,
        (book_id, chapter, verse_start, verse_end),
    ).fetchall()
    conn.close()
    return rows
