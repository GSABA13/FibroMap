"""
Tests unitaires pour le module src/services/excel_reader.py.

openpyxl est mocké intégralement : aucun fichier .xlsx réel n'est nécessaire.
Les tests couvrent les cas limites décrits dans le cahier des charges :
feuille absente, ligne ignorée (G vide), en-têtes ignorées, cas nominal.
"""

from unittest.mock import MagicMock, patch, call

import pytest

from src.services.excel_reader import charger_excel, maj_bulles_depuis_echantillons
from src.models.bulle import BulleLegende
from src.models.echantillon import Echantillon
from src.models.planche import Planche


# ---------------------------------------------------------------------------
# Fabrique de cellules et de lignes factices
# ---------------------------------------------------------------------------

def _cellule(valeur):
    """Retourne un objet cellule openpyxl factice avec l'attribut .value."""
    cellule = MagicMock()
    cellule.value = valeur
    return cellule


def _ligne(*valeurs):
    """
    Construit une ligne (tuple de cellules) positionnée en base-1.

    Les valeurs sont assignées aux colonnes A, B, C, D, E, F, G, H, I, …, O
    dans l'ordre de la liste passée en argument (jusqu'à 15 colonnes).
    """
    # On remplit 15 colonnes (O = indice 15 en base-1) avec None par défaut
    cellules = [_cellule(None)] * 15
    for i, v in enumerate(valeurs):
        cellules[i] = _cellule(v)
    return tuple(cellules)


# Indices base-0 pour référence dans les tests
_D = 3   # Localisation
_E = 4   # Element sondé
_F = 5   # Description
_G = 6   # Prélèvement
_I = 8   # Résultat
_O = 14  # Référence plan


def _ligne_complete(
    prelevement="PRV-001",
    description="Calorifuge",
    resultat="Absence",
    localisation="RDC",
    element_sonde="Conduit",
    reference_plan="PL-001",
):
    """Construit une ligne complète avec les valeurs aux bonnes positions."""
    cellules = [_cellule(None)] * 15
    cellules[_D] = _cellule(localisation)
    cellules[_E] = _cellule(element_sonde)
    cellules[_F] = _cellule(description)
    cellules[_G] = _cellule(prelevement)
    cellules[_I] = _cellule(resultat)
    cellules[_O] = _cellule(reference_plan)
    return tuple(cellules)


# ---------------------------------------------------------------------------
# Contexte commun : patch openpyxl.load_workbook
# ---------------------------------------------------------------------------

def _creer_classeur_mock(sheetnames, lignes_par_feuille=None):
    """
    Crée un classeur openpyxl mocké compatible avec le context manager (with).

    Args:
        sheetnames          : liste des noms de feuilles présents dans le classeur.
        lignes_par_feuille  : dict {nom_feuille: [liste_de_lignes]} pour iter_rows().
                              Si absent, la feuille retourne une liste vide.
    """
    lignes_par_feuille = lignes_par_feuille or {}

    classeur = MagicMock()
    classeur.sheetnames = sheetnames
    classeur.close = MagicMock()

    # Support du context manager : __enter__ retourne le classeur lui-même,
    # __exit__ appelle close() pour vérifier que la fermeture est bien effectuée.
    classeur.__enter__ = MagicMock(return_value=classeur)
    classeur.__exit__ = MagicMock(side_effect=lambda *args: classeur.close())

    def _getitem(nom):
        feuille = MagicMock()
        lignes = lignes_par_feuille.get(nom, [])
        feuille.iter_rows.return_value = iter(lignes)
        return feuille

    classeur.__getitem__ = MagicMock(side_effect=_getitem)
    return classeur


# ---------------------------------------------------------------------------
# Cas 1 : feuille "Prv Am" absente
# ---------------------------------------------------------------------------

class TestFeuilleAbsente:
    """Quand la feuille 'Prv Am' n'existe pas, retourner [] sans exception."""

    def test_liste_vide_si_feuille_absente(self):
        classeur_mock = _creer_classeur_mock(sheetnames=["Feuille1", "Données"])
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            resultat = charger_excel("fictif.xlsx")
        assert resultat == []

    def test_pas_d_exception_si_feuille_absente(self):
        classeur_mock = _creer_classeur_mock(sheetnames=[])
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            try:
                charger_excel("fictif.xlsx")
            except Exception as exc:
                pytest.fail(f"Exception inattendue levée : {exc}")

    def test_classeur_ferme_si_feuille_absente(self):
        """Le classeur doit être fermé même quand la feuille est absente."""
        classeur_mock = _creer_classeur_mock(sheetnames=["AutreFeuille"])
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            charger_excel("fictif.xlsx")
        classeur_mock.close.assert_called_once()


