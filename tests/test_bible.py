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
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
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
    assert len(bible.get_chapter(1, 1)) == 2
    assert len(bible.get_chapter(1, 2)) == 1


def test_passage():
    bible.import_data(SAMPLE)
    verses = bible.get_passage(1, 1, 1, 2)
    assert [v["verse"] for v in verses] == [1, 2]
    assert bible.get_passage(1, 1, 99, 99) == []


def test_label_de_passage():
    assert slides.passage_label("Jean", 3, 16, 16) == "Jean 3:16"
    assert slides.passage_label("Jean", 3, 16, 18) == "Jean 3:16-18"


def test_caches_suivent_la_base(tmp_path, monkeypatch):
    """Les caches mémoire (noms de livres, recherche plein texte) sont liés à la
    base ouverte : `DB_PATH` change d'un test à l'autre, et un cache qui lui
    survivrait décrirait un corpus qui n'est plus celui interrogé."""
    bible.import_data(SAMPLE)
    assert bible.parse_reference("gen") == (1, None, None)
    assert len(bible.search_verses("commencement")) == 2   # Genèse 1:1 et Jean 1:1

    autre = {"books": [{"nr": 66, "name": "Apocalypse", "chapters": [
        {"chapter": 1, "verses": [{"verse": 1, "text": "Révélation de Jésus-Christ"}]}]}]}
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autre.db")
    database.init_db()
    bible.import_data(autre)

    assert bible.parse_reference("genese") is None      # Genèse n'existe plus
    assert bible.parse_reference("apocalypse") == (66, None, None)
    assert bible.search_verses("commencement") == []


def test_groupes_canoniques():
    assert bible.book_group(1) == "pentateuque"      # Genèse
    assert bible.book_group(5) == "pentateuque"      # Deutéronome
    assert bible.book_group(6) == "historiques"      # Josué
    assert bible.book_group(17) == "historiques"     # Esther
    assert bible.book_group(18) == "poetiques"       # Job
    assert bible.book_group(23) == "prophetes"       # Ésaïe
    assert bible.book_group(40) == "evangiles"       # Matthieu
    assert bible.book_group(44) == "actes"
    assert bible.book_group(45) == "epitres"         # Romains
    assert bible.book_group(66) == "apocalypse"
    # Chaque groupe a sa couleur dans le thème.
    from logos.ui import theme
    for book_id in range(1, 67):
        assert bible.book_group(book_id) in theme.BOOK_GROUP_COLORS


def test_parse_reference():
    bible.import_data(SAMPLE)
    assert bible.parse_reference("Jean 3:16") == (43, 3, 16)
    assert bible.parse_reference("jean 3 16") == (43, 3, 16)
    assert bible.parse_reference("Jea 3") == (43, 3, None)      # abréviation
    assert bible.parse_reference("gen 1:2") == (1, 1, 2)        # début de nom
    assert bible.parse_reference("genèse") == (1, None, None)   # livre seul
    assert bible.parse_reference("bonjour tout le monde") is None
    assert bible.parse_reference("3:16") is None
    assert bible.parse_reference("") is None


def test_split_to_fit():
    fits = lambda t: len(t) <= 20
    assert slides.split_to_fit("court", fits) == ["court"]
    assert slides.split_to_fit("texte sans prédicat", None) == ["texte sans prédicat"]
    chunks = slides.split_to_fit("un deux trois quatre cinq six sept", fits)
    assert len(chunks) > 1
    assert all(len(c) <= 20 for c in chunks)
    assert " ".join(chunks) == "un deux trois quatre cinq six sept"
    # Un mot seul qui ne tient pas passe quand même (progression garantie).
    assert slides.split_to_fit("incompressible", lambda t: len(t) <= 3) == ["incompressible"]


def test_search_verses():
    bible.import_data(SAMPLE)
    # Accents et casse ignorés.
    rows = bible.search_verses("DIEU CREA")
    assert [(r["book_id"], r["chapter"], r["verse"]) for r in rows] == [(1, 1, 1)]
    assert "créa" in rows[0]["text"]
    # Moins de 3 caractères : pas de résultat (trop de bruit).
    assert bible.search_verses("au") == []
    # Limite respectée.
    assert len(bible.search_verses("informe", limit=1)) == 1
    # Le cache est invalidé quand le corpus est réimporté.
    modified = {"books": [dict(SAMPLE["books"][0], chapters=[
        {"chapter": 1, "verses": [{"verse": 1, "text": "Texte remplacé."}]},
    ])]}
    bible.import_data(modified)
    assert bible.search_verses("dieu crea") == []
    assert len(bible.search_verses("remplace")) == 1


def test_bible_embarquee_complete():
    """L'asset livré avec l'application contient bien les 66 livres."""
    assert bible.BIBLE_ASSET.exists()
    bible.ensure_imported()
    books = bible.get_books()
    assert len(books) == 66
    jean_316 = bible.get_passage(43, 3, 16, 16)
    assert "Dieu a tant aimé le monde" in jean_316[0]["text"]
    # L'apostrophe clavier « ' » doit trouver l'apostrophe typographique « ’ »
    # employée par le texte (et réciproquement).
    ascii_rows = bible.search_verses("l'eternel dit")
    typo_rows = bible.search_verses("l’eternel dit")
    assert ascii_rows and ascii_rows == typo_rows
