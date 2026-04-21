"""
Widget de visualisation et d'annotation du plan amiante.

Ce module définit la classe `CanvasWidget` qui affiche le plan chargé
(image raster ou PDF) et gère le dessin interactif des formes d'annotation.
Tout le rendu passe par `paintEvent` / `QPainter` et les méthodes `_dessiner_*`.
Aucune logique métier n'est présente ici : les traitements sont délégués
aux modules `src/services/` et `src/utils/`.

Modes de dessin disponibles (voir `ModeCanvas`) :
    ModeCanvas.SELECTION         : sélection, déplacement et redimensionnement
    ModeCanvas.DESSIN_RECT       : rectangle (cliquer-glisser)
    ModeCanvas.DESSIN_CERCLE     : cercle (cliquer-glisser depuis le centre)
    ModeCanvas.DESSIN_LIGNE      : segment (deux clics)
    ModeCanvas.DESSIN_POLYGONE   : polygone fermé (N clics + double-clic)
    ModeCanvas.LIGNES_CONNECTEES : polyligne ouverte (N clics + double-clic)
    ModeCanvas.CALLOUT           : bulle de légende (deux clics)

Système de coordonnées
----------------------
Toutes les formes stockent leurs points en **coordonnées image originale**.
La conversion canvas ↔ image passe par les méthodes `_canvas_vers_image` et
`_image_vers_canvas`, qui tiennent compte du zoom et du centrage automatique
du plan dans la zone canvas. Les attributs `_rect_affichage` et `_echelle`
sont recalculés à chaque `paintEvent` et utilisés par ces fonctions.
"""

import copy
import logging
import math
import uuid
from enum import Enum

from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QPointF, QRectF, QSizeF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPixmap, QPolygon, QCursor,
    QFont, QFontMetrics,
)
from PyQt6.QtWidgets import QWidget, QMenu, QMessageBox

from src.models.bulle import BulleLegende
from src.models.forme import (
    FormeBase,
    FormeRect,
    FormeCercle,
    FormeLigne,
    FormePolygone,
    FormeLignesConnectees,
)
from src.utils.constantes import (
    COULEUR_VERTE,
    COULEUR_ORANGE,
    COULEUR_ROUGE,
    ALPHA_PLEIN,
    ALPHA_SEMI,
    TAILLE_POIGNEE,
    EPAISSEUR_TRAIT,
    EPAISSEUR_POIGNEE,
    EPAISSEUR_GHOST,
    TOLERANCE_HIT,
    MARGE_PLAN,
    COULEUR_FOND_CANVAS,
    COULEUR_TEXTE_INVITE,
    ZOOM_MIN,
    ZOOM_MAX,
    ZOOM_FACTEUR_MOLETTE,
    ZOOM_DEFAUT,
    COULEUR_LASSO,
    ALPHA_LASSO,
    RAYON_POINT_GHOST,
    LARGEUR_BULLE,
    HAUTEUR_LIGNE,
    PADDING_BULLE,
    FACTEUR_LARGEUR_BULLE,
    PIED_LONGUEUR_DEFAUT,
    PIED_LONGUEUR_MIN,
)
from src.utils.pdf_to_image import pdf_vers_pixmap
from src.utils.pdf_utils import (
    BULLE_MARGE,
    LARGEUR_CALLOUT_PT,
    ZONE_DISPONIBLE_HAUT,
    ZONE_DISPONIBLE_LARG,
    ZONE_PLAN_HAUTEUR,
    ZONE_PLAN_LARGEUR,
)

# Journalisation propre au module
logger = logging.getLogger(__name__)


class ModeCanvas(str, Enum):
    """Modes de fonctionnement du canvas de dessin."""

    SELECTION         = "selection"
    DESSIN_RECT       = "rect"
    DESSIN_CERCLE     = "cercle"
    DESSIN_LIGNE      = "ligne"
    DESSIN_POLYGONE   = "polygone"
    LIGNES_CONNECTEES = "lignes_connectees"
    CALLOUT           = "callout"


