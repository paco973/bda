"""
Petits widgets et aides génériques partagés par les panneaux de l'UI
(disposition en flux, cases numérotées, logo rond, vidage de layout).

Aucune logique métier ici : uniquement des composants réutilisables.
"""
from contextlib import contextmanager

from PySide6.QtCore import Qt, QTimer, Signal, QRect, QSize, QPoint
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

    @contextmanager
    def bulk_fill(self):
        """Remplissage en masse d'une grille : `with host.bulk_fill() as flow:`.

        Tant que le conteneur est visible, chaque ajout repositionne toute la
        grille — le remplissage devient quadratique (623 ms pour les 642 cases
        d'une longue prédication, 123 ms en masquant le temps de l'ajout).
        Rien n'est peint entre-temps : aucun événement n'est traité ici."""
        hidden = self.isHidden()   # ne pas ré-afficher ce qu'on avait masqué
        self.setVisible(False)
        try:
            yield self.flow
        finally:
            if not hidden:
                self.setVisible(True)


# --------------------------------------------------------------------------- #
#  Petits composants
# --------------------------------------------------------------------------- #
class NumButton(QPushButton):
    """Carré numéroté (chapitre, verset, paragraphe…)."""

    picked = Signal(int)

    def __init__(self, number: int):
        super().__init__(str(number))
        self.number = number
        self._active = False
        self.setFixedSize(42, 42)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: self.picked.emit(self.number))
        # Les deux états tiennent dans une seule feuille, posée une fois ici.
        self.setProperty("active", False)
        self.setStyleSheet(theme.num_button_style())

    def set_active(self, active: bool):
        """Bascule l'état sélectionné (voir `theme.num_button_style`).

        Une grille compte des centaines de cases et les panneaux appellent
        `set_active` sur toute la grille à chaque clic : on ne fait que basculer
        une propriété, au lieu de reposer une feuille de style — ce qui obligeait
        Qt à réanalyser la cascade de chaque case."""
        if active == self._active:
            return
        self._active = active
        self.setProperty("active", active)
        # Qt ne réévalue pas la QSS sur un simple changement de propriété.
        self.style().unpolish(self)
        self.style().polish(self)


class NumberedTextRow(QLabel):
    """Ligne de texte numérotée de la colonne de lecture (verset, paragraphe…) :
    numéro en exposant, clic pour sélectionner, surlignage quand active.

    Le texte est sélectionnable à la souris : au relâchement, `partial_selected`
    transmet la position (dans le texte brut) du début de la sélection, ou -1
    s'il n'y a pas de sélection — le panneau peut s'en servir pour démarrer la
    projection au milieu du texte.

    **Ses mesures sont mémorisées** (`heightForWidth`, `sizeHint`) : une colonne
    de lecture en aligne des centaines dans une même `QVBoxLayout`, et Qt
    remesure *toutes* les lignes dès que l'une d'elles change — surligner le
    paragraphe sélectionné remettait en page 642 textes à retour à la ligne
    (~370 ms par clic sur une longue prédication). Ces mesures ne dépendent que
    du texte et de l'état actif : les recalculer à chaque fois est inutile."""

    clicked = Signal(int)
    partial_selected = Signal(int, int)   # (numéro, position de début, ou -1)

    def __init__(self, number: int, text: str):
        super().__init__()
        self.number = number
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setCursor(Qt.PointingHandCursor)
        self._text = text
        self._active = None
        self._forget_measures()
        self.set_active(False)

    # ------------------------- Mesures mémorisées ------------------------- #
    def _forget_measures(self):
        """À appeler dès que le contenu ou l'état change (la mise en page du
        texte, donc sa hauteur, en dépendent)."""
        self._heights = {}       # largeur -> hauteur du texte replié
        self._size_hint = None
        self._min_size_hint = None

    def heightForWidth(self, width: int) -> int:
        height = self._heights.get(width)
        if height is None:
            height = super().heightForWidth(width)
            self._heights[width] = height
        return height

    def sizeHint(self):
        if self._size_hint is None:
            self._size_hint = super().sizeHint()
        return self._size_hint

    def minimumSizeHint(self):
        if self._min_size_hint is None:
            self._min_size_hint = super().minimumSizeHint()
        return self._min_size_hint

    def set_active(self, active: bool):
        if active == self._active:
            return  # setText effacerait une sélection à la souris en cours
        self._active = active
        self._forget_measures()
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
        super().mousePressEvent(event)  # laisse la sélection de texte démarrer
        self.clicked.emit(self.number)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        offset = -1
        start = self.selectionStart()
        if start >= 0 and self.selectedText().strip():
            # Le texte affiché est précédé du numéro en exposant et d'une espace.
            offset = max(0, start - len(str(self.number)) - 1)
        self.partial_selected.emit(self.number, offset)


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


class ProgressiveRows:
    """Pose les lignes d'une colonne de lecture par lots, sans figer l'interface.

    Mettre en page des centaines de lignes de texte replié coûte près d'une
    seconde (Qt mesure chaque ligne) : sur une longue prédication, la fenêtre
    se figeait le temps d'afficher un texte dont l'opérateur ne voit qu'un
    écran. Les premières lignes sont donc posées tout de suite, le reste arrive
    par lots dès que la boucle d'événements est libre.

    `ensure_placed` force la suite quand une sélection vise une ligne pas encore
    posée (navigation au clavier, saut depuis le poste de contrôle) : une ligne
    absente du layout n'a pas de géométrie, on ne pourrait pas y défiler.
    """

    def __init__(self, layout, first: int = 40, batch: int = 40):
        self._layout = layout
        self._first = first
        self._batch = batch
        self._pending = []
        self._generation = 0

    def reset(self, widgets):
        """Repart d'une colonne vide et pose le premier lot."""
        self._generation += 1
        for widget in self._pending:  # reliquat jamais posé : à détruire aussi
            widget.setParent(None)
            widget.deleteLater()
        self._pending = list(widgets)
        clear_layout(self._layout)
        self._layout.addStretch()
        self._place(self._first)
        self._schedule(self._generation)

    def ensure_placed(self, widget):
        """Pose immédiatement `widget` (et tout ce qui le précède) s'il attend."""
        if widget in self._pending:
            self._place(self._pending.index(widget) + 1)

    def flush(self):
        """Pose tout le reliquat d'un coup (utile aux tests)."""
        self._place(len(self._pending))

    def _place(self, count):
        # L'étirement final doit rester en dernier : on insère juste avant.
        position = max(0, self._layout.count() - 1)
        for widget in self._pending[:count]:
            self._layout.insertWidget(position, widget)
            position += 1
        del self._pending[:count]

    def _schedule(self, generation):
        if self._pending:
            # Le layout sert de contexte : Qt abandonne le lot en attente s'il a
            # été détruit entre-temps (fenêtre fermée, panneau rechargé).
            QTimer.singleShot(0, self._layout, lambda: self._next(generation))

    def _next(self, generation):
        if generation != self._generation:
            return  # une autre colonne a été chargée entre-temps
        self._place(self._batch)
        self._schedule(generation)


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
