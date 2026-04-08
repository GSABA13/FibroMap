"""
Tests unitaires pour les modèles de données des formes (src/models/forme.py).

Vérifie que les dataclasses sont correctement définies : valeurs par défaut,
unicité des identifiants, indépendance des instances, et absence de tout
import PyQt6 dans le module de modèles.
"""

import ast
import uuid
import importlib

import pytest

from src.models.forme import (
    FormeBase,
    FormeRect,
    FormeCercle,
    FormeLigne,
    FormePolygone,
    FormeLignesConnectees,
)
from src.utils.constantes import (
    COULEUR_VERTE,
    COULEUR_ORANGE,
    COULEUR_ROUGE,
    ALPHA_PLEIN,
    ALPHA_SEMI,
)


# ---------------------------------------------------------------------------
# Vérification d'absence de dépendance PyQt6 (analyse AST des imports)
# ---------------------------------------------------------------------------

class TestAbsenceImportPyQt6:
    """Garantit que src/models/forme.py ne contient aucun import PyQt6."""

    def test_module_forme_ne_contient_pas_import_pyqt6(self):
        """
        Analyse syntaxiquement le fichier forme.py pour détecter tout
        noeud import ou from-import ciblant PyQt6.
        """
        import src.models.forme as module_forme
        with open(module_forme.__file__, encoding="utf-8") as f:
            source = f.read()

        arbre = ast.parse(source)
        imports_pyqt6 = []

        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    if alias.name.startswith("PyQt6"):
                        imports_pyqt6.append(alias.name)
            elif isinstance(noeud, ast.ImportFrom):
                if noeud.module and noeud.module.startswith("PyQt6"):
                    imports_pyqt6.append(noeud.module)

        assert imports_pyqt6 == [], (
            f"forme.py ne doit contenir aucun import PyQt6, trouvé : {imports_pyqt6}"
        )


# ---------------------------------------------------------------------------
# FormeBase — valeurs par défaut
# ---------------------------------------------------------------------------

class TestFormeBaseDefauts:
    """Vérifie les valeurs par défaut de FormeBase."""

    def test_couleur_par_defaut_est_verte(self):
        forme = FormeBase()
        assert forme.couleur_rgb == COULEUR_VERTE

    def test_alpha_par_defaut_est_plein(self):
        forme = FormeBase()
        assert forme.alpha == ALPHA_PLEIN

    def test_points_par_defaut_est_liste_vide(self):
        forme = FormeBase()
        assert forme.points == []

    def test_id_par_defaut_est_uuid_valide(self):
        forme = FormeBase()
        # Doit être parseable comme un UUID valide
        parsed = uuid.UUID(forme.id)
        assert str(parsed) == forme.id

    def test_id_est_une_chaine(self):
        forme = FormeBase()
        assert isinstance(forme.id, str)


# ---------------------------------------------------------------------------
# FormeBase — unicité et indépendance des instances
# ---------------------------------------------------------------------------

class TestFormeBaseUnicite:
    """Vérifie que chaque instance reçoit un identifiant unique."""

    def test_deux_instances_ont_des_ids_distincts(self):
        forme_a = FormeBase()
        forme_b = FormeBase()
        assert forme_a.id != forme_b.id

    def test_cent_instances_ont_toutes_des_ids_distincts(self):
        ids = {FormeBase().id for _ in range(100)}
        assert len(ids) == 100

    def test_points_ne_sont_pas_partages_entre_instances(self):
        """La liste points doit être propre à chaque instance (field factory)."""
        forme_a = FormeBase()
        forme_b = FormeBase()
        forme_a.points.append((1.0, 2.0))
        assert forme_b.points == [], (
            "La liste points de forme_b ne doit pas être affectée par forme_a"
        )


# ---------------------------------------------------------------------------
# FormeBase — modification des attributs
# ---------------------------------------------------------------------------

class TestFormeBaseModification:
    """Vérifie que les attributs sont mutables comme attendu."""

    def test_modification_couleur(self):
        forme = FormeBase()
        forme.couleur_rgb = (255, 0, 0)
        assert forme.couleur_rgb == (255, 0, 0)

    def test_modification_alpha(self):
        forme = FormeBase()
        forme.alpha = 128
        assert forme.alpha == 128

    def test_ajout_de_points(self):
        forme = FormeBase()
        forme.points.append((10.0, 20.0))
        assert len(forme.points) == 1
        assert forme.points[0] == (10.0, 20.0)

    def test_assignation_directe_de_points(self):
        forme = FormeBase()
        forme.points = [(0.0, 0.0), (100.0, 100.0)]
        assert len(forme.points) == 2


