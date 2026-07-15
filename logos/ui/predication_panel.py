"""
Navigateur de prédications (mode « Prédications »).

Reproduit la maquette : barre supérieure (logo, recherche, nombre d'entrées),
grille ALPHABET, préfixes 2-lettres, liste des prédications, grille des
paragraphes. Une prédication = des paragraphes numérotés ; chaque paragraphe est
une diapositive projetable.

Comme `BiblePanel`, ce panneau ne projette pas lui-même : il émet des signaux et
expose `current_deck()`. Les petits widgets génériques (FlowLayout, logo rond,
cases numérotées, styles de boutons) sont réutilisés depuis `bible_panel`.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
)

from logos.data import predications
from logos.ui import theme
from logos.ui.bible_panel import (
    FlowLayout,
    _FlowHost,
    _NumButton,
    _circular_logo,
    _btn_primary_style,
    _btn_secondary_style,
    _clear_layout,
)


# --------------------------------------------------------------------------- #
#  Petits composants
# --------------------------------------------------------------------------- #
class _LetterCard(QFrame):
    """Case d'une lettre de l'alphabet : lettre + nombre de prédications."""

    clicked = Signal(str)

    def __init__(self, letter: str, count: int):
        super().__init__()
        self.letter = letter
        self._count = count
        self._enabled = count > 0
        self.setFixedSize(84, 74)
        if self._enabled:
            self.setCursor(Qt.PointingHandCursor)

        col = QVBoxLayout(self)
        col.setContentsMargins(6, 10, 6, 8)
        col.setSpacing(2)
        self.letter_label = QLabel(letter)
        self.letter_label.setAlignment(Qt.AlignCenter)
        self.count_label = QLabel(str(count))
        self.count_label.setAlignment(Qt.AlignCenter)
        col.addWidget(self.letter_label)
        col.addStretch()
        col.addWidget(self.count_label)
        self.set_active(False)

    def set_active(self, active: bool):
        if not self._enabled:
            bg, border = theme.COLOR_BACKGROUND, theme.COLOR_BORDER_SUBTLE
            letter_c, count_c = theme.COLOR_TEXT_DISABLED, theme.COLOR_TEXT_DISABLED
        elif active:
            bg, border = theme.COLOR_PRIMARY, theme.COLOR_PRIMARY
            letter_c, count_c = theme.COLOR_TEXT_ON_PRIMARY, theme.COLOR_ON_PRIMARY_MUTED
        else:
            bg, border = theme.COLOR_SURFACE_ALT, theme.COLOR_BORDER_SUBTLE
            letter_c, count_c = theme.COLOR_TEXT, theme.BRONZE
        self.setStyleSheet(
            f"_LetterCard {{ background:{bg}; border:1px solid {border}; border-radius:8px; }}"
        )
        self.letter_label.setStyleSheet(
            f"color:{letter_c}; font-size:20px; font-weight:700; background:transparent; border:none;"
        )
        self.count_label.setStyleSheet(
            f"color:{count_c}; font-size:10px; font-weight:600; background:transparent; border:none;"
        )

    def mousePressEvent(self, event):
        if self._enabled:
            self.clicked.emit(self.letter)


class _PrefixChip(QPushButton):
    """Pastille d'un préfixe 2-lettres : « Ab 3 »."""

    picked = Signal(str)

    def __init__(self, prefix: str, count: int):
        super().__init__()
        self.prefix = prefix
        self.setCursor(Qt.PointingHandCursor)
        self.setText(f"{prefix}  {count}")
        self.clicked.connect(lambda: self.picked.emit(self.prefix))
        self.set_active(False)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.COLOR_PRIMARY};"
                f" color:{theme.COLOR_TEXT_ON_PRIMARY}; border:1px solid {theme.COLOR_PRIMARY};"
                f" border-radius:11px; padding:5px 12px; font-size:12px; font-weight:700; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.COLOR_SURFACE_ALT};"
                f" color:{theme.COLOR_TEXT_MUTED}; border:1px solid {theme.COLOR_BORDER_SUBTLE};"
                f" border-radius:11px; padding:5px 12px; font-size:12px; font-weight:600; }}"
                f" QPushButton:hover {{ border-color:{theme.COLOR_PRIMARY}; color:{theme.COLOR_TEXT}; }}"
            )


