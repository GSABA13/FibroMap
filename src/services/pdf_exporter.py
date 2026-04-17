"""
Export PDF multi-pages des planches de repérage amiante.

Génère un fichier PDF A4 Paysage avec une page par planche.
Chaque page contient :
  - Un cartouche en haut à gauche ("Planche de repérage : XX")
  - Le plan rogné et centré dans sa zone, avec bordure noire
  - Les formes colorées comme annotations PDF natives (Square, Circle, PolyLine, Polygon)
  - Les bulles de légende comme annotations PDF natives (FreeText callout natif via /CL)

Les annotations sont construites via les objets natifs reportlab
(PDFDictionary, PDFArray, PDFName, PDFString) afin d'être correctement
sérialisées et référencées dans le tableau /Annots de chaque page.
Adobe Acrobat génère les /AP (Appearance Streams) automatiquement.

Aucun import PyQt6 dans ce module.
"""

import logging
import math
import os
from io import BytesIO

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfdoc as rl_pdfdoc
from reportlab.pdfgen import canvas as rl_canvas

from src.models.bulle import BulleLegende
from src.models.forme import (
    FormeBase,
    FormeCercle,
    FormeLigne,
    FormeLignesConnectees,
    FormePolygone,
    FormeRect,
)
from src.models.planche import Planche
from src.utils.pdf_utils import (
    CARTOUCHE_HAUTEUR,
    CARTOUCHE_LARGEUR,
    LARGEUR_CALLOUT_PT,
    MARGE,
    PAGE_HAUTEUR,
    PAGE_LARGEUR,
    ZONE_PLAN_HAUTEUR,
    ZONE_PLAN_LARGEUR,
    ZONE_PLAN_X,
    ZONE_PLAN_Y,
    fit_in_box,
    image_vers_pdf,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers d'annotation PDF natifs (objets reportlab — sérialisation correcte)
# ---------------------------------------------------------------------------

def _annot_square(c: rl_canvas.Canvas,
                  x1: float, y1: float, x2: float, y2: float,
                  r_f: float, g_f: float, b_f: float,
                  opacite: float,
                  epaisseur_pt: float = 3.0) -> None:
    """
    Crée une annotation /Square via les objets reportlab natifs.

    Utilise PDFDictionary / PDFArray / PDFName afin que reportlab
    sérialise l'objet comme référence indirecte correctement inscrite
    dans le tableau /Annots de la page.

    Paramètres
    ----------
    c              : canvas ReportLab courant
    x1, y1, x2, y2: coins opposés du rectangle (points PDF, Y↑)
    r_f, g_f, b_f : composantes RGB normalisées [0, 1]
    opacite        : transparence (1.0 = plein, 0.5 = semi-transparent)
    """
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)

    d = rl_pdfdoc.PDFDictionary()
    d['Type']    = rl_pdfdoc.PDFName('Annot')
    d['Subtype'] = rl_pdfdoc.PDFName('Square')
    d['Rect']    = rl_pdfdoc.PDFArray([xmin, ymin, xmax, ymax])
    d['C']       = rl_pdfdoc.PDFArray([r_f, g_f, b_f])   # couleur bordure
    d['IC']      = rl_pdfdoc.PDFArray([r_f, g_f, b_f])   # couleur remplissage
    d['CA']      = opacite
    d['BS']      = rl_pdfdoc.PDFDictionary({'W': epaisseur_pt})
    d['F']       = 4  # Print flag
    c._addAnnotation(d)


