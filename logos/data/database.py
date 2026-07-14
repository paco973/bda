"""
Gestion de la base de données SQLite pour les chants.
Les paroles d'un chant sont stockées comme un texte unique où chaque
diapositive (slide) est séparée par une ligne vide.
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            lyrics TEXT NOT NULL DEFAULT ''
        )
        """
    )
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
    # Ordre du culte : liste ordonnée de chants et de passages bibliques
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS service_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position INTEGER NOT NULL,
            kind TEXT NOT NULL,             -- 'song' ou 'passage'
            song_id INTEGER,                -- renseigné si kind='song'
            label TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT ''  -- texte du passage si kind='passage'
        )
        """
    )
    conn.commit()
    conn.close()


def list_songs(search: str = ""):
    conn = get_connection()
    if search:
        rows = conn.execute(
            "SELECT id, title FROM songs WHERE title LIKE ? ORDER BY title",
            (f"%{search}%",),
        ).fetchall()
    else:
        rows = conn.execute("SELECT id, title FROM songs ORDER BY title").fetchall()
    conn.close()
    return rows


def get_song(song_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
    conn.close()
    return row


def save_song(song_id, title: str, lyrics: str):
    conn = get_connection()
    if song_id:
        conn.execute(
            "UPDATE songs SET title = ?, lyrics = ? WHERE id = ?",
            (title, lyrics, song_id),
        )
    else:
        cur = conn.execute(
            "INSERT INTO songs (title, lyrics) VALUES (?, ?)", (title, lyrics)
        )
        song_id = cur.lastrowid
    conn.commit()
    conn.close()
    return song_id


def delete_song(song_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    # Un chant supprimé ne doit pas laisser d'entrée orpheline dans le culte
    conn.execute("DELETE FROM service_items WHERE kind = 'song' AND song_id = ?", (song_id,))
    conn.commit()
    conn.close()