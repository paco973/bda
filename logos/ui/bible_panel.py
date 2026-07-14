"""
Panneau de sélection d'un passage biblique (livre, chapitre, versets).
Émet des signaux vers la fenêtre de contrôle — aucune logique de projection ici.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QSpinBox,
    QPushButton,
    QLabel,
)

from logos.data import bible, slides


class BiblePanel(QWidget):
    # (label du passage, texte projetable) — la fenêtre de contrôle décide quoi en faire
    display_requested = Signal(str, str)
    service_add_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Livre"))
        self.book_combo = QComboBox()
        layout.addWidget(self.book_combo)

        ref_row = QHBoxLayout()
        ref_row.addWidget(QLabel("Chapitre"))
        self.chapter_spin = QSpinBox()
        self.chapter_spin.setMinimum(1)
        ref_row.addWidget(self.chapter_spin)
        ref_row.addWidget(QLabel("Versets"))
        self.verse_from_spin = QSpinBox()
        self.verse_from_spin.setMinimum(1)
        ref_row.addWidget(self.verse_from_spin)
        ref_row.addWidget(QLabel("à"))
        self.verse_to_spin = QSpinBox()
        self.verse_to_spin.setMinimum(1)
        ref_row.addWidget(self.verse_to_spin)
        layout.addLayout(ref_row)

        self.show_btn = QPushButton("Afficher les diapositives")
        self.show_btn.clicked.connect(self._emit_display)
        layout.addWidget(self.show_btn)

        self.add_btn = QPushButton("Ajouter au culte")
        self.add_btn.clicked.connect(self._emit_service_add)
        layout.addWidget(self.add_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

        if bible.is_available():
            self.status_label.setText(bible.TRANSLATION)
            self._populate_books()
            self.book_combo.currentIndexChanged.connect(self._on_book_changed)
            self.chapter_spin.valueChanged.connect(self._on_chapter_changed)
            self.verse_from_spin.valueChanged.connect(self.verse_to_spin.setMinimum)
            self._on_book_changed()
        else:
            self.status_label.setText(
                "Bible non disponible : fichier logos/assets/bible_ls1910.json.gz "
                "manquant lors du premier lancement."
            )
            for widget in (self.book_combo, self.chapter_spin, self.verse_from_spin,
                           self.verse_to_spin, self.show_btn, self.add_btn):
                widget.setEnabled(False)

    # ---------- Sélection ----------
    def _populate_books(self):
        for row in bible.get_books():
            self.book_combo.addItem(row["name"], row)

    def _on_book_changed(self, _index=0):
        book = self.book_combo.currentData()
        if book is None:
            return
        self.chapter_spin.setMaximum(book["chapters"])
        self.chapter_spin.setValue(1)
        self._on_chapter_changed(1)

    def _on_chapter_changed(self, chapter: int):
        book = self.book_combo.currentData()
        if book is None:
            return
        count = bible.get_verse_count(book["id"], chapter)
        self.verse_from_spin.setMaximum(max(count, 1))
        self.verse_to_spin.setMaximum(max(count, 1))
        self.verse_from_spin.setValue(1)
        self.verse_to_spin.setValue(1)

    def current_passage(self):
        """(label, texte projetable) du passage sélectionné, ou None si vide."""
        book = self.book_combo.currentData()
        if book is None:
            return None
        chapter = self.chapter_spin.value()
        verse_start = self.verse_from_spin.value()
        verse_end = max(self.verse_to_spin.value(), verse_start)
        verses = bible.get_passage(book["id"], chapter, verse_start, verse_end)
        if not verses:
            return None
        label = slides.passage_label(book["name"], chapter, verse_start, verse_end)
        content = slides.passage_to_text(book["name"], chapter, verses)
        return label, content

    # ---------- Signaux ----------
    def _emit_display(self):
        passage = self.current_passage()
        if passage is not None:
            self.display_requested.emit(*passage)

    def _emit_service_add(self):
        passage = self.current_passage()
        if passage is not None:
            self.service_add_requested.emit(*passage)
