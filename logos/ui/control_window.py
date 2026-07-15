"""
Fenêtre principale : page d'accueil et mode Bible.

Le mode Bible embarque son propre poste de contrôle (`ProjectionControls`).
Un `ProjectionController` partagé possède l'unique fenêtre de projection.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QStackedWidget,
    QMessageBox,
)

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

        self._build_ui()

        # Le nombre de versets qui tiennent dépend de la taille du texte et de
        # l'écran cible : recharger le jeu Bible quand l'un des deux change.
        self._last_fit_key = self._fit_key()
        self.controller.changed.connect(self._on_controller_changed)

        # Branchement/débranchement d'un écran pendant l'exécution.
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self.controller.refresh_screens())
        app.screenRemoved.connect(lambda _s: self.controller.refresh_screens())

    def _fit_key(self):
        return (self.controller.font_size(), id(self.controller.screen()))

    def _on_controller_changed(self):
        key = self._fit_key()
        if key != self._last_fit_key:
            self._last_fit_key = key
            self._on_bible_selection()  # re-pagine selon la place disponible

    # ---------- Construction de l'interface ----------
    def _build_ui(self):
        self.stack = QStackedWidget()

        self.bible_page = self._build_bible_page()
        self.home_page = self._build_home_page()

        self.stack.addWidget(self.home_page)
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

    # ---------- Mode Bible ----------
    def _build_bible_page(self):
        self.bible_panel = BiblePanel()
        # Ne regrouper que les versets qui tiennent dans la projection.
        self.bible_panel.set_fit_predicate(self.controller.text_fits)
        self.bible_panel.close_requested.connect(self._go_home)
        self.bible_panel.selection_changed.connect(self._on_bible_selection)
        self.bible_panel.project_requested.connect(self._on_bible_project)

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
    def _open_bible(self):
        self.stack.setCurrentWidget(self.bible_page)

    def _go_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def _active_controls(self):
        """Poste de contrôle du mode affiché (ou None sur l'accueil)."""
        if self.stack.currentWidget() is self.bible_page:
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
        file_menu.addAction(action("Quitter", self.close, QKeySequence.Quit))

        # « Affichage » : navigation entre les vues. La projection se pilote depuis
        # le poste de contrôle embarqué dans le mode Bible.
        view_menu = bar.addMenu("Affichage")
        view_menu.addAction(action("Accueil", self._go_home, "Ctrl+H"))
        view_menu.addAction(action("Bible", self._open_bible, "F2"))

        help_menu = bar.addMenu("Aide")
        help_menu.addAction(action("À propos", self._show_about))

        # Raccourcis de projection (agissent sur le mode affiché) : conservés au
        # niveau fenêtre pour le direct, mais hors menu (doublon avec les boutons).
        for text, handler, shortcut in (
            ("Projeter", self._menu_project, "F5"),
            ("Écran noir", self._menu_blackout, "F6"),
            ("Arrêter la projection", self.controller.stop, "Shift+F5"),
            ("Diapositive suivante", self._menu_next, "Ctrl+Right"),
            ("Diapositive précédente", self._menu_prev, "Ctrl+Left"),
        ):
            self.addAction(action(text, handler, shortcut))

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
            "Projection des passages bibliques sur un écran secondaire "
            "pendant les cultes.",
        )

    # ---------- Bible ----------
    def _on_bible_selection(self):
        deck, index = self.bible_panel.current_deck()
        self.bible_controls.load(deck, index)

    def _on_bible_project(self):
        self.bible_controls.project()

    def _on_bible_controls_index(self, index: int):
        # Navigation depuis le poste de contrôle Bible : sélectionne la
        # diapositive (groupe de versets) correspondante.
        self.bible_panel.select_slide(index)

    def closeEvent(self, event):
        self.controller.close()
        super().closeEvent(event)
