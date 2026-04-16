"""
Tests unitaires pour src/services/sauvegarde.py.

Couvre la sérialisation JSON round-trip (sauvegarde → charger) pour :
  - Planches vides et avec contenu
  - Tous les types de formes
  - Bulles avec et sans échantillon
  - Détection des chemins de plans manquants sur disque
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.bulle import BulleLegende
from src.models.echantillon import Echantillon
from src.models.forme import (
    FormeCercle,
    FormeLigne,
    FormeLignesConnectees,
    FormePolygone,
    FormeRect,
)
from src.models.planche import Planche
from src.services.sauvegarde import charger, sauvegarder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sauvegarder_et_charger(planches: list[Planche]) -> tuple[list[Planche], list[str]]:
    """Écrit les planches dans un fichier temporaire, puis les relit."""
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    ) as f:
        chemin = f.name
    try:
        sauvegarder(planches, chemin)
        return charger(chemin)
    finally:
        os.unlink(chemin)


def _echantillon_minimal() -> Echantillon:
    return Echantillon(
        prelevement="PRV-001",
        description="Enduit",
        resultat="Présence amiante",
        localisation="Couloir RDC",
        element_sonde="Mur",
        reference_plan="Planche 01",
        couleur=(255, 0, 0),
        mention="a",
        texte_ligne1="PRV-001",
        texte_ligne2="Enduit",
        texte_ligne3="Couloir RDC",
    )


# ---------------------------------------------------------------------------
# Tests round-trip — structure générale
# ---------------------------------------------------------------------------

class TestRoundTripPlanche:
    """Vérifie que les champs de Planche survivent au round-trip JSON."""

    def test_round_trip_planche_vide(self):
        """Une planche sans formes ni bulles est reconstituée identique."""
        planche = Planche(
            numero=1,
            reference_plan="Planche de repérage 01",
        )
        chargees, _ = _sauvegarder_et_charger([planche])

        assert len(chargees) == 1
        p = chargees[0]
        assert p.id == planche.id
        assert p.numero == 1
        assert p.reference_plan == "Planche de repérage 01"
        assert p.plan_chemin is None
        assert p.formes == []
        assert p.bulles == []

    def test_round_trip_zoom_et_offset(self):
        """zoom_factor et offset sont préservés."""
        planche = Planche(numero=1, zoom_factor=2.5, offset=(30.0, 45.0))
        chargees, _ = _sauvegarder_et_charger([planche])

        p = chargees[0]
        assert p.zoom_factor == pytest.approx(2.5)
        assert p.offset == pytest.approx((30.0, 45.0))

    def test_round_trip_zone_plan(self):
        """zone_plan (tuple) est préservée, y compris None."""
        planche_avec = Planche(numero=1, zone_plan=(10.0, 20.0, 500.0, 400.0))
        planche_sans = Planche(numero=2, zone_plan=None)

        chargees, _ = _sauvegarder_et_charger([planche_avec, planche_sans])

        assert chargees[0].zone_plan == pytest.approx((10.0, 20.0, 500.0, 400.0))
        assert chargees[1].zone_plan is None

    def test_plan_chemin_none(self):
        """plan_chemin=None est sérialisé en null et reste None."""
        planche = Planche(numero=1, plan_chemin=None)
        chargees, _ = _sauvegarder_et_charger([planche])
        assert chargees[0].plan_chemin is None

    def test_plusieurs_planches_ordre_conserve(self):
        """L'ordre de la liste de planches est conservé après le round-trip."""
        planches = [
            Planche(numero=1, reference_plan="A"),
            Planche(numero=2, reference_plan="B"),
            Planche(numero=3, reference_plan="C"),
        ]
        chargees, _ = _sauvegarder_et_charger(planches)

        assert len(chargees) == 3
        assert [p.reference_plan for p in chargees] == ["A", "B", "C"]
        assert [p.numero for p in chargees] == [1, 2, 3]

    def test_version_dans_fichier(self):
        """Le fichier JSON contient la clé 'version'."""
        planche = Planche(numero=1)
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            chemin = f.name
        try:
            sauvegarder([planche], chemin)
            with open(chemin, encoding="utf-8") as f:
                donnees = json.load(f)
            assert "version" in donnees
            assert donnees["version"] == "1.0"
        finally:
            os.unlink(chemin)


# ---------------------------------------------------------------------------
# Tests round-trip — formes
# ---------------------------------------------------------------------------

