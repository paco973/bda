"""
Connexion SQLite et création des tables : Bible embarquée, prédications et
métadonnées d'import (les tables sont créées avec IF NOT EXISTS pour rester
compatibles avec les bases existantes des utilisateurs).

La base est reconstruite automatiquement au premier lancement (Bible et
prédications réimportées depuis `logos/assets/`) : changer d'emplacement ne
perd aucune donnée utilisateur.
"""
import sqlite3
import sys

from logos.resources import USER_DIR

DB_PATH = USER_DIR / "bda.db"


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
    # Index plein texte des paragraphes de prédications (recherche dans le
    # contenu, pas seulement dans les titres). 238 000 paragraphes et 142 Mo de
    # texte : le cache mémoire normalisé qui sert à la Bible coûterait 13 s de
    # construction et autant de mémoire, là où FTS5 s'indexe en 3 s et répond en
    # moins d'une milliseconde. `remove_diacritics 2` replie les accents, donc
    # « eternel » trouve « l'Éternel ».
    #
    # Index externe (`content=`) : le texte n'est pas dupliqué, seuls les termes
    # le sont. En contrepartie il référence les `rowid` de la table source et
    # doit être reconstruit après chaque import (voir `predications`).
    #
    # FTS5 est présent dans les distributions Python usuelles, mais pas garanti :
    # `has_paragraph_search()` permet à l'appel de se replier proprement.
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS paragraph_search USING fts5(
                text,
                content='predication_paragraphs',
                content_rowid='rowid',
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
    except sqlite3.OperationalError as exc:
        print(
            f"BDA : recherche plein texte indisponible ({exc}) — le reste de "
            "l'application fonctionne normalement.",
            file=sys.stderr,
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


def has_paragraph_search() -> bool:
    """L'index plein texte des paragraphes existe-t-il ? (FTS5 absent = False)"""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'paragraph_search'"
    ).fetchone()
    conn.close()
    return row is not None


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
