"""
Tests unitaires pour src/services/pdf_exporter.py et src/utils/pdf_utils.py.

Stratégie de mocking :
  - reportlab.pdfgen.canvas.Canvas est mocké pour éviter toute écriture disque.
  - reportlab.lib.utils.ImageReader est mocké pour court-circuiter la validation
    PIL qui survient à l'intérieur de _dessiner_plan (le canvas lui-même est mocké
    mais ImageReader est instancié avant d'être passé à drawImage).
  - PIL.Image est mocké pour éviter la lecture de fichiers réels.
  - os.path.isfile est mocké pour contrôler l'existence simulée des fichiers.
  - fit_in_box et image_vers_pdf sont testées sans mock (logique pure).

Depuis le refactor annotations PDF :
  - _annoter_forme et _annoter_bulle injectent des annotations brutes via
    c._addAnnotation(_AnnotationLitterale(contenu)).
  - Les tests sur les formes et les bulles capturent les appels à
    c._addAnnotation() et décodent les bytes pour vérifier le sous-type
    PDF (/Square, /Circle, /PolyLine, /FreeText) et la couleur.
"""

import math
from io import BytesIO
from unittest.mock import MagicMock, patch, call

import pytest

from src.models.planche import Planche
from src.models.bulle import BulleLegende
from src.models.echantillon import Echantillon
from src.models.forme import (
    FormeRect, FormeCercle, FormeLigne,
    FormePolygone, FormeLignesConnectees,
)
from src.utils.constantes import COULEUR_VERTE, COULEUR_ROUGE, COULEUR_ORANGE
from src.utils.pdf_utils import fit_in_box, image_vers_pdf
from src.utils.pdf_utils import (
    PAGE_LARGEUR, PAGE_HAUTEUR, MARGE,
    CARTOUCHE_LARGEUR, CARTOUCHE_HAUTEUR,
    ZONE_PLAN_X, ZONE_PLAN_Y, ZONE_PLAN_LARGEUR, ZONE_PLAN_HAUTEUR,
)


# ---------------------------------------------------------------------------
# Fabrique d'Echantillon minimal (tous les champs obligatoires)
# ---------------------------------------------------------------------------

def _echantillon(
    prelevement="PRV-001",
    description="Enduit",
    resultat="Absence de revêtement",
    localisation="Couloir RDC",
    element_sonde="Mur",
    reference_plan="PL-01",
    couleur=None,
    mention="sa",
    texte_ligne1="PRV-001",
    texte_ligne2="Enduit",
    texte_ligne3="Couloir RDC",
) -> Echantillon:
    return Echantillon(
        prelevement=prelevement,
        description=description,
        resultat=resultat,
        localisation=localisation,
        element_sonde=element_sonde,
        reference_plan=reference_plan,
        couleur=couleur if couleur is not None else COULEUR_VERTE,
        mention=mention,
        texte_ligne1=texte_ligne1,
        texte_ligne2=texte_ligne2,
        texte_ligne3=texte_ligne3,
    )


def _image_pil_mock(largeur=800, hauteur=600):
    """Retourne un mock PIL Image avec size et les méthodes requises."""
    img = MagicMock()
    img.size = (largeur, hauteur)
    img.convert.return_value = img
    img.crop.return_value = img
    # save() n'écrit rien de réel (ImageReader sera mocké séparément)
    img.save.return_value = None
    return img


# ---------------------------------------------------------------------------
# Utilitaire pour extraire les chaînes d'annotations injectées
# ---------------------------------------------------------------------------

def _annotations_injectees(mock_c) -> list[str]:
    """
    Retourne la liste des chaînes PDF brutes passées à c._addAnnotation().

    _addAnnotation reçoit un objet _AnnotationLitterale dont la méthode
    .format(doc) retourne des bytes. On extrait directement les bytes
    via l'attribut interne _contenu (latin-1).
    """
    resultat = []
    for appel in mock_c._addAnnotation.call_args_list:
        obj = appel[0][0]  # premier argument positionnel
        # _AnnotationLitterale stocke les bytes dans _contenu
        if hasattr(obj, "_contenu"):
            resultat.append(obj._contenu.decode("latin-1", errors="replace"))
        elif hasattr(obj, "format"):
            # Fallback : appeler format(None) pour obtenir les bytes
            try:
                resultat.append(obj.format(None).decode("latin-1", errors="replace"))
            except Exception:
                pass
    return resultat


def _appeler_annoter_forme(forme):
    """Appelle _annoter_forme avec un canvas mocké et des paramètres standards."""
    from src.services.pdf_exporter import _annoter_forme

    mock_c = MagicMock()
    _annoter_forme(
        mock_c, forme,
        img_larg=800, img_haut=600,
        zone_x=ZONE_PLAN_X, zone_y=ZONE_PLAN_Y,
        echelle=0.5,
    )
    return mock_c


def _appeler_annoter_bulle(bulle):
    """Appelle _annoter_bulle avec un canvas mocké et des paramètres standards."""
    from src.services.pdf_exporter import _annoter_bulle

    mock_c = MagicMock()
    _annoter_bulle(
        mock_c, bulle,
        img_larg=800, img_haut=600,
        zone_x=ZONE_PLAN_X, zone_y=ZONE_PLAN_Y,
        echelle=0.5,
    )
    return mock_c


