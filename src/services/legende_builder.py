"""
Construction des textes de légende pour un prélèvement amiante.

Ce module fournit la fonction `construire_texte` qui, à partir des données
brutes d'un prélèvement, génère les trois lignes de texte affichées dans la
bulle de légende sur le plan.

Règles de construction :
  - ligne1 : identifiant du prélèvement                        (colonne G)
  - ligne2 : description du matériau                           (colonne F), SAUF :
      * si F vaut "/"      → utiliser le résultat d'analyse    (colonne I)
      * si F contient "Joint" ET F contient "métallique"
                           → "Joint de " + [E] + " Métallique"
      * si F contient "Joint" ET E contient "étanchéité"
                           → [F] + " d'" + [E]
      * si F contient "Joint" (cas général)
                           → [F] + " de " + [E]
  - ligne3 : localisation dans le bâtiment                     (colonne D)
"""

import logging
import unicodedata

# Journalisation du module
logger = logging.getLogger(__name__)


def _sans_accents(s: str) -> str:
    """Retourne la chaîne en minuscules sans accents (pour comparaisons souples)."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode("ascii")


def construire_texte(
    prelevement: str,
    description: str,
    resultat: str,
    localisation: str,
    element_sonde: str,
) -> tuple[str, str, str]:
    """
    Construit les trois lignes de texte de la bulle de légende.

    Args:
        prelevement  : identifiant du prélèvement (colonne G).
        description  : description du matériau    (colonne F).
        resultat     : résultat d'analyse         (colonne I).
        localisation : localisation               (colonne D).
        element_sonde: élément sondé              (colonne E).

    Returns:
        Un tuple (ligne1, ligne2, ligne3) de chaînes de caractères prêtes
        à être affichées dans la bulle de légende.

    Exemples :
        >>> construire_texte("PRV-001", "Calorifuge", "Absence", "RDC", "Conduit")
        ('PRV-001', 'Calorifuge', 'RDC')

        >>> construire_texte("PRV-002", "/", "Présence", "Sous-sol", "Dalle")
        ('PRV-002', 'Présence', 'Sous-sol')

        >>> construire_texte("PRV-003", "Joint de dilatation", "Absence", "R+1", "Plancher")
        ('PRV-003', 'Joint de dilatation de Plancher', 'R+1')
    """
    # --- Ligne 1 : toujours l'identifiant du prélèvement ---
    ligne1: str = prelevement

    # Défense contre un None accidentel (normalement garanti str par excel_reader)
    description = description or ""

    # --- Ligne 2 : description, avec règles spécifiques ---
    if description.strip() == "/":
        # Si la description vaut "/", on affiche le résultat d'analyse à la place
        logger.debug(
            "Prélèvement '%s' : description '/' → utilisation du résultat '%s'.",
            prelevement,
            resultat,
        )
        ligne2 = resultat

    elif "joint" in description.strip().lower():
        desc_norm = _sans_accents(description.strip())
        elem_norm = _sans_accents(element_sonde or "")

        if "metallique" in desc_norm:
            # Joint métallique : "Joint de [E] Métallique"
            logger.debug(
                "Prélèvement '%s' : Joint métallique → 'Joint de %s Métallique'.",
                prelevement, element_sonde,
            )
            ligne2 = f"Joint de {element_sonde} Métallique"

        elif "etancheite" in elem_norm:
            # Joint sur élément d'étanchéité : [F] + " d'" + [E]
            logger.debug(
                "Prélèvement '%s' : Joint + étanchéité → '%s d'%s'.",
                prelevement, description, element_sonde,
            )
            ligne2 = f"{description} d'{element_sonde}"

        else:
            # Cas général Joint : [F] + " de " + [E]
            logger.debug(
                "Prélèvement '%s' : Joint → '%s de %s'.",
                prelevement, description, element_sonde,
            )
            ligne2 = f"{description} de {element_sonde}"

    else:
        # Cas standard : on affiche simplement la description
        ligne2 = description

    # --- Ligne 3 : toujours la localisation ---
    ligne3: str = localisation

    return ligne1, ligne2, ligne3