# ---------------------------------------------------------------------------
# Sous-classes — héritage et spécificité
# ---------------------------------------------------------------------------

class TestSousClassesHeritage:
    """Vérifie que toutes les sous-classes héritent correctement de FormeBase."""

    @pytest.mark.parametrize("classe", [
        FormeRect,
        FormeCercle,
        FormeLigne,
        FormePolygone,
        FormeLignesConnectees,
    ])
    def test_est_instance_de_forme_base(self, classe):
        assert isinstance(classe(), FormeBase)

    @pytest.mark.parametrize("classe", [
        FormeRect,
        FormeCercle,
        FormeLigne,
        FormePolygone,
        FormeLignesConnectees,
    ])
    def test_valeurs_par_defaut_coherentes(self, classe):
        forme = classe()
        assert forme.couleur_rgb == COULEUR_VERTE
        assert forme.alpha == ALPHA_PLEIN
        assert forme.points == []

    @pytest.mark.parametrize("classe", [
        FormeRect,
        FormeCercle,
        FormeLigne,
        FormePolygone,
        FormeLignesConnectees,
    ])
    def test_ids_distincts_entre_sous_classes(self, classe):
        f1 = classe()
        f2 = classe()
        assert f1.id != f2.id


# ---------------------------------------------------------------------------
# Sous-classes — construction avec arguments
# ---------------------------------------------------------------------------

class TestSousClassesConstruction:
    """Vérifie la construction des sous-classes avec des paramètres explicites."""

    def test_forme_rect_avec_deux_points(self):
        forme = FormeRect(points=[(0.0, 0.0), (100.0, 80.0)])
        assert len(forme.points) == 2
        assert forme.points[0] == (0.0, 0.0)
        assert forme.points[1] == (100.0, 80.0)

    def test_forme_cercle_avec_centre_et_bord(self):
        centre = (50.0, 50.0)
        bord = (80.0, 50.0)
        forme = FormeCercle(points=[centre, bord])
        assert forme.points[0] == centre
        assert forme.points[1] == bord

    def test_forme_ligne_avec_deux_points(self):
        forme = FormeLigne(points=[(0.0, 0.0), (200.0, 150.0)])
        assert len(forme.points) == 2

    def test_forme_polygone_avec_n_points(self):
        pts = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
        forme = FormePolygone(points=pts)
        assert len(forme.points) == 4

    def test_forme_lignes_connectees_avec_n_points(self):
        pts = [(0.0, 0.0), (30.0, 10.0), (60.0, 5.0)]
        forme = FormeLignesConnectees(points=pts)
        assert len(forme.points) == 3

    def test_construction_avec_couleur_rouge(self):
        forme = FormeRect(couleur_rgb=(255, 0, 0), points=[(0.0, 0.0), (10.0, 10.0)])
        assert forme.couleur_rgb == (255, 0, 0)

    def test_construction_avec_alpha_semi(self):
        forme = FormeCercle(alpha=128, points=[(50.0, 50.0), (80.0, 50.0)])
        assert forme.alpha == 128

    def test_construction_avec_id_explicite(self):
        id_fixe = "mon-id-fixe"
        forme = FormePolygone(id=id_fixe)
        assert forme.id == id_fixe


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------

class TestCasLimites:
    """Vérifie le comportement des modèles dans les cas limites."""

    def test_forme_base_avec_liste_vide(self):
        forme = FormeBase(points=[])
        assert forme.points == []

    def test_forme_polygone_accepte_deux_points_seulement(self):
        """Le modèle n'impose pas de contrainte métier sur le nombre de points."""
        forme = FormePolygone(points=[(0.0, 0.0), (10.0, 10.0)])
        assert len(forme.points) == 2

    def test_forme_rect_accepte_liste_vide(self):
        """Une forme peut être créée sans points (tracé en cours)."""
        forme = FormeRect()
        assert forme.points == []

    def test_points_flottants_acceptes(self):
        forme = FormeLigne(points=[(0.5, 1.7), (99.9, 200.3)])
        assert forme.points[0] == (0.5, 1.7)
        assert forme.points[1] == (99.9, 200.3)

    def test_couleur_rgb_tuple_trois_entiers(self):
        forme = FormeBase(couleur_rgb=(18, 169, 30))
        r, g, b = forme.couleur_rgb
        assert isinstance(r, int)
        assert isinstance(g, int)
        assert isinstance(b, int)


# ---------------------------------------------------------------------------
# Constantes importées — intégration avec constantes.py
# ---------------------------------------------------------------------------

