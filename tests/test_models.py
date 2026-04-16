"""
Tests unitaires pour les modèles de données des formes (src/models/forme.py).

Vérifie que les dataclasses sont correctement définies : valeurs par défaut,
unicité des identifiants, indépendance des instances, et absence de tout
import PyQt6 dans le module de modèles.

Couvre également la logique géométrique `contient_point` de chaque sous-classe.
"""

import ast
import math
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


# ---------------------------------------------------------------------------
# contient_point — FormeBase (bounding-box)
# ---------------------------------------------------------------------------

class TestFormeBaseContientPoint:
    """
    Vérifie l'implémentation par défaut de contient_point dans FormeBase :
    test de bounding-box avec tolérance sur les points de contrôle.
    """

    def test_liste_vide_retourne_faux(self):
        """Sans points, contient_point doit retourner False."""
        forme = FormeBase(points=[])
        assert forme.contient_point(0.0, 0.0) is False

    def test_point_interieur_bounding_box(self):
        """Un point situé à l'intérieur de la bounding-box est détecté."""
        forme = FormeBase(points=[(10.0, 10.0), (90.0, 80.0)])
        assert forme.contient_point(50.0, 45.0) is True

    def test_point_exterieur_bounding_box(self):
        """Un point clairement en dehors n'est pas détecté."""
        forme = FormeBase(points=[(10.0, 10.0), (90.0, 80.0)])
        assert forme.contient_point(200.0, 200.0) is False

    def test_point_dans_la_tolerance(self):
        """Un point légèrement en dehors de la bounding-box, mais dans la tolérance."""
        # bounding-box : x=[10,90], y=[10,80]. Avec tolerance=5, bord gauche à 5.0
        forme = FormeBase(points=[(10.0, 10.0), (90.0, 80.0)])
        assert forme.contient_point(6.0, 45.0, tolerance=5.0) is True

    def test_point_hors_tolerance(self):
        """Un point à exactement tolérance+1 en dehors est rejeté."""
        forme = FormeBase(points=[(10.0, 10.0), (90.0, 80.0)])
        assert forme.contient_point(4.0, 45.0, tolerance=5.0) is False

    def test_tolerance_nulle(self):
        """Avec tolérance=0, seul le point exactement sur la bounding-box est accepté."""
        forme = FormeBase(points=[(10.0, 10.0), (90.0, 80.0)])
        assert forme.contient_point(10.0, 10.0, tolerance=0.0) is True
        assert forme.contient_point(9.9, 10.0, tolerance=0.0) is False

    def test_un_seul_point(self):
        """Avec un seul point, la bounding-box est dégénérée ; le point exact est dedans."""
        forme = FormeBase(points=[(50.0, 50.0)])
        assert forme.contient_point(50.0, 50.0, tolerance=0.0) is True

    def test_un_seul_point_dans_tolerance(self):
        """Avec un seul point, un test dans la tolérance est positif."""
        forme = FormeBase(points=[(50.0, 50.0)])
        assert forme.contient_point(53.0, 50.0, tolerance=5.0) is True

    def test_un_seul_point_hors_tolerance(self):
        """Avec un seul point, un test hors tolérance est négatif."""
        forme = FormeBase(points=[(50.0, 50.0)])
        assert forme.contient_point(60.0, 50.0, tolerance=5.0) is False


# ---------------------------------------------------------------------------
# contient_point — FormeCercle
# ---------------------------------------------------------------------------

