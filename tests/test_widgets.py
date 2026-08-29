"""Tests des widgets génériques partagés (offscreen, sans écran)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _column(qapp):
    from logos.ui.widgets import ProgressiveRows

    host = QWidget()
    layout = QVBoxLayout(host)
    layout.addStretch()
    return host, layout, ProgressiveRows(layout, first=5, batch=5)


def _placed(layout):
    """Lignes réellement posées (l'étirement final ne compte pas)."""
    return layout.count() - 1


def test_lignes_posees_par_lots(qapp):
    """Seul le premier lot est posé tout de suite : mettre en page des centaines
    de lignes de texte replié figerait la fenêtre."""
    from logos.ui.widgets import NumberedTextRow

    host, layout, rows = _column(qapp)
    widgets = [NumberedTextRow(i, f"Texte {i}") for i in range(1, 31)]
    rows.reset(widgets)

    assert _placed(layout) == 5
    # Le reste arrive quand la boucle d'événements est libre.
    for _ in range(20):
        qapp.processEvents()
    assert _placed(layout) == 30
    # L'ordre est préservé et l'étirement reste en dernier.
    assert layout.itemAt(0).widget() is widgets[0]
    assert layout.itemAt(29).widget() is widgets[29]
    assert layout.itemAt(30).widget() is None
    host.deleteLater()


def test_ligne_posee_a_la_demande(qapp):
    """Une ligne hors du premier lot n'a pas de géométrie : on ne pourrait pas y
    défiler. `ensure_placed` la pose (avec tout ce qui la précède) sur demande."""
    from logos.ui.widgets import NumberedTextRow

    host, layout, rows = _column(qapp)
    widgets = [NumberedTextRow(i, f"Texte {i}") for i in range(1, 31)]
    rows.reset(widgets)
    assert _placed(layout) == 5

    rows.ensure_placed(widgets[19])       # 20e ligne
    assert _placed(layout) == 20
    assert widgets[19].parent() is host

    rows.ensure_placed(widgets[2])        # déjà posée : sans effet
    assert _placed(layout) == 20
    host.deleteLater()


def test_reset_annule_le_reliquat(qapp):
    """Changer de chapitre ou de prédication pendant le remplissage ne doit pas
    laisser des lignes de l'ancien contenu arriver après coup."""
    from logos.ui.widgets import NumberedTextRow

    host, layout, rows = _column(qapp)
    rows.reset([NumberedTextRow(i, f"Ancien {i}") for i in range(1, 31)])
    nouveaux = [NumberedTextRow(i, f"Nouveau {i}") for i in range(1, 9)]
    rows.reset(nouveaux)

    for _ in range(20):
        qapp.processEvents()
    assert _placed(layout) == 8
    assert all(layout.itemAt(i).widget() is nouveaux[i] for i in range(8))
    host.deleteLater()


def test_mesures_memorisees_et_invalidees(qapp):
    """La hauteur d'une ligne est mémorisée (Qt remesure toutes les lignes d'une
    colonne dès qu'une seule change), mais recalculée quand l'état actif change :
    la ligne sélectionnée n'a pas la même mise en page."""
    from logos.ui.widgets import NumberedTextRow

    row = NumberedTextRow(1, "Un texte assez long pour être replié " * 6)
    hauteur = row.heightForWidth(260)
    assert row._heights == {260: hauteur}

    row.heightForWidth(260)               # deuxième appel : servi par la mémoire
    assert row._heights == {260: hauteur}

    row.set_active(True)
    assert row._heights == {}             # l'état a changé : mesure périmée
    assert row.heightForWidth(260) > 0
