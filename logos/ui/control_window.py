"""
Fenêtre principale : accueil, mode Chants/Culte et mode Bible.

Chaque mode embarque son propre poste de contrôle (`ProjectionControls`).
Un `ProjectionController` partagé possède l'unique fenêtre de projection et
applique l'exclusivité : un seul mode peut être « à l'antenne » à la fois.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QSplitter,
    QStackedWidget,
    QMessageBox,
    QGroupBox,
)

from logos.data import database, service, slides
from logos.ui import theme
from logos.ui.bible_panel import BiblePanel, _circular_logo
from logos.ui.projection_controller import ProjectionController
from logos.ui.projection_controls import ProjectionControls, ProjectionSettingsBar


class _HomeCard(QFrame):
    """Grande carte cliquable de la page d'accueil (icône + titre + description)."""

    clicked = Signal()

    def __init__(self, icon: str, title: str, description: str):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(260, 150)
        self._apply_style(hover=False)

        col = QVBoxLayout(self)
        col.setContentsMargins(20, 18, 20, 18)
        col.setSpacing(6)
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size:34px; background:transparent; border:none;")
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:17px; font-weight:700;"
            f" background:transparent; border:none;"
        )
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:12px; font-weight:500;"
            f" background:transparent; border:none;"
        )
        col.addWidget(icon_label)
        col.addWidget(title_label)
        col.addWidget(desc_label)
        col.addStretch()

    def _apply_style(self, hover: bool):
        border = theme.COLOR_PRIMARY if hover else theme.COLOR_BORDER_SUBTLE
        bg = theme.COLOR_SURFACE_ALT if hover else theme.COLOR_SURFACE
        self.setStyleSheet(
            f"_HomeCard {{ background:{bg}; border:1px solid {border}; border-radius:12px; }}"
        )

    def enterEvent(self, event):
        self._apply_style(hover=True)

    def leaveEvent(self, event):
        self._apply_style(hover=False)

    def mousePressEvent(self, event):
        self.clicked.emit()


class ControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{theme.APP_NAME} - Contrôle")
        self.resize(1180, 700)

        # Contrôleur de projection partagé (unique fenêtre de projection).
        self.controller = ProjectionController()
        self.current_song_id = None
        self.current_slides = []
        self._syncing_slide = False

        self._build_ui()
        self._refresh_song_list()
        self._refresh_service_list()

        # Branchement/débranchement d'un écran pendant l'exécution.
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self.controller.refresh_screens())
        app.screenRemoved.connect(lambda _s: self.controller.refresh_screens())

    # ---------- Construction de l'interface ----------
    def _build_ui(self):
        self.stack = QStackedWidget()

        self.control_page = self._build_chants_page()
        self.bible_page = self._build_bible_page()
        self.home_page = self._build_home_page()

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.control_page)
        self.stack.addWidget(self.bible_page)
        self.stack.setCurrentWidget(self.home_page)

        # Réglages de projection globaux (écran + taille du texte), sous les pages.
        # Masqués sur l'accueil, où la projection n'a pas de sens.
        self.settings_bar = ProjectionSettingsBar(self.controller)
        self.settings_bar.setStyleSheet(
            f"background:{theme.COLOR_SURFACE};"
            f" border-top:1px solid {theme.COLOR_BORDER_SUBTLE};"
        )
        self.stack.currentChanged.connect(self._update_settings_bar_visibility)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.stack, 1)
        central_layout.addWidget(self.settings_bar)
        self.setCentralWidget(central)
        self._update_settings_bar_visibility()

        self._build_menu_bar()

    def _update_settings_bar_visibility(self, *_):
        self.settings_bar.setVisible(self.stack.currentWidget() is not self.home_page)

    # ---------- Mode Chants / Culte ----------
    def _build_chants_page(self):
        page = QWidget()
        root = QHBoxLayout(page)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # --- Colonne 1 : bibliothèque de chants ---
        songs_col = QWidget()
        left_layout = QVBoxLayout(songs_col)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Rechercher un chant...")
        self.search_box.textChanged.connect(self._refresh_song_list)
        self.song_list = QListWidget()
        self.song_list.currentItemChanged.connect(self._on_song_selected)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("Nouveau")
        new_btn.clicked.connect(self._new_song)
        del_btn = QPushButton("Supprimer")
        del_btn.setProperty("buttonStyle", "danger")
        del_btn.clicked.connect(self._delete_song)
        btn_row.addWidget(new_btn)
        btn_row.addWidget(del_btn)

        add_to_service_btn = QPushButton("Ajouter au culte")
        add_to_service_btn.clicked.connect(self._add_current_song_to_service)

        left_layout.addWidget(self.search_box)
        left_layout.addWidget(self.song_list)
        left_layout.addLayout(btn_row)
        left_layout.addWidget(add_to_service_btn)
        splitter.addWidget(songs_col)

        # --- Colonne 2 : édition + ordre du culte ---
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)

        edit_group = QGroupBox("Édition du chant")
        edit_layout = QVBoxLayout(edit_group)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titre du chant")
        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setPlaceholderText(
            "Paroles ici.\n\nLaissez une ligne vide entre chaque diapositive."
        )
        save_btn = QPushButton("Enregistrer le chant")
        save_btn.clicked.connect(self._save_song)
        edit_layout.addWidget(QLabel("Titre"))
        edit_layout.addWidget(self.title_edit)
        edit_layout.addWidget(QLabel("Paroles (une diapo par paragraphe)"))
        edit_layout.addWidget(self.lyrics_edit)
        edit_layout.addWidget(save_btn)
        middle_layout.addWidget(edit_group, 3)

        service_group = QGroupBox("Ordre du culte")
        service_layout = QVBoxLayout(service_group)
        self.service_list = QListWidget()
        self.service_list.setToolTip("Cliquer un élément charge ses diapositives")
        self.service_list.itemClicked.connect(self._on_service_item_clicked)
        service_layout.addWidget(self.service_list)
        service_btn_row = QHBoxLayout()
        up_btn = QPushButton("▲")
        up_btn.setProperty("buttonStyle", "secondary")
        up_btn.clicked.connect(lambda: self._move_service_item(-1))
        down_btn = QPushButton("▼")
        down_btn.setProperty("buttonStyle", "secondary")
        down_btn.clicked.connect(lambda: self._move_service_item(1))
        remove_btn = QPushButton("Retirer")
        remove_btn.setProperty("buttonStyle", "secondary")
        remove_btn.clicked.connect(self._remove_service_item)
        clear_btn = QPushButton("Vider")
        clear_btn.setProperty("buttonStyle", "danger")
        clear_btn.clicked.connect(self._clear_service)
        for btn in (up_btn, down_btn, remove_btn, clear_btn):
            service_btn_row.addWidget(btn)
        service_layout.addLayout(service_btn_row)
        middle_layout.addWidget(service_group, 2)
        splitter.addWidget(middle)

        # --- Colonne 3 : diapositives + poste de contrôle de projection ---
        right = QWidget()
        right_layout = QVBoxLayout(right)

        slides_group = QGroupBox("Diapositives")
        slides_layout = QVBoxLayout(slides_group)
        self.slide_list = QListWidget()
        self.slide_list.setToolTip("Cliquer une diapositive la met en aperçu")
        self.slide_list.currentItemChanged.connect(self._on_slide_row_changed)
        slides_layout.addWidget(self.slide_list)
        right_layout.addWidget(slides_group, 3)

        projection_group = QGroupBox("Projection")
        projection_layout = QVBoxLayout(projection_group)
        self.chants_controls = ProjectionControls(
            self.controller, "chants", "Chants / Culte"
        )
        self.chants_controls.index_changed.connect(self._on_controls_index_changed)
        projection_layout.addWidget(self.chants_controls)
        right_layout.addWidget(projection_group, 2)
        splitter.addWidget(right)

        splitter.setSizes([250, 460, 320])
        return page

    # ---------- Mode Bible ----------
    def _build_bible_page(self):
        self.bible_panel = BiblePanel()
        self.bible_panel.close_requested.connect(self._go_home)
        self.bible_panel.selection_changed.connect(self._on_bible_selection)
        self.bible_panel.project_requested.connect(self._on_bible_project)
        self.bible_panel.service_add_requested.connect(self._on_passage_add_to_service)

        # Pas de bouton « Projeter » ici : le navigateur a « Projeter le verset ».
        self.bible_controls = ProjectionControls(
            self.controller, "bible", "Bible", show_project_button=False
        )
        self.bible_controls.index_changed.connect(self._on_bible_controls_index)

        side = QFrame()
        side.setFixedWidth(300)
        side.setStyleSheet(
            f"background:{theme.COLOR_SURFACE};"
            f" border-left:1px solid {theme.COLOR_BORDER_SUBTLE};"
        )
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Projection")
        title.setStyleSheet(
            f"color:{theme.COLOR_TEXT_MUTED}; font-size:11px; font-weight:700;"
            f" letter-spacing:2px; background:transparent;"
        )
        side_layout.addWidget(title)
        side_layout.addWidget(self.bible_controls)

        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.bible_panel, 1)
        layout.addWidget(side)

        # Charge le jeu de versets initial dans le poste de contrôle Bible.
        self._on_bible_selection()
        return page

    # ---------- Page d'accueil ----------
    def _build_home_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch()

        logo = _circular_logo(96)
        if logo is not None:
            logo_label = QLabel()
            logo_label.setPixmap(logo)
            logo_label.setFixedSize(96, 96)
            logo_label.setAlignment(Qt.AlignCenter)
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(logo_label)
            row.addStretch()
            outer.addLayout(row)
            outer.addSpacing(18)

        title = QLabel(theme.APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{theme.COLOR_TEXT}; font-size:34px; font-weight:700; background:transparent;"
        )
        subtitle = QLabel("Logiciel de présentation pour l'église")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            f"color:{theme.BRONZE}; font-size:14px; font-weight:500; background:transparent;"
        )
        outer.addWidget(title)
        outer.addSpacing(4)
        outer.addWidget(subtitle)
        outer.addSpacing(32)

        cards = [
            ("🎵", "Chants / Culte", "Bibliothèque de chants, ordre du culte et projection.",
             self._show_chants),
            ("📖", "Bible", "Naviguer dans les livres et projeter des versets.",
             self._open_bible),
            ("ℹ️", "À propos", "Informations sur l'application.",
             self._show_about),
        ]
        grid = QHBoxLayout()
        grid.setSpacing(18)
        grid.addStretch()
        for icon, name, desc, handler in cards:
            card = _HomeCard(icon, name, desc)
            card.clicked.connect(handler)
            grid.addWidget(card)
        grid.addStretch()
        outer.addLayout(grid)

        outer.addStretch()
        return page

    # ---------- Navigation entre pages ----------
    def _show_chants(self):
        self.stack.setCurrentWidget(self.control_page)

    def _open_bible(self):
        self.stack.setCurrentWidget(self.bible_page)

    def _go_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def _active_controls(self):
        """Poste de contrôle du mode actuellement affiché (ou None sur l'accueil)."""
        current = self.stack.currentWidget()
        if current is self.control_page:
            return self.chants_controls
        if current is self.bible_page:
            return self.bible_controls
        return None

    # ---------- Barre de menus ----------
    def _build_menu_bar(self):
        bar = self.menuBar()
        # Garder la barre dans la fenêtre (sinon macOS l'envoie dans le menu système).
        bar.setNativeMenuBar(False)

        def action(text, handler, shortcut=None):
            act = QAction(text, self)
            act.triggered.connect(handler)
            if shortcut is not None:
                act.setShortcut(QKeySequence(shortcut))
            return act

        file_menu = bar.addMenu("Fichier")
        file_menu.addAction(action("Nouveau chant", self._new_song, QKeySequence.New))
        file_menu.addAction(action("Enregistrer le chant", self._save_song, QKeySequence.Save))
        file_menu.addAction(action("Supprimer le chant", self._delete_song))
        file_menu.addSeparator()
        file_menu.addAction(action("Quitter", self.close, QKeySequence.Quit))

        songs_menu = bar.addMenu("Chants")
        songs_menu.addAction(action("Nouveau chant", self._new_song))
        songs_menu.addAction(action("Ajouter au culte", self._add_current_song_to_service))
        songs_menu.addAction(action("Rechercher un chant", self._focus_song_search, QKeySequence.Find))

        service_menu = bar.addMenu("Culte")
        service_menu.addAction(action("Monter l'élément", lambda: self._move_service_item(-1)))
        service_menu.addAction(action("Descendre l'élément", lambda: self._move_service_item(1)))
        service_menu.addAction(action("Retirer l'élément", self._remove_service_item))
        service_menu.addSeparator()
        service_menu.addAction(action("Vider l'ordre du culte", self._clear_service))

        # « Affichage » ne garde que la navigation entre les vues : la projection
        # se pilote depuis le poste de contrôle embarqué dans chaque mode.
        view_menu = bar.addMenu("Affichage")
        view_menu.addAction(action("Accueil", self._go_home, "Ctrl+H"))
        view_menu.addAction(action("Chants / Culte", self._show_chants, "F3"))
        view_menu.addAction(action("Bible", self._open_bible, "F2"))

        help_menu = bar.addMenu("Aide")
        help_menu.addAction(action("À propos", self._show_about))

        # Raccourcis de projection (agissent sur le mode affiché) : conservés au
        # niveau fenêtre pour le direct, mais retirés du menu pour éviter les
        # doublons avec les boutons du poste de contrôle.
        for text, handler, shortcut in (
            ("Projeter", self._menu_project, "F5"),
            ("Écran noir", self._menu_blackout, "F6"),
            ("Arrêter la projection", self.controller.stop, "Shift+F5"),
            ("Diapositive suivante", self._menu_next, "Ctrl+Right"),
            ("Diapositive précédente", self._menu_prev, "Ctrl+Left"),
        ):
            self.addAction(action(text, handler, shortcut))

    def _focus_song_search(self):
        self._show_chants()
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _menu_project(self):
        controls = self._active_controls()
        if controls is not None:
            controls.project()

    def _menu_blackout(self):
        controls = self._active_controls()
        if controls is not None:
            controls.toggle_blackout()

    def _menu_next(self):
        controls = self._active_controls()
        if controls is not None:
            controls.go_next()

    def _menu_prev(self):
        controls = self._active_controls()
        if controls is not None:
            controls.go_prev()

    def _show_about(self):
        QMessageBox.about(
            self,
            f"À propos de {theme.APP_NAME}",
            f"<b>{theme.APP_NAME}</b><br>"
            "Logiciel de présentation pour l'église.<br><br>"
            "Projection des paroles de chants et des passages bibliques "
            "sur un écran secondaire pendant les cultes.",
        )

    # ---------- Chants ----------
    def _refresh_song_list(self):
        self.song_list.clear()
        for row in database.list_songs(self.search_box.text()):
            item = QListWidgetItem(row["title"])
            item.setData(Qt.UserRole, row["id"])
            self.song_list.addItem(item)

    def _on_song_selected(self, current, _previous):
        if current is None:
            return
        song_id = current.data(Qt.UserRole)
        row = database.get_song(song_id)
        if row is None:
            return
        self.current_song_id = song_id
        self.title_edit.setText(row["title"])
        self.lyrics_edit.setPlainText(row["lyrics"])
        self._refresh_slides(row["lyrics"])

    def _refresh_slides(self, lyrics: str):
        self.current_slides = slides.lyrics_to_slides(lyrics)
        self.slide_list.blockSignals(True)
        self.slide_list.clear()
        for i, slide in enumerate(self.current_slides):
            preview = slide.replace("\n", " / ")
            item = QListWidgetItem(f"{i + 1}. {preview[:60]}")
            item.setData(Qt.UserRole, slide)
            self.slide_list.addItem(item)
        self.slide_list.blockSignals(False)
        self.chants_controls.load(self.current_slides, 0)
        if self.current_slides:
            self.slide_list.setCurrentRow(0)

    def _on_slide_row_changed(self, current, _previous):
        if current is None or self._syncing_slide:
            return
        self.chants_controls.set_index(self.slide_list.row(current))

    def _on_controls_index_changed(self, index: int):
        self._syncing_slide = True
        self.slide_list.setCurrentRow(index)
        self._syncing_slide = False

    def _new_song(self):
        self.current_song_id = None
        self.title_edit.clear()
        self.lyrics_edit.clear()
        self._refresh_slides("")
        self.title_edit.setFocus()

    def _save_song(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Titre manquant", "Merci de saisir un titre.")
            return
        lyrics = self.lyrics_edit.toPlainText()
        self.current_song_id = database.save_song(self.current_song_id, title, lyrics)
        service.update_song_label(self.current_song_id, title)
        self._refresh_song_list()
        self._refresh_service_list()
        self._refresh_slides(lyrics)

    def _delete_song(self):
        item = self.song_list.currentItem()
        if item is None:
            return
        song_id = item.data(Qt.UserRole)
        confirm = QMessageBox.question(
            self, "Confirmer", "Supprimer ce chant définitivement ?"
        )
        if confirm == QMessageBox.Yes:
            database.delete_song(song_id)
            self._new_song()
            self._refresh_song_list()
            self._refresh_service_list()

    # ---------- Ordre du culte ----------
    def _refresh_service_list(self):
        self.service_list.clear()
        for row in service.list_items():
            prefix = "♪" if row["kind"] == "song" else "📖"
            item = QListWidgetItem(f"{prefix} {row['label']}")
            item.setData(Qt.UserRole, row["id"])
            self.service_list.addItem(item)

    def _add_current_song_to_service(self):
        item = self.song_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "Aucun chant", "Sélectionnez d'abord un chant dans la liste."
            )
            return
        service.add_song(item.data(Qt.UserRole), item.text())
        self._refresh_service_list()

    def _on_passage_add_to_service(self, label: str, content: str):
        service.add_passage(label, content)
        self._refresh_service_list()

    def _on_service_item_clicked(self, item: QListWidgetItem):
        row = service.get_item(item.data(Qt.UserRole))
        if row is None:
            return
        if row["kind"] == "song":
            song = database.get_song(row["song_id"])
            if song is None:
                QMessageBox.warning(self, "Chant introuvable", "Ce chant a été supprimé.")
                self._refresh_service_list()
                return
            self._refresh_slides(song["lyrics"])
        else:
            self._refresh_slides(row["content"])

    def _move_service_item(self, delta: int):
        item = self.service_list.currentItem()
        if item is None:
            return
        item_id = item.data(Qt.UserRole)
        service.move_item(item_id, delta)
        self._refresh_service_list()
        for i in range(self.service_list.count()):
            if self.service_list.item(i).data(Qt.UserRole) == item_id:
                self.service_list.setCurrentRow(i)
                break

    def _remove_service_item(self):
        item = self.service_list.currentItem()
        if item is None:
            return
        service.remove_item(item.data(Qt.UserRole))
        self._refresh_service_list()

    def _clear_service(self):
        if self.service_list.count() == 0:
            return
        confirm = QMessageBox.question(
            self, "Confirmer", "Vider tout l'ordre du culte ?"
        )
        if confirm == QMessageBox.Yes:
            service.clear_items()
            self._refresh_service_list()

    # ---------- Bible ----------
    def _on_bible_selection(self):
        deck, index = self.bible_panel.current_deck()
        self.bible_controls.load(deck, index)

    def _on_bible_project(self):
        self.bible_controls.project()

    def _on_bible_controls_index(self, index: int):
        # Navigation depuis le poste de contrôle Bible : sélectionne le verset.
        self.bible_panel.select_verse(index + 1)

    def closeEvent(self, event):
        self.controller.close()
        super().closeEvent(event)
