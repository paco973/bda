"""
Navigateur biblique (fenêtre dédiée), fidèle à la maquette « Bible Navigator ».

Disposition :
  - barre supérieure : logo, titre, recherche de livre, bascule LSG/KJV, état écran ;
  - colonne de lecture (gauche) : testament, référence, versets cliquables, actions ;
  - grille des livres (haut-droite) puis grilles chapitres / versets (bas-droite) ;
  - barre de statut.

Aucune logique de projection ici : le panneau émet des signaux vers la fenêtre
de contrôle, qui reste seule maîtresse de la fenêtre de projection.
"""
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QFontMetrics
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLayout,
    QScrollArea,
    QSizePolicy,
)

from logos.data import bible, slides
from logos.ui import theme

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


# Styles inline des boutons de lecture (indépendants du cascade Qt des parents
# stylés, qui neutralise l'accent doré des QPushButton primaires).
def _btn_primary_style() -> str:
    return (
        f"QPushButton {{ background:{theme.COLOR_PRIMARY}; color:{theme.COLOR_TEXT_ON_PRIMARY};"
        f" border:none; border-radius:6px; padding:11px; font-size:13px; font-weight:700; }}"
        f"QPushButton:hover {{ background:{theme.COLOR_PRIMARY_HOVER}; }}"
        f"QPushButton:disabled {{ background:{theme.COLOR_SURFACE_ALT}; color:{theme.BRONZE}; }}"
    )


def _btn_secondary_style() -> str:
    return (
        f"QPushButton {{ background:transparent; color:{theme.COLOR_TEXT};"
        f" border:1px solid {theme.COLOR_BORDER}; border-radius:6px; padding:11px 14px;"
        f" font-size:13px; font-weight:600; }}"
        f"QPushButton:hover {{ background:{theme.COLOR_SURFACE_ALT}; border-color:{theme.COLOR_PRIMARY}; }}"
        f"QPushButton:disabled {{ color:{theme.BRONZE}; border-color:{theme.COLOR_BORDER_SUBTLE}; }}"
    )


def _btn_danger_style() -> str:
    return (
        f"QPushButton {{ background:{theme.COLOR_DANGER}; color:white;"
        f" border:1px solid {theme.COLOR_DANGER}; border-radius:6px; padding:11px 14px;"
        f" font-size:13px; font-weight:700; }}"
        f"QPushButton:hover {{ background:{theme.COLOR_DANGER_HOVER}; border-color:{theme.COLOR_DANGER_HOVER}; }}"
    )


# --------------------------------------------------------------------------- #
#  Disposition en flux (les cartes se replacent sur plusieurs lignes)
# --------------------------------------------------------------------------- #
class FlowLayout(QLayout):
    """Dispose les widgets de gauche à droite en passant à la ligne au besoin."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect, test_only):
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class _FlowHost(QWidget):
    """Conteneur d'une FlowLayout qui déclare sa hauteur pour permettre le
    défilement vertical à l'intérieur d'un QScrollArea (widgetResizable)."""

    def __init__(self, spacing=6):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self.flow = FlowLayout(self, spacing=spacing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self.flow.heightForWidth(self.width()))


# --------------------------------------------------------------------------- #
#  Petits composants
# --------------------------------------------------------------------------- #
class _BookCard(QFrame):
    """Carte d'un livre : abréviation en gras + nom complet en dessous."""

    clicked = Signal(int)

    def __init__(self, book):
        super().__init__()
        self.book_id = book["id"]
        self.setFixedSize(76, 46)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(book["name"])

        col = QVBoxLayout(self)
        col.setContentsMargins(4, 5, 4, 5)
        col.setSpacing(2)
        self.abbr_label = QLabel(bible.book_abbreviation(self.book_id))
        self.abbr_label.setAlignment(Qt.AlignCenter)
        self.name_label = QLabel()
        self.name_label.setAlignment(Qt.AlignCenter)
        elided = QFontMetrics(self.name_label.font()).elidedText(
            book["name"], Qt.ElideRight, 66
        )
        self.name_label.setText(elided)
        col.addWidget(self.abbr_label)
        col.addWidget(self.name_label)

        self.set_active(False)

    def set_active(self, active: bool):
        abbr = theme.COLOR_TEXT_ON_PRIMARY if active else theme.COLOR_TEXT
        name = theme.COLOR_ON_PRIMARY_MUTED if active else theme.BRONZE
        bg = theme.COLOR_PRIMARY if active else theme.COLOR_SURFACE_ALT
        border = theme.COLOR_PRIMARY if active else theme.COLOR_BORDER_SUBTLE
        self.setStyleSheet(
            f"_BookCard {{ background:{bg}; border:1px solid {border}; border-radius:6px; }}"
        )
        self.abbr_label.setStyleSheet(
            f"color:{abbr}; font-size:14px; font-weight:700; background:transparent; border:none;"
        )
        self.name_label.setStyleSheet(
            f"color:{name}; font-size:9px; font-weight:600; background:transparent; border:none;"
        )

    def set_dimmed(self, dimmed: bool):
        self.setVisible(not dimmed)

    def mousePressEvent(self, event):
        self.clicked.emit(self.book_id)