class TestRoundTripFormes:
    """Vérifie que les types et champs de formes survivent au round-trip."""

    def test_round_trip_forme_rect(self):
        """FormeRect : type et champs conservés."""
        forme = FormeRect(
            points=[(10.0, 20.0), (100.0, 150.0)],
            couleur_rgb=(18, 169, 30),
            alpha=255,
            epaisseur=3.0,
        )
        planche = Planche(numero=1, formes=[forme])
        chargees, _ = _sauvegarder_et_charger([planche])

        f = chargees[0].formes[0]
        assert type(f).__name__ == "FormeRect"
        assert f.id == forme.id
        assert f.couleur_rgb == (18, 169, 30)
        assert f.alpha == 255
        assert f.epaisseur == pytest.approx(3.0)
        assert f.points == [(10.0, 20.0), (100.0, 150.0)]

    def test_round_trip_toutes_formes(self):
        """Les 5 types de formes sont reconstitués avec le bon type."""
        formes = [
            FormeRect(points=[(0, 0), (10, 10)]),
            FormeCercle(points=[(50, 50), (80, 80)]),
            FormeLigne(points=[(0, 0), (100, 100)]),
            FormePolygone(points=[(0, 0), (50, 0), (50, 50)]),
            FormeLignesConnectees(points=[(0, 0), (30, 0), (30, 30)]),
        ]
        planche = Planche(numero=1, formes=formes)
        chargees, _ = _sauvegarder_et_charger([planche])

        types_obtenus = [type(f).__name__ for f in chargees[0].formes]
        assert types_obtenus == [
            "FormeRect",
            "FormeCercle",
            "FormeLigne",
            "FormePolygone",
            "FormeLignesConnectees",
        ]

    def test_round_trip_forme_alpha_semi_transparent(self):
        """alpha=128 (semi-transparent) est préservé."""
        forme = FormeRect(points=[(0, 0), (10, 10)], alpha=128)
        planche = Planche(numero=1, formes=[forme])
        chargees, _ = _sauvegarder_et_charger([planche])
        assert chargees[0].formes[0].alpha == 128

    def test_round_trip_forme_points_multiples(self):
        """Les points d'un polygone (N points) sont tous préservés."""
        pts = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (50.0, 150.0), (0.0, 100.0)]
        forme = FormePolygone(points=pts)
        planche = Planche(numero=1, formes=[forme])
        chargees, _ = _sauvegarder_et_charger([planche])
        assert chargees[0].formes[0].points == pts


# ---------------------------------------------------------------------------
# Tests round-trip — bulles
# ---------------------------------------------------------------------------

class TestRoundTripBulles:
    """Vérifie que les bulles et leurs échantillons survivent au round-trip."""

    def test_round_trip_bulle_sans_echantillon(self):
        """Une bulle sans échantillon est reconstituée avec echantillon=None."""
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=None,
            couleur_rgb=(18, 169, 30),
        )
        planche = Planche(numero=1, bulles=[bulle])
        chargees, _ = _sauvegarder_et_charger([planche])

        b = chargees[0].bulles[0]
        assert b.echantillon is None
        assert b.ancrage == pytest.approx((100.0, 200.0))
        assert b.position == pytest.approx((300.0, 100.0))

    def test_round_trip_bulle_avec_echantillon(self):
        """Tous les champs de l'échantillon sont préservés."""
        ech = _echantillon_minimal()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=(255, 0, 0),
        )
        planche = Planche(numero=1, bulles=[bulle])
        chargees, _ = _sauvegarder_et_charger([planche])

        e = chargees[0].bulles[0].echantillon
        assert e is not None
        assert e.prelevement == "PRV-001"
        assert e.description == "Enduit"
        assert e.resultat == "Présence amiante"
        assert e.localisation == "Couloir RDC"
        assert e.element_sonde == "Mur"
        assert e.couleur == (255, 0, 0)
        assert e.mention == "a"
        assert e.texte_ligne1 == "PRV-001"
        assert e.texte_ligne2 == "Enduit"
        assert e.texte_ligne3 == "Couloir RDC"

    def test_round_trip_bulle_pied_longueur(self):
        """pied_longueur est préservé."""
        bulle = BulleLegende(
            ancrage=(0.0, 0.0),
            position=(0.0, 0.0),
            pied_longueur=45.5,
        )
        planche = Planche(numero=1, bulles=[bulle])
        chargees, _ = _sauvegarder_et_charger([planche])
        assert chargees[0].bulles[0].pied_longueur == pytest.approx(45.5)


# ---------------------------------------------------------------------------
# Tests — détection des chemins manquants
# ---------------------------------------------------------------------------

class TestCheminsManquants:
    """Vérifie la détection des plans introuvables sur disque."""

    def test_chemin_inexistant_dans_manquants(self):
        """Un plan_chemin qui n'existe pas sur disque apparaît dans manquants."""
        planche = Planche(numero=1, plan_chemin="C:\\inexistant\\plan.jpg")
        _, manquants = _sauvegarder_et_charger([planche])
        assert "C:\\inexistant\\plan.jpg" in manquants

    def test_chemin_existant_pas_dans_manquants(self):
        """Un plan_chemin qui existe sur disque n'apparaît pas dans manquants."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img:
            chemin_img = img.name
        try:
            planche = Planche(numero=1, plan_chemin=chemin_img)
            _, manquants = _sauvegarder_et_charger([planche])
            assert chemin_img not in manquants
        finally:
            os.unlink(chemin_img)

    def test_chemin_none_pas_dans_manquants(self):
        """plan_chemin=None ne génère aucun chemin manquant."""
        planche = Planche(numero=1, plan_chemin=None)
        _, manquants = _sauvegarder_et_charger([planche])
        assert manquants == []

    def test_plusieurs_planches_manquants_corrects(self):
        """Seuls les plans introuvables sont listés dans manquants."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img:
            chemin_existant = img.name
        try:
            planches = [
                Planche(numero=1, plan_chemin=chemin_existant),
                Planche(numero=2, plan_chemin="C:\\introuvable.jpg"),
                Planche(numero=3, plan_chemin=None),
            ]
            _, manquants = _sauvegarder_et_charger(planches)
            assert manquants == ["C:\\introuvable.jpg"]
        finally:
            os.unlink(chemin_existant)
