"""
Modèle de données d'une bulle de légende call-out coudé.

Stocke les coordonnées en coordonnées IMAGE originale (comme les formes),
la couleur en tuple RGB, et les données Excel associées optionnelles.
Aucun import PyQt6 dans ce module.
"""

import math
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.echantillon import Echantillon

from src.utils.constantes import (
    COULEUR_VERTE,
    LARGEUR_BULLE,
    FACTEUR_LARGEUR_BULLE,
    HAUTEUR_LIGNE,
    FACTEUR_INTERLIGNE,
    PADDING_BULLE,
    PIED_LONGUEUR_DEFAUT,
    LARGEUR_GLYPHE_MOYEN,
)


@dataclass
class BulleLegende:
    """
    Bulle de légende call-out coudée.

    Les coordonnées (ancrage et position) sont en coordonnées IMAGE originale.
    La conversion vers coordonnées canvas est effectuée dans canvas_widget.py.

    Attributs
    ---------
    id               : identifiant unique UUID
    ancrage          : point cliqué sur le plan (coords image)
    position         : coin supérieur gauche de la bulle (coords image)
    echantillon      : données Excel associées (optionnel)
    couleur_rgb      : couleur bordure + texte, tuple (R, G, B)
    largeur          : largeur fixe de la bulle en pixels image (144% de LARGEUR_BULLE, soit 1.2 × 1.2)
    pied_longueur    : longueur du segment perpendiculaire reliant la bulle au trait diagonal
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ancrage: tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    position: tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    echantillon: "Echantillon | None" = None
    couleur_rgb: tuple[int, int, int] = field(default_factory=lambda: COULEUR_VERTE)
    largeur: float = field(default_factory=lambda: LARGEUR_BULLE * FACTEUR_LARGEUR_BULLE)
    pied_longueur: float = PIED_LONGUEUR_DEFAUT

    def hauteur(self) -> float:
        """
        Calcule la hauteur de la bulle en tenant compte du word-wrap estimé.

        Pour chaque texte non vide (ligne1, ligne2, ligne3, mention), le nombre
        de lignes réel est estimé sans PyQt6 : la largeur utile disponible est
        divisée par la largeur moyenne d'un caractère à 9pt / 96 DPI (~6.5px),
        et le résultat est arrondi au plafond via math.ceil.

        Formule :
            largeur_texte   = self.largeur - PADDING_BULLE
            chars_par_ligne = max(1, int(largeur_texte / 6.5))
            nb_lignes       = math.ceil(len(texte) / chars_par_ligne)

        Chaque ligne estimée contribue HAUTEUR_LIGNE × 1.4 pixels.
        PADDING_BULLE est ajouté au total final.
        La hauteur retournée est au moins HAUTEUR_LIGNE × 1.4 + PADDING_BULLE.
        """
        if self.echantillon is None:
            return HAUTEUR_LIGNE * 1.4 + PADDING_BULLE

        # Ligne 1 : prélèvement (gras)
        ligne1 = self.echantillon.texte_ligne1
        # Ligne 2 : description/résultat
        ligne2 = self.echantillon.texte_ligne2
        # Ligne 3 : localisation
        ligne3 = self.echantillon.texte_ligne3
        # Mention : sa / a? / a
        mention = self.echantillon.mention

        # Largeur utile disponible pour le texte (hors padding)
        largeur_texte = self.largeur - PADDING_BULLE
        # Nombre de caractères par ligne selon largeur moyenne d'un glyphe 9pt à 96 DPI
        chars_par_ligne = max(1, int(largeur_texte / LARGEUR_GLYPHE_MOYEN))

        hauteur_totale = PADDING_BULLE
        for texte in (ligne1, ligne2, ligne3, mention):
            if texte and texte.strip():
                nb_lignes = math.ceil(len(texte) / chars_par_ligne)
                hauteur_totale += nb_lignes * HAUTEUR_LIGNE * FACTEUR_INTERLIGNE

        # Garantir une hauteur minimale d'une ligne
        return max(HAUTEUR_LIGNE * FACTEUR_INTERLIGNE + PADDING_BULLE, hauteur_totale)
