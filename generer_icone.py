"""
Génère l'icône FibroMap.ico en plusieurs tailles.

Représente un plan de bâtiment (lignes blanches sur fond bleu marine)
avec un marqueur rond tricolore (vert/orange/rouge) dans le coin bas-droit.

Usage : python generer_icone.py
Résultat : fibromap.ico (à la racine du projet)
"""

from PIL import Image, ImageDraw


def _dessiner_icone(taille: int) -> Image.Image:
    """Dessine l'icône à la taille demandée."""
    img = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = taille  # alias court

    # ── Fond arrondi bleu marine ─────────────────────────────────────────
    rayon = s // 6
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=rayon,
                        fill=(30, 58, 95))          # bleu marine

    # ── Plan de bâtiment (lignes blanches) ──────────────────────────────
    # Marges du plan dans l'icône
    mx = int(s * 0.14)   # marge horizontale
    my = int(s * 0.14)   # marge verticale
    ep = max(1, s // 32) # épaisseur des traits

    blanc = (255, 255, 255, 220)
    gris  = (180, 200, 230, 160)

    # Contour extérieur du bâtiment (rectangle principal)
    bx1, by1 = mx, my
    bx2, by2 = int(s * 0.72), int(s * 0.76)
    d.rectangle([bx1, by1, bx2, by2], outline=blanc, width=ep)

    # Mur horizontal intérieur (séparation haut/bas)
    my_sep = by1 + (by2 - by1) // 2
    d.line([bx1, my_sep, bx2, my_sep], fill=gris, width=ep)

    # Mur vertical intérieur (séparation gauche/droite, pièce du bas)
    mx_sep = bx1 + (bx2 - bx1) * 2 // 5
    d.line([mx_sep, my_sep, mx_sep, by2], fill=gris, width=ep)

    # Ouverture de porte (bas-gauche)
    porte_w = (mx_sep - bx1) // 3
    px = bx1 + (mx_sep - bx1 - porte_w) // 2
    d.line([px, by2, px + porte_w, by2], fill=(30, 58, 95), width=ep + 1)

    # ── Marqueur (pastille tricolore) ────────────────────────────────────
    # Centré en bas-droit, légèrement en dehors du plan
    r = int(s * 0.20)           # rayon extérieur
    cx = int(s * 0.76)          # centre X
    cy = int(s * 0.76)          # centre Y

    # Ombre portée subtile
    d.ellipse([cx - r + 2, cy - r + 2, cx + r + 2, cy + r + 2],
              fill=(0, 0, 0, 80))

    # Fond blanc du marqueur
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              fill=(255, 255, 255))

    # Trois segments colorés (vert, orange, rouge) — palette métier amiante
    r2 = int(r * 0.72)
    couleurs = [
        (18,  169,  30),   # vert  — absence
        (255, 128,   0),   # orange — non prélevé
        (255,   0,   0),   # rouge  — présence
    ]
    angles = [(-30, 90), (90, 210), (210, 330)]
    for (start, end), coul in zip(angles, couleurs):
        d.pieslice([cx - r2, cy - r2, cx + r2, cy + r2],
                   start=start, end=end, fill=coul)

    # Cercle central blanc (effet "donut")
    r3 = int(r * 0.38)
    d.ellipse([cx - r3, cy - r3, cx + r3, cy + r3],
              fill=(255, 255, 255))

    # Contour du marqueur
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              outline=(255, 255, 255), width=max(1, ep))

    return img


def generer_ico(chemin_sortie: str = "fibromap.ico") -> None:
    """Génère le fichier .ico multi-résolution."""
    tailles = [16, 24, 32, 48, 64, 128, 256]
    images = [_dessiner_icone(t) for t in tailles]

    # La première image est l'entrée principale, les autres sont les variantes
    images[0].save(
        chemin_sortie,
        format="ICO",
        sizes=[(t, t) for t in tailles],
        append_images=images[1:],
    )
    print(f"Icône générée : {chemin_sortie} ({len(tailles)} tailles : {tailles})")


if __name__ == "__main__":
    generer_ico("fibromap.ico")
