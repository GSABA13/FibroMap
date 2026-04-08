# Plan Légendage Amiante — Règles du projet

## Contexte métier
Outil desktop Windows de création de planches de repérage amiante.
L'utilisateur charge un plan (image ou PDF), charge un fichier Excel par chantier,
dessine des formes colorées sur le plan, place des bulles de légende (call-out coudé),
puis exporte un PDF multi-pages (une planche par page).

---

## Stack technique
- **Python 3.11+** sur Windows
- **PyQt6** — interface graphique, canvas de dessin, interactions souris
- **openpyxl** — lecture du fichier Excel (feuille "Prv Am")
- **pdf2image + Pillow** — conversion PDF → image et manipulation d'images
- **reportlab** — génération du PDF final multi-pages
- **PyInstaller** — packaging en .exe Windows

---

## Structure du projet
```
plan-legendage/
├── CLAUDE.md
├── .claude/
│   ├── agents/
│   │   ├── excel-reader.md
│   │   ├── canvas-engine.md
│   │   ├── legende-builder.md
│   │   └── pdf-exporter.md
│   ├── skills/
│   │   ├── metier-amiante/SKILL.md
│   │   ├── pyqt6-patterns/SKILL.md
│   │   └── pdf-export/SKILL.md
│   └── commands/
│       ├── new-feature.md
│       ├── test.md
│       └── build.md
├── src/
│   ├── main.py                  # Point d'entrée, fenêtre principale PyQt6
│   ├── models/
│   │   ├── projet.py            # Modèle de données global (planches, formes, légendes)
│   │   ├── planche.py           # Une planche = 1 plan + N formes + N bulles
│   │   ├── forme.py             # Cercle, Rectangle, Ligne, Polygone, LignesConnectées
│   │   ├── bulle.py             # Call-out coudé : point d'ancrage + position bulle
│   │   └── echantillon.py       # Données issues d'une ligne Excel
│   ├── services/
│   │   ├── excel_reader.py      # Lecture et parsing de la feuille "Prv Am"
│   │   ├── legende_builder.py   # Logique de construction du texte des bulles
│   │   ├── couleur_resolver.py  # Résolution couleur selon résultat amiante
│   │   └── pdf_exporter.py      # Export PDF multi-pages avec reportlab
│   ├── ui/
│   │   ├── main_window.py       # Fenêtre principale, gestion des planches
│   │   ├── canvas_widget.py     # Widget PyQt6 de dessin (plan + formes + bulles)
│   │   ├── toolbar.py           # Barre d'outils (sélection forme, transparence...)
│   │   └── panneau_excel.py     # Panneau liste des échantillons Excel
│   └── utils/
│       ├── pdf_to_image.py      # Conversion PDF → image via pdf2image
│       └── constantes.py        # Couleurs, dimensions fixes, marges
├── tests/
│   ├── test_excel_reader.py
│   ├── test_legende_builder.py
│   └── test_couleur_resolver.py
└── requirements.txt
```

---

## Conventions de code
- Tout le code, commentaires et docstrings sont **en français**
- Nommage des variables et fonctions en **snake_case français** (ex: `largeur_bulle`, `point_ancrage`)
- Nommage des classes en **PascalCase** (ex: `BulleLegende`, `FormePolygone`)
- Chaque module commence par une docstring décrivant son rôle
- Tests unitaires obligatoires pour tous les services métier
- Séparation stricte **UI** (ui/) / **logique métier** (services/) / **modèles** (models/)

---

## Logique métier : Excel → Bulle de légende

### Colonnes de la feuille "Prv Am"
| Lettre | Nom colonne |
|--------|-------------|
| A | Unités |
| B | Zone |
| C | Equipements |
| D | Localisation |
| E | Elément sondé |
| F | Description matériau/produit |
| G | Prélèvement(s)/Sondage(s) |
| H | Date |
| I | Résultat Amiante |
| L | Volume du matériau |
| M | Identifiant photo |
| N | Etage |
| O | Référence Plan |
| P | Marquage sur site |
| Q | N° Prv Laboratoire |
| R | Commentaires |

### Construction du texte de la bulle (3 lignes + mention)
```
Ligne 1 : [G]  (Prélèvement/Sondage)
Ligne 2 : [F]  sauf si F="/" → afficher [I]
               si F contient "Joint" → [F] + " de " + [E]
Ligne 3 : [D]  (Localisation)
──────────────────────────────
Mention : "sa"  si I contient "Absence" OU "pas" OU si I est vide
          "a?"  si I contient "non prélevé"
          "a"   si I contient "Présence"
```

### Couleurs (bordure + texte, fond blanc)
| Condition sur [I] | Couleur |
|-------------------|---------|
| Contient "Absence" OU "pas" OU vide | Vert RGB(18, 169, 30) |
| Contient "non prélevé" | Orange RGB(255, 128, 0) |
| Contient "Présence" | Rouge RGB(255, 0, 0) |

---

## Mise en page PDF (A4 Paysage)

### Structure d'une planche
```
┌─────────────────────────────────────────────┐
│ Planche de repérage: XX   (cartouche HG)    │
├─────────────────────────────────────────────┤
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │                                     │   │
│   │   PLAN (rogné, centré, max place)   │   │
│   │                                     │   │
│   └─────────────────────────────────────┘   │
│                                             │
│   [bulles placées autour ou sur le plan]    │
│                                             │
└─────────────────────────────────────────────┘
```

- Format : A4 Paysage (297 x 210 mm)
- Cartouche "Planche de repérage: XX" en haut à gauche, bordure noire
- Le plan est rogné manuellement par l'utilisateur et occupe le maximum de sa zone
- Les bulles de légende sont placées librement autour du plan (haut, bas, côtés)
- Le PDF final contient **plusieurs pages** (une par planche)

---

## Bulles de légende — call-out coudé

- **Liaison** : call-out coudé (deux segments à angle droit, pas de flèche)
- **Largeur fixe** : à définir (ex: 120px), hauteur automatique selon contenu
- **Texte centré** dans la bulle
- **Interaction** : clic sur le plan pour ancrer le point, puis clic pour poser la bulle
- **Édition** : déplacement du point d'ancrage et de la bulle après placement
- La bulle et la coloration sont **indépendantes** (on peut avoir l'un sans l'autre)

---

## Formes de coloration

Types disponibles : Cercle, Rectangle, Ligne, Lignes connectées, Polygone
- Couleur = même palette que les bulles (vert/orange/rouge)
- Remplissage : plein ou semi-transparent (50% d'opacité)
- **Édition après tracé** : déplacement des points de contrôle, changement de couleur, suppression
- Association à un échantillon Excel : optionnelle et indépendante de la bulle

---

## Ce que Claude NE doit PAS faire
- Ne jamais générer de sauvegarde de projet (pas de format .json ou autre) — l'export PDF est le seul output
- Ne pas implémenter de détection automatique des zones sur le plan (tout est manuel)
- Ne pas utiliser tkinter — uniquement PyQt6
- Ne pas mélanger la logique métier dans les fichiers UI
