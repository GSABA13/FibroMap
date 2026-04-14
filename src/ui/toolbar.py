"""
Barre d'outils principale de l'application Plan Légendage Amiante.

Ce module définit la classe `Toolbar` qui expose :
- un groupe de boutons radio (modes de dessin), chacun avec une icône dessinée via QPainter
- un bouton bascule pour la transparence
- un groupe de 3 boutons de sélection de couleur (vert / orange / rouge)
- des boutons de zoom (zoom avant, zoom arrière, 100%)
- signaux : `mode_change`, `transparence_change`, `couleur_change`,
            `zoom_in`, `zoom_out`, `zoom_reset`

Les icônes sont générées dynamiquement via `_creer_icone()` : chaque fonction de dessin
reçoit un QPainter et la taille cible (24px) pour tracer l'icône sur un QPixmap.
Le fond des icônes est blanc par défaut, bleu clair (#E3F0FF) pour le mode actif.
"""

import logging
import math

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction, QActionGroup, QBrush, QColor, QIcon, QPainter, QPen,
    QPixmap, QPolygon,
)
from PyQt6.QtWidgets import QToolBar

from src.utils.constantes import (
    COULEUR_VERTE, COULEUR_ORANGE, COULEUR_ROUGE, TAILLE_ICONE_TOOLBAR,
    COULEUR_FOND_ICONE, COULEUR_FOND_ICONE_ACTIVE,
)

# Journalisation propre au module
logger = logging.getLogger(__name__)


# ==============================================================================
# Fonctions utilitaires de dessin d'icônes (module-level)
# ==============================================================================

def _creer_icone(dessin_fn, taille: int = TAILLE_ICONE_TOOLBAR, actif: bool = False) -> QIcon:
    """Génère une QIcon à partir d'une fonction de dessin QPainter.

    Paramètres
    ----------
    dessin_fn : callable(QPainter, int)
        Fonction qui dessine l'icône sur le peintre fourni.
    taille : int
        Dimension en pixels du QPixmap carré (par défaut 24).
    actif : bool
        Si True, le fond est bleu clair (#E3F0FF) pour signaler le mode actif.
        Si False (par défaut), le fond est blanc.
    """
    pixmap = QPixmap(taille, taille)
    pixmap.fill(Qt.GlobalColor.transparent)
    with QPainter(pixmap) as peintre:
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Fond blanc ou bleu clair selon l'état actif
        couleur_fond = COULEUR_FOND_ICONE_ACTIVE if actif else COULEUR_FOND_ICONE
        peintre.fillRect(0, 0, taille, taille, QColor(*couleur_fond))
        dessin_fn(peintre, taille)
    return QIcon(pixmap)


def _creer_icone_couleur(rgb: tuple, taille: int = TAILLE_ICONE_TOOLBAR) -> QIcon:
    """
    Génère une icône disque coloré pour le sélecteur de couleur.
    Le disque est plein avec la couleur RGB, contour noir fin, sur fond blanc.

    Paramètres
    ----------
    rgb : tuple[int, int, int]
        Triplet RGB de la couleur à représenter.
    taille : int
        Dimension en pixels du QPixmap carré (par défaut 24).
    """
    def dessiner(peintre: QPainter, t: int) -> None:
        # Fond blanc
        peintre.fillRect(0, 0, t, t, QColor(*COULEUR_FOND_ICONE))
        # Disque coloré
        m = t // 6
        couleur = QColor(*rgb)
        peintre.setPen(QPen(Qt.GlobalColor.black, 1))
        peintre.setBrush(QBrush(couleur))
        peintre.drawEllipse(m, m, t - 2 * m, t - 2 * m)
    return _creer_icone(dessiner, taille)


