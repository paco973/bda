"""
Accès à la Bible embarquée (Louis Segond 1910, domaine public).
Le texte est livré compressé dans logos/assets/ et importé dans SQLite
au premier lancement — l'application reste 100 % hors ligne.
"""
import gzip
import hashlib
import json
from pathlib import Path

from logos.data.database import get_connection, get_meta, set_meta

BIBLE_ASSET = Path(__file__).parent.parent / "assets" / "bible_ls1910.json.gz"
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


def is_available() -> bool:
    """La Bible a-t-elle déjà été importée dans la base ?"""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM bible_books").fetchone()[0]
    conn.close()
    return count > 0


_ASSET_META_KEY = "bible_asset_sha256"


def _asset_fingerprint() -> str:
    return hashlib.sha256(BIBLE_ASSET.read_bytes()).hexdigest()


def ensure_imported():
    """Importe la Bible embarquée si absente de la base **ou** si l'asset a
    changé depuis le dernier import (empreinte stockée dans `meta`) — même
    mécanique que les prédications. L'import initial prend quelques secondes."""
    if not BIBLE_ASSET.exists():
        return
    fingerprint = _asset_fingerprint()
    if is_available() and get_meta(_ASSET_META_KEY) == fingerprint:
        return
    with gzip.open(BIBLE_ASSET, "rt", encoding="utf-8") as f:
        import_data(json.load(f))
    set_meta(_ASSET_META_KEY, fingerprint)


def import_data(data: dict):
    """Remplit les tables bible_* depuis le format {books: [{nr, name, chapters}]}."""
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


def get_verse_count(book_id: int, chapter: int) -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE book_id = ? AND chapter = ?",
        (book_id, chapter),
    ).fetchone()[0]
    conn.close()
    return count


def get_chapter(book_id: int, chapter: int):
    """Tous les versets (verse, text) d'un chapitre, dans l'ordre."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT verse, text FROM bible_verses WHERE book_id = ? AND chapter = ? ORDER BY verse",
        (book_id, chapter),
    ).fetchall()
    conn.close()
    return rows


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
