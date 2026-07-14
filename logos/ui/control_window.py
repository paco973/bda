"""
Fenêtre de contrôle : bibliothèque de chants, édition des paroles,
navigation des diapositives et pilotage de la fenêtre de projection.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QSplitter,
    QMessageBox,
    QTabWidget,
    QGroupBox,
)

from logos.data import database, service, slides
from logos.ui import theme
from logos.ui.bible_panel import BiblePanel
from logos.ui.projection_window import ProjectionWindow


class ControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{theme.APP_NAME} - Contrôle")
        self.resize(1100, 650)

        self.projection = ProjectionWindow()
        self.current_song_id = None
        self.current_slides = []

        self._build_ui()
        self._refresh_song_list()
        self._refresh_service_list()
        self._refresh_screens()

        # Mise à jour de la liste des écrans si un vidéoprojecteur est
        # branché/débranché pendant que l'application tourne.
        app = QGuiApplication.instance()
        app.screenAdded.connect(self._on_screens_changed)
        app.screenRemoved.connect(self._on_screens_changed)

    # ---------- Construction de l'interface ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # --- Colonne 1 : bibliothèque (chants + Bible) ---
        songs_tab = QWidget()
        left_layout = QVBoxLayout(songs_tab)
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

        self.bible_panel = BiblePanel()
        self.bible_panel.display_requested.connect(self._on_passage_display)
        self.bible_panel.service_add_requested.connect(self._on_passage_add_to_service)

        left_tabs = QTabWidget()
        left_tabs.addTab(songs_tab, "Chants")
        left_tabs.addTab(self.bible_panel, "Bible")
        splitter.addWidget(left_tabs)

        # --- Colonne 2 : édition ---
        middle = QGroupBox("Édition du chant")
        middle_layout = QVBoxLayout(middle)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titre du chant")
        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setPlaceholderText(
            "Paroles ici.\n\nLaissez une ligne vide entre chaque diapositive."
        )
        save_btn = QPushButton("Enregistrer le chant")
        save_btn.clicked.connect(self._save_song)

        middle_layout.addWidget(QLabel("Titre"))
        middle_layout.addWidget(self.title_edit)
        middle_layout.addWidget(QLabel("Paroles (une diapo par paragraphe)"))
        middle_layout.addWidget(self.lyrics_edit)
        middle_layout.addWidget(save_btn)
        splitter.addWidget(middle)

        # --- Colonne 3 : ordre du culte + diapositives + projection ---
        right = QWidget()
        right_layout = QVBoxLayout(right)

        service_group = QGroupBox("Ordre du culte")
        service_layout = QVBoxLayout(service_group)
        self.service_list = QListWidget()
        self.service_list.setToolTip("Cliquer un élément charge ses diapositives")
        self.service_list.itemClicked.connect(self._on_service_item_clicked)
        service_layout.addWidget(self.service_list)

        service_btn_row = QHBoxLayout()
        up_btn = QPushButton("▲")
        up_btn.setToolTip("Monter dans l'ordre du culte")
        up_btn.setProperty("buttonStyle", "secondary")
        up_btn.clicked.connect(lambda: self._move_service_item(-1))
        down_btn = QPushButton("▼")
        down_btn.setToolTip("Descendre dans l'ordre du culte")
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
        right_layout.addWidget(service_group, 2)

        slides_group = QGroupBox("Diapositives")
        slides_layout = QVBoxLayout(slides_group)
        self.slide_list = QListWidget()
        self.slide_list.setToolTip("Cliquer une diapositive la projette")
        self.slide_list.itemClicked.connect(self._send_slide_to_projection)
        self.slide_list.currentItemChanged.connect(self._on_current_slide_changed)
        slides_layout.addWidget(self.slide_list)

        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Précédent")
        self.prev_btn.clicked.connect(self._prev_slide)
        self.slide_counter = QLabel("")
        self.slide_counter.setAlignment(Qt.AlignCenter)
        self.next_btn = QPushButton("Suivant ▶")
        self.next_btn.clicked.connect(self._next_slide)
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.slide_counter, 1)
        nav_row.addWidget(self.next_btn)
        slides_layout.addLayout(nav_row)
        right_layout.addWidget(slides_group, 3)

        projection_group = QGroupBox("Projection")
        projection_layout = QVBoxLayout(projection_group)

        # Aperçu en direct : reflète exactement ce que voit l'assemblée
        self.preview_label = QLabel("")
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setFixedHeight(110)
        projection_layout.addWidget(self.preview_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        projection_layout.addWidget(self.status_label)

        screen_row = QHBoxLayout()
        screen_row.addWidget(QLabel("Écran"))
        self.screen_combo = QComboBox()
        screen_row.addWidget(self.screen_combo, 1)
        projection_layout.addLayout(screen_row)

        self.toggle_projection_btn = QPushButton("Démarrer la projection")
        self.toggle_projection_btn.setCheckable(True)
        self.toggle_projection_btn.clicked.connect(self._toggle_projection)
        projection_layout.addWidget(self.toggle_projection_btn)

        self.blank_btn = QPushButton("Écran noir (masquer)")
        self.blank_btn.setCheckable(True)
        self.blank_btn.clicked.connect(self._toggle_blank)
        projection_layout.addWidget(self.blank_btn)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Taille du texte"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 120)
        self.font_spin.setValue(48)
        self.font_spin.valueChanged.connect(self.projection.set_font_size)
        font_row.addWidget(self.font_spin, 1)
        projection_layout.addLayout(font_row)

        right_layout.addWidget(projection_group)
        splitter.addWidget(right)

        splitter.setSizes([260, 440, 400])
        self._update_status()

    # ---------- Écrans ----------
    def _refresh_screens(self):
        previous = self.screen_combo.currentData()
        self.screen_combo.clear()
        screens = QGuiApplication.screens()
        for i, screen in enumerate(screens):
            name = screen.name()
            geo = screen.geometry()
            self.screen_combo.addItem(
                f"Écran {i + 1} - {name} ({geo.width()}x{geo.height()})", screen
            )
        if previous is not None and previous in screens:
            # Conserve l'écran choisi par l'opérateur s'il existe toujours
            self.screen_combo.setCurrentIndex(screens.index(previous))
        elif self.screen_combo.count() > 1:
            # Par défaut, propose le dernier écran détecté (souvent le vidéoprojecteur)
            self.screen_combo.setCurrentIndex(self.screen_combo.count() - 1)

    def _on_screens_changed(self, _screen):
        projecting = self.toggle_projection_btn.isChecked()
        projection_screen = self.screen_combo.currentData()
        self._refresh_screens()
        # Si l'écran utilisé pour la projection vient d'être débranché,
        # on arrête proprement plutôt que de laisser une fenêtre orpheline.
        if projecting and projection_screen not in QGuiApplication.screens():
            self.toggle_projection_btn.setChecked(False)
            self._toggle_projection(False)

    def _toggle_projection(self, checked: bool):
        if checked:
            screen = self.screen_combo.currentData()
            if screen is None:
                QMessageBox.warning(self, "Aucun écran", "Aucun écran détecté.")
                self.toggle_projection_btn.setChecked(False)
                return
            self.projection.set_font_size(self.font_spin.value())
            self.projection.show_on_screen(screen)
            self.toggle_projection_btn.setText("Arrêter la projection")
        else:
            self.projection.hide()
            self.toggle_projection_btn.setText("Démarrer la projection")
        self._update_status()

    def _toggle_blank(self, checked: bool):
        self.projection.toggle_blank(checked)
        self.blank_btn.setText("Réafficher" if checked else "Écran noir (masquer)")
        self.preview_label.setText("" if checked else self.projection.current_text())
        self._update_status()

    def _update_status(self):
        """Indicateur d'état sous l'aperçu : arrêté / en direct / écran noir."""
        if not self.toggle_projection_btn.isChecked():
            self.status_label.setText("○ Projection arrêtée")
            self.status_label.setStyleSheet(f"color: {theme.COLOR_TEXT_MUTED};")
        elif self.blank_btn.isChecked():
            self.status_label.setText("● Écran noir")
            self.status_label.setStyleSheet(f"color: {theme.COLOR_DANGER_HOVER};")
        else:
            self.status_label.setText(f"● En direct — {self.screen_combo.currentText()}")
            self.status_label.setStyleSheet(f"color: {theme.COLOR_LIVE};")

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
        self.slide_list.clear()
        self.current_slides = slides.lyrics_to_slides(lyrics)
        for i, slide in enumerate(self.current_slides):
            preview = slide.replace("\n", " / ")
            item = QListWidgetItem(f"{i + 1}. {preview[:60]}")
            item.setData(Qt.UserRole, slide)
            self.slide_list.addItem(item)
        self._update_slide_counter()

    def _new_song(self):
        self.current_song_id = None
        self.title_edit.clear()
        self.lyrics_edit.clear()
        self.slide_list.clear()
        self._update_slide_counter()
        self.title_edit.setFocus()

    def _save_song(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Titre manquant", "Merci de saisir un titre.")
            return
        lyrics = self.lyrics_edit.toPlainText()
        self.current_song_id = database.save_song(
            self.current_song_id, title, lyrics
        )
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

    def _on_passage_display(self, _label: str, content: str):
        self._refresh_slides(content)

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

    # ---------- Projection ----------
    def _send_slide_to_projection(self, item: QListWidgetItem):
        text = item.data(Qt.UserRole)
        self.projection.set_text(text)
        self.preview_label.setText(text)
        if self.blank_btn.isChecked():
            self.blank_btn.setChecked(False)
            self.projection.toggle_blank(False)
            self._update_status()

    def _on_current_slide_changed(self, current, _previous):
        # Naviguer dans la liste (boutons, flèches du clavier) projette la diapo
        if current is not None:
            self._send_slide_to_projection(current)
        self._update_slide_counter()

    def _update_slide_counter(self):
        count = self.slide_list.count()
        row = self.slide_list.currentRow()
        if count == 0:
            self.slide_counter.setText("")
        elif row < 0:
            self.slide_counter.setText(f"{count} diapositive(s)")
        else:
            self.slide_counter.setText(f"{row + 1} / {count}")

    def _next_slide(self):
        row = self.slide_list.currentRow()
        if row < self.slide_list.count() - 1:
            self.slide_list.setCurrentRow(row + 1)

    def _prev_slide(self):
        row = self.slide_list.currentRow()
        if row > 0:
            self.slide_list.setCurrentRow(row - 1)

    def closeEvent(self, event):
        self.projection.close()
        super().closeEvent(event)