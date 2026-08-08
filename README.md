# Logos Tabernacle

Application de bureau de présentation pour l'église : l'opérateur pilote, depuis
un poste de contrôle, l'affichage des paroles de chants sur un second écran
(vidéoprojecteur) pendant le culte. Fonctionne 100 % hors ligne.

## Installation

Prérequis : Python 3.12+.

```bash
pip install -r requirements.txt
python main.py
```

## Utilisation

1. **Créer un chant** (onglet Chants) : bouton « Nouveau », saisir le titre et
   les paroles. Laisser une **ligne vide** entre chaque diapositive, puis
   « Enregistrer le chant ».
2. **Versets bibliques** (onglet Bible) : choisir livre, chapitre et plage de
   versets (Louis Segond 1910 incluse, une diapositive par verset avec sa
   référence), puis « Afficher les diapositives » ou « Ajouter au culte ».
3. **Préparer l'ordre du culte** : ajouter chants et passages avec « Ajouter au
   culte », réordonner avec ▲ ▼. La liste est sauvegardée et retrouvée au
   prochain lancement. Pendant le culte, cliquer un élément charge ses
   diapositives.
4. **Choisir l'écran de projection** dans la liste déroulante (le vidéoprojecteur
   est proposé par défaut), puis « Démarrer la projection ».
5. **Projeter** : cliquer une diapositive dans la liste, ou utiliser les boutons
   « ◀ Précédent / Suivant ▶ » (les flèches du clavier fonctionnent quand la
   liste des diapositives a le focus).
6. **Écran noir** : masque le texte projeté sans le perdre (moments de prière,
   prédication…). Recliquer ou projeter une diapo pour réafficher.

La section « Projection » affiche un **aperçu en direct** de ce que voit
l'assemblée, un indicateur d'état (arrêtée / en direct / écran noir) et le
compteur de diapositives.

Tout est sauvegardé localement dans `~/.holyrics_clone/songs.db` (chants, ordre
du culte et texte biblique — l'application fonctionne 100 % hors ligne).

## Développement

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

L'architecture (couches `logos/data` et `logos/ui`, conventions) est documentée
dans `claude.md`.

## Créer un exécutable (macOS / Windows)

La recette de construction est versionnée dans `packaging/bda.spec` : elle
embarque les assets (`logos/assets/`), pose l'icône et désactive la console.

```bash
pip install -r requirements-build.txt
pyinstaller --noconfirm --clean packaging/bda.spec
```

Résultat dans `dist/` :

- **macOS** : `dist/BDA.app`, double-cliquable, à glisser dans `/Applications`.
- **Windows** : `dist/BDA/BDA.exe` — distribuer le **dossier `BDA` entier**
  (l'`.exe` seul ne fonctionne pas), par exemple zippé.

PyInstaller ne fait pas de compilation croisée : le `.app` macOS se construit
**sur un Mac**, le `.exe` Windows **sur une machine Windows**, avec la même
commande. Un `.app` construit sur un Mac Apple Silicon ne tourne que sur Apple
Silicon (et inversement pour Intel).

Points à connaître :

- Les prédications ne sont embarquées que si `logos/assets/predications.json.gz`
  existe au moment du build (asset non versionné, voir
  `scripts/scrape_predications.py`). Sans lui, l'exécutable démarre et le mode
  Prédications affiche « non disponible ».
- Au premier lancement, l'exécutable reconstruit la base dans `~/.bda/bda.db`
  (import de la Bible et des prédications) : ce démarrage-là prend quelques
  secondes, les suivants sont immédiats.
- **macOS** : le bundle n'est pas signé ni notarisé. Sur un autre Mac, le
  premier lancement doit se faire par **clic droit → Ouvrir** (puis « Ouvrir »
  dans l'alerte), sinon Gatekeeper le bloque.
- **Windows** : SmartScreen peut afficher un avertissement pour un exécutable
  non signé — « Informations complémentaires » puis « Exécuter quand même ».
- Si le logo change, régénérer les icônes :
  `python packaging/make_icons.py`.
