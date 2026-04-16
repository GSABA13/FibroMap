"""
Utilitaires de mise en page pour l'export PDF.

Fonctions de conversion coordonnées image → coordonnées ReportLab,
et de calcul de mise en page (fit-in-box, centrage).
Aucun import PyQt6, aucun import de modèles.
"""


# ---------------------------------------------------------------------------
# Constantes de page (A4 Paysage en points PDF)
# 1 mm = 2.8346 points ; 10 mm = 28.35 pt
# ---------------------------------------------------------------------------

PAGE_LARGEUR  = 841.89   # points (297 mm)
PAGE_HAUTEUR  = 595.28   # points (210 mm)
MARGE         = 28.35    # 10 mm en points

# Dimensions du cartouche (en haut à gauche)
CARTOUCHE_LARGEUR = 170.0   # points (~60 mm)
CARTOUCHE_HAUTEUR =  20.0   # points (~7 mm)

# Largeur fixe des bulles call-out en points PDF
LARGEUR_CALLOUT_PT = 115.0

# Surface disponible totale (hors marges de page).
# Le cartouche en-tête est petit (170 pt large) et ne réduit pas la hauteur globale.
# Utilisée par le canvas pour les calculs de proportions.
ZONE_DISPONIBLE_LARG = PAGE_LARGEUR - 2 * MARGE
ZONE_DISPONIBLE_HAUT = PAGE_HAUTEUR - 2 * MARGE

# Espace entre le bord de la page (+ MARGE) et le border ZONE_PLAN.
# C'est dans cet espace que se placent les bulles de légende.
BULLE_MARGE = LARGEUR_CALLOUT_PT + 10.0   # 125 pt sur chaque côté

# Zone plan (cartouche) — border fixe, identique pour toutes les planches.
# Positionné à BULLE_MARGE à l'intérieur de ZONE_DISPONIBLE sur chaque côté.
# L'image du plan est centrée à l'intérieur, sans border supplémentaire.
ZONE_PLAN_X       = MARGE + BULLE_MARGE              # gauche/droite : BULLE_MARGE plein
ZONE_PLAN_Y       = MARGE + BULLE_MARGE / 2          # centré : demi-marge haut et bas
ZONE_PLAN_LARGEUR = ZONE_DISPONIBLE_LARG - 2 * BULLE_MARGE
ZONE_PLAN_HAUTEUR = ZONE_DISPONIBLE_HAUT - BULLE_MARGE   # idem : BULLE_MARGE en tout


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def fit_in_box(img_larg: float, img_haut: float,
               box_larg: float, box_haut: float) -> float:
    """
    Calcule le facteur d'échelle pour faire tenir (img_larg × img_haut)
    dans (box_larg × box_haut) en conservant les proportions.

    Paramètres
    ----------
    img_larg, img_haut : dimensions de l'image source (pixels)
    box_larg, box_haut : dimensions de la boîte cible (points PDF)

    Retourne
    --------
    Facteur d'échelle (float) à appliquer aux dimensions de l'image.
    Retourne 1.0 si l'image a des dimensions nulles.
    """
    if img_larg == 0 or img_haut == 0:
        return 1.0
    echelle_x = box_larg / img_larg
    echelle_y = box_haut / img_haut
    return min(echelle_x, echelle_y)


def image_vers_pdf(px: float, py: float,
                   img_largeur: float, img_hauteur: float,
                   zone_x: float, zone_y: float,
                   zone_larg: float, zone_haut: float,
                   echelle: float) -> tuple[float, float]:
    """
    Convertit un point (px, py) en coordonnées image vers coordonnées PDF.

    Le plan image est rendu dans une zone PDF (zone_x, zone_y, zone_larg, zone_haut)
    en conservant les proportions. L'image est centrée dans la zone.

    L'axe Y est inversé : l'origine de l'image est en haut à gauche (Y vers le bas),
    celle de ReportLab est en bas à gauche (Y vers le haut).

    Paramètres
    ----------
    px, py             : coordonnées du point dans l'image source (pixels)
    img_largeur,
    img_hauteur        : dimensions de l'image source (pixels)
    zone_x, zone_y     : coin bas-gauche de la zone plan dans le PDF (points ReportLab)
    zone_larg,
    zone_haut          : dimensions de la zone plan dans le PDF (points)
    echelle            : facteur pixels → points (calculé par fit_in_box)

    Retourne
    --------
    (x_pdf, y_pdf) en points ReportLab (origine bas-gauche)
    """
    # Décalage de centrage de l'image dans sa zone
    img_larg_pdf = img_largeur * echelle
    img_haut_pdf = img_hauteur * echelle
    offset_x = zone_x + (zone_larg - img_larg_pdf) / 2
    offset_y = zone_y + (zone_haut - img_haut_pdf) / 2

    # Conversion X : direct
    x_pdf = offset_x + px * echelle
    # Conversion Y : inversion de l'axe (image Y=0 en haut, PDF Y=0 en bas)
    y_pdf = offset_y + (img_hauteur - py) * echelle

    return x_pdf, y_pdf


def zone_plan_vers_pdf(
    zone_canvas: tuple,
    canvas_largeur: float,
    canvas_hauteur: float,
    page_largeur: float,
    page_hauteur: float,
) -> tuple:
    """
    Convertit la zone plan (tuple canvas) vers coordonnées reportlab.

    Paramètres
    ----------
    zone_canvas    : (x, y, largeur, hauteur) en pixels canvas Qt (Y↓)
    canvas_largeur : largeur du canvas en pixels
    canvas_hauteur : hauteur du canvas en pixels
    page_largeur   : largeur de la page PDF en points (ex: 841.89)
    page_hauteur   : hauteur de la page PDF en points (ex: 595.28)

    Retourne
    --------
    (x, y, largeur, hauteur) en points PDF (Y↑, origine bas-gauche)
    """
    cx, cy, cw, ch = zone_canvas
    ratio_x = page_largeur / canvas_largeur
    ratio_y = page_hauteur / canvas_hauteur
    x = cx * ratio_x
    # Inverser Y : Qt Y↓, reportlab Y↑
    y = page_hauteur - (cy + ch) * ratio_y
    w = cw * ratio_x
    h = ch * ratio_y
    return (x, y, w, h)