# ---------------------------------------------------------------------------
# Tests : fit_in_box (logique pure, sans mock)
# ---------------------------------------------------------------------------

class TestFitInBox:
    """Vérifie le calcul du facteur d'echelle pour l'image dans la zone plan."""

    def test_image_nulle_largeur_retourne_1(self):
        """Si la largeur de l'image vaut 0, retourne 1.0 sans division par zéro."""
        assert fit_in_box(0, 600, 500, 400) == 1.0

    def test_image_nulle_hauteur_retourne_1(self):
        """Si la hauteur de l'image vaut 0, retourne 1.0 sans division par zéro."""
        assert fit_in_box(800, 0, 500, 400) == 1.0

    def test_image_nulle_les_deux_retourne_1(self):
        """Si largeur et hauteur sont toutes les deux nulles, retourne 1.0."""
        assert fit_in_box(0, 0, 500, 400) == 1.0

    def test_contrainte_largeur_active(self):
        """
        Image très large → c'est la contrainte largeur qui s'applique.
        img 1000x100, box 500x400 → echelle_x=0.5, echelle_y=4.0 → min=0.5
        """
        echelle = fit_in_box(1000, 100, 500, 400)
        assert echelle == pytest.approx(0.5)

    def test_contrainte_hauteur_active(self):
        """
        Image très haute → c'est la contrainte hauteur qui s'applique.
        img 100x1000, box 500x400 → echelle_x=5.0, echelle_y=0.4 → min=0.4
        """
        echelle = fit_in_box(100, 1000, 500, 400)
        assert echelle == pytest.approx(0.4)

    def test_image_exactement_taille_boite(self):
        """Image identique à la boîte → facteur 1.0."""
        echelle = fit_in_box(500, 400, 500, 400)
        assert echelle == pytest.approx(1.0)

    def test_image_plus_petite_que_boite(self):
        """
        Image plus petite → facteur > 1.0.
        img 250x200, box 500x400 → facteur 2.0
        """
        echelle = fit_in_box(250, 200, 500, 400)
        assert echelle == pytest.approx(2.0)

    def test_image_carree_boite_non_carree(self):
        """
        Image carrée 400x400, boîte 500x200 → contrainte hauteur → 0.5
        """
        echelle = fit_in_box(400, 400, 500, 200)
        assert echelle == pytest.approx(0.5)

    def test_resultat_positif(self):
        """Le facteur retourné est toujours positif."""
        echelle = fit_in_box(1920, 1080, 785, 520)
        assert echelle > 0

    def test_ratio_largeur_identique_a_box(self):
        """
        Image plus large que haute dans une boîte plus large que haute :
        les deux contraintes sont proportionnelles, facteur = box_larg / img_larg.
        img 800x400, box 400x200 → echelle_x = 0.5, echelle_y = 0.5 → 0.5
        """
        echelle = fit_in_box(800, 400, 400, 200)
        assert echelle == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Tests : image_vers_pdf (logique pure, sans mock)
# ---------------------------------------------------------------------------

class TestImageVersPdf:
    """Vérifie la conversion de coordonnées image vers coordonnées PDF."""

    def test_coin_haut_gauche_image(self):
        """
        Le coin (0, 0) de l'image doit correspondre au coin haut-gauche
        de l'image rendue dans la zone PDF (offset_x, offset_y + img_haut_pdf).
        """
        x_pdf, y_pdf = image_vers_pdf(
            px=0, py=0,
            img_largeur=800, img_hauteur=600,
            zone_x=28.35, zone_y=28.35,
            zone_larg=785.19, zone_haut=518.58,
            echelle=0.5,
        )
        # offset_x = 28.35 + (785.19 - 400) / 2 = 28.35 + 192.595 = 220.945
        # offset_y = 28.35 + (518.58 - 300) / 2 = 28.35 + 109.29  = 137.64
        # x_pdf = 220.945 + 0 * 0.5 = 220.945
        # y_pdf = 137.64 + (600 - 0) * 0.5 = 137.64 + 300 = 437.64
        assert x_pdf == pytest.approx(220.945, abs=0.01)
        assert y_pdf == pytest.approx(437.64, abs=0.01)

    def test_coin_bas_droit_image(self):
        """
        Le coin (largeur, hauteur) de l'image → y_pdf = offset_y (bas de l'image en PDF).
        """
        img_larg, img_haut = 800, 600
        echelle = 0.5
        zone_x, zone_y = 28.35, 28.35
        zone_larg, zone_haut = 785.19, 518.58

        x_pdf, y_pdf = image_vers_pdf(
            px=img_larg, py=img_haut,
            img_largeur=img_larg, img_hauteur=img_haut,
            zone_x=zone_x, zone_y=zone_y,
            zone_larg=zone_larg, zone_haut=zone_haut,
            echelle=echelle,
        )
        offset_y = zone_y + (zone_haut - img_haut * echelle) / 2
        assert y_pdf == pytest.approx(offset_y, abs=0.01)

    def test_axe_y_inverse(self):
        """
        L'axe Y est inversé : un point en haut de l'image (py=0) a une
        coordonnée PDF y_pdf plus grande qu'un point en bas (py=hauteur).
        """
        kwargs = dict(
            img_largeur=800, img_hauteur=600,
            zone_x=0, zone_y=0,
            zone_larg=800, zone_haut=600,
            echelle=1.0,
        )
        _, y_haut = image_vers_pdf(px=0, py=0, **kwargs)
        _, y_bas  = image_vers_pdf(px=0, py=600, **kwargs)
        assert y_haut > y_bas

    def test_point_centre_image(self):
        """
        Le centre de l'image (img_larg/2, img_haut/2) doit tomber au centre
        de la zone PDF quand l'image remplit exactement la zone (echelle = zone/img).
        """
        img_larg, img_haut = 800, 600
        zone_x, zone_y = 0, 0
        zone_larg, zone_haut = 800, 600
        echelle = 1.0

        x_pdf, y_pdf = image_vers_pdf(
            px=img_larg / 2, py=img_haut / 2,
            img_largeur=img_larg, img_hauteur=img_haut,
            zone_x=zone_x, zone_y=zone_y,
            zone_larg=zone_larg, zone_haut=zone_haut,
            echelle=echelle,
        )
        assert x_pdf == pytest.approx(zone_larg / 2, abs=0.01)
        assert y_pdf == pytest.approx(zone_haut / 2, abs=0.01)

    def test_retourne_deux_floats(self):
        """La fonction retourne bien un tuple de deux floats."""
        resultat = image_vers_pdf(
            px=100, py=100,
            img_largeur=800, img_hauteur=600,
            zone_x=0, zone_y=0,
            zone_larg=800, zone_haut=600,
            echelle=1.0,
        )
        assert isinstance(resultat, tuple)
        assert len(resultat) == 2
        assert all(isinstance(v, float) for v in resultat)


