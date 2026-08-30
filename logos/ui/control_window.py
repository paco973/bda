"""
Fenêtre principale : page d'accueil et modes Bible et Prédications.

Chaque mode embarque son propre poste de contrôle (`ProjectionControls`).
Un `ProjectionController` partagé possède l'unique fenêtre de projection.
"""
from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QGuiApplication, QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QMainWindow,
    QSpinBox,
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QProgressDialog,
    QStackedWidget,
    QMessageBox,
)

from logos import updates
from logos.data import predications, scrape
from logos.data.database import get_meta, set_meta
from logos.ui import theme
from logos.ui.bible_panel import BiblePanel
from logos.ui.predication_panel import PredicationPanel
from logos.ui.update_banner import UpdateBanner, check_async
from logos.ui.widgets import circular_logo, section_title
from logos.ui.projection_controller import ProjectionController
from logos.ui.projection_controls import ProjectionControls, ProjectionSettingsBar
from logos.version import __version__

# Clé `meta` du réglage « vérifier les mises à jour au démarrage ».
_AUTO_CHECK_KEY = "check_updates_on_startup"

# Diamètre du logo sur la page d'accueil. À cette taille le sceau se lit
# (le nom de l'église est déchiffrable) et la page tient encore dans une
# fenêtre de 560 px de haut — au-delà, le contenu de l'accueil déborderait.
_HOME_LOGO_SIZE = 200


# --------------------------------------------------------------------------- #
#  Téléchargement du corpus de prédications en tâche de fond
# --------------------------------------------------------------------------- #
class _DownloadSignals(QObject):
    """Porte les signaux du téléchargement (un QRunnable n'est pas un QObject)."""
    progress = Signal(int, int, str)   # (i, total, libellé)
    finished = Signal(object)          # corpus (dict), ou None si annulé
    failed = Signal(str)               # l'index est injoignable


