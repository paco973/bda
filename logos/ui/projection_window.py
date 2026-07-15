"""
Fenêtre de projection : affichée en plein écran, sans bordure, sur
l'écran choisi (typiquement le vidéoprojecteur branché à l'ordinateur).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout

from logos.ui import theme


class ProjectionWindow(QWidget):
    def __init__(self):
        super().__init__()
        # Pas de bordure, toujours au premier plan sur son écran
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setStyleSheet(f"background-color: {theme.PROJECTION_BACKGROUND};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)

        layout.addWidget(self.label)

        self._blank = False
        self._current_text = ""
        self._font_size = 48
        self._apply_label_style()

    def _apply_label_style(self):
        # Style inline : prioritaire sur la feuille de style globale de
        # l'application, qui imposerait sinon sa petite taille de texte.
        self.label.setStyleSheet(
            f"color: {theme.PROJECTION_TEXT};"
            f" font-size: {self._font_size}pt;"
            " font-weight: 700;"
        )

    def show_on_screen(self, screen):
        """Positionne et affiche la fenêtre plein cadre sur l'écran donné.

        On utilise une fenêtre sans bordure à la géométrie de l'écran plutôt que
        `showFullScreen()` : ce dernier crée, sous macOS, un « espace » plein
        écran que `hide()` ne quitte pas proprement (l'écran resterait noir à
        l'arrêt de la projection). Ici, `hide()` retire nettement la fenêtre.
        """
        geometry = screen.geometry()
        self.setGeometry(geometry)
        self.show()
        self.raise_()

    def set_text(self, text: str):
        self._current_text = text
        if not self._blank:
            self.label.setText(text)

    def current_text(self) -> str:
        """Texte en cours, même masqué par l'écran noir (pour l'aperçu)."""
        return self._current_text

    def set_font_size(self, size: int):
        self._font_size = size
        self._apply_label_style()

    def toggle_blank(self, blank: bool):
        """Écran noir (blackout) sans perdre le contenu en cours."""
        self._blank = blank
        self.label.setText("" if blank else self._current_text)