# ---------------------------------------------------------------------------
# Tests : exporter_pdf — comportement de haut niveau
# ---------------------------------------------------------------------------

class TestExporterPdf:
    """Teste la fonction publique exporter_pdf."""

    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_liste_vide_ne_cree_pas_de_pdf(self, mock_canvas_cls):
        """
        exporter_pdf avec une liste de planches vide ne doit pas appeler
        c.save() (aucun PDF créé) et ne doit pas lever d'exception.
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c

        exporter_pdf("/tmp/sortie_test.pdf", [])

        mock_c.save.assert_not_called()

    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_planche_sans_plan_chemin_ignoree(self, mock_canvas_cls):
        """
        Une planche dont plan_chemin est None est ignorée silencieusement.
        Si toutes les planches sont ignorées, c.save() n'est pas appelé.
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c

        planche_sans_plan = Planche(numero=1, plan_chemin=None)
        exporter_pdf("/tmp/sortie_test.pdf", [planche_sans_plan])

        mock_c.save.assert_not_called()

    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_plusieurs_planches_sans_plan_chemin_ignorees(self, mock_canvas_cls):
        """
        Plusieurs planches sans plan_chemin → toutes ignorées → c.save() non appelé.
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c

        planches = [Planche(numero=i, plan_chemin=None) for i in range(1, 4)]
        exporter_pdf("/tmp/sortie_test.pdf", planches)

        mock_c.save.assert_not_called()

    @patch("src.services.pdf_exporter.ImageReader")
    @patch("src.services.pdf_exporter.Image")
    @patch("src.services.pdf_exporter.os.path.isfile", return_value=True)
    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_planche_avec_plan_produit_une_page(
        self, mock_canvas_cls, mock_isfile, mock_image_module, mock_image_reader
    ):
        """
        Une planche valide (plan_chemin renseigné, fichier existant) déclenche
        un appel à c.showPage() et à c.save().
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c
        img_mock = _image_pil_mock(800, 600)
        mock_image_module.open.return_value = img_mock
        mock_image_reader.return_value = MagicMock()

        planche = Planche(numero=1, plan_chemin="/chemin/fictif/plan.png")
        exporter_pdf("/tmp/sortie_test.pdf", [planche])

        mock_c.showPage.assert_called_once()
        mock_c.save.assert_called_once()

    @patch("src.services.pdf_exporter.ImageReader")
    @patch("src.services.pdf_exporter.Image")
    @patch("src.services.pdf_exporter.os.path.isfile", return_value=True)
    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_trois_planches_valides_produisent_trois_pages(
        self, mock_canvas_cls, mock_isfile, mock_image_module, mock_image_reader
    ):
        """
        Trois planches valides → trois appels à showPage() → un seul save().
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c
        img_mock = _image_pil_mock(800, 600)
        mock_image_module.open.return_value = img_mock
        mock_image_reader.return_value = MagicMock()

        planches = [
            Planche(numero=i, plan_chemin=f"/chemin/fictif/plan_{i}.png")
            for i in range(1, 4)
        ]
        exporter_pdf("/tmp/sortie_test.pdf", planches)

        assert mock_c.showPage.call_count == 3
        mock_c.save.assert_called_once()

    @patch("src.services.pdf_exporter.ImageReader")
    @patch("src.services.pdf_exporter.Image")
    @patch("src.services.pdf_exporter.os.path.isfile", return_value=True)
    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_planche_valide_et_planche_sans_plan_mixte(
        self, mock_canvas_cls, mock_isfile, mock_image_module, mock_image_reader
    ):
        """
        1 planche valide + 1 planche sans plan → 1 page exportée, pas 2.
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c
        img_mock = _image_pil_mock(800, 600)
        mock_image_module.open.return_value = img_mock
        mock_image_reader.return_value = MagicMock()

        planches = [
            Planche(numero=1, plan_chemin="/chemin/fictif/plan.png"),
            Planche(numero=2, plan_chemin=None),
        ]
        exporter_pdf("/tmp/sortie_test.pdf", planches)

        mock_c.showPage.assert_called_once()
        mock_c.save.assert_called_once()

    @patch("src.services.pdf_exporter.os.path.isfile", return_value=False)
    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_fichier_plan_introuvable_leve_file_not_found(
        self, mock_canvas_cls, mock_isfile
    ):
        """
        Si le fichier plan est absent du disque, FileNotFoundError doit être levée.
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c

        planche = Planche(numero=1, plan_chemin="/chemin/inexistant/plan.png")

        with pytest.raises(FileNotFoundError):
            exporter_pdf("/tmp/sortie_test.pdf", [planche])

    @patch("src.services.pdf_exporter.ImageReader")
    @patch("src.services.pdf_exporter.Image")
    @patch("src.services.pdf_exporter.os.path.isfile", return_value=True)
    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_planche_avec_crop_utilise_crop(
        self, mock_canvas_cls, mock_isfile, mock_image_module, mock_image_reader
    ):
        """
        Une planche avec plan_crop doit appeler img_pil.crop() avec les bonnes
        coordonnées entières (x, y, x+larg, y+haut).
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c
        mock_image_reader.return_value = MagicMock()

        img_mock = _image_pil_mock(800, 600)
        img_croppee = _image_pil_mock(200, 150)
        img_mock.crop.return_value = img_croppee
        mock_image_module.open.return_value = img_mock

        planche = Planche(
            numero=1,
            plan_chemin="/chemin/fictif/plan.png",
            plan_crop=(10.5, 20.5, 200.0, 150.0),
        )
        exporter_pdf("/tmp/sortie_test.pdf", [planche])

        # crop appelé avec (int(x), int(y), int(x+larg), int(y+haut))
        img_mock.crop.assert_called_once_with((10, 20, 210, 170))

    @patch("src.services.pdf_exporter.ImageReader")
    @patch("src.services.pdf_exporter.Image")
    @patch("src.services.pdf_exporter.os.path.isfile", return_value=True)
    @patch("src.services.pdf_exporter.rl_canvas.Canvas")
    def test_planche_sans_crop_n_appelle_pas_crop(
        self, mock_canvas_cls, mock_isfile, mock_image_module, mock_image_reader
    ):
        """
        Une planche sans plan_crop ne doit pas appeler img_pil.crop().
        """
        from src.services.pdf_exporter import exporter_pdf

        mock_c = MagicMock()
        mock_canvas_cls.return_value = mock_c
        mock_image_reader.return_value = MagicMock()

        img_mock = _image_pil_mock(800, 600)
        mock_image_module.open.return_value = img_mock

        planche = Planche(
            numero=1,
            plan_chemin="/chemin/fictif/plan.png",
            plan_crop=None,
        )
        exporter_pdf("/tmp/sortie_test.pdf", [planche])

        img_mock.crop.assert_not_called()


