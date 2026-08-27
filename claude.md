# CLAUDE.md

Ce fichier donne à Claude Code le contexte nécessaire pour travailler efficacement sur ce dépôt.

## Vue d'ensemble du projet

**BDA** est une application de bureau de présentation pour l'église Logos Tabernacle (type Holyrics/ProPresenter simplifié) — « BDA » est le nom de l'application, « Logos Tabernacle » celui de l'église (son logo fonde le thème visuel). Elle permet à un opérateur de piloter, depuis un poste de contrôle, l'affichage de **passages bibliques** et de **paragraphes de prédications** sur un second écran (vidéoprojecteur) pendant les cultes.

> **Note** : la partie « Chants / Culte » (bibliothèque de chants, édition des paroles, ordre du culte) a été **retirée** (réintroduction prévue plus tard sous forme d'un mode supplémentaire). L'application propose deux modes : **Bible** et **Prédications** (paragraphes numérotés issus de branham.fr, importés hors ligne). Le `cahier_des_charges.md` décrit encore les chants : le considérer comme historique sur ce point.

Le cahier des charges complet (fonctionnalités V1/V2/V3, exigences, planning) est dans `cahier_des_charges.md` à la racine — s'y référer avant d'ajouter une fonctionnalité pour vérifier son statut (Must/Should/Could) et sa phase prévue.

## Stack technique

- **Langage** : Python 3.12
- **Interface graphique** : PySide6 (Qt for Python)
- **Base de données** : SQLite (fichier local, `~/.bda/bda.db`, reconstruite automatiquement au premier lancement depuis les assets embarqués)
- **Packaging** : PyInstaller (macOS `.app` / Windows `.exe`) via `packaging/bda.spec`

## Structure du projet

```
.
├── main.py                     # Point d'entrée mince : délègue à logos.app.main()
├── logos/                      # Package de l'application
│   ├── app.py                  # Assemblage : init DB, import Bible, thème, ControlWindow
│   ├── version.py              # Numéro de version — source unique (À propos, updates, bda.spec)
│   ├── resources.py            # Localisation des assets (dépôt opérateur, bundle PyInstaller, dépôt)
│   ├── updates.py              # Vérification facultative d'une nouvelle version (seul accès réseau)
│   ├── assets/
│   │   └── bible_ls1910.json.gz # Bible Louis Segond 1910 (domaine public), embarquée
│   ├── data/                   # Couche données — AUCUN import Qt ici
│   │   ├── database.py         # Connexion SQLite + tables Bible et prédications
│   │   ├── bible.py            # Import + requêtes sur la Bible embarquée
│   │   ├── predications.py     # Import + requêtes sur les prédications (alphabet/préfixe/paragraphes)
│   │   ├── slides.py           # Mise en forme passages -> diapositives + découpage selon la place (split_to_fit)
│   │   └── textutils.py        # Utilitaires de texte partagés (strip_accents)
│   └── ui/                     # Couche interface — AUCUN SQL ici
│       ├── control_window.py   # Fenêtre principale : accueil + modes Bible et Prédications
│       ├── bible_panel.py      # Mode « Navigateur biblique » (grilles livres/chapitres/versets), émet des signaux
│       ├── predication_panel.py # Mode « Prédications » (alphabet -> préfixe -> prédication -> paragraphes)
│       ├── projection_controller.py # Contrôleur partagé : unique fenêtre de projection + exclusivité (un seul mode à l'antenne)
│       ├── projection_controls.py   # Poste de contrôle réutilisable embarqué par chaque mode
│       ├── projection_window.py # Fenêtre plein écran sans bordure sur l'écran secondaire
│       ├── update_banner.py    # Bandeau « nouvelle version » + vérification en tâche de fond
│       ├── widgets.py          # Widgets génériques partagés (FlowLayout/FlowHost, NumButton, logo rond, clear_layout)
│       └── theme.py            # Palette, feuille de style Qt (QSS) et styles inline de boutons, basé sur le logo
├── .github/workflows/
│   └── release.yml             # CI : build macOS + Windows sur tag, publication GitHub Release
├── packaging/                  # Construction de l'exécutable
│   ├── bda.spec                # Recette PyInstaller (assets embarqués, icône, sans console)
│   ├── package.py              # Archive versionnée + somme SHA-256 + latest.json
│   ├── make_icons.py           # Génère bda.icns / bda.ico depuis logo.png (à relancer si le logo change)
│   └── icons/                  # Icônes générées (versionnées)
├── scripts/                    # Outils hors-appli
│   └── scrape_predications.py  # Import branham.fr -> logos/assets/predications.json.gz (stdlib, lancé par l'utilisateur)
├── tests/                      # Tests pytest
│   ├── test_bible.py           # Import/requêtes Bible + mise en forme des passages
│   ├── test_bible_panel.py     # Panneau Bible en offscreen
│   ├── test_predications.py    # Data prédications + parseurs du script + panneau
│   ├── test_resources.py       # Priorité du dépôt opérateur + repli si fichier illisible
│   ├── test_updates.py         # Comparaison de versions + lecture du manifeste (réseau simulé)
│   └── test_control_window.py  # Fumée UI en QT_QPA_PLATFORM=offscreen
├── README.md                   # Guide d'installation/utilisation opérateur
├── requirements.txt            # Dépendances d'exécution (PySide6)
└── requirements-dev.txt        # Dépendances de dev (pytest)
```

### Rôle de chaque module

- **`logos/data/database.py`** : connexion SQLite et création des tables (`init_db`, `CREATE TABLE IF NOT EXISTS`) : Bible, prédications et table `meta` clé/valeur (helpers `get_meta`/`set_meta`, utilisée pour les empreintes d'assets). Les autres modules `data/` font leurs requêtes via `get_connection()` — aucun SQL hors de `logos/data/`. Ce sous-package ne doit jamais importer Qt.
- **`logos/data/bible.py`** : Bible Louis Segond 1910 embarquée dans `logos/assets/` (gzip) et importée dans SQLite au premier lancement (`ensure_imported()`, appelé par `app.main`) ; réimportée automatiquement si l'asset change (empreinte SHA-256 stockée dans `meta` — même mécanique pour les prédications). L'application reste 100 % hors ligne.
- **`logos/data/predications.py`** : prédications (paragraphes numérotés) importées depuis `logos/assets/predications.json.gz` (généré par `scripts/scrape_predications.py`). `letter`/`prefix` sont dérivés du titre FR **désaccentué** à l'import (« Élie » -> lettre E, préfixe « El ») pour un regroupement A-Z. Expose `letters_with_counts`, `prefixes_with_counts(letter)`, `list_by_prefix`, `search` (titres FR/EN et code date, accents/casse/apostrophes ignorés via `textutils.search_key`), `get_paragraphs`. L'asset ne doit **pas** être livré avec le dépôt ni avec un paquet public (contenu sous copyright branham.fr/VGR) : sans lui, le mode Prédications affiche « non disponible ».
- **`logos/data/slides.py`** : `passage_label()` et `passage_to_text()` mettent en forme un passage biblique en texte projetable (une diapositive par verset : texte + référence). `split_to_fit(text, fits)` découpe un texte par mots en morceaux satisfaisant un prédicat de place (dichotomie guidée par la taille du morceau précédent) — utilisé pour les paragraphes de prédication trop longs. Logique pure — toute nouvelle logique de contenu va dans `logos/data/`, pas dans l'UI.
- **`logos/data/textutils.py`** : utilitaires de texte partagés par la couche données (`strip_accents` — classement A-Z et références bibliques ; `search_key` — clé de recherche minuscules/sans accents/apostrophes unifiées, utilisée par `bible.search_verses` et `predications.search`).
- **`logos/data/bible.py`** expose aussi les données de référence d'affichage : `book_abbreviation(id)` (abréviations canoniques des 66 livres pour la grille des livres), `testament(id)` (Ancien/Nouveau) et `get_chapter(book_id, chapter)` (tous les versets d'un chapitre pour la colonne de lecture). `parse_reference("Jean 3:16")` analyse une référence tapée (nom, abréviation ou début de nom, accents ignorés ; chapitre/verset optionnels) — la barre de recherche du panneau Bible s'en sert pour sauter directement au passage. `search_verses(query)` fait une recherche plein texte dans les versets (accents/casse ignorés, apostrophes clavier `'` et typographique `’` unifiées, minimum 3 caractères, 50 résultats max) sur un cache mémoire normalisé construit à la première requête (`warm_search_cache()` le précharge au lancement) et invalidé par `import_data`.
- **`logos/ui/bible_panel.py`** : navigateur biblique reproduisant la maquette « Bible Navigator » (barre supérieure logo/recherches/badge LSG, colonne de lecture avec versets cliquables, grille des livres **colorée par groupe canonique** — Pentateuque, Historiques, Poétiques, Prophètes, Évangiles, Actes, Épîtres, Apocalypse ; clés `bible.book_group()`, couleurs `theme.BOOK_GROUP_COLORS`, la sélection restant dorée —, grilles chapitres/versets, barre de statut). La barre de recherche reconnaît livres **et** références (`bible.parse_reference`) : autocomplétion des noms de livres (`QCompleter`), indication en direct de la cible reconnue (« → Jean 3:16 »), saut immédiat dès qu'un chapitre est saisi, Entrée pour valider (livre seul inclus) puis effacer. Un **second champ** cherche dans le **texte des versets** (`bible.search_verses`, anti-rebond 300 ms) : résultats dans une liste flottante ancrée sous le champ (repositionnée par `resizeEvent`), clic ou Entrée pour sauter au verset. **Projection partielle** : sélectionner un passage du verset à la souris dans la colonne de lecture fait démarrer la projection à cet endroit (« …afin que… », préfixe `…`) — signal `partial_selected` de `NumberedTextRow`, offset conservé dans `_partial_start` (remis à zéro au changement de verset ou au clic sans sélection), appliqué par `_verse_display_text` dans le rendu du groupe, donc cohérent avec la mesure de place et le direct. L'état de projection n'est **pas** affiché ici (l'indicateur « à l'antenne » vit dans le `ProjectionControls` du mode). C'est le **staging** du mode Bible : il ne projette pas lui-même. Il expose `current_deck()` et émet `selection_changed` (sélection modifiée), `project_requested` (« Projeter le verset ») et `close_requested` (bouton « ‹ Retour » → accueil). Un sélecteur « Versets par diapositive » (`QSpinBox`, 1–20) fixe un **maximum**. Le pavage (`_deck_groups`/`_page`/`_group_from`) est **ancré sur le verset sélectionné** (il débute toujours sa diapositive, suivi des versets suivants ; les versets avant l'ancre forment des diapositives en tête, navigables) et **glouton selon la place** : on n'ajoute un verset au groupe que s'il tient dans la projection — via le prédicat injecté par `set_fit_predicate(fits)` (fourni par `ProjectionController.text_fits`). Ainsi on n'affiche jamais plus que ce qui rentre à l'écran ; réduire la taille du texte fait tenir davantage de versets. Quand une diapositive regroupe plusieurs versets, `_render_group` met chacun sur **son propre paragraphe** (séparés par une ligne vide, `\n\n`) et le préfixe de son **numéro en exposant** (chiffres Unicode ⁰-⁹, pas de HTML pour que la mesure de place reste exacte) afin de les distinguer à la projection ; un verset seul reste sans numéro. `boundingRect` respecte les retours à la ligne, donc `text_fits` reste exact. La navigation du poste passe par `select_slide(index)` (le poste raisonne en diapositives, pas en versets). La projection réelle passe par le `ProjectionControls` du mode Bible. Les widgets génériques (dont la `FlowLayout`, que Qt ne fournit pas) vivent dans `logos/ui/widgets.py` ; les boutons sont stylés en inline via les fonctions `theme.btn_*_style()` car le cascade QSS des parents stylés neutralise l'accent doré des `QPushButton` primaires.
- **`logos/ui/projection_controller.py`** : `ProjectionController(QObject)` — possède l'**unique** `ProjectionWindow` et l'état de projection **partagé** entre tous les modes (écran cible, taille du texte, écran noir) plus le mode actuellement **à l'antenne**. Applique l'exclusivité : `project(key, text)` met un seul mode à l'antenne (coupe l'autre). Émet `changed` (état) et `screens_changed` (branchement/débranchement d'écran) pour synchroniser tous les postes de contrôle. Expose `text_fits(text)` : mesure (via `QFontMetrics` sur la géométrie de l'écran cible + la taille de police) si un texte tient dans la projection — utilisé pour ne regrouper que les versets qui rentrent. Ne connaît pas les modes concrets (clé + libellé) et ne touche pas à `data`.
- **`logos/ui/projection_controls.py`** : deux widgets. `ProjectionControls(QWidget)` — poste de contrôle **réutilisable** embarqué par chaque mode (aperçu en direct, navigation ◀/▶, « Projeter », « Écran noir », « Arrêter », **unique** indicateur « à l'antenne »). Reçoit un jeu de diapos via `load(slides, index)` ; pilote la projection via le `ProjectionController` partagé et se resynchronise sur ses signaux. Le bouton « Projeter » est optionnel (`show_project_button=False` pour la Bible, qui projette via son propre « Projeter le verset » — pas de doublon). `ProjectionSettingsBar(QWidget)` — réglages de projection **globaux** (écran cible + taille du texte), une seule instance pour toute l'appli : ces réglages ne sont **pas** répétés dans chaque mode.
- **`logos/ui/projection_window.py`** : fenêtre `QWidget` sans bordure (`Qt.FramelessWindowHint`), affichée en **plein écran** via `show_on_screen(screen)` (`showFullScreen()`) sur un `QScreen` Qt. Le masquage passe par `hide_projection()` qui **quitte d'abord l'état plein écran** puis `hide()` : sous macOS, masquer une fenêtre restée en plein écran laisserait l'écran noir au lieu de le libérer (le contrôleur l'appelle depuis `stop()`/`close()`). Ne contient aucune logique métier — uniquement affichage (`set_text`, `set_font_size`, `toggle_blank`).
- **`logos/ui/predication_panel.py`** : mode « Prédications », **même disposition que `BiblePanel`** pour une prise en main identique : colonne de lecture à gauche (code date, titre, paragraphes cliquables via `NumberedTextRow`, boutons § préc./suiv. et « Projeter le paragraphe »), navigation à droite (grille ALPHABET avec compteurs en haut ; préfixes 2-lettres + liste des prédications et grille des paragraphes en bas), barre de statut (date · titre / paragraphe sélectionné). Un paragraphe trop long pour la projection est **découpé en plusieurs diapositives** « Titre · §N · i/n » (via `slides.split_to_fit` et le prédicat injecté par `set_fit_predicate` ; la mesure inclut un gabarit de suffixe pour que le libellé réel ne fasse pas déborder). Le découpage est mémorisé par prédication (`_deck_cache`) car la mesure est coûteuse — `invalidate_deck()` le fait recalculer quand la taille du texte ou l'écran change (appelé par `ControlWindow`). Comme `BiblePanel`, il ne projette pas : il émet `selection_changed`, `project_requested`, `close_requested` et expose `current_deck()` (un paragraphe = une diapositive, texte + « Titre · §N ») et `select_slide(index)`. Réutilise les widgets génériques de `logos/ui/widgets.py` (`FlowHost`, `NumButton`, `circular_logo`, `clear_layout`) et les styles de boutons de `theme`.
- **`logos/ui/control_window.py`** : orchestration UI (seul module UI qui parle à `data`). Organise l'interface en `QStackedWidget` à trois pages — **accueil** (logo, titre, cartes `_HomeCard` : Bible, Prédications, À propos ; affichée au démarrage), **mode Bible** et **mode Prédications** (chacun : son navigateur + son propre `ProjectionControls` en colonne latérale). Un `ProjectionController` unique possède l'unique fenêtre de projection ; le cadre reste **extensible** (plusieurs modes possibles, exclusivité « un seul à l'antenne »), même s'il ne reste qu'un mode. Une `ProjectionSettingsBar` globale (écran + taille du texte) est placée **sous** le `QStackedWidget`, masquée sur l'accueil (`_update_settings_bar_visibility`). Les **réglages sont persistants** (taille du texte, écran cible par nom, versets par diapositive) : restaurés depuis la table `meta` au lancement (`_restore_settings`) et sauvegardés à chaque changement (`_save_settings`, qui n'écrit que si la valeur a bougé car `changed` est émis souvent). Une **barre de menus** en haut (Fichier · Affichage · Aide, `setNativeMenuBar(False)`) offre une seconde voie d'accès. « Affichage » ne contient que la **navigation** (Accueil, Bible, Prédications) : les actions de projection ne sont **pas** dans le menu (doublon avec les boutons du poste de contrôle), mais leurs **raccourcis** restent actifs au niveau fenêtre — F5 Projeter, F6 Écran noir, Maj+F5 Arrêter, Ctrl+←/→ diapos — et agissent sur le **mode affiché** (`_active_controls()`). S'y ajoutent des touches « présentation » **sans modificateur** via `keyPressEvent` (→ ↓ PgSuiv Espace = suivante ; ← ↑ PgPréc = précédente ; B = écran noir) : Qt ne fait remonter au `keyPressEvent` de la fenêtre que les touches non consommées par le widget focalisé, donc les champs de recherche gardent leurs flèches — ne pas les convertir en `QShortcut`, qui court-circuiterait les widgets. « Aide → Raccourcis clavier » liste le tout. « Aide » porte la recherche de mise à jour : vérification manuelle (qui rapporte **toutes** les issues, y compris l'échec réseau et l'absence d'URL configurée) et bascule « Vérifier au démarrage » persistée dans `meta`. La vérification au lancement, elle, est **silencieuse** : elle n'affiche le bandeau qu'en cas de nouvelle version, jamais d'erreur — un poste sans connexion ne doit voir aucune alerte.
- **`logos/ui/theme.py`** : **toute couleur de l'UI doit passer par ce module.** Ne jamais coder une couleur en dur (`#RRGGBB`) directement dans les autres modules UI — ajouter/réutiliser une constante ici. La palette est dérivée du logo de l'église (or/bronze/noir). Boutons secondaires/destructeurs : `btn.setProperty("buttonStyle", "secondary"|"danger")` (stylés via la QSS). Quand le cascade QSS d'un parent stylé écrase ces styles, utiliser les styles inline `theme.btn_primary_style()`/`btn_secondary_style()`/`btn_danger_style()` — un seul jeu de styles de boutons pour toute l'appli, jamais de variante locale.
- **`logos/ui/widgets.py`** : widgets et aides génériques partagés par les panneaux (`FlowLayout`/`FlowHost` — disposition en flux avec repli, `NumButton` — case numérotée, `NumberedTextRow` — ligne de lecture cliquable au texte sélectionnable (signal `partial_selected`), `circular_logo`, `clear_layout`). Aucune logique métier : tout composant réutilisable par plusieurs panneaux va ici, pas dans un panneau.
- **Piège QSS** : la feuille de style globale (`QWidget { font-size: 13px }`) écrase tout `QFont` posé par code. Pour une taille de texte spécifique (ex. le texte projeté), utiliser un `setStyleSheet` inline sur le widget (voir `ProjectionWindow._apply_label_style`), jamais `setFont`.
- **Vérification visuelle sans écran** : la fenêtre se capture en offscreen (`QT_QPA_PLATFORM=offscreen`, `widget.grab().save("out.png")`) — utile pour contrôler un changement d'UI depuis la sandbox.
- **`logos/resources.py`** : **seul** module qui sait où sont les assets et le dossier utilisateur (`USER_DIR = ~/.bda`, dont `database.DB_PATH` dérive). `asset_path("nom")` cherche dans cet ordre : `~/.bda/assets/<nom>` (dépôt de l'opérateur), puis `sys._MEIPASS/logos/assets/` (appli gelée), puis `logos/assets/` (dépôt). Ne jamais reconstruire un chemin d'asset avec `Path(__file__)` ailleurs, cela casse l'exécutable. `bundled_asset_path()` force la version livrée (repli), `ensure_user_dirs()` crée le dossier de dépôt au lancement. N'importe pas Qt (utilisable depuis `logos/data/`).
- **Mise à jour du contenu** (sans réinstallation ni réseau) : déposer un fichier dans `~/.bda/assets/` remplace l'asset livré au lancement suivant — le changement d'empreinte SHA-256 stockée dans `meta` déclenche le réimport tout seul. `bible.ensure_imported()` et `predications.ensure_imported()` essaient le fichier déposé puis, **s'il est illisible**, préviennent sur `stderr` et retombent sur le corpus livré : un fichier corrompu déposé par erreur ne doit jamais empêcher l'application de démarrer un dimanche matin. Toute nouvelle logique d'import doit conserver ce repli.
- **`logos/version.py`** : numéro de version, **source unique**. En dérivent la fenêtre « À propos », la comparaison de `logos/updates.py` et les champs `CFBundle*Version` du bundle (relus par regex dans `packaging/bda.spec`, sans importer le paquet). Une publication = bumper ce fichier, rien d'autre.
- **`logos/updates.py`** : **seul** module qui accède au réseau. Interroge un manifeste JSON (`MANIFEST_URL`, **vide par défaut** → fonctionnalité dormante, aucun appel réseau) et renvoie un `CheckResult` de statut `DISABLED`/`ERROR`/`UP_TO_DATE`/`AVAILABLE`. **Ne lève jamais** et ne télécharge ni n'installe rien : il signale, l'opérateur décide. Le contenu distant étant non fiable, le schéma **HTTPS est imposé** (manifeste *et* lien de téléchargement), la réponse est bornée en taille et les champs texte tronqués. Pas de Qt, donc testable tel quel (`tests/test_updates.py` simule `urlopen`).
- **`logos/ui/update_banner.py`** : `UpdateBanner` (bandeau refermable en haut de la fenêtre, jamais modal — il ne doit pas interrompre un culte) et `check_async(owner, callback)` qui lance la vérification dans un `QThreadPool` pour que le réseau ne fige pas l'interface. Les textes venus du manifeste sont affichés en `Qt.PlainText` : **ne jamais** les passer en texte riche, Qt interpréterait le HTML.
- **`logos/app.py`** : seul endroit qui assemble les couches (DB + thème + fenêtres). `main.py` à la racine reste un simple relais pour `python main.py` et pour PyInstaller (c'est le script d'entrée déclaré dans `packaging/bda.spec`).
- **`packaging/bda.spec`** : recette PyInstaller, à lancer depuis la racine (`pyinstaller --noconfirm --clean packaging/bda.spec`). Mode « un dossier » (plus rapide au démarrage et plus simple à dépanner qu'un fichier unique), sans console, icône posée, `logos/assets/` copié **en conservant l'arborescence** attendue par `logos/resources.py` (destination `logos/assets`). Sur macOS, un `BUNDLE` produit `dist/BDA.app` ; ailleurs le livrable est le **dossier** `dist/BDA/` complet. Pas de compilation croisée : construire le `.exe` sur Windows, le `.app` sur macOS. Toute nouvelle donnée embarquée doit être ajoutée à `datas` ici **et** lue via `resources.asset_path`.
- **Corpus de prédications et diffusion** : le contenu de `predications.json.gz` est sous **copyright branham.fr / VGR**. Il ne doit sortir ni dans un paquet public ni dans le dépôt : `packaging/bda.spec` l'exclut sauf `BDA_BUNDLE_PREDICATIONS=1` (build interne), et il est listé dans `.gitignore`. Chaque poste reçoit son corpus via `~/.bda/assets/`. Ne jamais lever ces garde-fous « pour simplifier » un build de distribution.
- **`packaging/package.py`** : met en forme le résultat de PyInstaller pour la distribution — `dist/BDA-<version>-<plateforme>.zip` + `.sha256`, et `latest.json` (mode `--manifest-only`, utilisé par le job de release). Sur macOS l'archive passe par **`ditto`** et non `zip` : `zip` aplatit les liens symboliques des frameworks Qt et livre un `.app` cassé. Le manifeste pointe vers une **page** de release, pas un fichier, puisque l'utilisateur choisit sa plateforme.
- **`.github/workflows/release.yml`** : déclenché par un tag `v*`. Vérifie que le tag correspond à `logos/version.py` (sinon arrêt avant build), lance les tests, construit macOS et Windows — c'est la seule façon d'avoir un `.exe` sans machine Windows — puis publie la release via `gh release create` (pas d'action tierce). Publier une version = bumper `logos/version.py`, committer, taguer.
- **`packaging/make_icons.py`** : génère `packaging/icons/bda.icns` et `bda.ico` depuis `logos/assets/logo.png` (redimensionnement via Qt, conteneurs ICNS/ICO écrits à la main — aucune dépendance en plus). À relancer uniquement si le logo change ; les icônes produites sont versionnées.

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

# Construire l'exécutable (résultat dans dist/ : BDA.app sur macOS, BDA/ ailleurs)
pip install -r requirements-build.txt
pyinstaller --noconfirm --clean packaging/bda.spec

# Vérifier l'exécutable construit sans écran ni base existante (base repartie de zéro)
HOME=/tmp/bda-test QT_QPA_PLATFORM=offscreen ./dist/BDA.app/Contents/MacOS/BDA
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

- L'application doit fonctionner **100% hors ligne** — ne pas introduire de dépendance réseau sans en discuter (voir exigences non fonctionnelles du cahier des charges). **Seule exception admise** : la vérification de version de `logos/updates.py`, et sous conditions strictes — facultative (désactivable par « Aide → Vérifier au démarrage », dormante tant que `MANIFEST_URL` est vide), en tâche de fond, silencieuse en cas d'échec, et sans aucune conséquence sur le fonctionnement si le poste n'a pas de connexion. Toute autre fonctionnalité doit rester utilisable sans réseau.
- Le contenu récupéré sur le réseau est **non fiable** : imposer HTTPS, borner ce qu'on lit, et ne jamais l'afficher en texte riche Qt (`Qt.PlainText`). Aucun téléchargement ni installation automatique — l'opérateur reste maître du remplacement.
- La fenêtre de projection ne doit **jamais** afficher d'éléments d'interface (boutons, bordures, barre de titre) — seul le contenu projeté doit être visible par l'assemblée.
- Tester tout changement à la détection d'écran avec zéro, un et plusieurs écrans connectés si possible (`QGuiApplication.screens()` peut renvoyer une liste à un seul élément en environnement de test).

## Roadmap (voir cahier_des_charges.md pour le détail)

- **Actuel** : mode Bible (LSG 1910 embarquée) et mode Prédications (branham.fr, importé hors ligne via `scripts/scrape_predications.py`), projection plein écran multi-écran, navigation, écran noir, aperçu en direct, taille du texte réglable, exclusivité un-seul-mode-à-l'antenne, packaging PyInstaller (`packaging/bda.spec`).
- **Mises à jour** : contenu à jour par dépôt dans `~/.bda/assets/` (hors ligne) ; vérification de version facultative prête mais **dormante** tant que `MANIFEST_URL` (`logos/updates.py`) est vide — l'activer demande de publier un `latest.json` en HTTPS quelque part.
- **Packaging — restant** : signature/notarisation macOS — sans elle, un bundle **copié** se débloque par clic droit → Ouvrir, mais un bundle **téléchargé** (mis en quarantaine) exige sur macOS 15+ un passage par Réglages Système → Confidentialité et sécurité → « Ouvrir quand même » : rédhibitoire pour une distribution publique. Signature Windows (avertissement SmartScreen), et un installeur (DMG / Inno Setup) si la distribution par dossier zippé ne suffit plus. La **mise à jour automatique complète** (l'appli se remplace seule) suppose ces signatures : ne pas s'y lancer avant.
- **Retiré** : gestion des chants, ordre du culte/playlist (voir la note en tête de fichier).
- **Prédications — pistes** : import du corpus complet (actuellement sous-ensemble par lettre), dédoublonnage des traductions, recherche plein texte dans les paragraphes.
- **Pistes** : arrière-plans personnalisés, KJV/autres versions, télécommande mobile, historique d'usage.