class _NumButton(QPushButton):
    """Carré numéroté d'un chapitre ou d'un verset."""

    picked = Signal(int)

    def __init__(self, number: int):
        super().__init__(str(number))
        self.number = number
        self.setFixedSize(42, 42)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: self.picked.emit(self.number))
        self.set_active(False)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.COLOR_PRIMARY};"
                f" color:{theme.COLOR_TEXT_ON_PRIMARY};"
                f" border:1px solid {theme.COLOR_PRIMARY}; border-radius:5px;"
                f" font-size:13px; font-weight:700; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.COLOR_SURFACE_ALT};"
                f" color:{theme.COLOR_TEXT_MUTED};"
                f" border:1px solid {theme.COLOR_BORDER_SUBTLE}; border-radius:5px;"
                f" font-size:13px; font-weight:600; }}"
                f" QPushButton:hover {{ border-color:{theme.COLOR_PRIMARY};"
                f" color:{theme.COLOR_TEXT}; }}"
            )


class _VerseRow(QLabel):
    """Un verset dans la colonne de lecture ; numéro en exposant, clic pour choisir."""

    clicked = Signal(int)

    def __init__(self, verse: int, text: str):
        super().__init__()
        self.verse = verse
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setCursor(Qt.PointingHandCursor)
        self._text = text
        self.set_active(False)

    def set_active(self, active: bool):
        num_color = theme.COLOR_ON_PRIMARY_MUTED if active else theme.BRONZE
        text_color = theme.COLOR_TEXT_ON_PRIMARY if active else theme.COLOR_TEXT
        bg = theme.COLOR_PRIMARY if active else "transparent"
        self.setText(
            f'<sup style="color:{num_color}; font-family:sans-serif;'
            f' font-weight:700;">{self.verse}</sup> {self._text}'
        )
        self.setStyleSheet(
            f"color:{text_color}; background:{bg}; border-radius:5px;"
            f" padding:{'6px 9px' if active else '2px 3px'};"
            f" font-family:{theme.READING_FONT_FAMILY}; font-size:16px; font-weight:500;"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.verse)


def _circular_logo(size: int):
    """Pixmap circulaire du logo, ou None si l'asset est absent."""
    if not _LOGO_PATH.exists():
        return None
    src = QPixmap(str(_LOGO_PATH))
    if src.isNull():
        return None
    src = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return result


