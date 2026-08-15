"""
Fenêtre principale : page d'accueil et modes Bible et Prédications.

Chaque mode embarque son propre poste de contrôle (`ProjectionControls`).
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

from logos import updates
from logos.data.database import get_meta, set_meta
from logos.ui import theme
from logos.ui.bible_panel import BiblePanel
from logos.ui.predication_panel import PredicationPanel
from logos.ui.update_banner import UpdateBanner, check_async
from logos.ui.widgets import circular_logo
from logos.ui.projection_controller import ProjectionController
from logos.ui.projection_controls import ProjectionControls, ProjectionSettingsBar
from logos.version import __version__

# Clé `meta` du réglage « vérifier les mises à jour au démarrage ».
_AUTO_CHECK_KEY = "check_updates_on_startup"


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

        # Réglages persistants (taille du texte, écran, versets par diapositive) :
        # restaurés depuis la table `meta`, sauvegardés à chaque changement.
        self._saved_settings = None
        self._restore_settings()

        # Le contenu qui tient dépend de la taille du texte et de l'écran
        # cible : recharger les jeux de diapos quand l'un des deux change.
        self._last_fit_key = self._fit_key()
        self.controller.changed.connect(self._on_controller_changed)
        self.controller.changed.connect(self._save_settings)
        self.bible_panel.verses_spin.valueChanged.connect(
            lambda _value: self._save_settings()
        )

        # Branchement/débranchement d'un écran pendant l'exécution.
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self.controller.refresh_screens())
        app.screenRemoved.connect(lambda _s: self.controller.refresh_screens())

        self._check_updates_on_startup()

    def _fit_key(self):
        return (self.controller.font_size(), id(self.controller.screen()))

    def _on_controller_changed(self):
        key = self._fit_key()
        if key != self._last_fit_key:
            self._last_fit_key = key
            # Re-pagine les deux modes selon la place disponible.
            self._on_bible_selection()
            self.predication_panel.invalidate_deck()
            self._on_predication_selection()

    # ---------- Réglages persistants ----------
    def _restore_settings(self):
        size = get_meta("ui_font_size")
        if size and size.isdigit():
            self.controller.set_font_size(int(size))
        screen_name = get_meta("ui_screen_name")
        if screen_name:
            for screen in self.controller.screens():
                if screen.name() == screen_name:
                    self.controller.set_screen(screen)
                    break
        verses = get_meta("ui_verses_per_slide")
        if verses and verses.isdigit():
            self.bible_panel.verses_spin.setValue(int(verses))

    def _save_settings(self):
        screen = self.controller.screen()
        state = (
            str(self.controller.font_size()),
            screen.name() if screen is not None else "",
            str(self.bible_panel.verses_spin.value()),
        )
        if state == self._saved_settings:
            return  # `changed` est émis souvent : n'écrire que si ça a bougé
        self._saved_settings = state
        set_meta("ui_font_size", state[0])
        set_meta("ui_screen_name", state[1])
        set_meta("ui_verses_per_slide", state[2])

    # ---------- Construction de l'interface ----------
    def _build_ui(self):
        self.stack = QStackedWidget()

        self.bible_page = self._build_bible_page()
        self.predication_page = self._build_predication_page()
        self.home_page = self._build_home_page()

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.bible_page)
        self.stack.addWidget(self.predication_page)
        self.stack.setCurrentWidget(self.home_page)

        # Réglages de projection globaux (écran + taille du texte), sous les pages.
        # Masqués sur l'accueil, où la projection n'a pas de sens.
        self.settings_bar = ProjectionSettingsBar(self.controller)
        self.settings_bar.setStyleSheet(
            f"background:{theme.COLOR_SURFACE};"
            f" border-top:1px solid {theme.COLOR_BORDER_SUBTLE};"
        )
        self.stack.currentChanged.connect(self._update_settings_bar_visibility)

        # Bandeau « nouvelle version disponible » : masqué tant qu'aucune mise à
        # jour n'a été trouvée, au-dessus de tout le reste.
        self.update_banner = UpdateBanner()

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.update_banner)
        central_layout.addWidget(self.stack, 1)
        central_layout.addWidget(self.settings_bar)
        self.setCentralWidget(central)
        self._update_settings_bar_visibility()

        self._build_menu_bar()

    def _update_settings_bar_visibility(self, *_):
        self.settings_bar.setVisible(self.stack.currentWidget() is not self.home_page)

    # ---------- Pages des modes ----------
    def _mode_page(self, panel, controls):
        """Page d'un mode : navigateur à gauche + colonne « Projection » à droite."""
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
        side_layout.addWidget(controls)

        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel, 1)
        layout.addWidget(side)
        return page

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

        page = self._mode_page(self.bible_panel, self.bible_controls)
        # Charge le jeu de versets initial dans le poste de contrôle Bible.
        self._on_bible_selection()
        return page

    def _build_predication_page(self):
        self.predication_panel = PredicationPanel()
        # Découpe les paragraphes trop longs selon la place dans la projection.
        self.predication_panel.set_fit_predicate(self.controller.text_fits)
        self.predication_panel.close_requested.connect(self._go_home)
        self.predication_panel.selection_changed.connect(self._on_predication_selection)
        self.predication_panel.project_requested.connect(self._on_predication_project)

        # Projection via « Projeter le paragraphe » du navigateur (pas de doublon).
        self.predication_controls = ProjectionControls(
            self.controller, "predication", "Prédications", show_project_button=False
        )
        self.predication_controls.index_changed.connect(self._on_predication_controls_index)

        page = self._mode_page(self.predication_panel, self.predication_controls)
        self._on_predication_selection()
        return page

    # ---------- Page d'accueil ----------
    def _build_home_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch()

        logo = circular_logo(96)
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
            ("🎙️", "Prédications", "Parcourir les prédications et projeter des paragraphes.",
             self._open_predications),
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

    def _open_predications(self):
        self.stack.setCurrentWidget(self.predication_page)

    def _go_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def _active_controls(self):
        """Poste de contrôle du mode affiché (ou None sur l'accueil)."""
        current = self.stack.currentWidget()
        if current is self.bible_page:
            return self.bible_controls
        if current is self.predication_page:
            return self.predication_controls
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
        # le poste de contrôle embarqué dans chaque mode.
        view_menu = bar.addMenu("Affichage")
        view_menu.addAction(action("Accueil", self._go_home, "Ctrl+H"))
        view_menu.addAction(action("Bible", self._open_bible, "F2"))
        view_menu.addAction(action("Prédications", self._open_predications, "F4"))

        help_menu = bar.addMenu("Aide")
        help_menu.addAction(
            action("Rechercher les mises à jour…", self._check_updates_manually)
        )
        self.auto_check_action = QAction("Vérifier au démarrage", self)
        self.auto_check_action.setCheckable(True)
        self.auto_check_action.setChecked(self._auto_check_enabled())
        self.auto_check_action.toggled.connect(
            lambda enabled: set_meta(_AUTO_CHECK_KEY, "1" if enabled else "0")
        )
        help_menu.addAction(self.auto_check_action)
        help_menu.addSeparator()
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
            f"<b>{theme.APP_NAME}</b> — version {__version__}<br>"
            "Logiciel de présentation pour l'église.<br><br>"
            "Projection des passages bibliques et des paragraphes de "
            "prédications sur un écran secondaire pendant les cultes.",
        )

    # ---------- Mises à jour ----------
    def _auto_check_enabled(self) -> bool:
        """Vérification au démarrage : activée sauf refus explicite."""
        return get_meta(_AUTO_CHECK_KEY) != "0"

    def _check_updates_on_startup(self):
        """Vérification silencieuse au lancement : elle n'affiche le bandeau que
        s'il y a effectivement une nouvelle version, et ne dit rien en cas
        d'échec — un poste sans connexion ne doit voir aucune alerte."""
        if self._auto_check_enabled() and updates.is_configured():
            check_async(self, self._on_startup_check_done)

    def _on_startup_check_done(self, result):
        if result.status == updates.AVAILABLE:
            self.update_banner.show_release(result.release)

    def _check_updates_manually(self):
        """Vérification demandée depuis le menu : ici, toutes les issues sont
        rapportées, y compris « pas d'URL configurée » et l'échec réseau."""
        if not updates.is_configured():
            QMessageBox.information(
                self,
                "Mises à jour",
                "Aucune adresse de mise à jour n'est configurée dans cette "
                "version de l'application : la recherche automatique est "
                "désactivée.",
            )
            return
        check_async(self, self._on_manual_check_done)

    def _on_manual_check_done(self, result):
        if result.status == updates.AVAILABLE:
            self.update_banner.show_release(result.release)
            box = QMessageBox(self)
            box.setWindowTitle("Mises à jour")
            box.setTextFormat(Qt.PlainText)  # notes distantes : jamais du HTML
            box.setText(
                f"La version {result.release.version} est disponible "
                f"(vous utilisez la {__version__})."
                + (f"\n\n{result.release.notes}" if result.release.notes else "")
            )
            box.exec()
        elif result.status == updates.UP_TO_DATE:
            QMessageBox.information(
                self,
                "Mises à jour",
                f"{theme.APP_NAME} est à jour (version {__version__}).",
            )
        else:
            QMessageBox.warning(
                self,
                "Mises à jour",
                "Impossible de vérifier les mises à jour : le serveur est "
                "injoignable ou sa réponse est illisible.\n\n"
                "Ce n'est pas bloquant, l'application fonctionne hors ligne.",
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

    # ---------- Prédications ----------
    def _on_predication_selection(self):
        deck, index = self.predication_panel.current_deck()
        self.predication_controls.load(deck, index)

    def _on_predication_project(self):
        self.predication_controls.project()

    def _on_predication_controls_index(self, index: int):
        # Navigation depuis le poste de contrôle : sélectionne le paragraphe.
        self.predication_panel.select_slide(index)

    def closeEvent(self, event):
        self.controller.close()
        super().closeEvent(event)
