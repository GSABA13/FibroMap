"""
Module utilitaire pour la conversion de fichiers PDF en QPixmap.

Ce module fournit la fonction `pdf_vers_pixmap` qui transforme la première
page d'un fichier PDF en un objet QPixmap utilisable dans PyQt6.
Il s'appuie sur la bibliothèque pdf2image (Poppler) pour le rendu du PDF
et sur un buffer mémoire PNG pour la conversion vers Qt.
"""

import io
import logging
import os
import sys

from pdf2image import convert_from_path
from PyQt6.QtGui import QPixmap

from src.utils.constantes import DPI_CONVERSION_PDF


def _chemin_poppler() -> str | None:
    """
    Retourne le chemin vers les binaires Poppler selon le contexte d'exécution.

    - En mode PyInstaller (.exe) : extrait dans sys._MEIPASS/poppler/bin
    - En mode développement     : poppler/poppler-25.12.0/Library/bin/ à la racine
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "poppler", "bin")
    racine = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    chemin = os.path.join(racine, "poppler", "poppler-25.12.0", "Library", "bin")
    return chemin if os.path.isdir(chemin) else None

# Journalisation propre au module
logger = logging.getLogger(__name__)


def pdf_vers_pixmap(chemin_pdf: str, dpi: int = DPI_CONVERSION_PDF) -> QPixmap:
    """
    Convertit la première page d'un fichier PDF en QPixmap.

    Paramètres
    ----------
    chemin_pdf : str
        Chemin absolu ou relatif vers le fichier PDF à convertir.
    dpi : int, optional
        Résolution de rendu en points par pouce (défaut : DPI_CONVERSION_PDF).

    Retourne
    --------
    QPixmap
        Le pixmap correspondant à la première page du PDF,
        ou un QPixmap vide en cas d'erreur.
    """
    try:
        # Rendu du PDF — on ne conserve que la première page
        pages = convert_from_path(chemin_pdf, dpi=dpi, poppler_path=_chemin_poppler())
        if not pages:
            logger.warning("Le PDF '%s' ne contient aucune page.", chemin_pdf)
            return QPixmap()

        premiere_page = pages[0]

        # Conversion de l'image PIL en QPixmap via un buffer PNG en mémoire
        buffer = io.BytesIO()
        premiere_page.save(buffer, format="PNG")
        buffer.seek(0)

        pixmap = QPixmap()
        pixmap.loadFromData(buffer.read(), "PNG")
        if pixmap.isNull():
            logger.warning(
                "Le pixmap est vide après conversion du PDF '%s'.", chemin_pdf
            )
        return pixmap

    except FileNotFoundError:
        logger.error("Fichier PDF introuvable : '%s'.", chemin_pdf)
        return QPixmap()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Erreur lors de la conversion du PDF '%s' : %s", chemin_pdf, exc
        )
        return QPixmap()
