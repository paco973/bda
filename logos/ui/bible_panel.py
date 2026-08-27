"""
Navigateur biblique (fenêtre dédiée), fidèle à la maquette « Bible Navigator ».

Disposition :
  - barre supérieure : retour, logo, titre, recherches (référence, texte), badge LSG ;
  - colonne de lecture (gauche) : testament, référence, versets cliquables, actions ;
  - grille des livres (haut-droite) puis grilles chapitres / versets (bas-droite) ;
  - barre de statut (traduction · référence à gauche, versets sélectionnés à droite).

Aucune logique de projection ici : le panneau émet des signaux vers la fenêtre
de contrôle, qui reste seule maîtresse de la fenêtre de projection.
"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QWidget,
    QCompleter,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSpinBox,
)

from logos.data import bible, slides
from logos.ui import theme
from logos.ui.widgets import (
    FlowHost,
    NumButton,
    NumberedTextRow,
    circular_logo,
    clear_layout,
)

# Chiffres en exposant Unicode : préfixent chaque verset dans le texte projeté
# pour distinguer visuellement les versets d'une même diapositive. On reste en
# texte brut (pas de HTML) pour que la mesure de place demeure exacte.
_SUPERSCRIPT = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
}


def _superscript(number: int) -> str:
    return "".join(_SUPERSCRIPT[d] for d in str(number))


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
        # Couleur du groupe canonique (Pentateuque, Épîtres…) ; la sélection
        # garde l'accent doré de l'application.
        group_color = theme.BOOK_GROUP_COLORS[bible.book_group(self.book_id)]
        if active:
            abbr, name = theme.COLOR_TEXT_ON_PRIMARY, theme.COLOR_ON_PRIMARY_MUTED
            bg = border = theme.COLOR_PRIMARY
        else:
            abbr, name = theme.COLOR_TEXT_ON_GROUP, theme.COLOR_TEXT_ON_GROUP_MUTED
            bg = border = group_color
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


# --------------------------------------------------------------------------- #
#  Panneau principal
# --------------------------------------------------------------------------- #
class BiblePanel(QWidget):
    selection_changed = Signal()          # livre/chapitre/verset (jeu de diapos) modifié
    project_requested = Signal()          # « Projeter le verset » cliqué
    close_requested = Signal()            # retour à l'accueil (bouton « ‹ Retour »)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{theme.COLOR_BACKGROUND};")

        self._books = []            # liste de dicts {id, name, chapters}
        self._book = None           # livre sélectionné
        self._chapter = 1
        self._verse = None          # verset sélectionné (int) ou None
        self._partial_start = 0     # position de départ dans le verset sélectionné
        self._chapter_verses = []   # (verse, text) du chapitre courant
        self._book_cards = {}       # id -> _BookCard
        self._verses_per_slide = 1  # nombre MAX de versets regroupés par diapositive
        self._fits = None           # prédicat (texte)->bool : le texte tient-il à l'écran ?

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
        back_btn.setStyleSheet(theme.btn_secondary_style())
        back_btn.clicked.connect(self.close_requested.emit)
        row.addWidget(back_btn)

        logo = circular_logo(34)
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
        glass.setStyleSheet(
            f"color:{theme.BRONZE}; background:transparent; border:none; font-size:13px;"
        )
        search_row.addWidget(glass)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Livre ou référence (ex. Jean 3:16)…")
        self.search_edit.setFixedWidth(240)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setStyleSheet(
            f"background:transparent; border:none; color:{theme.COLOR_TEXT}; font-size:13px;"
        )
        self.search_edit.textChanged.connect(self._on_search)
        self.search_edit.returnPressed.connect(self._on_search_return)
        search_row.addWidget(self.search_edit)

        # Confirmation en direct de la référence reconnue (« → Jean 3:16 »).
        self.search_hint = QLabel("")
        self.search_hint.setStyleSheet(
            f"color:{theme.COLOR_PRIMARY}; font-size:12px; font-weight:700;"
            f" background:transparent; border:none;"
        )
        search_row.addWidget(self.search_hint)
        row.addWidget(search_box)

        # Recherche plein texte dans les versets (« tant aimé le monde »).
        verse_box = QFrame()
        verse_box.setStyleSheet(
            f"background:{theme.COLOR_SURFACE_ALT}; border:1px solid {theme.COLOR_BORDER};"
            f" border-radius:6px;"
        )
        verse_row = QHBoxLayout(verse_box)
        verse_row.setContentsMargins(12, 4, 12, 4)
        verse_row.setSpacing(8)
        pilcrow = QLabel("¶")
        pilcrow.setStyleSheet(
            f"color:{theme.BRONZE}; background:transparent; border:none; font-size:13px;"
        )
        verse_row.addWidget(pilcrow)
        self.verse_search_edit = QLineEdit()
        self.verse_search_edit.setPlaceholderText("Rechercher dans le texte…")
        self.verse_search_edit.setFixedWidth(200)
        self.verse_search_edit.setClearButtonEnabled(True)
        self.verse_search_edit.setStyleSheet(
            f"background:transparent; border:none; color:{theme.COLOR_TEXT}; font-size:13px;"
        )
        self.verse_search_edit.textChanged.connect(self._on_verse_search_text)
        self.verse_search_edit.returnPressed.connect(self._on_verse_search_return)
        verse_row.addWidget(self.verse_search_edit)
        row.addWidget(verse_box)
        self._verse_search_box = verse_box

        # Liste flottante des versets trouvés, ancrée sous le champ.
        self.verse_results = QListWidget(self)
        self.verse_results.setVisible(False)
        self.verse_results.setWordWrap(False)
        self.verse_results.setTextElideMode(Qt.ElideRight)
        self.verse_results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.verse_results.setStyleSheet(
            f"QListWidget {{ background:{theme.COLOR_SURFACE_ALT}; color:{theme.COLOR_TEXT};"
            f" border:1px solid {theme.COLOR_BORDER}; border-radius:6px; font-size:13px; }}"
            f"QListWidget::item {{ padding:6px 10px; }}"
            f"QListWidget::item:selected, QListWidget::item:hover"
            f" {{ background:{theme.COLOR_PRIMARY}; color:{theme.COLOR_TEXT_ON_PRIMARY}; }}"
        )
        self.verse_results.itemClicked.connect(self._on_verse_result_clicked)

        # Anti-rebond : la recherche part 300 ms après la dernière frappe.
        self._verse_search_timer = QTimer(self)
        self._verse_search_timer.setSingleShot(True)
        self._verse_search_timer.setInterval(300)
        self._verse_search_timer.timeout.connect(self._run_verse_search)

        row.addStretch()

        # Badge de la traduction embarquée (LSG).
        lsg = QLabel(f"  {bible.TRANSLATION_CODE}  ")
        lsg.setToolTip(bible.TRANSLATION)
        lsg.setStyleSheet(
            f"color:{theme.COLOR_TEXT_ON_PRIMARY}; background:{theme.COLOR_PRIMARY};"
            f" font-size:12px; font-weight:700; padding:6px 4px; border-radius:5px;"
        )
        row.addWidget(lsg)
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

        # Nombre de versets regroupés sur une même diapositive projetée.
        opts_row = QHBoxLayout()
        opts_label = QLabel("Versets par diapositive")
        opts_label.setStyleSheet("background:transparent;")
        self.verses_spin = QSpinBox()
        self.verses_spin.setRange(1, 20)
        self.verses_spin.setValue(self._verses_per_slide)
        self.verses_spin.setToolTip(
            "Regroupe ce nombre de versets consécutifs sur chaque diapositive."
        )
        self.verses_spin.valueChanged.connect(self._on_verses_per_slide_changed)
        opts_row.addWidget(opts_label)
        opts_row.addStretch()
        opts_row.addWidget(self.verses_spin)
        footer_col.addLayout(opts_row)

        self.project_btn = QPushButton("Projeter le verset")
        self.project_btn.setCursor(Qt.PointingHandCursor)
        self.project_btn.setStyleSheet(theme.btn_primary_style())
        self.project_btn.clicked.connect(self._on_project_clicked)
        footer_col.addWidget(self.project_btn)
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
        self.books_host = FlowHost(spacing=6)
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
        self.chapters_host = FlowHost(spacing=6)
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
        self.verses_host = FlowHost(spacing=6)
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

        # Autocomplétion des noms de livres dans la barre de recherche.
        completer = QCompleter([b["name"] for b in self._books], self.search_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.popup().setStyleSheet(
            f"background:{theme.COLOR_SURFACE_ALT}; color:{theme.COLOR_TEXT};"
            f" border:1px solid {theme.COLOR_BORDER};"
            f" selection-background-color:{theme.COLOR_PRIMARY};"
            f" selection-color:{theme.COLOR_TEXT_ON_PRIMARY};"
        )
        self.search_edit.setCompleter(completer)

        # Livre par défaut : Actes (comme la maquette), sinon le premier.
        default = next((b for b in self._books if b["id"] == 44), self._books[0])
        self._select_book(default["id"])

        # Précharge le cache de la recherche plein texte hors du chemin critique
        # (sinon la première recherche marquerait une pause de ~300 ms).
        QTimer.singleShot(500, bible.warm_search_cache)

    def _show_unavailable(self):
        for widget in (self.project_btn, self.search_edit, self.verse_search_edit):
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
        clear_layout(self.chapters_flow)
        for n in range(1, self._book["chapters"] + 1):
            btn = NumButton(n)
            btn.set_active(n == self._chapter)
            btn.picked.connect(self._select_chapter)
            self.chapters_flow.addWidget(btn)

    def _select_chapter(self, chapter):
        self._chapter = chapter
        self._verse = None
        for i in range(self.chapters_flow.count()):
            btn = self.chapters_flow.itemAt(i).widget()
            if isinstance(btn, NumButton):
                btn.set_active(btn.number == chapter)
        self._load_chapter()

    def _load_chapter(self):
        verses = bible.get_chapter(self._book["id"], self._chapter)
        self._chapter_verses = verses
        self.testament_label.setText(bible.testament(self._book["id"]).upper())
        self.reference_label.setText(f"{self._book['name']} {self._chapter}")

        # Colonne de lecture.
        clear_layout(self.reading_layout)
        self._verse_rows = {}
        for verse, text in verses:
            row = NumberedTextRow(verse, text)
            row.clicked.connect(self._select_verse)
            row.partial_selected.connect(self._on_partial_selected)
            self._verse_rows[verse] = row
            self.reading_layout.addWidget(row)
        self.reading_layout.addStretch()

        # Grille des versets.
        clear_layout(self.verses_flow)
        self._verse_buttons = {}
        for verse, _text in verses:
            btn = NumButton(verse)
            btn.picked.connect(self._select_verse)
            self._verse_buttons[verse] = btn
            self.verses_flow.addWidget(btn)

        self._update_status_texts()
        self.selection_changed.emit()

    def select_verse(self, verse):
        """Sélection d'un verset depuis l'extérieur (navigation du poste)."""
        self._select_verse(verse)

    def set_fit_predicate(self, fits):
        """Injecte un prédicat `(texte)->bool` : le texte tient-il dans la
        projection ? Utilisé pour ne regrouper que les versets qui rentrent."""
        self._fits = fits

    def select_slide(self, index: int):
        """Sélection d'une diapositive (groupe de versets) par son index."""
        groups, _index = self._deck_groups()
        if not groups:
            return
        index = max(0, min(index, len(groups) - 1))
        self._select_verse(groups[index][0][0])

    def _verse_display_text(self, verse, text) -> str:
        """Texte projetable d'un verset : tronqué au début de la sélection à la
        souris (« … la seconde moitié ») si elle porte sur le verset sélectionné."""
        if verse == self._verse and self._partial_start > 0:
            return "…" + text[self._partial_start:].lstrip()
        return text

    def _render_group(self, group) -> str:
        """Texte projetable d'un groupe de versets (texte + référence de plage).

        Quand plusieurs versets partagent une diapositive, chacun est mis sur son
        propre paragraphe et préfixé de son numéro en exposant pour les
        distinguer ; un verset seul reste sans numéro (la référence sous le texte
        suffit à l'identifier)."""
        if len(group) > 1:
            block = "\n\n".join(
                f"{_superscript(v)} {self._verse_display_text(v, text)}"
                for v, text in group
            )
        else:
            block = self._verse_display_text(group[0][0], group[0][1])
        ref = slides.passage_label(
            self._book["name"], self._chapter, group[0][0], group[-1][0]
        )
        return f"{block}\n{ref}"

    def _group_from(self, pos: int, end: int):
        """Groupe débutant à `pos` : le verset et les suivants, jusqu'à
        `verses_per_slide` versets ET tant que le texte tient à l'écran
        (`self._fits`). Toujours au moins un verset."""
        verses = self._chapter_verses
        n = max(1, self._verses_per_slide)
        group = [verses[pos]]
        k = pos + 1
        while k < end and len(group) < n:
            trial = group + [verses[k]]
            if self._fits is not None and not self._fits(self._render_group(trial)):
                break
            group.append(verses[k])
            k += 1
        return group

    def _page(self, start: int, end: int):
        """Découpe `verses[start:end]` en groupes successifs (pavage glouton)."""
        groups = []
        i = start
        while i < end:
            group = self._group_from(i, end)
            groups.append(group)
            i += len(group)
        return groups

    def _deck_groups(self):
        """(liste de groupes, index du groupe sélectionné). Le verset sélectionné
        débute toujours son groupe ; les versets avant l'ancre forment des
        diapositives en tête, pour rester navigables."""
        verses = self._chapter_verses
        if self._book is None or not verses:
            return [], 0
        sel = self._verse if any(v == self._verse for v, _t in verses) else verses[0][0]
        sel_pos = next(k for k, (v, _t) in enumerate(verses) if v == sel)
        before = self._page(0, sel_pos)
        after = self._page(sel_pos, len(verses))
        return before + after, len(before)

    def _group_verses(self, verse):
        """Le verset `verse` et les suivants effectivement regroupés avec lui."""
        verses = [v for v, _t in self._chapter_verses]
        if verse not in verses:
            return [verse]
        pos = verses.index(verse)
        return [v for v, _t in self._group_from(pos, len(verses))]

    def _select_verse(self, verse):
        if verse != self._verse:
            self._partial_start = 0  # la sélection partielle suit son verset
        self._verse = verse
        group = set(self._group_verses(verse))
        for v, row in getattr(self, "_verse_rows", {}).items():
            row.set_active(v in group)
        for v, btn in getattr(self, "_verse_buttons", {}).items():
            btn.set_active(v in group)
        # Fait défiler la lecture jusqu'au premier verset du groupe.
        anchor = min(group) if group else verse
        row = getattr(self, "_verse_rows", {}).get(anchor)
        if row is not None:
            self.reading_area.ensureWidgetVisible(row)
        self._update_status_texts()
        self.selection_changed.emit()

    def _on_partial_selected(self, verse, offset):
        """Sélection à la souris dans un verset : la projection démarre à la
        sélection (offset -1 = pas de sélection -> verset complet)."""
        if verse != self._verse:
            return
        partial = max(0, offset) if offset >= 0 else 0
        if partial == self._partial_start:
            return
        self._partial_start = partial
        self._update_status_texts()
        self.selection_changed.emit()  # recharge l'aperçu (et le direct si à l'antenne)

    def _on_verses_per_slide_changed(self, value: int):
        self._verses_per_slide = max(1, value)
        self.project_btn.setText(
            "Projeter le verset" if self._verses_per_slide == 1 else "Projeter les versets"
        )
        # Rafraîchit le surlignage du groupe et recharge le jeu de diapositives.
        self._select_verse(self._verse or 1)

    def current_deck(self):
        """(liste de diapositives, index sélectionné) du chapitre courant.

        Chaque diapositive regroupe jusqu'à `verses_per_slide` versets, mais
        **seulement ceux qui tiennent** dans la projection (`set_fit_predicate`).
        Le verset sélectionné débute toujours sa diapositive (réf. « Jean 3:16-18 »).
        """
        groups, index = self._deck_groups()
        return [self._render_group(g) for g in groups], index

    # --------------------------- Recherche -------------------------------- #
    def _on_search(self, text):
        query = text.strip()
        # Référence directe (« Jean 3:16 », « 1 co 13 ») : saute au passage dès
        # qu'un chapitre est saisi, sans filtrer la grille pendant la frappe.
        ref = bible.parse_reference(query) if self._books else None
        self._update_search_hint(query, ref)
        if ref is not None and ref[1] is not None:
            self._jump_to_reference(*ref)
            return
        query = query.lower()
        for book in self._books:
            match = (
                not query
                or query in book["name"].lower()
                or query in bible.book_abbreviation(book["id"]).lower()
            )
            self._book_cards[book["id"]].set_dimmed(not match)

    def _update_search_hint(self, query, ref):
        """Affiche la cible reconnue à côté de la saisie (« → Jean 3:16 »)."""
        book = self._find_book(ref[0]) if ref is not None else None
        if not query or book is None:
            self.search_hint.setText("")
            return
        target = book["name"]
        if ref[1] is not None:
            target += f" {max(1, min(ref[1], book['chapters']))}"
            if ref[2] is not None:
                target += f":{ref[2]}"
        self.search_hint.setText(f"→ {target}")

    def _on_search_return(self):
        """Entrée : saute à la référence reconnue (livre seul inclus) et efface."""
        ref = bible.parse_reference(self.search_edit.text().strip()) if self._books else None
        if ref is None:
            return
        book_id, chapter, verse = ref
        if chapter is None:
            self._select_book(book_id)
        else:
            self._jump_to_reference(book_id, chapter, verse)
        self.search_edit.clear()  # réaffiche tous les livres et vide l'indication

    # ---------------------- Recherche dans les versets --------------------- #
    def _on_verse_search_text(self, text):
        if len(text.strip()) < 3:  # même seuil que bible.search_verses
            self._verse_search_timer.stop()
            self.verse_results.hide()
            return
        self._verse_search_timer.start()

    def _run_verse_search(self):
        query = self.verse_search_edit.text().strip()
        if len(query) < 3 or not self._books:
            self.verse_results.hide()
            return
        results = bible.search_verses(query)
        self.verse_results.clear()
        if not results:
            empty = QListWidgetItem("Aucun verset trouvé")
            empty.setFlags(Qt.NoItemFlags)
            self.verse_results.addItem(empty)
        for row in results:
            book = self._find_book(row["book_id"])
            reference = f"{book['name'] if book else '?'} {row['chapter']}:{row['verse']}"
            text = row["text"]
            if len(text) > 90:
                text = text[:90].rstrip() + "…"
            item = QListWidgetItem(f"{reference} — {text}")
            item.setData(Qt.UserRole, (row["book_id"], row["chapter"], row["verse"]))
            self.verse_results.addItem(item)
        self._place_verse_results()
        self.verse_results.show()
        self.verse_results.raise_()

    def _place_verse_results(self):
        """Ancre la liste de résultats sous le champ de recherche plein texte."""
        anchor = self._verse_search_box.mapTo(
            self, self._verse_search_box.rect().bottomLeft()
        )
        row_height = self.verse_results.sizeHintForRow(0)
        height = min(360, self.verse_results.count() * max(row_height, 24) + 8)
        width = min(640, max(420, self.width() - anchor.x() - 24))
        self.verse_results.setGeometry(anchor.x(), anchor.y() + 6, width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.verse_results.isVisible():
            self._place_verse_results()

    def keyPressEvent(self, event):
        # Échap referme la liste de résultats (la touche remonte depuis le champ).
        if event.key() == Qt.Key_Escape and self.verse_results.isVisible():
            self.verse_results.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_verse_result_clicked(self, item):
        target = item.data(Qt.UserRole)
        if target:
            self.verse_results.hide()
            self._jump_to_reference(*target)

    def _on_verse_search_return(self):
        """Entrée : saute au premier verset trouvé."""
        self._verse_search_timer.stop()
        self._run_verse_search()
        for i in range(self.verse_results.count()):
            target = self.verse_results.item(i).data(Qt.UserRole)
            if target:
                self.verse_results.hide()
                self._jump_to_reference(*target)
                return

    def _jump_to_reference(self, book_id, chapter, verse):
        """Navigue vers la référence (bornée aux chapitres/versets existants)."""
        book = self._find_book(book_id)
        if book is None:
            return
        for card in self._book_cards.values():
            card.set_dimmed(False)
        if self._book is None or self._book["id"] != book_id:
            self._select_book(book_id)
        chapter = max(1, min(chapter, book["chapters"]))
        if self._chapter != chapter:
            self._select_chapter(chapter)
        if verse is not None and self._chapter_verses:
            numbers = [v for v, _t in self._chapter_verses]
            self._select_verse(max(numbers[0], min(verse, numbers[-1])))

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
            group = self._group_verses(self._verse)
            if len(group) > 1:
                status = f"Versets {group[0]}-{group[-1]} sélectionnés"
            else:
                status = f"Verset {self._verse} sélectionné"
            if self._partial_start > 0:
                status += " · projeté à partir de la sélection"
            self.status_right.setText(status)
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
