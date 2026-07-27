"""Tests de fumée de la fenêtre principale (rendu offscreen, sans écran)."""
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
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
    database.init_db()


def test_navigation_accueil_bible(qapp):
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        # Démarre sur l'accueil ; la barre de réglages y est masquée.
        assert win.stack.currentWidget() is win.home_page
        assert win.settings_bar.isHidden()

        # Ouvre la Bible : la barre de réglages globale devient visible.
        win._open_bible()
        assert win.stack.currentWidget() is win.bible_page
        assert not win.settings_bar.isHidden()

        win._go_home()
        assert win.stack.currentWidget() is win.home_page
    finally:
        win.close()


def test_projection_d_un_verset(qapp):
    bible.ensure_imported()
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        win._open_bible()
        win.bible_panel._select_book(43)   # Jean
        win.bible_panel._select_chapter(3)
        win.bible_panel._select_verse(16)

        # Rien à l'antenne tant qu'on n'a pas projeté
        assert win.controller.on_air() is None

        # « Projeter le verset » met la Bible à l'antenne
        win._on_bible_project()
        assert win.controller.is_on_air("bible")
        assert "Dieu a tant aimé le monde" in win.controller.window.label.text()

        # Navigation depuis le poste de contrôle : verset suivant
        win.bible_controls.go_next()
        assert "Jean 3:17" in win.controller.window.label.text()

        # L'écran noir masque sans perdre le contenu
        win.bible_controls.toggle_blackout()
        assert win.controller.window.label.text() == ""
        win.bible_controls.toggle_blackout()
        assert "Jean 3:17" in win.controller.window.label.text()
    finally:
        win.close()