class TestFormeCercleContientPoint:
    """
    Vérifie la détection de hit sur un cercle.
    Le cercle est défini par centre=points[0] et point de bord=points[1].
    """

    def _cercle_rayon_30(self):
        """Cercle centré en (50, 50) avec rayon 30 (bord en (80, 50))."""
        return FormeCercle(points=[(50.0, 50.0), (80.0, 50.0)])

    def test_point_au_centre(self):
        """Le centre appartient au cercle."""
        forme = self._cercle_rayon_30()
        assert forme.contient_point(50.0, 50.0) is True

    def test_point_interieur(self):
        """Un point clairement à l'intérieur du disque."""
        forme = self._cercle_rayon_30()
        assert forme.contient_point(60.0, 50.0) is True

    def test_point_sur_le_bord_exact(self):
        """Un point exactement sur le bord (distance = rayon) est dans le cercle."""
        forme = self._cercle_rayon_30()
        # Distance = 30, rayon = 30 → doit être accepté avec tolérance=0
        assert forme.contient_point(80.0, 50.0, tolerance=0.0) is True

    def test_point_dans_la_tolerance_hors_bord(self):
        """Un point légèrement au-delà du bord mais dans la tolérance est accepté."""
        forme = self._cercle_rayon_30()
        # Distance de (50,50) à (83, 50) = 33, rayon=30, tolerance=5 → 33 <= 35
        assert forme.contient_point(83.0, 50.0, tolerance=5.0) is True

    def test_point_hors_cercle_et_tolerance(self):
        """Un point nettement hors du cercle et de la tolérance est rejeté."""
        forme = self._cercle_rayon_30()
        # Distance de (50,50) à (150, 50) = 100 > 30+5
        assert forme.contient_point(150.0, 50.0, tolerance=5.0) is False

    def test_point_a_45_degres_interieur(self):
        """Un point à 45° à l'intérieur du disque."""
        forme = self._cercle_rayon_30()
        # distance = 20*sqrt(2) ≈ 28.28 < 30
        assert forme.contient_point(50.0 + 20.0, 50.0 + 20.0) is True

    def test_point_a_45_degres_exterieur(self):
        """Un point à 45° à l'extérieur du disque, hors tolérance."""
        forme = self._cercle_rayon_30()
        # distance = 25*sqrt(2) ≈ 35.36 > 30+5
        assert forme.contient_point(50.0 + 25.0, 50.0 + 25.0, tolerance=5.0) is False

    def test_moins_de_deux_points_retourne_faux(self):
        """Un cercle sans 2 points retourne toujours False."""
        forme = FormeCercle(points=[(50.0, 50.0)])
        assert forme.contient_point(50.0, 50.0) is False

    def test_liste_vide_retourne_faux(self):
        """Un cercle sans points retourne toujours False."""
        forme = FormeCercle(points=[])
        assert forme.contient_point(0.0, 0.0) is False

    def test_rayon_nul_point_sur_centre(self):
        """Cercle de rayon 0 : seul le centre exact est dans la tolérance nulle."""
        forme = FormeCercle(points=[(50.0, 50.0), (50.0, 50.0)])
        assert forme.contient_point(50.0, 50.0, tolerance=0.0) is True
        assert forme.contient_point(51.0, 50.0, tolerance=0.0) is False


# ---------------------------------------------------------------------------
# contient_point — FormeLigne
# ---------------------------------------------------------------------------

