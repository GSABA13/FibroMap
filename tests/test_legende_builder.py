"""
Tests unitaires pour le module src/services/legende_builder.py.

Vérifie la construction correcte des trois lignes de texte de la bulle
de légende selon les règles métier définies dans le cahier des charges.
"""

import pytest

from src.services.legende_builder import construire_texte


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _construire(
    prelevement="PRV-001",
    description="Calorifuge",
    resultat="Absence",
    localisation="RDC",
    element_sonde="Conduit",
):
    """Appel de construire_texte avec des valeurs par défaut pour simplifier les tests."""
    return construire_texte(
        prelevement=prelevement,
        description=description,
        resultat=resultat,
        localisation=localisation,
        element_sonde=element_sonde,
    )


# ---------------------------------------------------------------------------
# Structure du retour
# ---------------------------------------------------------------------------

class TestStructureRetour:
    """La fonction doit toujours retourner un tuple de trois chaînes."""

    def test_retour_est_tuple_trois_elements(self):
        retour = _construire()
        assert isinstance(retour, tuple)
        assert len(retour) == 3

    def test_elements_sont_des_chaines(self):
        ligne1, ligne2, ligne3 = _construire()
        assert isinstance(ligne1, str)
        assert isinstance(ligne2, str)
        assert isinstance(ligne3, str)


# ---------------------------------------------------------------------------
# Ligne 1 : identifiant du prélèvement (colonne G)
# ---------------------------------------------------------------------------

class TestLigne1Prelevement:
    """La ligne 1 doit toujours être l'identifiant du prélèvement."""

    def test_ligne1_vaut_prelevement(self):
        ligne1, _, _ = _construire(prelevement="PRV-042")
        assert ligne1 == "PRV-042"

    def test_ligne1_vide_si_prelevement_vide(self):
        ligne1, _, _ = _construire(prelevement="")
        assert ligne1 == ""


# ---------------------------------------------------------------------------
# Ligne 3 : localisation (colonne D)
# ---------------------------------------------------------------------------

class TestLigne3Localisation:
    """La ligne 3 doit toujours être la localisation."""

    def test_ligne3_vaut_localisation(self):
        _, _, ligne3 = _construire(localisation="Sous-sol")
        assert ligne3 == "Sous-sol"

    def test_ligne3_vide_si_localisation_vide(self):
        _, _, ligne3 = _construire(localisation="")
        assert ligne3 == ""


# ---------------------------------------------------------------------------
# Ligne 2 : cas normal (F présent, ni "/" ni "Joint")
# ---------------------------------------------------------------------------

class TestLigne2CasNormal:
    """Quand F est une description ordinaire, ligne 2 = F."""

    def test_description_normale(self):
        _, ligne2, _ = _construire(description="Calorifuge")
        assert ligne2 == "Calorifuge"

    def test_description_vide(self):
        _, ligne2, _ = _construire(description="")
        assert ligne2 == ""

    def test_description_non_impactee_par_resultat(self):
        """Quand F est normal, le résultat ne doit pas apparaître en ligne 2."""
        _, ligne2, _ = _construire(description="Enduit", resultat="Présence d'amiante")
        assert ligne2 == "Enduit"
        assert "Présence" not in ligne2


# ---------------------------------------------------------------------------
# Ligne 2 : F == "/" → afficher le résultat (colonne I)
# ---------------------------------------------------------------------------

class TestLigne2DescriptionSlash:
    """Quand F vaut '/', la ligne 2 doit afficher le résultat d'analyse."""

    def test_slash_exact(self):
        _, ligne2, _ = _construire(description="/", resultat="Présence d'amiante")
        assert ligne2 == "Présence d'amiante"

    def test_slash_avec_espaces(self):
        """Un '/' entouré d'espaces doit être traité de la même façon."""
        _, ligne2, _ = _construire(description="  /  ", resultat="Absence")
        assert ligne2 == "Absence"

    def test_slash_avec_resultat_vide(self):
        _, ligne2, _ = _construire(description="/", resultat="")
        assert ligne2 == ""

    def test_slash_ligne1_et_ligne3_non_affectees(self):
        """Le '/' ne doit impacter ni la ligne 1 ni la ligne 3."""
        ligne1, _, ligne3 = _construire(
            description="/", prelevement="PRV-010", localisation="Etage 1"
        )
        assert ligne1 == "PRV-010"
        assert ligne3 == "Etage 1"


# ---------------------------------------------------------------------------
# Ligne 2 : F contient "Joint" → F + " de " + element_sonde
# ---------------------------------------------------------------------------

