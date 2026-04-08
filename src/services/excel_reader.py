"""
Lecture du fichier Excel contenant les données de prélèvements amiante.

Ce module fournit la fonction `charger_excel` qui ouvre un classeur Excel
(.xlsx) en mode lecture seule, lit la feuille "Prv Am" et retourne la liste
des prélèvements sous forme d'objets Echantillon.

Correspondance des colonnes Excel (feuille "Prv Am") :
  A  – Unités
  B  – Zone
  C  – Équipements
  D  – Localisation
  E  – Élément sondé
  F  – Description
  G  – Prélèvement       ← clé : ligne ignorée si vide
  H  – Date
  I  – Résultat
  J  – (non utilisé)
  K  – (non utilisé)
  L  – Volume
  M  – Photo
  N  – Étage
  O  – Référence Plan
  P  – Marquage
  Q  – N° Prv Labo
  R  – Commentaires

Les deux premières lignes (en-têtes) sont ignorées.
Si la feuille "Prv Am" est absente, la fonction retourne une liste vide
sans lever d'exception.
"""

import logging
from typing import Optional

import openpyxl

from src.models.echantillon import Echantillon
from src.services.couleur_resolver import resoudre_couleur
from src.services.legende_builder import construire_texte

# Journalisation du module
logger = logging.getLogger(__name__)

# Nom de la feuille cible dans le classeur Excel
NOM_FEUILLE: str = "Prv Am"

# Indices de colonnes (base 1, correspondant à l'API openpyxl)
COL_LOCALISATION: int = 4    # D
COL_ELEMENT_SONDE: int = 5   # E
COL_DESCRIPTION: int = 6     # F
COL_PRELEVEMENT: int = 7     # G  ← colonne clé
COL_RESULTAT: int = 9        # I
COL_REFERENCE_PLAN: int = 15  # O

# Numéro de la première ligne de données (après les en-têtes)
PREMIERE_LIGNE_DONNEES: int = 3


def _valeur_cellule(row: tuple, index_1base: int) -> str:
    """
    Extrait la valeur d'une cellule dans une ligne openpyxl et la convertit
    en chaîne de caractères propre.

    Args:
        row         : tuple de cellules retourné par iter_rows().
        index_1base : numéro de colonne en base 1 (1 = colonne A).

    Returns:
        La valeur sous forme de str, ou une chaîne vide si la cellule est None.
    """
    cellule = row[index_1base - 1]  # Conversion base-1 → base-0
    valeur = cellule.value
    if valeur is None:
        return ""
    return str(valeur).strip()


def charger_excel(chemin: str) -> list[Echantillon]:
    """
    Charge et analyse le fichier Excel des prélèvements amiante.

    Ouvre le classeur en mode read_only pour minimiser la consommation mémoire,
    lit toutes les lignes valides de la feuille "Prv Am" (colonne G non vide,
    à partir de la ligne 3) et retourne la liste des Echantillon construits.

    Args:
        chemin: Chemin absolu ou relatif vers le fichier Excel (.xlsx).

    Returns:
        Liste d'objets Echantillon, dans l'ordre de lecture du fichier.
        Retourne une liste vide si :
          - la feuille "Prv Am" est absente du classeur,
          - aucune ligne valide n'est trouvée.

    Raises:
        FileNotFoundError : si le fichier Excel n'existe pas à l'emplacement indiqué.
        openpyxl.utils.exceptions.InvalidFileException : si le fichier n'est pas
            un classeur Excel valide.
    """
    logger.info("Chargement du fichier Excel : %s", chemin)

    # Ouverture en lecture seule pour les performances et la sécurité
    classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)

    # Vérification de la présence de la feuille cible
    if NOM_FEUILLE not in classeur.sheetnames:
        logger.warning(
            "Feuille '%s' absente du classeur '%s'. Retour d'une liste vide.",
            NOM_FEUILLE,
            chemin,
        )
        classeur.close()
        return []

    feuille = classeur[NOM_FEUILLE]
    echantillons: list[Echantillon] = []

    # Parcours des lignes à partir de la première ligne de données
    for numero_ligne, row in enumerate(
        feuille.iter_rows(min_row=PREMIERE_LIGNE_DONNEES), start=PREMIERE_LIGNE_DONNEES
    ):
        # Extraction de l'identifiant du prélèvement (colonne G)
        prelevement: str = _valeur_cellule(row, COL_PRELEVEMENT)

        # On ignore les lignes dont la colonne G est vide
        if not prelevement:
            logger.debug("Ligne %d ignorée : colonne G vide.", numero_ligne)
            continue

        # Extraction des autres champs utiles
        description: str = _valeur_cellule(row, COL_DESCRIPTION)
        resultat: str = _valeur_cellule(row, COL_RESULTAT)
        localisation: str = _valeur_cellule(row, COL_LOCALISATION)
        element_sonde: str = _valeur_cellule(row, COL_ELEMENT_SONDE)
        reference_plan: str = _valeur_cellule(row, COL_REFERENCE_PLAN)

        # Résolution de la couleur et de la mention selon le résultat
        couleur, mention = resoudre_couleur(resultat)

        # Construction des trois lignes de texte de la bulle de légende
        texte_ligne1, texte_ligne2, texte_ligne3 = construire_texte(
            prelevement=prelevement,
            description=description,
            resultat=resultat,
            localisation=localisation,
            element_sonde=element_sonde,
        )

        # Instanciation de l'objet Echantillon
        echantillon = Echantillon(
            prelevement=prelevement,
            description=description,
            resultat=resultat,
            localisation=localisation,
            element_sonde=element_sonde,
            reference_plan=reference_plan,
            couleur=couleur,
            mention=mention,
            texte_ligne1=texte_ligne1,
            texte_ligne2=texte_ligne2,
            texte_ligne3=texte_ligne3,
        )

        echantillons.append(echantillon)
        logger.debug(
            "Ligne %d – prélèvement '%s' chargé (résultat : '%s', mention : '%s').",
            numero_ligne,
            prelevement,
            resultat,
            mention,
        )

    classeur.close()

    logger.info(
        "%d prélèvement(s) chargé(s) depuis '%s'.", len(echantillons), chemin
    )
    return echantillons