class CanvasWidget(QWidget):
    """
    Zone de visualisation du plan et des annotations.

    Attributs
    ---------
    _pixmap : QPixmap | None
        Image du plan actuellement chargé (None si aucun plan).
    _mode : ModeCanvas
        Mode de dessin courant (par défaut ModeCanvas.SELECTION).
    _semi_transparent : bool
        Indique si le remplissage des annotations est semi-transparent.
    _formes : list[FormeBase]
        Toutes les formes dessinées sur la planche courante.
        Les points de chaque forme sont stockés en coordonnées image originale.
    _formes_selectionnees : list[FormeBase]
        Liste des formes actuellement sélectionnées (multi-sélection).
    _presse_papier : list[FormeBase]
        Copie profonde des formes copiées (Ctrl+C / Ctrl+X).
    _indice_poignee : int
        Indice du point de contrôle en cours de drag (-1 = aucun).
    _forme_active_poignee : FormeBase | None
        Forme dont on est en train de déplacer une poignée.
    _drag_corps : bool
        True si l'on déplace toute la sélection (et non une poignée).
    _drag_multi_debut : QPoint | None
        Position souris au début d'un drag multi (coordonnées canvas).
    _lasso_debut : QPointF | None
        Coin de départ du rectangle lasso (coordonnées canvas).
    _lasso_fin : QPointF | None
        Coin courant du rectangle lasso (coordonnées canvas).
    _points_en_cours : list[tuple[float, float]]
        Points de la forme en cours de tracé, en coordonnées image originale.
    _pos_souris : QPoint | None
        Dernière position connue de la souris (coordonnées canvas, pour le ghost).
    _zoom : float
        Facteur de zoom courant (1.0 = 100%).
    _rect_affichage : QRectF
        Rectangle décrivant où le plan est effectivement affiché dans le canvas
        (coordonnées canvas). Mis à jour à chaque paintEvent.
    _echelle : float
        Facteur pixels_canvas / pixels_image. Mis à jour à chaque paintEvent.
    _bulles : list[BulleLegende]
        Toutes les bulles de légende call-out de la planche courante.
    _bulle_selectionnee : BulleLegende | None
        Bulle actuellement sélectionnée (None si aucune).
    _ancrage_en_cours : tuple[float, float] | None
        Point d'ancrage du premier clic en mode CALLOUT (coords image).
    _drag_pied_bulle : BulleLegende | None
        Bulle dont on est en train de déplacer la poignée de pied (None si aucune).
    """

    # Signal émis quand le zoom change, avec la valeur (0.0–5.0)
    zoom_change = pyqtSignal(float)

    # Signal émis quand Échap est pressé (demande de retour en mode sélection)
    retour_selection = pyqtSignal()

    # Signal émis quand une ou plusieurs bulles sont supprimées
    bulle_supprimee = pyqtSignal()

    # Signal émis après création d'une bulle call-out (ou demande de changement d'échantillon)
    bulle_creee = pyqtSignal(object)

    # Signal émis quand une seule forme est sélectionnée, avec son épaisseur
    epaisseur_selection_change = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # --- Plan ---
        self._pixmap: QPixmap | None = None
        # Chemin du fichier plan actuellement chargé (nécessaire pour la sauvegarde d'état)
        self._plan_chemin: str | None = None

        # --- Mode de dessin ---
        self._mode: ModeCanvas = ModeCanvas.SELECTION

        # --- Transparence (conservé pour compatibilité) ---
        self._semi_transparent: bool = False

        # --- Couleur, transparence et épaisseur actives ---
        self._couleur_active: tuple = COULEUR_VERTE   # RGB tuple — couleur de la prochaine forme
        self._epaisseur_active: float = float(EPAISSEUR_TRAIT)  # Épaisseur du prochain tracé

        # --- Formes dessinées ---
        # Les points sont stockés en coordonnées image originale
        self._formes: list[FormeBase] = []

        # --- Multi-sélection ---
        self._formes_selectionnees: list[FormeBase] = []   # formes sélectionnées
        self._presse_papier: list[FormeBase] = []           # deepcopy des formes copiées

        # --- État du drag ---
        self._indice_poignee: int = -1               # -1 = aucune poignée draguée
        self._forme_active_poignee: FormeBase | None = None  # forme dont on drag la poignée
        self._drag_corps: bool = False               # True = on déplace toute la sélection
        self._drag_multi_debut: QPoint | None = None  # position souris début du drag multi

        # --- Lasso de sélection ---
        self._lasso_debut: QPointF | None = None    # coin départ du rectangle lasso (coords canvas)
        self._lasso_fin: QPointF | None = None      # coin courant du rectangle lasso (coords canvas)

        # --- Tracé en cours ---
        # Points en coordonnées image originale
        self._points_en_cours: list[tuple[float, float]] = []
        self._pos_souris: QPoint | None = None  # coordonnées canvas

        # --- Zoom ---
        self._zoom: float = ZOOM_DEFAUT          # Facteur de zoom courant
        self._pan_offset: QPointF = QPointF(0.0, 0.0)  # décalage de défilement en pixels canvas
        self._pan_en_cours: bool = False
        self._pan_debut: QPoint | None = None
        self._pan_offset_debut: QPointF = QPointF(0.0, 0.0)

        # --- Système de coordonnées centralisé ---
        # Mis à jour dans paintEvent ; utilisés par _canvas_vers_image / _image_vers_canvas
        self._rect_affichage: QRectF = QRectF()  # rectangle du plan dans le canvas
        self._echelle: float = 1.0               # facteur pixels_canvas / pixels_image

        # --- Bulles call-out ---
        self._bulles: list[BulleLegende] = []
        self._bulle_selectionnee: BulleLegende | None = None
        self._ancrage_en_cours: tuple[float, float] | None = None  # 1er clic callout (coords image)
        # Échantillon sélectionné dans le panneau Excel, injecté à la création de la bulle
        self._echantillon_en_attente = None

        # Rectangle cartouche (zone plan) en coordonnées canvas — mis à jour dans paintEvent
        self._rect_zone_plan: QRectF = QRectF()
        # Bulle dont on déplace la poignée de pied (segment perpendiculaire)
        self._drag_pied_bulle: BulleLegende | None = None

        # Fond par défaut du widget
        self.setAutoFillBackground(False)
        # Nécessaire pour recevoir les événements clavier
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Indispensable pour recevoir mouseMoveEvent même sans bouton pressé
        # (ghost polygone / lignes connectées entre les clics)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    def definir_echantillon_actif(self, echantillon) -> None:
        """
        Mémorise l'échantillon sélectionné dans le panneau Excel.

        Cet échantillon sera injecté dans la prochaine bulle call-out créée.

        Paramètres
        ----------
        echantillon : Echantillon
            L'échantillon sélectionné dans le panneau Excel.
        """
        self._echantillon_en_attente = echantillon
        logger.debug("Échantillon en attente défini : %s", echantillon.prelevement if echantillon else None)

    def _emettre_epaisseur_selection(self) -> None:
        """Émet epaisseur_selection_change si exactement une forme est sélectionnée."""
        if len(self._formes_selectionnees) == 1:
            self.epaisseur_selection_change.emit(int(self._formes_selectionnees[0].epaisseur))

    def definir_epaisseur(self, epaisseur: int) -> None:
        """
        Mémorise l'épaisseur de trait active pour les prochaines formes.
        Si des formes sont sélectionnées, leur épaisseur est mise à jour immédiatement.

        Paramètres
        ----------
        epaisseur : int
            Épaisseur en pixels (canvas) / points (PDF).
        """
        self._epaisseur_active = float(epaisseur)
        if self._formes_selectionnees:
            for forme in self._formes_selectionnees:
                forme.epaisseur = self._epaisseur_active
            self.update()
        logger.debug("Épaisseur active : %s px", epaisseur)

    def charger_plan(self, chemin: str) -> None:
        """
        Charge un plan depuis un fichier image (JPG/PNG) ou PDF.

        Pour les fichiers PDF, seule la première page est rendue.

        Paramètres
        ----------
        chemin : str
            Chemin vers le fichier à charger.
        """
        if chemin.lower().endswith(".pdf"):
            # Conversion PDF → QPixmap via le module utilitaire
            self._pixmap = pdf_vers_pixmap(chemin)
        else:
            # Chargement direct pour les formats raster courants
            self._pixmap = QPixmap(chemin)

        if self._pixmap is None or self._pixmap.isNull():
            logger.warning("Impossible de charger le plan : '%s'", chemin)
            self._pixmap = None
            self._plan_chemin = None
        else:
            self._plan_chemin = chemin
            logger.info("Plan chargé : '%s'", chemin)

        # Déclencher le redessin
        self.update()

    def changer_mode(self, mode: str) -> None:
        """
        Change le mode de dessin actif et adapte le curseur en conséquence.

        Accepte une chaîne de caractères pour rester compatible avec les
        signaux PyQt6, puis convertit en interne en `ModeCanvas`.

        Paramètres
        ----------
        mode : str
            Identifiant du mode (ex. "rect", "cercle", "selection", "callout", …).
        """
        self._mode = ModeCanvas(mode)
        # Abandon d'un tracé en cours si on change de mode — remise à zéro complète
        self._points_en_cours = []
        self._pos_souris = None
        # Réinitialisation de l'ancrage call-out si on quitte le mode CALLOUT
        self._ancrage_en_cours = None

        if self._mode == ModeCanvas.SELECTION:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

        self.update()

    def changer_transparence(self, semi: bool) -> None:
        """
        Active ou désactive le remplissage semi-transparent des annotations.

        Paramètres
        ----------
        semi : bool
            True pour activer la semi-transparence, False pour un rendu plein.
        """
        self._semi_transparent = semi
        self.update()

    def changer_couleur_active(self, couleur_rgb: tuple) -> None:
        """
        Met à jour la couleur active utilisée pour les nouvelles formes.

        Paramètres
        ----------
        couleur_rgb : tuple[int, int, int]
            Triplet RGB de la couleur sélectionnée dans la toolbar.
        """
        self._couleur_active = couleur_rgb
        logger.debug("Couleur active canvas : %s", couleur_rgb)

    def vider_formes(self) -> None:
        """Supprime toutes les formes et bulles de la planche et réinitialise l'état."""
        self._formes = []
        self._formes_selectionnees = []
        self._presse_papier = []
        self._pos_souris = None
        self._points_en_cours = []
        # Réinitialisation des bulles call-out
        self._bulles = []
        self._bulle_selectionnee = None
        self._ancrage_en_cours = None
        self._drag_pied_bulle = None
        self.update()

    # ------------------------------------------------------------------
    # Méthodes publiques presse-papier
    # ------------------------------------------------------------------

    def copier(self) -> None:
        """Copie les formes sélectionnées dans le presse-papier (deepcopy)."""
        if not self._formes_selectionnees:
            return
        self._presse_papier = copy.deepcopy(self._formes_selectionnees)
        logger.debug("%d forme(s) copiée(s).", len(self._presse_papier))

    def couper(self) -> None:
        """Copie puis supprime les formes sélectionnées."""
        self.copier()
        for forme in self._formes_selectionnees:
            if forme in self._formes:
                self._formes.remove(forme)
        self._formes_selectionnees = []
        self.update()

    def coller(self) -> None:
        """
        Colle les formes du presse-papier avec un décalage de +10px (coords image).
        Chaque forme collée reçoit un nouvel UUID.
        """
        if not self._presse_papier:
            return
        # Décalage en coordonnées image
        decalage = 10.0 / self._echelle if self._echelle > 0 else 10.0
        nouvelles: list[FormeBase] = []
        for forme in self._presse_papier:
            nouvelle = copy.deepcopy(forme)
            nouvelle.id = str(uuid.uuid4())
            nouvelle.points = [(p[0] + decalage, p[1] + decalage) for p in nouvelle.points]
            nouvelles.append(nouvelle)
        self._formes.extend(nouvelles)
        self._formes_selectionnees = nouvelles
        self.update()
        logger.debug("%d forme(s) collée(s).", len(nouvelles))

    # ------------------------------------------------------------------
    # Méthodes publiques de zoom
    # ------------------------------------------------------------------

    def zoom_in(self) -> None:
        """Augmente le zoom d'un cran (facteur ZOOM_FACTEUR_MOLETTE)."""
        self._appliquer_zoom(self._zoom * ZOOM_FACTEUR_MOLETTE, centre_canvas=None)

    def zoom_out(self) -> None:
        """Diminue le zoom d'un cran (facteur 1/ZOOM_FACTEUR_MOLETTE)."""
        self._appliquer_zoom(self._zoom / ZOOM_FACTEUR_MOLETTE, centre_canvas=None)

    def zoom_reset(self) -> None:
        """Remet le zoom à 100% et recentre l'image."""
        self._pan_offset = QPointF(0.0, 0.0)
        self._appliquer_zoom(ZOOM_DEFAUT, centre_canvas=None)

    def _appliquer_zoom(self, nouveau_zoom: float, centre_canvas: QPointF | None = None) -> None:
        """
        Applique le facteur de zoom en le clampant entre ZOOM_MIN et ZOOM_MAX.
        Quand centre_canvas est fourni, effectue un zoom centré sur le curseur
        (le point sous la souris reste fixe). Réinitialise le pan au zoom minimum.

        Paramètres
        ----------
        nouveau_zoom : float
            Nouveau facteur de zoom souhaité.
        centre_canvas : QPointF | None
            Point autour duquel centrer le zoom (coordonnées canvas).
        """
        nouveau_zoom = max(ZOOM_MIN, min(ZOOM_MAX, nouveau_zoom))

        if centre_canvas is not None and not self._rect_affichage.isNull() and self._zoom > 0:
            # Zoom centré sur le curseur : le point sous la souris reste fixe
            old_tl = self._rect_affichage.topLeft()
            ratio = nouveau_zoom / self._zoom
            new_tl = centre_canvas - (centre_canvas - old_tl) * ratio
            # Taille fit-to-view (zoom=1.0) dérivée de l'état courant
            taille_fit_w = self._rect_affichage.width() / self._zoom
            taille_fit_h = self._rect_affichage.height() / self._zoom
            zone_cx = self._rect_zone_plan.center().x()
            zone_cy = self._rect_zone_plan.center().y()
            centered_tl_x = zone_cx - taille_fit_w * nouveau_zoom / 2
            centered_tl_y = zone_cy - taille_fit_h * nouveau_zoom / 2
            self._pan_offset = QPointF(
                new_tl.x() - centered_tl_x,
                new_tl.y() - centered_tl_y,
            )

        if nouveau_zoom <= ZOOM_MIN:
            self._pan_offset = QPointF(0.0, 0.0)

        self._zoom = nouveau_zoom
        self.zoom_change.emit(self._zoom)
        self.update()

    def lire_etat(self) -> dict:
        """
        Retourne un dictionnaire représentant l'état complet du canvas.

        Utilisé par la fenêtre principale pour sauvegarder l'état d'une planche
        avant de basculer vers une autre.

        Retourne
        --------
        dict avec les clés :
            - ``plan_chemin``  : chemin du fichier plan (str | None)
            - ``formes``       : liste des formes dessinées (copie)
            - ``bulles``       : liste des bulles call-out (copie)
            - ``zoom_factor``  : facteur de zoom courant (float)
            - ``offset``       : (0.0, 0.0) — l'offset est calculé automatiquement
        """
        zp = self._rect_affichage
        return {
            "plan_chemin": self._plan_chemin,
            "formes":      list(self._formes),
            "bulles":      list(self._bulles),
            "zoom_factor": self._zoom,
            "offset":      (0.0, 0.0),
            "zone_plan":   (zp.x(), zp.y(), zp.width(), zp.height()) if not zp.isNull() else None,
        }

    def appliquer_etat(self, etat: dict) -> None:
        """
        Restaure l'état complet du canvas depuis un dictionnaire.

        Utilisé par la fenêtre principale lors du passage d'une planche à l'autre.

        Paramètres
        ----------
        etat : dict
            Dictionnaire produit par ``lire_etat()``.
        """
        # Réinitialiser la sélection et les états transitoires
        self._formes_selectionnees = []
        self._bulle_selectionnee = None
        self._points_en_cours = []
        self._ancrage_en_cours = None

        # Restaurer les formes et les bulles
        self._formes = list(etat.get("formes", []))
        self._bulles = list(etat.get("bulles", []))

        # Restaurer le zoom
        zoom = etat.get("zoom_factor", 1.0)
        self._zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))

        # Charger le plan (ou vider le canvas si aucun chemin)
        chemin = etat.get("plan_chemin")
        if chemin:
            self.charger_plan(chemin)
        else:
            self._pixmap = None
            self._plan_chemin = None

        self.update()

    # ------------------------------------------------------------------
    # Conversion de coordonnées (système centralisé)
    # ------------------------------------------------------------------

    def _canvas_vers_image(self, point_canvas: QPointF) -> QPointF:
        """
        Convertit un point en coordonnées canvas (écran) vers coordonnées image originale.

        Étapes :
        1. Soustraire le coin supérieur gauche de _rect_affichage
           (décalage dû au centrage du plan dans la zone canvas)
        2. Diviser par le facteur d'échelle effectif (_echelle)
        3. Ajouter le coin supérieur gauche de _rect_affichage (centrage)

        Paramètres
        ----------
        point_canvas : QPointF
            Point exprimé en coordonnées widget (pixels canvas).

        Retourne
        --------
        QPointF
            Point dans l'espace de l'image originale.
        """
        # Étape 1 : retirer le décalage de centrage
        x_relatif = point_canvas.x() - self._rect_affichage.x()
        y_relatif = point_canvas.y() - self._rect_affichage.y()

        # Étape 2 : passer en coordonnées image
        if self._echelle != 0.0:
            x_img = x_relatif / self._echelle
            y_img = y_relatif / self._echelle
        else:
            x_img = x_relatif
            y_img = y_relatif

        return QPointF(x_img, y_img)

    def _image_vers_canvas(self, point_image: QPointF) -> QPointF:
        """
        Convertit un point en coordonnées image originale vers coordonnées canvas.

        Opération inverse de _canvas_vers_image.

        Étapes :
        1. Multiplier par le facteur d'échelle effectif (_echelle)
        2. Ajouter le coin supérieur gauche de _rect_affichage

        Paramètres
        ----------
        point_image : QPointF
            Point exprimé en coordonnées image originale.

        Retourne
        --------
        QPointF
            Point dans l'espace canvas (pixels widget).
        """
        x_img = point_image.x()
        y_img = point_image.y()

        # Étape 1 : passer en coordonnées canvas (image × échelle)
        x_canvas = x_img * self._echelle
        y_canvas = y_img * self._echelle

        # Étape 2 : ajouter le décalage de centrage dans la zone canvas
        x_canvas += self._rect_affichage.x()
        y_canvas += self._rect_affichage.y()

        return QPointF(x_canvas, y_canvas)

    # ------------------------------------------------------------------
    # Méthode utilitaire : facteur d'échelle image-pixels → points PDF
    # ------------------------------------------------------------------

    def _echelle_pdf(self) -> float:
        """
        Facteur d'échelle image-pixels → points PDF.

        Utilise ZONE_PLAN_LARGEUR × ZONE_PLAN_HAUTEUR — la zone du cartouche,
        identique à celle utilisée dans pdf_exporter. Retourne 1.0 si pas d'image.
        """
        if self._pixmap is None:
            return 1.0

        img_larg = float(self._pixmap.width())
        img_haut = float(self._pixmap.height())
        if img_larg <= 0 or img_haut <= 0:
            return 1.0

        return min(ZONE_PLAN_LARGEUR / img_larg, ZONE_PLAN_HAUTEUR / img_haut)

    def _rect_zone_plan_canvas(self) -> QRectF:
        """
        Retourne le rectangle du cartouche (ZONE_PLAN) en coordonnées canvas.

        Calculé dans paintEvent et mémorisé dans self._rect_zone_plan.
        """
        return self._rect_zone_plan

    # ------------------------------------------------------------------
    # Méthode utilitaire : largeur canvas équivalente à LARGEUR_CALLOUT_PT PDF
    # ------------------------------------------------------------------

    def _bw_callout_canvas(self) -> float:
        """
        Largeur de la bulle call-out en pixels canvas, équivalente à LARGEUR_CALLOUT_PT
        dans le PDF exporté.
        """
        ep = self._echelle_pdf()
        if ep <= 0 or self._echelle <= 0:
            return LARGEUR_BULLE * FACTEUR_LARGEUR_BULLE * self._echelle
        return (LARGEUR_CALLOUT_PT / ep) * self._echelle

    # ------------------------------------------------------------------
    # Méthode utilitaire : hauteur réelle d'une bulle (via QFontMetrics)
    # ------------------------------------------------------------------

    def _hauteur_reelle_bulle(self, bulle: "BulleLegende") -> float:
        """
        Hauteur de la bulle en pixels canvas, calculée par la formule PDF.

        Utilise exactement la même logique que pdf_exporter._annoter_bulle :
        nb_lignes × 9.6 pt + 4 pt, puis convertit en pixels canvas via echelle_pdf.
        Garantit une cohérence visuelle totale avec le PDF exporté.
        """
        ep = self._echelle_pdf()
        if ep <= 0 or self._echelle <= 0:
            return (HAUTEUR_LIGNE * 1.4 + PADDING_BULLE) * self._echelle

        if bulle.echantillon is None:
            return (10.0 / ep) * self._echelle

        ech = bulle.echantillon
        chars_par_ligne = max(1, int(LARGEUR_CALLOUT_PT / 4.4))  # 26 (même valeur que pdf_exporter)
        nb_lignes = sum(
            math.ceil(len(t) / chars_par_ligne)
            for t in (ech.texte_ligne1, ech.texte_ligne2, ech.texte_ligne3)
            if t and t.strip()
        )
        if ech.mention and ech.mention.strip():
            nb_lignes += 2  # +1 séparateur "- - -", +1 mention
        bh_pdf = max(10.0, nb_lignes * 9.6 + 4.0)
        return (bh_pdf / ep) * self._echelle

    # ------------------------------------------------------------------
    # Méthode utilitaire : calcul du point_depart du pied d'une bulle
    # ------------------------------------------------------------------

    def _calculer_geometrie_callout(
        self, bulle: BulleLegende
    ) -> tuple[QPointF, QPointF, QPointF, QPointF]:
        """
        Calcule les quatre points géométriques du call-out d'une bulle.

        Géométrie :
        - bord_bulle     : point sur le bord gauche ou droit de la bulle, à mi-hauteur
        - point_depart   : extrémité du pied (segment perpendiculaire horizontal)
        - anc            : point d'ancrage sur le plan (pastille)
        - centre_bulle   : centre de la bulle (non utilisé en dehors du calcul interne)

        Règles de côté :
          Si ancrage.x < bx → pied sort du bord gauche (bord_bulle à gauche)
          Si ancrage.x >= bx + bw → pied sort du bord droit
          Sinon (ancrage au-dessus/en-dessous) → bord gauche par défaut

        Retourne
        --------
        (anc_canvas, bord_bulle, point_depart, rect_bulle_canvas)
            Tous en coordonnées canvas.
        """
        anc = self._image_vers_canvas(QPointF(*bulle.ancrage))
        bx_img, by_img = bulle.position
        bw = self._bw_callout_canvas()
        # Utiliser QFontMetrics pour une hauteur précise (évite la surestimation
        # de bulle.hauteur() basée sur une largeur de caractère fixe).
        bh = self._hauteur_reelle_bulle(bulle)
        coin_hg = self._image_vers_canvas(QPointF(bx_img, by_img))
        bx = coin_hg.x()
        by = coin_hg.y()
        centre_bulle_y = by + bh / 2
        pied_canvas = bulle.pied_longueur * self._echelle

        if anc.x() < bx:
            # Ancrage à gauche : pied sort du bord gauche
            bord_bulle = QPointF(bx, centre_bulle_y)
            point_depart = QPointF(bx - pied_canvas, centre_bulle_y)
        elif anc.x() >= bx + bw:
            # Ancrage à droite : pied sort du bord droit
            bord_bulle = QPointF(bx + bw, centre_bulle_y)
            point_depart = QPointF(bx + bw + pied_canvas, centre_bulle_y)
        else:
            # Ancrage au-dessus ou en-dessous : comportement par défaut (bord gauche)
            bord_bulle = QPointF(bx, centre_bulle_y)
            point_depart = QPointF(bx - pied_canvas, centre_bulle_y)

        rect_bulle = QRectF(bx, by, bw, bh)
        return anc, bord_bulle, point_depart, rect_bulle

    # ------------------------------------------------------------------
    # Événements souris
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:  # noqa: N802
        """Zoom à la molette uniquement avec Ctrl enfoncé (Ctrl+molette)."""
        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta > 0:
            facteur = ZOOM_FACTEUR_MOLETTE
        else:
            facteur = 1.0 / ZOOM_FACTEUR_MOLETTE
        centre = QPointF(event.position())
        self._appliquer_zoom(self._zoom * facteur, centre_canvas=centre)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Gère le clic souris selon le mode actif."""
        pos = event.pos()

        # --- Défilement par bouton central (priorité absolue) ---
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_en_cours = True
            self._pan_debut = event.pos()
            self._pan_offset_debut = QPointF(self._pan_offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # Convertir la position canvas en coordonnées image originale (utile dans plusieurs modes)
        pt_image = self._canvas_vers_image(QPointF(pos))
        pt = (pt_image.x(), pt_image.y())

        if self._mode == ModeCanvas.SELECTION:
            ctrl_enfonce = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

            if event.button() == Qt.MouseButton.RightButton:
                # Priorité au clic droit sur une bulle
                bulle = self._trouver_bulle_sous_curseur(pos)
                if bulle:
                    self._menu_contextuel_bulle(pos, bulle)
                    return
                # Sinon menu contextuel sur la première forme sous le curseur
                forme = self._trouver_forme_sous_curseur(pos)
                if forme:
                    self._menu_contextuel(pos, forme)
                return

            if event.button() != Qt.MouseButton.LeftButton:
                return

            # --- Test de la poignée de pied de la bulle sélectionnée ---
            if self._bulle_selectionnee is not None:
                _, _, point_depart, _ = self._calculer_geometrie_callout(self._bulle_selectionnee)
                tol_pied = TAILLE_POIGNEE
                pos_qf = QPointF(pos)
                if (abs(pos_qf.x() - point_depart.x()) <= tol_pied and
                        abs(pos_qf.y() - point_depart.y()) <= tol_pied):
                    # Clic sur la poignée de pied : commencer le drag du pied
                    self._drag_pied_bulle = self._bulle_selectionnee
                    self._drag_multi_debut = pos
                    self.update()
                    return

            # --- Priorité aux bulles sur les formes ---
            bulle_sous_curseur = self._trouver_bulle_sous_curseur(pos)
            if bulle_sous_curseur:
                self._bulle_selectionnee = bulle_sous_curseur
                self._drag_corps = True
                self._drag_multi_debut = pos
                # Désélectionner les formes quand on clique sur une bulle
                if not ctrl_enfonce:
                    self._formes_selectionnees = []
                self.update()
                return

            # Position image pour comparaison avec les poignées
            pos_image = self._canvas_vers_image(QPointF(pos))

            forme_cliquee = self._trouver_forme_sous_curseur(pos)

            if forme_cliquee:
                if ctrl_enfonce:
                    # Ctrl+clic : toggle sélection
                    if forme_cliquee in self._formes_selectionnees:
                        self._formes_selectionnees.remove(forme_cliquee)
                    else:
                        self._formes_selectionnees.append(forme_cliquee)
                    self._indice_poignee = -1
                    self._drag_corps = False
                else:
                    # Clic simple : sélectionner uniquement cette forme (+ vérif poignée)
                    if forme_cliquee not in self._formes_selectionnees:
                        self._formes_selectionnees = [forme_cliquee]
                    # Vérifier si une poignée est cliquée
                    demi = TAILLE_POIGNEE // 2
                    tol_img = demi / self._echelle if self._echelle > 0 else demi
                    self._indice_poignee = -1
                    self._forme_active_poignee = None
                    for i, pt_ctrl in enumerate(forme_cliquee.points):
                        if (abs(pos_image.x() - pt_ctrl[0]) <= tol_img and
                                abs(pos_image.y() - pt_ctrl[1]) <= tol_img):
                            self._indice_poignee = i
                            self._forme_active_poignee = forme_cliquee
                            break
                    else:
                        self._drag_corps = True
                        self._drag_multi_debut = pos
                    # Désélectionner la bulle si on clique sur une forme
                    self._bulle_selectionnee = None
                self._emettre_epaisseur_selection()
            else:
                if not ctrl_enfonce:
                    # Clic dans le vide sans Ctrl → désélectionner tout + démarrer lasso
                    self._formes_selectionnees = []
                    self._bulle_selectionnee = None
                # Démarrer le lasso
                self._lasso_debut = QPointF(pos)
                self._lasso_fin = QPointF(pos)
            self.update()
            return

        # --- Bouton DROIT hors mode sélection ---
        if event.button() == Qt.MouseButton.RightButton:
            return

        # --- Bouton GAUCHE ---
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._mode in (ModeCanvas.DESSIN_RECT, ModeCanvas.DESSIN_CERCLE):
            # Premier point : début du tracé (en coordonnées image)
            self._points_en_cours = [pt]

        elif self._mode == ModeCanvas.DESSIN_LIGNE:
            self._points_en_cours.append(pt)
            if len(self._points_en_cours) == 2:
                # Remise à zéro AVANT de créer la forme pour éviter tout ghost résiduel
                pts_captures = list(self._points_en_cours)
                self._points_en_cours = []
                self._pos_souris = None
                nouvelle_forme = FormeLigne(
                    points=pts_captures,
                    couleur_rgb=self._couleur_active,
                    alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                    epaisseur=self._epaisseur_active,
                )
                self._formes.append(nouvelle_forme)
                logger.debug("FormeLigne créée : %s", nouvelle_forme.id)

        elif self._mode in (ModeCanvas.DESSIN_POLYGONE, ModeCanvas.LIGNES_CONNECTEES):
            # Accumulation des points en coordonnées image (la forme est créée au double-clic)
            self._points_en_cours.append(pt)

        elif self._mode == ModeCanvas.CALLOUT:
            # Mode call-out : deux clics successifs pour créer une bulle
            if self._ancrage_en_cours is None:
                # Premier clic : vérifier qu'un échantillon est sélectionné
                if self._echantillon_en_attente is None:
                    QMessageBox.warning(
                        self,
                        "Aucun échantillon sélectionné",
                        "Veuillez d'abord sélectionner un échantillon dans le panneau Excel\n"
                        "avant de placer une bulle de légende.",
                    )
                    return
                # Enregistrer l'ancrage en coordonnées image
                self._ancrage_en_cours = (pt_image.x(), pt_image.y())
                logger.debug("Ancrage call-out posé : %s", self._ancrage_en_cours)
            else:
                # Second clic : refuser si la position bulle est dans la zone plan
                pos_canvas = self._image_vers_canvas(QPointF(pt_image.x(), pt_image.y()))
                if self._rect_affichage.contains(pos_canvas):
                    QMessageBox.warning(
                        self,
                        "Placement invalide",
                        "Placez la bulle hors du plan.\n"
                        "Le point d'ancrage peut être sur le plan, mais la bulle doit être dans la zone de légende.",
                    )
                    return
                # Créer la bulle avec l'échantillon lié
                # Centrer horizontalement sur le clic — même largeur que le ghost
                bw_img = self._bw_callout_canvas() / self._echelle if self._echelle > 0 else LARGEUR_BULLE
                position = (pt_image.x() - bw_img / 2, pt_image.y())
                ech = self._echantillon_en_attente
                bulle = BulleLegende(
                    ancrage=self._ancrage_en_cours,
                    position=position,
                    couleur_rgb=ech.couleur,
                    echantillon=ech,
                )
                self._bulles.append(bulle)
                self._ancrage_en_cours = None
                self._echantillon_en_attente = None
                self.bulle_creee.emit(bulle)
                logger.debug(
                    "Bulle call-out créée : ancrage=%s, pos=%s, échantillon='%s'",
                    bulle.ancrage,
                    bulle.position,
                    ech.prelevement,
                )

        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Met à jour la position souris et gère les déplacements.

        _pos_souris est toujours mis à jour — même sans bouton pressé —
        grâce à setMouseTracking(True). Cela permet d'afficher le ghost
        des modes DESSIN_POLYGONE et LIGNES_CONNECTEES entre les clics.
        """
        # Mise à jour inconditionnelle de la position canvas (tracking actif)
        self._pos_souris = event.pos()

        # --- Défilement par bouton central ---
        if self._pan_en_cours and self._pan_debut is not None:
            delta = event.pos() - self._pan_debut
            self._pan_offset = QPointF(
                self._pan_offset_debut.x() + delta.x(),
                self._pan_offset_debut.y() + delta.y(),
            )
            self.update()
            return

        if self._mode == ModeCanvas.SELECTION:
            # Drag de la poignée de pied d'une bulle (priorité absolue)
            if self._drag_pied_bulle is not None and self._drag_multi_debut is not None:
                bulle = self._drag_pied_bulle
                ancien_img = self._canvas_vers_image(QPointF(self._drag_multi_debut))
                nouveau_img = self._canvas_vers_image(QPointF(event.pos()))
                delta_x = nouveau_img.x() - ancien_img.x()
                # Déterminer le côté du pied pour savoir le sens d'ajustement
                anc_x, _ = bulle.ancrage
                bx, _ = bulle.position
                bw = self._bw_callout_canvas() / self._echelle if self._echelle > 0 else bulle.largeur
                if anc_x >= bx + bw:
                    # Ancrage à droite : augmenter pied si on tire à droite
                    nouvelle_longueur = bulle.pied_longueur + delta_x
                else:
                    # Ancrage à gauche (ou au-dessus/dessous) : augmenter si on tire à gauche
                    nouvelle_longueur = bulle.pied_longueur - delta_x
                bulle.pied_longueur = max(PIED_LONGUEUR_MIN, nouvelle_longueur)
                self._drag_multi_debut = event.pos()

            # Drag bulle sélectionnée (corps)
            elif self._bulle_selectionnee is not None and self._drag_corps and self._drag_multi_debut is not None:
                ancien_img = self._canvas_vers_image(QPointF(self._drag_multi_debut))
                nouveau_img = self._canvas_vers_image(QPointF(event.pos()))
                dx = nouveau_img.x() - ancien_img.x()
                dy = nouveau_img.y() - ancien_img.y()
                bx, by = self._bulle_selectionnee.position
                self._bulle_selectionnee.position = (bx + dx, by + dy)
                self._drag_multi_debut = event.pos()

            # Drag multi-sélection de formes (déplacement du corps)
            elif self._drag_corps and self._drag_multi_debut is not None and self._formes_selectionnees:
                ancien_img = self._canvas_vers_image(QPointF(self._drag_multi_debut))
                nouveau_img = self._canvas_vers_image(QPointF(event.pos()))
                dx = nouveau_img.x() - ancien_img.x()
                dy = nouveau_img.y() - ancien_img.y()
                for forme in self._formes_selectionnees:
                    forme.points = [(p[0] + dx, p[1] + dy) for p in forme.points]
                self._drag_multi_debut = event.pos()

            # Drag poignée (une seule forme)
            elif self._indice_poignee >= 0 and self._forme_active_poignee is not None:
                pt_image = self._canvas_vers_image(QPointF(event.pos()))
                if self._indice_poignee < len(self._forme_active_poignee.points):
                    self._forme_active_poignee.points[self._indice_poignee] = (
                        pt_image.x(), pt_image.y()
                    )

            # Lasso : mise à jour du coin courant
            elif self._lasso_debut is not None:
                self._lasso_fin = QPointF(event.pos())

        # Toujours redessiner pour que le ghost suive le curseur
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Finalise le tracé ou le drag en cours."""
        # --- Fin du défilement par bouton central ---
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_en_cours = False
            self._pan_debut = None
            # Restaurer le curseur selon le mode courant
            if self._mode == ModeCanvas.SELECTION:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()

        if (
            self._mode in (ModeCanvas.DESSIN_RECT, ModeCanvas.DESSIN_CERCLE)
            and len(self._points_en_cours) == 1
        ):
            # Le deuxième point est la position de relâchement — convertir en coordonnées image
            pt_image = self._canvas_vers_image(QPointF(pos))
            pt = (pt_image.x(), pt_image.y())
            self._points_en_cours.append(pt)
            p0 = self._points_en_cours[0]
            p1 = self._points_en_cours[1]

            # Remise à zéro AVANT de créer la forme pour éviter tout ghost résiduel
            self._points_en_cours = []
            self._pos_souris = None

            # Créer la forme uniquement si les deux points sont distincts
            if p0 != p1:
                if self._mode == ModeCanvas.DESSIN_RECT:
                    nouvelle_forme = FormeRect(
                        points=[p0, p1],
                        couleur_rgb=self._couleur_active,
                        alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                        epaisseur=self._epaisseur_active,
                    )
                    self._formes.append(nouvelle_forme)
                    logger.debug("FormeRect créée : %s", nouvelle_forme.id)
                else:
                    nouvelle_forme = FormeCercle(
                        points=[p0, p1],
                        couleur_rgb=self._couleur_active,
                        alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                        epaisseur=self._epaisseur_active,
                    )
                    self._formes.append(nouvelle_forme)
                    logger.debug("FormeCercle créée : %s", nouvelle_forme.id)

        elif self._mode == ModeCanvas.SELECTION:
            # Appliquer la sélection lasso si active
            if self._lasso_debut is not None and self._lasso_fin is not None:
                self._appliquer_lasso()
                self._lasso_debut = None
                self._lasso_fin = None
            # Fin du drag
            self._drag_corps = False
            self._drag_multi_debut = None
            self._indice_poignee = -1
            self._forme_active_poignee = None
            # Fin du drag du pied de bulle
            self._drag_pied_bulle = None

        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        """Ferme le polygone ou termine la polyligne au double-clic."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._mode == ModeCanvas.DESSIN_POLYGONE and len(self._points_en_cours) >= 3:
            # Remise à zéro AVANT de créer la forme pour éviter tout ghost résiduel
            pts_captures = list(self._points_en_cours)
            self._points_en_cours = []
            self._pos_souris = None
            nouvelle_forme = FormePolygone(
                points=pts_captures,
                couleur_rgb=self._couleur_active,
                alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                epaisseur=self._epaisseur_active,
            )
            self._formes.append(nouvelle_forme)
            logger.debug("FormePolygone créée : %s", nouvelle_forme.id)

        elif (
            self._mode == ModeCanvas.LIGNES_CONNECTEES
            and len(self._points_en_cours) >= 2
        ):
            # Remise à zéro AVANT de créer la forme pour éviter tout ghost résiduel
            pts_captures = list(self._points_en_cours)
            self._points_en_cours = []
            self._pos_souris = None
            nouvelle_forme = FormeLignesConnectees(
                points=pts_captures,
                couleur_rgb=self._couleur_active,
                alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                epaisseur=self._epaisseur_active,
            )
            self._formes.append(nouvelle_forme)
            logger.debug("FormeLignesConnectees créée : %s", nouvelle_forme.id)

        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Gère les touches clavier globales du canvas."""
        if event.key() == Qt.Key.Key_Escape:
            self.changer_mode("selection")
            self.retour_selection.emit()
            return
        if event.key() == Qt.Key.Key_Delete:
            modifie = False
            # Suppression des formes sélectionnées
            if self._formes_selectionnees:
                for forme in self._formes_selectionnees:
                    if forme in self._formes:
                        self._formes.remove(forme)
                        logger.debug("Forme supprimée : %s", forme.id)
                self._formes_selectionnees = []
                modifie = True
            # Suppression de la bulle sélectionnée
            if self._bulle_selectionnee is not None:
                if self._bulle_selectionnee in self._bulles:
                    self._bulles.remove(self._bulle_selectionnee)
                    logger.debug("Bulle supprimée : %s", self._bulle_selectionnee.id)
                self._bulle_selectionnee = None
                modifie = True
            if modifie:
                self.update()
                self.bulle_supprimee.emit()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Logique de sélection
    # ------------------------------------------------------------------

    def _trouver_forme_sous_curseur(self, pos: QPoint) -> "FormeBase | None":
        """
        Retourne la forme la plus haute (dernière ajoutée) sous le curseur.
        Utilise forme.contient_point() avec la tolérance en coordonnées image.
        """
        if self._echelle <= 0:
            return None
        pos_image = self._canvas_vers_image(QPointF(pos))
        tolerance_image = TOLERANCE_HIT / self._echelle
        for forme in reversed(self._formes):
            if forme.contient_point(pos_image.x(), pos_image.y(), tolerance_image):
                return forme
        return None

    def _trouver_bulle_sous_curseur(self, pos: QPoint) -> "BulleLegende | None":
        """
        Retourne la bulle sous le curseur, ou None.
        Teste d'abord le rectangle de la bulle, puis le point d'ancrage.
        """
        if self._echelle <= 0:
            return None
        pos_img = self._canvas_vers_image(QPointF(pos))
        for bulle in reversed(self._bulles):
            bx, by = bulle.position
            bw = self._bw_callout_canvas() / self._echelle if self._echelle > 0 else bulle.largeur
            bh = self._hauteur_reelle_bulle(bulle) / self._echelle if self._echelle > 0 else bulle.hauteur()
            # Test sur le rectangle de la bulle
            if bx <= pos_img.x() <= bx + bw and by <= pos_img.y() <= by + bh:
                return bulle
            # Test sur le point d'ancrage (tolérance 8px en coordonnées image)
            tol = 8.0 / self._echelle if self._echelle > 0 else 8.0
            ax, ay = bulle.ancrage
            if abs(pos_img.x() - ax) <= tol and abs(pos_img.y() - ay) <= tol:
                return bulle
        return None

    def _appliquer_lasso(self) -> None:
        """
        Sélectionne toutes les formes dont le bounding-box intersecte le rectangle lasso.
        Le lasso est en coordonnées canvas, les bounding-boxes des formes en coordonnées image.
        """
        if self._lasso_debut is None or self._lasso_fin is None:
            return
        # Convertir les coins du lasso en coordonnées image
        p1 = self._canvas_vers_image(self._lasso_debut)
        p2 = self._canvas_vers_image(self._lasso_fin)
        lasso_img = QRectF(p1, p2).normalized()

        for forme in self._formes:
            if not forme.points:
                continue
            xs = [p[0] for p in forme.points]
            ys = [p[1] for p in forme.points]
            bbox = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            if lasso_img.intersects(bbox) and forme not in self._formes_selectionnees:
                self._formes_selectionnees.append(forme)
        self.update()

    # ------------------------------------------------------------------
    # Menus contextuels
    # ------------------------------------------------------------------

    def _menu_contextuel(self, pos: QPoint, forme: FormeBase) -> None:
        """
        Affiche un menu contextuel pour modifier la couleur, la transparence
        ou supprimer la forme donnée.

        Paramètres
        ----------
        pos : QPoint
            Position d'affichage du menu (coordonnées widget).
        forme : FormeBase
            Forme cible des actions.
        """
        menu = QMenu(self)

        # --- Couleurs ---
        action_vert = menu.addAction("Vert")
        action_orange = menu.addAction("Orange")
        action_rouge = menu.addAction("Rouge")
        menu.addSeparator()

        # --- Transparence ---
        action_plein = menu.addAction("Plein")
        action_transparent = menu.addAction("Transparent")
        menu.addSeparator()

        # --- Suppression ---
        action_suppr = menu.addAction("Supprimer")

        # Affichage et traitement du choix
        action_choisie = menu.exec(self.mapToGlobal(pos))

        if action_choisie == action_vert:
            forme.couleur_rgb = COULEUR_VERTE
        elif action_choisie == action_orange:
            forme.couleur_rgb = COULEUR_ORANGE
        elif action_choisie == action_rouge:
            forme.couleur_rgb = COULEUR_ROUGE
        elif action_choisie == action_plein:
            forme.alpha = ALPHA_PLEIN
        elif action_choisie == action_transparent:
            forme.alpha = ALPHA_SEMI
        elif action_choisie == action_suppr:
            if forme in self._formes:
                self._formes.remove(forme)
            # Nettoyer la sélection si la forme supprimée en faisait partie
            if forme in self._formes_selectionnees:
                self._formes_selectionnees.remove(forme)

        self.update()

    def _menu_contextuel_bulle(self, pos: QPoint, bulle: BulleLegende) -> None:
        """
        Affiche un menu contextuel sur une bulle : changer l'échantillon ou supprimer.

        Paramètres
        ----------
        pos : QPoint
            Position d'affichage du menu (coordonnées widget).
        bulle : BulleLegende
            Bulle cible des actions.
        """
        menu = QMenu(self)
        action_echantillon = menu.addAction("Changer l'échantillon")
        menu.addSeparator()
        action_supprimer = menu.addAction("Supprimer")

        action = menu.exec(self.mapToGlobal(pos))

        if action == action_echantillon:
            # Réutilise le signal bulle_creee pour ouvrir le panneau Excel
            self.bulle_creee.emit(bulle)
        elif action == action_supprimer:
            if bulle in self._bulles:
                self._bulles.remove(bulle)
                logger.debug("Bulle supprimée via menu contextuel : %s", bulle.id)
                self.bulle_supprimee.emit()
            if self._bulle_selectionnee is bulle:
                self._bulle_selectionnee = None

        self.update()

    # ------------------------------------------------------------------
    # Rendu — paintEvent et méthodes _dessiner_*
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        """
        Orchestre le rendu dans l'ordre strict :
        1. Fond gris
        2. Plan (QPixmap) centré avec bordure noire, avec prise en compte
           du zoom
        3. Formes colorées
        4. Bulles call-out
        5. Poignées de sélection
        6. Ghost de la forme en cours de tracé
        7. Lasso de sélection (rectangle pointillé bleu)

        Met à jour _rect_affichage et _echelle à chaque appel, ce qui permet
        aux méthodes de conversion de coordonnées d'être toujours cohérentes.
        """
        with QPainter(self) as peintre:
            peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 1. Fond gris clair
            peintre.fillRect(self.rect(), QColor(*COULEUR_FOND_CANVAS))

            if self._pixmap is not None and not self._pixmap.isNull():
                # Zone cartouche (fixe, proportionnelle à la mise en page PDF) :
                # - Gauche/droite : BULLE_MARGE de chaque côté (symétrique)
                # - Haut/bas      : BULLE_MARGE/2 de chaque côté (centré verticalement)
                canvas_inner_w = self.width()  - 2 * MARGE_PLAN
                canvas_inner_h = self.height() - 2 * MARGE_PLAN
                extra_x = int(canvas_inner_w * BULLE_MARGE / ZONE_DISPONIBLE_LARG)
                extra_y = int(canvas_inner_h * (BULLE_MARGE / 2) / ZONE_DISPONIBLE_HAUT)
                zone_plan = self.rect().adjusted(
                    MARGE_PLAN + extra_x, MARGE_PLAN + extra_y,
                    -(MARGE_PLAN + extra_x), -(MARGE_PLAN + extra_y),
                )
                zone_plan_qrectf = QRectF(zone_plan)
                # Mémoriser le cartouche pour les méthodes de conversion et le dessin de bordure
                self._rect_zone_plan = zone_plan_qrectf

                # --- Source : image entière ---
                src_rect = QRectF(self._pixmap.rect())

                taille_source = src_rect.size()  # QSizeF

                # --- Calcul de la taille affichée ---
                # Étape 1 : taille fit-to-view (zoom=1.0) — image contrainte dans zone_plan
                taille_fit = taille_source.scaled(
                    zone_plan_qrectf.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                # Étape 2 : appliquer le zoom sur la taille fit
                # À zoom=1.0 l'image remplit la zone plan ; à zoom>1.0 elle déborde (agrandissement)
                taille_affichee = QSizeF(
                    taille_fit.width() * self._zoom,
                    taille_fit.height() * self._zoom,
                )

                # --- Facteur d'échelle effectif ---
                # pixels_canvas / pixels_image (espace source rogné)
                if taille_source.width() > 0:
                    self._echelle = taille_affichee.width() / taille_source.width()
                else:
                    self._echelle = 1.0

                # --- Centrage dans zone_plan + offset de défilement ---
                x_centre = zone_plan_qrectf.x() + (zone_plan_qrectf.width() - taille_affichee.width()) / 2 + self._pan_offset.x()
                y_centre = zone_plan_qrectf.y() + (zone_plan_qrectf.height() - taille_affichee.height()) / 2 + self._pan_offset.y()
                self._rect_affichage = QRectF(
                    x_centre, y_centre,
                    taille_affichee.width(), taille_affichee.height(),
                )

                # 2. Dessin du pixmap (éventuellement rogné) mis à l'échelle et centré
                peintre.drawPixmap(
                    self._rect_affichage.toRect(),
                    self._pixmap,
                    src_rect.toRect(),
                )

                # Cadre de la zone plan — même position qu'à zoom=1.0, agrandi par le zoom
                # et décalé par le pan, comme n'importe quel objet de la scène
                zone_cx = zone_plan_qrectf.center().x()
                zone_cy = zone_plan_qrectf.center().y()
                zone_w  = zone_plan_qrectf.width()  * self._zoom
                zone_h  = zone_plan_qrectf.height() * self._zoom
                rect_cadre_zoome = QRectF(
                    zone_cx - zone_w / 2 + self._pan_offset.x(),
                    zone_cy - zone_h / 2 + self._pan_offset.y(),
                    zone_w,
                    zone_h,
                )
                peintre.setPen(QPen(QColor("black"), 1.5))
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                peintre.drawRect(rect_cadre_zoome)

            else:
                # Aucun plan chargé : message d'invite centré
                # _rect_affichage et _echelle restent à leurs valeurs par défaut
                peintre.setPen(QColor(*COULEUR_TEXTE_INVITE))
                peintre.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    "Ouvrir un plan via Fichier \u2192 Ouvrir Plan",
                )

            # 3. Formes dessinées
            self._dessiner_formes(peintre)

            # 4. Bulles call-out
            self._dessiner_bulles(peintre)

            # 5. Poignées de sélection
            self._dessiner_poignees(peintre)

            # 6. Ghost de la forme en cours
            self._dessiner_ghost(peintre)

            # 7. Lasso de sélection (rectangle pointillé bleu)
            if (self._mode == ModeCanvas.SELECTION and
                    self._lasso_debut is not None and self._lasso_fin is not None):
                couleur_lasso = QColor(*COULEUR_LASSO)
                stylo_lasso = QPen(couleur_lasso, 1, Qt.PenStyle.DashLine)
                couleur_fond_lasso = QColor(*COULEUR_LASSO)
                couleur_fond_lasso.setAlpha(ALPHA_LASSO)
                peintre.setPen(stylo_lasso)
                peintre.setBrush(QBrush(couleur_fond_lasso))
                lasso_rect = QRectF(self._lasso_debut, self._lasso_fin).normalized()
                peintre.drawRect(lasso_rect)

    def _dessiner_formes(self, peintre: QPainter) -> None:
        """
        Dessine toutes les formes validées de ``_formes``.

        Les points des formes sont stockés en coordonnées image originale.
        Ils sont convertis en coordonnées canvas via _image_vers_canvas avant le rendu.

        Chaque forme est rendue avec :
        - un contour de couleur pleine (alpha=255)
        - un remplissage coloré semi-transparent ou plein selon ``forme.alpha``
        """
        for forme in self._formes:
            pts_img = forme.points
            if len(pts_img) < 2:
                # Forme incomplète (moins de 2 points) : non rendue visuellement mais valide en mémoire
                continue

            # Conversion coordonnées image → canvas pour le rendu
            pts_canvas = [self._image_vers_canvas(QPointF(*p)) for p in pts_img]

            # Couleur de remplissage avec transparence configurée
            couleur_remplissage = QColor(*forme.couleur_rgb)
            couleur_remplissage.setAlpha(forme.alpha)

            # Contour toujours opaque
            couleur_contour = QColor(*forme.couleur_rgb)
            couleur_contour.setAlpha(255)

            # L'épaisseur est stockée en "pixels à zoom 100%".
            # On la multiplie par le facteur de zoom pour qu'elle reste
            # visuellement constante quelle que soit la mise à l'échelle.
            epaisseur_canvas = forme.epaisseur * self._zoom
            # Le contour adopte la même transparence que le remplissage :
            # en mode semi-transparent le trait lui-même laisse voir le plan.
            couleur_contour.setAlpha(forme.alpha)
            stylo = QPen(couleur_contour, epaisseur_canvas)
            brosse = QBrush(couleur_remplissage)

            if isinstance(forme, FormeRect):
                peintre.setPen(stylo)
                peintre.setBrush(brosse)
                p0 = pts_canvas[0].toPoint()
                p1 = pts_canvas[1].toPoint()
                peintre.drawRect(QRect(p0, p1))

            elif isinstance(forme, FormeCercle):
                peintre.setPen(stylo)
                peintre.setBrush(brosse)
                centre = pts_canvas[0]
                bord   = pts_canvas[1]
                rayon  = math.hypot(bord.x() - centre.x(), bord.y() - centre.y())
                peintre.drawEllipse(centre, rayon, rayon)

            elif isinstance(forme, FormeLigne):
                # Pas de remplissage pour un segment
                peintre.setPen(stylo)
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                peintre.drawLine(pts_canvas[0], pts_canvas[1])

            elif isinstance(forme, FormePolygone):
                peintre.setPen(stylo)
                peintre.setBrush(brosse)
                polygone = QPolygon([p.toPoint() for p in pts_canvas])
                peintre.drawPolygon(polygone)

            elif isinstance(forme, FormeLignesConnectees):
                peintre.setPen(stylo)
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                polyligne = QPolygon([p.toPoint() for p in pts_canvas])
                peintre.drawPolyline(polyligne)

    def _dessiner_bulles(self, peintre: QPainter) -> None:
        """Dessine tous les call-out coudés et les bulles de légende."""
        for bulle in self._bulles:
            self._dessiner_une_bulle(
                peintre, bulle, selectionne=(bulle is self._bulle_selectionnee)
            )

        # --- Ghost CALLOUT : bulle fantôme identique à la bulle finale ---
        if self._ancrage_en_cours is not None and self._mode == ModeCanvas.CALLOUT:
            if self._pos_souris is not None and self._echantillon_en_attente is not None:
                curseur     = QPointF(float(self._pos_souris.x()), float(self._pos_souris.y()))
                curseur_img = self._canvas_vers_image(curseur)

                # Position bulle en coords image : centrée horizontalement sur le curseur
                bw_img = self._bw_callout_canvas() / self._echelle if self._echelle > 0 else LARGEUR_BULLE
                pos_img = (curseur_img.x() - bw_img / 2, curseur_img.y())

                # BulleLegende temporaire avec l'échantillon réel → rendu 100% identique
                ech = self._echantillon_en_attente
                bulle_ghost = BulleLegende(
                    ancrage=self._ancrage_en_cours,
                    position=pos_img,
                    couleur_rgb=ech.couleur,
                    echantillon=ech,
                )

                # Dessiner avec opacité réduite pour l'effet "fantôme"
                peintre.setOpacity(0.65)
                self._dessiner_une_bulle(peintre, bulle_ghost)
                peintre.setOpacity(1.0)

    def _dessiner_une_bulle(
        self, peintre: QPainter, bulle: BulleLegende, selectionne: bool = False
    ) -> None:
        """
        Dessine un call-out (pied + segment diagonal) et sa bulle de légende.

        Géométrie du call-out :
        - Segment 1 (pied) : bord de la bulle → point_depart (horizontal, longueur pied_longueur)
        - Segment 2        : point_depart → ancrage (ligne droite)

        Paramètres
        ----------
        peintre    : QPainter actif dans le paintEvent
        bulle      : BulleLegende à dessiner
        selectionne: True si la bulle est sélectionnée (bordure plus épaisse)
        """
        couleur = QColor(*bulle.couleur_rgb)

        # --- Calcul de la géométrie ---
        anc, bord_bulle, point_depart, rect_bulle = self._calculer_geometrie_callout(bulle)

        # --- Call-out (pied perpendiculaire + segment diagonal vers ancrage) ---
        epaisseur_trait = max(1.0, EPAISSEUR_TRAIT * self._echelle)
        peintre.setPen(QPen(couleur, epaisseur_trait))
        peintre.setBrush(Qt.BrushStyle.NoBrush)

        # Segment 1 : bord de la bulle → point_depart (pied horizontal)
        peintre.drawLine(bord_bulle, point_depart)
        # Segment 2 : point_depart → ancrage (trait diagonal)
        peintre.drawLine(point_depart, anc)

        # --- Pastille sur le point d'ancrage ---
        peintre.setBrush(QBrush(couleur))
        peintre.drawEllipse(anc, 3.0, 3.0)
        peintre.setBrush(Qt.BrushStyle.NoBrush)

        # --- Rectangle de la bulle (fond blanc, bordure colorée) ---
        epaisseur_bordure = max(2.5, (4.0 if selectionne else 2.5) * self._echelle)
        peintre.setPen(QPen(couleur, epaisseur_bordure))
        peintre.setBrush(QBrush(Qt.GlobalColor.white))
        peintre.drawRect(rect_bulle)

        # --- Texte centré dans la bulle ---
        if bulle.echantillon is None:
            # Aucun échantillon associé : texte gris italique
            font_invite = QFont("Helvetica", 8, QFont.Weight.Normal)
            font_invite.setItalic(True)
            peintre.setFont(font_invite)
            peintre.setPen(QPen(QColor(150, 150, 150)))
            peintre.drawText(rect_bulle, Qt.AlignmentFlag.AlignCenter, "Sans échantillon")
        else:
            ech = bulle.echantillon
            marge_interne = (PADDING_BULLE / 2) * self._echelle
            bx = rect_bulle.x()
            by = rect_bulle.y()
            bw = rect_bulle.width()
            y_texte = by + marge_interne
            peintre.setPen(QPen(couleur))

            # Taille de police en pixels canvas : 8pt PDF × (canvas_px / pdf_pt)
            # On utilise setPixelSize pour éviter la conversion DPI de Qt
            # (QFont("Helvetica", N) interprète N en pt Qt → N × DPI/72 px, soit +33% à 96 DPI)
            ep = self._echelle_pdf()
            taille_px = max(4, round(8 * self._echelle / ep)) if ep > 0 else max(4, round(8 * self._echelle))

            # Une seule fonte : Helvetica normal (identique au rendu Acrobat du PDF)
            font_normal = QFont("Helvetica", -1, QFont.Weight.Normal)
            font_normal.setPixelSize(taille_px)

            # Séparateur ASCII identique au PDF ("- " × 8, strippé)
            separateur = ("- " * 8).strip()
            mention_visible = bool(ech.mention and ech.mention.strip())

            # Lignes à afficher dans l'ordre PDF : corps + séparateur + mention
            textes = [t for t in (ech.texte_ligne1, ech.texte_ligne2, ech.texte_ligne3) if t and t.strip()]
            if mention_visible:
                textes.append(separateur)
                textes.append(ech.mention)

            hauteur_ligne_px = float(QFontMetrics(font_normal).height())
            peintre.setFont(font_normal)
            for texte in textes:
                # Mesure avec word-wrap pour obtenir la hauteur réelle occupée
                rect_mesure = peintre.boundingRect(
                    QRectF(bx + 2, y_texte, bw - 4, 10000),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                    texte,
                )
                hauteur_zone = max(hauteur_ligne_px, rect_mesure.height())
                rect_ligne = QRectF(bx + 2, y_texte, bw - 4, hauteur_zone)
                peintre.drawText(
                    rect_ligne,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                    texte,
                )
                y_texte += hauteur_zone

    def _dessiner_poignees(self, peintre: QPainter) -> None:
        """
        Dessine les poignées de contrôle (petits carrés blancs bordés de noir)
        pour chaque forme sélectionnée, et les poignées de la bulle sélectionnée
        (ancrage + pied).

        Les points sont stockés en coordonnées image originale ; ils sont convertis
        en coordonnées canvas pour le rendu.
        """
        demi = TAILLE_POIGNEE // 2

        # --- Poignées des formes sélectionnées ---
        for forme in self._formes_selectionnees:
            for pt_img in forme.points:
                # Conversion coordonnées image → canvas
                pt_canvas = self._image_vers_canvas(QPointF(*pt_img))
                rect_poignee = QRectF(
                    pt_canvas.x() - demi,
                    pt_canvas.y() - demi,
                    TAILLE_POIGNEE,
                    TAILLE_POIGNEE,
                )
                peintre.setPen(QPen(QColor("black"), EPAISSEUR_POIGNEE))
                peintre.setBrush(QBrush(Qt.GlobalColor.white))
                peintre.drawRect(rect_poignee)

        # --- Poignées de la bulle sélectionnée ---
        if self._bulle_selectionnee is not None:
            bulle = self._bulle_selectionnee
            anc, bord_bulle, point_depart, rect_bulle = self._calculer_geometrie_callout(bulle)

            # Poignée d'ancrage (carré blanc/noir standard)
            rect_anc = QRectF(
                anc.x() - demi, anc.y() - demi,
                TAILLE_POIGNEE, TAILLE_POIGNEE,
            )
            peintre.setPen(QPen(QColor("black"), EPAISSEUR_POIGNEE))
            peintre.setBrush(QBrush(Qt.GlobalColor.white))
            peintre.drawRect(rect_anc)

            # Poignée de la position de la bulle (coin supérieur gauche)
            coin_hg = QPointF(rect_bulle.x(), rect_bulle.y())
            rect_pos = QRectF(
                coin_hg.x() - demi, coin_hg.y() - demi,
                TAILLE_POIGNEE, TAILLE_POIGNEE,
            )
            peintre.setPen(QPen(QColor("black"), EPAISSEUR_POIGNEE))
            peintre.setBrush(QBrush(Qt.GlobalColor.white))
            peintre.drawRect(rect_pos)

            # Poignée du pied (orange, pour distinguer)
            couleur_pied = QColor(255, 165, 0)
            rect_pied = QRectF(
                point_depart.x() - demi, point_depart.y() - demi,
                TAILLE_POIGNEE, TAILLE_POIGNEE,
            )
            peintre.setPen(QPen(QColor("black"), EPAISSEUR_POIGNEE))
            peintre.setBrush(QBrush(couleur_pied))
            peintre.drawRect(rect_pied)

    def _dessiner_ghost(self, peintre: QPainter) -> None:
        """
        Dessine l'aperçu fantôme de la forme en cours de tracé.

        Les points de ``_points_en_cours`` sont en coordonnées image originale.
        Ils sont convertis en canvas avant le rendu. La position du curseur
        (``_pos_souris``) est déjà en coordonnées canvas.

        Stratégie par mode :
        - DESSIN_RECT / DESSIN_CERCLE / DESSIN_LIGNE : nécessitent un point
          de départ ET la position courante du curseur. Ghost à 10% opacité.
        - DESSIN_POLYGONE / LIGNES_CONNECTEES : les points et segments déjà
          validés sont toujours dessinés (opacité 100%) dès le premier clic ;
          seul le segment vers le curseur est en ghost (40% opacité, tirets).
          Cela garantit la visibilité même si le tracking souris n'est pas encore
          déclenché.
        """
        pts_img = self._points_en_cours

        # --- DESSIN_RECT / DESSIN_CERCLE / DESSIN_LIGNE ---
        # Ces modes nécessitent impérativement un point de départ ET le curseur.
        if self._mode in (ModeCanvas.DESSIN_RECT, ModeCanvas.DESSIN_CERCLE, ModeCanvas.DESSIN_LIGNE):
            if not pts_img or self._pos_souris is None:
                return  # pas de ghost possible sans point de départ ou sans curseur

            couleur = QColor(*self._couleur_active)
            # Le curseur est en coordonnées canvas
            curseur = QPointF(float(self._pos_souris.x()), float(self._pos_souris.y()))
            # Convertir le premier point image → canvas pour le rendu
            p0_canvas = self._image_vers_canvas(QPointF(*pts_img[0]))

            peintre.setOpacity(0.10)
            peintre.setPen(QPen(couleur, self._epaisseur_active * self._zoom))
            peintre.setBrush(QBrush(couleur))

            if self._mode == ModeCanvas.DESSIN_RECT:
                rect = QRectF(p0_canvas, curseur).normalized()
                peintre.drawRect(rect)

            elif self._mode == ModeCanvas.DESSIN_CERCLE:
                rayon_vecteur = curseur - p0_canvas
                r = (rayon_vecteur.x() ** 2 + rayon_vecteur.y() ** 2) ** 0.5
                peintre.drawEllipse(p0_canvas, r, r)

            elif self._mode == ModeCanvas.DESSIN_LIGNE:
                peintre.drawLine(p0_canvas, curseur)

            # Rétablir l'opacité normale
            peintre.setOpacity(1.0)
            return

        # --- DESSIN_POLYGONE / LIGNES_CONNECTEES ---
        # Les points validés sont toujours visibles (opacité pleine) dès le premier clic.
        # Le segment ghost vers le curseur n'apparaît que si le curseur est connu.
        if self._mode in (ModeCanvas.DESSIN_POLYGONE, ModeCanvas.LIGNES_CONNECTEES):
            if not pts_img:
                return  # rien à dessiner avant le premier clic

            couleur = QColor(*self._couleur_active)

            # Convertir tous les points image → canvas pour le rendu
            pts_canvas = [self._image_vers_canvas(QPointF(*p)) for p in pts_img]

            # --- Points validés et segments entre eux : toujours opaques ---
            peintre.setOpacity(1.0)
            peintre.setPen(QPen(couleur, self._epaisseur_active * self._zoom))
            peintre.setBrush(QBrush(couleur))

            # Dessiner un disque de RAYON_POINT_GHOST px de rayon sur chaque point validé (canvas)
            for pt_c in pts_canvas:
                peintre.drawEllipse(pt_c, RAYON_POINT_GHOST, RAYON_POINT_GHOST)

            # Segments entre les points validés (canvas)
            if len(pts_canvas) >= 2:
                for i in range(len(pts_canvas) - 1):
                    peintre.drawLine(pts_canvas[i], pts_canvas[i + 1])

            # --- Segment ghost vers le curseur (seulement si curseur connu) ---
            if self._pos_souris is not None:
                curseur = QPointF(
                    float(self._pos_souris.x()),
                    float(self._pos_souris.y()),
                )
                dernier = pts_canvas[-1]

                # Ghost semi-transparent en tirets : distinct du tracé définitif
                peintre.setOpacity(0.40)
                peintre.setPen(
                    QPen(couleur, EPAISSEUR_GHOST, Qt.PenStyle.DashLine)
                )
                peintre.setBrush(Qt.BrushStyle.NoBrush)

                # Segment ghost : dernier point validé → curseur
                peintre.drawLine(dernier, curseur)

                # Fermeture ghost pour polygone uniquement (curseur → premier point)
                if self._mode == ModeCanvas.DESSIN_POLYGONE and len(pts_canvas) >= 2:
                    premier = pts_canvas[0]
                    peintre.drawLine(curseur, premier)

            # Rétablir l'opacité normale impérativement
            peintre.setOpacity(1.0)