# ---------------------------------------------------------------------------
# Tests : _dessiner_cartouche — texte contient le numéro de planche
# ---------------------------------------------------------------------------

class TestDessinerCartouche:
    """Vérifie le rendu textuel du cartouche PDF."""

    def test_texte_contient_numero_planche(self):
        """
        _dessiner_cartouche doit appeler drawCentredString avec un texte
        contenant le numéro formaté sur 2 chiffres de la planche.
        """
        from src.services.pdf_exporter import _dessiner_cartouche

        mock_c = MagicMock()
        planche = Planche(numero=7)

        _dessiner_cartouche(mock_c, planche)

        appels = mock_c.drawCentredString.call_args_list
        assert len(appels) >= 1, "drawCentredString doit être appelé au moins une fois"

        texte_appele = appels[0][0][2]  # 3e argument positionnel
        assert "07" in texte_appele, (
            f"Le texte du cartouche doit contenir '07', reçu : {texte_appele!r}"
        )

    def test_texte_contient_libelle_planche(self):
        """
        Le texte du cartouche doit contenir 'Planche de rep'.
        """
        from src.services.pdf_exporter import _dessiner_cartouche

        mock_c = MagicMock()
        planche = Planche(numero=1)

        _dessiner_cartouche(mock_c, planche)

        appels = mock_c.drawCentredString.call_args_list
        texte_appele = appels[0][0][2]
        assert "Planche de rep" in texte_appele, (
            f"Le cartouche doit contenir 'Planche de rep...', reçu : {texte_appele!r}"
        )

    def test_numeros_planche_multiples(self):
        """
        Vérifie les numéros 1, 10 et 99 pour s'assurer du formatage à 2 chiffres.
        """
        from src.services.pdf_exporter import _dessiner_cartouche

        for numero, attendu in [(1, "01"), (10, "10"), (99, "99")]:
            mock_c = MagicMock()
            planche = Planche(numero=numero)
            _dessiner_cartouche(mock_c, planche)
            texte = mock_c.drawCentredString.call_args_list[0][0][2]
            assert attendu in texte, (
                f"Planche {numero} → texte attendu '{attendu}', reçu : {texte!r}"
            )

    def test_cartouche_dessine_deux_rectangles(self):
        """
        Le cartouche dessine 2 rect() : fond blanc + bordure noire.
        """
        from src.services.pdf_exporter import _dessiner_cartouche

        mock_c = MagicMock()
        planche = Planche(numero=1)

        _dessiner_cartouche(mock_c, planche)

        assert mock_c.rect.call_count == 2, (
            f"Le cartouche doit dessiner exactement 2 rectangles, "
            f"reçu : {mock_c.rect.call_count}"
        )

    def test_cartouche_positionne_en_haut_a_gauche(self):
        """
        Le premier rect() doit être positionné à (MARGE, PAGE_HAUTEUR - MARGE - CARTOUCHE_HAUTEUR).
        """
        from src.services.pdf_exporter import _dessiner_cartouche

        mock_c = MagicMock()
        planche = Planche(numero=1)

        _dessiner_cartouche(mock_c, planche)

        premier_appel_rect = mock_c.rect.call_args_list[0]
        x_appele, y_appele = premier_appel_rect[0][0], premier_appel_rect[0][1]
        y_attendu = PAGE_HAUTEUR - MARGE - CARTOUCHE_HAUTEUR

        assert x_appele == pytest.approx(MARGE, abs=0.01)
        assert y_appele == pytest.approx(y_attendu, abs=0.01)