def _annot_circle(c: rl_canvas.Canvas,
                  cx: float, cy: float, rayon: float,
                  r_f: float, g_f: float, b_f: float,
                  opacite: float,
                  epaisseur_pt: float = 3.0) -> None:
    """
    Crée une annotation /Circle via les objets reportlab natifs.

    Paramètres
    ----------
    c              : canvas ReportLab courant
    cx, cy         : centre du cercle (points PDF, Y↑)
    rayon          : rayon en points PDF
    r_f, g_f, b_f : composantes RGB normalisées [0, 1]
    opacite        : transparence (1.0 = plein, 0.5 = semi-transparent)
    """
    d = rl_pdfdoc.PDFDictionary()
    d['Type']    = rl_pdfdoc.PDFName('Annot')
    d['Subtype'] = rl_pdfdoc.PDFName('Circle')
    d['Rect']    = rl_pdfdoc.PDFArray([cx - rayon, cy - rayon,
                                       cx + rayon, cy + rayon])
    d['C']       = rl_pdfdoc.PDFArray([r_f, g_f, b_f])
    d['IC']      = rl_pdfdoc.PDFArray([r_f, g_f, b_f])
    d['CA']      = opacite
    d['BS']      = rl_pdfdoc.PDFDictionary({'W': epaisseur_pt})
    d['F']       = 4
    c._addAnnotation(d)


def _annot_polyline(c: rl_canvas.Canvas,
                    points_pdf: list[tuple[float, float]],
                    r_f: float, g_f: float, b_f: float,
                    opacite: float,
                    epaisseur_pt: float = 3.0) -> None:
    """
    Crée une annotation /PolyLine via les objets reportlab natifs.

    Les sommets sont aplatis dans un tableau [x1, y1, x2, y2, ...].
    Si moins de 2 points, l'annotation est ignorée silencieusement.

    Paramètres
    ----------
    c          : canvas ReportLab courant
    points_pdf : liste de tuples (x, y) en points PDF (Y↑)
    r_f, g_f, b_f : composantes RGB normalisées [0, 1]
    opacite    : transparence CA
    """
    if len(points_pdf) < 2:
        return

    xs = [p[0] for p in points_pdf]
    ys = [p[1] for p in points_pdf]

    # Aplatissement des sommets pour le champ /Vertices
    sommets_plats: list[float] = []
    for x, y in points_pdf:
        sommets_plats.extend([x, y])

    d = rl_pdfdoc.PDFDictionary()
    d['Type']     = rl_pdfdoc.PDFName('Annot')
    d['Subtype']  = rl_pdfdoc.PDFName('PolyLine')
    d['Rect']     = rl_pdfdoc.PDFArray([min(xs), min(ys), max(xs), max(ys)])
    d['Vertices'] = rl_pdfdoc.PDFArray(sommets_plats)
    d['C']        = rl_pdfdoc.PDFArray([r_f, g_f, b_f])
    d['CA']       = opacite
    d['BS']       = rl_pdfdoc.PDFDictionary({'W': epaisseur_pt})
    d['F']        = 4
    c._addAnnotation(d)


def _annot_polygon(c: rl_canvas.Canvas,
                   points_pdf: list[tuple[float, float]],
                   r_f: float, g_f: float, b_f: float,
                   opacite: float,
                   epaisseur_pt: float = 3.0) -> None:
    """
    Annotation /Polygon via objets reportlab natifs (PDF 1.6+).

    Contrairement à /PolyLine, /Polygon est un polygone fermé : la visionneuse
    ferme automatiquement le contour sans qu'il faille répéter le premier point.
    Si moins de 2 points, l'annotation est ignorée silencieusement.

    Paramètres
    ----------
    c          : canvas ReportLab courant
    points_pdf : liste de tuples (x, y) en points PDF (Y↑)
    r_f, g_f, b_f : composantes RGB normalisées [0, 1]
    opacite    : transparence CA
    """
    if len(points_pdf) < 2:
        return

    xs = [p[0] for p in points_pdf]
    ys = [p[1] for p in points_pdf]

    # Aplatissement des sommets pour le champ /Vertices
    vertices_flat: list[float] = []
    for x, y in points_pdf:
        vertices_flat.extend([x, y])

    d = rl_pdfdoc.PDFDictionary()
    d['Type']     = rl_pdfdoc.PDFName('Annot')
    d['Subtype']  = rl_pdfdoc.PDFName('Polygon')
    d['Rect']     = rl_pdfdoc.PDFArray([min(xs), min(ys), max(xs), max(ys)])
    d['Vertices'] = rl_pdfdoc.PDFArray(vertices_flat)
    d['C']        = rl_pdfdoc.PDFArray([r_f, g_f, b_f])
    d['IC']       = rl_pdfdoc.PDFArray([r_f, g_f, b_f])   # remplissage
    d['CA']       = opacite
    d['BS']       = rl_pdfdoc.PDFDictionary({'W': epaisseur_pt})
    d['F']        = 4
    c._addAnnotation(d)