class TestFormeLigneContientPoint:
    """
    Vérifie la détection de hit sur un segment de droite.
    La distance est calculée par projection orthogonale.
    """

    def _segment_horizontal(self):
        """Segment de (0, 0) à (100, 0)."""
        return FormeLigne(points=[(0.0, 0.0), (100.0, 0.0)])

    def test_point_sur_le_segment_au_milieu(self):
        """Un point exactement sur le segment est détecté."""
        forme = self._segment_horizontal()
        assert forme.contient_point(50.0, 0.0, tolerance=0.0) is True

    def test_point_sur_le_segment_a_lextrémite(self):
        """Le premier point du segment est détecté."""
        forme = self._segment_horizontal()
        assert forme.contient_point(0.0, 0.0, tolerance=0.0) is True

    def test_point_sur_le_segment_au_bout(self):
        """Le dernier point du segment est détecté."""
        forme = self._segment_horizontal()
        assert forme.contient_point(100.0, 0.0, tolerance=0.0) is True

    def test_point_perpendiculaire_dans_tolerance(self):
        """Un point à 3px du segment (perpendiculaire) avec tolérance=5 est accepté."""
        forme = self._segment_horizontal()
        assert forme.contient_point(50.0, 3.0, tolerance=5.0) is True

    def test_point_perpendiculaire_hors_tolerance(self):
        """Un point à 10px du segment avec tolérance=5 est rejeté."""
        forme = self._segment_horizontal()
        assert forme.contient_point(50.0, 10.0, tolerance=5.0) is False

    def test_point_en_dehors_de_la_projection(self):
        """
        Un point situé après l'extrémité du segment (hors projection).
        La distance est calculée vers l'extrémité la plus proche.
        """
        forme = self._segment_horizontal()
        # Point (110, 0) : projection clampée à t=1 → distance vers (100,0) = 10 > 5
        assert forme.contient_point(110.0, 0.0, tolerance=5.0) is False

    def test_point_pres_extremite_dans_tolerance(self):
        """Un point très proche d'une extrémité est accepté selon la tolérance."""
        forme = self._segment_horizontal()
        # Point (103, 0) : distance vers (100,0) = 3 <= 5
        assert forme.contient_point(103.0, 0.0, tolerance=5.0) is True

    def test_segment_diagonal(self):
        """Test sur un segment diagonal."""
        # Segment de (0,0) à (100,100) — la diagonale
        forme = FormeLigne(points=[(0.0, 0.0), (100.0, 100.0)])
        # Point (50,50) est exactement sur le segment
        assert forme.contient_point(50.0, 50.0, tolerance=0.0) is True

    def test_segment_diagonal_point_a_cote(self):
        """Un point nettement à côté d'un segment diagonal est rejeté."""
        forme = FormeLigne(points=[(0.0, 0.0), (100.0, 100.0)])
        # Point (0, 50) est à 35px environ de la diagonale
        assert forme.contient_point(0.0, 50.0, tolerance=5.0) is False

    def test_moins_de_deux_points_retourne_faux(self):
        """Un segment avec un seul point retourne False."""
        forme = FormeLigne(points=[(0.0, 0.0)])
        assert forme.contient_point(0.0, 0.0) is False

    def test_liste_vide_retourne_faux(self):
        """Un segment sans points retourne False."""
        forme = FormeLigne(points=[])
        assert forme.contient_point(0.0, 0.0) is False

    def test_segment_degenere_deux_points_identiques(self):
        """Segment dégénéré (deux points identiques) : se comporte comme un point."""
        forme = FormeLigne(points=[(50.0, 50.0), (50.0, 50.0)])
        assert forme.contient_point(50.0, 50.0, tolerance=0.0) is True
        assert forme.contient_point(60.0, 50.0, tolerance=5.0) is False


# ---------------------------------------------------------------------------
# contient_point — FormeLignesConnectees
# ---------------------------------------------------------------------------

class TestFormeLignesConnecteesContientPoint:
    """
    Vérifie la détection de hit sur une polyligne (série de segments).
    """

    def _polyligne_en_l(self):
        """Polyligne en L : (0,0) → (100,0) → (100,100)."""
        return FormeLignesConnectees(points=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)])

    def test_point_sur_premier_segment(self):
        """Un point sur le premier segment est détecté."""
        forme = self._polyligne_en_l()
        assert forme.contient_point(50.0, 0.0, tolerance=0.0) is True

    def test_point_sur_deuxieme_segment(self):
        """Un point sur le second segment est détecté."""
        forme = self._polyligne_en_l()
        assert forme.contient_point(100.0, 50.0, tolerance=0.0) is True

    def test_point_entre_deux_segments_hors_tolerance(self):
        """Un point entre les deux segments mais hors tolérance est rejeté."""
        forme = self._polyligne_en_l()
        # Point (50, 50) : distance au segment 1 = 50, distance au segment 2 = 50 → rejeté avec tol=5
        assert forme.contient_point(50.0, 50.0, tolerance=5.0) is False

    def test_point_sur_le_coude(self):
        """Le point de coude (100, 0) appartient aux deux segments."""
        forme = self._polyligne_en_l()
        assert forme.contient_point(100.0, 0.0, tolerance=0.0) is True

    def test_point_dans_tolerance_premier_segment(self):
        """Un point proche du premier segment (dans la tolérance) est accepté."""
        forme = self._polyligne_en_l()
        assert forme.contient_point(50.0, 3.0, tolerance=5.0) is True

    def test_point_hors_de_la_polyligne(self):
        """Un point nettement en dehors de tous les segments est rejeté."""
        forme = self._polyligne_en_l()
        assert forme.contient_point(200.0, 200.0, tolerance=5.0) is False

    def test_un_seul_point_dans_tolerance(self):
        """Une polyligne d'un seul point : test de distance pure."""
        forme = FormeLignesConnectees(points=[(50.0, 50.0)])
        assert forme.contient_point(53.0, 50.0, tolerance=5.0) is True

    def test_un_seul_point_hors_tolerance(self):
        """Une polyligne d'un seul point hors tolérance est rejetée."""
        forme = FormeLignesConnectees(points=[(50.0, 50.0)])
        assert forme.contient_point(60.0, 50.0, tolerance=5.0) is False

    def test_liste_vide_retourne_faux(self):
        """Une polyligne sans points retourne False."""
        forme = FormeLignesConnectees(points=[])
        assert forme.contient_point(0.0, 0.0) is False

    def test_polyligne_trois_segments(self):
        """Test sur une polyligne avec trois segments consécutifs."""
        forme = FormeLignesConnectees(
            points=[(0.0, 0.0), (50.0, 50.0), (100.0, 0.0), (150.0, 50.0)]
        )
        # Point sur le troisième segment, entre (100,0) et (150,50)
        assert forme.contient_point(125.0, 25.0, tolerance=1.0) is True


