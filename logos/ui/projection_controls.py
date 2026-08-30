"""
Poste de contrôle de projection réutilisable, embarqué par chaque mode
(Bible, Prédications, et tout mode futur — ex. Chants), plus la barre de
réglages globale.

`ProjectionControls` pilote la projection via le `ProjectionController` partagé :
aperçu en direct, navigation entre diapositives, « Écran noir », « Arrêter », et
un indicateur montrant quel mode est à l'antenne. Chaque mode projette depuis son
propre bouton (« Projeter le verset », « Projeter le paragraphe ») : le poste n'en
propose pas un second, mais expose `project()` pour le raccourci F5.

Le choix de l'écran cible et la taille du texte sont **globaux** (ils valent pour
toute la projection quel que soit le mode) : ils vivent dans une unique
`ProjectionSettingsBar`, pas dans chaque poste de contrôle.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QMessageBox,
)

from logos.ui import theme


class ProjectionControls(QWidget):
    # Navigation interne (diapo changée) — permet au mode de synchroniser sa vue.
    index_changed = Signal(int)

    def __init__(self, controller, mode_key: str, mode_label: str):
        super().__init__()
        self.controller = controller
        self.mode_key = mode_key
        controller.register_mode(mode_key, mode_label)

        self._slides = []
        self._index = 0

        self._build_ui()
        controller.changed.connect(self._sync)
        self._sync()

    # ----------------------------- Construction --------------------------- #
    def _build_ui(self):
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(9)

        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignCenter)
        col.addWidget(self.badge)

        # Aperçu en direct : reflète ce que ce mode projette (ou projetterait).
        self.preview = QLabel("")
        self.preview.setObjectName("PreviewLabel")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setWordWrap(True)
        self.preview.setFixedHeight(118)
        col.addWidget(self.preview)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setProperty("buttonStyle", "secondary")
        self.prev_btn.setToolTip("Diapositive précédente")
        self.prev_btn.clicked.connect(self.go_prev)
        self.counter = QLabel("—")
        self.counter.setAlignment(Qt.AlignCenter)
        self.next_btn = QPushButton("▶")
        self.next_btn.setProperty("buttonStyle", "secondary")
        self.next_btn.setToolTip("Diapositive suivante")
        self.next_btn.clicked.connect(self.go_next)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.counter, 1)
        nav.addWidget(self.next_btn)
        col.addLayout(nav)

        row = QHBoxLayout()
        self.blackout_btn = QPushButton("Écran noir")
        self.blackout_btn.setCheckable(True)
        self.blackout_btn.setStyleSheet(theme.btn_secondary_style())
        self.blackout_btn.clicked.connect(self._on_blackout_clicked)
        self.stop_btn = QPushButton("Arrêter")
        self.stop_btn.setProperty("buttonStyle", "secondary")
        self.stop_btn.setToolTip("Arrêter la projection (aucun mode à l'antenne)")
        self.stop_btn.clicked.connect(self.controller.stop)
        row.addWidget(self.blackout_btn, 1)
        row.addWidget(self.stop_btn)
        col.addLayout(row)

        col.addStretch()

    # ------------------------------ Diapos -------------------------------- #
    def load(self, slides, index: int = 0):
        """Charge le jeu de diapositives de ce mode (sans projeter)."""
        self._slides = list(slides)
        if self._slides:
            self._index = max(0, min(index, len(self._slides) - 1))
        else:
            self._index = 0
        self._push_live_if_on_air()
        self._sync()

    def set_index(self, index: int):
        if not self._slides:
            return
        index = max(0, min(index, len(self._slides) - 1))
        if index == self._index:
            return
        self._index = index
        self._push_live_if_on_air()
        self._sync()
        self.index_changed.emit(index)

    def go_prev(self):
        self.set_index(self._index - 1)

    def go_next(self):
        self.set_index(self._index + 1)

    def current_text(self) -> str:
        return self._slides[self._index] if self._slides else ""

    def _push_live_if_on_air(self):
        if self.controller.is_on_air(self.mode_key):
            self.controller.update_live(self.mode_key, self.current_text())

    # ---------------------------- Projection ------------------------------ #
    def project(self):
        """Met ce mode à l'antenne avec la diapositive courante."""
        if not self._slides:
            return
        if not self.controller.project(self.mode_key, self.current_text()):
            QMessageBox.warning(
                self, "Aucun écran",
                "Aucun écran de projection détecté. Branchez un second écran.",
            )

    def toggle_blackout(self):
        self.controller.set_blackout(not self.controller.blackout())

    def _on_blackout_clicked(self, checked: bool):
        self.controller.set_blackout(checked)

    # ---------------------------- Synchronisation ------------------------- #
    def _set_badge(self, text: str, color: str):
        self.badge.setText(text)
        self.badge.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:700; background:transparent;"
        )

    def _sync(self):
        controller = self.controller
        on_air = controller.on_air()
        if on_air == self.mode_key:
            self._set_badge("● À l'antenne", theme.COLOR_LIVE)
        elif on_air is not None:
            self._set_badge(
                f"○ {controller.mode_label(on_air)} à l'antenne", theme.COLOR_WARNING
            )
        else:
            self._set_badge("○ Projection arrêtée", theme.COLOR_TEXT_MUTED)

        blackout = controller.blackout()
        self.blackout_btn.blockSignals(True)
        self.blackout_btn.setChecked(blackout)
        self.blackout_btn.blockSignals(False)
        self.blackout_btn.setText("Réafficher" if blackout else "Écran noir")
        self.blackout_btn.setStyleSheet(theme.btn_danger_style() if blackout else theme.btn_secondary_style())

        total = len(self._slides)
        self.counter.setText(f"{self._index + 1} / {total}" if total else "—")
        if controller.is_on_air(self.mode_key) and blackout:
            self.preview.setText("")
        else:
            self.preview.setText(self.current_text())


