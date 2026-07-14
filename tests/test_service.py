"""Tests de l'ordre du culte : ajout, déplacement, retrait, synchronisation."""
import pytest

from logos.data import database, service


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "songs.db")
    database.init_db()


def labels():
    return [r["label"] for r in service.list_items()]


def test_ajout_dans_l_ordre():
    song_id = database.save_song(None, "Chant A", "x")
    service.add_song(song_id, "Chant A")
    service.add_passage("Jean 3:16", "texte\nJean 3:16")
    assert labels() == ["Chant A", "Jean 3:16"]
    kinds = [r["kind"] for r in service.list_items()]
    assert kinds == ["song", "passage"]


def test_deplacement():
    a = service.add_passage("A", "")
    service.add_passage("B", "")
    service.add_passage("C", "")
    service.move_item(a, 1)
    assert labels() == ["B", "A", "C"]
    service.move_item(a, 1)
    assert labels() == ["B", "C", "A"]
    service.move_item(a, 1)  # déjà en bas : ne bouge pas
    assert labels() == ["B", "C", "A"]
    service.move_item(a, -1)
    assert labels() == ["B", "A", "C"]


def test_retrait_et_vidage():
    a = service.add_passage("A", "")
    service.add_passage("B", "")
    service.remove_item(a)
    assert labels() == ["B"]
    service.clear_items()
    assert labels() == []


def test_suppression_chant_retire_du_culte():
    song_id = database.save_song(None, "Chant", "x")
    service.add_song(song_id, "Chant")
    service.add_passage("Jean 1:1", "")
    database.delete_song(song_id)
    assert labels() == ["Jean 1:1"]


def test_renommage_chant_synchronise_le_culte():
    song_id = database.save_song(None, "Ancien titre", "x")
    service.add_song(song_id, "Ancien titre")
    database.save_song(song_id, "Nouveau titre", "x")
    service.update_song_label(song_id, "Nouveau titre")
    assert labels() == ["Nouveau titre"]