# ---------------------------------------------------------------------------
# contient_point — FormePolygone
# ---------------------------------------------------------------------------

class TestFormePolygoneContientPoint:
    """
    Vérifie la détection de hit sur un polygone fermé.
    Deux mécanismes : test des bords (distance ≤ tolérance) et ray casting intérieur.
    """

    def _carre_100(self):
        """Carré de 100px de côté centré sur l'origine : (0,0)-(100,0)-(100,100)-(0,100)."""
        return FormePolygone(points=[
            (0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)
        ])

    # --- Tests intérieur (ray casting) ---

    def test_point_strictement_interieur(self):
        """Un point clairement à l'intérieur du carré est détecté."""
        forme = self._carre_100()
        assert forme.contient_point(50.0, 50.0) is True

    def test_point_centre_exact(self):
        """Le centre géométrique du carré est à l'intérieur."""
        forme = self._carre_100()
        assert forme.contient_point(50.0, 50.0, tolerance=0.0) is True

    def test_point_strictement_exterieur(self):
        """Un point clairement en dehors du carré est rejeté."""
        forme = self._carre_100()
        assert forme.contient_point(200.0, 200.0, tolerance=0.0) is False

    def test_point_exterieur_negatif(self):
        """Un point avec des coordonnées négatives est hors du carré."""
        forme = self._carre_100()
        assert forme.contient_point(-50.0, -50.0, tolerance=0.0) is False

    # --- Tests bords ---

    def test_point_sur_bord_haut(self):
        """Un point exactement sur le bord supérieur est détecté."""
        forme = self._carre_100()
        assert forme.contient_point(50.0, 0.0, tolerance=0.0) is True

    def test_point_sur_bord_gauche(self):
        """Un point exactement sur le bord gauche est détecté."""
        forme = self._carre_100()
        assert forme.contient_point(0.0, 50.0, tolerance=0.0) is True

    def test_point_dans_tolerance_bord(self):
        """Un point légèrement à l'extérieur du bord mais dans la tolérance."""
        forme = self._carre_100()
        # Point (50, -3) : à 3px du bord supérieur, tolérance=5 → accepté
        assert forme.contient_point(50.0, -3.0, tolerance=5.0) is True

    def test_point_hors_tolerance_bord(self):
        """Un point au-delà de la tolérance du bord est rejeté."""
        forme = self._carre_100()
        # Point (50, -10) : à 10px du bord supérieur, tolérance=5 → rejeté
        assert forme.contient_point(50.0, -10.0, tolerance=5.0) is False

    def test_coin_dans_tolerance(self):
        """Un coin du polygone est dans sa propre tolérance."""
        forme = self._carre_100()
        assert forme.contient_point(0.0, 0.0, tolerance=0.0) is True

    # --- Tests avec des polygones variés ---

    def test_triangle_point_interieur(self):
        """Un point à l'intérieur d'un triangle rectangle."""
        forme = FormePolygone(points=[(0.0, 0.0), (100.0, 0.0), (0.0, 100.0)])
        assert forme.contient_point(20.0, 20.0, tolerance=0.0) is True

    def test_triangle_point_exterieur(self):
        """Un point hors du triangle rectangle."""
        forme = FormePolygone(points=[(0.0, 0.0), (100.0, 0.0), (0.0, 100.0)])
        assert forme.contient_point(80.0, 80.0, tolerance=0.0) is False

    def test_polygone_deux_points_test_bord(self):
        """Un polygone dégénéré à 2 points ne fait pas de ray casting mais teste les bords."""
        forme = FormePolygone(points=[(0.0, 0.0), (100.0, 0.0)])
        # Le point sur le segment dégénéré est détecté via le test de bord
        assert forme.contient_point(50.0, 0.0, tolerance=0.0) is True

    def test_liste_vide_retourne_faux(self):
        """Un polygone sans points retourne False."""
        forme = FormePolygone(points=[])
        assert forme.contient_point(0.0, 0.0) is False

    def test_un_seul_point_retourne_faux(self):
        """Un polygone d'un seul point retourne False (condition len < 2)."""
        forme = FormePolygone(points=[(50.0, 50.0)])
        assert forme.contient_point(50.0, 50.0) is False

    def test_polygone_non_convexe_point_interieur(self):
        """Un polygone en forme de L : un point dans le creux intérieur."""
        # Polygone en L (vue de dessus) : intérieur complexe
        forme = FormePolygone(points=[
            (0.0, 0.0), (60.0, 0.0), (60.0, 40.0),
            (100.0, 40.0), (100.0, 100.0), (0.0, 100.0)
        ])
        # Point dans la partie basse du L
        assert forme.contient_point(80.0, 70.0, tolerance=0.0) is True
        # Point dans la partie haute du L
        assert forme.contient_point(30.0, 20.0, tolerance=0.0) is True

    def test_polygone_non_convexe_point_exterieur_dans_creux(self):
        """Un polygone en L : un point dans le creux (extérieur) est rejeté."""
        forme = FormePolygone(points=[
            (0.0, 0.0), (60.0, 0.0), (60.0, 40.0),
            (100.0, 40.0), (100.0, 100.0), (0.0, 100.0)
        ])
        # Point dans le creux haut-droit du L : (80, 20) est hors du polygone
        assert forme.contient_point(80.0, 20.0, tolerance=0.0) is False


