"""
Modèles de données pour les formes dessinées sur le canvas.

Ce module définit uniquement des dataclasses pures (aucun import PyQt6).
Les couleurs sont stockées en tuple RGB ; les QColor sont construits à la volée
dans la couche de rendu (canvas_widget.py).

Formes disponibles :
    - FormeRect            : rectangle défini par deux points opposés
    - FormeCercle          : cercle défini par un centre et un point de bord
    - FormeLigne           : segment défini par deux points
    - FormePolygone        : polygone fermé défini par N points
    - FormeLignesConnectees: polyligne ouverte définie par N points
"""

import uuid
from dataclasses import dataclass, field

from src.utils.constantes import COULEUR_VERTE, ALPHA_PLEIN


@dataclass
class FormeBase:
    """Attributs communs à toutes les formes."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    couleur_rgb: tuple[int, int, int] = field(
        default_factory=lambda: COULEUR_VERTE
    )  # RGB (vert par défaut)
    alpha: int = field(default=ALPHA_PLEIN)    # 255=plein, 128=semi-transparent
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class FormeRect(FormeBase):
    """Rectangle défini par deux points opposés (haut-gauche, bas-droite)."""


@dataclass
class FormeCercle(FormeBase):
    """Cercle défini par le centre (points[0]) et un point de bord (points[1])."""


@dataclass
class FormeLigne(FormeBase):
    """Segment défini par deux points."""


@dataclass
class FormePolygone(FormeBase):
    """Polygone fermé défini par N points."""


@dataclass
class FormeLignesConnectees(FormeBase):
    """Polyligne ouverte définie par N points."""
