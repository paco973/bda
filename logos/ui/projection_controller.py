"""
Contrôleur de projection partagé.

Possède l'unique `ProjectionWindow` et l'état commun à tous les modes :
écran cible, taille du texte, écran noir, et le mode actuellement « à l'antenne ».
Règle d'exclusivité : un seul mode projette à la fois — projeter depuis un mode
coupe automatiquement celui qui était à l'antenne.

Ne connaît pas les modes concrets (il les identifie par une clé) et ne dépend
d'aucune couche `data` : il coordonne l'affichage, rien d'autre.
"""
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QGuiApplication, QFont, QFontMetrics

from logos.ui.projection_window import ProjectionWindow

# Marges de la fenêtre de projection (voir ProjectionWindow) : à retrancher de
# l'écran pour connaître la surface réellement disponible pour le texte.
_PROJECTION_MARGIN = 40


class ProjectionController(QObject):
    # État partagé modifié (écran, taille, écran noir, mode à l'antenne, texte).
    changed = Signal()
    # La liste des écrans disponibles a changé (branchement/débranchement).
    screens_changed = Signal()

    def __init__(self):
        super().__init__()
        self.window = ProjectionWindow()
        self._font_size = 48
        self._blackout = False
        self._on_air = None       # clé du mode à l'antenne, ou None
        self._live_text = ""
        self._modes = {}          # clé -> libellé lisible
        self._screen = None
        self._pick_default_screen()

    # ---------------------------- Modes ---------------------------------- #
    def register_mode(self, key: str, label: str):
        self._modes[key] = label

    def mode_label(self, key) -> str:
        return self._modes.get(key, key or "")

    def on_air(self):
        return self._on_air

    def is_on_air(self, key) -> bool:
        return self._on_air is not None and self._on_air == key

    def live_text(self) -> str:
        return self._live_text

    # ---------------------------- Écrans --------------------------------- #
    def screens(self):
        return QGuiApplication.screens()

    def screen(self):
        return self._screen

    def _pick_default_screen(self):
        screens = self.screens()
        if not screens:
            self._screen = None
        elif len(screens) > 1:
            # Souvent le dernier écran détecté est le vidéoprojecteur.
            self._screen = screens[-1]
        else:
            self._screen = screens[0]

    def set_screen(self, screen):
        self._screen = screen
        if screen is not None and self._on_air is not None:
            self.window.set_font_size(self._font_size)
            self.window.show_on_screen(screen)
            self.window.toggle_blank(self._blackout)
        self.changed.emit()

    def refresh_screens(self):
        """À appeler quand un écran est branché/débranché."""
        screens = self.screens()
        if self._screen not in screens:
            # L'écran cible a disparu : on coupe proprement et on réélit un défaut.
            if self._on_air is not None:
                self.stop()
            self._pick_default_screen()
        self.screens_changed.emit()
        self.changed.emit()

    # ------------------------- Mesure de place --------------------------- #
    def text_fits(self, text: str) -> bool:
        """`text` tient-il dans la surface de projection à la taille actuelle ?

        Mesuré contre l'écran cible et la police projetée (même taille/graisse
        que `ProjectionWindow`). Sans écran cible, aucune contrainte (True) :
        on ne peut pas mesurer, donc on ne bride pas.
        """
        screen = self._screen
        if screen is None:
            return True
        geo = screen.geometry()
        avail_w = geo.width() - 2 * _PROJECTION_MARGIN
        avail_h = geo.height() - 2 * _PROJECTION_MARGIN
        if avail_w <= 0 or avail_h <= 0:
            return True
        font = QFont()
        font.setPointSize(self._font_size)
        font.setWeight(QFont.Bold)
        rect = QFontMetrics(font).boundingRect(
            0, 0, avail_w, 0, Qt.TextWordWrap | Qt.AlignCenter, text
        )
        return rect.height() <= avail_h

    # ------------------------- Taille du texte --------------------------- #
    def font_size(self) -> int:
        return self._font_size

    def set_font_size(self, size: int):
        self._font_size = size
        self.window.set_font_size(size)
        self.changed.emit()

    # ----------------------------- Écran noir ---------------------------- #
    def blackout(self) -> bool:
        return self._blackout

    def set_blackout(self, active: bool):
        self._blackout = active
        self.window.toggle_blank(active)
        self.changed.emit()

    # ----------------------------- Projection ---------------------------- #
    def project(self, key: str, text: str) -> bool:
        """Met `key` à l'antenne avec `text`. Retourne False si aucun écran cible."""
        if self._screen is None:
            return False
        self._on_air = key
        self._live_text = text
        self._blackout = False
        self.window.set_font_size(self._font_size)
        self.window.show_on_screen(self._screen)
        self.window.set_text(text)
        self.window.toggle_blank(False)
        self.changed.emit()
        return True

    def update_live(self, key: str, text: str):
        """Met à jour le texte projeté si `key` est le mode à l'antenne."""
        if self.is_on_air(key):
            self._live_text = text
            self.window.set_text(text)  # respecte l'écran noir en interne
            self.changed.emit()

    def stop(self):
        """Arrête toute projection (aucun mode à l'antenne)."""
        self._on_air = None
        self._live_text = ""
        self.window.hide()
        self.changed.emit()

    def close(self):
        self.window.close()