class _PredicationRow(QFrame):
    """Ligne d'une prédication : code date + titre FR + titre EN."""

    clicked = Signal(int)

    def __init__(self, row):
        super().__init__()
        self.pred_id = row["id"]
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(16)

        self.code_label = QLabel(row["date_code"])
        self.code_label.setFixedWidth(64)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title_label = QLabel(row["title_fr"])
        self.subtitle_label = QLabel(row["title_en"])
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        layout.addWidget(self.code_label)
        layout.addLayout(titles, 1)
        self.set_active(False)

    def set_active(self, active: bool):
        bg = theme.COLOR_PRIMARY if active else "transparent"
        code_c = theme.COLOR_ON_PRIMARY_MUTED if active else theme.BRONZE
        title_c = theme.COLOR_TEXT_ON_PRIMARY if active else theme.COLOR_TEXT
        sub_c = theme.COLOR_ON_PRIMARY_MUTED if active else theme.BRONZE
        self.setStyleSheet(
            f"_PredicationRow {{ background:{bg}; border-radius:8px; }}"
        )
        self.code_label.setStyleSheet(
            f"color:{code_c}; font-size:12px; font-weight:600; background:transparent;"
        )
        self.title_label.setStyleSheet(
            f"color:{title_c}; font-size:16px; font-weight:600;"
            f" font-family:{theme.READING_FONT_FAMILY}; background:transparent;"
        )
        self.subtitle_label.setStyleSheet(
            f"color:{sub_c}; font-size:11px; font-style:italic; background:transparent;"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.pred_id)


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{theme.COLOR_TEXT_MUTED}; font-size:11px; font-weight:700;"
        f" letter-spacing:2px; background:transparent;"
    )
    return label


