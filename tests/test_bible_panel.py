"""Test du panneau Bible en offscreen, avec la Bible embarquée réelle."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from logos.data import bible, database


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
    database.init_db()


def test_selection_d_un_verset(qapp):
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    assert len(panel._books) == 66

    # Jean 3:16 (le navigateur sélectionne un verset précis)
    panel._select_book(43)  # Jean
    assert panel._book["name"] == "Jean"
    panel._select_chapter(3)
    panel._select_verse(16)

    label, content = panel.current_passage()
    assert label == "Jean 3:16"
    slides = content.split("\n\n")
    assert len(slides) == 1
    assert "Dieu a tant aimé le monde" in slides[0]
    assert slides[0].endswith("Jean 3:16")


def test_defaut_actes_et_recherche(qapp):
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    # Livre par défaut : Actes (id 44), chapitre 1 (comme la maquette)
    assert panel._book["id"] == 44
    assert panel._chapter == 1
    assert panel.reference_label.text() == f"{panel._book['name']} 1"

    # La recherche masque les livres qui ne correspondent pas
    panel.search_edit.setText("jean")
    assert panel._book_cards[43].isVisibleTo(panel)      # Jean reste visible
    assert not panel._book_cards[1].isVisibleTo(panel)   # Genèse masquée
    panel.search_edit.setText("")
    assert panel._book_cards[1].isVisibleTo(panel)


def test_deck_du_chapitre(qapp):
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    panel._select_book(43)   # Jean
    panel._select_chapter(3)
    panel._select_verse(16)

    deck, index = panel.current_deck()
    assert index == 15                       # verset 16 -> index 15
    assert "Dieu a tant aimé le monde" in deck[index]
    assert deck[index].endswith("Jean 3:16")


def test_projeter_emet_le_signal(qapp):
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    recu = []
    panel.project_requested.connect(lambda: recu.append(True))
    panel._on_project_clicked()
    assert recu == [True]


def test_recherche_dans_les_versets(qapp):
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    panel.verse_search_edit.setText("tant aimé le monde")
    panel._run_verse_search()  # sans attendre l'anti-rebond
    assert panel.verse_results.isVisibleTo(panel)
    assert panel.verse_results.count() == 1
    item = panel.verse_results.item(0)
    assert item.text().startswith("Jean 3:16 — ")

    # Cliquer un résultat saute au verset et referme la liste.
    panel._on_verse_result_clicked(item)
    assert not panel.verse_results.isVisibleTo(panel)
    assert (panel._book["id"], panel._chapter, panel._verse) == (43, 3, 16)

    # Requête sans correspondance : ligne « Aucun verset trouvé », non cliquable.
    panel.verse_search_edit.setText("zzzzzzzz")
    panel._run_verse_search()
    assert panel.verse_results.count() == 1
    assert panel.verse_results.item(0).data(Qt.UserRole) is None


def test_projection_partielle_d_un_verset(qapp):
    """Sélectionner un passage du verset fait démarrer la projection à cet
    endroit (« … »), et changer de verset revient au texte complet."""
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    panel._select_book(43)   # Jean
    panel._select_chapter(3)
    panel._select_verse(16)
    full_text = dict(panel._chapter_verses)[16]
    offset = full_text.index("afin que")

    # Sélection à la souris simulée : la diapo démarre à la sélection.
    panel._on_partial_selected(16, offset)
    deck, index = panel.current_deck()
    assert deck[index].startswith("…afin que")
    assert deck[index].endswith("Jean 3:16")

    # Une sélection sur un autre verset que le verset courant est ignorée.
    panel._on_partial_selected(17, 5)
    deck2, index2 = panel.current_deck()
    assert deck2[index2].startswith("…afin que")

    # Relâchement sans sélection (offset -1) ou changement de verset : complet.
    panel._on_partial_selected(16, -1)
    deck3, index3 = panel.current_deck()
    assert deck3[index3].startswith("Car Dieu a tant aimé")
    panel._on_partial_selected(16, offset)
    panel._select_verse(17)
    assert panel._partial_start == 0


def test_panneau_desactive_sans_bible(qapp):
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()  # base vide : la Bible n'est pas importée
    assert not panel.project_btn.isEnabled()
    assert panel.current_deck() == ([], 0)