def _annot_freetext_callout(c: rl_canvas.Canvas,
                             bx: float, by: float, bw: float, bh: float,
                             anc_x: float, anc_y: float,
                             pied_x: float, pied_y: float,
                             bord_x: float, bord_y: float,
                             ligne1: str, ligne2: str, ligne3: str, mention: str,
                             r_f: float, g_f: float, b_f: float) -> None:
    """
    Annotation de légende call-out = deux annotations superposées.

    Stratégie deux couches (seule solution fiable pour fond transparent dans Acrobat) :
    ─ Couche 1 : /FreeText avec /C [] (couleur vide = Acrobat génère un /AP sans remplissage)
      Porte le texte, le call-out natif (/CL, /IT FreeTextCallout) et la pastille (/LE).
    ─ Couche 2 : /Square sans /IC (pas de remplissage), même /Rect que le FreeText.
      Dessine uniquement la bordure colorée de la bulle.

    Les 3 points du call-out /CL (dans l'ordre PDF) :
      [anc_x, anc_y,   <- point d'ancrage (pointe)
       pied_x, pied_y, <- coude horizontal
       bord_x, bord_y] <- sortie sur le bord de la bulle
    """
    # Corps du texte (lignes 1, 2, 3)
    corps = [t for t in (ligne1, ligne2, ligne3) if t and t.strip()]
    if not corps and not (mention and mention.strip()):
        return

    # Séparateur ASCII + mention (pas de caractère Unicode étendu pour Helvetica)
    if mention and mention.strip():
        separateur = "- " * 8   # tirets ASCII centrés visuellement
        if corps:
            contenu = "\r".join(corps) + "\r" + separateur.strip() + "\r" + mention
        else:
            contenu = separateur.strip() + "\r" + mention
    else:
        contenu = "\r".join(corps)

    # Default Appearance : Helvetica 8pt, couleur de texte = couleur bulle
    da_str = f"/Helvetica 8 Tf {r_f:.4f} {g_f:.4f} {b_f:.4f} rg"

    # Default Style String CSS-like : centrage + taille police
    r_hex = int(r_f * 255)
    g_hex = int(g_f * 255)
    b_hex = int(b_f * 255)
    ds_str = (
        f"font: Helvetica,sans-serif 8.0pt; text-align:center; "
        f"color:#{r_hex:02x}{g_hex:02x}{b_hex:02x}"
    )

    # --- Couche 1 : FreeText pour le texte + géométrie du call-out ---
    # /C [] = tableau vide → Acrobat génère un /AP sans remplissage (fond transparent)
    ft = rl_pdfdoc.PDFDictionary()
    ft['Type']     = rl_pdfdoc.PDFName('Annot')
    ft['Subtype']  = rl_pdfdoc.PDFName('FreeText')
    ft['IT']       = rl_pdfdoc.PDFName('FreeTextCallout')
    ft['Rect']     = rl_pdfdoc.PDFArray([bx, by, bx + bw, by + bh])
    ft['CL']       = rl_pdfdoc.PDFArray([anc_x, anc_y, pied_x, pied_y, bord_x, bord_y])
    ft['Contents'] = rl_pdfdoc.PDFString(contenu)
    ft['DA']       = rl_pdfdoc.PDFString(da_str)
    ft['DS']       = rl_pdfdoc.PDFString(ds_str)
    ft['Q']        = 1    # 0=gauche, 1=centré, 2=droite
    ft['C']        = rl_pdfdoc.PDFArray([])   # couleur vide → fond transparent dans Acrobat
    ft['BS']       = rl_pdfdoc.PDFDictionary({'W': 2.0})  # épaisseur trait call-out
    ft['F']        = 4
    ft['LE']       = rl_pdfdoc.PDFArray([rl_pdfdoc.PDFName('Circle'),
                                          rl_pdfdoc.PDFName('None')])
    c._addAnnotation(ft)


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def exporter_pdf(chemin_sortie: str, planches: list[Planche]) -> None:
    """
    Génère le fichier PDF multi-pages à partir d'une liste de planches.

    Seules les planches avec un plan_chemin non None sont incluses.
    Un avertissement est journalisé pour les planches ignorées.

    Paramètres
    ----------
    chemin_sortie : chemin absolu du fichier PDF à créer
    planches      : liste des planches dans l'ordre d'export

    Lève
    ----
    FileNotFoundError : si le fichier image d'une planche est introuvable
    """
    c = rl_canvas.Canvas(chemin_sortie, pagesize=landscape(A4))

    planches_valides  = [p for p in planches if p.plan_chemin is not None]
    planches_ignorees = [p for p in planches if p.plan_chemin is None]

    for planche in planches_ignorees:
        logger.warning(
            "Planche %s ignorée : aucun plan chargé (plan_chemin est None).",
            planche.id,
        )

    if not planches_valides:
        logger.warning("Aucune planche avec plan à exporter. Fichier PDF non créé.")
        return

    for planche in planches_valides:
        _dessiner_planche(c, planche)
        c.showPage()

    c.save()
    logger.info(
        "PDF exporté : %s (%d planche(s))",
        chemin_sortie,
        len(planches_valides),
    )


