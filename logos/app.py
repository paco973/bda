"""
Assemblage de l'application : initialise la base, applique le thème
et lance la fenêtre de contrôle.
"""
import sys

from PySide6.QtWidgets import QApplication

from logos.data import bible, database, predications
from logos.ui import theme
from logos.ui.control_window import ControlWindow


def main():
    database.init_db()
    bible.ensure_imported()         # premier lancement : importe la Bible embarquée
    predications.ensure_imported()  # importe les prédications si l'asset est présent
    app = QApplication(sys.argv)
    app.setApplicationName(theme.APP_NAME)
    app.setStyleSheet(theme.build_stylesheet())
    window = ControlWindow()
    window.show()
    sys.exit(app.exec())