class ProjectionSettingsBar(QWidget):
    """Réglages de projection **globaux** : écran cible + taille du texte.

    Une seule instance pour toute l'application (les réglages valent pour la
    projection quel que soit le mode à l'antenne).
    """

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(10)

        row.addWidget(QLabel("Écran de projection"))
        self.screen_combo = QComboBox()
        # Focus au clic seulement : sinon ce sélecteur prend le focus dès
        # l'ouverture d'un mode, et une flèche « diapositive suivante » y
        # changerait l'écran de projection au lieu d'avancer.
        self.screen_combo.setFocusPolicy(Qt.ClickFocus)
        self.screen_combo.setMinimumWidth(240)
        self.screen_combo.currentIndexChanged.connect(self._on_screen_changed)
        row.addWidget(self.screen_combo)

        row.addStretch()

        row.addWidget(QLabel("Taille du texte"))
        self.font_spin = QSpinBox()
        self.font_spin.setFocusPolicy(Qt.ClickFocus)  # idem : pas de focus par défaut
        self.font_spin.setRange(12, 120)
        self.font_spin.valueChanged.connect(self.controller.set_font_size)
        row.addWidget(self.font_spin)

        controller.changed.connect(self._sync)
        controller.screens_changed.connect(self._rebuild_screens)
        self._rebuild_screens()
        self._sync()

    def _on_screen_changed(self, _index: int):
        self.controller.set_screen(self.screen_combo.currentData())

    def _rebuild_screens(self):
        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()
        for i, screen in enumerate(self.controller.screens()):
            geo = screen.geometry()
            self.screen_combo.addItem(
                f"Écran {i + 1} — {screen.name()} ({geo.width()}×{geo.height()})", screen
            )
        self.screen_combo.blockSignals(False)
        self._select_screen(self.controller.screen())

    def _select_screen(self, screen):
        self.screen_combo.blockSignals(True)
        for i in range(self.screen_combo.count()):
            if self.screen_combo.itemData(i) is screen:
                self.screen_combo.setCurrentIndex(i)
                break
        self.screen_combo.blockSignals(False)

    def _sync(self):
        self._select_screen(self.controller.screen())
        self.font_spin.blockSignals(True)
        self.font_spin.setValue(self.controller.font_size())
        self.font_spin.blockSignals(False)