class TestLigne2DescriptionJoint:
    """Quand F contient 'Joint' (insensible à la casse), ligne 2 = F + ' de ' + E."""

    def test_joint_majuscule(self):
        """'Joint de dilatation' avec J majuscule."""
        _, ligne2, _ = _construire(
            description="Joint de dilatation", element_sonde="Plancher"
        )
        assert ligne2 == "Joint de dilatation de Plancher"

    def test_joint_minuscule(self):
        """'joint' en minuscule doit produire le même résultat."""
        _, ligne2, _ = _construire(
            description="joint d'étanchéité", element_sonde="Façade"
        )
        assert ligne2 == "joint d'étanchéité de Façade"

    def test_joint_majuscules_totales(self):
        """'JOINT' en majuscules totales doit aussi déclencher la règle."""
        _, ligne2, _ = _construire(
            description="JOINT D'ABOUT", element_sonde="Mur"
        )
        assert ligne2 == "JOINT D'ABOUT de Mur"

    def test_joint_casse_mixte(self):
        """'JoInT' en casse mixte doit aussi déclencher la règle."""
        _, ligne2, _ = _construire(
            description="JoInT de sol", element_sonde="Dalle"
        )
        assert ligne2 == "JoInT de sol de Dalle"

    def test_joint_element_sonde_vide(self):
        """Element sondé vide → concaténation avec chaîne vide."""
        _, ligne2, _ = _construire(
            description="Joint de dilatation", element_sonde=""
        )
        assert ligne2 == "Joint de dilatation de "

    def test_joint_ligne1_et_ligne3_non_affectees(self):
        """La règle 'Joint' ne doit pas affecter les lignes 1 et 3."""
        ligne1, _, ligne3 = _construire(
            prelevement="PRV-007",
            description="Joint de dilatation",
            element_sonde="Plancher",
            localisation="R+2",
        )
        assert ligne1 == "PRV-007"
        assert ligne3 == "R+2"

    def test_joint_priorite_sur_slash(self):
        """
        Si la description contient 'Joint', la règle Joint prime
        (car la description n'est pas '/').
        """
        _, ligne2, _ = _construire(
            description="Joint/étanchéité", element_sonde="Mur"
        )
        assert ligne2 == "Joint/étanchéité de Mur"



# ---------------------------------------------------------------------------
# Ligne 2 : cas avancés de Joint (métallique, étanchéité)
# ---------------------------------------------------------------------------

class TestLigne2JointVariantes:
    """Cas avancés : Joint métallique et Joint sur élément d étanchéité."""

    def test_joint_metallique_produit_formule_fixe(self):
        """F contient 'Joint' + 'métallique' → 'Joint de [E] Métallique'."""
        _, ligne2, _ = _construire(
            description="Joint métallique de dilatation",
            element_sonde="Dalle",
        )
        assert ligne2 == "Joint de Dalle Métallique"

    def test_joint_metallique_majuscules(self):
        """'MÉTALLIQUE' en majuscules doit déclencher la règle métallique."""
        _, ligne2, _ = _construire(
            description="Joint MÉTALLIQUE",
            element_sonde="Plancher",
        )
        assert ligne2 == "Joint de Plancher Métallique"

    def test_joint_etancheite_avec_accent_utilise_apostrophe_d(self):
        """E contient 'étanchéité' (avec accent) → [F] + " d'" + [E]."""
        _, ligne2, _ = _construire(
            description="Joint d'about",
            element_sonde="étanchéité toiture",
        )
        assert ligne2 == "Joint d'about d'étanchéité toiture"

    def test_joint_etancheite_sans_accent_utilise_apostrophe_d(self):
        """E contient 'Etanchéité' (sans accent initial) → même résultat."""
        _, ligne2, _ = _construire(
            description="Joint souple",
            element_sonde="Etanchéité façade",
        )
        assert ligne2 == "Joint souple d'Etanchéité façade"

    def test_joint_etancheite_majuscules_utilise_apostrophe_d(self):
        """E contient 'ÉTANCHÉITÉ' (tout majuscules) → même résultat."""
        _, ligne2, _ = _construire(
            description="Joint de rive",
            element_sonde="ÉTANCHÉITÉ TOITURE",
        )
        assert ligne2 == "Joint de rive d'ÉTANCHÉITÉ TOITURE"

    def test_joint_metallique_priorite_sur_etancheite(self):
        """
        Si F contient 'métallique' ET E contient 'étanchéité',
        la règle 'métallique' est prioritaire (vérifiée en premier).
        """
        _, ligne2, _ = _construire(
            description="Joint métallique",
            element_sonde="étanchéité terrasse",
        )
        assert ligne2 == "Joint de étanchéité terrasse Métallique"


# ---------------------------------------------------------------------------
# Combinaisons complètes — cas issus de la documentation
# ---------------------------------------------------------------------------

class TestCasDocumentation:
    """Cas d'usage tirés des exemples de la docstring."""

    def test_exemple_cas_normal(self):
        """Exemple 1 : description ordinaire."""
        ligne1, ligne2, ligne3 = construire_texte(
            prelevement="PRV-001",
            description="Calorifuge",
            resultat="Absence",
            localisation="RDC",
            element_sonde="Conduit",
        )
        assert (ligne1, ligne2, ligne3) == ("PRV-001", "Calorifuge", "RDC")

    def test_exemple_slash(self):
        """Exemple 2 : description vaut '/'."""
        ligne1, ligne2, ligne3 = construire_texte(
            prelevement="PRV-002",
            description="/",
            resultat="Présence",
            localisation="Sous-sol",
            element_sonde="Dalle",
        )
        assert (ligne1, ligne2, ligne3) == ("PRV-002", "Présence", "Sous-sol")

    def test_exemple_joint(self):
        """Exemple 3 : description contient 'Joint'."""
        ligne1, ligne2, ligne3 = construire_texte(
            prelevement="PRV-003",
            description="Joint de dilatation",
            resultat="Absence",
            localisation="R+1",
            element_sonde="Plancher",
        )
        assert (ligne1, ligne2, ligne3) == (
            "PRV-003",
            "Joint de dilatation de Plancher",
            "R+1",
        )
