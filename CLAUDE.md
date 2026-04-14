# Règle de réflexion et d'utilisation des sous agents

1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

    State your assumptions explicitly. If uncertain, ask.
    If multiple interpretations exist, present them - don't pick silently.
    If a simpler approach exists, say so. Push back when warranted.
    If something is unclear, stop. Name what's confusing. Ask.

2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

    No features beyond what was asked.
    No abstractions for single-use code.
    No "flexibility" or "configurability" that wasn't requested.
    No error handling for impossible scenarios.
    If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.
3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:

    Don't "improve" adjacent code, comments, or formatting.
    Don't refactor things that aren't broken.
    Match existing style, even if you'd do it differently.
    If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

    Remove imports/variables/functions that YOUR changes made unused.
    Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.
4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

    "Add validation" → "Write tests for invalid inputs, then make them pass"
    "Fix the bug" → "Write a test that reproduces it, then make it pass"
    "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.


### Séparation stricte des responsabilités
- `ui-ux`, `excel-reader`, `pdf-exporter` : produisent du code, 
   ne lancent JAMAIS pytest
- `code-reviewer` : seul agent autorisé à lancer pytest, 
   invoqué uniquement via /test ou appel explicite

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

## Export PDF — Contrainte métier NON NÉGOCIABLE

Le fichier PDF final est ouvert dans **Adobe Acrobat** pour exploitation ultérieure.
Les formes et bulles DOIVENT être des **annotations PDF natives** (pas dessinées sur le flux de contenu) :

| Objet           | Annotation PDF              |
|-----------------|-----------------------------|
| FormeRect       | `/Subtype /Square`          |
| FormeCercle     | `/Subtype /Circle`          |
| FormeLigne / FormePolygone / FormeLignesConnectees | `/Subtype /PolyLine` |
| BulleLegende    | `/Subtype /FreeText`        |

- Implémentation : utiliser `reportlab.pdfbase.pdfdoc.PDFDictionary` / `PDFArray` / `PDFName` pour construire les objets annotation, puis `canvas._addAnnotation(obj)` pour les injecter dans le /Annots de la page.
- Adobe Acrobat génère automatiquement les /AP (Appearance Streams) à l'ouverture — ne pas les générer manuellement.
- **Ne jamais** remplacer les annotations par du dessin sur le flux de contenu — c'est une régression métier.

---

## Ce que Claude NE doit PAS faire
- Ne jamais générer de sauvegarde de projet (pas de format .json ou autre) — l'export PDF est le seul output
- Ne pas implémenter de détection automatique des zones sur le plan (tout est manuel)
- Ne pas utiliser tkinter — uniquement PyQt6
- Ne pas mélanger la logique métier dans les fichiers UI
- Ne jamais convertir les annotations PDF en dessin sur le flux de contenu