# ---------------------------------------------------------------------------
# Champ epaisseur — FormeBase et sous-classes
# ---------------------------------------------------------------------------

class TestFormeBaseEpaisseur:
    """FormeBase doit exposer un champ epaisseur initialisé à 2.0."""

    def test_epaisseur_defaut_vaut_2(self):
        assert FormeBase().epaisseur == 2.0

    def test_epaisseur_est_float(self):
        assert isinstance(FormeBase().epaisseur, float)

    def test_epaisseur_modifiable(self):
        forme = FormeBase()
        forme.epaisseur = 5.0
        assert forme.epaisseur == 5.0

    def test_epaisseur_personnalisee_a_la_creation(self):
        assert FormeBase(epaisseur=3.5).epaisseur == 3.5


class TestSousClassesHeritentEpaisseur:
    """Chaque sous-classe de FormeBase hérite du champ epaisseur."""

    def test_forme_rect_epaisseur_defaut(self):
        assert FormeRect().epaisseur == 2.0

    def test_forme_cercle_epaisseur_defaut(self):
        assert FormeCercle().epaisseur == 2.0

    def test_forme_ligne_epaisseur_defaut(self):
        assert FormeLigne().epaisseur == 2.0

    def test_forme_polygone_epaisseur_defaut(self):
        assert FormePolygone().epaisseur == 2.0

    def test_forme_lignes_connectees_epaisseur_defaut(self):
        assert FormeLignesConnectees().epaisseur == 2.0

    def test_forme_rect_epaisseur_personnalisee(self):
        assert FormeRect(epaisseur=7.0).epaisseur == 7.0

    def test_forme_cercle_epaisseur_personnalisee(self):
        assert FormeCercle(epaisseur=4.0).epaisseur == 4.0

    def test_independance_instances_epaisseur(self):
        """Modifier l'épaisseur d'une instance ne doit pas affecter les autres."""
        f1 = FormeRect()
        f2 = FormeRect()
        f1.epaisseur = 10.0
        assert f2.epaisseur == 2.0
