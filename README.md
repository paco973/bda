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

## Mettre à jour

### Le contenu (prédications, texte biblique) — sans réinstaller

Déposer le nouveau fichier dans **`~/.bda/assets/`** (dossier créé au premier
lancement), en gardant le nom d'origine :

| Fichier | Contenu |
|---|---|
| `predications.json.gz` | corpus des prédications |
| `bible_ls1910.json.gz` | texte biblique |
| `logo.png` | logo affiché dans l'application |

Au lancement suivant, l'application détecte le changement et réimporte
automatiquement (quelques secondes). Aucune connexion Internet n'est nécessaire.

Pour revenir au contenu d'origine, supprimer le fichier déposé. Si le fichier
déposé est abîmé, l'application le signale et repart du contenu livré : elle
démarre dans tous les cas.

### L'application elle-même

Le menu **Aide → Rechercher les mises à jour…** interroge l'adresse de
publication et signale l'existence d'une version plus récente ; un bandeau
apparaît alors en haut de la fenêtre avec un lien de téléchargement. Le
remplacement reste manuel : rien n'est téléchargé ni installé automatiquement.

**Aide → Vérifier au démarrage** désactive la vérification automatique. Sur un
poste sans Internet, la vérification échoue en silence et ne gêne pas
l'utilisation.

> Cette fonction reste **inactive tant qu'aucune adresse de publication n'est
> configurée** dans `logos/updates.py` (`MANIFEST_URL`). Pour l'activer, publier
> en HTTPS un fichier JSON de la forme
> `{"version": "1.1.0", "url": "https://…/BDA-1.1.0.zip", "notes": "…"}`
> et renseigner son adresse. Le numéro de version de l'application se change à
> un seul endroit : `logos/version.py`.

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

- Le corpus de prédications est **exclu du paquet par défaut** : son contenu est
  sous copyright (branham.fr / VGR) et ne doit pas être rediffusé. Pour un build
  interne à l'église, l'inclure explicitement :

  ```bash
  BDA_BUNDLE_PREDICATIONS=1 pyinstaller --noconfirm --clean packaging/bda.spec
  ```

  Sans lui, l'exécutable démarre normalement et le mode Prédications affiche
  « non disponible » jusqu'à ce qu'un corpus soit déposé dans `~/.bda/assets/`.
- Au premier lancement, l'exécutable reconstruit la base dans `~/.bda/bda.db`
  (import de la Bible et des prédications) : ce démarrage-là prend quelques
  secondes, les suivants sont immédiats.
- **macOS** : le bundle n'est ni signé ni notarisé, donc Gatekeeper le bloque au
  premier lancement sur une autre machine. La manœuvre dépend de l'origine :
  - copié par clé USB ou réseau local : **clic droit → Ouvrir** suffit ;
  - **téléchargé depuis Internet** : le fichier est mis en quarantaine et, sur
    les versions récentes de macOS (15 et au-delà), le clic droit → Ouvrir ne
    suffit **plus**. Il faut lancer l'appli une première fois, se faire
    refuser, puis aller dans **Réglages Système → Confidentialité et sécurité**
    et cliquer « Ouvrir quand même ».

  La seule façon d'éviter cette manœuvre est de **signer et notariser** le
  bundle (programme développeur Apple, ~99 $/an).
- **Windows** : SmartScreen peut afficher un avertissement pour un exécutable
  non signé — « Informations complémentaires » puis « Exécuter quand même ».
- Si le logo change, régénérer les icônes :
  `python packaging/make_icons.py`.

## Publier une version téléchargeable

### Automatiquement (GitHub Releases)

Une fois le dépôt poussé sur GitHub, `.github/workflows/release.yml` construit
macOS **et** Windows à chaque tag de version, lance les tests, et publie une
release avec les archives, leurs sommes de contrôle et le `latest.json` du
vérificateur de mise à jour :

```bash
git tag v1.0.1 && git push origin v1.0.1
```

Le tag doit correspondre à `logos/version.py`, sinon le workflow s'arrête avant
de construire. C'est aussi ce qui résout le problème Windows : pas besoin d'une
machine Windows, le runner s'en charge.

Pour activer la notification de mise à jour dans l'application, renseigner dans
`logos/updates.py` :

```python
MANIFEST_URL = "https://github.com/<compte>/<depot>/releases/latest/download/latest.json"
```

Cette adresse suit toujours la release la plus récente.

### À la main

```bash
pyinstaller --noconfirm --clean packaging/bda.spec
python packaging/package.py
```

Produit `dist/BDA-<version>-<plateforme>.zip` et sa somme `.sha256`. Sur macOS
l'archive est faite avec `ditto` : un `.app` zippé avec `zip` arrive cassé chez
le destinataire (les liens symboliques des frameworks Qt sont aplatis).

Le destinataire vérifie son téléchargement avec :

```bash
shasum -a 256 -c BDA-1.0.0-macos.zip.sha256
```

### Limites de la distribution publique

- **Le corpus de prédications ne doit pas être publié** : ni dans les archives
  (exclu par défaut), ni dans le dépôt (`logos/assets/predications.json.gz` est
  dans `.gitignore`). Chaque église installe le sien via `~/.bda/assets/`.
- Les exécutables ne sont **pas signés** : voir les avertissements Gatekeeper et
  SmartScreen ci-dessus. C'est le principal frein pour un public non technique.
- Le build macOS de GitHub Actions est **Apple Silicon uniquement**. Pour servir
  aussi les Mac Intel, ajouter un runner `macos-13` à la matrice du workflow.
- Le dépôt n'a **pas de fichier `LICENSE`** : sans licence explicite, personne
  n'est autorisé à réutiliser le code publié.
