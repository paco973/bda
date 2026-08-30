"""
Thème visuel de l'application BDA, basé sur le logo de l'église Logos
Tabernacle (sceau doré sur bleu marine profond : anneau et lettrage dorés,
croix et barre dorées, rameaux de laurier).

Toutes les couleurs de l'interface doivent passer par ce module afin de
garder une identité visuelle cohérente et facile à ajuster.

Les tons sombres sont ceux du sceau ; l'or reste l'accent. L'échelle marine
reprend les **clartés** de l'ancienne échelle brune : tous les contrastes de
texte déjà validés restent valides (l'or clair est à 14,9:1 sur le fond,
le bronze à 5,2:1, au-dessus du seuil AA de 4,5).
"""

APP_NAME = "BDA"

# ---------- Palette extraite du logo ----------
GOLD_LIGHTEST = "#FDE1AC"   # reflet clair sur la barre dorée
GOLD_LIGHT = "#FAD693"      # fond bokeh clair
GOLD = "#F3CD87"            # or principal
GOLD_MID = "#EEC781"        # or intermédiaire
GOLD_DARK = "#E4BC77"       # ambre
BRONZE = "#A3814C"          # bronze foncé (ombre de la barre dorée)
NAVY_DEEPEST = "#071023"    # bleu du sceau, au plus sombre (pourtour du logo)
NAVY_DEEP = "#0C1830"       # bleu du champ intérieur du sceau
NAVY = "#11203C"            # bleu éclairci (zones alternées)
NAVY_SUNKEN = "#091428"     # bleu en creux (sous la barre dorée)
NAVY_BORDER = "#16253F"     # bleu des séparations discrètes
BLACK = "#0A0F1A"           # noir bleuté, pour le texte posé sur un aplat doré

# ---------- Rôles sémantiques ----------
COLOR_BACKGROUND = NAVY_DEEPEST   # fond des panneaux (thème sombre)
COLOR_SURFACE = NAVY_DEEP         # fond des zones de contenu (légèrement plus clair)
COLOR_SURFACE_ALT = NAVY          # fond alterné (listes, champs)
COLOR_SURFACE_SUNKEN = NAVY_SUNKEN  # zone en creux (chapitres/versets sous la Bible)
COLOR_BORDER = BRONZE
COLOR_BORDER_SUBTLE = NAVY_BORDER  # séparateurs et bordures discrètes
COLOR_PRIMARY = GOLD              # accent principal (boutons, sélection)
COLOR_PRIMARY_HOVER = GOLD_LIGHT
COLOR_PRIMARY_PRESSED = GOLD_DARK
COLOR_ON_PRIMARY_MUTED = "#5A4420"  # texte secondaire posé sur un fond doré
COLOR_TEXT = GOLD_LIGHTEST        # texte principal sur fond sombre
COLOR_TEXT_MUTED = GOLD_MID
COLOR_TEXT_DISABLED = "#6E5A38"   # texte inactif (lettres sans prédication…)
COLOR_TEXT_ON_PRIMARY = BLACK     # texte sur bouton doré (contraste)
COLOR_DANGER = "#B33A2E"          # pour actions destructrices (supprimer)
COLOR_DANGER_HOVER = "#CC4A3D"
COLOR_SUCCESS = "#4E8C5A"         # état positif (écran détecté)
COLOR_WARNING = "#D89A3C"         # avertissement (un autre mode est à l'antenne)
COLOR_LIVE = "#79C77B"            # indicateur « en direct » (projection active)

# ---------- Grille des livres bibliques ----------
# Une couleur par groupe canonique (clés de logos/data/bible.py :: book_group).
# Mêmes teintes qu'à l'origine, mais **éclaircies** et calées sur une luminance
# commune : à teinte égale, une même clarté HSL se perçoit très différemment
# (l'orange criait quand le brun s'effaçait). Toutes donnent maintenant 6,1:1
# avec le texte des cartes, bien au-dessus du seuil AA de 4,5 — la version
# sombre précédente passait sous ce seuil sur trois groupes.
BOOK_GROUP_COLORS = {
    "pentateuque": "#BB8655",     # brun
    "historiques": "#C18429",     # orange
    "poetiques": "#D4776C",       # rouge brique
    "prophetes": "#AC82B8",       # violet
    "evangiles": "#7691C8",       # bleu
    "actes": "#399EAB",           # cyan
    "epitres": "#3DA368",         # vert
    "apocalypse": "#7F9B33",      # vert clair
}
# Cartes éclaircies : le texte passe en sombre, comme sur la carte sélectionnée
# (aplat doré) — un fond clair et un texte clair ne pouvaient pas cohabiter.
COLOR_TEXT_ON_GROUP = BLACK                          # abréviation sur carte colorée
COLOR_TEXT_ON_GROUP_MUTED = "rgba(10, 15, 26, 0.68)"  # nom du livre

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

    /* ---------- Onglets (aucun pour l'instant ; prêts pour un mode futur) ---------- */
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

    /* ---------- Barre de menus (Fichier / Affichage / Aide) ---------- */
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