# ---------------------------------------------------------------------------
# Rendu d'une planche (une page)
# ---------------------------------------------------------------------------

def _dessiner_planche(c: rl_canvas.Canvas, planche: Planche) -> None:
    """
    Orchestre le rendu complet d'une page pour une planche donnée.

    Étapes :
    1. Cartouche (dessiné sur le flux de contenu)
    2. Chargement de l'image (avec gestion d'un plan au format PDF)
    3. Zone plan fixe définie par les constantes ZONE_PLAN_* de pdf_utils
    4. Calcul de l'échelle et dessin du plan centré dans sa zone
    5. Formes colorées → annotations PDF natives (_annoter_forme)
    6. Bulles de légende → annotations PDF natives (_annoter_bulle)
    """
    # --- Cartouche ---
    _dessiner_cartouche(c, planche)

    # --- Vérification de l'existence du fichier ---
    chemin = planche.plan_chemin
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"Le fichier plan est introuvable : {chemin!r}"
        )

    # --- Chargement de l'image ---
    extension = os.path.splitext(chemin)[1].lower()
    if extension == ".pdf":
        # Conversion PDF → image PIL via pdf2image (première page uniquement)
        from pdf2image import convert_from_path  # import local évitant une dépendance globale
        from src.utils.pdf_to_image import _chemin_poppler
        pages = convert_from_path(chemin, dpi=150, poppler_path=_chemin_poppler())
        img_pil = pages[0]
    else:
        img_pil = Image.open(chemin).convert("RGBA")

    img_largeur, img_hauteur = img_pil.size

    # --- Zone plan fixe : identique pour toutes les planches ---
    # ZONE_PLAN = cartouche (border affiché). L'image se centre à l'intérieur.
    # Les bulles se placent entre ZONE_PLAN et le bord de la page (BULLE_MARGE).
    zone_x    = ZONE_PLAN_X
    zone_y    = ZONE_PLAN_Y
    zone_larg = ZONE_PLAN_LARGEUR
    zone_haut = ZONE_PLAN_HAUTEUR
    logger.debug(
        "Planche %s : zone plan fixe (%.1f, %.1f, %.1f×%.1f)",
        planche.id, zone_x, zone_y, zone_larg, zone_haut,
    )

    # --- Calcul de l'échelle pour tenir dans la zone plan ---
    echelle = fit_in_box(img_largeur, img_hauteur, zone_larg, zone_haut)

    # --- Dessin du plan (flux de contenu — intentionnel) ---
    _dessiner_plan(c, img_pil, zone_x, zone_y, zone_larg, zone_haut,
                   echelle, img_largeur, img_hauteur)

    # --- Formes colorées → annotations PDF natives ---
    for forme in planche.formes:
        _annoter_forme(c, forme, img_largeur, img_hauteur,
                       zone_x, zone_y, zone_larg, zone_haut, echelle)

    # --- Bulles de légende → annotations PDF natives ---
    for bulle in planche.bulles:
        _annoter_bulle(c, bulle, img_largeur, img_hauteur,
                       zone_x, zone_y, zone_larg, zone_haut, echelle)


