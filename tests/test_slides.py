"""Tests du découpage paroles -> diapositives (logique pure, sans Qt ni DB)."""
from logos.data.slides import lyrics_to_slides


def test_decoupe_sur_ligne_vide():
    lyrics = "Couplet 1\nligne 2\n\nRefrain\nligne 2"
    assert lyrics_to_slides(lyrics) == ["Couplet 1\nligne 2", "Refrain\nligne 2"]


def test_ignore_blocs_vides_et_espaces():
    lyrics = "  Couplet  \n\n\n\nRefrain\n\n"
    assert lyrics_to_slides(lyrics) == ["Couplet", "Refrain"]


def test_paroles_vides():
    assert lyrics_to_slides("") == []


def test_un_seul_bloc():
    assert lyrics_to_slides("Alléluia") == ["Alléluia"]
