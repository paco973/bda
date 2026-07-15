# CLAUDE.md

Ce fichier donne à Claude Code le contexte nécessaire pour travailler efficacement sur ce dépôt.

## Vue d'ensemble du projet

**Logos Tabernacle** est une application de bureau de présentation pour l'église (type Holyrics/ProPresenter simplifié). Elle permet à un opérateur de piloter, depuis un poste de contrôle, l'affichage de **passages bibliques** et de **paragraphes de prédications** sur un second écran (vidéoprojecteur) pendant les cultes.

> **Note** : la partie « Chants / Culte » (bibliothèque de chants, édition des paroles, ordre du culte) a été **retirée**. L'application propose deux modes : **Bible** et **Prédications** (paragraphes numérotés issus de branham.fr, importés hors ligne). Le `cahier_des_charges.md` décrit encore les chants : le considérer comme historique sur ce point.

Le cahier des charges complet (fonctionnalités V1/V2/V3, exigences, planning) est dans `cahier_des_charges.md` à la racine — s'y référer avant d'ajouter une fonctionnalité pour vérifier son statut (Must/Should/Could) et sa phase prévue.

## Stack technique

- **Langage** : Python 3.12
- **Interface graphique** : PySide6 (Qt for Python)
- **Base de données** : SQLite (fichier local, `~/.holyrics_clone/songs.db`)
- **Packaging cible** : PyInstaller (Windows `.exe` / macOS `.app`) — pas encore mis en place

## Structure du projet

```
.
├── main.py                     # Point d'entrée mince : délègue à logos.app.main()
├── logos/                      # Package de l'application
│   ├── app.py                  # Assemblage : init DB, import Bible, thème, ControlWindow
│   ├── assets/
│   │   └── bible_ls1910.json.gz # Bible Louis Segond 1910 (domaine public), embarquée
│   ├── data/                   # Couche données — AUCUN import Qt ici
│   │   ├── database.py         # Connexion SQLite + tables Bible et prédications
│   │   ├── bible.py            # Import + requêtes sur la Bible embarquée
│   │   ├── predications.py     # Import + requêtes sur les prédications (alphabet/préfixe/paragraphes)
│   │   └── slides.py           # Mise en forme des passages bibliques -> diapositives
│   └── ui/                     # Couche interface — AUCUN SQL ici
│       ├── control_window.py   # Fenêtre principale : accueil + modes Bible et Prédications
│       ├── bible_panel.py      # Mode « Navigateur biblique » (grilles livres/chapitres/versets), émet des signaux
│       ├── predication_panel.py # Mode « Prédications » (alphabet -> préfixe -> prédication -> paragraphes)
│       ├── projection_controller.py # Contrôleur partagé : unique fenêtre de projection + exclusivité (un seul mode à l'antenne)
│       ├── projection_controls.py   # Poste de contrôle réutilisable embarqué par chaque mode
│       ├── projection_window.py # Fenêtre plein écran sans bordure sur l'écran secondaire
│       └── theme.py            # Palette de couleurs + feuille de style Qt (QSS), basé sur le logo
├── scripts/                    # Outils hors-appli
│   └── scrape_predications.py  # Import branham.fr -> logos/assets/predications.json.gz (stdlib, lancé par l'utilisateur)
├── tests/                      # Tests pytest
│   ├── test_bible.py           # Import/requêtes Bible + mise en forme des passages
│   ├── test_bible_panel.py     # Panneau Bible en offscreen
│   ├── test_predications.py    # Data prédications + parseurs du script + panneau
│   └── test_control_window.py  # Fumée UI en QT_QPA_PLATFORM=offscreen
├── README.md                   # Guide d'installation/utilisation opérateur
├── requirements.txt            # Dépendances d'exécution (PySide6)
└── requirements-dev.txt        # Dépendances de dev (pytest)
```

### Rôle de chaque module

