"""
Thème visuel de l'application, basé sur le logo "Logos Tabernacle"
(cercle noir, fond doré/bronze avec bokeh, barre dorée centrale).

Toutes les couleurs de l'interface doivent passer par ce module afin de
garder une identité visuelle cohérente et facile à ajuster.
"""

APP_NAME = "Logos Tabernacle"

# ---------- Palette extraite du logo ----------
GOLD_LIGHTEST = "#FDE1AC"   # reflet clair sur la barre dorée
GOLD_LIGHT = "#FAD693"      # fond bokeh clair
GOLD = "#F3CD87"            # or principal
GOLD_MID = "#EEC781"        # or intermédiaire
GOLD_DARK = "#E4BC77"       # ambre
BRONZE = "#A3814C"          # bronze foncé (ombre de la barre dorée)
BLACK = "#1A120A"           # noir profond (cercle, texte du logo)

# ---------- Rôles sémantiques ----------
COLOR_BACKGROUND = BLACK          # fond des panneaux (thème sombre)
COLOR_SURFACE = "#241C12"         # fond des zones de contenu (légèrement plus clair)
COLOR_SURFACE_ALT = "#2E2416"     # fond alterné (listes, champs)
COLOR_SURFACE_SUNKEN = "#211A10"  # zone en creux (chapitres/versets sous la Bible)
COLOR_BORDER = BRONZE
COLOR_BORDER_SUBTLE = "#3A2E1C"   # séparateurs et bordures discrètes
COLOR_PRIMARY = GOLD              # accent principal (boutons, sélection)
COLOR_PRIMARY_HOVER = GOLD_LIGHT
COLOR_PRIMARY_PRESSED = GOLD_DARK
COLOR_ON_PRIMARY_MUTED = "#5A4420"  # texte secondaire posé sur un fond doré
COLOR_TEXT = GOLD_LIGHTEST        # texte principal sur fond sombre
COLOR_TEXT_MUTED = GOLD_MID
COLOR_TEXT_ON_PRIMARY = BLACK     # texte sur bouton doré (contraste)
COLOR_DANGER = "#B33A2E"          # pour actions destructrices (supprimer)
COLOR_DANGER_HOVER = "#CC4A3D"
COLOR_SUCCESS = "#4E8C5A"         # état positif (écran détecté)
COLOR_WARNING = "#D89A3C"         # avertissement (un autre mode est à l'antenne)
COLOR_LIVE = "#79C77B"            # indicateur « en direct » (projection active)

# Police à empattement pour la lecture du texte biblique (rappel « imprimé »).
READING_FONT_FAMILY = "Georgia, 'Times New Roman', 'Noto Serif', serif"

# Fenêtre de projection : reste noire pour la lisibilité en salle,
# avec le texte projeté en doré clair pour rappeler l'identité visuelle.
PROJECTION_BACKGROUND = "#000000"
PROJECTION_TEXT = GOLD_LIGHTEST


