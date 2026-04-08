"""
Panneau latéral gauche : gestion de la liste des planches du projet.

Ce module définit la classe `PanneauPlanches` qui permet à l'utilisateur
d'ajouter et de supprimer des planches (pages de légende). La logique
de création et de persistance des planches est déléguée aux services.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.constantes import MARGE_PANNEAU


class PanneauPlanches(QWidget):
    """
    Panneau de gestion de la liste des planches.

    Signaux
    -------
    planche_ajoutee : pyqtSignal()
        Émis lorsque l'utilisateur demande l'ajout d'une nouvelle planche.
    planche_supprimee : pyqtSignal(int)
        Émis lorsque l'utilisateur demande la suppression de la planche
        dont l'index (ligne dans la liste) est fourni en paramètre.
    """

    planche_ajoutee = pyqtSignal()
    planche_supprimee = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # --- Mise en page verticale ----------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU)
        layout.setSpacing(MARGE_PANNEAU)

        # En-tête du panneau
        label_titre = QLabel("Planches")
        label_titre.setStyleSheet("font-weight: bold;")
        layout.addWidget(label_titre)

        # Liste scrollable des planches
        self._liste = QListWidget()
        self._liste.setToolTip("Liste des planches du projet")
        layout.addWidget(self._liste)

        # --- Boutons Ajouter / Supprimer -----------------------------------
        layout_boutons = QHBoxLayout()
        layout_boutons.setSpacing(MARGE_PANNEAU)

        self._btn_ajouter = QPushButton("+ Ajouter")
        self._btn_ajouter.setToolTip("Ajouter une nouvelle planche")
        layout_boutons.addWidget(self._btn_ajouter)

        self._btn_supprimer = QPushButton("- Supprimer")
        self._btn_supprimer.setToolTip("Supprimer la planche sélectionnée")
        layout_boutons.addWidget(self._btn_supprimer)

        layout.addLayout(layout_boutons)

        # --- Connexions des signaux ----------------------------------------
        self._btn_ajouter.clicked.connect(self.planche_ajoutee)
        self._btn_supprimer.clicked.connect(self._on_supprimer_clique)

    # ------------------------------------------------------------------
    # Slots privés
    # ------------------------------------------------------------------

    def _on_supprimer_clique(self) -> None:
        """
        Émet `planche_supprimee` avec l'index de la planche sélectionnée.
        Si aucune planche n'est sélectionnée, l'index vaut -1.
        """
        index = self._liste.currentRow()
        self.planche_supprimee.emit(index)
