"""
Connexion SQLite et création des tables : Bible embarquée, prédications et
métadonnées d'import (les tables sont créées avec IF NOT EXISTS pour rester
compatibles avec les bases existantes des utilisateurs).

La base est reconstruite automatiquement au premier lancement (Bible et
prédications réimportées depuis `logos/assets/`) : changer d'emplacement ne
perd aucune donnée utilisateur.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".bda" / "bda.db"


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
    # Prédications (importées depuis logos/assets/ via le script d'import).
    # `letter`/`prefix` sont dérivés du titre à l'import pour un regroupement rapide.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_code TEXT NOT NULL,
            title_fr TEXT NOT NULL,
            title_en TEXT NOT NULL DEFAULT '',
            letter TEXT NOT NULL,
            prefix TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predication_paragraphs (
            predication_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            text TEXT NOT NULL,
            PRIMARY KEY (predication_id, number)
        )
        """
    )
    # Métadonnées clé/valeur (ex. empreintes des assets importés, pour
    # réimporter automatiquement quand un asset embarqué change).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def get_meta(key: str):
    """Valeur de la table `meta` pour `key`, ou None si absente."""
    conn = get_connection()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row is not None else None


def set_meta(key: str, value: str):
    """Enregistre (ou remplace) la valeur de `key` dans la table `meta`."""
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
