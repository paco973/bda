"""Choix de l'écran de projection (écrans simulés, rendu offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from logos.data import database


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
    database.init_db()


class FakeScreen:
    """Le strict nécessaire de `QScreen` pour le contrôleur et la barre de réglages."""

    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def geometry(self):
        return QRect(0, 0, 1920, 1080)

    def __repr__(self):
        return f"FakeScreen({self._name})"


POSTE = FakeScreen("Poste")
PROJECTEUR = FakeScreen("Projecteur")
AUTRE = FakeScreen("Autre")


def _controller(qapp, screens, primary=POSTE):
    from logos.ui.projection_controller import ProjectionController

    state = {"screens": list(screens)}
    ProjectionController.screens = lambda self: state["screens"]
    ProjectionController.primary_screen = lambda self: primary
    controller = ProjectionController()
    return controller, state


@pytest.fixture(autouse=True)
def restore_controller_methods(monkeypatch):
    """Les tests remplacent `screens`/`primary_screen` sur la classe : on les rétablit."""
    from logos.ui.projection_controller import ProjectionController

    monkeypatch.setattr(ProjectionController, "screens", ProjectionController.screens)
    monkeypatch.setattr(
        ProjectionController, "primary_screen", ProjectionController.primary_screen
    )


def test_defaut_second_ecran_quel_que_soit_l_ordre(qapp):
    """Le second écran est celui qui n'est pas l'écran principal, même détecté
    en premier : l'ordre de `screens()` ne désigne pas le projecteur."""
    controller, _ = _controller(qapp, [PROJECTEUR, POSTE])
    assert controller.screen() is PROJECTEUR
    controller, _ = _controller(qapp, [POSTE, PROJECTEUR])
    assert controller.screen() is PROJECTEUR


def test_seul_ecran_ou_aucun(qapp):
    controller, _ = _controller(qapp, [POSTE])
    assert controller.screen() is POSTE
    controller, _ = _controller(qapp, [])
    assert controller.screen() is None


def test_projecteur_branche_apres_le_lancement(qapp):
    """Lancée avec le seul écran du poste, l'appli adopte le projecteur dès son
    branchement, et y déplace la projection si elle est à l'antenne."""
    controller, state = _controller(qapp, [POSTE])
    controller.register_mode("bible", "Bible")
    shown = []
    controller.window.show_on_screen = shown.append
    assert controller.project("bible", "Jean 3:16")
    assert shown == [POSTE]

    state["screens"].append(PROJECTEUR)
    controller.refresh_screens()
    assert controller.screen() is PROJECTEUR
    assert controller.on_air() == "bible"        # pas coupée, déplacée
    assert shown[-1] is PROJECTEUR


def test_choix_explicite_d_un_ecran_secondaire_conserve(qapp):
    """Un écran secondaire choisi par l'opérateur survit au branchement d'un
    écran de plus : seule la cible « écran du poste » est réélue."""
    controller, state = _controller(qapp, [POSTE, PROJECTEUR, AUTRE])
    controller.set_screen(AUTRE)
    state["screens"] = [POSTE, PROJECTEUR, AUTRE, FakeScreen("Encore")]
    controller.refresh_screens()
    assert controller.screen() is AUTRE


def test_disparition_de_la_cible_coupe_et_reelit(qapp):
    controller, state = _controller(qapp, [POSTE, PROJECTEUR])
    controller.register_mode("bible", "Bible")
    controller.window.show_on_screen = lambda _s: None
    assert controller.project("bible", "Jean 3:16")
    state["screens"] = [POSTE]
    controller.refresh_screens()
    assert controller.on_air() is None
    assert controller.screen() is POSTE


def test_ecran_principal_memorise_ne_prime_pas_sur_un_second_ecran(qapp):
    """Un nom d'écran mémorisé qui désigne l'écran du poste est la trace d'une
    session sans projecteur : avec un second écran présent, ce dernier gagne."""
    from logos.data.database import set_meta
    from logos.ui.projection_controller import ProjectionController
    from logos.ui.control_window import ControlWindow

    ProjectionController.screens = lambda self: [POSTE, PROJECTEUR]
    ProjectionController.primary_screen = lambda self: POSTE
    set_meta("ui_screen_name", "Poste")
    win = ControlWindow()
    try:
        assert win.controller.screen() is PROJECTEUR
    finally:
        win.close()

    # Un écran secondaire mémorisé, lui, est bien retrouvé.
    ProjectionController.screens = lambda self: [POSTE, PROJECTEUR, AUTRE]
    set_meta("ui_screen_name", "Autre")
    win = ControlWindow()
    try:
        assert win.controller.screen() is AUTRE
    finally:
        win.close()