# ---------------------------------------------------------------------------
# Cartouche (dessiné sur le flux de contenu — intentionnel)
# ---------------------------------------------------------------------------

def _dessiner_cartouche(c: rl_canvas.Canvas, planche: Planche) -> None:
    """
    Dessine le cartouche "Planche de repérage : XX" en haut à gauche.

    Le cartouche est dessiné sur le flux de contenu (pas annotation) car il
    fait partie de la mise en page fixe de la planche.
    Fond blanc, bordure noire 1pt, texte Helvetica-Bold 10pt centré verticalement.
    """
    x = MARGE
    y = PAGE_HAUTEUR - MARGE - CARTOUCHE_HAUTEUR

    # Fond blanc
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y, CARTOUCHE_LARGEUR, CARTOUCHE_HAUTEUR, fill=1, stroke=0)

    # Bordure noire 1pt
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.rect(x, y, CARTOUCHE_LARGEUR, CARTOUCHE_HAUTEUR, fill=0, stroke=1)

    # Texte centré verticalement dans le cartouche
    # Descente approximative de la police Helvetica 10pt : ~3.5 pt
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 10)
    texte = f"Planche de repérage : {planche.numero:02d}"
    centre_x = x + CARTOUCHE_LARGEUR / 2
    centre_y = y + CARTOUCHE_HAUTEUR / 2 - 3.5
    c.drawCentredString(centre_x, centre_y, texte)


# ---------------------------------------------------------------------------
# Zone plan (dessinée sur le flux de contenu — intentionnel)
# ---------------------------------------------------------------------------

def _dessiner_plan(c: rl_canvas.Canvas, img_pil: Image.Image,
                   zone_x: float, zone_y: float,
                   zone_larg: float, zone_haut: float,
                   echelle: float,
                   img_larg: float, img_haut: float) -> None:
    """
    Dessine le plan (image PIL déjà croppée) centré dans sa zone, avec bordure noire.

    La bordure de la zone complète est dessinée avant l'image, puis l'image
    est placée centrée à l'intérieur en conservant ses proportions.
    Le plan est dessiné sur le flux de contenu (pas annotation).

    Paramètres
    ----------
    c              : canvas ReportLab
    img_pil        : image PIL déjà croppée
    zone_x, zone_y : coin bas-gauche de la zone plan (points PDF, origine ReportLab)
    zone_larg,
    zone_haut      : dimensions de la zone plan en points PDF
    echelle        : facteur pixels → points (issu de fit_in_box)
    img_larg,
    img_haut       : dimensions de l'image source après crop (pixels)
    """
    # Border du cartouche (ZONE_PLAN — identique pour toutes les planches)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.rect(zone_x, zone_y, zone_larg, zone_haut, fill=0, stroke=1)

    # Dimensions de l'image en points PDF après mise à l'échelle
    img_larg_pdf = img_larg * echelle
    img_haut_pdf = img_haut * echelle

    # Centrage de l'image dans ZONE_PLAN (pas de border supplémentaire autour de l'image)
    offset_x = zone_x + (zone_larg - img_larg_pdf) / 2
    offset_y = zone_y + (zone_haut - img_haut_pdf) / 2

    # Redimensionnement à 150 DPI par rapport à la taille d'affichage PDF.
    # Évite d'embarquer une image pleine résolution (ex: 3000×2000 px) dans le PDF
    # alors qu'elle n'est affichée qu'à ~700×500 pt → réduction massive du poids.
    DPI_CIBLE = 150
    cible_w = max(1, round(img_larg_pdf / 72 * DPI_CIBLE))
    cible_h = max(1, round(img_haut_pdf / 72 * DPI_CIBLE))
    if img_pil.width > cible_w or img_pil.height > cible_h:
        img_pil = img_pil.resize((cible_w, cible_h), Image.LANCZOS)

    # JPEG (compression avec perte, x5–x10 vs PNG pour des scans/photos)
    # Conversion RGB obligatoire (JPEG ne supporte pas l'alpha)
    if img_pil.mode in ("RGBA", "LA", "P"):
        fond = Image.new("RGB", img_pil.size, (255, 255, 255))
        fond.paste(img_pil, mask=img_pil.split()[-1] if img_pil.mode in ("RGBA", "LA") else None)
        img_pil = fond
    elif img_pil.mode != "RGB":
        img_pil = img_pil.convert("RGB")

    buf = BytesIO()
    img_pil.save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)

    c.drawImage(
        ImageReader(buf),
        offset_x,
        offset_y,
        width=img_larg_pdf,
        height=img_haut_pdf,
    )


