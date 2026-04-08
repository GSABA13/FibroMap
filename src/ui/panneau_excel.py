"""
Panneau latéral droit : gestion et affichage des échantillons Excel.

Ce module définit la classe `PanneauExcel` qui permettra à l'utilisateur
d'ouvrir un fichier Excel et d'afficher la liste des échantillons qu'il
contient. La logique de lecture du fichier est déléguée aux services.
"""

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.constantes import MARGE_PANNEAU


class PanneauExcel(QWidget):
    """
    Panneau de gestion des échantillons issus d'un fichier Excel.

    Signaux
    -------
    ouvrir_excel_demande : pyqtSignal()
        Émis lorsque l'utilisateur clique sur le bouton "Ouvrir Excel".
        La fenêtre principale se charge d'ouvrir la boîte de dialogue.
    """

    ouvrir_excel_demande = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # --- Mise en page verticale ----------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU)
        layout.setSpacing(MARGE_PANNEAU)

        # Bouton d'ouverture du fichier Excel
        self._btn_ouvrir = QPushButton("Ouvrir Excel")
        self._btn_ouvrir.setToolTip("Ouvrir un fichier Excel contenant les échantillons")
        layout.addWidget(self._btn_ouvrir)

        # Liste scrollable des échantillons (vide pour l'instant)
        self._liste = QListWidget()
        self._liste.setToolTip("Liste des échantillons chargés depuis le fichier Excel")
        layout.addWidget(self._liste)

        # Connexion du bouton au signal
        self._btn_ouvrir.clicked.connect(self.ouvrir_excel_demande)

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    def charger_echantillons(self, echantillons: list[Any]) -> None:
        """
        Peuple la liste avec les échantillons fournis.

        Cette méthode sera complétée lors de l'implémentation du service
        de lecture Excel. Pour l'instant elle est un squelette vide.

        Paramètres
        ----------
        echantillons : list
            Liste d'échantillons à afficher (format à définir avec le service).
        """
        # TODO : implémenter l'affichage des échantillons
        pass  # noqa: PIE790