# --------------------------------------------------------------------------- #
#  Panneau principal
# --------------------------------------------------------------------------- #
class BiblePanel(QWidget):
    selection_changed = Signal()          # livre/chapitre/verset (jeu de diapos) modifié
    project_requested = Signal()          # « Projeter le verset » cliqué
    service_add_requested = Signal(str, str)
    close_requested = Signal()            # retour à l'accueil (bouton « ‹ Retour »)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{theme.COLOR_BACKGROUND};")

        self._books = []            # liste de dicts {id, name, chapters}
        self._book = None           # livre sélectionné
        self._chapter = 1
        self._verse = None          # verset sélectionné (int) ou None
        self._chapter_verses = []   # (verse, text) du chapitre courant
        self._book_cards = {}       # id -> _BookCard

        self._build_ui()

        if bible.is_available():
            self._load_books()
        else:
            self._show_unavailable()

    # ---------------------------- Construction ---------------------------- #
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_reading_column())
        body.addWidget(self._build_navigation_column(), 1)
        root.addLayout(body, 1)

        root.addWidget(self._build_statusbar())

    def _build_topbar(self):
        bar = QFrame()
        bar.setStyleSheet(
            f"background:{theme.COLOR_SURFACE};"
            f" border-bottom:1px solid {theme.COLOR_BORDER_SUBTLE};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 10, 18, 10)
        row.setSpacing(14)

        back_btn = QPushButton("‹ Retour")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setToolTip("Revenir à la fenêtre de contrôle")
        back_btn.setStyleSheet(_btn_secondary_style())
        back_btn.clicked.connect(self.close_requested.emit)
        row.addWidget(back_btn)

        logo = _circular_logo(34)
        if logo is not None:
            logo_label = QLabel()
            logo_label.setPixmap(logo)
            logo_label.setFixedSize(34, 34)
            row.addWidget(logo_label)

        title = QLabel(theme.APP_NAME)
        title.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:15px; font-weight:700; background:transparent;"
        )
        row.addWidget(title)

        search_box = QFrame()
        search_box.setStyleSheet(
            f"background:{theme.COLOR_SURFACE_ALT}; border:1px solid {theme.COLOR_BORDER};"
            f" border-radius:6px;"
        )
        search_row = QHBoxLayout(search_box)
        search_row.setContentsMargins(12, 4, 12, 4)
        search_row.setSpacing(8)
        glass = QLabel("⌕")
        glass.setStyleSheet(f"color:{theme.BRONZE}; background:transparent; font-size:13px;")
        search_row.addWidget(glass)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher un livre…")
        self.search_edit.setFixedWidth(220)
        self.search_edit.setStyleSheet(
            f"background:transparent; border:none; color:{theme.COLOR_TEXT}; font-size:13px;"
        )
        self.search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_edit)
        row.addWidget(search_box)

        row.addStretch()

        # Bascule LSG / KJV (seule la LSG est embarquée).
        toggle = QFrame()
        toggle.setStyleSheet(
            f"background:{theme.COLOR_SURFACE_ALT}; border:1px solid {theme.COLOR_BORDER_SUBTLE};"
            f" border-radius:6px;"
        )
        toggle_row = QHBoxLayout(toggle)
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(0)
        lsg = QLabel(f"  {bible.TRANSLATION_CODE}  ")
        lsg.setStyleSheet(
            f"color:{theme.COLOR_TEXT_ON_PRIMARY}; background:{theme.COLOR_PRIMARY};"
            f" font-size:12px; font-weight:700; padding:6px 4px; border-radius:5px;"
        )
        kjv = QLabel("  KJV  ")
        kjv.setToolTip("Version indisponible (application hors ligne, LSG uniquement).")
        kjv.setStyleSheet(
            f"color:{theme.BRONZE}; background:transparent; font-size:12px;"
            f" font-weight:600; padding:6px 4px;"
        )
        toggle_row.addWidget(lsg)
        toggle_row.addWidget(kjv)
        row.addWidget(toggle)
        return bar

    def _build_reading_column(self):
        col = QFrame()
        col.setFixedWidth(360)
        col.setStyleSheet(
            f"background:{theme.COLOR_SURFACE};"
            f" border-right:1px solid {theme.COLOR_SURFACE_ALT};"
        )
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(f"border-bottom:1px solid {theme.COLOR_SURFACE_ALT};")
        header_col = QVBoxLayout(header)
        header_col.setContentsMargins(20, 16, 20, 12)
        header_col.setSpacing(3)
        self.testament_label = QLabel("")
        self.testament_label.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        self.reference_label = QLabel("")
        self.reference_label.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:22px; font-weight:700; background:transparent;"
        )
        header_col.addWidget(self.testament_label)
        header_col.addWidget(self.reference_label)
        layout.addWidget(header)

        # Zone de lecture défilante.
        self.reading_area = QScrollArea()
        self.reading_area.setWidgetResizable(True)
        self.reading_area.setFrameShape(QFrame.NoFrame)
        self.reading_area.setStyleSheet("background:transparent; border:none;")
        self.reading_host = QWidget()
        self.reading_host.setStyleSheet("background:transparent;")
        self.reading_layout = QVBoxLayout(self.reading_host)
        self.reading_layout.setContentsMargins(20, 16, 20, 24)
        self.reading_layout.setSpacing(4)
        self.reading_layout.addStretch()
        self.reading_area.setWidget(self.reading_host)
        layout.addWidget(self.reading_area, 1)

        footer = QFrame()
        footer.setStyleSheet(f"border-top:1px solid {theme.COLOR_SURFACE_ALT};")
        footer_col = QVBoxLayout(footer)
        footer_col.setContentsMargins(20, 12, 20, 12)
        footer_col.setSpacing(8)

        self.project_btn = QPushButton("Projeter le verset")
        self.project_btn.setCursor(Qt.PointingHandCursor)
        self.project_btn.setStyleSheet(_btn_primary_style())
        self.project_btn.clicked.connect(self._on_project_clicked)
        footer_col.addWidget(self.project_btn)

        self.add_btn = QPushButton("＋ Ajouter au culte")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet(_btn_secondary_style())
        self.add_btn.clicked.connect(self._emit_service_add)
        footer_col.addWidget(self.add_btn)
        layout.addWidget(footer)
        return col

    def _build_navigation_column(self):
        col = QWidget()
        col.setStyleSheet(f"background:{theme.COLOR_BACKGROUND};")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Livres (haut) ---
        books_wrap = QWidget()
        books_col = QVBoxLayout(books_wrap)
        books_col.setContentsMargins(22, 18, 22, 14)
        books_col.setSpacing(10)
        books_title = QLabel("Livres")
        books_title.setStyleSheet(
            f"color:{theme.COLOR_TEXT_MUTED}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        books_col.addWidget(books_title)

        books_scroll = QScrollArea()
        books_scroll.setWidgetResizable(True)
        books_scroll.setFrameShape(QFrame.NoFrame)
        books_scroll.setStyleSheet("background:transparent; border:none;")
        self.books_host = _FlowHost(spacing=6)
        self.books_flow = self.books_host.flow
        books_scroll.setWidget(self.books_host)
        books_col.addWidget(books_scroll, 1)
        layout.addWidget(books_wrap, 1)

        # --- Chapitres + versets (bas) ---
        bottom = QFrame()
        bottom.setStyleSheet(
            f"background:{theme.COLOR_SURFACE_SUNKEN};"
            f" border-top:1px solid {theme.COLOR_SURFACE_ALT};"
        )
        bottom.setMaximumHeight(300)
        bottom_row = QHBoxLayout(bottom)
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(0)

        # Chapitres
        chap_wrap = QFrame()
        chap_wrap.setStyleSheet(f"border-right:1px solid {theme.COLOR_SURFACE_ALT};")
        chap_col = QVBoxLayout(chap_wrap)
        chap_col.setContentsMargins(18, 14, 18, 14)
        chap_col.setSpacing(10)
        chap_head = QHBoxLayout()
        chap_head.setSpacing(8)
        chap_title = QLabel("Chapitre")
        chap_title.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        self.chapter_book_label = QLabel("")
        self.chapter_book_label.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:13px; font-weight:700; background:transparent;"
        )
        chap_head.addWidget(chap_title)
        chap_head.addWidget(self.chapter_book_label)
        chap_head.addStretch()
        chap_col.addLayout(chap_head)
        chap_scroll = QScrollArea()
        chap_scroll.setWidgetResizable(True)
        chap_scroll.setFrameShape(QFrame.NoFrame)
        chap_scroll.setStyleSheet("background:transparent; border:none;")
        self.chapters_host = _FlowHost(spacing=6)
        self.chapters_flow = self.chapters_host.flow
        chap_scroll.setWidget(self.chapters_host)
        chap_col.addWidget(chap_scroll, 1)
        bottom_row.addWidget(chap_wrap, 1)

        # Versets
        verse_wrap = QWidget()
        verse_col = QVBoxLayout(verse_wrap)
        verse_col.setContentsMargins(18, 14, 18, 14)
        verse_col.setSpacing(10)
        verse_title = QLabel("Verset")
        verse_title.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        verse_col.addWidget(verse_title)
        verse_scroll = QScrollArea()
        verse_scroll.setWidgetResizable(True)
        verse_scroll.setFrameShape(QFrame.NoFrame)
        verse_scroll.setStyleSheet("background:transparent; border:none;")
        self.verses_host = _FlowHost(spacing=6)
        self.verses_flow = self.verses_host.flow
        verse_scroll.setWidget(self.verses_host)
        verse_col.addWidget(verse_scroll, 1)
        bottom_row.addWidget(verse_wrap, 1)

        layout.addWidget(bottom)
        return col

    def _build_statusbar(self):
        bar = QFrame()
        bar.setStyleSheet(
            f"background:{theme.COLOR_SURFACE}; border-top:1px solid {theme.COLOR_BORDER_SUBTLE};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 8, 18, 8)
        self.status_left = QLabel("")
        self.status_left.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:600; background:transparent;"
        )
        self.status_right = QLabel("")
        self.status_right.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:600; background:transparent;"
        )
        row.addWidget(self.status_left)
        row.addStretch()
        row.addWidget(self.status_right)
        return bar

    # ------------------------------ Données ------------------------------- #
    def _load_books(self):
        self._books = [
            {"id": row["id"], "name": row["name"], "chapters": row["chapters"]}
            for row in bible.get_books()
        ]
        for book in self._books:
            card = _BookCard(book)
            card.clicked.connect(self._select_book)
            self._book_cards[book["id"]] = card
            self.books_flow.addWidget(card)

        # Livre par défaut : Actes (comme la maquette), sinon le premier.
        default = next((b for b in self._books if b["id"] == 44), self._books[0])
        self._select_book(default["id"])

    def _show_unavailable(self):
        for widget in (self.project_btn, self.add_btn, self.search_edit):
            widget.setEnabled(False)
        message = QLabel(
            "Bible non disponible : fichier logos/assets/bible_ls1910.json.gz "
            "manquant lors du premier lancement."
        )
        message.setWordWrap(True)
        message.setStyleSheet(
            f"color:{theme.COLOR_TEXT_MUTED}; font-size:14px; background:transparent;"
        )
        self.reading_layout.insertWidget(0, message)
        self.status_left.setText(bible.TRANSLATION)

    # --------------------------- Sélection -------------------------------- #
    def _find_book(self, book_id):
        return next((b for b in self._books if b["id"] == book_id), None)

    def _select_book(self, book_id):
        book = self._find_book(book_id)
        if book is None:
            return
        for bid, card in self._book_cards.items():
            card.set_active(bid == book_id)
        self._book = book
        self._chapter = 1
        self._verse = None
        self.chapter_book_label.setText(book["name"])
        self._rebuild_chapters()
        self._load_chapter()

    def _rebuild_chapters(self):
        _clear_layout(self.chapters_flow)
        for n in range(1, self._book["chapters"] + 1):
            btn = _NumButton(n)
            btn.set_active(n == self._chapter)
            btn.picked.connect(self._select_chapter)
            self.chapters_flow.addWidget(btn)

    def _select_chapter(self, chapter):
        self._chapter = chapter
        self._verse = None
        for i in range(self.chapters_flow.count()):
            btn = self.chapters_flow.itemAt(i).widget()
            if isinstance(btn, _NumButton):
                btn.set_active(btn.number == chapter)
        self._load_chapter()

    def _load_chapter(self):
        verses = bible.get_chapter(self._book["id"], self._chapter)
        self._chapter_verses = verses
        self.testament_label.setText(bible.testament(self._book["id"]).upper())
        self.reference_label.setText(f"{self._book['name']} {self._chapter}")

        # Colonne de lecture.
        _clear_layout(self.reading_layout)
        self._verse_rows = {}
        for verse, text in verses:
            row = _VerseRow(verse, text)
            row.clicked.connect(self._select_verse)
            self._verse_rows[verse] = row
            self.reading_layout.addWidget(row)
        self.reading_layout.addStretch()

        # Grille des versets.
        _clear_layout(self.verses_flow)
        self._verse_buttons = {}
        for verse, _text in verses:
            btn = _NumButton(verse)
            btn.picked.connect(self._select_verse)
            self._verse_buttons[verse] = btn
            self.verses_flow.addWidget(btn)

        self._update_status_texts()
        self.selection_changed.emit()

    def select_verse(self, verse):
        """Sélection d'un verset depuis l'extérieur (navigation du poste)."""
        self._select_verse(verse)

    def _select_verse(self, verse):
        self._verse = verse
        for v, row in getattr(self, "_verse_rows", {}).items():
            row.set_active(v == verse)
        for v, btn in getattr(self, "_verse_buttons", {}).items():
            btn.set_active(v == verse)
        # Fait défiler la lecture jusqu'au verset choisi.
        row = getattr(self, "_verse_rows", {}).get(verse)
        if row is not None:
            self.reading_area.ensureWidgetVisible(row)
        self._update_status_texts()
        self.selection_changed.emit()

    def current_deck(self):
        """(liste de diapositives, index sélectionné) du chapitre courant.

        Une diapositive par verset (texte + référence), prête à projeter.
        """
        if self._book is None or not self._chapter_verses:
            return [], 0
        deck = [
            f"{text}\n{self._book['name']} {self._chapter}:{verse}"
            for verse, text in self._chapter_verses
        ]
        index = (self._verse or 1) - 1
        index = max(0, min(index, len(deck) - 1))
        return deck, index

    # --------------------------- Recherche -------------------------------- #
    def _on_search(self, text):
        query = text.strip().lower()
        for book in self._books:
            match = (
                not query
                or query in book["name"].lower()
                or query in bible.book_abbreviation(book["id"]).lower()
            )
            self._book_cards[book["id"]].set_dimmed(not match)

    # ----------------------------- Statut --------------------------------- #
    def _current_reference(self):
        if self._book is None:
            return "—"
        ref = f"{self._book['name']} {self._chapter}"
        if self._verse:
            ref += f":{self._verse}"
        return ref

    def _update_status_texts(self):
        self.status_left.setText(f"{bible.TRANSLATION_CODE} · {self._current_reference()}")
        if self._verse:
            self.status_right.setText(f"Verset {self._verse} sélectionné")
        else:
            self.status_right.setText("Sélectionnez un verset")

    # ------------------------- Passage courant ---------------------------- #
    def current_passage(self):
        """(label, texte projetable) du verset sélectionné (verset 1 par défaut)."""
        if self._book is None:
            return None
        verse = self._verse or 1
        rows = bible.get_passage(self._book["id"], self._chapter, verse, verse)
        if not rows:
            return None
        label = slides.passage_label(self._book["name"], self._chapter, verse, verse)
        content = slides.passage_to_text(self._book["name"], self._chapter, rows)
        return label, content

    # ----------------------------- Signaux -------------------------------- #
    def _on_project_clicked(self):
        if self._verse is None:
            self._select_verse(1)
        self.project_requested.emit()

    def _emit_service_add(self):
        passage = self.current_passage()
        if passage is not None:
            self.service_add_requested.emit(*passage)


def _clear_layout(layout):
    """Retire et détruit tous les widgets d'un layout (versets, boutons…).

    Le reparentage immédiat (setParent(None)) fait disparaître le widget aussitôt,
    sans attendre le traitement différé de deleteLater — évite tout chevauchement
    visuel transitoire lors d'un changement de chapitre.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
