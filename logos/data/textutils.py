"""Petits utilitaires de texte partagés par la couche données (logique pure)."""
import unicodedata


def strip_accents(text: str) -> str:
    """« Élie » -> « Elie » : retire les signes diacritiques (comparaisons A-Z)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


# Les textes emploient l'apostrophe typographique « ’ » alors que le clavier
# produit « ' » : les unifier pour que « l'eternel » trouve « l’Éternel ».
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'"})


def search_key(text: str) -> str:
    """Forme de comparaison pour les recherches : minuscules, sans accents,
    apostrophes unifiées. Utilisée pour les versets et les titres de prédications."""
    return strip_accents(text).lower().translate(_APOSTROPHES)
