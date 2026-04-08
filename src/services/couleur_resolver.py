"""
Résolution de la couleur et de la mention d'un prélèvement amiante.

Ce module fournit la fonction `resoudre_couleur` qui, à partir du résultat
d'analyse d'un échantillon, détermine :
  - la couleur RGB à utiliser pour la légende (bulle de marquage),
  - la mention courte associée (ex. "sa" pour sans amiante, "a" pour avec amiante).

Règles appliquées (insensibles à la casse) :
  - Résultat vide, contenant "Absence" ou "pas"  → vert  RGB(18, 169, 30),  mention "sa"
  - Résultat contenant "non prélevé"             → orange RGB(255, 128, 0), mention "a?"
  - Résultat contenant "Présence"                → rouge  RGB(255, 0, 0),   mention "a"
"""

import logging

# Journalisation du module
logger = logging.getLogger(__name__)

# --- Constantes de couleurs RGB ---
COULEUR_ABSENCE: tuple = (18, 169, 30)    # Vert  – sans amiante détecté
COULEUR_NON_PRELEVE: tuple = (255, 128, 0)  # Orange – prélèvement non réalisé
COULEUR_PRESENCE: tuple = (255, 0, 0)     # Rouge – amiante détecté

# --- Constantes de mentions ---
MENTION_ABSENCE: str = "sa"    # Sans amiante
MENTION_NON_PRELEVE: str = "a?"  # Statut inconnu / non prélevé
MENTION_PRESENCE: str = "a"    # Amiante présent


def resoudre_couleur(resultat: str) -> tuple[tuple, str]:
    """
    Détermine la couleur RGB et la mention associée au résultat d'analyse.

    Comparaisons réalisées de manière insensible à la casse.

    Args:
        resultat: Chaîne de caractères issue de la colonne I du fichier Excel.
                  Peut être vide ou contenir des valeurs telles que "Absence",
                  "Présence", "non prélevé", etc.

    Returns:
        Un tuple (couleur_rgb, mention) où :
          - couleur_rgb est un tuple (R, G, B) d'entiers entre 0 et 255,
          - mention est une chaîne courte décrivant le statut amiante.

    Exemples:
        >>> resoudre_couleur("Absence d'amiante")
        ((18, 169, 30), 'sa')
        >>> resoudre_couleur("Présence d'amiante")
        ((255, 0, 0), 'a')
        >>> resoudre_couleur("Non prélevé")
        ((255, 128, 0), 'a?')
        >>> resoudre_couleur("")
        ((18, 169, 30), 'sa')
    """
    # Normalisation en minuscules pour les comparaisons insensibles à la casse
    resultat_lower: str = resultat.strip().lower() if resultat else ""

    # Cas 1 : résultat vide → sans amiante par défaut
    if not resultat_lower:
        logger.debug("Résultat vide – couleur absence appliquée par défaut.")
        return COULEUR_ABSENCE, MENTION_ABSENCE

    # Cas 2 : prélèvement non réalisé
    if "non prélevé" in resultat_lower:
        logger.debug("Résultat '%s' → non prélevé.", resultat)
        return COULEUR_NON_PRELEVE, MENTION_NON_PRELEVE

    # Cas 3 : absence d'amiante (mot "absence" ou "pas" présent)
    if "absence" in resultat_lower or "pas" in resultat_lower:
        logger.debug("Résultat '%s' → absence.", resultat)
        return COULEUR_ABSENCE, MENTION_ABSENCE

    # Cas 4 : présence d'amiante
    if "présence" in resultat_lower or "presence" in resultat_lower:
        logger.debug("Résultat '%s' → présence.", resultat)
        return COULEUR_PRESENCE, MENTION_PRESENCE

    # Cas par défaut non prévu : on applique la couleur absence et on journalise
    logger.warning(
        "Résultat non reconnu : '%s'. Couleur absence appliquée par défaut.", resultat
    )
    return COULEUR_ABSENCE, MENTION_ABSENCE
