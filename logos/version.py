"""
Version de l'application — **source unique**.

Tout le reste en dérive : la fenêtre « À propos », la comparaison faite par
`logos.updates` et les champs `CFBundleShortVersionString` / `CFBundleVersion`
du bundle macOS (lus directement dans ce fichier par `packaging/bda.spec`).

Format attendu : « MAJEUR.MINEUR.CORRECTIF » (comparaison numérique champ par
champ, donc 1.10.0 est bien postérieure à 1.9.0).
"""
__version__ = "1.0.1"
