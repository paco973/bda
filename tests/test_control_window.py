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


def test_raccourcis_presentation(qapp):
    """Flèches seules = diapositive précédente/suivante, B = écran noir."""
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QKeyEvent
    bible.ensure_imported()
    from logos.ui.control_window import ControlWindow

    def key(win, k):
        win.keyPressEvent(QKeyEvent(QEvent.KeyPress, k, Qt.KeyboardModifier.NoModifier))

    win = ControlWindow()
    try:
        win._open_bible()
        win.bible_panel._select_book(43)
        win.bible_panel._select_chapter(3)
        win.bible_panel._select_verse(16)
        win._on_bible_project()
        assert "Jean 3:16" in win.controller.window.label.text()

        key(win, Qt.Key_Right)
        assert "Jean 3:17" in win.controller.window.label.text()
        key(win, Qt.Key_Left)
        assert "Jean 3:16" in win.controller.window.label.text()
        key(win, Qt.Key_B)
        assert win.controller.blackout()
        key(win, Qt.Key_B)
        assert not win.controller.blackout()

        # Sur l'accueil (aucun mode affiché), les touches sont sans effet.
        win._go_home()
        key(win, Qt.Key_Right)
        assert "Jean 3:16" in win.controller.window.label.text()
    finally:
        win.close()


def test_echap_quitte_la_presentation(qapp):
    """Échap arrête la projection, comme dans un logiciel de diaporama — sauf
    dans un champ de recherche rempli, où il vide d'abord le champ : couper le
    direct par réflexe en effaçant une recherche serait le pire moment."""
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QKeyEvent
    bible.ensure_imported()
    from logos.ui.control_window import ControlWindow

    def echap(win):
        win.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )

    win = ControlWindow()
    try:
        win._open_bible()
        win.bible_panel._select_book(43)
        win.bible_panel._select_chapter(3)
        win.bible_panel._select_verse(16)
        win._on_bible_project()
        assert win.controller.is_on_air("bible")

        echap(win)
        assert win.controller.on_air() is None
        assert not win.controller.window.isVisible()

        # Une recherche en cours protège le direct.
        win._on_bible_project()
        win.bible_panel.search_edit.setText("Jean")
        win.bible_panel.search_edit.setFocus()
        echap(win)
        assert win.bible_panel.search_edit.text() == ""
        assert win.controller.is_on_air("bible")   # toujours à l'antenne
        echap(win)                                 # champ vide : Échap quitte
        assert win.controller.on_air() is None

        # Depuis l'accueil aussi : arrêter la projection n'est pas lié au mode.
        win._on_bible_project()
        win._go_home()
        echap(win)
        assert win.controller.on_air() is None

        # Et depuis la fenêtre de projection, qui peut avoir le focus clavier.
        win._open_bible()
        win._on_bible_project()
        echap(win.controller.window)
        assert win.controller.on_air() is None
    finally:
        win.close()


def test_reglages_persistants(qapp):
    """Taille du texte et versets par diapositive sont restaurés au relancement."""
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        win.controller.set_font_size(72)
        win._open_bible()
        win.bible_panel.verses_spin.setValue(4)
    finally:
        win.close()

    win2 = ControlWindow()
    try:
        assert win2.controller.font_size() == 72
        # Le réglage est restauré avant même que la page Bible n'existe...
        assert win2.bible_page is None
        assert win2._verses_per_slide == 4
        # ... puis posé sur le panneau à sa construction.
        win2._open_bible()
        assert win2.bible_panel.verses_spin.value() == 4
    finally:
        win2.close()


def test_pages_de_mode_construites_a_la_demande(qapp):
    """Le démarrage ne construit que l'accueil : peupler les deux navigateurs
    d'avance coûtait plusieurs secondes de lancement."""
    from logos.ui.control_window import ControlWindow

    win = ControlWindow()
    try:
        assert win.bible_page is None and win.bible_panel is None
        assert win.predication_page is None and win.predication_panel is None
        assert win._active_controls() is None

        win._open_bible()
        assert win.bible_panel is not None
        assert win.predication_page is None  # l'autre mode reste inconstruit
        assert win._active_controls() is win.bible_controls

        page = win.bible_page
        win._go_home()
        win._open_bible()
        assert win.bible_page is page  # rouverte, pas reconstruite
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
