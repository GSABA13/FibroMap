"""
Modèle de données représentant un échantillon de prélèvement amiante.

Ce module définit la dataclass Echantillon qui regroupe toutes les informations
issues d'une ligne du fichier Excel (feuille "Prv Am") : identification du
prélèvement, localisation, résultat, couleur de légende et textes d'affichage.
"""

from dataclasses import dataclass


@dataclass
class Echantillon:
    """
    Représente un prélèvement amiante issu du fichier Excel.

    Attributs issus des colonnes Excel :
        prelevement     : identifiant du prélèvement          (colonne G)
        description     : description du matériau             (colonne F)
        resultat        : résultat d'analyse                  (colonne I)
        localisation    : localisation du prélèvement         (colonne D)
        element_sonde   : élément sondé                       (colonne E)
        reference_plan  : référence du plan associé           (colonne O)

    Attributs calculés :
        couleur         : couleur RGB sous forme de tuple (R, G, B)
        mention         : mention courte (ex. "sa", "a", "a?")

    Attributs de texte pour l'affichage en légende :
        texte_ligne1    : première ligne de la bulle de légende
        texte_ligne2    : deuxième ligne de la bulle de légende
        texte_ligne3    : troisième ligne de la bulle de légende
    """

    # --- Champs issus des colonnes Excel ---
    prelevement: str        # Colonne G – identifiant du prélèvement
    description: str        # Colonne F – description du matériau
    resultat: str           # Colonne I – résultat d'analyse (Présence / Absence / …)
    localisation: str       # Colonne D – localisation dans le bâtiment
    element_sonde: str      # Colonne E – élément sondé (mur, plafond, …)
    reference_plan: str     # Colonne O – référence du plan sur lequel figure le prélèvement
    id_primaire: str = ""   # Colonne K – clé primaire unique de la ligne Excel

    # --- Champs calculés à partir du résultat ---
    couleur: tuple          # Tuple RGB (R, G, B) déterminé par le résultat d'analyse
    mention: str            # Mention courte associée à la couleur (ex. "sa", "a", "a?")

    # --- Textes de la bulle de légende ---
    texte_ligne1: str       # Ligne 1 : identifiant du prélèvement
    texte_ligne2: str       # Ligne 2 : description (ou résultat si F == "/", ou F + élément)
    texte_ligne3: str       # Ligne 3 : localisation