# --------------------------------------------------------------------------- #
#  Panneau principal
# --------------------------------------------------------------------------- #
class PredicationPanel(QWidget):
    selection_changed = Signal()   # prédication/paragraphe (jeu de diapos) modifié
    project_requested = Signal()   # « Projeter le paragraphe »
    close_requested = Signal()     # retour à l'accueil

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{theme.COLOR_BACKGROUND};")

        self._letter = None
        self._prefix = None
        self._predication = None       # row sélectionnée
        self._paragraph = None         # numéro de paragraphe sélectionné
        self._paragraphs = []          # (number, text) de la prédication courante
        self._letter_cards = {}        # lettre -> _LetterCard
        self._prefix_chips = {}        # préfixe -> _PrefixChip

        self._build_ui()

        if predications.is_available():
            self._load_alphabet()
        else:
            self._show_unavailable()

    # ---------------------------- Construction ---------------------------- #
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(16)
        body.addWidget(self._build_left_column(), 1)
        body.addWidget(self._build_right_column())
        root.addLayout(body, 1)

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
        section = QLabel("Prédications")
        section.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:13px; font-weight:600; background:transparent;"
        )
        row.addWidget(section)

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
        self.search_edit.setPlaceholderText("Rechercher une prédication…")
        self.search_edit.setMinimumWidth(240)
        self.search_edit.setStyleSheet(
            f"background:transparent; border:none; color:{theme.COLOR_TEXT}; font-size:13px;"
        )
        self.search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_edit)
        row.addWidget(search_box)

        row.addStretch()
        self.entries_label = QLabel("")
        self.entries_label.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:600; background:transparent;"
        )
        row.addWidget(self.entries_label)
        return bar

    def _panel_frame(self):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{theme.COLOR_SURFACE}; border:1px solid {theme.COLOR_BORDER_SUBTLE};"
            f" border-radius:12px; }}"
        )
        return frame

    def _build_left_column(self):
        col = QWidget()
        col.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # --- ALPHABET ---
        alpha = self._panel_frame()
        alpha_col = QVBoxLayout(alpha)
        alpha_col.setContentsMargins(18, 16, 18, 16)
        alpha_col.setSpacing(12)
        alpha_col.addWidget(_section_title("ALPHABET"))
        self.alphabet_host = _FlowHost(spacing=8)
        self.alphabet_flow = self.alphabet_host.flow
        alpha_col.addWidget(self.alphabet_host)
        layout.addWidget(alpha)

        # --- Liste des prédications ---
        listing = self._panel_frame()
        list_col = QVBoxLayout(listing)
        list_col.setContentsMargins(18, 16, 18, 16)
        list_col.setSpacing(10)
        head = QHBoxLayout()
        self.list_title = QLabel("")
        self.list_title.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:15px; font-weight:700; background:transparent;"
        )
        self.list_count = QLabel("")
        self.list_count.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:600; background:transparent;"
        )
        head.addWidget(self.list_title)
        head.addStretch()
        head.addWidget(self.list_count)
        list_col.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        self.list_host = QWidget()
        self.list_host.setStyleSheet("background:transparent;")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_host)
        list_col.addWidget(scroll, 1)
        layout.addWidget(listing, 1)
        return col

    def _build_right_column(self):
        col = QWidget()
        col.setFixedWidth(300)
        col.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # --- PRÉFIXE ---
        pref = self._panel_frame()
        pref_col = QVBoxLayout(pref)
        pref_col.setContentsMargins(16, 14, 16, 14)
        pref_col.setSpacing(10)
        self.prefix_title = _section_title("PRÉFIXE")
        pref_col.addWidget(self.prefix_title)
        self.prefix_host = _FlowHost(spacing=6)
        self.prefix_flow = self.prefix_host.flow
        pref_col.addWidget(self.prefix_host)
        layout.addWidget(pref)

        # --- PARAGRAPHES ---
        para = self._panel_frame()
        para_col = QVBoxLayout(para)
        para_col.setContentsMargins(16, 14, 16, 14)
        para_col.setSpacing(10)
        para_col.addWidget(_section_title("PARAGRAPHES"))
        self.para_subtitle = QLabel("")
        self.para_subtitle.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:13px; font-weight:700; background:transparent;"
        )
        para_col.addWidget(self.para_subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        self.para_host = _FlowHost(spacing=6)
        self.para_flow = self.para_host.flow
        scroll.setWidget(self.para_host)
        para_col.addWidget(scroll, 1)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("‹ § préc.")
        self.prev_btn.setProperty("buttonStyle", "secondary")
        self.prev_btn.clicked.connect(lambda: self._step_paragraph(-1))
        self.next_btn = QPushButton("§ suiv. ›")
        self.next_btn.setProperty("buttonStyle", "secondary")
        self.next_btn.clicked.connect(lambda: self._step_paragraph(1))
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        para_col.addLayout(nav)

        self.project_btn = QPushButton("Projeter le paragraphe")
        self.project_btn.setCursor(Qt.PointingHandCursor)
        self.project_btn.setStyleSheet(_btn_primary_style())
        self.project_btn.clicked.connect(self._on_project_clicked)
        para_col.addWidget(self.project_btn)

        layout.addWidget(para, 1)
        return col

    # ------------------------------ Données ------------------------------- #
    def _load_alphabet(self):
        self.entries_label.setText(f"{predications.total_count()} entrées")
        first_letter = None
        for letter, count in predications.letters_with_counts():
            card = _LetterCard(letter, count)
            card.clicked.connect(self._select_letter)
            self._letter_cards[letter] = card
            self.alphabet_flow.addWidget(card)
            if first_letter is None and count > 0:
                first_letter = letter
        if first_letter is not None:
            self._select_letter(first_letter)

    def _show_unavailable(self):
        self.entries_label.setText("0 entrée")
        for widget in (self.search_edit, self.project_btn, self.prev_btn, self.next_btn):
            widget.setEnabled(False)
        message = QLabel(
            "Prédications non disponibles. Lancez le script d'import "
            "(scripts/scrape_predications.py) pour générer "
            "logos/assets/predications.json.gz."
        )
        message.setWordWrap(True)
        message.setStyleSheet(
            f"color:{theme.COLOR_TEXT_MUTED}; font-size:13px; background:transparent;"
        )
        self.list_layout.insertWidget(0, message)

    # --------------------------- Sélection -------------------------------- #
    def _select_letter(self, letter):
        self._letter = letter
        for l, card in self._letter_cards.items():
            card.set_active(l == letter)
        self.prefix_title.setText(f"PRÉFIXE {letter}")
        self._rebuild_prefixes()

    def _rebuild_prefixes(self):
        _clear_layout(self.prefix_flow)
        self._prefix_chips = {}
        first = None
        for prefix, count in predications.prefixes_with_counts(self._letter):
            chip = _PrefixChip(prefix, count)
            chip.picked.connect(self._select_prefix)
            self._prefix_chips[prefix] = chip
            self.prefix_flow.addWidget(chip)
            if first is None:
                first = prefix
        if first is not None:
            self._select_prefix(first)

    def _select_prefix(self, prefix):
        self._prefix = prefix
        for p, chip in self._prefix_chips.items():
            chip.set_active(p == prefix)
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self._populate_list(predications.list_by_prefix(prefix), header=prefix)

    def _populate_list(self, rows, header):
        _clear_layout(self.list_layout)
        self.list_title.setText(f"{header}")
        self.list_count.setText(f"{len(rows)} prédication(s)")
        self._pred_rows = {}
        for row in rows:
            widget = _PredicationRow(row)
            widget.clicked.connect(self._select_predication)
            self._pred_rows[row["id"]] = widget
            self.list_layout.addWidget(widget)
        self.list_layout.addStretch()
        if rows:
            self._select_predication(rows[0]["id"], row_data=rows[0])
        else:
            self._predication = None
            self._paragraphs = []
            self._paragraph = None
            self.para_subtitle.setText("")
            _clear_layout(self.para_flow)
            self.selection_changed.emit()

    def _select_predication(self, pred_id, row_data=None):
        for pid, widget in getattr(self, "_pred_rows", {}).items():
            widget.set_active(pid == pred_id)
        # Titre pour le sous-titre des paragraphes (depuis la ligne ou la donnée).
        if row_data is not None:
            title = row_data["title_fr"]
        else:
            widget = getattr(self, "_pred_rows", {}).get(pred_id)
            title = widget.title_label.text() if widget is not None else ""
        self._predication = {"id": pred_id, "title_fr": title}
        self.para_subtitle.setText(title)

        self._paragraphs = predications.get_paragraphs(pred_id)
        self._paragraph = 1 if self._paragraphs else None
        self._rebuild_paragraphs()
        self.list_count.setText(
            f"{predications.paragraph_count(pred_id)} paragraphes"
        )
        self.selection_changed.emit()

    def _rebuild_paragraphs(self):
        _clear_layout(self.para_flow)
        self._para_buttons = {}
        for number, _text in self._paragraphs:
            btn = _NumButton(number)
            btn.set_active(number == self._paragraph)
            btn.picked.connect(self._select_paragraph)
            self._para_buttons[number] = btn
            self.para_flow.addWidget(btn)

    def _select_paragraph(self, number):
        self._paragraph = number
        for n, btn in getattr(self, "_para_buttons", {}).items():
            btn.set_active(n == number)
        self.selection_changed.emit()

    def _step_paragraph(self, delta):
        if not self._paragraphs:
            return
        numbers = [n for n, _t in self._paragraphs]
        if self._paragraph in numbers:
            i = numbers.index(self._paragraph)
        else:
            i = 0
        i = max(0, min(i + delta, len(numbers) - 1))
        self._select_paragraph(numbers[i])

    # --------------------------- Recherche -------------------------------- #
    def _on_search(self, text):
        query = text.strip()
        if not query:
            if self._prefix is not None:
                self._populate_list(
                    predications.list_by_prefix(self._prefix), header=self._prefix
                )
            return
        self._populate_list(predications.search(query), header=f"« {query} »")

    # ----------------------- Diapositives / signaux ----------------------- #
    def current_deck(self):
        """(liste de diapositives, index) : un paragraphe = une diapositive."""
        if not self._paragraphs:
            return [], 0
        title = self._predication["title_fr"] if self._predication else ""
        deck = [f"{text}\n{title} · §{number}" for number, text in self._paragraphs]
        index = (self._paragraph or 1) - 1
        index = max(0, min(index, len(deck) - 1))
        return deck, index

    def select_slide(self, index):
        """Sélection d'un paragraphe par index de diapositive (navigation du poste)."""
        numbers = [n for n, _t in self._paragraphs]
        if not numbers:
            return
        index = max(0, min(index, len(numbers) - 1))
        self._select_paragraph(numbers[index])

    def _on_project_clicked(self):
        if self._paragraph is None and self._paragraphs:
            self._select_paragraph(self._paragraphs[0][0])
        self.project_requested.emit()
