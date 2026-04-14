"""
Panneau latéral de gestion des planches du projet.

Affiche la liste des planches sous forme de QListWidget et propose
des boutons pour ajouter, supprimer et réordonner les planches.
Toute communication avec la fenêtre principale passe par des signaux PyQt6 —
aucune logique métier n'est présente ici.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.constantes import MARGE_PANNEAU


class PanneauPlanches(QWidget):
    """
    Panneau gauche listant les planches du projet.

    Signaux
    -------
    planche_selectionnee(int)
        Émis lors d'un clic simple sur un item ; transmet l'index dans la liste.
    planche_ajoutee()
        Émis quand l'utilisateur clique sur « + Ajouter ».
    planche_supprimee(int)
        Émis quand l'utilisateur clique sur « − Supprimer » ; transmet l'index courant.
    planche_montee(int)
        Émis quand l'utilisateur clique sur « ↑ » ; transmet l'index avant déplacement.
    planche_descendue(int)
        Émis quand l'utilisateur clique sur « ↓ » ; transmet l'index avant déplacement.
    planche_renommee(int, str)
        Émis après confirmation d'un renommage ; transmet l'index et le nouveau nom.
    """

    # --- Signaux -----------------------------------------------------------
    planche_selectionnee = pyqtSignal(int)
    planche_ajoutee      = pyqtSignal()
    planche_supprimee    = pyqtSignal(int)
    planche_montee       = pyqtSignal(int)
    planche_descendue    = pyqtSignal(int)
    planche_renommee     = pyqtSignal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setMinimumWidth(140)

        # --- Construction de l'interface ------------------------------------
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(
            MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU
        )
        disposition.setSpacing(MARGE_PANNEAU)

        # Titre
        etiquette = QLabel("Planches")
        etiquette.setStyleSheet("font-weight: bold;")
        disposition.addWidget(etiquette)

        # Liste des planches
        self._liste = QListWidget()
        self._liste.setAlternatingRowColors(True)
        self._liste.setToolTip("Liste des planches du projet")
        disposition.addWidget(self._liste)

        # --- Rangée de boutons Ajouter / Supprimer -------------------------
        rangee_principale = QHBoxLayout()
        rangee_principale.setSpacing(MARGE_PANNEAU)

        self._btn_ajouter   = QPushButton("+ Ajouter")
        self._btn_supprimer = QPushButton("− Supprimer")

        self._btn_ajouter.setToolTip("Ajouter une nouvelle planche vide")
        self._btn_supprimer.setToolTip("Supprimer la planche sélectionnée")

        rangee_principale.addWidget(self._btn_ajouter)
        rangee_principale.addWidget(self._btn_supprimer)
        disposition.addLayout(rangee_principale)

        # --- Rangée de boutons Monter / Descendre --------------------------
        rangee_ordre = QHBoxLayout()
        rangee_ordre.setSpacing(MARGE_PANNEAU)

        self._btn_monter    = QPushButton("↑ Monter")
        self._btn_descendre = QPushButton("↓ Descendre")

        self._btn_monter.setToolTip("Remonter la planche d'un cran")
        self._btn_descendre.setToolTip("Descendre la planche d'un cran")

        rangee_ordre.addWidget(self._btn_monter)
        rangee_ordre.addWidget(self._btn_descendre)
        disposition.addLayout(rangee_ordre)

        # --- Connexions internes -------------------------------------------
        # Clic simple → sélection (via currentRowChanged pour fiabilité)
        self._liste.currentRowChanged.connect(self._sur_selection)
        # Double-clic → renommage
        self._liste.itemDoubleClicked.connect(self._sur_double_clic)

        self._btn_ajouter.clicked.connect(self.planche_ajoutee.emit)
        self._btn_supprimer.clicked.connect(self._sur_suppression)
        self._btn_monter.clicked.connect(self._sur_montee)
        self._btn_descendre.clicked.connect(self._sur_descente)

        # Drapeau interne : True pendant les mises à jour programmatiques
        # pour empêcher l'émission intempestive de planche_selectionnee
        self._mise_a_jour_en_cours: bool = False

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def rafraichir(self, planches: list) -> None:
        """
        Vide et repeuple le QListWidget à partir de la liste de planches fournie.

        Le texte de chaque item est obtenu via ``str(planche)``, ce qui exploite
        la méthode ``__str__`` du modèle ``Planche`` sans connaître sa structure interne.

        Paramètres
        ----------
        planches : list[Planche]
            Liste des planches du projet dans l'ordre d'affichage souhaité.
        """
        self._mise_a_jour_en_cours = True
        try:
            self._liste.clear()
            for planche in planches:
                item = QListWidgetItem(str(planche))
                self._liste.addItem(item)
        finally:
            self._mise_a_jour_en_cours = False

    def selectionner(self, index: int) -> None:
        """
        Sélectionne programmatiquement l'item à l'index donné sans émettre de signal.

        Paramètres
        ----------
        index : int
            Index de la planche à sélectionner (0-based).
        """
        self._mise_a_jour_en_cours = True
        try:
            self._liste.setCurrentRow(index)
        finally:
            self._mise_a_jour_en_cours = False

    # ------------------------------------------------------------------
    # Slots privés
    # ------------------------------------------------------------------

    def _sur_selection(self, index: int) -> None:
        """Émet ``planche_selectionnee`` uniquement lors d'un geste utilisateur."""
        if self._mise_a_jour_en_cours:
            return
        if index >= 0:
            self.planche_selectionnee.emit(index)

    def _sur_double_clic(self, item: QListWidgetItem) -> None:
        """Ouvre une boîte de dialogue de renommage pour l'item double-cliqué."""
        index = self._liste.row(item)
        if index < 0:
            return

        nouveau_nom, confirme = QInputDialog.getText(
            self,
            "Renommer la planche",
            "Nouveau nom de référence :",
            text=item.text(),
        )
        if confirme and nouveau_nom.strip():
            self.planche_renommee.emit(index, nouveau_nom.strip())

    def _sur_suppression(self) -> None:
        """Émet ``planche_supprimee`` avec l'index de la sélection courante."""
        index = self._liste.currentRow()
        if index >= 0:
            self.planche_supprimee.emit(index)

    def _sur_montee(self) -> None:
        """Émet ``planche_montee`` si l'item courant n'est pas déjà en tête de liste."""
        index = self._liste.currentRow()
        if index > 0:
            self.planche_montee.emit(index)

    def _sur_descente(self) -> None:
        """Émet ``planche_descendue`` si l'item courant n'est pas en fin de liste."""
        index = self._liste.currentRow()
        if index >= 0 and index < self._liste.count() - 1:
            self.planche_descendue.emit(index)
