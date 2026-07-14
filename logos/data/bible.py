"""
Accès à la Bible embarquée (Louis Segond 1910, domaine public).
Le texte est livré compressé dans logos/assets/ et importé dans SQLite
au premier lancement — l'application reste 100 % hors ligne.
"""
import gzip
import json
from pathlib import Path

from logos.data.database import get_connection

BIBLE_ASSET = Path(__file__).parent.parent / "assets" / "bible_ls1910.json.gz"
TRANSLATION = "Louis Segond (1910)"


def is_available() -> bool:
    """La Bible a-t-elle déjà été importée dans la base ?"""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM bible_books").fetchone()[0]
    conn.close()
    return count > 0


def ensure_imported():
    """Importe la Bible embarquée au premier lancement (quelques secondes)."""
    if is_available() or not BIBLE_ASSET.exists():
        return
    with gzip.open(BIBLE_ASSET, "rt", encoding="utf-8") as f:
        import_data(json.load(f))


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