- **`logos/data/database.py`** : connexion SQLite et création des tables de la **Bible** (`init_db`, `CREATE TABLE IF NOT EXISTS`). Les autres modules `data/` font leurs requêtes via `get_connection()` — aucun SQL hors de `logos/data/`. Ce sous-package ne doit jamais importer Qt.
- **`logos/data/bible.py`** : Bible Louis Segond 1910 embarquée dans `logos/assets/` (gzip) et importée dans SQLite au premier lancement (`ensure_imported()`, appelé par `app.main`). L'application reste 100 % hors ligne.
- **`logos/data/predications.py`** : prédications (paragraphes numérotés) importées depuis `logos/assets/predications.json.gz` (généré par `scripts/scrape_predications.py`). `letter`/`prefix` sont dérivés du titre FR **désaccentué** à l'import (« Élie » -> lettre E, préfixe « El ») pour un regroupement A-Z. Expose `letters_with_counts`, `prefixes_with_counts(letter)`, `list_by_prefix`, `search`, `get_paragraphs`. L'asset n'est **pas** livré avec le dépôt (contenu sous copyright branham.fr/VGR) : sans lui, le mode Prédications affiche « non disponible ».
- **`logos/data/slides.py`** : `passage_label()` et `passage_to_text()` mettent en forme un passage biblique en texte projetable (une diapositive par verset : texte + référence). Logique pure — toute nouvelle logique de contenu va dans `logos/data/`, pas dans l'UI.
- **`logos/data/bible.py`** expose aussi les données de référence d'affichage : `book_abbreviation(id)` (abréviations canoniques des 66 livres pour la grille des livres), `testament(id)` (Ancien/Nouveau) et `get_chapter(book_id, chapter)` (tous les versets d'un chapitre pour la colonne de lecture).
- **`logos/ui/bible_panel.py`** : navigateur biblique reproduisant la maquette « Bible Navigator » (barre supérieure logo/recherche/LSG-KJV, colonne de lecture avec versets cliquables, grille des livres, grilles chapitres/versets, barre de statut). L'état de projection n'est **pas** affiché ici (l'indicateur « à l'antenne » vit dans le `ProjectionControls` du mode). C'est le **staging** du mode Bible : il ne projette pas lui-même. Il expose `current_deck()` et émet `selection_changed` (sélection modifiée), `project_requested` (« Projeter le verset ») et `close_requested` (bouton « ‹ Retour » → accueil). Un sélecteur « Versets par diapositive » (`QSpinBox`, 1–20) fixe un **maximum**. Le pavage (`_deck_groups`/`_page`/`_group_from`) est **ancré sur le verset sélectionné** (il débute toujours sa diapositive, suivi des versets suivants ; les versets avant l'ancre forment des diapositives en tête, navigables) et **glouton selon la place** : on n'ajoute un verset au groupe que s'il tient dans la projection — via le prédicat injecté par `set_fit_predicate(fits)` (fourni par `ProjectionController.text_fits`). Ainsi on n'affiche jamais plus que ce qui rentre à l'écran ; réduire la taille du texte fait tenir davantage de versets. Quand une diapositive regroupe plusieurs versets, `_render_group` met chacun sur **son propre paragraphe** (séparés par une ligne vide, `\n\n`) et le préfixe de son **numéro en exposant** (chiffres Unicode ⁰-⁹, pas de HTML pour que la mesure de place reste exacte) afin de les distinguer à la projection ; un verset seul reste sans numéro. `boundingRect` respecte les retours à la ligne, donc `text_fits` reste exact. La navigation du poste passe par `select_slide(index)` (le poste raisonne en diapositives, pas en versets). La projection réelle passe par le `ProjectionControls` du mode Bible. Contient une `FlowLayout` (repli des cartes) car Qt n'en fournit pas. Les boutons de lecture sont stylés en inline (via constantes `theme`) car le cascade QSS des parents stylés neutralise l'accent doré des `QPushButton` primaires.
- **`logos/ui/projection_controller.py`** : `ProjectionController(QObject)` — possède l'**unique** `ProjectionWindow` et l'état de projection **partagé** entre tous les modes (écran cible, taille du texte, écran noir) plus le mode actuellement **à l'antenne**. Applique l'exclusivité : `project(key, text)` met un seul mode à l'antenne (coupe l'autre). Émet `changed` (état) et `screens_changed` (branchement/débranchement d'écran) pour synchroniser tous les postes de contrôle. Expose `text_fits(text)` : mesure (via `QFontMetrics` sur la géométrie de l'écran cible + la taille de police) si un texte tient dans la projection — utilisé pour ne regrouper que les versets qui rentrent. Ne connaît pas les modes concrets (clé + libellé) et ne touche pas à `data`.
- **`logos/ui/projection_controls.py`** : deux widgets. `ProjectionControls(QWidget)` — poste de contrôle **réutilisable** embarqué par chaque mode (aperçu en direct, navigation ◀/▶, « Projeter », « Écran noir », « Arrêter », **unique** indicateur « à l'antenne »). Reçoit un jeu de diapos via `load(slides, index)` ; pilote la projection via le `ProjectionController` partagé et se resynchronise sur ses signaux. Le bouton « Projeter » est optionnel (`show_project_button=False` pour la Bible, qui projette via son propre « Projeter le verset » — pas de doublon). `ProjectionSettingsBar(QWidget)` — réglages de projection **globaux** (écran cible + taille du texte), une seule instance pour toute l'appli : ces réglages ne sont **pas** répétés dans chaque mode.
- **`logos/ui/projection_window.py`** : fenêtre `QWidget` sans bordure (`Qt.FramelessWindowHint`), affichée en **plein écran** via `show_on_screen(screen)` (`showFullScreen()`) sur un `QScreen` Qt. Le masquage passe par `hide_projection()` qui **quitte d'abord l'état plein écran** puis `hide()` : sous macOS, masquer une fenêtre restée en plein écran laisserait l'écran noir au lieu de le libérer (le contrôleur l'appelle depuis `stop()`/`close()`). Ne contient aucune logique métier — uniquement affichage (`set_text`, `set_font_size`, `toggle_blank`).
- **`logos/ui/predication_panel.py`** : mode « Prédications » reproduisant la maquette (barre logo/recherche/nombre d'entrées, grille ALPHABET avec compteurs, préfixes 2-lettres, liste des prédications, grille des paragraphes + boutons § préc./suiv.). Comme `BiblePanel`, il ne projette pas : il émet `selection_changed`, `project_requested`, `close_requested` et expose `current_deck()` (un paragraphe = une diapositive, texte + « Titre · §N ») et `select_slide(index)`. Réutilise les widgets génériques de `bible_panel` (`FlowLayout`, `_FlowHost`, `_NumButton`, `_circular_logo`, styles de boutons, `_clear_layout`).
- **`logos/ui/control_window.py`** : orchestration UI (seul module UI qui parle à `data`). Organise l'interface en `QStackedWidget` à trois pages — **accueil** (logo, titre, cartes `_HomeCard` : Bible, Prédications, À propos ; affichée au démarrage), **mode Bible** et **mode Prédications** (chacun : son navigateur + son propre `ProjectionControls` en colonne latérale). Un `ProjectionController` unique possède l'unique fenêtre de projection ; le cadre reste **extensible** (plusieurs modes possibles, exclusivité « un seul à l'antenne »), même s'il ne reste qu'un mode. Une `ProjectionSettingsBar` globale (écran + taille du texte) est placée **sous** le `QStackedWidget`, masquée sur l'accueil (`_update_settings_bar_visibility`). Une **barre de menus** en haut (Fichier · Affichage · Aide, `setNativeMenuBar(False)`) offre une seconde voie d'accès. « Affichage » ne contient que la **navigation** (Accueil, Bible) : les actions de projection ne sont **pas** dans le menu (doublon avec les boutons du poste de contrôle), mais leurs **raccourcis** restent actifs au niveau fenêtre — F5 Projeter, F6 Écran noir, Maj+F5 Arrêter, Ctrl+←/→ diapos — et agissent sur le **mode affiché** (`_active_controls()`).
- **`logos/ui/theme.py`** : **toute couleur de l'UI doit passer par ce module.** Ne jamais coder une couleur en dur (`#RRGGBB`) directement dans les autres modules UI — ajouter/réutiliser une constante ici. La palette est dérivée du logo de l'église (or/bronze/noir). Boutons secondaires/destructeurs : `btn.setProperty("buttonStyle", "secondary"|"danger")` (stylés via la QSS).
- **Piège QSS** : la feuille de style globale (`QWidget { font-size: 13px }`) écrase tout `QFont` posé par code. Pour une taille de texte spécifique (ex. le texte projeté), utiliser un `setStyleSheet` inline sur le widget (voir `ProjectionWindow._apply_label_style`), jamais `setFont`.
- **Vérification visuelle sans écran** : la fenêtre se capture en offscreen (`QT_QPA_PLATFORM=offscreen`, `widget.grab().save("out.png")`) — utile pour contrôler un changement d'UI depuis la sandbox.
- **`logos/app.py`** : seul endroit qui assemble les couches (DB + thème + fenêtres). `main.py` à la racine reste un simple relais pour `python main.py` et le futur packaging PyInstaller.

## Commandes utiles

```bash
# Installer les dépendances (dev inclut pytest)
pip install -r requirements-dev.txt

# Lancer l'application
python main.py

# Lancer les tests
python -m pytest tests/ -q

# Vérifier la compilation sans lancer l'UI
python -m py_compile main.py logos/app.py logos/data/*.py logos/ui/*.py

# Tester sans affichage graphique (headless, utile en CI/sandbox)
QT_QPA_PLATFORM=offscreen python3 -c "from logos.data import database; database.init_db(); print('OK')"
```

Les tests couvrent la logique pure (`logos/data/`), le CRUD SQLite (base temporaire via `monkeypatch` de `DB_PATH`) et un test de fumée de la fenêtre de contrôle en offscreen. Pas encore de linter ; pytest-qt serait adapté si les tests de widgets deviennent plus poussés.

## Conventions de code

- Commentaires et messages UI **en français** (public cible francophone).
- Noms de fonctions/variables/classes en anglais, comme le reste du code Python existant.
- Un module = une responsabilité claire (voir "rôle de chaque module" ci-dessus). Séparation stricte des couches : `logos/data/` n'importe jamais Qt, `logos/ui/` ne contient jamais de SQL.
- Pas de couleur, taille de police par défaut, ou style visuel codé en dur hors de `logos/ui/theme.py`.
- Base de données : toute nouvelle table/colonne doit passer par une fonction dédiée dans `logos/data/database.py`, avec `CREATE TABLE IF NOT EXISTS` pour rester compatible avec les bases existantes des utilisateurs (pas de système de migration pour l'instant).
- Toute nouvelle logique pure (parsing, découpage, formatage) va dans `logos/data/` avec un test dans `tests/`.

## Points d'attention

- L'application doit fonctionner **100% hors ligne** — ne pas introduire de dépendance réseau sans en discuter (voir exigences non fonctionnelles du cahier des charges).
- La fenêtre de projection ne doit **jamais** afficher d'éléments d'interface (boutons, bordures, barre de titre) — seul le contenu projeté doit être visible par l'assemblée.
- Tester tout changement à la détection d'écran avec zéro, un et plusieurs écrans connectés si possible (`QGuiApplication.screens()` peut renvoyer une liste à un seul élément en environnement de test).

## Roadmap (voir cahier_des_charges.md pour le détail)

- **Actuel** : mode Bible (LSG 1910 embarquée) et mode Prédications (branham.fr, importé hors ligne via `scripts/scrape_predications.py`), projection plein écran multi-écran, navigation, écran noir, aperçu en direct, taille du texte réglable, exclusivité un-seul-mode-à-l'antenne. Packaging PyInstaller restant.
- **Retiré** : gestion des chants, ordre du culte/playlist (voir la note en tête de fichier).
- **Prédications — pistes** : import du corpus complet (actuellement sous-ensemble par lettre), dédoublonnage des traductions, recherche plein texte dans les paragraphes.
- **Pistes** : arrière-plans personnalisés, KJV/autres versions, télécommande mobile, historique d'usage.