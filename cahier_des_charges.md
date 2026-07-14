# CAHIER DES CHARGES
## Logiciel de présentation pour l'église (projet type Holyrics)

| | |
|---|---|
| **Version** | 0.1 - Brouillon |
| **Date** | 10 juillet 2026 |
| **Statut** | En cours de rédaction |
| **Rédacteur** | À compléter |
| **Plateforme cible** | Application de bureau (Windows / macOS) |

---

## 1. Contexte et objectifs

### 1.1 Contexte

L'église (ou l'organisation) a besoin d'un outil de présentation permettant d'afficher les paroles de chants, des versets bibliques et d'autres contenus sur un écran de projection (vidéoprojecteur ou écran secondaire), pendant les cultes et événements.

### 1.2 Objectifs du projet

- Remplacer les solutions manuelles (diapositives PowerPoint, transparents) par un outil dédié et rapide à utiliser.
- Permettre à un opérateur de piloter l'affichage projeté depuis un poste de contrôle, sans que l'assemblée ne voie l'interface de gestion.
- Disposer d'une bibliothèque de chants réutilisable et modifiable facilement.
- Offrir une prise en main simple, y compris pour des bénévoles peu expérimentés en informatique.

### 1.3 Objectifs non poursuivis (hors périmètre V1)

- Diffusion en streaming / retransmission vidéo en ligne.
- Gestion multi-utilisateurs / comptes en ligne.
- Version mobile ou web dans un premier temps.

---

## 2. Utilisateurs cibles

| Profil | Besoin principal | Niveau technique |
|---|---|---|
| Opérateur / technicien média | Piloter l'affichage en direct pendant le culte | Faible à moyen |
| Responsable louange | Préparer les chants et l'ordre du culte à l'avance | Faible |
| Administrateur | Gérer la bibliothèque de contenus, les modèles d'affichage | Moyen |

---

## 3. Fonctionnalités

### 3.1 Fonctionnalités essentielles (V1 - MVP)

| # | Fonctionnalité | Description | Priorité |
|---|---|---|---|
| F1 | Gestion des chants | Créer, modifier, supprimer, rechercher des chants (titre + paroles) | Must |
| F2 | Découpage en diapositives | Découper automatiquement les paroles en diapositives (couplet/refrain) | Must |
| F3 | Fenêtre de projection | Afficher le contenu en plein écran, sans bordure, sur l'écran secondaire choisi | Must |
| F4 | Détection des écrans | Détecter automatiquement les écrans connectés et permettre de choisir celui de projection | Must |
| F5 | Navigation en direct | Naviguer entre les diapositives d'un chant pendant la projection (clic, flèches clavier) | Must |
| F6 | Écran noir / masquage | Couper temporairement l'affichage projeté sans perdre le contenu en cours | Must |
| F7 | Réglage de la taille du texte | Adapter la taille de police affichée à l'écran | Should |
| F8 | Sauvegarde locale | Stocker les chants dans une base de données locale (hors ligne) | Must |

### 3.2 Fonctionnalités souhaitables (V2)

| # | Fonctionnalité | Description | Priorité |
|---|---|---|---|
| F9 | Bibliothèque de versets bibliques | Rechercher et afficher des versets par référence (livre, chapitre, verset) | Should |
| F10 | Arrière-plans personnalisés | Image ou vidéo en fond de la diapositive projetée | Should |
| F11 | Ordre du culte / playlist | Enchaîner plusieurs chants et éléments dans un ordre prédéfini | Should |
| F12 | Import/export de chants | Import depuis fichiers texte, export vers d'autres formats | Could |
| F13 | Aperçu en direct pour l'opérateur | Vignette montrant ce qui est actuellement projeté vs la diapo suivante | Should |
| F14 | Raccourcis clavier | Navigation rapide sans souris pendant le culte | Could |

### 3.3 Fonctionnalités envisageables (V3+)

- Télécommande depuis un smartphone (application compagnon ou page web locale).
- Gestion multi-postes en réseau local (un poste prépare, un autre projette).
- Compte-rendu / historique des chants utilisés (statistiques d'usage).

---

## 4. Exigences non fonctionnelles

| Catégorie | Exigence |
|---|---|
| Plateformes | Windows 10/11 et macOS (build natif pour chaque OS) |
| Performance | Changement de diapositive affiché en moins de 200 ms |
| Fiabilité | Fonctionnement 100% hors ligne, aucune dépendance à Internet en fonctionnement normal |
| Ergonomie | Prise en main en moins de 15 minutes pour un bénévole non technique |
| Données | Sauvegarde locale persistante ; pas de perte de données en cas de fermeture inattendue |
| Affichage | Support du multi-écran natif de l'OS, sans configuration manuelle complexe |

---

## 5. Architecture technique (proposition)

### 5.1 Stack technique

- Langage : Python 3.12
- Interface graphique : PySide6 (Qt for Python)
- Base de données : SQLite (fichier local)
- Packaging : PyInstaller pour générer des exécutables Windows (.exe) et macOS (.app)

### 5.2 Composants principaux

- Fenêtre de contrôle : bibliothèque, édition, navigation (visible uniquement par l'opérateur)
- Fenêtre de projection : affichage plein écran sans bordure sur l'écran secondaire
- Module base de données : accès et persistance des chants et contenus

---

## 6. Livrables attendus

- Application installable (Windows et/ou macOS selon les priorités définies)
- Code source commenté
- Documentation utilisateur simplifiée (guide de prise en main)

---

## 7. Planning indicatif

| Phase | Contenu | Durée estimée |
|---|---|---|
| Phase 1 | Socle applicatif : gestion des chants + projection basique (F1-F6, F8) | À définir |
| Phase 2 | Confort d'utilisation : taille de texte, aperçu, raccourcis (F7, F13, F14) | À définir |
| Phase 3 | Versets bibliques, arrière-plans, ordre du culte (F9-F11) | À définir |
| Phase 4 | Packaging, tests, documentation, mise en production | À définir |

---

## 8. Critères d'acceptation (V1)

- L'opérateur peut créer un chant, le découper en diapositives, et le retrouver par recherche.
- La fenêtre de projection s'affiche correctement en plein écran sur l'écran secondaire sélectionné, sans bordure ni barre de titre visible.
- Le changement de diapositive projetée est instantané au clic depuis le poste de contrôle.
- La fonction écran noir masque l'affichage sans perdre le contenu en cours.
- Les données restent disponibles après redémarrage de l'application.

---

## 9. Risques identifiés

| Risque | Impact | Mitigation |
|---|---|---|
| Configuration multi-écran variable selon le matériel | Moyen | Tester sur plusieurs configurations vidéoprojecteur/écran |
| Prise en main difficile pour bénévoles non techniques | Moyen | Interface simplifiée, tests utilisateurs réguliers |
| Absence de sauvegarde/synchronisation distante | Faible | Prévoir export/sauvegarde manuelle de la base de données |

---

## 10. Validation du cahier des charges

Ce document doit être relu et validé par le commanditaire du projet avant le démarrage du développement. Toute évolution du périmètre après validation doit faire l'objet d'un avenant.