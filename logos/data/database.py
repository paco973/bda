"""
Connexion SQLite et création des tables. La base ne contient plus que la Bible
embarquée (les tables sont créées avec IF NOT EXISTS pour rester compatibles
avec les bases existantes des utilisateurs).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".holyrics_clone" / "songs.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    # Bible embarquée (importée au premier lancement depuis logos/assets/)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bible_books (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            chapters INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bible_verses (
            book_id INTEGER NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL,
            PRIMARY KEY (book_id, chapter, verse)
        )
        """
    )
    conn.commit()
    conn.close()