class TestIntegrationConstantes:
    """
    Vérifie que les valeurs par défaut de forme.py sont bien issues de
    constantes.py et correspondent aux valeurs documentées.
    """

    def test_couleur_verte_defaut_correspond_a_constante(self):
        """COULEUR_VERTE dans constantes.py = RGB(18, 169, 30)."""
        assert COULEUR_VERTE == (18, 169, 30)

    def test_alpha_plein_correspond_a_constante(self):
        """ALPHA_PLEIN dans constantes.py = 255."""
        assert ALPHA_PLEIN == 255

    def test_alpha_semi_correspond_a_constante(self):
        """ALPHA_SEMI dans constantes.py = 128."""
        assert ALPHA_SEMI == 128

    def test_couleur_orange_correspond_a_constante(self):
        """COULEUR_ORANGE dans constantes.py = RGB(255, 128, 0)."""
        assert COULEUR_ORANGE == (255, 128, 0)

    def test_couleur_rouge_correspond_a_constante(self):
        """COULEUR_ROUGE dans constantes.py = RGB(255, 0, 0)."""
        assert COULEUR_ROUGE == (255, 0, 0)

    def test_forme_base_couleur_verte_via_constante(self):
        """La couleur par défaut de FormeBase correspond exactement à COULEUR_VERTE."""
        forme = FormeBase()
        assert forme.couleur_rgb == (18, 169, 30)

    def test_forme_base_alpha_plein_via_constante(self):
        """L'alpha par défaut de FormeBase correspond exactement à ALPHA_PLEIN."""
        forme = FormeBase()
        assert forme.alpha == 255


# ---------------------------------------------------------------------------
# Indépendance de la couleur par défaut entre instances
# ---------------------------------------------------------------------------

class TestIndependanceCouleurDefaut:
    """
    Vérifie que la modification de la couleur d'une instance n'affecte pas
    les autres instances créées avec la valeur par défaut.

    Cas introduit par le passage à default_factory=lambda: COULEUR_VERTE
    dans forme.py : chaque instance doit avoir son propre tuple couleur.
    """

    def test_modification_couleur_instance_a_naffecte_pas_instance_b(self):
        """
        Modifier couleur_rgb de forme_a ne doit pas changer couleur_rgb de forme_b.
        Les tuples étant immuables en Python, ce test est conservatif mais
        il documente l'intention de non-partage entre instances.
        """
        forme_a = FormeBase()
        forme_b = FormeBase()
        forme_a.couleur_rgb = COULEUR_ROUGE
        assert forme_b.couleur_rgb == COULEUR_VERTE, (
            "La modification de couleur_rgb de forme_a ne doit pas affecter forme_b"
        )

    def test_modification_couleur_sous_classe_naffecte_pas_autres(self):
        """Même vérification pour une sous-classe (FormeRect)."""
        rect_a = FormeRect()
        rect_b = FormeRect()
        rect_a.couleur_rgb = COULEUR_ORANGE
        assert rect_b.couleur_rgb == COULEUR_VERTE

    def test_cent_instances_ont_toutes_couleur_verte_par_defaut(self):
        """Toutes les instances créées sans argument ont la couleur verte."""
        instances = [FormeBase() for _ in range(100)]
        assert all(f.couleur_rgb == COULEUR_VERTE for f in instances)

    def test_couleur_orange_assigne_via_constante(self):
        """La couleur orange peut être assignée via la constante."""
        forme = FormeRect(couleur_rgb=COULEUR_ORANGE)
        assert forme.couleur_rgb == COULEUR_ORANGE
        assert forme.couleur_rgb == (255, 128, 0)

    def test_couleur_rouge_assigne_via_constante(self):
        """La couleur rouge peut être assignée via la constante."""
        forme = FormeCercle(couleur_rgb=COULEUR_ROUGE)
        assert forme.couleur_rgb == COULEUR_ROUGE
        assert forme.couleur_rgb == (255, 0, 0)

    def test_alpha_semi_assigne_via_constante(self):
        """ALPHA_SEMI peut être assigné à la construction."""
        forme = FormePolygone(alpha=ALPHA_SEMI)
        assert forme.alpha == 128

    def test_alpha_plein_apres_modification_semi(self):
        """On peut revenir à ALPHA_PLEIN après avoir mis ALPHA_SEMI."""
        forme = FormeBase()
        forme.alpha = ALPHA_SEMI
        assert forme.alpha == 128
        forme.alpha = ALPHA_PLEIN
        assert forme.alpha == 255
