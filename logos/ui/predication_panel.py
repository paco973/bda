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
    QListWidget,
    QListWidgetItem,
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
    ProgressiveRows,
    TOPBAR_LOGO_SIZE,
    circular_logo,
    clear_layout,
    section_title,
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
        self._active = None
        self.set_active(False)

    def set_active(self, active: bool):
        # Le panneau appelle set_active sur les 26 lettres à chaque changement :
        # sans ce garde, on reposerait trois feuilles de style par carte alors
        # que deux cartes seulement changent d'état (cf. `NumButton`).
        if active == self._active:
            return
        self._active = active
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
        self._active = None
        self.set_active(False)

    def set_active(self, active: bool):
        if active == self._active:
            return  # appelé sur toute la rangée à chaque changement de préfixe
        self._active = active
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
        self._active = None
        self.set_active(False)

    def set_active(self, active: bool):
        # Une recherche renvoie jusqu'à 200 lignes et le panneau les parcourt
        # toutes à chaque clic : sans ce garde, on reposait près de mille
        # feuilles de style pour deux lignes réellement modifiées (280 ms).
        if active == self._active:
            return
        self._active = active
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


# --------------------------------------------------------------------------- #
#  Panneau principal
# --------------------------------------------------------------------------- #
class PredicationPanel(QWidget):
    selection_changed = Signal()   # prédication/paragraphe (jeu de diapos) modifié
    project_requested = Signal()   # « Projeter le paragraphe »
    close_requested = Signal()     # retour à l'accueil
    download_requested = Signal()  # « Télécharger les prédications… » (état vide)

    def __init__(self, parent=None):
        # Le parent est passé dès la construction : rattacher le panneau
        # après coup repolirait tout son sous-arbre (coûteux sous QSS).
        super().__init__(parent)
        self.setStyleSheet(f"background:{theme.COLOR_BACKGROUND};")

        self._letter = None
        self._prefix = None
        self._predication = None       # {id, date_code, title_fr} sélectionné
        self._paragraph = None         # numéro de paragraphe sélectionné
        self._part = 0                 # partie sélectionnée d'un paragraphe découpé
        self._partial_start = 0        # position de départ dans le paragraphe sélectionné
        self._paragraphs = []          # (number, text) de la prédication courante
        self._letter_cards = {}        # lettre -> _LetterCard
        self._prefix_chips = {}        # préfixe -> _PrefixChip
        self._fits = None              # prédicat (texte)->bool : tient-il à l'écran ?
        self._deck_cache = None        # (clé, deck, meta) — jeu de diapos assemblé
        self._chunks = {}              # numéro -> morceaux du paragraphe entier
        self._chunks_pred = None       # prédication à laquelle ces morceaux appartiennent

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

        logo = circular_logo(TOPBAR_LOGO_SIZE)
        if logo is not None:
            logo_label = QLabel()
            logo_label.setPixmap(logo)
            logo_label.setFixedSize(TOPBAR_LOGO_SIZE, TOPBAR_LOGO_SIZE)
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

        # Recherche plein texte dans les paragraphes (« le Saint-Esprit »),
        # pendant de la recherche dans les versets du mode Bible.
        text_box = QFrame()
        text_box.setStyleSheet(
            f"background:{theme.COLOR_SURFACE_ALT}; border:1px solid {theme.COLOR_BORDER};"
            f" border-radius:6px;"
        )
        text_row = QHBoxLayout(text_box)
        text_row.setContentsMargins(12, 4, 12, 4)
        text_row.setSpacing(8)
        pilcrow = QLabel("¶")
        pilcrow.setStyleSheet(
            f"color:{theme.BRONZE}; background:transparent; border:none; font-size:13px;"
        )
        text_row.addWidget(pilcrow)
        self.text_search_edit = QLineEdit()
        self.text_search_edit.setPlaceholderText("Rechercher dans les paragraphes…")
        self.text_search_edit.setFixedWidth(220)
        self.text_search_edit.setClearButtonEnabled(True)
        self.text_search_edit.setStyleSheet(
            f"background:transparent; border:none; color:{theme.COLOR_TEXT}; font-size:13px;"
        )
        self.text_search_edit.textChanged.connect(self._on_text_search_text)
        self.text_search_edit.returnPressed.connect(self._on_text_search_return)
        text_row.addWidget(self.text_search_edit)
        row.addWidget(text_box)
        self._text_search_box = text_box

        # Liste flottante des paragraphes trouvés, ancrée sous le champ.
        self.text_results = QListWidget(self)
        self.text_results.setVisible(False)
        self.text_results.setWordWrap(False)
        self.text_results.setTextElideMode(Qt.ElideRight)
        self.text_results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_results.setStyleSheet(
            f"QListWidget {{ background:{theme.COLOR_SURFACE_ALT}; color:{theme.COLOR_TEXT};"
            f" border:1px solid {theme.COLOR_BORDER}; border-radius:6px; font-size:13px; }}"
            f"QListWidget::item {{ padding:6px 10px; }}"
            f"QListWidget::item:selected, QListWidget::item:hover"
            f" {{ background:{theme.COLOR_PRIMARY}; color:{theme.COLOR_TEXT_ON_PRIMARY}; }}"
        )
        self.text_results.itemClicked.connect(self._on_text_result_clicked)

        # Anti-rebond : les recherches partent 300 ms après la dernière frappe
        # (la liste n'est pas reconstruite à chaque caractère).
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._run_search)

        self._text_search_timer = QTimer(self)
        self._text_search_timer.setSingleShot(True)
        self._text_search_timer.setInterval(300)
        self._text_search_timer.timeout.connect(self._run_text_search)

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
        self.kicker_label = section_title(subdued=True)
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
        self._reading_rows = ProgressiveRows(self.reading_layout)
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
        alpha_col.addWidget(section_title("Alphabet"))
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
        pred_title = section_title("Prédication", subdued=True)
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
        para_title = section_title("Paragraphe", subdued=True)
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
        with self.alphabet_host.bulk_fill() as flow:
            for letter, count in predications.letters_with_counts():
                card = _LetterCard(letter, count)
                card.clicked.connect(self._select_letter)
                self._letter_cards[letter] = card
                flow.addWidget(card)
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
        self._reading_rows.reset([])  # vide la colonne et annule le reliquat
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
        self._chunks = {}
        self._chunks_pred = None
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
        self._prefix_chips = {}
        first = None
        with self.prefix_host.bulk_fill() as flow:
            clear_layout(flow)
            for prefix, count in predications.prefixes_with_counts(self._letter):
                chip = _PrefixChip(prefix, count)
                chip.picked.connect(self._select_prefix)
                self._prefix_chips[prefix] = chip
                flow.addWidget(chip)
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
            self._reading_rows.reset([])
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
        self._partial_start = 0
        self._rebuild_reading()
        self._rebuild_paragraphs()
        self._update_status_texts()
        self.selection_changed.emit()

    def _rebuild_reading(self):
        self._para_rows = {}
        rows = []
        for number, text in self._paragraphs:
            row = NumberedTextRow(number, text)
            row.clicked.connect(self._select_paragraph)
            row.partial_selected.connect(self._on_partial_selected)
            row.set_active(number == self._paragraph)
            self._para_rows[number] = row
            rows.append(row)
        # Posées par lots : une longue prédication figeait la fenêtre le temps
        # de mettre en page des centaines de paragraphes.
        self._reading_rows.reset(rows)

    def _rebuild_paragraphs(self):
        self._para_buttons = {}
        with self.para_host.bulk_fill() as flow:
            clear_layout(flow)
            for number, _text in self._paragraphs:
                btn = NumButton(number)
                btn.set_active(number == self._paragraph)
                btn.picked.connect(self._select_paragraph)
                self._para_buttons[number] = btn
                flow.addWidget(btn)

    def _select_paragraph(self, number, part=0):
        if number != self._paragraph:
            self._partial_start = 0  # la sélection partielle suit son paragraphe
        self._paragraph = number
        self._part = part
        for n, row in getattr(self, "_para_rows", {}).items():
            row.set_active(n == number)
        for n, btn in getattr(self, "_para_buttons", {}).items():
            btn.set_active(n == number)
        # Fait défiler la lecture jusqu'au paragraphe sélectionné (en le posant
        # d'abord s'il fait encore partie du reliquat à afficher).
        row = getattr(self, "_para_rows", {}).get(number)
        if row is not None:
            self._reading_rows.ensure_placed(row)
            self.reading_area.ensureWidgetVisible(row)
        self._update_status_texts()
        self.selection_changed.emit()

    def _on_partial_selected(self, number, offset):
        """Sélection à la souris dans un paragraphe : la projection démarre à la
        sélection (offset -1 = pas de sélection -> paragraphe entier)."""
        if number != self._paragraph:
            return
        partial = max(0, offset) if offset >= 0 else 0
        if partial == self._partial_start:
            return
        self._partial_start = partial
        # Le texte projeté est plus court : le découpage repart de son début.
        self._part = 0
        self._update_status_texts()
        self.selection_changed.emit()  # recharge l'aperçu (et le direct si à l'antenne)

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

    # ------------------ Recherche dans le texte des paragraphes ------------ #
    def _on_text_search_text(self, text):
        if len(text.strip()) < 3:  # même seuil que predications.search_paragraphs
            self._text_search_timer.stop()
            self.text_results.hide()
            return
        self._text_search_timer.start()

    def _run_text_search(self):
        query = self.text_search_edit.text().strip()
        if len(query) < 3 or not self._letter_cards:
            self.text_results.hide()
            return
        results = predications.search_paragraphs(query)
        self.text_results.clear()
        if not results:
            empty = QListWidgetItem("Aucun paragraphe trouvé")
            empty.setFlags(Qt.NoItemFlags)
            self.text_results.addItem(empty)
        for row in results:
            texte = row["text"]
            if len(texte) > 90:
                texte = texte[:90].rstrip() + "…"
            item = QListWidgetItem(
                f"{row['date_code']} · {row['title_fr']} · §{row['number']} — {texte}"
            )
            item.setData(Qt.UserRole, row)
            self.text_results.addItem(item)
        self._place_text_results()
        self.text_results.show()
        self.text_results.raise_()

    def _place_text_results(self):
        """Ancre la liste de résultats sous le champ de recherche plein texte."""
        anchor = self._text_search_box.mapTo(
            self, self._text_search_box.rect().bottomLeft()
        )
        row_height = self.text_results.sizeHintForRow(0)
        height = min(360, self.text_results.count() * max(row_height, 24) + 8)
        width = min(720, max(460, self.width() - anchor.x() - 24))
        self.text_results.setGeometry(anchor.x(), anchor.y() + 6, width, height)

    def _on_text_result_clicked(self, item):
        cible = item.data(Qt.UserRole)
        if cible:
            # Arrêter l'anti-rebond : une frappe encore en attente rouvrirait la
            # liste juste après le saut.
            self._text_search_timer.stop()
            self.text_results.hide()
            self._jump_to_paragraph(cible)

    def _on_text_search_return(self):
        """Entrée : rejoint le premier paragraphe trouvé."""
        self._text_search_timer.stop()
        self._run_text_search()
        for i in range(self.text_results.count()):
            cible = self.text_results.item(i).data(Qt.UserRole)
            if cible:
                self.text_results.hide()
                self._jump_to_paragraph(cible)
                return

    def _jump_to_paragraph(self, cible):
        """Rejoint un paragraphe trouvé par la recherche plein texte.

        La prédication visée est en général sous une autre lettre et un autre
        préfixe que ceux affichés : on refait donc tout le chemin (lettre,
        préfixe, prédication, paragraphe). `letter` et `prefix` viennent du
        résultat, ce qui évite une requête de plus."""
        if cible["letter"] != self._letter:
            self._select_letter(cible["letter"])
        if cible["prefix"] != self._prefix:
            self._select_prefix(cible["prefix"])
        if self._predication is None or self._predication["id"] != cible["predication_id"]:
            self._select_predication(cible["predication_id"], row_data=cible)
        self._select_paragraph(cible["number"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.text_results.isVisible():
            self._place_text_results()

    def keyPressEvent(self, event):
        # Échap referme la liste de résultats (la touche remonte depuis le champ).
        if event.key() == Qt.Key_Escape and self.text_results.isVisible():
            self.text_results.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    # ----------------------------- Statut --------------------------------- #
    def _update_status_texts(self):
        if self._predication is not None:
            self.status_left.setText(
                f"{self._predication['date_code']} · {self._predication['title_fr']}"
            )
        else:
            self.status_left.setText("Prédications")
        if self._paragraph is not None:
            status = f"Paragraphe {self._paragraph} sélectionné"
            if self._partial_start > 0:
                status += " · projeté à partir de la sélection"
            self.status_right.setText(status)
        else:
            self.status_right.setText("Sélectionnez un paragraphe")

    # ----------------------- Diapositives / signaux ----------------------- #
    def set_fit_predicate(self, fits):
        """Injecte un prédicat `(texte)->bool` : le texte tient-il dans la
        projection ? Un paragraphe trop long est alors découpé en plusieurs
        diapositives (« Titre · §3 · 2/4 »)."""
        self._fits = fits
        self._deck_cache = None
        self._chunks = {}
        self._chunks_pred = None

    def invalidate_deck(self):
        """À appeler quand les conditions de mesure changent (taille du texte,
        écran cible) : le découpage sera recalculé à la prochaine demande."""
        self._deck_cache = None
        self._chunks = {}
        self._chunks_pred = None

    def _paragraph_chunks(self, number, raw_text, label, fits):
        """Morceaux projetables d'un paragraphe, mémorisés pour le texte entier.

        Les morceaux sont indexés par numéro de paragraphe : ils n'ont de sens
        que pour **une** prédication, et deux prédications ont toutes deux un
        paragraphe 1. Le cache porte donc l'identifiant de sa prédication et se
        vide de lui-même quand elle change — s'en remettre à un vidage explicite
        au bon endroit ferait projeter le texte d'une autre prédication.

        Le paragraphe tronqué par une sélection à la souris n'est pas mémorisé :
        il change à chaque glissement de souris, et il est le seul dans ce cas.
        Sans cela, chaque sélection redécouperait toute la prédication — un quart
        de seconde sur les plus longues, juste au relâchement du bouton."""
        pred_id = self._predication["id"] if self._predication else None
        if pred_id != self._chunks_pred:
            self._chunks = {}
            self._chunks_pred = pred_id
        text = self._paragraph_display_text(number, raw_text)
        if text is not raw_text:
            return self._split(text, label, fits)
        chunks = self._chunks.get(number)
        if chunks is None:
            chunks = self._split(raw_text, label, fits)
            self._chunks[number] = chunks
        return chunks

    @staticmethod
    def _split(text, label, fits):
        """Découpe un texte en morceaux qui tiennent dans la projection."""
        # La mesure inclut un gabarit de suffixe « 99/99 » : le libellé réel
        # « i/n » ajouté ensuite ne peut alors pas faire déborder la diapo.
        pred = None if fits is None else (
            lambda chunk: fits(f"{chunk}\n{label} · 99/99")
        )
        return slides.split_to_fit(text, pred)

    def _paragraph_display_text(self, number, text) -> str:
        """Texte projetable d'un paragraphe : tronqué au début de la sélection à
        la souris (« … la seconde moitié ») si elle porte sur le paragraphe
        sélectionné."""
        if number == self._paragraph and self._partial_start > 0:
            return "…" + text[self._partial_start:].lstrip()
        return text

    def _deck_key(self):
        """Ce dont dépend le découpage : la prédication, et — seulement quand une
        sélection partielle est active — le paragraphe visé et son point de
        départ. Sans sélection partielle, la clé ne bouge pas d'un paragraphe à
        l'autre : le découpage reste mémorisé."""
        pred_id = self._predication["id"] if self._predication else None
        if not self._partial_start:
            return (pred_id, None, 0)
        return (pred_id, self._paragraph, self._partial_start)

    def _build_deck(self):
        """(diapositives, méta) : méta[i] = (numéro de paragraphe, partie).

        Un paragraphe = une diapositive, sauf s'il ne tient pas dans la
        projection (`set_fit_predicate`) : il est alors découpé par mots en
        autant de parties que nécessaire, chacune libellée « i/n ». Le résultat
        est mémorisé (la mesure de place est coûteuse), la clé tenant compte
        d'une éventuelle sélection partielle."""
        key = self._deck_key()
        if self._deck_cache is not None and self._deck_cache[0] == key:
            return self._deck_cache[1], self._deck_cache[2]
        deck, meta = [], []
        title = self._predication["title_fr"] if self._predication else ""
        fits = self._fits
        for number, raw_text in self._paragraphs:
            label = f"{title} · §{number}"
            chunks = self._paragraph_chunks(number, raw_text, label, fits)
            total = len(chunks)
            for part, chunk in enumerate(chunks):
                suffix = label if total == 1 else f"{label} · {part + 1}/{total}"
                deck.append(f"{chunk}\n{suffix}")
                meta.append((number, part))
        self._deck_cache = (key, deck, meta)
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
