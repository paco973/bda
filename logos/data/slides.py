"""
Découpage du contenu en diapositives. Logique pure (pas de SQL, pas de Qt)
pour rester testable et réutilisable (chants aujourd'hui, versets en V2).
"""


def lyrics_to_slides(lyrics: str) -> list[str]:
    """Découpe le texte des paroles en diapositives (séparées par une ligne vide)."""
    blocks = [b.strip() for b in lyrics.split("\n\n")]
    return [b for b in blocks if b]


def passage_label(book_name: str, chapter: int, verse_start: int, verse_end: int) -> str:
    """Référence lisible d'un passage, ex. « Jean 3:16 » ou « Jean 3:16-18 »."""
    if verse_end > verse_start:
        return f"{book_name} {chapter}:{verse_start}-{verse_end}"
    return f"{book_name} {chapter}:{verse_start}"


def passage_to_text(book_name: str, chapter: int, verses) -> str:
    """Met en forme un passage en texte projetable : une diapositive par verset
    (texte + référence), au même format que des paroles de chant."""
    slides = [
        f"{text}\n{book_name} {chapter}:{verse}"
        for verse, text in verses
    ]
    return "\n\n".join(slides)
