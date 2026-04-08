"""
Constantes globales de l'application Plan Légendage Amiante.

Ce module centralise toutes les valeurs de référence (couleurs, dimensions,
seuils) afin d'éviter les valeurs magiques dispersées dans le code.
Tout nouveau paramètre configurable doit être ajouté ici.
"""

# ---------------------------------------------------------------------------
# Couleurs RGB utilisées pour les annotations (tuples R, G, B)
# ---------------------------------------------------------------------------

# Vert : zones conformes / OK
COULEUR_VERTE: tuple[int, int, int] = (18, 169, 30)

# Orange : zones à surveiller / avertissement
COULEUR_ORANGE: tuple[int, int, int] = (255, 128, 0)

# Rouge : zones dangereuses / non conformes
COULEUR_ROUGE: tuple[int, int, int] = (255, 0, 0)

# ---------------------------------------------------------------------------
# Transparence (valeur du canal alpha, 0 = invisible, 255 = opaque)
# ---------------------------------------------------------------------------

# Remplissage totalement opaque
ALPHA_PLEIN: int = 255

# Remplissage semi-transparent (superposition lisible avec le plan)
ALPHA_SEMI: int = 128

# ---------------------------------------------------------------------------
# Dimensions des bulles de légende (CallOut)
# ---------------------------------------------------------------------------

# Largeur d'une bulle en pixels
LARGEUR_BULLE: int = 120   # px

# Hauteur d'une ligne de texte dans la bulle
HAUTEUR_LIGNE: int = 14    # px

# Marge intérieure (padding) de la bulle
PADDING_BULLE: int = 12    # px

# ---------------------------------------------------------------------------
# Poignées de sélection (handles de redimensionnement)
# ---------------------------------------------------------------------------

# Côté du carré représentant une poignée
TAILLE_POIGNEE: int = 6    # px

# ---------------------------------------------------------------------------
# Rendu des traits
# ---------------------------------------------------------------------------

# Épaisseur par défaut des contours dessinés sur le canvas
EPAISSEUR_TRAIT: float = 1.5   # px

# Épaisseurs de trait secondaires
EPAISSEUR_POIGNEE: float = 1.0    # Contour des poignées de sélection (px)
EPAISSEUR_GHOST: float = 1.0      # Contour du tracé fantôme en cours (px)

# ---------------------------------------------------------------------------
# Tolérance de sélection
# ---------------------------------------------------------------------------

# Distance maximale en pixels pour sélectionner une forme au clic
TOLERANCE_HIT: int = 5            # Distance max (px) pour sélectionner une forme

# ---------------------------------------------------------------------------
# Historique des actions (undo / redo)
# ---------------------------------------------------------------------------

# Nombre maximal d'états mémorisés dans la pile d'historique
TAILLE_HISTORIQUE: int = 20

# --- Conversion PDF ---
DPI_CONVERSION_PDF: int = 150      # Résolution de conversion PDF → image

# --- Canvas ---
MARGE_PLAN: int = 10               # Marge autour du plan dans le canvas (px)
# Couleur de fond du canvas — tuple RGB (232, 232, 232) ≈ gris clair
COULEUR_FOND_CANVAS: tuple[int, int, int] = (232, 232, 232)
# Couleur du texte d'invite affiché quand aucun plan n'est chargé
COULEUR_TEXTE_INVITE: tuple[int, int, int] = (136, 136, 136)

# Zoom
ZOOM_MIN: float = 0.10             # Facteur de zoom minimal (10%)
ZOOM_MAX: float = 5.00             # Facteur de zoom maximal (500%)
ZOOM_FACTEUR_MOLETTE: float = 1.15 # Facteur appliqué par cran de molette
ZOOM_DEFAUT: float = 1.0           # Facteur de zoom par défaut (100%)

# --- Fenêtre principale ---
LARGEUR_FENETRE: int = 1200        # Largeur initiale de la fenêtre
HAUTEUR_FENETRE: int = 700         # Hauteur initiale de la fenêtre
LARGEUR_PANNEAU_PLANCHES: int = 150  # Largeur initiale du panneau planches
LARGEUR_PANNEAU_EXCEL: int = 200   # Largeur initiale du panneau Excel

# --- Panneaux ---
MARGE_PANNEAU: int = 4             # Marges et espacement des panneaux latéraux

# --- Toolbar ---
TAILLE_ICONE_TOOLBAR: int = 24     # Taille des icônes dessinées dans la barre d'outils (px)