# ---------------------------------------------------------------------------
# Cas 2 : lignes avec colonne G vide → ignorées
# ---------------------------------------------------------------------------

class TestLigneGVide:
    """Les lignes dont la colonne G (prélèvement) est vide doivent être ignorées."""

    def test_ligne_g_none_ignoree(self):
        ligne_vide = _ligne_complete(prelevement=None)
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne_vide]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            resultat = charger_excel("fictif.xlsx")
        assert resultat == []

    def test_ligne_g_chaine_vide_ignoree(self):
        ligne_vide = _ligne_complete(prelevement="")
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne_vide]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            resultat = charger_excel("fictif.xlsx")
        assert resultat == []

    def test_ligne_g_espaces_ignoree(self):
        """Une colonne G contenant uniquement des espaces est considérée vide."""
        ligne_espaces = _ligne_complete(prelevement="   ")
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne_espaces]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            resultat = charger_excel("fictif.xlsx")
        assert resultat == []

    def test_seules_les_lignes_valides_sont_retournees(self):
        """Mélange de lignes valides et vides : seules les valides sont retournées."""
        ligne_valide = _ligne_complete(prelevement="PRV-001")
        ligne_vide = _ligne_complete(prelevement=None)
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne_valide, ligne_vide, ligne_valide]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            resultat = charger_excel("fictif.xlsx")
        assert len(resultat) == 2


# ---------------------------------------------------------------------------
# Cas 3 : en-têtes ignorées (iter_rows part de min_row=3)
# ---------------------------------------------------------------------------

class TestEntetesIgnorees:
    """
    La lecture démarre à partir de la ligne 3.
    On vérifie que iter_rows est appelé avec min_row=3.
    """

    def test_iter_rows_demarre_a_la_ligne_5(self):
        feuille_mock = MagicMock()
        feuille_mock.iter_rows.return_value = iter([])

        classeur_mock = MagicMock()
        classeur_mock.sheetnames = ["Prv Am"]
        classeur_mock.__getitem__ = MagicMock(return_value=feuille_mock)
        classeur_mock.close = MagicMock()
        classeur_mock.__enter__ = MagicMock(return_value=classeur_mock)
        classeur_mock.__exit__ = MagicMock(side_effect=lambda *args: classeur_mock.close())

        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            charger_excel("fictif.xlsx")

        feuille_mock.iter_rows.assert_called_once_with(min_row=5)


# ---------------------------------------------------------------------------
# Cas 4 : lecture nominale
# ---------------------------------------------------------------------------

class TestLectureNominale:
    """Vérifie qu'une ligne complète produit un Echantillon correctement rempli."""

    def _charger_avec_une_ligne(self, **kwargs):
        ligne = _ligne_complete(**kwargs)
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            return charger_excel("fictif.xlsx")

    def test_retourne_un_echantillon(self):
        echantillons = self._charger_avec_une_ligne()
        assert len(echantillons) == 1
        assert isinstance(echantillons[0], Echantillon)

    def test_prelevement_correct(self):
        echantillons = self._charger_avec_une_ligne(prelevement="PRV-042")
        assert echantillons[0].prelevement == "PRV-042"

    def test_description_correcte(self):
        echantillons = self._charger_avec_une_ligne(description="Flocage")
        assert echantillons[0].description == "Flocage"

    def test_resultat_correct(self):
        echantillons = self._charger_avec_une_ligne(resultat="Absence d'amiante")
        assert echantillons[0].resultat == "Absence d'amiante"

    def test_localisation_correcte(self):
        echantillons = self._charger_avec_une_ligne(localisation="Sous-sol")
        assert echantillons[0].localisation == "Sous-sol"

    def test_element_sonde_correct(self):
        echantillons = self._charger_avec_une_ligne(element_sonde="Plafond")
        assert echantillons[0].element_sonde == "Plafond"

    def test_reference_plan_correcte(self):
        echantillons = self._charger_avec_une_ligne(reference_plan="PL-007")
        assert echantillons[0].reference_plan == "PL-007"

    def test_couleur_resolue(self):
        """La couleur doit être résolue via couleur_resolver."""
        echantillons = self._charger_avec_une_ligne(resultat="Absence d'amiante")
        assert echantillons[0].couleur == (18, 169, 30)

    def test_mention_resolue(self):
        echantillons = self._charger_avec_une_ligne(resultat="Absence d'amiante")
        assert echantillons[0].mention == "sa"

    def test_texte_ligne1_vaut_prelevement(self):
        echantillons = self._charger_avec_une_ligne(prelevement="PRV-001")
        assert echantillons[0].texte_ligne1 == "PRV-001"

    def test_texte_ligne3_vaut_localisation(self):
        echantillons = self._charger_avec_une_ligne(localisation="RDC")
        assert echantillons[0].texte_ligne3 == "RDC"

    def test_plusieurs_lignes(self):
        """Plusieurs lignes valides produisent plusieurs Echantillons dans l'ordre."""
        ligne1 = _ligne_complete(prelevement="PRV-001")
        ligne2 = _ligne_complete(prelevement="PRV-002")
        ligne3 = _ligne_complete(prelevement="PRV-003")
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne1, ligne2, ligne3]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            echantillons = charger_excel("fictif.xlsx")
        assert len(echantillons) == 3
        assert [e.prelevement for e in echantillons] == ["PRV-001", "PRV-002", "PRV-003"]


