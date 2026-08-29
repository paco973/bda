"""
Fenêtre de projection : affichée en plein écran, sans bordure, sur
l'écran choisi (typiquement le vidéoprojecteur branché à l'ordinateur).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout

from logos.ui import theme


class ProjectionWindow(QWidget):
    # Échap pressé alors que cette fenêtre a le focus : l'opérateur veut sortir
    # de la présentation. Le contrôleur décide de la suite (il possède l'état) ;
    # cette fenêtre n'affiche que du contenu.
    close_requested = Signal()

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

    def keyPressEvent(self, event):
        """Échap quitte la présentation, comme dans un logiciel de diaporama.

        Affichée en plein écran, cette fenêtre peut recevoir le focus clavier :
        sans cela, aucune touche n'agirait tant que l'opérateur ne serait pas
        revenu sur la fenêtre de contrôle."""
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _apply_label_style(self):
        # Style inline : prioritaire sur la feuille de style globale de
        # l'application, qui imposerait sinon sa petite taille de texte.
        self.label.setStyleSheet(
            f"color: {theme.PROJECTION_TEXT};"
            f" font-size: {self._font_size}pt;"
            " font-weight: 700;"
        )

    def show_on_screen(self, screen):
        """Affiche la fenêtre en plein écran sur l'écran donné."""
        geometry = screen.geometry()
        self.setGeometry(geometry)
        self.showFullScreen()
        self.raise_()

    def hide_projection(self):
        """Masque la projection proprement.

        On quitte d'abord l'état plein écran : sous macOS, masquer une fenêtre
        laissée en plein écran laisse l'écran noir au lieu de le libérer.
        """
        self.setWindowState(self.windowState() & ~Qt.WindowFullScreen)
        self.hide()

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