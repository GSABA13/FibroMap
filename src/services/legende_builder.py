"""
Construction des textes de légende pour un prélèvement amiante.

Ce module fournit la fonction `construire_texte` qui, à partir des données
brutes d'un prélèvement, génère les trois lignes de texte affichées dans la
bulle de légende sur le plan.

Règles de construction :
  - ligne1 : identifiant du prélèvement                        (colonne G)
  - ligne2 : description du matériau                           (colonne F), SAUF :
      * si F vaut "/"      → utiliser le résultat d'analyse    (colonne I)
      * si F contient "Joint" (insensible à la casse)
                           → F + " de " + élément sondé        (colonne E)
  - ligne3 : localisation dans le bâtiment                     (colonne D)
"""

import logging

# Journalisation du module
logger = logging.getLogger(__name__)


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
        # Si la description contient "Joint", on concatène avec l'élément sondé
        logger.debug(
            "Prélèvement '%s' : description contient 'Joint' → ajout de l'élément sondé '%s'.",
            prelevement,
            element_sonde,
        )
        ligne2 = f"{description} de {element_sonde}"

    else:
        # Cas standard : on affiche simplement la description
        ligne2 = description

    # --- Ligne 3 : toujours la localisation ---
    ligne3: str = localisation

    return ligne1, ligne2, ligne3
