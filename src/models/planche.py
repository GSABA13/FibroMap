"""
Modèle de données d'une planche de repérage amiante.

Une planche correspond à une page du document PDF final.
Elle regroupe un plan (image ou PDF), les formes colorées dessinées dessus,
les bulles de légende et l'état du canvas (zoom, décalage).

Aucun import PyQt6 dans ce module.
Le décalage est stocké sous forme de tuple pour rester indépendant de PyQt6.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Planche:
    """
    Une planche de repérage.

    Attributs
    ---------
    id              : identifiant unique UUID
    numero          : numéro affiché dans le cartouche PDF (ex: 1, 2, 3…)
    reference_plan  : libellé de référence (ex: "Planche de repérage 01")
    plan_chemin     : chemin absolu vers l'image ou le PDF du plan, ou None
    formes          : liste des Forme* dessinées sur cette planche
    bulles          : liste des BulleLegende placées sur cette planche
    zoom_factor     : facteur de zoom du canvas au moment de la sauvegarde
    offset          : décalage du canvas sous forme de tuple (dx, dy) en pixels
    zone_plan       : position et dimensions du plan affiché dans le canvas,
                      sous la forme (x, y, largeur, hauteur) en pixels canvas,
                      ou None si le plan n'est pas encore affiché.
                      Mis à jour par canvas_widget à chaque paintEvent pour
                      permettre à pdf_exporter de connaître la géométrie du plan.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    numero: int = 1
    reference_plan: str = ""
    plan_chemin: str | None = None
    formes: list[Any] = field(default_factory=list)   # list[FormeBase]
    bulles: list[Any] = field(default_factory=list)   # list[BulleLegende]
    zoom_factor: float = 1.0
    # Décalage du plan dans le canvas : (dx, dy) en pixels canvas
    offset: tuple = field(default_factory=lambda: (0.0, 0.0))
    # Zone plan : (x, y, largeur, hauteur) en pixels canvas, ou None
    # Mis à jour par canvas_widget à chaque paintEvent pour permettre au PDF exporter
    # de connaître la position du plan sur la planche
    zone_plan: tuple | None = None   # (x, y, w, h) en pixels canvas

    def __str__(self) -> str:
        """Représentation courte pour l'affichage dans le panneau."""
        numero_str = f"{self.numero:02d}"
        if self.reference_plan:
            return f"{numero_str} — {self.reference_plan}"
        return f"Planche {numero_str}"