class _DownloadTask(QRunnable):
    """Télécharge le corpus hors du fil de l'interface (opération très longue :
    la fenêtre doit rester utilisable, et le direct ne doit jamais se figer)."""

    def __init__(self, signals, should_stop):
        super().__init__()
        self._signals = signals
        self._should_stop = should_stop

    def run(self):
        try:
            data = scrape.download_corpus(
                on_progress=self._signals.progress.emit,
                should_stop=self._should_stop,
            )
        except Exception as exc:  # index injoignable : rien n'a été modifié
            self._emit(self._signals.failed, str(exc))
            return
        self._emit(self._signals.finished, data)

    @staticmethod
    def _emit(signal, payload):
        try:
            signal.emit(payload)
        except RuntimeError:
            pass  # fenêtre fermée entre-temps : plus personne à prévenir


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

        # Réglage « versets par diapositive » : détenu par la fenêtre, car il est
        # restauré avant que le panneau Bible n'existe (construction paresseuse).
        self._verses_per_slide = 1

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

        # Branchement/débranchement d'un écran pendant l'exécution.
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self.controller.refresh_screens())
        app.screenRemoved.connect(lambda _s: self.controller.refresh_screens())

        # Les touches de présentation sont captées avant le widget focalisé
        # (voir `eventFilter`) : sans cela, elles ne survivent pas au premier clic.
        QApplication.instance().installEventFilter(self)

        self._check_updates_on_startup()

    def _fit_key(self):
        return (self.controller.font_size(), id(self.controller.screen()))

    def _on_controller_changed(self):
        key = self._fit_key()
        if key != self._last_fit_key:
            self._last_fit_key = key
            # Re-pagine les modes déjà construits selon la place disponible
            # (un mode encore jamais ouvert se paginera à sa construction).
            if self.bible_panel is not None:
                self.bible_panel.invalidate_deck()
                self._on_bible_selection()
            if self.predication_panel is not None:
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
            # Le panneau Bible n'existe pas encore (construit à la première
            # ouverture) : la fenêtre garde la valeur et la lui posera alors.
            self._verses_per_slide = int(verses)

    def _on_verses_per_slide(self, value: int):
        self._verses_per_slide = value
        self._save_settings()

    def _save_settings(self):
        screen = self.controller.screen()
        state = (
            str(self.controller.font_size()),
            screen.name() if screen is not None else "",
            str(self._verses_per_slide),
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

        # Les pages de mode sont construites à la **première ouverture**, pas au
        # lancement : peupler les deux navigateurs d'avance coûtait plusieurs
        # secondes de démarrage (des centaines de widgets, repolis en entier à
        # chaque reparentage sous la feuille de style globale) pour des pages que
        # l'opérateur ne voit pas encore — il arrive sur l'accueil.
        self.bible_page = None
        self.bible_panel = None
        self.bible_controls = None
        self.predication_page = None
        self.predication_panel = None
        self.predication_controls = None

        self.home_page = self._build_home_page()
        self.stack.addWidget(self.home_page)
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
    def _new_mode_page(self):
        """Coquille vide d'une page de mode, **déjà rattachée à la pile**.

        L'ordre compte : sous une feuille de style applicative, reparenter un
        widget repolit tout son sous-arbre. En rattachant la page d'abord, le
        navigateur qu'on y construit ensuite n'est polissé qu'une fois, au lieu
        d'une fois par étape d'assemblage (page, pile, widget central)."""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.stack.addWidget(page)
        return page, layout

    def _add_mode_side(self, page, controls):
        """Colonne « Projection » à droite d'une page de mode."""
        side = QFrame(page)
        side.setFixedWidth(300)
        side.setStyleSheet(
            f"background:{theme.COLOR_SURFACE};"
            f" border-left:1px solid {theme.COLOR_BORDER_SUBTLE};"
        )
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 16, 16, 16)
        title = section_title("Projection")
        side_layout.addWidget(title)
        side_layout.addWidget(controls)
        page.layout().addWidget(side)

    def _ensure_bible_page(self):
        """Construit la page Bible à sa première ouverture (voir `_build_ui`)."""
        if self.bible_page is not None:
            return
        page, layout = self._new_mode_page()

        self.bible_panel = BiblePanel(page)
        # Ne regrouper que les versets qui tiennent dans la projection.
        self.bible_panel.set_fit_predicate(self.controller.text_fits)
        # Réglage restauré depuis `meta` avant que le panneau n'existe. Posé
        # avant tout branchement : le poste de contrôle n'existe pas encore, et
        # changer la valeur recharge le jeu de diapositives.
        self.bible_panel.verses_spin.setValue(self._verses_per_slide)
        self.bible_panel.close_requested.connect(self._go_home)
        self.bible_panel.selection_changed.connect(self._on_bible_selection)
        self.bible_panel.project_requested.connect(self._on_bible_project)
        self.bible_panel.verses_spin.valueChanged.connect(self._on_verses_per_slide)
        layout.addWidget(self.bible_panel, 1)

        self.bible_controls = ProjectionControls(self.controller, "bible", "Bible")
        self.bible_controls.index_changed.connect(self._on_bible_controls_index)
        self._add_mode_side(page, self.bible_controls)

        self.bible_page = page
        # Charge le jeu de versets initial dans le poste de contrôle Bible.
        self._on_bible_selection()

    def _ensure_predication_page(self):
        """Construit la page Prédications à sa première ouverture."""
        if self.predication_page is not None:
            return
        page, layout = self._new_mode_page()

        self.predication_panel = PredicationPanel(page)
        # Découpe les paragraphes trop longs selon la place dans la projection.
        self.predication_panel.set_fit_predicate(self.controller.text_fits)
        self.predication_panel.download_requested.connect(self._download_predications)
        self.predication_panel.close_requested.connect(self._go_home)
        self.predication_panel.selection_changed.connect(self._on_predication_selection)
        self.predication_panel.project_requested.connect(self._on_predication_project)
        layout.addWidget(self.predication_panel, 1)

        self.predication_controls = ProjectionControls(
            self.controller, "predication", "Prédications"
        )
        self.predication_controls.index_changed.connect(self._on_predication_controls_index)
        self._add_mode_side(page, self.predication_controls)

        self.predication_page = page
        self._on_predication_selection()

    # ---------- Page d'accueil ----------
    def _build_home_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch()

        logo = circular_logo(_HOME_LOGO_SIZE)
        if logo is not None:
            logo_label = QLabel()
            logo_label.setPixmap(logo)
            logo_label.setFixedSize(_HOME_LOGO_SIZE, _HOME_LOGO_SIZE)
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
        self._ensure_bible_page()
        self._show_page(self.bible_page)

    def _open_predications(self):
        self._ensure_predication_page()
        self._show_page(self.predication_page)

    def _go_home(self):
        self._show_page(self.home_page)

    def _show_page(self, page):
        """Affiche une page et libère le focus d'un éventuel champ de saisie.

        Un champ garde légitimement les flèches (voir `eventFilter`) : en
        changeant de page, on ne veut pas que celui qu'on vient de quitter
        continue de les capter."""
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.clearFocus()
        self.stack.setCurrentWidget(page)

    def _active_controls(self):
        """Poste de contrôle du mode affiché (ou None sur l'accueil)."""
        current = self.stack.currentWidget()
        if self.bible_page is not None and current is self.bible_page:
            return self.bible_controls
        if self.predication_page is not None and current is self.predication_page:
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
        file_menu.addAction(
            action("Télécharger les prédications…", self._download_predications)
        )
        file_menu.addSeparator()
        file_menu.addAction(action("Quitter", self.close, QKeySequence.Quit))

        # « Affichage » : navigation entre les vues. La projection se pilote depuis
        # le poste de contrôle embarqué dans chaque mode.
        view_menu = bar.addMenu("Affichage")
        view_menu.addAction(action("Accueil", self._go_home, "Ctrl+H"))
        view_menu.addAction(action("Bible", self._open_bible, "F2"))
        view_menu.addAction(action("Prédications", self._open_predications, "F4"))

        help_menu = bar.addMenu("Aide")
        help_menu.addAction(action("Raccourcis clavier", self._show_shortcuts))
        help_menu.addSeparator()
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
            ("Quitter la présentation", self.controller.stop, "Shift+F5"),
            ("Diapositive suivante", self._menu_next, "Ctrl+Right"),
            ("Diapositive précédente", self._menu_prev, "Ctrl+Left"),
        ):
            self.addAction(action(text, handler, shortcut))

    def keyPressEvent(self, event):
        """Raccourcis « présentation » sans modificateur, à la manière d'un
        logiciel de diaporama : flèches / PgPréc-PgSuiv / Espace pour naviguer,
        B pour l'écran noir, Échap pour quitter la présentation. Qt ne fait
        remonter ici que les touches non consommées par le widget qui a le focus
        — un champ de recherche ou une liste garde donc ses propres flèches."""
        if event.key() == Qt.Key_Escape:
            # Échap quitte la présentation, quel que soit le mode affiché.
            # Exception : dans un champ de recherche rempli, il vide le champ.
            # Qt n'y consomme pas la touche, et couper le direct par réflexe en
            # effaçant une recherche serait le pire moment pour le faire.
            focused = self.focusWidget()
            if isinstance(focused, QLineEdit) and focused.text():
                focused.clear()
            else:
                self.controller.stop()
            event.accept()
            return

        if self._presentation_key(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)

    # ---------- Touches de présentation ----------
    def _presentation_key(self, key) -> bool:
        """Exécute l'action de présentation liée à `key`. False si aucune."""
        controls = self._active_controls()
        if controls is None:
            return False
        if key in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown, Qt.Key_Space):
            controls.go_next()
            return True
        if key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp):
            controls.go_prev()
            return True
        if key == Qt.Key_B:
            controls.toggle_blackout()
            return True
        return False

    def eventFilter(self, obj, event):
        """Capte les touches de présentation **avant** le widget focalisé.

        `keyPressEvent` ne voit que les touches dont personne n'a voulu, et les
        widgets qui ont le focus en usage courant mangent justement les flèches :
        une ligne de lecture, une case numérotée, une zone défilante. Après un
        clic sur un verset — le geste le plus fréquent — les flèches ne faisaient
        donc rien. Pire, le sélecteur d'écran a le focus à l'ouverture d'un mode :
        ↓ y changeait l'écran de projection en plein culte.

        Les widgets dont les flèches ont un usage propre gardent la main : champs
        de saisie, compteurs, listes de résultats, sélecteur d'écran une fois
        cliqué. Un modificateur enfoncé laisse aussi passer (Ctrl+←/→ reste géré
        par les `QAction`).
        """
        if event.type() != QEvent.KeyPress:
            return False
        if QApplication.activeModalWidget() is not None:
            return False       # une boîte de dialogue a la main
        # Pas de garde sur la fenêtre au premier plan : la seule autre fenêtre
        # de l'application est celle de projection, affichée en plein écran, et
        # les flèches doivent y agir aussi (elle n'a aucun widget focalisable).
        if event.modifiers() not in (Qt.NoModifier, Qt.KeypadModifier):
            return False
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QSpinBox, QComboBox, QAbstractItemView)):
            return False
        if event.key() == Qt.Key_Space and isinstance(focused, QAbstractButton):
            return False       # Espace doit continuer d'actionner un bouton
        return self._presentation_key(event.key())

    def _show_shortcuts(self):
        QMessageBox.information(
            self,
            "Raccourcis clavier",
            "<b>Projection</b> (mode affiché)<br>"
            "F5 — Projeter<br>"
            "F6 ou B — Écran noir<br>"
            "Échap ou Maj+F5 — Quitter la présentation<br>"
            "→ ↓ PgSuiv Espace ou Ctrl+→ — Diapositive suivante<br>"
            "← ↑ PgPréc ou Ctrl+← — Diapositive précédente<br><br>"
            "<i>Les flèches seules sont inactives quand le curseur est dans un "
            "champ de recherche ; Échap y vide d'abord le champ.</i><br><br>"
            "<b>Navigation</b><br>"
            "Ctrl+H — Accueil · F2 — Bible · F4 — Prédications",
        )

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

    # ---------- Téléchargement des prédications ----------
    def _download_predications(self):
        """Téléchargement du corpus depuis branham.fr, après une confirmation
        explicite rappelant les risques et conséquences."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Télécharger les prédications")
        box.setText("Télécharger le corpus des prédications depuis branham.fr ?")
        box.setInformativeText(
            "Avant de continuer, prenez connaissance des risques et "
            "conséquences :\n\n"
            "• Contenu sous copyright (branham.fr / VGR) : réservé à l'usage "
            "interne de l'église. Ne le rediffusez pas et ne l'incluez jamais "
            "dans un paquet distribué publiquement.\n\n"
            "• Environ 1 800 pages seront demandées au site, avec une pause de "
            "politesse entre chacune : comptez une heure à une heure et demie, "
            "avec une connexion Internet stable. Évitez de lancer cela pendant "
            "un culte.\n\n"
            "• À la fin, le corpus de ce poste sera remplacé par la version "
            "téléchargée. En cas d'annulation ou d'échec, rien ne change.\n\n"
            "En continuant, vous confirmez disposer des droits nécessaires "
            "pour cet usage."
        )
        download_btn = box.addButton("Télécharger", QMessageBox.AcceptRole)
        cancel_btn = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_btn)  # le geste prudent est le choix par défaut
        box.exec()
        if box.clickedButton() is not download_btn:
            return

        progress = QProgressDialog(
            "Récupération de l'index des prédications…", "Annuler", 0, 0, self
        )
        progress.setWindowTitle("Téléchargement des prédications")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setMinimumWidth(480)
        progress.setValue(0)

        cancelled = {"stop": False}
        progress.canceled.connect(lambda: cancelled.update(stop=True))

        signals = _DownloadSignals(self)

        def on_progress(i, total, label):
            progress.setMaximum(total)
            progress.setValue(i)
            progress.setLabelText(f"[{i}/{total}]  {label}")

        def on_finished(data):
            progress.reset()
            if data is None:  # annulé : rien n'a été conservé
                QMessageBox.information(
                    self, "Téléchargement annulé",
                    "Le téléchargement a été annulé : le corpus du poste n'a "
                    "pas été modifié.",
                )
                return
            path = predications.save_user_corpus(data)
            if self.predication_panel is not None:
                # Le mode a pu ne jamais être ouvert (téléchargement via le menu) :
                # il lira le nouveau corpus à sa construction.
                self.predication_panel.reload()
                self._on_predication_selection()
            QMessageBox.information(
                self, "Téléchargement terminé",
                f"{len(data['predications'])} prédications importées.\n\n"
                f"Le corpus est conservé dans :\n{path}\n\n"
                "Rappel : contenu sous copyright, à ne pas rediffuser.",
            )

        def on_failed(message):
            progress.reset()
            QMessageBox.warning(
                self, "Téléchargement impossible",
                "Le site branham.fr est injoignable ou sa réponse est "
                f"illisible ({message}).\n\nLe corpus du poste n'a pas été "
                "modifié — réessayez plus tard.",
            )

        signals.progress.connect(on_progress)
        signals.finished.connect(on_finished)
        signals.failed.connect(on_failed)
        QThreadPool.globalInstance().start(
            _DownloadTask(signals, lambda: cancelled["stop"])
        )

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
        elif result.status == updates.NOT_PUBLISHED:
            QMessageBox.information(
                self,
                "Mises à jour",
                "Aucune version n'est publiée pour l'instant à l'adresse de "
                "mise à jour : le serveur répond bien, mais le fichier "
                "« latest.json » y est introuvable.",
            )
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
        if self.bible_controls is None:
            return  # page en cours de construction : rechargée à la fin
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
        if self.predication_controls is None:
            return  # page en cours de construction : rechargée à la fin
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
