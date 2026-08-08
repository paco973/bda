"""
Petits widgets et aides génériques partagés par les panneaux de l'UI
(disposition en flux, cases numérotées, logo rond, vidage de layout).

Aucune logique métier ici : uniquement des composants réutilisables.
"""
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QLabel, QLayout, QPushButton

from logos.resources import asset_path
from logos.ui import theme

_LOGO_PATH = asset_path("logo.png")


# --------------------------------------------------------------------------- #
#  Disposition en flux (les cartes se replacent sur plusieurs lignes)
# --------------------------------------------------------------------------- #
class FlowLayout(QLayout):
    """Dispose les widgets de gauche à droite en passant à la ligne au besoin."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect, test_only):
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class FlowHost(QWidget):
    """Conteneur d'une FlowLayout qui déclare sa hauteur pour permettre le
    défilement vertical à l'intérieur d'un QScrollArea (widgetResizable)."""

    def __init__(self, spacing=6):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self.flow = FlowLayout(self, spacing=spacing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self.flow.heightForWidth(self.width()))


# --------------------------------------------------------------------------- #
#  Petits composants
# --------------------------------------------------------------------------- #
class NumButton(QPushButton):
    """Carré numéroté (chapitre, verset, paragraphe…)."""

    picked = Signal(int)

    def __init__(self, number: int):
        super().__init__(str(number))
        self.number = number
        self.setFixedSize(42, 42)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: self.picked.emit(self.number))
        self.set_active(False)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.COLOR_PRIMARY};"
                f" color:{theme.COLOR_TEXT_ON_PRIMARY};"
                f" border:1px solid {theme.COLOR_PRIMARY}; border-radius:5px;"
                f" font-size:13px; font-weight:700; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.COLOR_SURFACE_ALT};"
                f" color:{theme.COLOR_TEXT_MUTED};"
                f" border:1px solid {theme.COLOR_BORDER_SUBTLE}; border-radius:5px;"
                f" font-size:13px; font-weight:600; }}"
                f" QPushButton:hover {{ border-color:{theme.COLOR_PRIMARY};"
                f" color:{theme.COLOR_TEXT}; }}"
            )


class NumberedTextRow(QLabel):
    """Ligne de texte numérotée de la colonne de lecture (verset, paragraphe…) :
    numéro en exposant, clic pour sélectionner, surlignage quand active."""

    clicked = Signal(int)

    def __init__(self, number: int, text: str):
        super().__init__()
        self.number = number
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setCursor(Qt.PointingHandCursor)
        self._text = text
        self.set_active(False)

    def set_active(self, active: bool):
        num_color = theme.COLOR_ON_PRIMARY_MUTED if active else theme.BRONZE
        text_color = theme.COLOR_TEXT_ON_PRIMARY if active else theme.COLOR_TEXT
        bg = theme.COLOR_PRIMARY if active else "transparent"
        self.setText(
            f'<sup style="color:{num_color}; font-family:sans-serif;'
            f' font-weight:700;">{self.number}</sup> {self._text}'
        )
        self.setStyleSheet(
            f"color:{text_color}; background:{bg}; border-radius:5px;"
            f" padding:{'6px 9px' if active else '2px 3px'};"
            f" font-family:{theme.READING_FONT_FAMILY}; font-size:16px; font-weight:500;"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.number)


def circular_logo(size: int):
    """Pixmap circulaire du logo de l'église, ou None si l'asset est absent."""
    if not _LOGO_PATH.exists():
        return None
    src = QPixmap(str(_LOGO_PATH))
    if src.isNull():
        return None
    src = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return result


def clear_layout(layout):
    """Retire et détruit tous les widgets d'un layout (versets, boutons…).

    Le reparentage immédiat (setParent(None)) fait disparaître le widget aussitôt,
    sans attendre le traitement différé de deleteLater — évite tout chevauchement
    visuel transitoire lors d'un changement de chapitre.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