# ---------------------------------------------------------------------------
# Formes colorées → annotations PDF natives
# ---------------------------------------------------------------------------

def _annoter_forme(c: rl_canvas.Canvas, forme: FormeBase,
                   img_larg: float, img_haut: float,
                   zone_x: float, zone_y: float,
                   zone_larg: float, zone_haut: float,
                   echelle: float) -> None:
    """
    Génère une annotation PDF native pour une forme colorée.

    Mapping :
      FormeRect             → annotation /Square   (_annot_square)
      FormeCercle           → annotation /Circle   (_annot_circle)
      FormeLigne            → annotation /PolyLine 2 points (_annot_polyline)
      FormePolygone         → annotation /Polygon  N points (_annot_polygon)
      FormeLignesConnectees → annotation /PolyLine N points (_annot_polyline)

    Les coordonnées image (origine haut-gauche, Y↓) sont converties en
    coordonnées PDF (origine bas-gauche, Y↑) via image_vers_pdf.

    Paramètres
    ----------
    c              : canvas ReportLab
    forme          : instance d'une sous-classe de FormeBase
    img_larg,
    img_haut       : dimensions de l'image source après crop (pixels)
    zone_x, zone_y : coin bas-gauche de la zone plan dans le PDF (points)
    zone_larg,
    zone_haut      : dimensions de la zone plan dans le PDF (points)
    echelle        : facteur pixels → points
    """
    # Raccourci local pour la conversion de coordonnées
    def conv(px: float, py: float) -> tuple[float, float]:
        return image_vers_pdf(
            px, py, img_larg, img_haut,
            zone_x, zone_y,
            zone_larg, zone_haut, echelle,
        )

    r, g, b = forme.couleur_rgb
    r_f, g_f, b_f = r / 255.0, g / 255.0, b / 255.0
    # alpha : 255 = plein (opacité 1.0), 128 = semi-transparent (opacité 0.5)
    opacite = 1.0 if forme.alpha >= 200 else 0.5

    # --- Rectangle ---
    if isinstance(forme, FormeRect):
        if len(forme.points) < 2:
            logger.debug("FormeRect ignorée : moins de 2 points (id=%s).", forme.id)
            return
        x1, y1 = conv(*forme.points[0])
        x2, y2 = conv(*forme.points[1])
        _annot_square(c, x1, y1, x2, y2, r_f, g_f, b_f, opacite, forme.epaisseur)

    # --- Cercle ---
    elif isinstance(forme, FormeCercle):
        if len(forme.points) < 2:
            logger.debug("FormeCercle ignorée : moins de 2 points (id=%s).", forme.id)
            return
        cx, cy = conv(*forme.points[0])
        bx, by = conv(*forme.points[1])
        # Le rayon est la distance euclidienne entre le centre et le point bord
        rayon = math.sqrt((bx - cx) ** 2 + (by - cy) ** 2)
        _annot_circle(c, cx, cy, rayon, r_f, g_f, b_f, opacite, forme.epaisseur)

    # --- Ligne simple ---
    elif isinstance(forme, FormeLigne):
        if len(forme.points) < 2:
            logger.debug("FormeLigne ignorée : moins de 2 points (id=%s).", forme.id)
            return
        pts = [conv(*pt) for pt in forme.points[:2]]
        _annot_polyline(c, pts, r_f, g_f, b_f, opacite, forme.epaisseur)

    # --- Polygone fermé — annotation /Polygon native (PDF 1.6+) ---
    elif isinstance(forme, FormePolygone):
        if len(forme.points) < 2:
            logger.debug("FormePolygone ignorée : moins de 2 points (id=%s).", forme.id)
            return
        # La fermeture est implicite dans /Polygon : on ne répète pas le premier point
        pts_pdf = [conv(*pt) for pt in forme.points]
        _annot_polygon(c, pts_pdf, r_f, g_f, b_f, opacite, forme.epaisseur)

    # --- Lignes connectées ---
    elif isinstance(forme, FormeLignesConnectees):
        if len(forme.points) < 2:
            logger.debug(
                "FormeLignesConnectees ignorée : moins de 2 points (id=%s).", forme.id
            )
            return
        pts = [conv(*pt) for pt in forme.points]
        _annot_polyline(c, pts, r_f, g_f, b_f, opacite, forme.epaisseur)

    else:
        logger.debug("Type de forme inconnu ignoré : %s.", type(forme).__name__)