# ---------------------------------------------------------------------------
# Tests : constantes pdf_utils — cohérence des valeurs
# ---------------------------------------------------------------------------

class TestConstantesPdfUtils:
    """Vérifie la cohérence des constantes de mise en page."""

    def test_zone_plan_x_egal_marge(self):
        assert ZONE_PLAN_X == pytest.approx(MARGE)

    def test_zone_plan_y_egal_marge(self):
        assert ZONE_PLAN_Y == pytest.approx(MARGE)

    def test_zone_plan_largeur_coherente(self):
        """La zone plan ne doit pas dépasser la largeur de page moins les marges."""
        assert ZONE_PLAN_X + ZONE_PLAN_LARGEUR <= PAGE_LARGEUR - MARGE + 0.01

    def test_zone_plan_hauteur_coherente(self):
        """La zone plan ne doit pas dépasser la hauteur de page moins les marges et le cartouche."""
        assert ZONE_PLAN_Y + ZONE_PLAN_HAUTEUR <= PAGE_HAUTEUR - MARGE + 0.01

    def test_page_paysage_largeur_superieure_a_hauteur(self):
        """En format A4 paysage, la largeur doit être supérieure à la hauteur."""
        assert PAGE_LARGEUR > PAGE_HAUTEUR

    def test_cartouche_dans_zone_superieure(self):
        """Le cartouche doit tenir dans la marge supérieure disponible."""
        espace_au_dessus = PAGE_HAUTEUR - MARGE - ZONE_PLAN_Y - ZONE_PLAN_HAUTEUR
        assert CARTOUCHE_HAUTEUR <= espace_au_dessus + 1  # tolérance 1pt

    def test_marge_strictement_positive(self):
        assert MARGE > 0

    def test_dimensions_zone_plan_strictement_positives(self):
        assert ZONE_PLAN_LARGEUR > 0
        assert ZONE_PLAN_HAUTEUR > 0


# ---------------------------------------------------------------------------
# Tests : _annotation_litterale — infrastructure d'injection PDF
# ---------------------------------------------------------------------------

class TestAnnotationLitterale:
    """
    Vérifie que _AnnotationLitterale produit des bytes corrects via .format(doc).
    """

    def test_format_retourne_bytes(self):
        """format(doc) doit retourner des bytes, peu importe la valeur de doc."""
        from src.services.pdf_exporter import _AnnotationLitterale

        obj = _AnnotationLitterale("<< /Type /Annot /Subtype /Square >>")
        resultat = obj.format(None)
        assert isinstance(resultat, bytes)

    def test_format_contenu_correct(self):
        """Les bytes retournés doivent correspondre au contenu encodé en latin-1."""
        from src.services.pdf_exporter import _AnnotationLitterale

        contenu = "<< /Type /Annot /Subtype /Circle >>"
        obj = _AnnotationLitterale(contenu)
        assert obj.format(None) == contenu.encode("latin-1")

    def test_format_doc_ignoré(self):
        """Le paramètre doc est ignoré : format(None) == format(MagicMock())."""
        from src.services.pdf_exporter import _AnnotationLitterale

        obj = _AnnotationLitterale("<< /Subtype /FreeText >>")
        assert obj.format(None) == obj.format(MagicMock())


# ---------------------------------------------------------------------------
# Tests : _echapper_pdf — échappement des chaînes PDF
# ---------------------------------------------------------------------------

class TestEchapperPdf:
    """Vérifie l'échappement correct des caractères spéciaux dans les chaînes PDF."""

    def test_backslash_echappe(self):
        """Un backslash simple doit être doublé."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("a\\b") == "a\\\\b"

    def test_parenthese_ouvrante_echappee(self):
        """Une parenthèse ouvrante doit être précédée d'un backslash."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("(texte") == "\\(texte"

    def test_parenthese_fermante_echappee(self):
        """Une parenthèse fermante doit être précédée d'un backslash."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("texte)") == "texte\\)"

    def test_retour_chariot_echappe(self):
        """Un \\r dans la chaîne doit être transformé en \\\\r."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("a\rb") == "a\\rb"

    def test_saut_de_ligne_converti_en_retour_chariot(self):
        """Un \\n doit être converti en \\\\r (standard PDF multi-ligne)."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("ligne1\nligne2") == "ligne1\\rligne2"

    def test_texte_sans_caractere_special_inchange(self):
        """Un texte sans caractères spéciaux est retourné tel quel."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("PRV-001 Enduit Couloir RDC") == "PRV-001 Enduit Couloir RDC"

    def test_texte_vide_inchange(self):
        """Une chaîne vide reste vide."""
        from src.services.pdf_exporter import _echapper_pdf
        assert _echapper_pdf("") == ""


