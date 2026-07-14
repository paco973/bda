"""Tests de la Bible embarquée : import, requêtes et mise en forme des passages."""
import pytest

from logos.data import bible, database, slides

SAMPLE = {
    "translation": "Test",
    "books": [
        {
            "nr": 1,
            "name": "Genèse",
            "chapters": [
                {
                    "chapter": 1,
                    "verses": [
                        {"verse": 1, "text": "Au commencement, Dieu créa les cieux et la terre."},
                        {"verse": 2, "text": "La terre était informe et vide."},
                    ],
                },
                {"chapter": 2, "verses": [{"verse": 1, "text": "Ainsi furent achevés les cieux."}]},
            ],
        },
        {
            "nr": 43,
            "name": "Jean",
            "chapters": [
                {"chapter": 1, "verses": [{"verse": 1, "text": "Au commencement était la Parole."}]},
            ],
        },
    ],
}


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "songs.db")
    database.init_db()


def test_disponibilite():
    assert not bible.is_available()
    bible.import_data(SAMPLE)
    assert bible.is_available()


def test_livres_et_compteurs():
    bible.import_data(SAMPLE)
    books = bible.get_books()
    assert [b["name"] for b in books] == ["Genèse", "Jean"]
    assert books[0]["chapters"] == 2
    assert bible.get_verse_count(1, 1) == 2
    assert bible.get_verse_count(1, 2) == 1


def test_passage():
    bible.import_data(SAMPLE)
    verses = bible.get_passage(1, 1, 1, 2)
    assert [v["verse"] for v in verses] == [1, 2]
    assert bible.get_passage(1, 1, 99, 99) == []


def test_label_et_texte_projetable():
    assert slides.passage_label("Jean", 3, 16, 16) == "Jean 3:16"
    assert slides.passage_label("Jean", 3, 16, 18) == "Jean 3:16-18"
    bible.import_data(SAMPLE)
    verses = bible.get_passage(1, 1, 1, 2)
    text = slides.passage_to_text("Genèse", 1, verses)
    # Une diapositive par verset, référence sur la dernière ligne
    parts = slides.lyrics_to_slides(text)
    assert len(parts) == 2
    assert parts[0].endswith("Genèse 1:1")
    assert parts[1].startswith("La terre était informe")


def test_bible_embarquee_complete():
    """L'asset livré avec l'application contient bien les 66 livres."""
    assert bible.BIBLE_ASSET.exists()
    bible.ensure_imported()
    books = bible.get_books()
    assert len(books) == 66
    jean_316 = bible.get_passage(43, 3, 16, 16)
    assert "Dieu a tant aimé le monde" in jean_316[0]["text"]
