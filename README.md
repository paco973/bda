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

## Créer un exécutable (Windows/macOS)

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Logos Tabernacle" main.py
```

L'application empaquetée se trouve ensuite dans `dist/`.