# ---------------------------------------------------------------------------
# Tests : _annoter_bulle — annotations PDF pour les bulles de légende
# ---------------------------------------------------------------------------

class TestAnnoterBulle:
    """
    Vérifie que _annoter_bulle injecte les bonnes annotations PDF via _addAnnotation.

    Depuis le refactor, _annoter_bulle :
    - Retourne immédiatement sans rien injecter si bulle.echantillon is None.
    - Injecte exactement 3 annotations si un échantillon est présent :
        1. /PolyLine (call-out coudé)
        2. /Circle  (pastille au point d'ancrage)
        3. /FreeText (rectangle bulle + texte)
    """

    def test_bulle_sans_echantillon_aucune_annotation(self):
        """
        Une bulle sans échantillon ne doit produire aucune annotation PDF.
        La règle métier : pas de texte = pas d'annotation.
        """
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=None,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        mock_c._addAnnotation.assert_not_called()

    def test_bulle_avec_echantillon_injecte_trois_annotations(self):
        """
        Une bulle avec échantillon doit produire exactement 3 annotations :
        /PolyLine (call-out) + /Circle (pastille) + /FreeText (bulle texte).
        """
        ech = _echantillon(
            texte_ligne1="PRV-001",
            texte_ligne2="Enduit",
            texte_ligne3="Couloir RDC",
            mention="sa",
        )
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        assert mock_c._addAnnotation.call_count == 3, (
            f"3 annotations attendues (PolyLine + Circle + FreeText), "
            f"reçu : {mock_c._addAnnotation.call_count}"
        )

    def test_bulle_avec_echantillon_contient_freetext(self):
        """Les annotations produites doivent inclure un /FreeText."""
        ech = _echantillon()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        assert any("/FreeText" in a for a in annotations), (
            f"Une annotation /FreeText attendue. Annotations reçues : {annotations}"
        )

    def test_bulle_avec_echantillon_contient_polyline_callout(self):
        """Les annotations produites doivent inclure un /PolyLine (call-out coudé)."""
        ech = _echantillon()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        assert any("/PolyLine" in a for a in annotations), (
            f"Une annotation /PolyLine attendue. Annotations reçues : {annotations}"
        )

    def test_bulle_avec_echantillon_contient_circle_pastille(self):
        """Les annotations produites doivent inclure un /Circle (pastille ancrage)."""
        ech = _echantillon()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        assert any("/Circle" in a for a in annotations), (
            f"Une annotation /Circle attendue. Annotations reçues : {annotations}"
        )

    def test_bulle_freetext_contient_texte_ligne1(self):
        """
        L'annotation /FreeText doit contenir texte_ligne1 de l'échantillon
        dans le champ /Contents.
        """
        ech = _echantillon(texte_ligne1="PRV-UNIQUE-42")
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        freetext = [a for a in annotations if "/FreeText" in a]
        assert freetext, "Annotation /FreeText introuvable"
        assert "PRV-UNIQUE-42" in freetext[0], (
            f"texte_ligne1 attendu dans /Contents : {freetext[0]!r}"
        )

    def test_bulle_rouge_couleur_dans_annotation(self):
        """
        Une bulle rouge doit produire des annotations contenant la composante
        rouge normalisée (1.0000) dans les chaînes /Color.
        """
        ech = _echantillon(couleur=COULEUR_ROUGE)
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_ROUGE,  # (255, 0, 0)
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        # La couleur normalisée 255/255 = 1.0 doit apparaître dans /Color [1.0000 ...]
        assert any("1.0000 0.0000 0.0000" in a for a in annotations), (
            f"Couleur rouge (1.0000 0.0000 0.0000) attendue dans /Color. "
            f"Annotations : {annotations}"
        )

    def test_bulle_freetext_possede_flag_f4(self):
        """L'annotation /FreeText doit avoir le flag /F 4 (impression)."""
        ech = _echantillon()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        freetext = [a for a in annotations if "/FreeText" in a]
        assert freetext, "Annotation /FreeText introuvable"
        assert "/F 4" in freetext[0], (
            f"/F 4 attendu dans l'annotation /FreeText : {freetext[0]!r}"
        )

    def test_bulle_freetext_possede_centrage_q1(self):
        """L'annotation /FreeText doit avoir /Q 1 (texte centré)."""
        ech = _echantillon()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        freetext = [a for a in annotations if "/FreeText" in a]
        assert freetext, "Annotation /FreeText introuvable"
        assert "/Q 1" in freetext[0], (
            f"/Q 1 attendu dans l'annotation /FreeText : {freetext[0]!r}"
        )

    def test_bulle_freetext_possede_da(self):
        """L'annotation /FreeText doit avoir un champ /DA (apparence par défaut)."""
        ech = _echantillon()
        bulle = BulleLegende(
            ancrage=(100.0, 200.0),
            position=(300.0, 100.0),
            echantillon=ech,
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_bulle(bulle)

        annotations = _annotations_injectees(mock_c)
        freetext = [a for a in annotations if "/FreeText" in a]
        assert freetext, "Annotation /FreeText introuvable"
        assert "/DA" in freetext[0], (
            f"/DA attendu dans l'annotation /FreeText : {freetext[0]!r}"
        )


# ---------------------------------------------------------------------------
# Tests : _annoter_forme — annotations PDF pour les formes colorées
# ---------------------------------------------------------------------------

class TestAnnoterForme:
    """
    Vérifie que _annoter_forme injecte les bonnes annotations PDF via _addAnnotation.

    Depuis le refactor, _annoter_forme utilise uniquement c._addAnnotation() :
      FormeRect             → annotation /Square
      FormeCercle           → annotation /Circle
      FormeLigne            → annotation /PolyLine
      FormePolygone         → annotation /PolyLine (fermé : premier point répété)
      FormeLignesConnectees → annotation /PolyLine (ouvert)
    """

    def test_forme_rect_injecte_annotation_square(self):
        """FormeRect avec 2 points → annotation /Square injectée."""
        forme = FormeRect(points=[(100, 100), (300, 250)], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)

        assert mock_c._addAnnotation.call_count == 1
        annotations = _annotations_injectees(mock_c)
        assert "/Square" in annotations[0], (
            f"Annotation /Square attendue, reçu : {annotations[0]!r}"
        )

    def test_forme_rect_annotation_possede_rect(self):
        """L'annotation /Square doit contenir un champ /Rect."""
        forme = FormeRect(points=[(100, 100), (300, 250)], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert "/Rect" in annotations[0], (
            f"/Rect attendu dans l'annotation /Square : {annotations[0]!r}"
        )

    def test_forme_rect_annotation_possede_color(self):
        """L'annotation /Square doit contenir un champ /Color."""
        forme = FormeRect(points=[(100, 100), (300, 250)], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert "/Color" in annotations[0], (
            f"/Color attendu dans l'annotation /Square : {annotations[0]!r}"
        )

    def test_forme_rect_annotation_possede_flag_f4(self):
        """L'annotation /Square doit avoir /F 4 (impression)."""
        forme = FormeRect(points=[(100, 100), (300, 250)], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert "/F 4" in annotations[0], (
            f"/F 4 attendu dans l'annotation /Square : {annotations[0]!r}"
        )

    def test_forme_rect_sans_points_aucune_annotation(self):
        """FormeRect avec moins de 2 points doit être ignorée silencieusement."""
        forme = FormeRect(points=[(100, 100)], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)
        mock_c._addAnnotation.assert_not_called()

    def test_forme_rect_liste_vide_aucune_annotation(self):
        """FormeRect sans aucun point doit être ignorée silencieusement."""
        forme = FormeRect(points=[], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)
        mock_c._addAnnotation.assert_not_called()

    def test_forme_cercle_injecte_annotation_circle(self):
        """FormeCercle avec 2 points → annotation /Circle injectée."""
        forme = FormeCercle(points=[(200, 200), (250, 200)], couleur_rgb=COULEUR_ROUGE)
        mock_c = _appeler_annoter_forme(forme)

        assert mock_c._addAnnotation.call_count == 1
        annotations = _annotations_injectees(mock_c)
        assert "/Circle" in annotations[0], (
            f"Annotation /Circle attendue, reçu : {annotations[0]!r}"
        )

    def test_forme_cercle_annotation_possede_rect(self):
        """L'annotation /Circle doit contenir /Rect (carré englobant)."""
        forme = FormeCercle(points=[(200, 200), (250, 200)], couleur_rgb=COULEUR_ROUGE)
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert "/Rect" in annotations[0], (
            f"/Rect attendu dans l'annotation /Circle : {annotations[0]!r}"
        )

    def test_forme_cercle_sans_points_aucune_annotation(self):
        """FormeCercle sans points → ignorée, aucune annotation."""
        forme = FormeCercle(points=[], couleur_rgb=COULEUR_ROUGE)
        mock_c = _appeler_annoter_forme(forme)
        mock_c._addAnnotation.assert_not_called()

    def test_forme_ligne_injecte_annotation_polyline(self):
        """FormeLigne avec 2 points → annotation /PolyLine injectée."""
        forme = FormeLigne(points=[(50, 50), (400, 300)], couleur_rgb=COULEUR_ORANGE)
        mock_c = _appeler_annoter_forme(forme)

        assert mock_c._addAnnotation.call_count == 1
        annotations = _annotations_injectees(mock_c)
        assert "/PolyLine" in annotations[0], (
            f"Annotation /PolyLine attendue, reçu : {annotations[0]!r}"
        )

    def test_forme_ligne_annotation_possede_vertices(self):
        """L'annotation /PolyLine pour une FormeLigne doit contenir /Vertices."""
        forme = FormeLigne(points=[(50, 50), (400, 300)], couleur_rgb=COULEUR_ORANGE)
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert "/Vertices" in annotations[0], (
            f"/Vertices attendu dans l'annotation /PolyLine : {annotations[0]!r}"
        )

    def test_forme_ligne_sans_points_aucune_annotation(self):
        """FormeLigne avec 1 seul point → ignorée, aucune annotation."""
        forme = FormeLigne(points=[(50, 50)], couleur_rgb=COULEUR_ORANGE)
        mock_c = _appeler_annoter_forme(forme)
        mock_c._addAnnotation.assert_not_called()

    def test_forme_polygone_injecte_annotation_polyline(self):
        """FormePolygone avec 3 points → annotation /PolyLine injectée (fermée)."""
        forme = FormePolygone(
            points=[(100, 100), (200, 50), (300, 150)],
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_forme(forme)

        assert mock_c._addAnnotation.call_count == 1
        annotations = _annotations_injectees(mock_c)
        assert "/PolyLine" in annotations[0], (
            f"Annotation /PolyLine attendue pour FormePolygone : {annotations[0]!r}"
        )

    def test_forme_polygone_vertices_ferme_premier_point_repete(self):
        """
        L'annotation /PolyLine pour un polygone doit répéter le premier
        sommet en dernier pour fermer la forme.
        On utilise 3 points et on vérifie que les vertices contiennent 4 paires.
        """
        forme = FormePolygone(
            points=[(0, 0), (100, 0), (50, 100)],
            couleur_rgb=COULEUR_VERTE,
        )
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert annotations, "Aucune annotation produite"
        # /Vertices [x1 y1 x2 y2 x3 y3 x4 y4] → 4 paires pour 3 points + fermeture
        # On cherche /Vertices [ ... ] dans la chaîne
        import re
        m = re.search(r"/Vertices \[([^\]]+)\]", annotations[0])
        assert m, f"/Vertices introuvable dans {annotations[0]!r}"
        valeurs = m.group(1).strip().split()
        # 4 paires de coordonnées = 8 valeurs
        assert len(valeurs) == 8, (
            f"8 valeurs attendues dans /Vertices (4 paires), reçu {len(valeurs)} : {valeurs}"
        )

    def test_forme_lignes_connectees_injecte_annotation_polyline(self):
        """FormeLignesConnectees (polyligne ouverte) → annotation /PolyLine."""
        forme = FormeLignesConnectees(
            points=[(50, 50), (150, 100), (250, 200)],
            couleur_rgb=COULEUR_ROUGE,
        )
        mock_c = _appeler_annoter_forme(forme)

        assert mock_c._addAnnotation.call_count == 1
        annotations = _annotations_injectees(mock_c)
        assert "/PolyLine" in annotations[0], (
            f"Annotation /PolyLine attendue pour FormeLignesConnectees : {annotations[0]!r}"
        )

    def test_forme_lignes_connectees_sans_points_aucune_annotation(self):
        """FormeLignesConnectees avec 1 seul point → ignorée, aucune annotation."""
        forme = FormeLignesConnectees(
            points=[(50, 50)],
            couleur_rgb=COULEUR_ROUGE,
        )
        mock_c = _appeler_annoter_forme(forme)
        mock_c._addAnnotation.assert_not_called()

    def test_forme_couleur_orange_dans_annotation(self):
        """
        La couleur orange (255, 128, 0) doit être correctement normalisée
        et présente dans la chaîne /Color de l'annotation.
        255/255 = 1.0000, 128/255 ≈ 0.5020, 0/255 = 0.0000.
        """
        forme = FormeRect(
            points=[(0, 0), (100, 100)],
            couleur_rgb=COULEUR_ORANGE,  # (255, 128, 0)
        )
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert annotations, "Aucune annotation produite"
        # Valeurs attendues : 1.0000, 0.5020, 0.0000
        assert "1.0000" in annotations[0], (
            f"Composante rouge normalisée (1.0000) attendue : {annotations[0]!r}"
        )
        assert "0.5020" in annotations[0], (
            f"Composante verte normalisée (~0.5020) attendue : {annotations[0]!r}"
        )

    def test_forme_pleine_opacite_1(self):
        """
        Une forme avec alpha >= 200 (pleine) doit avoir /CA 1.00 dans l'annotation.
        """
        forme = FormeRect(
            points=[(0, 0), (100, 100)],
            couleur_rgb=COULEUR_VERTE,
            alpha=255,
        )
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert annotations, "Aucune annotation produite"
        assert "/CA 1.00" in annotations[0], (
            f"/CA 1.00 attendu pour une forme pleine : {annotations[0]!r}"
        )

    def test_forme_semi_transparente_opacite_0_5(self):
        """
        Une forme avec alpha < 200 (semi-transparente) doit avoir /CA 0.50
        dans l'annotation.
        """
        forme = FormeRect(
            points=[(0, 0), (100, 100)],
            couleur_rgb=COULEUR_VERTE,
            alpha=128,
        )
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert annotations, "Aucune annotation produite"
        assert "/CA 0.50" in annotations[0], (
            f"/CA 0.50 attendu pour une forme semi-transparente : {annotations[0]!r}"
        )

    def test_annotation_square_possede_bs(self):
        """/Square doit avoir un dictionnaire /BS pour la largeur de bordure."""
        forme = FormeRect(points=[(0, 0), (100, 100)], couleur_rgb=COULEUR_VERTE)
        mock_c = _appeler_annoter_forme(forme)

        annotations = _annotations_injectees(mock_c)
        assert "/BS" in annotations[0], (
            f"/BS attendu dans l'annotation /Square : {annotations[0]!r}"
        )
