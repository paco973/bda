"""
Ordre du culte : liste ordonnée et persistante de chants et de passages
bibliques, préparée avant le culte et déroulée pendant.
"""
from logos.data.database import get_connection


def list_items():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, position, kind, song_id, label, content"
        " FROM service_items ORDER BY position"
    ).fetchall()
    conn.close()
    return rows


def _next_position(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(position), 0) FROM service_items").fetchone()
    return row[0] + 1


def add_song(song_id: int, title: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO service_items (position, kind, song_id, label) VALUES (?, 'song', ?, ?)",
        (_next_position(conn), song_id, title),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def add_passage(label: str, content: str) -> int:
    """Ajoute un passage biblique ; content est le texte prêt à projeter
    (diapositives séparées par des lignes vides, comme les paroles)."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO service_items (position, kind, label, content) VALUES (?, 'passage', ?, ?)",
        (_next_position(conn), label, content),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def update_song_label(song_id: int, title: str):
    """Garde le libellé du culte synchronisé quand un chant est renommé."""
    conn = get_connection()
    conn.execute(
        "UPDATE service_items SET label = ? WHERE kind = 'song' AND song_id = ?",
        (title, song_id),
    )
    conn.commit()
    conn.close()


def get_item(item_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, position, kind, song_id, label, content FROM service_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    conn.close()
    return row


def remove_item(item_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM service_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def move_item(item_id: int, delta: int):
    """Décale un élément vers le haut (delta=-1) ou le bas (delta=+1)
    en échangeant sa position avec celle de son voisin."""
    conn = get_connection()
    current = conn.execute(
        "SELECT id, position FROM service_items WHERE id = ?", (item_id,)
    ).fetchone()
    if current is None:
        conn.close()
        return
    comparator, order = ("<", "DESC") if delta < 0 else (">", "ASC")
    neighbor = conn.execute(
        f"SELECT id, position FROM service_items WHERE position {comparator} ?"
        f" ORDER BY position {order} LIMIT 1",
        (current["position"],),
    ).fetchone()
    if neighbor is not None:
        conn.execute(
            "UPDATE service_items SET position = ? WHERE id = ?",
            (neighbor["position"], current["id"]),
        )
        conn.execute(
            "UPDATE service_items SET position = ? WHERE id = ?",
            (current["position"], neighbor["id"]),
        )
        conn.commit()
    conn.close()


def clear_items():
    conn = get_connection()
    conn.execute("DELETE FROM service_items")
    conn.commit()
    conn.close()
