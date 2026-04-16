"""
Sérialisation / désérialisation d'un chantier de légendage amiante.

Format : un seul fichier JSON par chantier.
Fonctions publiques :
  - sauvegarder(planches, chemin) : écrit le fichier JSON
  - charger(chemin) → (planches, chemins_manquants) : lit le fichier JSON

Les types de formes sont discriminés via le champ "type" dans le JSON.
Les chemins de plans qui n'existent plus sur disque sont signalés dans
la liste `chemins_manquants` retournée par `charger`.
"""

import json
import os

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

# Version du format de fichier — à incrémenter si le schéma change
_VERSION = "1.0"

# Correspondance nom → classe pour la désérialisation des formes
_TYPES_FORMES = {
    "FormeRect":             FormeRect,
    "FormeCercle":           FormeCercle,
    "FormeLigne":            FormeLigne,
    "FormePolygone":         FormePolygone,
    "FormeLignesConnectees": FormeLignesConnectees,
}


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------

def sauvegarder(planches: list[Planche], chemin: str) -> None:
    """
    Sérialise la liste de planches dans un fichier JSON.

    Paramètres
    ----------
    planches : list[Planche]
        Planches du chantier à sauvegarder.
    chemin : str
        Chemin absolu du fichier de destination (ex. C:\\chantier.json).
    """
    donnees = {
        "version": _VERSION,
        "planches": [_planche_vers_dict(p) for p in planches],
    }
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)


def charger(chemin: str) -> tuple[list[Planche], list[str]]:
    """
    Désérialise un fichier JSON de chantier.

    Paramètres
    ----------
    chemin : str
        Chemin absolu du fichier JSON à ouvrir.

    Retourne
    --------
    (planches, chemins_manquants)
      - planches          : liste des Planche reconstituées
      - chemins_manquants : liste des plan_chemin non trouvés sur disque
    """
    with open(chemin, "r", encoding="utf-8") as f:
        donnees = json.load(f)

    planches = [_dict_vers_planche(d) for d in donnees.get("planches", [])]

    chemins_manquants = [
        p.plan_chemin
        for p in planches
        if p.plan_chemin is not None and not os.path.isfile(p.plan_chemin)
    ]

    return planches, chemins_manquants


# ---------------------------------------------------------------------------
# Sérialisation (objet → dict)
# ---------------------------------------------------------------------------

def _planche_vers_dict(p: Planche) -> dict:
    return {
        "id":             p.id,
        "numero":         p.numero,
        "reference_plan": p.reference_plan,
        "plan_chemin":    p.plan_chemin,
        "zoom_factor":    p.zoom_factor,
        "offset":         list(p.offset),
        "zone_plan":      list(p.zone_plan) if p.zone_plan is not None else None,
        "formes":         [_forme_vers_dict(f) for f in p.formes],
        "bulles":         [_bulle_vers_dict(b) for b in p.bulles],
    }


def _forme_vers_dict(f) -> dict:
    return {
        "type":       type(f).__name__,
        "id":         f.id,
        "couleur_rgb": list(f.couleur_rgb),
        "alpha":      f.alpha,
        "points":     [list(pt) for pt in f.points],
        "epaisseur":  f.epaisseur,
    }


def _bulle_vers_dict(b: BulleLegende) -> dict:
    return {
        "id":           b.id,
        "ancrage":      list(b.ancrage),
        "position":     list(b.position),
        "couleur_rgb":  list(b.couleur_rgb),
        "largeur":      b.largeur,
        "pied_longueur": b.pied_longueur,
        "echantillon":  _echantillon_vers_dict(b.echantillon),
    }


def _echantillon_vers_dict(e: Echantillon | None) -> dict | None:
    if e is None:
        return None
    return {
        "prelevement":   e.prelevement,
        "description":   e.description,
        "resultat":      e.resultat,
        "localisation":  e.localisation,
        "element_sonde": e.element_sonde,
        "reference_plan": e.reference_plan,
        "couleur":       list(e.couleur),
        "mention":       e.mention,
        "texte_ligne1":  e.texte_ligne1,
        "texte_ligne2":  e.texte_ligne2,
        "texte_ligne3":  e.texte_ligne3,
    }


# ---------------------------------------------------------------------------
# Désérialisation (dict → objet)
# ---------------------------------------------------------------------------

def _dict_vers_planche(d: dict) -> Planche:
    zone_plan = d.get("zone_plan")
    return Planche(
        id=d["id"],
        numero=d["numero"],
        reference_plan=d["reference_plan"],
        plan_chemin=d.get("plan_chemin"),
        zoom_factor=d.get("zoom_factor", 1.0),
        offset=tuple(d.get("offset", [0.0, 0.0])),
        zone_plan=tuple(zone_plan) if zone_plan is not None else None,
        formes=[_dict_vers_forme(f) for f in d.get("formes", [])],
        bulles=[_dict_vers_bulle(b) for b in d.get("bulles", [])],
    )


def _dict_vers_forme(d: dict):
    type_nom = d.get("type", "")
    classe = _TYPES_FORMES.get(type_nom)
    if classe is None:
        raise ValueError(f"Type de forme inconnu : {type_nom!r}")
    return classe(
        id=d["id"],
        couleur_rgb=tuple(d["couleur_rgb"]),
        alpha=d["alpha"],
        points=[tuple(pt) for pt in d["points"]],
        epaisseur=d.get("epaisseur", 2.0),
    )


def _dict_vers_bulle(d: dict) -> BulleLegende:
    return BulleLegende(
        id=d["id"],
        ancrage=tuple(d["ancrage"]),
        position=tuple(d["position"]),
        couleur_rgb=tuple(d["couleur_rgb"]),
        largeur=d.get("largeur", 172.8),
        pied_longueur=d.get("pied_longueur", 20.0),
        echantillon=_dict_vers_echantillon(d.get("echantillon")),
    )


def _dict_vers_echantillon(d: dict | None) -> Echantillon | None:
    if d is None:
        return None
    return Echantillon(
        prelevement=d["prelevement"],
        description=d["description"],
        resultat=d["resultat"],
        localisation=d["localisation"],
        element_sonde=d["element_sonde"],
        reference_plan=d["reference_plan"],
        couleur=tuple(d["couleur"]),
        mention=d["mention"],
        texte_ligne1=d["texte_ligne1"],
        texte_ligne2=d["texte_ligne2"],
        texte_ligne3=d["texte_ligne3"],
    )
