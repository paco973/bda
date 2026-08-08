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


def _fit_count(words, start, fits, guess) -> int:
    """Nombre de mots (>= 1) à partir de `start` qui satisfont `fits`.

    Dichotomie (prédicat supposé monotone : plus long ne tient pas mieux),
    guidée par `guess` (taille du morceau précédent) : les morceaux successifs
    d'un même texte ayant des tailles voisines, le cas stable se résout en
    deux mesures au lieu de log(n).
    """
    remaining = len(words) - start

    def ok(count):
        return fits(" ".join(words[start:start + count]))

    lo, hi, best = 1, remaining, 1
    if 1 <= guess <= remaining and ok(guess):
        if guess == remaining or not ok(guess + 1):
            return guess
        lo, best = guess + 1, guess
    elif 1 <= guess <= remaining:
        hi = guess - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if ok(mid):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def split_to_fit(text: str, fits) -> list:
    """Découpe `text` en morceaux successifs satisfaisant le prédicat `fits`.

    Découpage par mots. Sans prédicat, ou si le texte tient déjà, retourne
    `[text]`. Chaque morceau contient au moins un mot, ce qui garantit la
    progression même si un mot seul ne tient pas.
    """
    if fits is None or fits(text):
        return [text]
    words = text.split()
    if not words:
        return [text]
    chunks, start, guess = [], 0, 0
    while start < len(words):
        count = _fit_count(words, start, fits, guess)
        chunks.append(" ".join(words[start:start + count]))
        start += count
        guess = count
    return chunks
