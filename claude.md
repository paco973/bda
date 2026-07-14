# CLAUDE.md

Ce fichier donne à Claude Code le contexte nécessaire pour travailler efficacement sur ce dépôt.

## Vue d'ensemble du projet

**Logos Tabernacle** est une application de bureau de présentation pour l'église (type Holyrics/ProPresenter simplifié). Elle permet à un opérateur de piloter, depuis un poste de contrôle, l'affichage de paroles de chants sur un second écran (vidéoprojecteur) pendant les cultes.

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
│   │   ├── database.py         # Connexion SQLite, CREATE TABLE, CRUD des chants
│   │   ├── bible.py            # Import + requêtes sur la Bible embarquée
│   │   ├── service.py          # Ordre du culte (liste ordonnée chants/passages)
│   │   └── slides.py           # Logique de contenu : paroles/passages -> diapositives
│   └── ui/                     # Couche interface — AUCUN SQL ici
│       ├── control_window.py   # Fenêtre de contrôle (bibliothèque, édition, culte, projection)
│       ├── bible_panel.py      # Onglet Bible (livre/chapitre/versets), émet des signaux
│       ├── projection_window.py # Fenêtre plein écran sans bordure sur l'écran secondaire
│       └── theme.py            # Palette de couleurs + feuille de style Qt (QSS), basé sur le logo
├── tests/                      # Tests pytest
│   ├── test_slides.py          # Découpage paroles -> diapos (logique pure)
│   ├── test_database.py        # CRUD SQLite sur base temporaire
│   ├── test_bible.py           # Import/requêtes Bible + mise en forme des passages
│   ├── test_service.py         # Ordre du culte (ajout, déplacement, synchronisation)
│   ├── test_bible_panel.py     # Panneau Bible en offscreen
│   └── test_control_window.py  # Fumée UI en QT_QPA_PLATFORM=offscreen
├── README.md                   # Guide d'installation/utilisation opérateur
├── requirements.txt            # Dépendances d'exécution (PySide6)
└── requirements-dev.txt        # Dépendances de dev (pytest)
```

### Rôle de chaque module

- **`logos/data/database.py`** : connexion SQLite et création de **toutes** les tables (`init_db`), plus le CRUD des chants. Les autres modules `data/` font leurs requêtes via `get_connection()` — aucun SQL hors de `logos/data/`. Ce sous-package ne doit jamais importer Qt.
- **`logos/data/bible.py`** : Bible Louis Segond 1910 embarquée dans `logos/assets/` (gzip) et importée dans SQLite au premier lancement (`ensure_imported()`, appelé par `app.main`). L'application reste 100 % hors ligne.
- **`logos/data/service.py`** : ordre du culte persistant — liste ordonnée d'éléments `song` (référence vers un chant, paroles chargées en direct) ou `passage` (texte figé au moment de l'ajout). `database.delete_song` retire aussi le chant du culte.
- **`logos/data/slides.py`** : `lyrics_to_slides()` découpe les paroles en diapositives sur les lignes vides (`\n\n`). C'est la seule logique de "parsing" du contenu — toute nouvelle logique de contenu (versets V2, etc.) va dans `logos/data/`, pas dans l'UI.
- **`logos/ui/projection_window.py`** : fenêtre `QWidget` sans bordure (`Qt.FramelessWindowHint`), positionnée via `show_on_screen(screen)` sur un `QScreen` Qt. Ne contient aucune logique métier — uniquement affichage (`set_text`, `set_font_size`, `toggle_blank`).
- **`logos/ui/control_window.py`** : contient toute la logique d'interaction (UI + orchestration). Instancie une seule `ProjectionWindow`. Détecte les écrans via `QGuiApplication.screens()`. C'est le seul module UI qui parle à la couche `data`.
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

- **V1 (fonctionnalités terminées ; packaging PyInstaller restant)** : gestion des chants, projection plein écran multi-écran, navigation, écran noir, sauvegarde locale.
- **V2 (en cours)** : versets bibliques ✅, ordre du culte/playlist ✅, aperçu en direct ✅ — restent : arrière-plans personnalisés, raccourcis clavier.
- **V3+** : télécommande mobile, multi-postes en réseau local, historique d'usage.