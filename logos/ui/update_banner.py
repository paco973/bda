"""
Bandeau « nouvelle version disponible » et lancement de la vérification en
tâche de fond.

Le bandeau est discret et refermable : il n'interrompt jamais l'opérateur en
plein culte. Aucun téléchargement automatique — le bouton ouvre simplement le
lien dans le navigateur.

Les textes venus du manifeste (numéro de version, notes) sont **non fiables** :
ils sont affichés en `Qt.PlainText` pour ne jamais être interprétés comme du
HTML par Qt.
"""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from logos import updates
from logos.ui import theme
from logos.version import __version__


# --------------------------------------------------------------------------- #
#  Vérification en tâche de fond
# --------------------------------------------------------------------------- #
class _CheckSignals(QObject):
    """Porte le signal de fin : un QRunnable n'est pas un QObject."""
    finished = Signal(object)  # updates.CheckResult


class _CheckTask(QRunnable):
    """Interroge le manifeste hors du fil de l'interface (le réseau peut
    bloquer plusieurs secondes ; la fenêtre ne doit pas se figer)."""

    def __init__(self, signals, manifest_url):
        super().__init__()
        self._signals = signals
        self._manifest_url = manifest_url

    def run(self):
        result = updates.check_for_update(self._manifest_url)
        try:
            self._signals.finished.emit(result)
        except RuntimeError:
            pass  # fenêtre fermée entre-temps : plus personne à prévenir


def check_async(owner, callback, manifest_url=None):
    """Lance une vérification et appelle `callback(CheckResult)` dans le fil de
    l'interface. `owner` (un QWidget) sert de parent : le porteur de signal vit
    et meurt avec lui."""
    signals = _CheckSignals(owner)
    signals.finished.connect(callback)
    QThreadPool.globalInstance().start(_CheckTask(signals, manifest_url))


# --------------------------------------------------------------------------- #
#  Bandeau
# --------------------------------------------------------------------------- #
class UpdateBanner(QFrame):
    """Bandeau horizontal masqué par défaut, affiché par `show_release()`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._release = None
        self.setStyleSheet(
            f"UpdateBanner {{ background:{theme.COLOR_SURFACE_ALT};"
            f" border-bottom:1px solid {theme.COLOR_PRIMARY}; }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(10)

        self._label = QLabel()
        self._label.setTextFormat(Qt.PlainText)  # contenu distant : jamais du HTML
        self._label.setStyleSheet(f"color:{theme.COLOR_TEXT};")
        row.addWidget(self._label, 1)

        self._download_btn = QPushButton("Télécharger")
        self._download_btn.setStyleSheet(theme.btn_primary_style())
        self._download_btn.clicked.connect(self._open_download)
        row.addWidget(self._download_btn)

        # Libellé plutôt qu'une croix : plus clair pour l'opérateur, et pas de
        # glyphe exotique qui risque de ne pas exister dans la police système.
        later_btn = QPushButton("Plus tard")
        later_btn.setToolTip("Masquer le bandeau jusqu'au prochain lancement")
        later_btn.setStyleSheet(theme.btn_secondary_style())
        later_btn.clicked.connect(self.hide)
        row.addWidget(later_btn)

        self.hide()

    def show_release(self, release):
        """Affiche le bandeau pour `release`."""
        self._release = release
        self._label.setText(
            f"Version {release.version} disponible "
            f"(vous utilisez la {__version__})."
        )
        self.show()

    def _open_download(self):
        # Le schéma HTTPS a été validé par `updates.check_for_update` : on ne
        # peut donc pas être amené à ouvrir autre chose qu'une page web.
        if self._release is not None:
            QDesktopServices.openUrl(QUrl(self._release.url))
