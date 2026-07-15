"""
Mise en forme des passages bibliques en diapositives. Logique pure (pas de SQL,
pas de Qt) pour rester testable.
"""


def passage_label(book_name: str, chapter: int, verse_start: int, verse_end: int) -> str:
    """Référence lisible d'un passage, ex. « Jean 3:16 » ou « Jean 3:16-18 »."""
    if verse_end > verse_start:
        return f"{book_name} {chapter}:{verse_start}-{verse_end}"
    return f"{book_name} {chapter}:{verse_start}"


def passage_to_text(book_name: str, chapter: int, verses) -> str:
    """Met en forme un passage en texte projetable : une diapositive par verset
    (texte + référence)."""
    slides = [
        f"{text}\n{book_name} {chapter}:{verse}"
        for verse, text in verses
    ]
    return "\n\n".join(slides)