def _dessiner_selection(peintre: QPainter, t: int) -> None:
    """Flèche de sélection (curseur pointant en haut à gauche)."""
    m = t // 6  # marge ~4px
    # Corps de la flèche : triangle plein noir
    pts = QPolygon([
        QPoint(m,              m),               # pointe
        QPoint(m,              m + t // 2),      # bas gauche
        QPoint(m + t // 4,     m + t // 3),      # encoche
        QPoint(m + t // 2,     m + t // 2),      # bas droite
        QPoint(m + t // 3,     m + t // 4),      # encoche haute
        QPoint(m + t // 2,     m),               # droite haute
    ])
    peintre.setPen(QPen(Qt.GlobalColor.black, 1))
    peintre.setBrush(QBrush(Qt.GlobalColor.black))
    peintre.drawPolygon(pts)


def _dessiner_rectangle(peintre: QPainter, t: int) -> None:
    """Carré vide représentant le mode rectangle."""
    m = t // 6
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    peintre.setBrush(Qt.BrushStyle.NoBrush)
    peintre.drawRect(m, m, t - 2 * m, t - 2 * m)


def _dessiner_cercle(peintre: QPainter, t: int) -> None:
    """Cercle vide représentant le mode cercle."""
    m = t // 6
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    peintre.setBrush(Qt.BrushStyle.NoBrush)
    peintre.drawEllipse(m, m, t - 2 * m, t - 2 * m)


def _dessiner_ligne(peintre: QPainter, t: int) -> None:
    """Trait diagonal du coin haut-gauche au coin bas-droite."""
    m = t // 6
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    peintre.drawLine(m, m, t - m, t - m)


def _dessiner_lignes_connectees(peintre: QPainter, t: int) -> None:
    """Trait brisé en zigzag (3 segments) représentant les lignes connectées."""
    m = t // 6
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    pts = [
        QPoint(m,            t - m),
        QPoint(m + t // 4,   m),
        QPoint(m + t // 2,   t - m),
        QPoint(t - m,        m),
    ]
    for i in range(len(pts) - 1):
        peintre.drawLine(pts[i], pts[i + 1])


def _dessiner_polygone(peintre: QPainter, t: int) -> None:
    """Pentagone régulier vide représentant le mode polygone."""
    cx, cy = t / 2, t / 2
    r = t / 2 - t // 6
    pts = QPolygon([
        QPoint(
            int(cx + r * math.sin(2 * math.pi * i / 5 - math.pi / 2)),
            int(cy + r * math.cos(2 * math.pi * i / 5 - math.pi / 2) * -1),
        )
        for i in range(5)
    ])
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    peintre.setBrush(Qt.BrushStyle.NoBrush)
    peintre.drawPolygon(pts)


def _dessiner_callout(peintre: QPainter, t: int) -> None:
    """Bulle de dialogue rectangulaire avec queue en bas à gauche (mode callout)."""
    m = t // 6
    h_bulle = t // 2
    # Corps de la bulle
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    peintre.setBrush(Qt.BrushStyle.NoBrush)
    peintre.drawRoundedRect(m, m, t - 2 * m, h_bulle, 3, 3)
    # Queue : triangle pointant vers le bas-gauche
    queue = QPolygon([
        QPoint(m + t // 5,  m + h_bulle),   # base gauche
        QPoint(m + t // 3,  m + h_bulle),   # base droite
        QPoint(m,           t - m),          # pointe
    ])
    peintre.drawPolygon(queue)


def _dessiner_rognage(peintre: QPainter, t: int) -> None:
    """Octogone à coins coupés évoquant le rognage du plan."""
    m = t // 6
    c = t // 5  # taille du coin coupé
    pts = QPolygon([
        QPoint(m + c,      m),
        QPoint(t - m - c,  m),
        QPoint(t - m,      m + c),
        QPoint(t - m,      t - m - c),
        QPoint(t - m - c,  t - m),
        QPoint(m + c,      t - m),
        QPoint(m,          t - m - c),
        QPoint(m,          m + c),
    ])
    peintre.setPen(QPen(Qt.GlobalColor.black, 2))
    peintre.setBrush(Qt.BrushStyle.NoBrush)
    peintre.drawPolygon(pts)


# Mapping valeur interne du mode → fonction de dessin de l'icône
_ICONES_MODES: dict = {
    "selection":         _dessiner_selection,
    "rect":              _dessiner_rectangle,
    "cercle":            _dessiner_cercle,
    "ligne":             _dessiner_ligne,
    "lignes_connectees": _dessiner_lignes_connectees,
    "polygone":          _dessiner_polygone,
    "callout":           _dessiner_callout,
    "rognage":           _dessiner_rognage,
}


# ==============================================================================
# Classe Toolbar
# ==============================================================================

class Toolbar(QToolBar):
    """
    Barre d'outils de l'application.

    Signaux
    -------
    mode_change : pyqtSignal(str)
        Émis lorsque l'utilisateur change de mode de dessin.
        Valeurs possibles : "selection", "rect", "cercle", "ligne",
        "lignes_connectees", "polygone", "callout", "rognage".
    transparence_change : pyqtSignal(bool)
        Émis lorsque le bouton bascule Plein / Semi-transparent change d'état.
        True = semi-transparent, False = plein.
    couleur_change : pyqtSignal(tuple)
        Émis lorsque l'utilisateur sélectionne une couleur.
        Valeur : triplet RGB (int, int, int) de la couleur active.
    zoom_in : pyqtSignal()
        Émis lorsque l'utilisateur clique sur le bouton zoom avant.
    zoom_out : pyqtSignal()
        Émis lorsque l'utilisateur clique sur le bouton zoom arrière.
    zoom_reset : pyqtSignal()
        Émis lorsque l'utilisateur clique sur le bouton 100%.
    """

    mode_change = pyqtSignal(str)
    transparence_change = pyqtSignal(bool)
    couleur_change = pyqtSignal(tuple)  # Émet le tuple RGB (int, int, int) de la couleur active
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()
    zoom_reset = pyqtSignal()

    # Définition des modes : (libellé affiché, valeur interne, tooltip)
    _MODES: list[tuple[str, str, str]] = [
        ("Sélection",         "selection",         "Mode sélection : déplacer et redimensionner les annotations"),
        ("Rect",              "rect",              "Mode rectangle : dessiner un rectangle"),
        ("Cercle",            "cercle",            "Mode cercle : dessiner un cercle"),
        ("Ligne",             "ligne",             "Mode ligne : tracer une ligne droite"),
        ("Lignes connectées", "lignes_connectees", "Mode lignes connectées : tracer une polyligne"),
        ("Polygone",          "polygone",          "Mode polygone : dessiner un polygone fermé"),
        ("CallOut",           "callout",           "Mode CallOut : ajouter une bulle de légende"),
        ("Rogner",            "rognage",           "Définir la zone de rognage du plan"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__("Outils", parent)

        # Groupe exclusif : un seul mode actif à la fois
        self._groupe_modes = QActionGroup(self)
        self._groupe_modes.setExclusive(True)

        # Création des actions de mode avec icônes dessinées via QPainter.
        # Les icônes sont d'abord créées sans fond actif ; _rafraichir_icones_modes
        # sera appelé en fin de __init__ pour appliquer le bon fond dès le démarrage.
        self._actions_mode: dict[str, QAction] = {}
        for libelle, valeur, tooltip in self._MODES:
            fn_dessin = _ICONES_MODES.get(valeur)
            if fn_dessin:
                # Texte vide : l'icône seule identifie le mode ; le tooltip apporte le libellé
                action = QAction(_creer_icone(fn_dessin), "", self)
            else:
                # Repli sur le texte si aucune icône n'est définie
                action = QAction(libelle, self)
            action.setCheckable(True)
            action.setToolTip(tooltip)
            # Stocker la valeur interne dans les données de l'action
            action.setData(valeur)
            self._groupe_modes.addAction(action)
            self.addAction(action)
            self._actions_mode[valeur] = action

        # Activer le mode "Sélection" par défaut
        self._actions_mode["selection"].setChecked(True)

        # Séparateur visuel entre les modes et les options
        self.addSeparator()

        # Bouton bascule Plein / Semi-transparent
        self._action_transparence = QAction("Semi-transparent", self)
        self._action_transparence.setCheckable(True)
        self._action_transparence.setToolTip(
            "Basculer entre remplissage plein et semi-transparent"
        )
        self.addAction(self._action_transparence)

        # Séparateur visuel entre la transparence et le groupe couleur
        self.addSeparator()

        # --- Groupe couleur ---
        # Dictionnaire des 3 couleurs disponibles : libellé → tuple RGB
        self._couleurs: dict[str, tuple] = {
            "vert":   COULEUR_VERTE,
            "orange": COULEUR_ORANGE,
            "rouge":  COULEUR_ROUGE,
        }
        self._couleur_active: tuple = COULEUR_VERTE  # couleur par défaut

        # Groupe exclusif : une seule couleur cochée à la fois
        self._groupe_couleurs = QActionGroup(self)
        self._groupe_couleurs.setExclusive(True)

        self._actions_couleur: dict[str, QAction] = {}
        for nom, rgb in self._couleurs.items():
            icone = _creer_icone_couleur(rgb)
            action = QAction(icone, "", self)
            action.setToolTip(nom.capitalize())
            action.setCheckable(True)
            action.setData(rgb)
            action.triggered.connect(self._on_couleur_selectionnee)
            self._groupe_couleurs.addAction(action)
            self.addAction(action)
            self._actions_couleur[nom] = action

        # Activer le vert par défaut
        self._actions_couleur["vert"].setChecked(True)

        # Séparateur visuel entre le groupe couleur et les boutons de zoom
        self.addSeparator()

        # Groupe zoom — textes courts conservés (lisibles sans icône)
        action_zoom_plus = QAction("+", self)
        action_zoom_moins = QAction("−", self)
        action_zoom_reset = QAction("100%", self)
        action_zoom_plus.setToolTip("Zoom avant")
        action_zoom_moins.setToolTip("Zoom arrière")
        action_zoom_reset.setToolTip("Zoom à 100%")
        self.addAction(action_zoom_plus)
        self.addAction(action_zoom_moins)
        self.addAction(action_zoom_reset)

        # Connexion des signaux internes
        self._groupe_modes.triggered.connect(self._on_mode_triggered)
        self._action_transparence.toggled.connect(self.transparence_change)
        action_zoom_plus.triggered.connect(self.zoom_in)
        action_zoom_moins.triggered.connect(self.zoom_out)
        action_zoom_reset.triggered.connect(self.zoom_reset)

        # Initialisation du fond des icônes : sélection active au démarrage
        self._rafraichir_icones_modes(mode_actif="selection")

    # ------------------------------------------------------------------
    # Slots privés
    # ------------------------------------------------------------------

    def _on_mode_triggered(self, action: QAction) -> None:
        """Met à jour le mode actif, rafraîchit les icônes et émet mode_change."""
        if action.data() is None:
            logger.warning("Action de mode sans données associées.")
            return
        valeur: str = action.data()
        # Régénérer toutes les icônes de mode avec le fond adapté (actif/inactif)
        self._rafraichir_icones_modes(mode_actif=valeur)
        self.mode_change.emit(valeur)
        logger.debug("Mode actif : %s", valeur)

    def _rafraichir_icones_modes(self, mode_actif: str) -> None:
        """Régénère toutes les icônes de mode avec le fond adapté (actif/inactif).

        Paramètres
        ----------
        mode_actif : str
            Valeur interne du mode actuellement actif (ex. "selection", "rect").
            L'action correspondante reçoit le fond bleu clair, les autres le fond blanc.
        """
        for valeur, action in self._actions_mode.items():
            fn = _ICONES_MODES.get(valeur)
            if fn:
                est_actif = (valeur == mode_actif)
                action.setIcon(_creer_icone(fn, actif=est_actif))

    def _on_couleur_selectionnee(self) -> None:
        """Met à jour la couleur active et émet le signal couleur_change."""
        action = self._groupe_couleurs.checkedAction()
        if action is None:
            return
        self._couleur_active = action.data()
        self.couleur_change.emit(self._couleur_active)
        logger.debug("Couleur active : %s", self._couleur_active)
