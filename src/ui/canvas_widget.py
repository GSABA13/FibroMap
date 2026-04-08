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
    ModeCanvas.ROGNAGE           : définition de la zone de rognage (cliquer-glisser)
"""

import logging
import math
from enum import Enum

from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QPointF, QRectF, QSizeF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPixmap, QPolygon, QCursor
)
from PyQt6.QtWidgets import QWidget, QMenu

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
)
from src.utils.pdf_to_image import pdf_vers_pixmap

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
    ROGNAGE           = "rognage"


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
    _forme_selectionnee : FormeBase | None
        Forme actuellement sélectionnée.
    _indice_poignee : int
        Indice du point de contrôle en cours de drag (-1 = aucun).
    _drag_corps : bool
        True si l'on déplace toute la forme (et non une poignée).
    _pos_drag_debut : QPoint | None
        Position de la souris au début d'un drag de corps.
    _points_en_cours : list[tuple[float, float]]
        Points de la forme en cours de tracé.
    _pos_souris : QPoint | None
        Dernière position connue de la souris (pour le ghost).
    _zoom : float
        Facteur de zoom courant (1.0 = 100%).
    _offset : QPointF
        Décalage de l'image pour le pan (réservé usage futur).
    _rect_rognage : QRectF | None
        Rectangle de rognage en coordonnées image originale (None = pas de rognage).
    _rognage_en_cours : QPointF | None
        Point de départ du tracé de rognage en cours.
    """

    # Signal émis quand le zoom change, avec la valeur (0.0–5.0)
    zoom_change = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # --- Plan ---
        self._pixmap: QPixmap | None = None

        # --- Mode de dessin ---
        self._mode: ModeCanvas = ModeCanvas.SELECTION

        # --- Transparence (conservé pour compatibilité) ---
        self._semi_transparent: bool = False

        # --- Couleur et transparence actives ---
        self._couleur_active: tuple = COULEUR_VERTE   # RGB tuple — couleur de la prochaine forme

        # --- Formes dessinées ---
        self._formes: list[FormeBase] = []
        self._forme_selectionnee: FormeBase | None = None

        # --- État du drag ---
        self._indice_poignee: int = -1          # -1 = aucune poignée draguée
        self._drag_corps: bool = False           # True = on déplace toute la forme
        self._pos_drag_debut: QPoint | None = None

        # --- Tracé en cours ---
        self._points_en_cours: list[tuple[float, float]] = []
        self._pos_souris: QPoint | None = None

        # --- Zoom ---
        self._zoom: float = ZOOM_DEFAUT          # Facteur de zoom courant
        self._offset: QPointF = QPointF(0, 0)   # Décalage de l'image (pan futur)

        # --- Rognage ---
        self._rect_rognage: QRectF | None = None          # Rectangle de rognage (coordonnées image originale)
        self._rognage_en_cours: QPointF | None = None     # Point de départ du tracé de rognage

        # Fond par défaut du widget
        self.setAutoFillBackground(False)
        # Nécessaire pour recevoir les événements clavier
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

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
        else:
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
            Identifiant du mode (ex. "rect", "cercle", "selection", "rognage", …).
        """
        self._mode = ModeCanvas(mode)
        # Abandon d'un tracé en cours si on change de mode
        self._points_en_cours.clear()

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
        """Supprime toutes les formes de la planche et réinitialise la sélection."""
        self._formes.clear()
        self._forme_selectionnee = None
        self._points_en_cours.clear()
        self.update()

    # ------------------------------------------------------------------
    # Méthodes publiques de zoom
    # ------------------------------------------------------------------

    def zoom_in(self) -> None:
        """Augmente le zoom d'un cran (facteur ZOOM_FACTEUR_MOLETTE)."""
        self._appliquer_zoom(self._zoom * ZOOM_FACTEUR_MOLETTE, centre=None)

    def zoom_out(self) -> None:
        """Diminue le zoom d'un cran (facteur 1/ZOOM_FACTEUR_MOLETTE)."""
        self._appliquer_zoom(self._zoom / ZOOM_FACTEUR_MOLETTE, centre=None)

    def zoom_reset(self) -> None:
        """Remet le zoom à 100% et recentre l'image."""
        self._appliquer_zoom(ZOOM_DEFAUT, centre=None)
        self._offset = QPointF(0, 0)
        self.update()

    def _appliquer_zoom(self, nouveau_zoom: float, centre: QPointF | None) -> None:
        """
        Applique le facteur de zoom en le clampant entre ZOOM_MIN et ZOOM_MAX.
        Si `centre` est fourni, ajuste _offset pour que le zoom soit centré sur ce point.

        Paramètres
        ----------
        nouveau_zoom : float
            Nouveau facteur de zoom souhaité.
        centre : QPointF | None
            Point autour duquel centrer le zoom (coordonnées widget), ou None.
        """
        zoom_clamp = max(ZOOM_MIN, min(ZOOM_MAX, nouveau_zoom))
        if centre is not None:
            # Ajuster l'offset pour centrer le zoom sur le curseur
            facteur = zoom_clamp / self._zoom
            self._offset = QPointF(
                centre.x() - facteur * (centre.x() - self._offset.x()),
                centre.y() - facteur * (centre.y() - self._offset.y()),
            )
        self._zoom = zoom_clamp
        self.zoom_change.emit(self._zoom)
        self.update()

    # ------------------------------------------------------------------
    # Méthodes publiques de rognage
    # ------------------------------------------------------------------

    def reinitialiser_rognage(self) -> None:
        """Supprime le rognage et affiche l'image entière."""
        self._rect_rognage = None
        self.update()

    def obtenir_rect_rognage(self) -> QRectF | None:
        """Retourne le rectangle de rognage en coordonnées image originale, ou None."""
        return self._rect_rognage

    # ------------------------------------------------------------------
    # Événements souris
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:  # noqa: N802
        """Zoom centré sur la position du curseur à la molette."""
        delta = event.angleDelta().y()
        if delta > 0:
            facteur = ZOOM_FACTEUR_MOLETTE
        else:
            facteur = 1.0 / ZOOM_FACTEUR_MOLETTE
        centre = QPointF(event.position())
        self._appliquer_zoom(self._zoom * facteur, centre=centre)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Gère le clic souris selon le mode actif."""
        pos = event.pos()

        # --- Bouton DROIT : menu contextuel en mode sélection ---
        if event.button() == Qt.MouseButton.RightButton:
            if self._mode == ModeCanvas.SELECTION:
                forme = self._trouver_forme_sous_curseur(pos)
                if forme is not None:
                    self._menu_contextuel(pos, forme)
            return

        # --- Bouton GAUCHE ---
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pt = (float(pos.x()), float(pos.y()))

        if self._mode == ModeCanvas.SELECTION:
            self._selectionner_forme(pos)

        elif self._mode in (ModeCanvas.DESSIN_RECT, ModeCanvas.DESSIN_CERCLE):
            # Premier point : début du tracé
            self._points_en_cours = [pt]

        elif self._mode == ModeCanvas.DESSIN_LIGNE:
            self._points_en_cours.append(pt)
            if len(self._points_en_cours) == 2:
                # Deux points suffisent pour créer le segment
                nouvelle_forme = FormeLigne(
                    points=list(self._points_en_cours),
                    couleur_rgb=self._couleur_active,
                    alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                )
                self._formes.append(nouvelle_forme)
                logger.debug("FormeLigne créée : %s", nouvelle_forme.id)
                self._points_en_cours.clear()

        elif self._mode in (ModeCanvas.DESSIN_POLYGONE, ModeCanvas.LIGNES_CONNECTEES):
            # Accumulation des points (la forme est créée au double-clic)
            self._points_en_cours.append(pt)

        elif self._mode == ModeCanvas.ROGNAGE:
            # Début du tracé du rectangle de rognage
            self._rognage_en_cours = QPointF(float(pos.x()), float(pos.y()))

        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Met à jour la position souris et gère les déplacements."""
        self._pos_souris = event.pos()

        if self._mode == ModeCanvas.SELECTION and self._forme_selectionnee is not None:
            pos = event.pos()

            if self._drag_corps and self._pos_drag_debut is not None:
                # --- Déplacement de toute la forme ---
                delta_x = float(pos.x() - self._pos_drag_debut.x())
                delta_y = float(pos.y() - self._pos_drag_debut.y())
                pts = self._forme_selectionnee.points
                self._forme_selectionnee.points = [
                    (p[0] + delta_x, p[1] + delta_y) for p in pts
                ]
                self._pos_drag_debut = pos

            elif self._indice_poignee >= 0:
                # --- Déplacement d'un point de contrôle individuel ---
                i = self._indice_poignee
                if i < len(self._forme_selectionnee.points):
                    self._forme_selectionnee.points[i] = (
                        float(pos.x()),
                        float(pos.y()),
                    )

        elif self._mode == ModeCanvas.ROGNAGE:
            # En mode rognage, on met à jour uniquement _pos_souris
            # (déjà fait ci-dessus) pour afficher le ghost du rectangle
            pass

        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Finalise le tracé ou le drag en cours."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()
        pt = (float(pos.x()), float(pos.y()))

        if (
            self._mode in (ModeCanvas.DESSIN_RECT, ModeCanvas.DESSIN_CERCLE)
            and len(self._points_en_cours) == 1
        ):
            # Le deuxième point est la position de relâchement
            self._points_en_cours.append(pt)
            p0 = self._points_en_cours[0]
            p1 = self._points_en_cours[1]

            # Créer la forme uniquement si les deux points sont distincts
            if p0 != p1:
                if self._mode == ModeCanvas.DESSIN_RECT:
                    nouvelle_forme = FormeRect(
                        points=[p0, p1],
                        couleur_rgb=self._couleur_active,
                        alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                    )
                    self._formes.append(nouvelle_forme)
                    logger.debug("FormeRect créée : %s", nouvelle_forme.id)
                else:
                    nouvelle_forme = FormeCercle(
                        points=[p0, p1],
                        couleur_rgb=self._couleur_active,
                        alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
                    )
                    self._formes.append(nouvelle_forme)
                    logger.debug("FormeCercle créée : %s", nouvelle_forme.id)

            self._points_en_cours.clear()

        elif self._mode == ModeCanvas.SELECTION:
            # Fin du drag
            self._drag_corps = False
            self._indice_poignee = -1
            self._pos_drag_debut = None

        elif self._mode == ModeCanvas.ROGNAGE and self._rognage_en_cours is not None:
            fin = QPointF(float(pos.x()), float(pos.y()))
            debut = self._rognage_en_cours
            if debut != fin:
                # Convertir les coordonnées écran → coordonnées image originale
                rect_ecran = QRectF(debut, fin).normalized()
                self._rect_rognage = self._ecran_vers_image(rect_ecran)
            self._rognage_en_cours = None

        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        """Ferme le polygone ou termine la polyligne au double-clic."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._mode == ModeCanvas.DESSIN_POLYGONE and len(self._points_en_cours) >= 3:
            nouvelle_forme = FormePolygone(
                points=list(self._points_en_cours),
                couleur_rgb=self._couleur_active,
                alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
            )
            self._formes.append(nouvelle_forme)
            logger.debug("FormePolygone créée : %s", nouvelle_forme.id)
            self._points_en_cours.clear()

        elif (
            self._mode == ModeCanvas.LIGNES_CONNECTEES
            and len(self._points_en_cours) >= 2
        ):
            nouvelle_forme = FormeLignesConnectees(
                points=list(self._points_en_cours),
                couleur_rgb=self._couleur_active,
                alpha=ALPHA_SEMI if self._semi_transparent else ALPHA_PLEIN,
            )
            self._formes.append(nouvelle_forme)
            logger.debug("FormeLignesConnectees créée : %s", nouvelle_forme.id)
            self._points_en_cours.clear()

        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Supprime la forme sélectionnée sur appui de la touche Suppr."""
        if event.key() == Qt.Key.Key_Delete:
            if self._forme_selectionnee is not None:
                try:
                    self._formes.remove(self._forme_selectionnee)
                    logger.debug(
                        "Forme supprimée : %s", self._forme_selectionnee.id
                    )
                except ValueError:
                    pass
                self._forme_selectionnee = None
                self.update()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Logique de sélection
    # ------------------------------------------------------------------

    def _trouver_forme_sous_curseur(self, pos: QPoint) -> "FormeBase | None":
        """
        Renvoie la première forme (priorité aux formes du dessus) dont le
        bounding-box contient ``pos`` avec une tolérance de ``TOLERANCE_HIT`` px.
        """
        for forme in reversed(self._formes):
            if self._point_dans_forme(pos, forme):
                return forme
        return None

    def _selectionner_forme(self, pos: QPoint) -> None:
        """
        Sélectionne la forme sous le curseur et prépare le drag.

        Si le curseur est sur une poignée, initialise ``_indice_poignee``.
        Sinon, initialise ``_drag_corps``.
        Si aucune forme n'est touchée, désélectionne tout.
        """
        # Réinitialiser l'état de drag
        self._drag_corps = False
        self._indice_poignee = -1
        self._pos_drag_debut = None

        for forme in reversed(self._formes):
            # Vérification poignées en priorité
            for i, pt in enumerate(forme.points):
                demi = TAILLE_POIGNEE // 2
                rect_poignee = QRect(
                    int(pt[0]) - demi,
                    int(pt[1]) - demi,
                    TAILLE_POIGNEE,
                    TAILLE_POIGNEE,
                )
                if rect_poignee.contains(pos):
                    self._forme_selectionnee = forme
                    self._indice_poignee = i
                    return

            # Vérification bounding-box
            if self._point_dans_forme(pos, forme):
                self._forme_selectionnee = forme
                self._drag_corps = True
                self._pos_drag_debut = pos
                return

        # Aucune forme touchée
        self._forme_selectionnee = None

    @staticmethod
    def _point_dans_forme(pos: QPoint, forme: FormeBase) -> bool:
        """
        Teste si ``pos`` se trouve dans le bounding-box de ``forme``
        avec une tolérance de ``TOLERANCE_HIT`` pixels.
        """
        pts = forme.points
        if not pts:
            return False

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        t = TOLERANCE_HIT

        rect = QRect(
            int(min(xs)) - t,
            int(min(ys)) - t,
            int(max(xs) - min(xs)) + 2 * t,
            int(max(ys) - min(ys)) + 2 * t,
        )
        return rect.contains(pos)

    # ------------------------------------------------------------------
    # Menu contextuel
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
            try:
                self._formes.remove(forme)
            except ValueError:
                pass
            if self._forme_selectionnee is forme:
                self._forme_selectionnee = None

        self.update()

    # ------------------------------------------------------------------
    # Conversion de coordonnées
    # ------------------------------------------------------------------

    def _ecran_vers_image(self, rect_ecran: QRectF) -> QRectF:
        """
        Convertit un rectangle en coordonnées écran vers coordonnées image originale.
        Tient compte du zoom et de l'offset courants.

        Paramètres
        ----------
        rect_ecran : QRectF
            Rectangle exprimé en coordonnées widget (pixels écran).

        Retourne
        --------
        QRectF
            Rectangle dans l'espace de l'image originale, clampé dans ses limites.
        """
        if self._pixmap is None:
            logger.warning("_ecran_vers_image appelé sans pixmap chargé.")
            return rect_ecran
        x = (rect_ecran.x() - self._offset.x()) / self._zoom
        y = (rect_ecran.y() - self._offset.y()) / self._zoom
        w = rect_ecran.width() / self._zoom
        h = rect_ecran.height() / self._zoom
        # Clamp dans les limites de l'image originale
        pw = float(self._pixmap.width())
        ph = float(self._pixmap.height())
        x = max(0.0, min(x, pw))
        y = max(0.0, min(y, ph))
        w = min(w, pw - x)
        h = min(h, ph - y)
        return QRectF(x, y, w, h)

    # ------------------------------------------------------------------
    # Rendu — paintEvent et méthodes _dessiner_*
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        """
        Orchestre le rendu dans l'ordre strict :
        1. Fond gris
        2. Plan (QPixmap) centré avec bordure noire, avec prise en compte
           du zoom et du rognage éventuel
        3. Formes colorées
        4. Poignées de sélection
        5. Ghost de la forme en cours de tracé
        """
        with QPainter(self) as peintre:
            peintre.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 1. Fond gris clair
            peintre.fillRect(self.rect(), QColor(*COULEUR_FOND_CANVAS))

            if self._pixmap is not None and not self._pixmap.isNull():
                # Zone disponible pour le plan (avec marge sur chaque côté)
                zone_plan = self.rect().adjusted(
                    MARGE_PLAN, MARGE_PLAN, -MARGE_PLAN, -MARGE_PLAN
                )

                # Bordure noire autour de la zone plan
                stylo_bordure = QPen(QColor("black"), EPAISSEUR_TRAIT)
                peintre.setPen(stylo_bordure)
                peintre.drawRect(zone_plan)

                # --- Détermination de la source : image rognée ou entière ---
                if self._rect_rognage is not None:
                    src_rect = self._rect_rognage.toRect()
                    taille_src = QSizeF(
                        self._rect_rognage.width(),
                        self._rect_rognage.height(),
                    )
                else:
                    src_rect = self._pixmap.rect()
                    taille_src = QSizeF(self._pixmap.size())

                # --- Calcul de la taille affichée avec zoom + KeepAspectRatio ---
                zone_plan_qsizef = QSizeF(zone_plan.size())

                # Appliquer le zoom, puis ramener dans les limites de la zone plan
                taille_zoomee = taille_src.scaled(
                    zone_plan_qsizef.width() * self._zoom,
                    zone_plan_qsizef.height() * self._zoom,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                # Clamp pour ne pas dépasser la zone plan visible
                taille_affichee = taille_zoomee.scaled(
                    zone_plan_qsizef,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )

                # Centrage dans la zone plan
                x_centre = zone_plan.x() + (zone_plan_qsizef.width() - taille_affichee.width()) / 2
                y_centre = zone_plan.y() + (zone_plan_qsizef.height() - taille_affichee.height()) / 2
                rect_dest = QRectF(
                    x_centre,
                    y_centre,
                    taille_affichee.width(),
                    taille_affichee.height(),
                )

                # 2. Dessin du pixmap (éventuellement rogné) mis à l'échelle et centré
                peintre.drawPixmap(rect_dest.toRect(), self._pixmap, src_rect)

            else:
                # Aucun plan chargé : message d'invite centré
                peintre.setPen(QColor(*COULEUR_TEXTE_INVITE))
                peintre.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    "Ouvrir un plan via Fichier \u2192 Ouvrir Plan",
                )

            # 3. Formes dessinées
            self._dessiner_formes(peintre)

            # 4. Poignées de sélection
            self._dessiner_poignees(peintre)

            # 5. Ghost de la forme en cours
            self._dessiner_ghost(peintre)

    def _dessiner_formes(self, peintre: QPainter) -> None:
        """
        Dessine toutes les formes validées de ``_formes``.

        Chaque forme est rendue avec :
        - un contour de couleur pleine (alpha=255)
        - un remplissage coloré semi-transparent ou plein selon ``forme.alpha``
        """
        for forme in self._formes:
            pts = forme.points
            if len(pts) < 2:
                continue  # forme incomplète, on ignore

            # Couleur de remplissage avec transparence configurée
            couleur_remplissage = QColor(*forme.couleur_rgb)
            couleur_remplissage.setAlpha(forme.alpha)

            # Contour toujours opaque
            couleur_contour = QColor(*forme.couleur_rgb)
            couleur_contour.setAlpha(255)

            stylo = QPen(couleur_contour, EPAISSEUR_TRAIT)
            brosse = QBrush(couleur_remplissage)

            if isinstance(forme, FormeRect):
                peintre.setPen(stylo)
                peintre.setBrush(brosse)
                p0 = QPoint(int(pts[0][0]), int(pts[0][1]))
                p1 = QPoint(int(pts[1][0]), int(pts[1][1]))
                peintre.drawRect(QRect(p0, p1))

            elif isinstance(forme, FormeCercle):
                peintre.setPen(stylo)
                peintre.setBrush(brosse)
                cx, cy = pts[0]
                bx, by = pts[1]
                rayon = int(math.hypot(bx - cx, by - cy))
                peintre.drawEllipse(QPoint(int(cx), int(cy)), rayon, rayon)

            elif isinstance(forme, FormeLigne):
                # Pas de remplissage pour un segment
                peintre.setPen(stylo)
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                peintre.drawLine(
                    QPoint(int(pts[0][0]), int(pts[0][1])),
                    QPoint(int(pts[1][0]), int(pts[1][1])),
                )

            elif isinstance(forme, FormePolygone):
                peintre.setPen(stylo)
                peintre.setBrush(brosse)
                polygone = QPolygon(
                    [QPoint(int(p[0]), int(p[1])) for p in pts]
                )
                peintre.drawPolygon(polygone)

            elif isinstance(forme, FormeLignesConnectees):
                peintre.setPen(stylo)
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                polyligne = QPolygon(
                    [QPoint(int(p[0]), int(p[1])) for p in pts]
                )
                peintre.drawPolyline(polyligne)

    def _dessiner_poignees(self, peintre: QPainter) -> None:
        """
        Dessine les poignées de contrôle (petits carrés blancs bordés de noir)
        autour de chaque point de la forme sélectionnée.
        """
        if self._forme_selectionnee is None:
            return

        demi = TAILLE_POIGNEE // 2
        # Utilisation de EPAISSEUR_POIGNEE (constante) plutôt qu'un entier magique
        stylo_poignee = QPen(QColor("black"), EPAISSEUR_POIGNEE)
        brosse_poignee = QBrush(QColor("white"))

        peintre.setPen(stylo_poignee)
        peintre.setBrush(brosse_poignee)

        for pt in self._forme_selectionnee.points:
            rect_poignee = QRect(
                int(pt[0]) - demi,
                int(pt[1]) - demi,
                TAILLE_POIGNEE,
                TAILLE_POIGNEE,
            )
            peintre.drawRect(rect_poignee)

    def _dessiner_ghost(self, peintre: QPainter) -> None:
        """
        Dessine l'aperçu (ghost) de la forme en cours de tracé.

        Utilise un stylo pointillé gris sans remplissage pour les formes classiques,
        et un stylo pointillé bleu pour le rectangle de rognage.
        """
        # --- Ghost de rognage ---
        if (
            self._mode == ModeCanvas.ROGNAGE
            and self._rognage_en_cours is not None
            and self._pos_souris is not None
        ):
            stylo_rognage = QPen(QColor("blue"), EPAISSEUR_GHOST, Qt.PenStyle.DashLine)
            peintre.setPen(stylo_rognage)
            peintre.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(
                self._rognage_en_cours,
                QPointF(float(self._pos_souris.x()), float(self._pos_souris.y())),
            ).normalized()
            peintre.drawRect(rect)
            return

        # --- Ghosts des modes simples (rect, cercle, ligne) ---
        # Pour ces modes, on a besoin d'au moins un point ET du curseur
        modes_simples = (ModeCanvas.DESSIN_RECT, ModeCanvas.DESSIN_CERCLE, ModeCanvas.DESSIN_LIGNE)
        if self._mode in modes_simples:
            if not self._points_en_cours or self._pos_souris is None:
                return

            stylo_ghost = QPen(
                Qt.GlobalColor.gray, EPAISSEUR_GHOST, Qt.PenStyle.DashLine
            )
            peintre.setPen(stylo_ghost)
            peintre.setBrush(Qt.BrushStyle.NoBrush)

            souris_x = float(self._pos_souris.x())
            souris_y = float(self._pos_souris.y())

            if self._mode == ModeCanvas.DESSIN_RECT:
                p0 = self._points_en_cours[0]
                p0q = QPoint(int(p0[0]), int(p0[1]))
                p1q = QPoint(int(souris_x), int(souris_y))
                peintre.drawRect(QRect(p0q, p1q))

            elif self._mode == ModeCanvas.DESSIN_CERCLE:
                cx, cy = self._points_en_cours[0]
                rayon = int(math.hypot(souris_x - cx, souris_y - cy))
                peintre.drawEllipse(QPoint(int(cx), int(cy)), rayon, rayon)

            elif self._mode == ModeCanvas.DESSIN_LIGNE:
                p0 = self._points_en_cours[0]
                peintre.drawLine(
                    QPoint(int(p0[0]), int(p0[1])),
                    QPoint(int(souris_x), int(souris_y)),
                )

        # --- LIGNES CONNECTÉES : segments validés (trait solide) + 1 ghost (pointillé) ---
        elif self._mode == ModeCanvas.LIGNES_CONNECTEES and self._points_en_cours:
            couleur_active = QColor(*self._couleur_active)

            # 1. Segments déjà validés (traits solides)
            if len(self._points_en_cours) >= 2:
                stylo_solide = QPen(couleur_active, EPAISSEUR_TRAIT)
                peintre.setPen(stylo_solide)
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                for i in range(len(self._points_en_cours) - 1):
                    p0 = self._points_en_cours[i]
                    p1 = self._points_en_cours[i + 1]
                    peintre.drawLine(
                        QPoint(int(p0[0]), int(p0[1])),
                        QPoint(int(p1[0]), int(p1[1])),
                    )

            # 2. Segment ghost vers le curseur (un seul, pointillé)
            if self._pos_souris is not None:
                dernier = self._points_en_cours[-1]
                stylo_ghost = QPen(couleur_active, EPAISSEUR_GHOST, Qt.PenStyle.DashLine)
                peintre.setPen(stylo_ghost)
                peintre.drawLine(
                    QPoint(int(dernier[0]), int(dernier[1])),
                    self._pos_souris,
                )

        # --- POLYGONE : segments validés (trait solide) + 2 ghosts de fermeture (pointillés) ---
        elif self._mode == ModeCanvas.DESSIN_POLYGONE and self._points_en_cours:
            couleur_active = QColor(*self._couleur_active)

            # 1. Segments déjà validés (traits solides)
            if len(self._points_en_cours) >= 2:
                stylo_solide = QPen(couleur_active, EPAISSEUR_TRAIT)
                peintre.setPen(stylo_solide)
                peintre.setBrush(Qt.BrushStyle.NoBrush)
                for i in range(len(self._points_en_cours) - 1):
                    p0 = self._points_en_cours[i]
                    p1 = self._points_en_cours[i + 1]
                    peintre.drawLine(
                        QPoint(int(p0[0]), int(p0[1])),
                        QPoint(int(p1[0]), int(p1[1])),
                    )

            # 2. Segments ghost pointillés : dernier→curseur et curseur→premier
            if self._pos_souris is not None:
                stylo_ghost = QPen(couleur_active, EPAISSEUR_GHOST, Qt.PenStyle.DashLine)
                peintre.setPen(stylo_ghost)
                dernier = self._points_en_cours[-1]
                premier = self._points_en_cours[0]
                # Dernier point → curseur
                peintre.drawLine(
                    QPoint(int(dernier[0]), int(dernier[1])),
                    self._pos_souris,
                )
                # Curseur → premier point (fermeture visible dès le 2e point posé)
                if len(self._points_en_cours) >= 2:
                    peintre.drawLine(
                        self._pos_souris,
                        QPoint(int(premier[0]), int(premier[1])),
                    )
