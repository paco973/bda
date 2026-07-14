"""Tests de fumée de la fenêtre de contrôle (rendu offscreen, sans écran)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from logos.data import database, bible


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "songs.db")
    database.init_db()


def test_projection_et_navigation(qapp):
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        win.title_edit.setText("Chant de test")
        win.lyrics_edit.setPlainText("Diapo un\n\nDiapo deux\n\nDiapo trois")
        win._save_song()

        assert win.song_list.count() == 1
        assert win.slide_list.count() == 3

        # Rien n'est à l'antenne tant qu'on n'a pas projeté
        assert win.controller.on_air() is None

        # « Projeter » met le mode Chants à l'antenne
        win.chants_controls.project()
        assert win.controller.is_on_air("chants")
        assert win.controller.window.label.text() == "Diapo un"

        # Naviguer met à jour la projection en direct + la liste
        win.chants_controls.go_next()
        assert win.slide_list.currentRow() == 1
        assert win.controller.window.label.text() == "Diapo deux"

        # La liste pilote aussi le poste de contrôle
        win.slide_list.setCurrentRow(2)
        assert win.controller.window.label.text() == "Diapo trois"

        # L'écran noir masque sans perdre le contenu
        win.chants_controls.toggle_blackout()
        assert win.controller.window.label.text() == ""
        win.chants_controls.toggle_blackout()
        assert win.controller.window.label.text() == "Diapo trois"
    finally:
        win.close()


def test_ordre_du_culte(qapp):
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        win.title_edit.setText("Chant culte")
        win.lyrics_edit.setPlainText("Un\n\nDeux")
        win._save_song()
        win.song_list.setCurrentRow(0)
        win._add_current_song_to_service()

        # Un passage biblique ajouté au culte (comme via le mode Bible)
        win._on_passage_add_to_service("Jean 3:16", "Texte du verset\nJean 3:16")
        assert win.service_list.count() == 2

        # Cliquer un élément du culte charge ses diapositives
        win._on_service_item_clicked(win.service_list.item(1))
        assert win.slide_list.count() == 1
        win._on_service_item_clicked(win.service_list.item(0))
        assert win.slide_list.count() == 2

        # Réordonner : le chant descend en position 2
        win.service_list.setCurrentRow(0)
        win._move_service_item(1)
        assert win.service_list.item(0).text().endswith("Jean 3:16")
    finally:
        win.close()


def test_exclusivite_de_projection(qapp):
    """Un seul mode à l'antenne : projeter depuis la Bible coupe les Chants."""
    bible.ensure_imported()
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        win.title_edit.setText("Chant")
        win.lyrics_edit.setPlainText("A\n\nB")
        win._save_song()
        win.chants_controls.project()
        assert win.controller.is_on_air("chants")

        # Prépare Jean 3:16 puis projette depuis la Bible
        win.bible_panel._select_book(43)  # Jean
        win.bible_panel._select_chapter(3)
        win.bible_panel._select_verse(16)
        win.bible_controls.project()

        # La Bible prend l'antenne, les Chants sont coupés
        assert win.controller.is_on_air("bible")
        assert not win.controller.is_on_air("chants")
        assert "Dieu a tant aimé le monde" in win.controller.window.label.text()
    finally:
        win.close()