# --------------------------------------------------------------------------- #
#  Styles inline des boutons
#
#  Appliqués via setStyleSheet directement sur le bouton : le cascade QSS d'un
#  parent stylé neutralise sinon l'accent doré des QPushButton primaires.
#  Un seul jeu de styles pour toute l'application (panneaux et postes de
#  contrôle) — toute variante passe par ici, jamais par un style local.
# --------------------------------------------------------------------------- #
def btn_primary_style() -> str:
    """Bouton d'action principale (accent doré)."""
    return (
        f"QPushButton {{ background:{COLOR_PRIMARY}; color:{COLOR_TEXT_ON_PRIMARY};"
        f" border:none; border-radius:6px; padding:11px; font-size:13px; font-weight:700; }}"
        f"QPushButton:hover {{ background:{COLOR_PRIMARY_HOVER}; }}"
        f"QPushButton:disabled {{ background:{COLOR_SURFACE_ALT}; color:{BRONZE}; }}"
    )


def num_button_style() -> str:
    """Case numérotée (chapitre, verset, paragraphe), états inactif et actif.

    Les deux états tiennent dans **une seule** feuille, posée une fois à la
    construction : la sélection ne fait ensuite que basculer la propriété
    `active` (voir `widgets.NumButton`). Reposer une feuille à chaque clic
    obligeait Qt à réanalyser la cascade des centaines de cases d'une grille.

    Ce style ne peut pas vivre dans `build_stylesheet` : les conteneurs des
    grilles posent des déclarations sans sélecteur, qui cascadent sur leurs
    descendants et priment sur la feuille applicative.

    `padding:0` est indispensable : le padding QPushButton de la feuille globale
    rognerait les nombres à 2-3 chiffres dans la case de taille fixe.
    """
    return (
        f"QPushButton {{ background:{COLOR_SURFACE_ALT}; color:{COLOR_TEXT_MUTED};"
        f" padding:0; border:1px solid {COLOR_BORDER_SUBTLE}; border-radius:5px;"
        f" font-size:13px; font-weight:600; }}"
        f"QPushButton:hover {{ border-color:{COLOR_PRIMARY}; color:{COLOR_TEXT}; }}"
        f'QPushButton[active="true"] {{ background:{COLOR_PRIMARY};'
        f" color:{COLOR_TEXT_ON_PRIMARY}; border-color:{COLOR_PRIMARY};"
        f" font-weight:700; }}"
    )


def btn_secondary_style() -> str:
    """Bouton d'action secondaire (contour, fond transparent)."""
    return (
        f"QPushButton {{ background:transparent; color:{COLOR_TEXT};"
        f" border:1px solid {COLOR_BORDER}; border-radius:6px; padding:11px 14px;"
        f" font-size:13px; font-weight:600; }}"
        f"QPushButton:hover {{ background:{COLOR_SURFACE_ALT}; border-color:{COLOR_PRIMARY}; }}"
        f"QPushButton:disabled {{ color:{BRONZE}; border-color:{COLOR_BORDER_SUBTLE}; }}"
    )


def btn_danger_style() -> str:
    """Bouton d'action destructrice ou d'état d'alerte (écran noir actif…)."""
    return (
        f"QPushButton {{ background:{COLOR_DANGER}; color:white;"
        f" border:1px solid {COLOR_DANGER}; border-radius:6px; padding:11px 14px;"
        f" font-size:13px; font-weight:700; }}"
        f"QPushButton:hover {{ background:{COLOR_DANGER_HOVER}; border-color:{COLOR_DANGER_HOVER}; }}"
    )