def build_stylesheet() -> str:
    """Feuille de style Qt (QSS) appliquée à toute l'application de contrôle.

    On ne fixe volontairement aucune `font-family` : Qt utilise alors la police
    par défaut de l'application, qui est déjà la police système native (Segoe UI
    sur Windows, San Francisco sur macOS, etc.). Coder en dur une police absente
    selon l'OS (« Segoe UI » hors Windows) déclencherait un avertissement Qt et
    un coût de résolution d'alias.
    """
    return f"""
    QWidget {{
        background-color: {COLOR_BACKGROUND};
        color: {COLOR_TEXT};
        font-size: 13px;
    }}

    QMainWindow {{
        background-color: {COLOR_BACKGROUND};
    }}

    QLabel {{
        color: {COLOR_TEXT_MUTED};
        font-weight: 600;
        background: transparent;
    }}

    /* ---------- Sections ---------- */
    QGroupBox {{
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        margin-top: 14px;
        padding-top: 6px;
        font-weight: 700;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {COLOR_PRIMARY};
    }}

    /* ---------- Onglets (Chants / Bible) ---------- */
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        top: -1px;
    }}

    QTabBar::tab {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT_MUTED};
        border: 1px solid {COLOR_BORDER};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 7px 20px;
        margin-right: 2px;
        font-weight: 700;
    }}

    QTabBar::tab:selected {{
        background: {COLOR_PRIMARY};
        color: {COLOR_TEXT_ON_PRIMARY};
    }}

    QTabBar::tab:hover:!selected {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
    }}

    /* ---------- Champs de saisie ---------- */
    QLineEdit, QTextEdit, QComboBox, QSpinBox {{
        background-color: {COLOR_SURFACE_ALT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px;
        color: {COLOR_TEXT};
        selection-background-color: {COLOR_PRIMARY};
        selection-color: {COLOR_TEXT_ON_PRIMARY};
    }}

    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {COLOR_PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {COLOR_PRIMARY};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        selection-background-color: {COLOR_PRIMARY};
        selection-color: {COLOR_TEXT_ON_PRIMARY};
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        background: {COLOR_SURFACE};
        border-left: 1px solid {COLOR_BORDER};
        width: 18px;
    }}

    QSpinBox::up-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid {COLOR_PRIMARY};
    }}

    QSpinBox::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {COLOR_PRIMARY};
    }}

    /* ---------- Listes ---------- */
    QListWidget {{
        background-color: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 6px;
        border-radius: 3px;
    }}

    QListWidget::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: {COLOR_TEXT_ON_PRIMARY};
    }}

    QListWidget::item:hover:!selected {{
        background-color: {COLOR_SURFACE_ALT};
    }}

    /* ---------- Boutons ---------- */
    QPushButton {{
        background-color: {COLOR_PRIMARY};
        color: {COLOR_TEXT_ON_PRIMARY};
        border: none;
        border-radius: 4px;
        padding: 8px 14px;
        font-weight: 700;
    }}

    QPushButton:hover {{
        background-color: {COLOR_PRIMARY_HOVER};
    }}

    QPushButton:pressed {{
        background-color: {COLOR_PRIMARY_PRESSED};
    }}

    QPushButton:checked {{
        background-color: {COLOR_DANGER};
        color: white;
    }}

    QPushButton:checked:hover {{
        background-color: {COLOR_DANGER_HOVER};
    }}

    /* Actions secondaires (réordonner, retirer...) : discrètes */
    QPushButton[buttonStyle="secondary"] {{
        background-color: transparent;
        color: {COLOR_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        font-weight: 600;
    }}

    QPushButton[buttonStyle="secondary"]:hover {{
        background-color: {COLOR_SURFACE_ALT};
        border-color: {COLOR_PRIMARY};
    }}

    QPushButton[buttonStyle="secondary"]:pressed {{
        background-color: {COLOR_SURFACE};
    }}

    /* Actions destructrices : rouges, mais discrètes tant que non survolées */
    QPushButton[buttonStyle="danger"] {{
        background-color: transparent;
        color: {COLOR_DANGER_HOVER};
        border: 1px solid {COLOR_DANGER};
        font-weight: 600;
    }}

    QPushButton[buttonStyle="danger"]:hover {{
        background-color: {COLOR_DANGER};
        color: white;
    }}

    /* ---------- Aperçu en direct et état de projection ---------- */
    QLabel#PreviewLabel {{
        background-color: {PROJECTION_BACKGROUND};
        color: {PROJECTION_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 8px;
        font-weight: 600;
    }}

    QLabel#StatusLabel {{
        font-weight: 700;
    }}

    /* ---------- Divers ---------- */
    QSplitter::handle {{
        background-color: {COLOR_BORDER};
    }}

    QScrollBar:vertical {{
        background: {COLOR_SURFACE};
        width: 10px;
    }}

    QScrollBar::handle:vertical {{
        background: {COLOR_BORDER};
        border-radius: 5px;
        min-height: 20px;
    }}

    /* ---------- Barre de menus (Fichier / Chants / Culte…) ---------- */
    QMenuBar {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT_MUTED};
        border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        padding: 2px 6px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 6px 12px;
        border-radius: 4px;
    }}

    QMenuBar::item:selected {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
    }}

    QMenuBar::item:pressed {{
        background: {COLOR_PRIMARY};
        color: {COLOR_TEXT_ON_PRIMARY};
    }}

    QMenu {{
        background-color: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        padding: 4px;
    }}

    QMenu::item {{
        padding: 6px 24px 6px 20px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background: {COLOR_PRIMARY};
        color: {COLOR_TEXT_ON_PRIMARY};
    }}

    QMenu::item:disabled {{
        color: {COLOR_TEXT_MUTED};
    }}

    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER_SUBTLE};
        margin: 4px 8px;
    }}

    QMessageBox {{
        background-color: {COLOR_SURFACE};
    }}

    QToolTip {{
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        padding: 4px;
    }}
    """
