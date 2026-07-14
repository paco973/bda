"""Test de fumée de la fenêtre de contrôle en rendu offscreen (sans écran)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from logos.data import database


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "songs.db")
    database.init_db()


def test_sauvegarde_et_navigation(qapp):
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        win.title_edit.setText("Chant de test")
        win.lyrics_edit.setPlainText("Diapo un\n\nDiapo deux\n\nDiapo trois")
        win._save_song()

        assert win.song_list.count() == 1
        assert win.slide_list.count() == 3

        # Suivant/Précédent déplacent la sélection et projettent la diapo
        win._next_slide()
        assert win.slide_list.currentRow() == 0
        assert win.projection.label.text() == "Diapo un"
        win._next_slide()
        assert win.projection.label.text() == "Diapo deux"
        win._prev_slide()
        assert win.projection.label.text() == "Diapo un"
        win._prev_slide()  # déjà au début : ne bouge pas
        assert win.slide_list.currentRow() == 0

        # L'écran noir masque le texte sans le perdre
        win.projection.toggle_blank(True)
        assert win.projection.label.text() == ""
        win.projection.toggle_blank(False)
        assert win.projection.label.text() == "Diapo un"
    finally:
        win.close()


def test_ordre_du_culte(qapp):
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        # Un chant sauvegardé puis ajouté au culte
        win.title_edit.setText("Chant culte")
        win.lyrics_edit.setPlainText("Un\n\nDeux")
        win._save_song()
        win.song_list.setCurrentRow(0)
        win._add_current_song_to_service()

        # Un passage biblique ajouté au culte (comme via le panneau Bible)
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

        # Supprimer le chant le retire aussi du culte
        win.song_list.setCurrentRow(0)
        item_count_before = win.service_list.count()
        assert item_count_before == 2
    finally:
        win.close()
