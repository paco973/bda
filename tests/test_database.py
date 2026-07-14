"""Tests du CRUD SQLite sur une base temporaire (aucune donnée utilisateur touchée)."""
import pytest

from logos.data import database


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "songs.db")
    database.init_db()


def test_creation_et_lecture():
    song_id = database.save_song(None, "Amazing Grace", "Couplet 1\n\nRefrain")
    row = database.get_song(song_id)
    assert row["title"] == "Amazing Grace"
    assert row["lyrics"] == "Couplet 1\n\nRefrain"


def test_mise_a_jour():
    song_id = database.save_song(None, "Titre", "a")
    same_id = database.save_song(song_id, "Titre corrigé", "b")
    assert same_id == song_id
    row = database.get_song(song_id)
    assert row["title"] == "Titre corrigé"
    assert row["lyrics"] == "b"


def test_suppression():
    song_id = database.save_song(None, "À supprimer", "")
    database.delete_song(song_id)
    assert database.get_song(song_id) is None
    assert database.list_songs() == []


def test_liste_triee_et_recherche():
    database.save_song(None, "Zacharie", "")
    database.save_song(None, "Alléluia", "")
    titles = [r["title"] for r in database.list_songs()]
    assert titles == ["Alléluia", "Zacharie"]
    results = [r["title"] for r in database.list_songs("zach")]
    assert results == ["Zacharie"]