# ---------------------------------------------------------------------------
# Cas 5 : fermeture du classeur
# ---------------------------------------------------------------------------

class TestFermetureClasseur:
    """Le classeur doit toujours être fermé après lecture, même sur liste vide."""

    def test_classeur_ferme_apres_lecture_nominale(self):
        ligne = _ligne_complete(prelevement="PRV-001")
        classeur_mock = _creer_classeur_mock(
            sheetnames=["Prv Am"],
            lignes_par_feuille={"Prv Am": [ligne]},
        )
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            charger_excel("fictif.xlsx")
        classeur_mock.close.assert_called_once()

    def test_classeur_ferme_sur_feuille_absente(self):
        classeur_mock = _creer_classeur_mock(sheetnames=["AutreFeuille"])
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock):
            charger_excel("fictif.xlsx")
        classeur_mock.close.assert_called_once()

    def test_classeur_ouvert_en_read_only(self):
        """openpyxl doit être appelé avec read_only=True, data_only=True et keep_vba=True."""
        classeur_mock = _creer_classeur_mock(sheetnames=[])
        with patch("src.services.excel_reader.openpyxl.load_workbook", return_value=classeur_mock) as mock_load:
            charger_excel("mon_fichier.xlsx")
        mock_load.assert_called_once_with("mon_fichier.xlsx", read_only=True, data_only=True, keep_vba=True)


# ---------------------------------------------------------------------------
# Tests : maj_bulles_depuis_echantillons
# ---------------------------------------------------------------------------

def _ech(prelevement: str, resultat: str = "Absence amiante") -> Echantillon:
    """Fabrique un Echantillon minimal pour les tests de mise à jour."""
    from src.services.couleur_resolver import resoudre_couleur
    couleur, mention = resoudre_couleur(resultat)
    return Echantillon(
        prelevement=prelevement,
        description="Desc",
        resultat=resultat,
        localisation="Local",
        element_sonde="Elem",
        reference_plan="",
        couleur=couleur,
        mention=mention,
        texte_ligne1=prelevement,
        texte_ligne2="Desc",
        texte_ligne3="Local",
    )


def _bulle_avec(prelevement: str, resultat: str = "Absence amiante") -> BulleLegende:
    ech = _ech(prelevement, resultat)
    return BulleLegende(
        ancrage=(10.0, 10.0),
        position=(50.0, 50.0),
        echantillon=ech,
        couleur_rgb=ech.couleur,
    )


