"""
Tests unitaires pour le module src/services/couleur_resolver.py.

Vérifie la résolution de la couleur RGB et de la mention selon le résultat
d'analyse amiante. Toutes les comparaisons doivent être insensibles à la casse.
"""

import pytest

from src.services.couleur_resolver import (
    COULEUR_ABSENCE,
    COULEUR_NON_PRELEVE,
    COULEUR_PRESENCE,
    MENTION_ABSENCE,
    MENTION_NON_PRELEVE,
    MENTION_PRESENCE,
    resoudre_couleur,
)


# ---------------------------------------------------------------------------
# Cas : absence d'amiante → vert + "sa"
# ---------------------------------------------------------------------------

class TestAbsenceAmiante:
    """Résultats qui doivent produire la couleur verte et la mention 'sa'."""

    def test_absence_de_revetement(self):
        """Libellé exact 'Absence de revêtement' → vert, mention 'sa'."""
        couleur, mention = resoudre_couleur("Absence de revêtement")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE

    def test_absence_majuscules(self):
        """'ABSENCE' en majuscules → même résultat que la casse normale."""
        couleur, mention = resoudre_couleur("ABSENCE")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE

    def test_absence_minuscules(self):
        """'absence' en minuscules → vert, mention 'sa'."""
        couleur, mention = resoudre_couleur("absence d'amiante")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE

    def test_pas_detecte(self):
        """'pas détecté' contient 'pas' → vert, mention 'sa'."""
        couleur, mention = resoudre_couleur("pas détecté")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE

    def test_resultat_vide(self):
        """Résultat vide '' → vert par défaut, mention 'sa'."""
        couleur, mention = resoudre_couleur("")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE

    def test_resultat_espaces_seuls(self):
        """Résultat composé uniquement d'espaces → traité comme vide."""
        couleur, mention = resoudre_couleur("   ")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE

    def test_resultat_none_equivalent(self):
        """Résultat None-like (chaîne vide après strip) → vert par défaut."""
        couleur, mention = resoudre_couleur("")
        assert couleur == (18, 169, 30)
        assert mention == "sa"

    def test_valeurs_rgb_vertes_correctes(self):
        """Vérifie les valeurs RGB exactes pour l'absence."""
        couleur, _ = resoudre_couleur("Absence")
        assert couleur == (18, 169, 30)


# ---------------------------------------------------------------------------
# Cas : présence d'amiante → rouge + "a"
# ---------------------------------------------------------------------------

class TestPresenceAmiante:
    """Résultats qui doivent produire la couleur rouge et la mention 'a'."""

    def test_presence_amiante(self):
        """'Présence d'amiante' → rouge, mention 'a'."""
        couleur, mention = resoudre_couleur("Présence d'amiante")
        assert couleur == COULEUR_PRESENCE
        assert mention == MENTION_PRESENCE

    def test_presence_majuscules(self):
        """'PRÉSENCE' en majuscules → rouge, mention 'a'."""
        couleur, mention = resoudre_couleur("PRÉSENCE D'AMIANTE")
        assert couleur == COULEUR_PRESENCE
        assert mention == MENTION_PRESENCE

    def test_presence_sans_accent(self):
        """'presence' sans accent → rouge, mention 'a' (branche 'presence')."""
        couleur, mention = resoudre_couleur("presence")
        assert couleur == COULEUR_PRESENCE
        assert mention == MENTION_PRESENCE

    def test_valeurs_rgb_rouges_correctes(self):
        """Vérifie les valeurs RGB exactes pour la présence."""
        couleur, _ = resoudre_couleur("Présence")
        assert couleur == (255, 0, 0)


# ---------------------------------------------------------------------------
# Cas : non prélevé → orange + "a?"
# ---------------------------------------------------------------------------

class TestNonPreleve:
    """Résultats qui doivent produire la couleur orange et la mention 'a?'."""

    def test_non_preleve_minuscules(self):
        """'non prélevé' en minuscules → orange, mention 'a?'."""
        couleur, mention = resoudre_couleur("non prélevé")
        assert couleur == COULEUR_NON_PRELEVE
        assert mention == MENTION_NON_PRELEVE

    def test_non_preleve_majuscules(self):
        """'NON PRÉLEVÉ' en majuscules → orange, mention 'a?'."""
        couleur, mention = resoudre_couleur("NON PRÉLEVÉ")
        assert couleur == COULEUR_NON_PRELEVE
        assert mention == MENTION_NON_PRELEVE

    def test_non_preleve_casse_mixte(self):
        """'Non Prélevé' en casse mixte → orange, mention 'a?'."""
        couleur, mention = resoudre_couleur("Non Prélevé")
        assert couleur == COULEUR_NON_PRELEVE
        assert mention == MENTION_NON_PRELEVE

    def test_valeurs_rgb_orange_correctes(self):
        """Vérifie les valeurs RGB exactes pour le non prélevé."""
        couleur, _ = resoudre_couleur("non prélevé")
        assert couleur == (255, 128, 0)


# ---------------------------------------------------------------------------
# Cas : résultat non reconnu → vert par défaut
# ---------------------------------------------------------------------------

class TestResultatNonReconnu:
    """Un résultat inconnu doit produire la couleur absence par défaut."""

    def test_valeur_inconnue(self):
        """Valeur inconnue → vert par défaut, mention 'sa'."""
        couleur, mention = resoudre_couleur("Résultat inconnu XYZ")
        assert couleur == COULEUR_ABSENCE
        assert mention == MENTION_ABSENCE


# ---------------------------------------------------------------------------
# Vérification des constantes exportées
# ---------------------------------------------------------------------------

class TestConstantes:
    """Les constantes du module doivent avoir les valeurs exactes du cahier des charges."""

    def test_constante_couleur_absence(self):
        assert COULEUR_ABSENCE == (18, 169, 30)

    def test_constante_couleur_non_preleve(self):
        assert COULEUR_NON_PRELEVE == (255, 128, 0)

    def test_constante_couleur_presence(self):
        assert COULEUR_PRESENCE == (255, 0, 0)

    def test_constante_mention_absence(self):
        assert MENTION_ABSENCE == "sa"

    def test_constante_mention_non_preleve(self):
        assert MENTION_NON_PRELEVE == "a?"

    def test_constante_mention_presence(self):
        assert MENTION_PRESENCE == "a"


# ---------------------------------------------------------------------------
# Vérification du type de retour
# ---------------------------------------------------------------------------

class TestTypeRetour:
    """La fonction doit toujours retourner un tuple (tuple, str)."""

    def test_retour_est_tuple_deux_elements(self):
        resultat = resoudre_couleur("Absence")
        assert isinstance(resultat, tuple)
        assert len(resultat) == 2

    def test_couleur_est_tuple_trois_entiers(self):
        couleur, _ = resoudre_couleur("Absence")
        assert isinstance(couleur, tuple)
        assert len(couleur) == 3
        assert all(isinstance(v, int) for v in couleur)

    def test_mention_est_chaine(self):
        _, mention = resoudre_couleur("Absence")
        assert isinstance(mention, str)
