"""
Navigateur de prédications (mode « Prédications »), même disposition que le
navigateur biblique (`BiblePanel`) pour une prise en main identique :

  - barre supérieure : retour, logo, titre, recherche, nombre d'entrées ;
  - colonne de lecture (gauche) : code date, titre, paragraphes cliquables,
    navigation § préc./suiv. et « Projeter le paragraphe » ;
  - navigation (droite) : grille ALPHABET (haut), puis préfixes + liste des
    prédications et grille des paragraphes (bas) ;
  - barre de statut (date · titre à gauche, paragraphe sélectionné à droite).

Comme `BiblePanel`, ce panneau ne projette pas lui-même : il émet des signaux et
expose `current_deck()`. Les petits widgets génériques (disposition en flux,
logo rond, cases numérotées, lignes de lecture) viennent de `widgets`, les
styles de boutons de `theme`.
"""
from PySide6.QtCore import Qt, QTimer, Signal
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

from logos import resources
from logos.data import predications, slides
from logos.ui import theme
from logos.ui.widgets import (
    FlowHost,
    NumButton,
    NumberedTextRow,
    circular_logo,
    clear_layout,
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
        # Case compacte : l'alphabet doit rester un bandeau, l'espace vertical
        # revient à la liste des prédications et à la grille des paragraphes.
        self.setFixedSize(56, 50)
        if self._enabled:
            self.setCursor(Qt.PointingHandCursor)

        col = QVBoxLayout(self)
        col.setContentsMargins(4, 5, 4, 5)
        col.setSpacing(1)
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
            f"color:{letter_c}; font-size:15px; font-weight:700; background:transparent; border:none;"
        )
        self.count_label.setStyleSheet(
            f"color:{count_c}; font-size:9px; font-weight:600; background:transparent; border:none;"
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
        self.date_code = row["date_code"]
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(16)

        self.code_label = QLabel(row["date_code"])
        self.code_label.setFixedWidth(64)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        # Retour à la ligne : un titre long ne doit pas élargir la liste (et
        # déclencher un défilement horizontal), il s'écrit sur deux lignes.
        self.title_label = QLabel(row["title_fr"])
        self.title_label.setWordWrap(True)
        self.subtitle_label = QLabel(row["title_en"])
        self.subtitle_label.setWordWrap(True)
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
    download_requested = Signal()  # « Télécharger les prédications… » (état vide)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{theme.COLOR_BACKGROUND};")

        self._letter = None
        self._prefix = None
        self._predication = None       # {id, date_code, title_fr} sélectionné
        self._paragraph = None         # numéro de paragraphe sélectionné
        self._part = 0                 # partie sélectionnée d'un paragraphe découpé
        self._paragraphs = []          # (number, text) de la prédication courante
        self._letter_cards = {}        # lettre -> _LetterCard
        self._prefix_chips = {}        # préfixe -> _PrefixChip
        self._fits = None              # prédicat (texte)->bool : tient-il à l'écran ?
        self._deck_cache = None        # (pred_id, deck, meta) — découpage mémorisé

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
        self.search_edit.setPlaceholderText("Titre ou code date (ex. 62-0123)…")
        self.search_edit.setFixedWidth(240)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setStyleSheet(
            f"background:transparent; border:none; color:{theme.COLOR_TEXT}; font-size:13px;"
        )
        self.search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_edit)
        row.addWidget(search_box)

        # Anti-rebond : la recherche part 300 ms après la dernière frappe (la
        # liste n'est pas reconstruite à chaque caractère).
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._run_search)

        row.addStretch()

        self.entries_label = QLabel("")
        self.entries_label.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:600; background:transparent;"
        )
        row.addWidget(self.entries_label)
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
        self.kicker_label = QLabel("")
        self.kicker_label.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:22px; font-weight:700; background:transparent;"
        )
        header_col.addWidget(self.kicker_label)
        header_col.addWidget(self.title_label)
        layout.addWidget(header)

        # Zone de lecture défilante (les paragraphes de la prédication).
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

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("‹ § préc.")
        self.prev_btn.setProperty("buttonStyle", "secondary")
        self.prev_btn.clicked.connect(lambda: self._step_paragraph(-1))
        self.next_btn = QPushButton("§ suiv. ›")
        self.next_btn.setProperty("buttonStyle", "secondary")
        self.next_btn.clicked.connect(lambda: self._step_paragraph(1))
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        footer_col.addLayout(nav)

        self.project_btn = QPushButton("Projeter le paragraphe")
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

        # --- Alphabet (haut) : bandeau compact à hauteur naturelle (la FlowHost
        # déclare sa hauteur), sans défilement — 26 lettres = 2-3 rangées.
        alpha_wrap = QWidget()
        alpha_col = QVBoxLayout(alpha_wrap)
        alpha_col.setContentsMargins(22, 16, 22, 12)
        alpha_col.setSpacing(10)
        alpha_col.addWidget(_section_title("Alphabet"))
        self.alphabet_host = FlowHost(spacing=6)
        self.alphabet_flow = self.alphabet_host.flow
        alpha_col.addWidget(self.alphabet_host)
        layout.addWidget(alpha_wrap)

        # --- Prédications + paragraphes : tout l'espace vertical restant ---
        bottom = QFrame()
        bottom.setStyleSheet(
            f"background:{theme.COLOR_SURFACE_SUNKEN};"
            f" border-top:1px solid {theme.COLOR_SURFACE_ALT};"
        )
        bottom_row = QHBoxLayout(bottom)
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(0)

        # Prédications (préfixes puis liste)
        pred_wrap = QFrame()
        pred_wrap.setStyleSheet(f"border-right:1px solid {theme.COLOR_SURFACE_ALT};")
        pred_col = QVBoxLayout(pred_wrap)
        pred_col.setContentsMargins(18, 14, 18, 14)
        pred_col.setSpacing(10)
        pred_head = QHBoxLayout()
        pred_head.setSpacing(8)
        pred_title = QLabel("Prédication")
        pred_title.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        self.list_title = QLabel("")
        self.list_title.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:13px; font-weight:700; background:transparent;"
        )
        self.list_count = QLabel("")
        self.list_count.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:600; background:transparent;"
        )
        pred_head.addWidget(pred_title)
        pred_head.addWidget(self.list_title)
        pred_head.addStretch()
        pred_head.addWidget(self.list_count)
        pred_col.addLayout(pred_head)

        self.prefix_host = FlowHost(spacing=6)
        self.prefix_flow = self.prefix_host.flow
        pred_col.addWidget(self.prefix_host)

        list_scroll = QScrollArea()
        list_scroll.setWidgetResizable(True)
        list_scroll.setFrameShape(QFrame.NoFrame)
        list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_scroll.setStyleSheet("background:transparent; border:none;")
        self.list_host = QWidget()
        self.list_host.setStyleSheet("background:transparent;")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()
        list_scroll.setWidget(self.list_host)
        pred_col.addWidget(list_scroll, 1)
        bottom_row.addWidget(pred_wrap, 3)

        # Paragraphes
        para_wrap = QWidget()
        para_col = QVBoxLayout(para_wrap)
        para_col.setContentsMargins(18, 14, 18, 14)
        para_col.setSpacing(10)
        para_title = QLabel("Paragraphe")
        para_title.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        para_col.addWidget(para_title)
        para_scroll = QScrollArea()
        para_scroll.setWidgetResizable(True)
        para_scroll.setFrameShape(QFrame.NoFrame)
        para_scroll.setStyleSheet("background:transparent; border:none;")
        self.para_host = FlowHost(spacing=6)
        self.para_flow = self.para_host.flow
        para_scroll.setWidget(self.para_host)
        para_col.addWidget(para_scroll, 1)
        bottom_row.addWidget(para_wrap, 2)

        layout.addWidget(bottom, 1)
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
        # Message orienté opérateur : sur un poste installé (paquet public sans
        # corpus, pour cause de copyright), le geste attendu est le dépôt du
        # fichier dans le dossier utilisateur — pas le script de développeur.
        message = QLabel(
            "Prédications non disponibles sur ce poste.\n\n"
            "Déposez le fichier « predications.json.gz » (fourni par le "
            "responsable) dans le dossier :\n"
            f"{resources.USER_ASSETS_DIR}\n\n"
            "puis relancez l'application : le corpus sera importé "
            "automatiquement."
        )
        message.setWordWrap(True)
        message.setStyleSheet(
            f"color:{theme.COLOR_TEXT_MUTED}; font-size:14px; background:transparent;"
        )
        self.reading_layout.insertWidget(0, message)

        # Ou, si le poste a Internet : téléchargement intégré (la fenêtre de
        # contrôle demande confirmation — copyright, durée — avant de lancer).
        self.download_btn = QPushButton("Télécharger les prédications…")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setStyleSheet(theme.btn_primary_style())
        self.download_btn.clicked.connect(self.download_requested.emit)
        self.reading_layout.insertWidget(1, self.download_btn)
        self._update_status_texts()

    def reload(self):
        """Recharge entièrement le panneau (après un téléchargement de corpus)."""
        for flow in (self.alphabet_flow, self.prefix_flow, self.para_flow):
            clear_layout(flow)
        clear_layout(self.reading_layout)
        self.reading_layout.addStretch()
        clear_layout(self.list_layout)
        self.list_layout.addStretch()
        self._letter_cards = {}
        self._prefix_chips = {}
        self._pred_rows = {}
        self._para_rows = {}
        self._para_buttons = {}
        self._letter = self._prefix = None
        self._predication = None
        self._paragraph = None
        self._part = 0
        self._paragraphs = []
        self._deck_cache = None
        self.kicker_label.setText("")
        self.title_label.setText("")
        self.list_title.setText("")
        self.list_count.setText("")
        for widget in (self.search_edit, self.project_btn, self.prev_btn, self.next_btn):
            widget.setEnabled(True)
        if predications.is_available():
            self._load_alphabet()
        else:
            self._show_unavailable()
        self._update_status_texts()

    # --------------------------- Sélection -------------------------------- #
    def _select_letter(self, letter):
        self._letter = letter
        for l, card in self._letter_cards.items():
            card.set_active(l == letter)
        self._rebuild_prefixes()

    def _rebuild_prefixes(self):
        clear_layout(self.prefix_flow)
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
        clear_layout(self.list_layout)
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
            self.kicker_label.setText("")
            self.title_label.setText("")
            clear_layout(self.reading_layout)
            clear_layout(self.para_flow)
            self._update_status_texts()
            self.selection_changed.emit()

    def _select_predication(self, pred_id, row_data=None):
        for pid, widget in getattr(self, "_pred_rows", {}).items():
            widget.set_active(pid == pred_id)
        # Titre et code date pour l'en-tête de lecture (ligne ou donnée).
        if row_data is not None:
            title, date_code = row_data["title_fr"], row_data["date_code"]
        else:
            widget = getattr(self, "_pred_rows", {}).get(pred_id)
            title = widget.title_label.text() if widget is not None else ""
            date_code = widget.date_code if widget is not None else ""
        self._predication = {"id": pred_id, "date_code": date_code, "title_fr": title}
        self.kicker_label.setText(date_code.upper())
        self.title_label.setText(title)

        self._paragraphs = predications.get_paragraphs(pred_id)
        self._paragraph = 1 if self._paragraphs else None
        self._rebuild_reading()
        self._rebuild_paragraphs()
        self._update_status_texts()
        self.selection_changed.emit()

    def _rebuild_reading(self):
        clear_layout(self.reading_layout)
        self._para_rows = {}
        for number, text in self._paragraphs:
            row = NumberedTextRow(number, text)
            row.clicked.connect(self._select_paragraph)
            self._para_rows[number] = row
            self.reading_layout.addWidget(row)
        self.reading_layout.addStretch()
        for number, row in self._para_rows.items():
            row.set_active(number == self._paragraph)

    def _rebuild_paragraphs(self):
        clear_layout(self.para_flow)
        self._para_buttons = {}
        for number, _text in self._paragraphs:
            btn = NumButton(number)
            btn.set_active(number == self._paragraph)
            btn.picked.connect(self._select_paragraph)
            self._para_buttons[number] = btn
            self.para_flow.addWidget(btn)

    def _select_paragraph(self, number, part=0):
        self._paragraph = number
        self._part = part
        for n, row in getattr(self, "_para_rows", {}).items():
            row.set_active(n == number)
        for n, btn in getattr(self, "_para_buttons", {}).items():
            btn.set_active(n == number)
        # Fait défiler la lecture jusqu'au paragraphe sélectionné.
        row = getattr(self, "_para_rows", {}).get(number)
        if row is not None:
            self.reading_area.ensureWidgetVisible(row)
        self._update_status_texts()
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
        if not text.strip():
            # Effacement : retour immédiat à la liste du préfixe courant.
            self._search_timer.stop()
            if self._prefix is not None:
                self._populate_list(
                    predications.list_by_prefix(self._prefix), header=self._prefix
                )
            return
        self._search_timer.start()

    def _run_search(self):
        query = self.search_edit.text().strip()
        if query:
            self._populate_list(predications.search(query), header=f"« {query} »")

    # ----------------------------- Statut --------------------------------- #
    def _update_status_texts(self):
        if self._predication is not None:
            self.status_left.setText(
                f"{self._predication['date_code']} · {self._predication['title_fr']}"
            )
        else:
            self.status_left.setText("Prédications")
        if self._paragraph is not None:
            self.status_right.setText(f"Paragraphe {self._paragraph} sélectionné")
        else:
            self.status_right.setText("Sélectionnez un paragraphe")

    # ----------------------- Diapositives / signaux ----------------------- #
    def set_fit_predicate(self, fits):
        """Injecte un prédicat `(texte)->bool` : le texte tient-il dans la
        projection ? Un paragraphe trop long est alors découpé en plusieurs
        diapositives (« Titre · §3 · 2/4 »)."""
        self._fits = fits
        self._deck_cache = None

    def invalidate_deck(self):
        """À appeler quand les conditions de mesure changent (taille du texte,
        écran cible) : le découpage sera recalculé à la prochaine demande."""
        self._deck_cache = None

    def _build_deck(self):
        """(diapositives, méta) : méta[i] = (numéro de paragraphe, partie).

        Un paragraphe = une diapositive, sauf s'il ne tient pas dans la
        projection (`set_fit_predicate`) : il est alors découpé par mots en
        autant de parties que nécessaire, chacune libellée « i/n ». Le résultat
        est mémorisé par prédication (la mesure de place est coûteuse)."""
        pred_id = self._predication["id"] if self._predication else None
        if self._deck_cache is not None and self._deck_cache[0] == pred_id:
            return self._deck_cache[1], self._deck_cache[2]
        deck, meta = [], []
        title = self._predication["title_fr"] if self._predication else ""
        fits = self._fits
        for number, text in self._paragraphs:
            label = f"{title} · §{number}"
            # La mesure inclut un gabarit de suffixe « 99/99 » : le libellé réel
            # « i/n » ajouté ensuite ne peut alors pas faire déborder la diapo.
            pred = None if fits is None else (
                lambda chunk, label=label: fits(f"{chunk}\n{label} · 99/99")
            )
            chunks = slides.split_to_fit(text, pred)
            total = len(chunks)
            for part, chunk in enumerate(chunks):
                suffix = label if total == 1 else f"{label} · {part + 1}/{total}"
                deck.append(f"{chunk}\n{suffix}")
                meta.append((number, part))
        self._deck_cache = (pred_id, deck, meta)
        return deck, meta

    def current_deck(self):
        """(liste de diapositives, index sélectionné) de la prédication courante."""
        if not self._paragraphs:
            return [], 0
        deck, meta = self._build_deck()
        number = self._paragraph or self._paragraphs[0][0]
        if (number, self._part) in meta:
            index = meta.index((number, self._part))
        else:
            index = next((i for i, (n, _p) in enumerate(meta) if n == number), 0)
        return deck, index

    def select_slide(self, index):
        """Sélection d'une diapositive (paragraphe ou partie de paragraphe) par
        son index — navigation du poste de contrôle."""
        if not self._paragraphs:
            return
        _deck, meta = self._build_deck()
        if not meta:
            return
        index = max(0, min(index, len(meta) - 1))
        number, part = meta[index]
        self._select_paragraph(number, part)

    def _on_project_clicked(self):
        if self._paragraph is None and self._paragraphs:
            self._select_paragraph(self._paragraphs[0][0])
        self.project_requested.emit()
