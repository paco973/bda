"""Test du panneau Bible en offscreen, avec la Bible embarquée réelle."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from logos.data import bible, database


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "songs.db")
    database.init_db()


def test_selection_d_un_passage(qapp):
    bible.ensure_imported()
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()
    assert panel.book_combo.count() == 66

    # Jean 3:16-18
    panel.book_combo.setCurrentIndex(42)
    assert panel.book_combo.currentText() == "Jean"
    panel.chapter_spin.setValue(3)
    panel.verse_from_spin.setValue(16)
    panel.verse_to_spin.setValue(18)

    label, content = panel.current_passage()
    assert label == "Jean 3:16-18"
    slides = content.split("\n\n")
    assert len(slides) == 3
    assert "Dieu a tant aimé le monde" in slides[0]
    assert slides[0].endswith("Jean 3:16")


def test_panneau_desactive_sans_bible(qapp):
    from logos.ui.bible_panel import BiblePanel

    panel = BiblePanel()  # base vide : la Bible n'est pas importée
    assert not panel.show_btn.isEnabled()
    assert not panel.add_btn.isEnabled()