# ---------------------------------------------------------------------------
# Bulles de légende → annotations PDF natives
# ---------------------------------------------------------------------------

def _annoter_bulle(c: rl_canvas.Canvas, bulle: BulleLegende,
                   img_larg: float, img_haut: float,
                   zone_x: float, zone_y: float,
                   zone_larg: float, zone_haut: float,
                   echelle: float) -> None:
    """
    Génère l'annotation PDF native pour une bulle call-out.

    La bulle n'est produite que si un échantillon est associé (conformément
    à la règle métier : pas de texte = pas de bulle).

    Composant produit :
      - Trois annotations superposées via _annot_freetext_callout :
        1. /FreeText fond blanc (texte centré, bordure invisible)
        2. /Square bordure colorée (/IC [] transparent explicite)
        3. /PolyLine call-out coudé + pastille /LE Circle à l'ancrage

    Structure du call-out (/CL, 3 points) :
      [anc_x, anc_y,   <- point d'ancrage (pointe du call-out)
       pied_x, pied_y, <- coude du call-out
       bord_x, bord_y] <- point de sortie sur le bord de la bulle

    Paramètres
    ----------
    c              : canvas ReportLab
    bulle          : instance BulleLegende
    img_larg,
    img_haut       : dimensions de l'image source après crop (pixels)
    zone_x, zone_y : coin bas-gauche de la zone plan dans le PDF (points)
    zone_larg,
    zone_haut      : dimensions de la zone plan dans le PDF (points)
    echelle        : facteur pixels → points
    """
    # Si pas d'échantillon associé, on ne produit aucune annotation
    if bulle.echantillon is None:
        return

    ech = bulle.echantillon
    r, g, b = bulle.couleur_rgb
    r_f, g_f, b_f = r / 255.0, g / 255.0, b / 255.0

    # --- Textes extraits de l'échantillon (avant le calcul de bh) ---
    ligne1  = ech.texte_ligne1 if ech.texte_ligne1 else ""
    ligne2  = ech.texte_ligne2 if ech.texte_ligne2 else ""
    ligne3  = ech.texte_ligne3 if ech.texte_ligne3 else ""
    mention = ech.mention      if ech.mention      else ""

    # --- Conversion de l'ancrage (coords image → PDF) ---
    anc_x, anc_y = image_vers_pdf(
        bulle.ancrage[0], bulle.ancrage[1],
        img_larg, img_haut,
        zone_x, zone_y,
        zone_larg, zone_haut, echelle,
    )

    # --- Conversion du coin supérieur gauche de la bulle (coords image → PDF) ---
    # bulle.position = (x_img, y_img) coin haut-gauche en coordonnées image (Y↓)
    # Après conversion, by_hg est la coordonnée Y du haut de la bulle en PDF (Y↑)
    bx, by_hg = image_vers_pdf(
        bulle.position[0], bulle.position[1],
        img_larg, img_haut,
        zone_x, zone_y,
        zone_larg, zone_haut, echelle,
    )

    # --- Largeur fixe en points PDF (importée depuis pdf_utils) ---
    bw = LARGEUR_CALLOUT_PT

    # --- Hauteur de la bulle calculée depuis le contenu PDF réel ---
    # Evite les lignes vides dues à l'écart entre l'interligne canvas (×1.4) et
    # l'interligne Acrobat pour Helvetica 8pt (≈ 9.6 pt = 8 × 1.2).
    # Le séparateur "- - -" est compté explicitement (absent de bulle.hauteur()).
    # Word-wrap : Helvetica 8pt ≈ 4.4 pt/glyphe moyen (55 % de la taille police).
    # 4.5 donnait 25 chars/ligne et sur-estimait les longs textes (ex. "a?").
    _chars_par_ligne_pdf = max(1, int(LARGEUR_CALLOUT_PT / 4.4))  # ≈ 26
    _nb_lignes_pdf = sum(
        math.ceil(len(t) / _chars_par_ligne_pdf)
        for t in (ligne1, ligne2, ligne3)
        if t and t.strip()
    )
    if mention and mention.strip():
        _nb_lignes_pdf += 2  # +1 séparateur "- - -", +1 mention
    bh = max(10.0, _nb_lignes_pdf * 9.6 + 4.0)

    # by_hg = haut de la bulle en PDF (Y↑) → coin bas-gauche ReportLab = by_hg - bh
    by = by_hg - bh

    # --- Clamp : la bulle se positionne par rapport aux bords du cartouche (ZONE_PLAN) ---
    # Cohérent avec l'outil canvas où les bulles sont placées par rapport au cartouche,
    # non par rapport au bord de l'image (qui peut être plus petite que la zone plan).
    GAP_PLAN = 5.0  # Espacement entre la bulle et le bord du cartouche (points PDF, ~1,8 mm)

    # Axe X — snap relatif au bord du cartouche (zone_x / zone_x + zone_larg)
    if bx < zone_x:
        # Bulle à gauche : snapée à exactement GAP_PLAN du bord gauche du cartouche
        bx = max(0.0, zone_x - bw - GAP_PLAN)
    elif bx >= zone_x + zone_larg:
        # Bulle à droite : snapée à exactement GAP_PLAN du bord droit du cartouche
        bx = min(PAGE_LARGEUR - bw, zone_x + zone_larg + GAP_PLAN)
    else:
        bx = max(0.0, min(bx, PAGE_LARGEUR - bw))

    # Axe Y — snap relatif au bord du cartouche (zone_y / zone_y + zone_haut)
    if by + bh <= zone_y:
        # Bulle en dessous du plan : snapée à GAP_PLAN sous le bord bas du cartouche
        by = max(0.0, min(by, zone_y - bh - GAP_PLAN))
    elif by >= zone_y + zone_haut:
        # Bulle au-dessus du plan : snapée à GAP_PLAN au-dessus du bord haut du cartouche
        by = max(zone_y + zone_haut + GAP_PLAN, min(by, PAGE_HAUTEUR - bh))
    else:
        by = max(0.0, min(by, PAGE_HAUTEUR - bh))

    # Recalcul après clamp (centre_y_bulle dépend de by)
    centre_y_bulle = by + bh / 2

    # --- Longueur du pied en points PDF ---
    pied_pdf = bulle.pied_longueur * echelle

    # --- Détermination du côté de sortie du pied (gauche ou droit) ---
    # Recalcul après clamp de bx (bord_x et pied_x dépendent de bx)
    if anc_x < bx + bw / 2:
        # Ancrage à gauche du centre de la bulle : pied sort à gauche
        bord_x = bx
        pied_x = bx - pied_pdf
    else:
        # Ancrage à droite du centre de la bulle : pied sort à droite
        bord_x = bx + bw
        pied_x = bx + bw + pied_pdf

    # --- Trois annotations superposées (fond blanc + bordure + call-out) ---
    _annot_freetext_callout(
        c,
        bx=bx, by=by, bw=bw, bh=bh,
        anc_x=anc_x, anc_y=anc_y,
        pied_x=pied_x, pied_y=centre_y_bulle,
        bord_x=bord_x, bord_y=centre_y_bulle,
        ligne1=ligne1, ligne2=ligne2, ligne3=ligne3, mention=mention,
        r_f=r_f, g_f=g_f, b_f=b_f,
    )
