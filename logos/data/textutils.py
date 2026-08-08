"""Petits utilitaires de texte partagés par la couche données (logique pure)."""
import unicodedata


def strip_accents(text: str) -> str:
    """« Élie » -> « Elie » : retire les signes diacritiques (comparaisons A-Z)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