class TestMajBullesDepuisEchantillons:
    """Vérifie la mise à jour automatique des bulles lors du rechargement Excel."""

    def test_bulle_existante_mise_a_jour(self):
        """Une bulle dont le prélèvement existe dans la nouvelle liste est mise à jour."""
        bulle = _bulle_avec("PRV-001", resultat="Absence amiante")
        planche = Planche(numero=1, bulles=[bulle])

        nouvel_ech = _ech("PRV-001", resultat="Présence amiante")
        nb = maj_bulles_depuis_echantillons([planche], [nouvel_ech])

        assert nb == 1
        assert bulle.echantillon.resultat == "Présence amiante"

    def test_couleur_bulle_mise_a_jour(self):
        """La couleur_rgb de la bulle est synchronisée avec le nouvel échantillon."""
        bulle = _bulle_avec("PRV-001", resultat="Absence amiante")
        couleur_avant = bulle.couleur_rgb
        planche = Planche(numero=1, bulles=[bulle])

        nouvel_ech = _ech("PRV-001", resultat="Présence amiante")
        maj_bulles_depuis_echantillons([planche], [nouvel_ech])

        assert bulle.couleur_rgb != couleur_avant
        assert bulle.couleur_rgb == nouvel_ech.couleur

    def test_bulle_introuvable_conservee(self):
        """Une bulle dont le prélèvement n'existe plus dans l'Excel est conservée."""
        bulle = _bulle_avec("PRV-DISPARU")
        planche = Planche(numero=1, bulles=[bulle])
        resultat_avant = bulle.echantillon.resultat

        nb = maj_bulles_depuis_echantillons([planche], [_ech("PRV-AUTRE")])

        assert nb == 0
        assert bulle.echantillon.resultat == resultat_avant

    def test_bulle_sans_echantillon_ignoree(self):
        """Une bulle sans échantillon lié n'est pas touchée."""
        bulle = BulleLegende(ancrage=(0.0, 0.0), position=(0.0, 0.0), echantillon=None)
        planche = Planche(numero=1, bulles=[bulle])

        nb = maj_bulles_depuis_echantillons([planche], [_ech("PRV-001")])

        assert nb == 0
        assert bulle.echantillon is None

    def test_plusieurs_planches_toutes_mises_a_jour(self):
        """Les bulles de toutes les planches sont mises à jour, pas seulement la première."""
        bulle1 = _bulle_avec("PRV-001")
        bulle2 = _bulle_avec("PRV-002")
        planches = [
            Planche(numero=1, bulles=[bulle1]),
            Planche(numero=2, bulles=[bulle2]),
        ]
        nouveaux = [
            _ech("PRV-001", resultat="Présence amiante"),
            _ech("PRV-002", resultat="Présence amiante"),
        ]

        nb = maj_bulles_depuis_echantillons(planches, nouveaux)

        assert nb == 2
        assert bulle1.echantillon.resultat == "Présence amiante"
        assert bulle2.echantillon.resultat == "Présence amiante"

    def test_position_ancrage_inchangee(self):
        """La position et l'ancrage de la bulle ne sont pas modifiés."""
        bulle = _bulle_avec("PRV-001")
        bulle.ancrage = (123.0, 456.0)
        bulle.position = (789.0, 321.0)
        planche = Planche(numero=1, bulles=[bulle])

        maj_bulles_depuis_echantillons([planche], [_ech("PRV-001", "Présence amiante")])

        assert bulle.ancrage == (123.0, 456.0)
        assert bulle.position == (789.0, 321.0)

    def test_retourne_zero_si_aucune_bulle(self):
        """Retourne 0 si les planches ne contiennent aucune bulle."""
        planche = Planche(numero=1, bulles=[])
        nb = maj_bulles_depuis_echantillons([planche], [_ech("PRV-001")])
        assert nb == 0

    def test_cle_primaire_distingue_deux_bulles(self):
        """
        Deux bulles avec des id_primaire différents (colonne K) sont mises à jour
        indépendamment — la clé primaire permet de les distinguer même si [G] est identique.
        """
        from src.services.couleur_resolver import resoudre_couleur

        def _ech(id_primaire, resultat="Absence amiante"):
            couleur, mention = resoudre_couleur(resultat)
            return Echantillon(
                prelevement="PRV-001", description="Desc", resultat=resultat,
                localisation="Couloir", element_sonde="Elem", reference_plan="",
                couleur=couleur, mention=mention,
                texte_ligne1="PRV-001", texte_ligne2="Desc", texte_ligne3="Couloir",
                id_primaire=id_primaire,
            )

        def _bulle(id_primaire):
            ech = _ech(id_primaire)
            return BulleLegende(ancrage=(0.0, 0.0), position=(0.0, 0.0),
                                echantillon=ech, couleur_rgb=ech.couleur)

        bulle_a = _bulle("K-001")
        bulle_b = _bulle("K-002")
        planche = Planche(numero=1, bulles=[bulle_a, bulle_b])

        nouveaux = [
            _ech("K-001", "Présence amiante"),
            _ech("K-002", "Absence amiante"),
        ]
        nb = maj_bulles_depuis_echantillons([planche], nouveaux)

        assert nb == 2
        assert bulle_a.echantillon.resultat == "Présence amiante"
        assert bulle_b.echantillon.resultat == "Absence amiante"
