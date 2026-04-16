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

import math
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
    epaisseur: float = field(default=2.0)      # Épaisseur du trait/contour (px canvas / pt PDF)

    def contient_point(self, px: float, py: float, tolerance: float = 5.0) -> bool:
        """
        Teste si le point (px, py) est dans la zone de la forme, avec tolérance.
        Implémentation par défaut : bounding-box des points de contrôle.
        """
        if not self.points:
            return False
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs) - tolerance <= px <= max(xs) + tolerance and
                min(ys) - tolerance <= py <= max(ys) + tolerance)


@dataclass
class FormeRect(FormeBase):
    """Rectangle défini par deux points opposés (haut-gauche, bas-droite)."""

    # Hérite de contient_point de FormeBase (bounding-box correct pour un rectangle)


@dataclass
class FormeCercle(FormeBase):
    """Cercle défini par le centre (points[0]) et un point de bord (points[1])."""

    def contient_point(self, px: float, py: float, tolerance: float = 5.0) -> bool:
        """Teste si (px, py) est dans le disque du cercle (centre + tolérance)."""
        if len(self.points) < 2:
            return False
        cx, cy = self.points[0]
        bx, by = self.points[1]
        rayon = math.sqrt((bx - cx) ** 2 + (by - cy) ** 2)
        distance = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)
        return distance <= rayon + tolerance


@dataclass
class FormeLigne(FormeBase):
    """Segment défini par deux points."""

    def contient_point(self, px: float, py: float, tolerance: float = 5.0) -> bool:
        """Teste si (px, py) est à moins de `tolerance` px du segment."""
        if len(self.points) < 2:
            return False
        ax, ay = self.points[0]
        bx, by = self.points[1]
        # Projection du point sur le segment
        dx, dy = bx - ax, by - ay
        long2 = dx * dx + dy * dy
        if long2 == 0:
            return math.sqrt((px - ax) ** 2 + (py - ay) ** 2) <= tolerance
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / long2))
        proj_x = ax + t * dx
        proj_y = ay + t * dy
        return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2) <= tolerance


@dataclass
class FormePolygone(FormeBase):
    """Polygone fermé défini par N points."""

    def contient_point(self, px: float, py: float, tolerance: float = 5.0) -> bool:
        """
        Teste si (px, py) est dans le polygone (ray casting)
        ou à moins de `tolerance` px d'un bord.
        """
        pts = self.points
        if len(pts) < 2:
            return False
        # Test bord (distance segment ≤ tolérance)
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            long2 = dx * dx + dy * dy
            if long2 == 0:
                if math.sqrt((px - ax) ** 2 + (py - ay) ** 2) <= tolerance:
                    return True
                continue
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / long2))
            if math.sqrt((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) <= tolerance:
                return True
        # Test intérieur (ray casting)
        if len(pts) >= 3:
            dedans = False
            j = n - 1
            for i in range(n):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if ((yi > py) != (yj > py) and
                        px < (xj - xi) * (py - yi) / (yj - yi + 1e-10) + xi):
                    dedans = not dedans
                j = i
            if dedans:
                return True
        return False


@dataclass
class FormeLignesConnectees(FormeBase):
    """Polyligne ouverte définie par N points."""

    def contient_point(self, px: float, py: float, tolerance: float = 5.0) -> bool:
        """Teste si (px, py) est à moins de `tolerance` px d'un des segments."""
        if not self.points:
            return False
        # Cas d'un seul point : distance directe
        if len(self.points) == 1:
            ax, ay = self.points[0]
            return math.sqrt((px - ax) ** 2 + (py - ay) ** 2) <= tolerance
        # Cas général : test sur chaque segment
        for i in range(len(self.points) - 1):
            ax, ay = self.points[i]
            bx, by = self.points[i + 1]
            dx, dy = bx - ax, by - ay
            long2 = dx * dx + dy * dy
            if long2 == 0:
                if math.sqrt((px - ax) ** 2 + (py - ay) ** 2) <= tolerance:
                    return True
                continue
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / long2))
            proj_x = ax + t * dx
            proj_y = ay + t * dy
            if math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2) <= tolerance:
                return True
        return False
